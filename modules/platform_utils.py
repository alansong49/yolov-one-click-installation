import os
import sys
import platform


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
        paths.extend([
            os.path.join(home, 'miniconda3', 'Scripts', 'conda.exe'),
            os.path.join(home, 'anaconda3', 'Scripts', 'conda.exe'),
            os.path.join(home, 'Miniconda3', 'Scripts', 'conda.exe'),
            os.path.join(home, 'Anaconda3', 'Scripts', 'conda.exe'),
            os.path.join('C:', os.sep, 'ProgramData', 'Miniconda3', 'Scripts', 'conda.exe'),
            os.path.join('C:', os.sep, 'ProgramData', 'Anaconda3', 'Scripts', 'conda.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Continuum', 'miniconda3', 'Scripts', 'conda.exe'),
        ])
    else:
        # Linux/macOS: 同时支持大小写两种命名
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
        # 系统级路径
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
            return os.path.join(home, 'Miniconda3')
        else:
            return os.path.join(home, 'Anaconda3')
    else:
        if conda_type == 'miniconda':
            return os.path.join(home, 'miniconda3')
        else:
            return os.path.join(home, 'anaconda3')


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
