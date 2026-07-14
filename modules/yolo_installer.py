import os
import yaml
import sys
import re


def clean_output(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\r', '', text)
    return text.strip()


class YoloInstaller:
    def __init__(self, conda_handler, workspace_dir='yolo_workspace', config_path=None):
        self.conda = conda_handler
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.config = self._load_config(config_path)

    def _load_config(self, config_path=None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'repos.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'配置文件不存在: {config_path}')
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_versions(self):
        return self.config.get('yolo_versions', [])

    def get_python_versions(self):
        return self.config.get('python_versions', ['3.10', '3.9', '3.11', '3.8'])

    def get_pytorch_versions(self):
        return self.config.get('pytorch_versions', ['latest', '2.5.1', '2.4.1'])

    def _ensure_workspace(self):
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir, exist_ok=True)

    def _step(self, step_name, log_line=None):
        yield {'type': 'step', 'step': step_name, 'log': log_line or f'=== {step_name} ==='}

    def _log(self, log_line):
        yield {'type': 'log', 'log': log_line}

    def _validate_repo(self, repo_path):
        if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
            return False

        marker_files = [
            'pyproject.toml',
            'setup.py',
            'requirements.txt',
            'detect.py',
            'predict.py',
            'train.py',
        ]

        for marker in marker_files:
            if os.path.exists(os.path.join(repo_path, marker)):
                return True

        try:
            contents = os.listdir(repo_path)
            if len(contents) == 0:
                return False
            has_subdirs = any(os.path.isdir(os.path.join(repo_path, item)) for item in contents if item not in ['.git'])
            if not has_subdirs and len(contents) <= 1:
                return False
        except:
            pass

        return False

    def install(self, version_info, use_gpu=False, python_version=None, pytorch_version=None):
        mode = version_info.get('mode')
        env_name = version_info.get('env_name')
        if python_version is None:
            python_version = version_info.get('python_version', '3.10')
        if pytorch_version is None:
            pytorch_version = version_info.get('recommended_pytorch', 'latest')

        yield from self._step('创建工作目录')
        self._ensure_workspace()
        yield from self._log(f'工作目录: {self.workspace_dir}')

        yield from self._step('创建 Conda 虚拟环境')
        yield from self._log(f'环境名称: {env_name}')
        yield from self._log(f'Python 版本: {python_version}')

        env_exists = self.conda.env_exists(env_name)
        if env_exists:
            yield from self._log(f'环境 {env_name} 已存在，跳过创建')
        else:
            create_success = True
            yield from self._log('使用清华镜像源 + 精简模式加速创建...')
            for line in self.conda.create_env(env_name, python_version):
                if '[错误]' in line:
                    create_success = False
                yield from self._log(line)
            if not create_success:
                yield {'type': 'error', 'log': '虚拟环境创建失败'}
                return

        yield from self._step('配置 pip 镜像源')
        yield from self._log('正在配置清华 pip 镜像源，加速下载...')
        for line in self.conda.config_pip_mirror(env_name):
            yield from self._log(line)

        yield from self._step('安装 PyTorch')
        if use_gpu:
            yield from self._log(f'正在安装 GPU 版 PyTorch {pytorch_version} (CUDA 12.1)...')
            torch_success = True
            for line in self.conda.install_torch_cuda121(env_name, version=pytorch_version):
                if '[错误]' in line:
                    torch_success = False
                yield from self._log(line)
            if not torch_success:
                yield {'type': 'error', 'log': 'PyTorch GPU 版安装失败'}
                return
        else:
            yield from self._log(f'正在安装 CPU 版 PyTorch {pytorch_version}...')
            torch_success = True
            for line in self.conda.install_torch_cpu(env_name, version=pytorch_version):
                if '[错误]' in line:
                    torch_success = False
                yield from self._log(line)
            if not torch_success:
                yield {'type': 'error', 'log': 'PyTorch CPU 版安装失败'}
                return

        if mode == 'source':
            yield from self._install_source(version_info, env_name)
        elif mode == 'pip':
            yield from self._install_pip(version_info, env_name)
        else:
            yield {'type': 'error', 'log': f'未知的安装模式: {mode}'}
            return

        yield {'type': 'success', 'log': f'YOLO 环境部署完成！环境名称: {env_name}'}

    def reinstall_dependencies(self, version_info, env_name, pytorch_version=None, use_gpu=False):
        mode = version_info.get('mode')
        yield from self._step('重新安装依赖')
        yield from self._log('检测到依赖缺失，正在重新安装...')
        yield from self._log('第1步：升级 pip、setuptools、wheel 基础工具...')
        for line in self.conda.pip_upgrade_base(env_name):
            yield from self._log(line)

        if mode == 'source':
            yield from self._reinstall_source_deps(version_info, env_name)
        elif mode == 'pip':
            yield from self._reinstall_pip_deps(version_info, env_name)
        else:
            yield from self._log(f'未知模式: {mode}，跳过重新安装')
            return

        if pytorch_version:
            yield from self._log('第4步：重新安装指定版本的 PyTorch...')
            if use_gpu:
                yield from self._log(f'正在安装 GPU 版 PyTorch {pytorch_version} (CUDA 12.1)...')
                for line in self.conda.install_torch_cuda121(env_name, version=pytorch_version):
                    yield from self._log(line)
            else:
                yield from self._log(f'正在安装 CPU 版 PyTorch {pytorch_version}...')
                for line in self.conda.install_torch_cpu(env_name, version=pytorch_version):
                    yield from self._log(line)

        yield from self._log('依赖重新安装完成')

    def apply_compat_patches(self, version_info):
        mode = version_info.get('mode')
        if mode != 'source':
            yield from self._log('非源码模式，跳过代码补丁')
            return

        folder_name = version_info.get('folder_name')
        repo_path = os.path.join(self.workspace_dir, folder_name)

        yield from self._step('应用代码兼容补丁')
        yield from self._log('正在检查并应用兼容性补丁...')
        yield from self._apply_patches_internal(repo_path)

    def _reinstall_source_deps(self, version_info, env_name):
        folder_name = version_info.get('folder_name')
        install_method = version_info.get('install_method', 'requirements')
        repo_path = os.path.join(self.workspace_dir, folder_name)

        yield from self._log(f'第2步：重新安装源码依赖...')
        if install_method == 'editable':
            yield from self._log('正在重新安装可编辑模式依赖...')
            for line in self.conda.pip_install_editable(env_name, repo_path, force_reinstall=True):
                yield from self._log(line)
        else:
            req_path = os.path.join(repo_path, 'requirements.txt')
            if os.path.exists(req_path):
                yield from self._log(f'正在重新安装 {req_path} 中的依赖...')
                yield from self._log('使用 --force-reinstall 强制重新安装...')
                for line in self.conda.pip_install_requirements(env_name, req_path, force_reinstall=True):
                    yield from self._log(line)
            else:
                yield from self._log('未找到 requirements.txt')

        yield from self._log('第3步：安装补充依赖 (setuptools 等)...')
        extra_pkgs = ['setuptools']
        for pkg in extra_pkgs:
            for line in self.conda.pip_install(env_name, pkg, upgrade=True):
                yield from self._log(line)

    def _reinstall_pip_deps(self, version_info, env_name):
        pkg_name = version_info.get('pkg_name', 'ultralytics')
        yield from self._log(f'第2步：重新安装 {pkg_name}...')
        for line in self.conda.pip_install(env_name, pkg_name, force_reinstall=True):
            yield from self._log(line)

        yield from self._log('第3步：安装补充依赖 (setuptools 等)...')
        extra_pkgs = ['setuptools']
        for pkg in extra_pkgs:
            for line in self.conda.pip_install(env_name, pkg, upgrade=True):
                yield from self._log(line)

    def _install_source(self, version_info, env_name):
        git_urls = version_info.get('git_urls') or [version_info.get('git_url')]
        git_urls = [u for u in git_urls if u]
        folder_name = version_info.get('folder_name')
        install_method = version_info.get('install_method', 'requirements')

        if not git_urls or not folder_name:
            yield {'type': 'error', 'log': '配置缺少 git_url 或 folder_name'}
            return

        repo_path = os.path.join(self.workspace_dir, folder_name)

        yield from self._step('拉取源码')
        if os.path.exists(repo_path):
            yield from self._log(f'目录 {repo_path} 已存在，跳过克隆')
        else:
            import subprocess
            import shutil
            max_retries_per_url = 2
            clone_success = False

            yield from self._log(f'共 {len(git_urls)} 个下载源，每个源最多重试 {max_retries_per_url} 次')

            for url_idx, git_url in enumerate(git_urls):
                for retry in range(max_retries_per_url):
                    attempt_info = f'[{url_idx + 1}/{len(git_urls)}] 源{retry + 1}次尝试'
                    yield from self._log(f'{attempt_info} 从 {git_url} 克隆...')

                    if os.path.exists(repo_path):
                        shutil.rmtree(repo_path, ignore_errors=True)

                    try:
                        process = subprocess.Popen(
                            f'git clone --depth 1 {git_url} "{repo_path}"',
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            shell=True,
                            bufsize=1
                        )
                        success = True
                        for line in process.stdout:
                            line = clean_output(line)
                            if line:
                                yield from self._log(f'  {line}')
                        process.wait(timeout=600)

                        if process.returncode == 0 and os.path.exists(repo_path) and os.path.isdir(repo_path):
                            is_valid = self._validate_repo(repo_path)
                            if is_valid:
                                yield from self._log(f'✅ 克隆成功！')
                                clone_success = True
                                break
                            else:
                                yield from self._log(f'  ⚠️ 克隆的仓库为空或无效，切换到下一个源...')
                                if os.path.exists(repo_path):
                                    shutil.rmtree(repo_path, ignore_errors=True)
                        else:
                            yield from self._log(f'  克隆失败，返回码: {process.returncode}')
                            if os.path.exists(repo_path):
                                shutil.rmtree(repo_path, ignore_errors=True)
                    except subprocess.TimeoutExpired:
                        yield from self._log('  克隆超时')
                        if os.path.exists(repo_path):
                            shutil.rmtree(repo_path, ignore_errors=True)
                    except Exception as e:
                        yield from self._log(f'  克隆异常: {e}')
                        if os.path.exists(repo_path):
                            shutil.rmtree(repo_path, ignore_errors=True)

                if clone_success:
                    break

                if url_idx < len(git_urls) - 1:
                    yield from self._log(f'切换到下一个下载源...')

            if not clone_success:
                yield {'type': 'error', 'log': '所有下载源均克隆失败，请检查网络连接'}
                return

        yield from self._step('安装依赖')
        if install_method == 'editable':
            yield from self._log(f'正在以可编辑模式安装 {repo_path}...')
            yield from self._log('执行: pip install -e .')
            install_success = True
            for line in self.conda.pip_install_editable(env_name, repo_path):
                if '[错误]' in line:
                    install_success = False
                yield from self._log(line)
            if not install_success:
                yield {'type': 'error', 'log': '可编辑模式安装失败'}
                return
        else:
            req_path = os.path.join(repo_path, 'requirements.txt')
            if os.path.exists(req_path):
                yield from self._log(f'正在安装 {req_path} 中的依赖...')
                req_success = True
                for line in self.conda.pip_install_requirements(env_name, req_path):
                    if '[错误]' in line:
                        req_success = False
                    yield from self._log(line)
                if not req_success:
                    yield {'type': 'error', 'log': '依赖安装失败'}
                    return
            else:
                yield from self._log('未找到 requirements.txt，跳过依赖安装')

        yield from self._log('正在安装补充依赖 (setuptools 等)...')
        extra_pkgs = ['setuptools']
        for pkg in extra_pkgs:
            for line in self.conda.pip_install(env_name, pkg):
                yield from self._log(line)

        yield from self._step('应用代码兼容补丁')
        yield from self._apply_patches_internal(repo_path)

    def _apply_patches_internal(self, repo_path):
        import re
        import shutil
        patches_applied = 0

        for log_msg in self._patch_pkg_resources(repo_path):
            if log_msg.get('patches_applied') is not None:
                patches_applied += log_msg['patches_applied']
            else:
                yield log_msg

        for log_msg in self._patch_google_utils(repo_path):
            if log_msg.get('patches_applied') is not None:
                patches_applied += log_msg['patches_applied']
            else:
                yield log_msg

        if patches_applied == 0:
            yield from self._log('  没有需要应用的补丁')
        else:
            yield from self._log(f'  共应用了 {patches_applied} 个补丁')

    def _patch_pkg_resources(self, repo_path):
        import re
        import shutil
        general_py = os.path.join(repo_path, 'utils', 'general.py')
        if not os.path.exists(general_py):
            yield {'patches_applied': 0}
            return

        try:
            with open(general_py, 'r', encoding='utf-8') as f:
                content = f.read()

            if '_PkgCompat' in content or 'importlib.metadata' in content:
                yield from self._log('  pkg_resources 补丁已应用，跳过')
                yield {'patches_applied': 0}
                return

            pattern = re.compile(r'^([ \t]*)import\s+pkg_resources\s+as\s+pkg\s*$', re.MULTILINE)
            match = pattern.search(content)

            if not match:
                yield {'patches_applied': 0}
                return

            indent_str = match.group(1)
            if indent_str and '\t' in indent_str:
                indent_unit = '\t'
                indent_size = len(indent_str)
            elif indent_str:
                indent_unit = ' '
                indent_size = len(indent_str)
            else:
                lines = content.split('\n')
                indent_unit = '    '
                for line in lines:
                    stripped = line.lstrip()
                    if stripped and not stripped.startswith('#') and line[0] in (' ', '\t'):
                        if line[0] == '\t':
                            indent_unit = '\t'
                        else:
                            count = 0
                            for ch in line:
                                if ch == ' ':
                                    count += 1
                                else:
                                    break
                            if count >= 2:
                                indent_unit = ' ' * count
                        break

            def make_indent(level):
                if indent_unit == '\t':
                    return '\t' * level
                else:
                    return indent_unit * level

            base_indent = indent_str

            patch_lines = [
                'try:',
                make_indent(1) + 'import pkg_resources as pkg',
                'except ImportError:',
                make_indent(1) + 'import importlib.metadata as importlib_metadata',
                '',
                make_indent(1) + 'class _PkgCompat:',
                make_indent(2) + '@staticmethod',
                make_indent(2) + 'def parse_version(v):',
                make_indent(3) + 'from packaging import version',
                make_indent(3) + 'return version.parse(v)',
                '',
                make_indent(2) + '@staticmethod',
                make_indent(2) + 'def requirement(name):',
                make_indent(3) + 'try:',
                make_indent(4) + 'dist = importlib_metadata.distribution(name)',
                make_indent(4) + 'return dist.requires or []',
                make_indent(3) + 'except importlib_metadata.PackageNotFoundError:',
                make_indent(4) + 'return []',
                '',
                make_indent(2) + '@staticmethod',
                make_indent(2) + 'def get_distribution(name):',
                make_indent(3) + 'return importlib_metadata.distribution(name)',
                '',
                make_indent(1) + 'pkg = _PkgCompat()',
            ]

            full_patch_lines = []
            for line in patch_lines:
                if line:
                    full_patch_lines.append(base_indent + line)
                else:
                    full_patch_lines.append('')

            indented_patch = '\n'.join(full_patch_lines)
            new_content = pattern.sub(indented_patch, content, count=1)

            try:
                compile(new_content, general_py, 'exec')
            except SyntaxError as e:
                yield from self._log(f'  ⚠️ pkg_resources 补丁语法错误: {e}')
                yield {'patches_applied': 0}
                return

            backup_path = general_py + '.bak_before_patch'
            if not os.path.exists(backup_path):
                shutil.copy2(general_py, backup_path)

            with open(general_py, 'w', encoding='utf-8') as f:
                f.write(new_content)

            yield from self._log(f'  ✅ 已应用 pkg_resources 兼容补丁')
            yield {'patches_applied': 1}
            return

        except Exception as e:
            yield from self._log(f'  ⚠️ 应用 pkg_resources 补丁失败: {e}')
            yield {'patches_applied': 0}
            return

    def _patch_google_utils(self, repo_path):
        import shutil
        google_utils_py = os.path.join(repo_path, 'utils', 'google_utils.py')
        if not os.path.exists(google_utils_py):
            yield {'patches_applied': 0}
            return

        try:
            with open(google_utils_py, 'r', encoding='utf-8') as f:
                content = f.read()

            if '_safe_attempt_download' in content:
                yield from self._log('  google_utils 补丁已应用，跳过')
                yield {'patches_applied': 0}
                return

            if 'def attempt_download' not in content:
                yield {'patches_applied': 0}
                return

            patch_code = '''

def _safe_attempt_download(file, repo='WongKinYiu/yolov7', release='v0.1'):
    """Safe version of attempt_download that handles git tag failures."""
    import subprocess
    from urllib.request import urlretrieve

    file = Path(str(file).strip().replace("'", ''))
    if file.exists():
        return str(file)

    parent = file.parent.resolve()
    name = file.name
    parent.mkdir(parents=True, exist_ok=True)

    tag = release
    try:
        tag = subprocess.check_output('git tag', shell=True, stderr=subprocess.DEVNULL).decode().split()[-1]
    except Exception:
        pass

    assets = [name]
    try:
        import requests
        response = requests.get(f'https://api.github.com/repos/{repo}/releases/tags/{tag}').json()
        if 'assets' in response:
            assets = [x['name'] for x in response['assets']]
    except Exception:
        pass

    for asset in assets:
        if name == asset:
            url = f'https://github.com/{repo}/releases/download/{tag}/{asset}'
            try:
                print(f'Downloading {url} ...')
                urlretrieve(url, str(parent / asset))
                return str(parent / asset)
            except Exception:
                continue

    alt_urls = [
        f'https://github.com/{repo}/releases/download/{tag}/{name}',
        f'https://gh.api.99988866.xyz/https://github.com/{repo}/releases/download/{tag}/{name}',
        f'https://ghproxy.com/https://github.com/{repo}/releases/download/{tag}/{name}',
    ]
    for url in alt_urls:
        try:
            print(f'Trying {url} ...')
            urlretrieve(url, str(file))
            return str(file)
        except Exception:
            continue

    raise FileNotFoundError(f'Failed to download {name} from all sources')
'''

            import re

            pattern = re.compile(r'def attempt_download\([^)]+\):')
            match = pattern.search(content)
            if not match:
                yield {'patches_applied': 0}
                return

            new_content = content[:match.start()] + patch_code + '\n' + content[match.start():]

            new_content = new_content.replace(
                'def attempt_download(',
                'def _old_attempt_download(',
                1
            )
            new_content = new_content.replace(
                'def _safe_attempt_download',
                'def attempt_download',
                1
            )

            try:
                compile(new_content, google_utils_py, 'exec')
            except SyntaxError as e:
                yield from self._log(f'  ⚠️ google_utils 补丁语法错误: {e}')
                yield {'patches_applied': 0}
                return

            backup_path = google_utils_py + '.bak_before_patch'
            if not os.path.exists(backup_path):
                shutil.copy2(google_utils_py, backup_path)

            with open(google_utils_py, 'w', encoding='utf-8') as f:
                f.write(new_content)

            yield from self._log(f'  ✅ 已应用 google_utils 下载兼容补丁')
            yield {'patches_applied': 1}
            return

        except Exception as e:
            yield from self._log(f'  ⚠️ 应用 google_utils 补丁失败: {e}')
            yield {'patches_applied': 0}
            return

    def _install_pip(self, version_info, env_name):
        pkg_name = version_info.get('pkg_name', 'ultralytics')

        yield from self._step('安装 YOLO 包')
        yield from self._log(f'正在通过 pip 安装 {pkg_name}...')
        pip_success = True
        for line in self.conda.pip_install(env_name, pkg_name):
            if '[错误]' in line:
                pip_success = False
            yield from self._log(line)
        if not pip_success:
            yield {'type': 'error', 'log': f'{pkg_name} 安装失败'}
            return

        yield from self._log('正在安装补充依赖 (setuptools 等)...')
        extra_pkgs = ['setuptools']
        for pkg in extra_pkgs:
            for line in self.conda.pip_install(env_name, pkg):
                yield from self._log(line)
