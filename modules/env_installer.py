import os
import sys
import subprocess
import tempfile
import time
import re
import shutil


def clean_output(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\r', '', text)
    return text.strip()


from .platform_utils import (
    is_windows, is_linux,
    get_miniconda_download_url, get_anaconda_download_url,
    get_default_install_path,
    get_conda_exe_name, get_conda_scripts_dir, get_home_dir,
    normalize_path, is_admin, run_as_admin,
    save_conda_install_path,
    load_conda_install_path, get_conda_search_paths,
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
        ('官方源', 'https://repo.anaconda.com/miniconda'),
    ]
    return [(name, f'{base}/{filename}') for name, base in base_urls]


def _build_anaconda_urls(version='2024.10-1'):
    filename = get_anaconda_download_url(version)
    base_urls = [
        ('北京大学镜像', 'https://mirrors.pku.edu.cn/anaconda/archive'),
        ('清华镜像', 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/archive'),
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
        if version is None:
            version = ANACONDA_VERSIONS[0]
        url_list = _build_anaconda_urls(version)
    else:
        display_name = 'Miniconda3'
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

    # 先检查本地安装包
    local_installer = None
    is_temp_file = True
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(os.path.dirname(sys.executable), f'{display_name}-installer.exe'),
            os.path.join(base_dir, '..', 'assets', f'{display_name}-installer.exe'),
            os.path.join(base_dir, '..', 'assets', f'{display_name}-installer.sh'),
        ]
        for p in candidates:
            p = os.path.normpath(p)
            if os.path.exists(p):
                local_installer = p
                log(f'发现本地 {display_name} 安装包: {p}')
                break
    except Exception:
        pass

    if local_installer:
        tmp_path = local_installer
        is_temp_file = False
        log('使用本地安装包进行安装...')
    else:
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
            log('请手动下载安装：')
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
        write_test_failed = False
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
                write_test_failed = True
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
            if is_windows() and not is_admin() and (not writable or write_test_failed):
                log('⚠️  普通权限安装失败，正在尝试以管理员权限安装...')
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
                log('⚠  安装目录已存在但 conda 不可用，目录内容:')
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
        if is_temp_file:
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


def _find_conda_exe(log=None):
    """查找 conda 可执行文件路径。

    优先使用已保存的安装记录和常见安装路径，而不是仅依赖 PATH
    （Anaconda 刚装好时当前进程的 PATH 可能尚未刷新）。
    """
    # 1. 已保存的安装记录
    saved = load_conda_install_path()
    if saved and os.path.exists(saved):
        if log:
            log(f'  找到已保存的 conda 路径: {saved}')
        return saved

    # 2. 常见安装路径
    for p in get_conda_search_paths():
        if os.path.exists(p):
            if log:
                log(f'  在常见路径找到 conda: {p}')
            return p

    # 3. PATH（最后才检查）
    found = shutil.which('conda')
    if found:
        if log:
            log(f'  在 PATH 中找到 conda: {found}')
        return found

    return None


def install_git(version=None, progress_log=None):
    def log(msg):
        if progress_log:
            progress_log(msg)
        print(msg)

    if version is None:
        version = GIT_VERSIONS[0]

    log('=== 开始安装 Git ===')

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

    # 1) winget（若系统已安装，这是最干净的方式）
    log('尝试使用 winget 安装 Git...')
    winget_exe = _find_winget_exe()
    if winget_exe and _winget_install_git(log, winget_exe):
        return True

    # 2) 国内镜像下载官方 Git 完整安装包（阿里 npmmirror CDN，速度快、无需 winget）
    log('winget 不可用，从国内镜像（npmmirror）下载官方 Git 安装包...')
    if _install_git_from_npmmirror(log):
        return True

    # 3) 用户要求：没有 winget 就自动安装 winget，再用 winget 安装 Git
    log('镜像安装失败，尝试自动安装 winget 后再安装 Git...')
    new_winget = _install_winget(log)
    if new_winget and _winget_install_git(log, new_winget):
        return True

    # 4) 通过 Conda 安装（优先 defaults 走已配置的国内镜像，失败再试 tuna conda-forge）
    log('尝试通过 Conda 安装 Git...')
    if _install_git_conda(log):
        return True

    # 5) 最后兜底：检查本地是否放了 Git 安装包
    if _install_git_local(log):
        return True

    log('❌ Git 自动安装失败，请手动安装 Git 后重试')
    log('官网下载: https://git-scm.com/download/win')
    return False


def _find_winget_exe():
    """查找 winget 可执行文件路径（可能在 WindowsApps 中但不在 PATH 里）。"""
    # 1. PATH
    found = shutil.which('winget')
    if found:
        return found
    # 2. WindowsApps 常见路径
    home = get_home_dir()
    candidates = [
        os.path.join(home, 'AppData', 'Local', 'Microsoft', 'WindowsApps', 'winget.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps', 'winget.exe'),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def _augment_process_path(dirpath):
    """把目录加入当前进程 PATH（子进程随后继承）。目录存在才添加。"""
    if dirpath and os.path.isdir(dirpath):
        cur = os.environ.get('PATH', '')
        parts = cur.split(os.pathsep) if cur else []
        if os.path.normpath(dirpath) not in [os.path.normpath(p) for p in parts]:
            os.environ['PATH'] = dirpath + (os.pathsep + cur if cur else '')
        return True
    return False


def _ps_quote(path):
    """PowerShell 单引号字符串转义。"""
    return "'" + path.replace("'", "''") + "'"


def _download_file(url, target, log, expect_size=None, expect_sha256=None,
                   retries=2, label='文件'):
    """流式下载文件，支持大小/SHA256 校验与失败重试。

    返回 True/False。
    """
    import hashlib
    import requests

    for attempt in range(retries + 1):
        try:
            if attempt:
                log(f'  第 {attempt + 1} 次尝试下载 {label}...')
            with requests.get(url, stream=True, timeout=(30, 300)) as r:
                r.raise_for_status()
                sha = hashlib.sha256()
                total = 0
                tmp_target = target + '.part'
                with open(tmp_target, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)
                            sha.update(chunk)
                            total += len(chunk)
                os.replace(tmp_target, target)

            if expect_size is not None and total != expect_size:
                log(f'  {label}大小不符: {total} != {expect_size}')
                if attempt < retries:
                    continue
                _safe_remove(target)
                return False
            if expect_sha256 and sha.hexdigest().lower() != expect_sha256.lower():
                log(f'  {label}SHA256 校验失败，文件可能已损坏')
                if attempt < retries:
                    continue
                _safe_remove(target)
                return False
            return True
        except Exception as e:
            log(f'  下载{label}异常: {e}')
            if attempt >= retries:
                _safe_remove(target)
                return False
    return False


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _check_windows_build(min_build=17763):
    """返回 (build号, 是否满足最低版本)。检测失败时返回 (0, True) 不阻塞安装。"""
    try:
        out = subprocess.run(
            'powershell -NoProfile -Command "[System.Environment]::OSVersion.Version.Build"',
            capture_output=True, text=True, shell=True, timeout=15
        )
        if out.returncode == 0:
            build = int(out.stdout.strip())
            return build, build >= min_build
    except Exception:
        pass
    return 0, True


def _install_winget(log):
    """自动安装 winget（App Installer），成功返回 winget 路径，失败返回 None。

    从 GitHub 下载最新 .msixbundle（约 205MB）与依赖包 zip，
    经 SHA256 完整性校验后通过 PowerShell 安装。需要 Windows 10 1809+。
    """
    import tempfile
    import zipfile

    log('  正在尝试自动安装 winget...')

    build, ok = _check_windows_build()
    if not ok:
        log(f'  Windows 版本过低 (build {build})，winget 需要 1809+，跳过')
        return None

    # 获取最新 release 信息
    try:
        import requests
        resp = requests.get(
            'https://api.github.com/repos/microsoft/winget-cli/releases/latest', timeout=30)
        resp.raise_for_status()
        release = resp.json()
    except Exception as e:
        log(f'  获取 winget 最新版本失败: {e}')
        return None

    assets = {a['name']: a for a in release.get('assets', [])}
    msix_asset = assets.get('Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle')
    deps_asset = assets.get('DesktopAppInstaller_Dependencies.zip')

    if not msix_asset:
        log('  未找到 winget 安装包')
        return None

    msix_digest = (msix_asset.get('digest') or '').replace('sha256:', '') or None
    log(f"  winget 版本: {release.get('tag_name')}，安装包约 "
        f"{msix_asset['size'] // 1048576} MB")

    tmpdir = tempfile.mkdtemp(prefix='winget_')
    msix_path = os.path.join(tmpdir, 'winget.msixbundle')
    deps_path = os.path.join(tmpdir, 'deps.zip')
    deps_dir = os.path.join(tmpdir, 'deps')

    try:
        # 下载主安装包（带 sha256 校验，失败重试）
        if not _download_file(
                msix_asset['browser_download_url'], msix_path, log,
                expect_size=msix_asset['size'], expect_sha256=msix_digest,
                retries=2, label='winget 安装包'):
            log('  winget 安装包下载/校验失败')
            return None

        # 下载并解压依赖（VCLibs、Microsoft.UI.Xaml 等）
        dep_files = []
        if deps_asset:
            log('  正在下载 winget 依赖包（约 90MB）...')
            deps_digest = (deps_asset.get('digest') or '').replace('sha256:', '') or None
            if _download_file(
                    deps_asset['browser_download_url'], deps_path, log,
                    expect_size=deps_asset['size'], expect_sha256=deps_digest,
                    retries=2, label='winget 依赖包'):
                with zipfile.ZipFile(deps_path) as z:
                    z.extractall(deps_dir)
                # 只取 x64 的 appx/msix 依赖
                for root_dir, _dirs, files in os.walk(deps_dir):
                    rel = os.path.relpath(root_dir, deps_dir).lower()
                    if 'x64' not in rel and 'neutral' not in rel:
                        continue
                    for fn in files:
                        if fn.lower().endswith(('.appx', '.appxbundle', '.msix')):
                            dep_files.append(os.path.join(root_dir, fn))
            else:
                log('  依赖包下载失败，将尝试直接安装主包')

        # PowerShell 安装
        log('  正在安装 winget...')
        ps_parts = [f'Add-AppxPackage -Path {_ps_quote(msix_path)} -ForceApplicationShutdown']
        if dep_files:
            arr = ','.join(_ps_quote(p) for p in dep_files)
            ps_parts.append(f'-DependencyPaths @({arr})')
        ps_cmd = ' '.join(ps_parts)

        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=180
        )

        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            log(f'  winget 安装失败: {err[-400:]}')
            return None

        time.sleep(2)
        winget_path = _find_winget_exe()
        if winget_path:
            log(f'  ✅ winget 安装成功: {winget_path}')
            return winget_path
        log('  安装命令已完成，但未检测到 winget（可能需要重新打开程序）')
        return None

    except Exception as e:
        log(f'  winget 自动安装异常: {e}')
        return None
    finally:
        import shutil as _sh
        try:
            _sh.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def _git_cmd_dirs():
    """Git 安装后可能的 cmd 目录（用户级 / 系统级）。"""
    home = get_home_dir()
    pf = os.environ.get('ProgramFiles', r'C:\Program Files')
    return [
        os.path.join(home, 'AppData', 'Local', 'Programs', 'Git', 'cmd'),
        os.path.join(pf, 'Git', 'cmd'),
    ]


def _refresh_and_verify_git(log):
    """安装后把已知 Git 目录加入进程 PATH，并验证 git 可用。"""
    for d in _git_cmd_dirs():
        if os.path.isdir(d):
            _augment_process_path(d)
    ok, ver = _check_git_installed()
    if ok:
        log(f'✅ Git 安装成功: {ver}')
    return ok


def _winget_install_git(log, winget_exe):
    """使用指定 winget 安装 Git。返回 True/False。"""
    log(f'使用 winget 安装 Git... ({winget_exe})')
    try:
        result = subprocess.run(
            f'"{winget_exe}" install --id Git.Git -e '
            '--accept-source-agreements --accept-package-agreements --silent',
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            shell=True, timeout=900
        )
        if result.returncode == 0:
            return _refresh_and_verify_git(log)
        err = result.stderr or result.stdout or ''
        log(f'winget 安装 Git 失败: {err[-400:]}')
        return False
    except Exception as e:
        log(f'winget 安装 Git 异常: {e}')
        return False


def _install_git_from_npmmirror(log):
    """从阿里 npmmirror 国内镜像下载官方 Git for Windows 完整安装包并静默安装。"""
    import tempfile
    import requests

    base = 'https://registry.npmmirror.com/-/binary/git-for-windows/'
    try:
        data = requests.get(base, timeout=30).json()
    except Exception as e:
        log(f'  获取镜像版本列表失败: {e}')
        return False

    # 选最新正式版 vX.Y.Z.windows.N
    candidates = []
    for item in data:
        m = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)\.windows\.(\d+)/?', item.get('name', ''))
        if m:
            candidates.append((tuple(int(x) for x in m.groups()), item['name'].rstrip('/')))
    if not candidates:
        log('  镜像中未找到正式版 Git')
        return False
    candidates.sort()
    ver_name = candidates[-1][1]

    # 读取该版本文件列表，找完整安装包 Git-*-64-bit.exe（排除 MinGit）
    try:
        files = requests.get(f'{base}{ver_name}/', timeout=30).json()
    except Exception as e:
        log(f'  获取版本文件列表失败: {e}')
        return False

    installer = None
    for f in files:
        fn = f.get('name', '')
        if re.fullmatch(r'Git-[\d.]+-64-bit\.exe', fn):
            installer = f
            break
    if not installer:
        log(f'  未找到 {ver_name} 的 64 位完整安装包')
        return False

    log(f"  最新版本: {ver_name}，安装包约 {installer['size'] // 1048576} MB")
    tmpdir = tempfile.mkdtemp(prefix='git_install_')
    installer_path = os.path.join(tmpdir, 'Git-installer.exe')

    try:
        if not _download_file(
                installer['url'], installer_path, log,
                expect_size=installer['size'], retries=2, label='Git 安装包'):
            log('  Git 安装包下载失败')
            return False

        # 先按当前用户静默安装（无需管理员权限）
        log('  正在静默安装 Git（当前用户）...')
        common_flags = ['/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-',
                        '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS']
        try:
            _ = subprocess.run([installer_path] + common_flags + ['/CURRENTUSER'],
                               capture_output=True, timeout=900)
        except Exception as e:
            log(f'  安装执行异常: {e}')

        if _refresh_and_verify_git(log):
            return True

        # 当前用户安装未成功：尝试系统级安装（若程序是管理员可静默成功，否则会弹 UAC）
        log('  当前用户安装未生效，尝试系统级安装（可能弹出权限请求，请允许）...')
        try:
            subprocess.run([installer_path] + common_flags + ['/ALLUSERS'],
                           capture_output=True, timeout=900)
        except Exception as e:
            log(f'  系统级安装异常: {e}')
        return _refresh_and_verify_git(log)

    except Exception as e:
        log(f'  镜像安装 Git 异常: {e}')
        return False
    finally:
        import shutil as _sh
        _sh.rmtree(tmpdir, ignore_errors=True)


def _install_git_conda(log):
    """通过 conda 安装 Git。

    1) defaults 通道（.condarc 通常已配置国内镜像，且 main 通道自带 git）
    2) 失败再用清华 conda-forge 镜像
    conda 版 git 位于 <conda根>\\Library\\bin，会加入当前进程 PATH。
    """
    conda_exe = _find_conda_exe(log)
    if not conda_exe:
        log('  未找到 conda 可执行文件')
        return False

    # conda_exe = <root>\Scripts\conda.exe
    root = os.path.dirname(os.path.dirname(os.path.abspath(conda_exe)))

    command_sets = [
        [conda_exe, 'install', '-y', 'git'],
        [conda_exe, 'install', '-y', '--override-channels',
         '-c', 'https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/',
         'git'],
    ]

    for i, cmd in enumerate(command_sets):
        label = 'defaults 通道' if i == 0 else '清华 conda-forge 镜像'
        log(f'  使用 conda {label} 安装 git（元数据较大，请耐心等待）...')
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except Exception as e:
            log(f'  conda 安装异常: {e}')
            continue

        if res.returncode != 0:
            combined = (res.stdout or '') + (res.stderr or '')
            log(f'  {label}安装失败: {combined[-500:]}')
            continue

        # conda 版 git 不进系统 PATH，直接定位并加入当前进程 PATH
        lib_bin = os.path.join(root, 'Library', 'bin')
        git_exe = os.path.join(lib_bin, 'git.exe')
        if os.path.exists(git_exe):
            _augment_process_path(lib_bin)
            ok, ver = _check_git_installed()
            if ok:
                log(f'✅ Git 通过 Conda 安装成功: {ver}')
                log('  提示：conda 版 Git 仅在本程序内自动可用，'
                    '如需在普通终端使用请手动添加环境变量')
                return True
        log('  conda 报告安装完成，但未找到 git.exe')

    return False


def _install_git_local(log):
    """兜底：从 exe 同级 / assets 目录查找用户自行放置的 Git 安装包。"""
    possible_paths = [
        os.path.join(os.path.dirname(sys.executable), 'Git-installer.exe'),
    ]
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        possible_paths.append(os.path.join(base, 'assets', 'Git-installer.exe'))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.append(os.path.join(base_dir, '..', 'assets', 'Git-installer.exe'))

    for p in possible_paths:
        p = os.path.normpath(p)
        if os.path.exists(p):
            log(f'发现本地 Git 安装包: {p}，尝试静默安装...')
            try:
                subprocess.run(
                    f'"{p}" /VERYSILENT /NORESTART /NOCANCEL /SP-',
                    shell=True, timeout=900)
                if _refresh_and_verify_git(log):
                    return True
            except Exception as e:
                log(f'本地安装包尝试失败: {e}')
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
