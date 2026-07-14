import os
import subprocess
import sys
from .platform_utils import (
    get_conda_search_paths, get_gpu_check_cmd, is_windows, is_linux,
    load_conda_install_path
)


def run_command(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            shell=True
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': f'命令执行超时（{timeout}秒）',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }


def find_conda():
    log_lines = []
    log_lines.append('[环境扫描] 正在查找 Conda 安装路径...')

    saved_path = load_conda_install_path()
    if saved_path:
        log_lines.append(f'[环境扫描] 找到保存的 Conda 路径: {saved_path}')
        verify = run_command(f'"{saved_path}" --version')
        if verify['success']:
            log_lines.append(f'[环境扫描] Conda 版本验证通过: {verify["stdout"]}')
            return saved_path, log_lines
        else:
            log_lines.append(f'[环境扫描] 保存的路径验证失败，尝试扫描其他位置')

    common_paths = get_conda_search_paths()

    for path in common_paths:
        if os.path.exists(path):
            log_lines.append(f'[环境扫描] 在 {path} 找到 Conda')
            verify = run_command(f'"{path}" --version')
            if verify['success']:
                log_lines.append(f'[环境扫描] Conda 版本验证通过: {verify["stdout"]}')
                return path, log_lines
            else:
                log_lines.append(f'[环境扫描] Conda 路径存在但无法执行: {verify["stderr"]}')

    if not is_windows():
        home = os.path.expanduser('~')
        search_bases = [home, '/opt', '/usr/local']
        conda_keywords = ['conda', 'anaconda', 'miniconda', 'miniforge', 'mambaforge']
        for base in search_bases:
            if not os.path.isdir(base):
                continue
            try:
                for item in os.listdir(base):
                    item_lower = item.lower()
                    if any(kw in item_lower for kw in conda_keywords):
                        full_path = os.path.join(base, item, 'bin', 'conda')
                        if os.path.exists(full_path):
                            log_lines.append(f'[环境扫描] 在 {full_path} 找到 Conda')
                            verify = run_command(f'"{full_path}" --version')
                            if verify['success']:
                                log_lines.append(f'[环境扫描] Conda 版本验证通过: {verify["stdout"]}')
                                return full_path, log_lines
            except Exception:
                pass

    log_lines.append('[环境扫描] 正在检查系统 PATH 环境变量...')
    if is_windows():
        path_check = run_command('where conda')
    else:
        path_check = run_command('which conda')
    if path_check['success']:
        conda_path = path_check['stdout'].split('\n')[0].strip()
        if conda_path and os.path.exists(conda_path):
            log_lines.append(f'[环境扫描] 在 PATH 中找到 Conda: {conda_path}')
            return conda_path, log_lines

    log_lines.append('[环境扫描] 未检测到 Conda，请先安装 Miniconda3 或 Anaconda')
    return None, log_lines


def check_git():
    log_lines = []
    log_lines.append('[环境扫描] 正在检测 Git...')

    result = run_command('git --version')
    if result['success']:
        log_lines.append(f'[环境扫描] Git 已安装: {result["stdout"]}')
        return True, log_lines

    if is_linux():
        linux_git_paths = [
            '/usr/bin/git',
            '/usr/local/bin/git',
            '/bin/git',
            '/snap/bin/git',
        ]
        for gpath in linux_git_paths:
            if os.path.exists(gpath):
                ver_result = run_command(f'"{gpath}" --version')
                if ver_result['success']:
                    log_lines.append(f'[环境扫描] Git 已安装: {ver_result["stdout"]}')
                    log_lines.append(f'[环境扫描] Git 路径: {gpath}')
                    return True, log_lines

    log_lines.append('[环境扫描] 未检测到 Git，请先安装 Git 并配置环境变量')
    return False, log_lines


def check_nvidia_gpu():
    log_lines = []
    log_lines.append('[环境扫描] 正在检测 NVIDIA 显卡...')

    gpu_cmd = get_gpu_check_cmd()
    result = run_command(gpu_cmd)
    if result['success']:
        log_lines.append('[环境扫描] 检测到 NVIDIA 独立显卡')
        lines = result['stdout'].split('\n')
        for line in lines:
            if 'Driver Version' in line or 'CUDA Version' in line:
                log_lines.append(f'[环境扫描] {line.strip()}')
                break
        return True, log_lines
    else:
        log_lines.append('[环境扫描] 未检测到 NVIDIA 显卡，将使用 CPU 模式')
        return False, log_lines


def scan_environment():
    log_lines = []
    log_lines.append('=' * 60)
    log_lines.append('开始系统环境扫描')
    log_lines.append('=' * 60)

    conda_path, conda_log = find_conda()
    log_lines.extend(conda_log)

    git_available, git_log = check_git()
    log_lines.extend(git_log)

    has_gpu, gpu_log = check_nvidia_gpu()
    log_lines.extend(gpu_log)

    log_lines.append('=' * 60)
    log_lines.append('环境扫描完成')
    log_lines.append('=' * 60)

    return {
        'conda_path': conda_path,
        'git_available': git_available,
        'has_gpu': has_gpu,
        'log': '\n'.join(log_lines)
    }


def global_scan_conda():
    log_lines = []
    log_lines.append('=' * 60)
    log_lines.append('开始全局扫描 Conda')
    log_lines.append('=' * 60)

    conda_path = None

    if is_windows():
        log_lines.append('[全局扫描] 正在扫描所有磁盘分区...')
        import string
        import ctypes
        DRIVE_FIXED = 3
        drives = []
        for letter in string.ascii_uppercase:
            drive = f'{letter}:'
            if os.path.exists(drive):
                try:
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(f'{drive}\\')
                    if drive_type == DRIVE_FIXED:
                        drives.append(drive)
                    else:
                        log_lines.append(f'[全局扫描] 跳过非本地磁盘: {drive}')
                except Exception:
                    drives.append(drive)

        log_lines.append(f'[全局扫描] 发现 {len(drives)} 个本地磁盘: {", ".join(drives)}')

        for drive in drives:
            log_lines.append(f'[全局扫描] 正在扫描 {drive}...')
            try:
                result = subprocess.run(
                    f'where /R {drive} conda.exe',
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    shell=True,
                    timeout=120
                )
                if result.returncode == 0 and result.stdout:
                    paths = result.stdout.strip().split('\n')
                    for path in paths:
                        path = path.strip()
                        if path and os.path.exists(path):
                            verify = run_command(f'"{path}" --version')
                            if verify['success']:
                                log_lines.append(f'[全局扫描] ✅ 在 {path} 找到 Conda')
                                log_lines.append(f'[全局扫描] Conda 版本: {verify["stdout"]}')
                                conda_path = path
                                break
                    if conda_path:
                        break
            except subprocess.TimeoutExpired:
                log_lines.append(f'[全局扫描] ⚠️  {drive} 扫描超时，跳过')
            except Exception as e:
                log_lines.append(f'[全局扫描] ⚠️  扫描 {drive} 时出错: {e}')
    else:
        log_lines.append('[全局扫描] 正在扫描 Linux 系统...')
        try:
            result = subprocess.run(
                'find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -path /run -prune -o -name conda -type f -print 2>/dev/null',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                timeout=300
            )
            if result.returncode == 0 and result.stdout:
                paths = result.stdout.strip().split('\n')
                for path in paths:
                    path = path.strip()
                    if path and os.path.exists(path):
                        verify = run_command(f'"{path}" --version')
                        if verify['success']:
                            log_lines.append(f'[全局扫描] ✅ 在 {path} 找到 Conda')
                            log_lines.append(f'[全局扫描] Conda 版本: {verify["stdout"]}')
                            conda_path = path
                            break
        except subprocess.TimeoutExpired:
            log_lines.append('[全局扫描] ⚠️  扫描超时')
        except Exception as e:
            log_lines.append(f'[全局扫描] ⚠️  扫描时出错: {e}')

    log_lines.append('=' * 60)
    if conda_path:
        log_lines.append('全局扫描完成 - 找到 Conda！')
    else:
        log_lines.append('全局扫描完成 - 未找到 Conda')
    log_lines.append('=' * 60)

    return conda_path, '\n'.join(log_lines)


if __name__ == '__main__':
    result = scan_environment()
    print(result['log'])
    print(f'\nConda路径: {result["conda_path"]}')
    print(f'Git可用: {result["git_available"]}')
    print(f'有GPU: {result["has_gpu"]}')
