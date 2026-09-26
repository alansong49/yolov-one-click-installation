import subprocess
import os
import re
from .platform_utils import (
    get_python_exe_name, get_conda_scripts_dir, get_conda_python_path, is_windows
)

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_TRUSTED_HOST = "pypi.tuna.tsinghua.edu.cn"

# PyTorch wheel 下载源：上海交大为标准 PEP 503 索引（国内高速），官方源兜底
PYTORCH_INDEX_SOURCES = {
    'cpu': [
        ('上海交大镜像', 'https://mirror.sjtu.edu.cn/pytorch-wheels/cpu'),
        ('PyTorch 官方源', 'https://download.pytorch.org/whl/cpu'),
    ],
    'cu121': [
        ('上海交大镜像', 'https://mirror.sjtu.edu.cn/pytorch-wheels/cu121'),
        ('PyTorch 官方源', 'https://download.pytorch.org/whl/cu121'),
    ],
}
# 慢网络下放宽 pip 读超时与重试（默认 15 秒容易掐断大文件下载）
PIP_TORCH_NETWORK_FLAGS = "--timeout 300 --retries 5"
TORCH_INSTALL_TIMEOUT = 1800

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

            # 看门狗：超时后强制结束进程，保证 timeout 真正生效
            import threading
            timed_out = {'value': False}

            def _watchdog():
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out['value'] = True
                    try:
                        process.kill()
                    except Exception:
                        pass

            wd = threading.Thread(target=_watchdog, daemon=True)
            wd.start()

            output_lines = []
            for line in process.stdout:
                line = clean_output(line)
                if line:
                    output_lines.append(line)
                    yield line
            wd.join()

            if timed_out['value']:
                yield f'[错误] 命令执行超时（{timeout}秒）'
            elif process.returncode != 0:
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

    def run_in_env(self, env_name, command, timeout=600):
        # --no-capture-output：让子进程输出直通，避免 conda 缓冲导致日志延迟
        cmd = f'"{self.conda_path}" run -n {env_name} --no-capture-output {command}'
        for line in self._run_cmd(cmd, timeout):
            yield line

    def run_in_env_sync(self, env_name, command):
        cmd = f'"{self.conda_path}" run -n {env_name} {command}'
        return self._run_cmd_sync(cmd)

    def _install_torch(self, env_name, version, variant):
        if version == 'latest':
            spec = 'torch torchvision torchaudio'
        else:
            spec = f'torch=={version} torchvision torchaudio'

        sources = PYTORCH_INDEX_SOURCES.get(variant, PYTORCH_INDEX_SOURCES['cpu'])
        total = len(sources)

        for i, (source_name, index_url) in enumerate(sources):
            yield f'下载源 ({i + 1}/{total}): {source_name}'
            cmd = (
                f'python -m pip install {spec} --index-url {index_url} '
                f'{PIP_TORCH_NETWORK_FLAGS} --prefer-binary --no-cache-dir --progress-bar raw'
            )
            failed = False
            for line in self.run_in_env(env_name, cmd, timeout=TORCH_INSTALL_TIMEOUT):
                if '[错误]' in line:
                    failed = True
                yield line

            if not failed:
                return

            if i < total - 1:
                yield f'⚠  {source_name} 安装失败，正在自动切换下载源...'

    def install_torch_cuda121(self, env_name, version='latest'):
        yield from self._install_torch(env_name, version, 'cu121')

    def install_torch_cpu(self, env_name, version='latest'):
        yield from self._install_torch(env_name, version, 'cpu')

    def pip_install(self, env_name, package, force_reinstall=False, upgrade=False, index_url=None):
        flags = ''
        if force_reinstall:
            flags += ' --force-reinstall'
        if upgrade:
            flags += ' --upgrade'
        mirror = index_url if index_url else PIP_MIRROR
        cmd = f'python -m pip install {package}{flags} -i {mirror} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_uninstall(self, env_name, package):
        cmd = f'python -m pip uninstall {package} -y'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_upgrade_base(self, env_name):
        cmd = f'python -m pip install --upgrade pip setuptools wheel -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_install_requirements(self, env_name, requirements_path, force_reinstall=False):
        force_flag = ' --force-reinstall' if force_reinstall else ''
        cmd = f'python -m pip install -r "{requirements_path}"{force_flag} -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def pip_install_editable(self, env_name, package_path, force_reinstall=False):
        force_flag = ' --force-reinstall' if force_reinstall else ''
        cmd = f'python -m pip install -e "{package_path}"{force_flag} -i {PIP_MIRROR} --trusted-host {PIP_TRUSTED_HOST} --prefer-binary --no-cache-dir'
        for line in self.run_in_env(env_name, cmd):
            yield line

    def config_pip_mirror(self, env_name):
        cmd = f'python -m pip config set global.index-url {PIP_MIRROR}'
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

    def get_env_python_version(self, env_name):
        """查询环境内实际的 Python 版本（如 '3.8.10'），失败返回 None"""
        python_path = self.get_python_path(env_name)
        if python_path and os.path.exists(python_path):
            try:
                result = subprocess.run(
                    f'"{python_path}" -c "import sys;print(\'%d.%d.%d\' % sys.version_info[:3])"',
                    capture_output=True, text=True, shell=True, timeout=30
                )
                ver = result.stdout.strip()
                if ver:
                    return ver
            except Exception:
                pass
        # 回退：conda run 方式
        success, output = self._run_cmd_sync(
            f'"{self.conda_path}" run -n {env_name} python -c "import sys;print(\'%d.%d.%d\' % sys.version_info[:3])"'
        )
        if success:
            for line in output.splitlines():
                line = line.strip()
                if re.fullmatch(r'\d+\.\d+\.\d+', line):
                    return line
        return None

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

    def _find_env_prefix(self, env_name):
        """通过 conda env list 查找环境的实际安装路径，找不到返回 None"""
        for env in self.list_envs():
            if env.get('name') == env_name and env.get('path'):
                return env['path']
        return None

    def _guess_env_prefix(self, env_name):
        """conda 不认识该环境名时，按默认 envs 目录猜测路径（用于残留目录清理）"""
        conda_root = os.path.dirname(os.path.dirname(self.conda_path))
        guess = os.path.join(conda_root, 'envs', env_name)
        return guess if os.path.isdir(guess) else None

    def _force_rmtree(self, path, retries=3):
        """强制递归删除目录：解除只读属性 + 重试，应对 Windows 文件占用。"""
        import shutil
        import stat
        import time

        def on_error(func, p, exc_info):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass

        for _ in range(retries):
            if not os.path.exists(path):
                return True
            shutil.rmtree(path, onerror=on_error)
            if not os.path.exists(path):
                return True
            time.sleep(0.6)
        return not os.path.exists(path)

    def detect_orphan_env_dirs(self):
        """检测 envs 目录下的残留文件夹：环境已被 conda 注销（无 conda-meta）但文件仍在。

        典型成因：conda env remove 只清理自己登记的文件，pip 安装的包（如 torch）
        等未跟踪文件残留，导致环境从 conda 列表消失而磁盘目录还在。
        """
        envs_dirs = set()
        conda_root = os.path.dirname(os.path.dirname(self.conda_path))
        conda_root_norm = os.path.normpath(conda_root)
        # 默认 envs 目录：<conda根>\envs
        envs_dirs.add(os.path.join(conda_root, 'envs'))
        for env in self.list_envs():
            p = env.get('path')
            if not p:
                continue
            # base 环境路径就是 conda 根目录，绝不能取其父目录（否则会把
            # 整个盘符根目录当成 envs 目录，误报系统文件夹为残留）
            if os.path.normpath(p) == conda_root_norm:
                continue
            parent = os.path.dirname(p)
            # 只有父目录名为 envs（不区分大小写）才是合法的环境存放目录
            if os.path.basename(parent).lower() == 'envs':
                envs_dirs.add(parent)

        orphans = []
        for envs_dir in envs_dirs:
            if not os.path.isdir(envs_dir):
                continue
            try:
                entries = os.listdir(envs_dir)
            except Exception:
                continue
            for entry in entries:
                full = os.path.join(envs_dir, entry)
                if not os.path.isdir(full):
                    continue
                # 仍含 conda-meta 的是有效环境，跳过
                if os.path.isdir(os.path.join(full, 'conda-meta')):
                    continue
                orphans.append({
                    'name': f'{entry}（残留）',
                    'real_name': entry,
                    'path': full,
                    'python': '',
                    'orphan': True,
                })
        orphans.sort(key=lambda e: e['real_name'].lower())
        return orphans

    def scan_envs(self, progress_callback=None):
        """扫描所有 conda 环境，并附带每个环境的 Python 版本。

        progress_callback(index, total, env_info) 每处理完一个环境回调一次。
        返回 [{'name', 'path', 'python'}]，base 环境排在最前。
        """
        envs = self.list_envs()
        total = len(envs)
        result = []
        for i, env in enumerate(envs):
            name = env.get('name', '')
            path = env.get('path', '')
            py_ver = ''

            # 优先直接从环境路径找解释器，速度快且不依赖环境名拼接
            python_path = ''
            if path:
                python_path = get_conda_python_path(path)
            if not python_path or not os.path.exists(python_path):
                python_path = self.get_python_path(name) if name else None

            if python_path and os.path.exists(python_path):
                try:
                    pres = subprocess.run(
                        f'"{python_path}" -c "import sys;print(\'%d.%d.%d\' % sys.version_info[:3])"',
                        capture_output=True, text=True, shell=True, timeout=30
                    )
                    py_ver = (pres.stdout or '').strip()
                except Exception:
                    py_ver = ''

            info = {'name': name, 'path': path, 'python': py_ver}
            result.append(info)
            if progress_callback:
                progress_callback(i + 1, total, info)
        # base 排最前，其余按名称排序
        result.sort(key=lambda e: (e.get('name') != 'base', e.get('name', '')))
        # 追加已注销但残留的目录，供管理器一键清理
        result.extend(self.detect_orphan_env_dirs())
        return result

    def remove_env(self, env_name, prefix=None):
        """删除 conda 环境。

        流程：有效环境先由 conda 正常注销，随后检查磁盘目录是否残留，
        若有 pip 安装的包等未跟踪文件则强制删除整个目录。
        prefix 已知时（如残留目录）可直接传入其路径。
        """
        if not prefix:
            prefix = self._find_env_prefix(env_name)
        if not prefix:
            prefix = self._guess_env_prefix(env_name)

        # 已是残留目录（无 conda-meta）：直接强删，无需再调 conda
        if prefix and os.path.isdir(prefix) and not os.path.isdir(os.path.join(prefix, 'conda-meta')):
            if self._force_rmtree(prefix):
                return True, '已删除残留的环境文件夹'
            return False, '残留文件夹删除失败：文件可能被占用，或需要管理员权限'

        cmd = f'"{self.conda_path}" env remove -n "{env_name}" -y'
        success, output = self._run_cmd_sync(cmd)

        if prefix and os.path.isdir(prefix):
            # conda 已注销环境但目录残留（pip 包等未跟踪文件）
            if self._force_rmtree(prefix):
                output += '\n已自动删除残留的环境文件夹'
                success = True
            else:
                output += '\n环境文件夹仍有文件无法删除（被占用或权限不足）'
                success = False

        return success, output

    def remove_env_as_admin(self, env_name, prefix=None):
        """以管理员权限删除环境（UAC），返回 run_as_admin 的结果字典。

        单个提权进程内完成：conda 注销 + 强制 rmdir 残留目录。
        """
        from .platform_utils import run_as_admin

        if not prefix:
            prefix = self._find_env_prefix(env_name)
        if not prefix:
            prefix = self._guess_env_prefix(env_name)

        comspec = os.environ.get('COMSPEC', 'cmd.exe')
        # cmd /c 首尾加引号的写法，内部的引号与 & 才能被正确解析
        inner = f'""{self.conda_path}" env remove -n "{env_name}" -y'
        if prefix:
            inner += f' & if exist "{prefix}" rmdir /s /q "{prefix}"'
        inner += '"'

        return run_as_admin(
            comspec,
            wait=True, timeout=300,
            raw_params=f'/c {inner}'
        )

    # ---------- 残留环境路径安全 ----------
    def _safe_orphan_paths(self):
        """当前 conda 配置下所有合法 envs 目录（绝对路径，小写）。"""
        safe = set()
        conda_root = os.path.dirname(os.path.dirname(self.conda_path))
        safe.add(os.path.normpath(os.path.join(conda_root, 'envs')).lower())
        try:
            for env in self.list_envs():
                p = env.get('path')
                if not p:
                    continue
                if os.path.normpath(p) == os.path.normpath(conda_root):
                    continue
                parent = os.path.dirname(p)
                if os.path.basename(parent).lower() == 'envs':
                    safe.add(os.path.normpath(parent).lower())
        except Exception:
            pass
        return safe

    def _is_safe_orphan_path(self, path, safe_dirs=None):
        """残留目录必须位于某个 envs 目录的直接子级。

        防止误删盘符根目录下的系统文件夹（Program Files、PerfLogs 等）。
        """
        if not path:
            return False
        norm = os.path.normpath(path)
        # 盘符根目录 / 没有父目录层级 -> 拒绝
        parent = os.path.dirname(norm)
        if not parent or parent == norm:
            return False
        if safe_dirs is None:
            safe_dirs = self._safe_orphan_paths()
        return parent.lower() in safe_dirs

    def remove_orphan_dirs(self, paths, progress_callback=None):
        """批量删除残留环境目录（这些目录已无 conda-meta，仅为文件残留）。

        paths: 残留目录绝对路径列表
        progress_callback(index, total, path)
        返回 {'removed': [已删路径], 'failed': [(路径, 原因)], 'permission_like': bool}
        """
        removed = []
        failed = []
        permission_like = False
        total = len(paths)
        safe_dirs = self._safe_orphan_paths()

        for i, path in enumerate(paths):
            if progress_callback:
                progress_callback(i, total, path)
            if not path:
                continue
            # 安全保护 1：必须位于合法 envs 目录内
            if not self._is_safe_orphan_path(path, safe_dirs):
                failed.append((path, '路径不在 conda envs 目录内，已自动跳过'))
                continue
            if not os.path.isdir(path):
                # 已不存在，视为清理成功
                removed.append(path)
                continue
            # 安全保护 2：仍含 conda-meta 的是有效环境，绝不删除
            if os.path.isdir(os.path.join(path, 'conda-meta')):
                failed.append((path, '该目录是有效环境，已自动跳过'))
                continue
            if self._force_rmtree(path):
                removed.append(path)
            else:
                failed.append((path, '删除失败：文件被占用，或需要管理员权限'))
                permission_like = True

        if progress_callback and total:
            progress_callback(total, total, '')
        return {'removed': removed, 'failed': failed, 'permission_like': permission_like}

    def remove_orphan_dirs_as_admin(self, paths):
        """以管理员权限批量删除残留目录（单个 UAC 进程内 rmdir 全部路径）。

        返回 run_as_admin 的结果字典。
        """
        from .platform_utils import run_as_admin

        # 同样过滤，绝不提权删除 envs 目录之外的路径
        safe_dirs = self._safe_orphan_paths()
        valid = [p for p in paths
                 if p and self._is_safe_orphan_path(p, safe_dirs)]
        if not valid:
            return {'success': True, 'returncode': 0, 'stderr': ''}

        comspec = os.environ.get('COMSPEC', 'cmd.exe')
        parts = [f'if exist "{p}" rmdir /s /q "{p}"' for p in valid]
        # cmd /c 首尾加引号，内部的引号与 & 才能被正确解析
        inner = '"' + ' & '.join(parts) + '"'

        return run_as_admin(
            comspec,
            wait=True, timeout=600,
            raw_params=f'/c {inner}'
        )
