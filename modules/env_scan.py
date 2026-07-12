import os
import subprocess
import sys
from .platform_utils import (
    get_conda_search_paths, get_gpu_check_cmd, is_windows
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

    # Linux/macOS 下额外扫描 home 目录
    if not is_windows():
        home = os.path.expanduser('~')
        if os.path.isdir(home):
            try:
                for item in os.listdir(home):
                    item_lower = item.lower()
                    if any(keyword in item_lower for keyword in ['conda', 'anaconda', 'miniconda', 'miniforge', 'mambaforge']):
                        full_path = os.path.join(home, item, 'bin', 'conda')
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
    else:
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


if __name__ == '__main__':
    result = scan_environment()
    print(result['log'])
    print(f'\nConda路径: {result["conda_path"]}')
    print(f'Git可用: {result["git_available"]}')
    print(f'有GPU: {result["has_gpu"]}')
