import os
import sys
import platform
import time


def is_windows():
    return sys.platform.startswith('win')


def is_linux():
    return sys.platform.startswith('linux')


def is_macos():
    return sys.platform == 'darwin'


def get_os_name():
    if is_windows():
        return 'Windows'
    elif is_linux():
        return 'Linux'
    elif is_macos():
        return 'macOS'
    else:
        return platform.system()


def get_home_dir():
    return os.path.expanduser('~')


def get_conda_search_paths():
    paths = []
    home = get_home_dir()

    if is_windows():
        conda_dir_names = [
            'Miniconda3', 'miniconda3',
            'Anaconda3', 'anaconda3',
            'Miniforge3', 'miniforge3',
            'Mambaforge', 'mambaforge',
        ]

        base_dirs = [
            home,
            os.path.join(home, 'AppData', 'Local', 'Continuum'),
            os.path.join(home, 'AppData', 'Local'),
            'C:\\ProgramData',
            'C:\\Program Files',
            'C:\\Program Files (x86)',
        ]

        for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive_path = f'{drive}:\\'
            if os.path.exists(drive_path):
                base_dirs.append(drive_path)
                base_dirs.append(os.path.join(drive_path, 'ProgramData'))
                base_dirs.append(os.path.join(drive_path, 'Program Files'))

        for base in base_dirs:
            for name in conda_dir_names:
                conda_path = os.path.join(base, name, 'Scripts', 'conda.exe')
                paths.append(conda_path)

        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_CURRENT_USER, r'Software\Python\ContinuumAnalytics', 'InstallPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\Python\ContinuumAnalytics', 'InstallPath'),
                (winreg.HKEY_CURRENT_USER, r'Software\Anaconda\Anaconda', 'InstallPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\Anaconda\Anaconda', 'InstallPath'),
                (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 'InstallLocation'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 'InstallLocation'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall', 'InstallLocation'),
            ]
            for hkey, subkey, val_name in reg_paths:
                try:
                    key = winreg.OpenKey(hkey, subkey)
                    try:
                        i = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey_path = subkey + '\\' + subkey_name
                                sub_key = winreg.OpenKey(hkey, subkey_path)
                                try:
                                    install_path, _ = winreg.QueryValueEx(sub_key, val_name)
                                    if install_path and os.path.exists(install_path):
                                        name_lower = os.path.basename(install_path).lower()
                                        if any(kw in name_lower for kw in ['conda', 'anaconda', 'miniconda', 'miniforge', 'mambaforge']):
                                            conda_exe = os.path.join(install_path, 'Scripts', 'conda.exe')
                                            paths.append(conda_exe)
                                except FileNotFoundError:
                                    pass
                                finally:
                                    winreg.CloseKey(sub_key)
                                i += 1
                            except OSError:
                                break
                    except Exception:
                        pass
                    finally:
                        winreg.CloseKey(key)
                except Exception:
                    pass
        except ImportError:
            pass
    else:
        conda_dir_names = [
            'miniconda3', 'Miniconda3',
            'anaconda3', 'Anaconda3',
            'miniforge3', 'Miniforge3',
            'mambaforge', 'Mambaforge',
        ]
        base_dirs = [
            home,
            '/opt',
            '/usr/local',
        ]
        for base in base_dirs:
            for name in conda_dir_names:
                conda_path = os.path.join(base, name, 'bin', 'conda')
                paths.append(conda_path)
        paths.extend([
            '/usr/bin/conda',
            '/usr/local/bin/conda',
        ])

    return [p for p in paths if p]


def get_gpu_check_cmd():
    if is_windows():
        return 'nvidia-smi.exe'
    else:
        return 'nvidia-smi'


def get_conda_exe_name():
    if is_windows():
        return 'conda.exe'
    else:
        return 'conda'


def get_python_exe_name():
    if is_windows():
        return 'python.exe'
    else:
        return 'python'


def get_conda_python_path(env_path):
    if is_windows():
        return os.path.join(env_path, 'python.exe')
    else:
        return os.path.join(env_path, 'bin', 'python')


def get_conda_scripts_dir(env_path):
    if is_windows():
        return os.path.join(env_path, 'Scripts')
    else:
        return os.path.join(env_path, 'bin')


def get_conda_envs_dir(conda_path):
    base_dir = os.path.dirname(os.path.dirname(conda_path))
    if is_windows():
        envs_dir = os.path.join(base_dir, 'envs')
    else:
        envs_dir = os.path.join(base_dir, 'envs')
    return envs_dir


