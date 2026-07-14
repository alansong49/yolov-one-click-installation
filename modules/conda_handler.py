import subprocess
import os
import sys
import re
from .platform_utils import (
    get_python_exe_name, get_conda_scripts_dir, get_conda_python_path, is_windows
)

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_TRUSTED_HOST = "pypi.tuna.tsinghua.edu.cn"

CONDA_MIRRORS = [
    "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main",
    "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free",
]


def clean_output(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\r', '', text)
    return text.strip()


class CondaHandler:
    def __init__(self, conda_path):
        self.conda_path = conda_path
        if not os.path.exists(conda_path):
            raise FileNotFoundError(f'Conda 路径不存在: {conda_path}')

    def _run_cmd(self, cmd, timeout=600):
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            env['PYTHONUNBUFFERED'] = '1'
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                bufsize=1,
                env=env
            )
            output_lines = []
            for line in process.stdout:
                line = clean_output(line)
                if line:
                    output_lines.append(line)
                    yield line
            process.wait()
            if process.returncode != 0:
                yield f'[错误] 命令执行失败，返回码: {process.returncode}'
        except subprocess.TimeoutExpired:
            yield f'[错误] 命令执行超时（{timeout}秒）'
        except Exception as e:
            yield f'[错误] 执行异常: {str(e)}'

    def _run_cmd_sync(self, cmd, timeout=600):
        full_output = []
        for line in self._run_cmd(cmd, timeout):
            full_output.append(line)
        success = not any('[错误]' in line for line in full_output)
        return success, '\n'.join(full_output)

    def create_env(self, env_name, python_version):
        cmd = f'"{self.conda_path}" create -n {env_name} python={python_version} --no-default-packages -y -c {CONDA_MIRRORS[0]} -c {CONDA_MIRRORS[1]} --override-channels'
        for line in self._run_cmd(cmd, timeout=900):
            yield line

    def run_in_env(self, env_name, command):
        cmd = f'"{self.conda_path}" run -n {env_name} {command}'
        for line in self._run_cmd(cmd):
            yield line

    def run_in_env_sync(self, env_name, command):
        cmd = f'"{self.conda_path}" run -n {env_name} {command}'
        return self._run_cmd_sync(cmd)

    def install_torch_cuda121(self, env_name, version='latest'):
        if version == 'latest':
            cmd = f'pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --prefer-binary --no-cache-dir'
        else:
            cmd = f'pip install torch=={version} torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def install_torch_cpu(self, env_name, version='latest'):
        if version == 'latest':
            cmd = f'pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --prefer-binary --no-cache-dir'
        else:
            cmd = f'pip install torch=={version} torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_install(self, env_name, package, force_reinstall=False, upgrade=False, index_url=None):
        flags = ''
        if force_reinstall:
            flags += ' --force-reinstall'
        if upgrade:
            flags += ' --upgrade'
        mirror = index_url if index_url else PIP_MIRROR
        cmd = f'pip install {package}{flags} -i {mirror} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_uninstall(self, env_name, package):
        cmd = f'pip uninstall {package} -y'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_upgrade_base(self, env_name):
        cmd = f'pip install --upgrade pip setuptools wheel -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_install_requirements(self, env_name, requirements_path, force_reinstall=False):
        force_flag = ' --force-reinstall' if force_reinstall else ''
        cmd = f'pip install -r "{requirements_path}"{force_flag} -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_install_editable(self, env_name, package_path, force_reinstall=False):
        force_flag = ' --force-reinstall' if force_reinstall else ''
        cmd = f'pip install -e "{package_path}"{force_flag} -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def config_pip_mirror(self, env_name):
        cmd = f'pip config set global.index-url {PIP_MIRROR}'
        for line in self.run_in_env(env_name, cmd):
            yield line
        cmd2 = f'pip config set global.trusted-host {PIP_TRUSTED_HOST}'
        for line in self.run_in_env(env_name, cmd2):
            yield line

    def env_exists(self, env_name):
        cmd = f'"{self.conda_path}" env list'
        success, output = self._run_cmd_sync(cmd)
        if success:
            return env_name in output
        return False

    def list_envs(self):
        cmd = f'"{self.conda_path}" env list'
        success, output = self._run_cmd_sync(cmd)
        if not success:
            return []

        envs = []
        for line in output.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('='):
                continue
            parts = line.split()
            if len(parts) >= 1:
                name = parts[0]
                path = parts[-1] if len(parts) >= 2 else ''
                envs.append({'name': name, 'path': path})
        return envs

    def check_package_installed(self, env_name, package_name):
        cmd = f'pip show {package_name}'
        success, output = self.run_in_env_sync(env_name, cmd)
        return success and 'Name:' in output

    def _get_activate_cmd(self, env_name):
        conda_dir = os.path.dirname(os.path.dirname(self.conda_path))
        scripts_dir = get_conda_scripts_dir(conda_dir)
        if is_windows():
            activate_script = os.path.join(scripts_dir, 'activate.bat')
        else:
            activate_script = os.path.join(scripts_dir, 'activate')
        return f'"{activate_script}" {env_name}'

    def get_python_path(self, env_name):
        conda_dir = os.path.dirname(os.path.dirname(self.conda_path))
        envs_dir = os.path.join(conda_dir, 'envs')
        python_exe = os.path.join(envs_dir, env_name, get_python_exe_name())
        if os.path.exists(python_exe):
            return python_exe

        envs = self.list_envs()
        for env in envs:
            if env.get('name') == env_name and env.get('path'):
                python_path = get_conda_python_path(env['path'])
                if os.path.exists(python_path):
                    return python_path

        return None

    def remove_env(self, env_name):
        cmd = f'"{self.conda_path}" env remove -n {env_name} -y'
        success, output = self._run_cmd_sync(cmd)
        return success, output
