import os
import sys
import subprocess
import tempfile
import time
import re


def clean_output(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\r', '', text)
    return text.strip()


from .platform_utils import (
    is_windows, is_linux, is_macos,
    get_miniconda_download_url, get_anaconda_download_url,
    get_git_download_url, get_default_install_path,
    get_conda_exe_name, get_conda_scripts_dir, get_home_dir,
    normalize_path, is_admin, run_as_admin,
    save_conda_install_path
)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


MINICONDA_VERSIONS = [
    'latest',
    'py312_24.11.1-0',
    'py311_24.7.1-0',
    'py310_24.3.0-0',
    'py39_23.11.0-2',
]

ANACONDA_VERSIONS = [
    '2024.10-1',
    '2024.06-1',
    '2023.09-0',
    '2023.07-2',
    '2023.03-1',
]

GIT_VERSIONS = [
    '2.49.0',
    '2.48.1',
    '2.47.0',
    '2.46.0',
    '2.45.0',
]


def _build_miniconda_urls(version='latest'):
    filename = get_miniconda_download_url(version)
    base_urls = [
        ('清华镜像', 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda'),
        ('中科大镜像', 'https://mirrors.ustc.edu.cn/anaconda/miniconda'),
        ('阿里镜像', 'https://mirrors.aliyun.com/anaconda/miniconda'),
        ('华为云镜像', 'https://mirrors.huaweicloud.com/anaconda/miniconda'),
        ('南京大学镜像', 'https://mirrors.nju.edu.cn/anaconda/miniconda'),
        ('官方源', 'https://repo.anaconda.com/miniconda'),
    ]
    return [(name, f'{base}/{filename}') for name, base in base_urls]


def _build_anaconda_urls(version='2024.10-1'):
    filename = get_anaconda_download_url(version)
    base_urls = [
        ('清华镜像', 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/archive'),
        ('中科大镜像', 'https://mirrors.ustc.edu.cn/anaconda/archive'),
        ('阿里镜像', 'https://mirrors.aliyun.com/anaconda/archive'),
        ('华为云镜像', 'https://mirrors.huaweicloud.com/anaconda/archive'),
        ('南京大学镜像', 'https://mirrors.nju.edu.cn/anaconda/archive'),
        ('官方源', 'https://repo.anaconda.com/archive'),
    ]
    return [(name, f'{base}/{filename}') for name, base in base_urls]


def _build_git_urls(version='2.49.0'):
    if is_windows():
        ver_tag = f'v{version}.windows.1'
        filename = f'Git-{version}-64-bit.exe'
        base_urls = [
            ('淘宝镜像', f'https://registry.npmmirror.com/-/binary/git-for-windows/{ver_tag}'),
            ('华为云镜像', f'https://mirrors.huaweicloud.com/git-for-windows/{ver_tag}'),
            ('清华镜像', f'https://mirrors.tuna.tsinghua.edu.cn/github-release/git-for-windows/git/{ver_tag}'),
            ('中科大镜像', f'https://mirrors.ustc.edu.cn/github-release/git-for-windows/git/{ver_tag}'),
            ('GitHub 官方', f'https://github.com/git-for-windows/git/releases/download/{ver_tag}'),
        ]
        return [(name, f'{base}/{filename}') for name, base in base_urls]
    else:
        return []


MAX_RETRY_PER_SOURCE = 3
DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT = 30


def _download_with_requests(url, save_path, progress_callback=None, log=None):
    try:
        session = requests.Session()
        session.verify = False
        requests.packages.urllib3.disable_warnings()

        downloaded = 0
        total_size = 0

        if os.path.exists(save_path):
            downloaded = os.path.getsize(save_path)

        headers = {}
        if downloaded > 0:
            headers['Range'] = f'bytes={downloaded}-'

        response = session.get(url, stream=True, headers=headers, timeout=DOWNLOAD_TIMEOUT)

        if response.status_code in (200, 206):
            if 'Content-Length' in response.headers:
                total_size = int(response.headers['Content-Length'])
                if downloaded > 0 and response.status_code == 206:
                    total_size += downloaded

            mode = 'ab' if downloaded > 0 and response.status_code == 206 else 'wb'
            with open(save_path, mode) as f:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(percent, downloaded, total_size)

            return True
        else:
            if log:
                log(f'  HTTP 状态码: {response.status_code}')
            return False
    except Exception as e:
        if log:
            log(f'  下载错误: {e}')
        return False


def _download_with_urllib(url, save_path, progress_callback=None, log=None):
    try:
        import urllib.request
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url)
        downloaded = 0
        total_size = 0

        if os.path.exists(save_path):
            downloaded = os.path.getsize(save_path)
            if downloaded > 0:
                req.add_header('Range', f'bytes={downloaded}-')

        response = urllib.request.urlopen(req, context=ctx, timeout=DOWNLOAD_TIMEOUT)

        if response.status in (200, 206):
            content_length = response.getheader('Content-Length')
            if content_length:
                total_size = int(content_length)
                if downloaded > 0 and response.status == 206:
                    total_size += downloaded

            mode = 'ab' if downloaded > 0 and response.status == 206 else 'wb'
            with open(save_path, mode) as f:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        percent = (downloaded / total_size) * 100
                        progress_callback(percent, downloaded, total_size)

            return True
        else:
            if log:
                log(f'  HTTP 状态码: {response.status}')
            return False
    except Exception as e:
        if log:
            log(f'  下载错误: {e}')
        return False


def download_file_with_fallback(url_list, save_path, progress_callback=None, log=None):
    for source_idx, (source_name, url) in enumerate(url_list):
        if log:
            log(f'正在从 {source_name} 下载...')

        for retry in range(MAX_RETRY_PER_SOURCE):
            tmp_path = save_path + '.tmp'

            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except:
                    pass

            if HAS_REQUESTS:
                success = _download_with_requests(url, tmp_path, progress_callback, log)
            else:
                success = _download_with_urllib(url, tmp_path, progress_callback, log)

            if success and os.path.exists(tmp_path):
                file_size = os.path.getsize(tmp_path)
                if file_size > 1024 * 1024:
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                        except:
                            pass
                    os.rename(tmp_path, save_path)
                    if log:
                        log(f'✅ 从 {source_name} 下载成功 ({file_size / (1024*1024):.1f} MB)')
                    return True
                else:
                    if log:
                        log(f'  ⚠️ 文件过小 ({file_size} 字节)，重试')
            else:
                if log and retry < MAX_RETRY_PER_SOURCE - 1:
                    log(f'  下载失败，{MAX_RETRY_PER_SOURCE - retry - 1} 次重试机会')

            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

        if log and source_idx < len(url_list) - 1:
            log(f'  {source_name} 下载失败，切换到下一个下载源...')

    if os.path.exists(save_path + '.tmp'):
        try:
            os.remove(save_path + '.tmp')
        except:
            pass

    return False


def _check_conda_installed(install_path):
    conda_exe = get_conda_exe_name()
    scripts_dir = get_conda_scripts_dir(install_path)
    conda_path = os.path.join(scripts_dir, conda_exe)
    return os.path.exists(conda_path)


def _configure_linux_shell(conda_path, log=None):
    home = get_home_dir()
    shell_configs = [
        os.path.join(home, '.bashrc'),
        os.path.join(home, '.bash_profile'),
        os.path.join(home, '.zshrc'),
    ]

    conda_bin_dir = os.path.dirname(conda_path)
    path_line = f'export PATH="{conda_bin_dir}:$PATH"'

    for config_file in shell_configs:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if path_line not in content:
                    with open(config_file, 'a', encoding='utf-8') as f:
                        f.write(f'\n# YOLO-AutoInstaller: Added Conda to PATH\n{path_line}\n')
                    if log:
                        log(f'📝 已更新 {config_file}')
            except Exception as e:
                if log:
                    log(f'⚠  更新 {config_file} 失败: {e}')

    init_line = f'eval "$({conda_path} shell.$(basename "$SHELL") hook)"'
    for config_file in shell_configs:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if init_line not in content and 'conda init' not in content:
                    with open(config_file, 'a', encoding='utf-8') as f:
                        f.write(f'\n# YOLO-AutoInstaller: Conda initialization\n{init_line}\n')
                    if log:
                        log(f'📝 已添加 Conda 初始化到 {config_file}')
            except Exception as e:
                if log:
                    log(f'⚠  添加初始化到 {config_file} 失败: {e}')

    if log:
        log('💡 注意：重启终端或执行 `source ~/.bashrc` 后即可使用 conda 命令')


def install_conda(conda_type='miniconda', version=None, install_path=None, progress_log=None):
    def log(msg):
        if progress_log:
            progress_log(msg)
        print(msg)

    if conda_type == 'anaconda':
        display_name = 'Anaconda3'
        default_folder = 'Anaconda3'
        if version is None:
            version = ANACONDA_VERSIONS[0]
        url_list = _build_anaconda_urls(version)
    else:
        display_name = 'Miniconda3'
        default_folder = 'Miniconda3'
        if version is None:
            version = MINICONDA_VERSIONS[0]
        url_list = _build_miniconda_urls(version)

    if install_path is None:
        install_path = get_default_install_path(conda_type)

    install_path = normalize_path(install_path)

    log(f'=== 开始安装 {display_name} ({version}) ===')
    log(f'安装路径: {install_path}')

    if _check_conda_installed(install_path):
        log(f'{display_name} 已安装，跳过')
        return True, install_path

    if not url_list:
        log(f'❌ 当前平台不支持自动安装 {display_name}')
        return False, None

    log(f'正在下载 {display_name} 安装包（多个下载源自动切换）...')

    if is_windows():
        suffix = '.exe'
    else:
        suffix = '.sh'

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        def progress_cb(percent, downloaded, total_size):
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            log(f'下载进度: {percent:.1f}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)')

        success = download_file_with_fallback(url_list, tmp_path, progress_cb, log)
        if not success:
            log(f'❌ 下载 {display_name} 失败，所有下载源均不可用')
            log(f'请手动下载安装：')
            for source_name, url in url_list:
                log(f'  {source_name}: {url}')
            return False, None

        log(f'正在安装 {display_name}（静默安装，可能需要几分钟到十几分钟）...')
        log('安装过程中请耐心等待，请勿关闭程序')
        if conda_type == 'anaconda':
            log('注意：Anaconda 体积较大，安装时间较长，请耐心等待')

        parent_dir = os.path.dirname(install_path)
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
                log(f'创建安装目录: {parent_dir}')
            except Exception as e:
                log(f'⚠  创建目录失败: {e}')
                return False, None

        writable = False
        try:
            if os.path.exists(install_path):
                test_file = os.path.join(install_path, '.write_test_' + str(os.getpid()))
            else:
                test_file = os.path.join(parent_dir, '.write_test_' + str(os.getpid()))
            with open(test_file, 'w') as f:
                f.write('test')
            os.unlink(test_file)
            writable = True
            log(f'✅ 安装目录可写: {parent_dir}')
        except Exception as e:
            if is_windows():
                log(f'⚠  安装目录写入测试失败: {e}')
                log('注意：Windows 系统盘可能需要管理员权限，安装程序会自动请求权限')
                log('将继续尝试安装，如果失败请更换安装路径')
                writable = True
            else:
                log(f'❌ 安装目录不可写: {e}')
                log('请更换安装路径或检查权限')
                return False, None

        if not is_windows():
            try:
                import shutil
                total, used, free = shutil.disk_usage(parent_dir)
                free_gb = free / (1024 ** 3)
                required_gb = 5 if conda_type == 'anaconda' else 2
                log(f'💾 磁盘剩余空间: {free_gb:.1f} GB (需要约 {required_gb} GB)')
                if free_gb < required_gb:
                    log(f'❌ 磁盘空间不足！至少需要 {required_gb} GB')
                    return False, None
            except Exception as e:
                log(f'⚠  无法检测磁盘空间: {e}')
        else:
            try:
                import shutil
                total, used, free = shutil.disk_usage(parent_dir)
                free_gb = free / (1024 ** 3)
                required_gb = 5 if conda_type == 'anaconda' else 2
                log(f'💾 磁盘剩余空间: {free_gb:.1f} GB (需要约 {required_gb} GB)')
                if free_gb < required_gb:
                    log(f'❌ 磁盘空间不足！至少需要 {required_gb} GB')
                    return False, None
            except Exception as e:
                log(f'⚠  无法检测磁盘空间: {e}')

        if is_windows():
            cmd = f'"{tmp_path}" /S /AddToPath=0 /RegisterPython=0 /D={install_path}'
            timeout = 1200 if conda_type == 'anaconda' else 600
        else:
            os.chmod(tmp_path, 0o755)
            log(f'安装脚本: {tmp_path}')
            log(f'目标路径: {install_path}')
            cmd = f'bash "{tmp_path}" -b -p "{install_path}"'
            timeout = 1200 if conda_type == 'anaconda' else 600

        log(f'执行安装命令... (超时: {timeout}秒)')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            timeout=timeout
        )

        stdout = clean_output(result.stdout) if result.stdout else ''
        stderr = clean_output(result.stderr) if result.stderr else ''

        log(f'安装进程结束，返回码: {result.returncode}')

        if _check_conda_installed(install_path):
            log(f'✅ {display_name} 安装成功！')
            conda_exe_path = os.path.join(install_path, 'Scripts' if is_windows() else 'bin', 'conda.exe' if is_windows() else 'conda')
            if os.path.exists(conda_exe_path):
                save_conda_install_path(conda_exe_path)
                log(f'📋 已保存 Conda 安装路径: {conda_exe_path}')

            if not is_windows():
                _configure_linux_shell(conda_exe_path, log)

            return True, install_path
        else:
            if is_windows() and not is_admin() and not writable:
                log(f'⚠️  普通权限安装失败，正在尝试以管理员权限安装...')
                log('📢 即将弹出 UAC 权限请求，请点击"是"继续')
                time.sleep(1)

                admin_result = run_as_admin(cmd, wait=True, timeout=timeout)

                if admin_result['returncode'] == 0 and _check_conda_installed(install_path):
                    log(f'✅ {display_name} 安装成功！（管理员权限）')
                    conda_exe_path = os.path.join(install_path, 'Scripts' if is_windows() else 'bin', 'conda.exe' if is_windows() else 'conda')
                    if os.path.exists(conda_exe_path):
                        save_conda_install_path(conda_exe_path)
                        log(f'📋 已保存 Conda 安装路径: {conda_exe_path}')

                        if not is_windows():
                            _configure_linux_shell(conda_exe_path, log)

                        return True, install_path
                    else:
                        log(f'❌ {display_name} 管理员权限安装也失败')
                        log(f'返回码: {admin_result["returncode"]}')
                        if admin_result['stderr']:
                            log(f'错误信息: {clean_output(admin_result["stderr"])}')
                        return False, None

            log(f'❌ {display_name} 安装失败')
            log(f'返回码: {result.returncode}')
            all_output = ''
            if stdout:
                all_output += '=== 标准输出 ===\n' + stdout
            if stderr:
                all_output += '\n=== 错误输出 ===\n' + stderr
            if all_output:
                log(f'安装日志:\n{all_output[-2000:]}')
            else:
                log('安装进程没有任何输出')

            if os.path.exists(install_path):
                log(f'⚠  安装目录已存在但 conda 不可用，目录内容:')
                try:
                    items = os.listdir(install_path)
                    for item in items[:20]:
                        log(f'  - {item}')
                    if len(items) > 20:
                        log(f'  ... 共 {len(items)} 项')
                except Exception as e:
                    log(f'  无法列出目录: {e}')

            return False, None
    except subprocess.TimeoutExpired:
        log('❌ 安装超时')
        return False, None
    except Exception as e:
        log(f'❌ 安装异常: {e}')
        return False, None
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def install_miniconda(install_path=None, progress_log=None):
    return install_conda('miniconda', install_path=install_path, progress_log=progress_log)


def install_anaconda(install_path=None, progress_log=None):
    return install_conda('anaconda', install_path=install_path, progress_log=progress_log)


def _check_git_installed():
    try:
        result = subprocess.run(
            'git --version',
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout.strip()
    except:
        return False, ''


def _install_git_linux(log):
    is_root = (os.geteuid() == 0) if hasattr(os, 'geteuid') else False

    package_managers = []

    if is_root:
        package_managers = [
            ('apt (Debian/Ubuntu)', 'apt-get update && apt-get install -y git', 'apt-get'),
            ('yum (CentOS/RHEL)', 'yum install -y git', 'yum'),
            ('dnf (Fedora)', 'dnf install -y git', 'dnf'),
            ('pacman (Arch)', 'pacman -S --noconfirm git', 'pacman'),
            ('zypper (openSUSE)', 'zypper install -y git', 'zypper'),
        ]
    else:
        package_managers = [
            ('apt (Debian/Ubuntu)', 'sudo -n apt-get update && sudo -n apt-get install -y git', 'apt-get'),
            ('yum (CentOS/RHEL)', 'sudo -n yum install -y git', 'yum'),
            ('dnf (Fedora)', 'sudo -n dnf install -y git', 'dnf'),
            ('pacman (Arch)', 'sudo -n pacman -S --noconfirm git', 'pacman'),
            ('zypper (openSUSE)', 'sudo -n zypper install -y git', 'zypper'),
        ]

    for pm_name, pm_cmd, pm_check in package_managers:
        try:
            check = subprocess.run(
                f'which {pm_check}',
                capture_output=True,
                shell=True,
                timeout=5
            )
            if check.returncode == 0:
                log(f'检测到 {pm_name}，正在安装 Git...')
                if not is_root:
                    log('注意：需要管理员权限，正在尝试免密 sudo...')
                result = subprocess.run(
                    pm_cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    shell=True,
                    timeout=300
                )
                if result.returncode == 0:
                    return True
                else:
                    err_msg = result.stderr[-300:] if result.stderr else result.stdout[-300:]
                    if 'password' in err_msg.lower() or 'sudo:' in err_msg:
                        log('需要管理员密码，无法自动安装')
                    else:
                        log(f'{pm_name} 安装失败: {err_msg}')
        except Exception as e:
            log(f'{pm_name} 尝试失败: {e}')
            continue

    return False


def install_git(version=None, progress_log=None):
    def log(msg):
        if progress_log:
            progress_log(msg)
        print(msg)

    if version is None:
        version = GIT_VERSIONS[0]

    log(f'=== 开始安装 Git ===')

    git_ok, git_ver = _check_git_installed()
    if git_ok:
        log(f'Git 已安装: {git_ver}')
        return True

    if is_linux():
        log('Linux 系统，尝试使用包管理器安装 Git...')
        success = _install_git_linux(log)
        if success:
            git_ok2, git_ver2 = _check_git_installed()
            if git_ok2:
                log(f'✅ Git 安装成功: {git_ver2}')
                return True
        log('❌ 自动安装失败，请手动安装 Git:')
        log('  Debian/Ubuntu: sudo apt-get install git')
        log('  CentOS/RHEL: sudo yum install git')
        log('  Fedora: sudo dnf install git')
        return False

    if not is_windows():
        log('❌ 当前平台不支持自动安装 Git')
        log('请手动安装 Git 并确保在 PATH 中可用')
        return False

    log('正在下载 Git 安装包（多个下载源自动切换）...')

    with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        def progress_cb(percent, downloaded, total_size):
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            log(f'下载进度: {percent:.1f}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)')

        git_urls = _build_git_urls(version)
        success = download_file_with_fallback(git_urls, tmp_path, progress_cb, log)
        if not success:
            log('下载 Git 失败，所有下载源均不可用')
            log('尝试使用 winget 安装...')
            winget_ok = _install_git_winget(log)
            if winget_ok:
                return True
            log('❌ Git 自动安装失败')
            log('请手动下载安装：')
            for source_name, url in git_urls:
                log(f'  {source_name}: {url}')
            return False

        log('正在安装 Git（静默安装，可能需要几分钟）...')

        cmd = f'"{tmp_path}" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS="icons,ext\\reg\\shellhere,assoc,assoc_sh"'
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            timeout=600
        )

        time.sleep(2)

        git_ok2, git_ver2 = _check_git_installed()
        if git_ok2:
            log(f'✅ Git 安装成功: {git_ver2}')
            return True
        else:
            log('安装完成但 git 命令未找到，可能需要重启后生效')
            log('尝试在常见路径查找...')
            common_paths = [
                r'C:\Program Files\Git\bin\git.exe',
                r'C:\Program Files (x86)\Git\bin\git.exe',
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Git', 'bin', 'git.exe'),
            ]
            for p in common_paths:
                if os.path.exists(p):
                    log(f'在 {p} 找到 Git，安装成功')
                    return True
            log('❌ Git 安装验证失败')
            return False
    except subprocess.TimeoutExpired:
        log('❌ 安装超时')
        return False
    except Exception as e:
        log(f'❌ 安装异常: {e}')
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def _install_git_winget(log):
    try:
        log('尝试使用 winget 安装 Git...')
        result = subprocess.run(
            'winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements --silent',
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            timeout=600
        )
        if result.returncode == 0:
            log('✅ winget Git 安装完成')
            return True
        else:
            log(f'winget 安装失败: {result.stderr[-300:] if result.stderr else result.stdout[-300:]}')
            return False
    except Exception as e:
        log(f'winget 安装异常: {e}')
        return False


def install_all(conda_type='miniconda', conda_version=None, git_version=None, conda_install_path=None, progress_log=None):
    def log(msg):
        if progress_log:
            progress_log(msg)
        print(msg)

    conda_display = 'Anaconda3' if conda_type == 'anaconda' else 'Miniconda3'

    log('=' * 50)
    log('开始自动安装运行环境')
    log('=' * 50)

    results = {}

    log('\n--- 第 1 步：安装 Git ---')
    git_ok = install_git(version=git_version, progress_log=log)
    results['git'] = git_ok

    log(f'\n--- 第 2 步：安装 {conda_display} ---')
    conda_ok, conda_path = install_conda(
        conda_type=conda_type,
        version=conda_version,
        install_path=conda_install_path,
        progress_log=log
    )
    results['conda'] = conda_ok
    results['conda_path'] = conda_path
    results['conda_type'] = conda_type

    log('\n' + '=' * 50)
    log('环境安装完成')
    log('=' * 50)

    if git_ok and conda_ok:
        log('✅ 所有环境安装成功！')
        if is_windows():
            log('提示：Git 可能需要重启电脑后才能在命令行中使用')
    else:
        log('⚠️ 部分环境安装失败，请查看上方日志')

    return results


if __name__ == '__main__':
    results = install_all()
    print(f'\n结果: {results}')