def get_available_install_locations():
    locations = []
    home = get_home_dir()

    if is_windows():
        import string
        for letter in string.ascii_uppercase:
            drive = f'{letter}:\\'
            if os.path.exists(drive):
                locations.append(drive)
    else:
        locations.extend([
            home,
            '/opt',
            '/usr/local',
        ])
        locations = [p for p in locations if os.path.exists(p) and os.access(p, os.W_OK)]

    return locations


def get_default_install_path(conda_type='miniconda'):
    home = get_home_dir()
    if is_windows():
        if conda_type == 'miniconda':
            path = os.path.join(home, 'Miniconda3')
        else:
            path = os.path.join(home, 'Anaconda3')
    else:
        if conda_type == 'miniconda':
            path = os.path.join(home, 'miniconda3')
        else:
            path = os.path.join(home, 'anaconda3')
    return normalize_path(path)


def normalize_path(path):
    if not path:
        return path
    path = os.path.normpath(path)
    if not is_windows():
        path = path.replace('\\', '/')
    return path


def get_miniconda_download_url(version='latest'):
    if is_windows():
        if version == 'latest':
            filename = 'Miniconda3-latest-Windows-x86_64.exe'
        else:
            filename = f'Miniconda3-{version}-Windows-x86_64.exe'
    elif is_linux():
        arch = 'x86_64'
        if version == 'latest':
            filename = f'Miniconda3-latest-Linux-{arch}.sh'
        else:
            filename = f'Miniconda3-{version}-Linux-{arch}.sh'
    else:
        filename = ''

    return filename


def get_anaconda_download_url(version='2024.02-0'):
    if is_windows():
        filename = f'Anaconda3-{version}-Windows-x86_64.exe'
    elif is_linux():
        arch = 'x86_64'
        filename = f'Anaconda3-{version}-Linux-{arch}.sh'
    else:
        filename = ''

    return filename


def get_git_download_url(version='2.45.1'):
    if is_windows():
        filename = f'Git-{version}-64-bit.exe'
    elif is_linux():
        filename = ''
    else:
        filename = ''

    return filename


def get_labelimg_exe_path(env_path):
    if is_windows():
        return os.path.join(env_path, 'Scripts', 'labelImg.exe')
    else:
        return os.path.join(env_path, 'bin', 'labelImg')


def get_vscode_search_paths():
    paths = []
    if is_windows():
        paths.extend([
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe'),
            os.path.expandvars(r'%ProgramFiles%\Microsoft VS Code\Code.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft VS Code\Code.exe'),
        ])
    elif is_linux():
        paths.extend([
            '/usr/bin/code',
            '/usr/share/code/bin/code',
            '/snap/bin/code',
            '/opt/visual-studio-code/bin/code',
            '/opt/VSCode-linux-x64/bin/code',
            '/opt/vscode/code',
            os.path.expanduser('~/.local/share/code/bin/code'),
            os.path.expanduser('~/vscode/code'),
            os.path.expanduser('~/VSCode-linux-x64/bin/code'),
            '/var/lib/flatpak/exports/bin/com.visualstudio.code',
            os.path.expanduser('~/.local/share/flatpak/exports/bin/com.visualstudio.code'),
        ])
    elif is_macos():
        paths.extend([
            '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code',
        ])

    return [p for p in paths if p]


def get_pycharm_search_patterns():
    patterns = []
    if is_windows():
        patterns.extend([
            os.path.expandvars(r'%LOCALAPPDATA%\JetBrains\Toolbox\apps\PyCharm-P\ch-0\*\bin\pycharm64.exe'),
            os.path.expandvars(r'%ProgramFiles%\JetBrains\PyCharm *\bin\pycharm64.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\JetBrains\PyCharm *\bin\pycharm64.exe'),
        ])
    elif is_linux():
        patterns.extend([
            '/opt/pycharm-*/bin/pycharm.sh',
            '/opt/pycharm-community-*/bin/pycharm.sh',
            '/opt/pycharm-professional-*/bin/pycharm.sh',
            '/usr/share/pycharm/bin/pycharm.sh',
            '/snap/pycharm-community/current/bin/pycharm.sh',
            '/snap/pycharm-professional/current/bin/pycharm.sh',
            os.path.expanduser('~/.local/share/JetBrains/Toolbox/apps/PyCharm-P/ch-0/*/bin/pycharm.sh'),
            os.path.expanduser('~/.local/share/JetBrains/Toolbox/apps/PyCharm-C/ch-0/*/bin/pycharm.sh'),
            os.path.expanduser('~/pycharm-*/bin/pycharm.sh'),
            os.path.expanduser('~/PyCharm-*/bin/pycharm.sh'),
            '/var/lib/flatpak/exports/bin/com.jetbrains.PyCharm-Community',
            '/var/lib/flatpak/exports/bin/com.jetbrains.PyCharm-Professional',
            os.path.expanduser('~/.local/share/flatpak/exports/bin/com.jetbrains.PyCharm-Community'),
            os.path.expanduser('~/.local/share/flatpak/exports/bin/com.jetbrains.PyCharm-Professional'),
        ])
    elif is_macos():
        patterns.extend([
            '/Applications/PyCharm.app/Contents/MacOS/pycharm',
            '/Applications/PyCharm CE.app/Contents/MacOS/pycharm',
        ])

    return [p for p in patterns if p]


def has_registry_support():
    return is_windows()


def get_runtime_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_conda_install_record_file():
    return os.path.join(get_runtime_dir(), 'conda_install_record.json')


def save_conda_install_path(conda_path):
    record = {
        'conda_path': conda_path,
        'install_time': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    try:
        import json
        with open(get_conda_install_record_file(), 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_conda_install_path():
    file_path = get_conda_install_record_file()
    if not os.path.exists(file_path):
        return None
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        conda_path = record.get('conda_path')
        if conda_path and os.path.exists(conda_path):
            return conda_path
        return None
    except Exception:
        return None


def is_admin():
    if not is_windows():
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin(cmd, wait=True, timeout=None):
    if not is_windows():
        return {'success': False, 'stdout': '', 'stderr': '非 Windows 平台不支持 UAC 提权', 'returncode': -1}

    try:
        import ctypes
        from ctypes import wintypes

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        SEE_MASK_FLAG_NO_UI = 0x00000400
        SW_HIDE = 0
        SW_SHOWNORMAL = 1

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('fMask', wintypes.ULONG),
                ('hwnd', wintypes.HWND),
                ('lpVerb', wintypes.LPCWSTR),
                ('lpFile', wintypes.LPCWSTR),
                ('lpParameters', wintypes.LPCWSTR),
                ('lpDirectory', wintypes.LPCWSTR),
                ('nShow', ctypes.c_int),
                ('hInstApp', wintypes.HINSTANCE),
                ('lpIDList', ctypes.c_void_p),
                ('lpClass', wintypes.LPCWSTR),
                ('hkeyClass', wintypes.HKEY),
                ('dwHotKey', wintypes.DWORD),
                ('DUMMYUNIONNAME', wintypes.HANDLE),
                ('hProcess', wintypes.HANDLE),
            ]

        ShellExecuteEx = ctypes.windll.shell32.ShellExecuteExW
        GetExitCodeProcess = ctypes.windll.kernel32.GetExitCodeProcess
        CloseHandle = ctypes.windll.kernel32.CloseHandle
        WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject

        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = 'runas'

        if isinstance(cmd, list):
            exe = cmd[0]
            params = ' '.join(f'"{c}"' for c in cmd[1:])
        else:
            import shlex
            parts = shlex.split(cmd, posix=False)
            if parts:
                exe = parts[0]
                params = ' '.join(f'"{c}"' for c in parts[1:])
            else:
                exe = cmd
                params = ''

        sei.lpFile = exe
        sei.lpParameters = params
        sei.lpDirectory = None
        sei.nShow = SW_HIDE
        sei.hInstApp = None

        result = ShellExecuteEx(ctypes.byref(sei))
        if not result:
            error_code = ctypes.windll.kernel32.GetLastError()
            return {'success': False, 'stdout': '', 'stderr': f'ShellExecuteEx 失败，错误码: {error_code}', 'returncode': -1}

        if not wait:
            CloseHandle(sei.hProcess)
            return {'success': True, 'stdout': '', 'stderr': '', 'returncode': 0, 'pid': sei.hProcess}

        if timeout:
            WAIT_TIMEOUT = 0x00000102
            wait_result = WaitForSingleObject(sei.hProcess, int(timeout * 1000))
            if wait_result == WAIT_TIMEOUT:
                CloseHandle(sei.hProcess)
                return {'success': False, 'stdout': '', 'stderr': '安装超时', 'returncode': -1}

        else:
            WaitForSingleObject(sei.hProcess, -1)

        exit_code = wintypes.DWORD()
        GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        CloseHandle(sei.hProcess)

        return {'success': exit_code.value == 0, 'stdout': '', 'stderr': '', 'returncode': exit_code.value}

    except Exception as e:
        return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}
