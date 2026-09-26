import os
import yaml
import sys
import re


# GitHub release 下载加速镜像（2026-09 实测可用，空串=官方直连兜底）
GITHUB_MIRROR_PREFIXES = [
    'https://gh-proxy.com/',
    'https://ghproxy.net/',
    'https://gh.ddlc.top/',
    '',
]


def build_github_release_urls(repo, tag, name):
    """构建权重下载 URL 列表：release 标签或 latest，多镜像。"""
    if tag:
        base = f'https://github.com/{repo}/releases/download/{tag}/{name}'
    else:
        base = f'https://github.com/{repo}/releases/latest/download/{name}'
    return [prefix + base for prefix in GITHUB_MIRROR_PREFIXES]


def clean_output(text):
    text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
    text = re.sub(r'\r', '', text)
    return text.strip()


class YoloInstaller:
    def __init__(self, conda_handler, workspace_dir='yolo_workspace', config_path=None):
        self.conda = conda_handler
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.config = self._load_config(config_path)
        # 断点恢复：任务状态管理器（TaskStateManager）与已完成步骤集合，
        # 由 install(state=...) 注入；为空时所有步骤照常执行
        self._state_mgr = None
        self._completed = set()

    # ---------- 断点状态辅助 ----------

    def _st_done(self, step_name):
        return step_name in self._completed

    def _st_mark(self, step_name):
        self._completed.add(step_name)
        mgr = self._state_mgr
        if mgr is not None:
            try:
                mgr.mark_step_done(step_name)
            except Exception:
                pass

    def _st_current(self, step_name):
        mgr = self._state_mgr
        if mgr is not None:
            try:
                mgr.set_current_step(step_name)
            except Exception:
                pass

    def _load_config(self, config_path=None):
        if config_path is None:
            config_path = self._default_config_path()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'配置文件不存在: {config_path}')
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    @staticmethod
    def _default_config_path():
        """定位 repos.yaml。

        PyInstaller 打包后模块位于 PYZ 归档内，__file__ 的路径结构与真实
        解压目录不一致，因此冻结模式下必须使用 sys._MEIPASS（repos.yaml
        被打包在其根目录）；开发模式下按本文件位置向上两级推算。
        """
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            return os.path.join(base, 'repos.yaml')
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'repos.yaml')

    def get_versions(self):
        return self.config.get('yolo_versions', [])

    def get_python_versions(self):
        return self.config.get('python_versions', ['3.10', '3.9', '3.11', '3.8'])

    def get_pytorch_versions(self):
        return self.config.get('pytorch_versions', ['latest', '2.5.1', '2.4.1'])

    def _ensure_workspace(self):
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir, exist_ok=True)

    def _scaffold_dataset(self):
        """部署完成后自动创建标准数据集目录结构和 data.yaml 模板。

        已存在的 data.yaml 不会被覆盖，避免破坏用户已有配置。
        """
        data_root = os.path.join(self.workspace_dir, 'data')
        sub_dirs = [
            os.path.join('images', 'train'),
            os.path.join('images', 'val'),
            os.path.join('labels', 'train'),
            os.path.join('labels', 'val'),
        ]
        for sub in sub_dirs:
            os.makedirs(os.path.join(data_root, sub), exist_ok=True)

        yaml_path = os.path.join(data_root, 'data.yaml')
        yield from self._log(f'数据集目录: {data_root}')

        if os.path.exists(yaml_path):
            yield from self._log('data.yaml 已存在，跳过创建（不会覆盖您的配置）')
        else:
            # Windows 路径在 YAML 中统一使用正斜杠，避免反斜杠转义问题
            path_line = data_root.replace('\\', '/')
            content = (
                '# YOLO 数据集配置文件（自动生成模板，请按您的实际数据集修改）\n'
                '# 数据集根目录，train/val 路径均相对于它\n'
                f'path: {path_line}\n'
                '\n'
                '# 训练集 / 验证集图片目录（相对于 path）\n'
                'train: images/train\n'
                'val: images/val\n'
                '\n'
                '# 类别数量\n'
                'nc: 1\n'
                '\n'
                '# 类别名称：编号从 0 开始，顺序必须与标注文件中的编号一致\n'
                'names:\n'
                '  0: object\n'
            )
            with open(yaml_path, 'w', encoding='utf-8') as f:
                f.write(content)
            yield from self._log('✅ 已创建 data.yaml 模板（请修改其中的 nc 类别数量和 names 类别名称）')

        yield from self._log('目录结构:')
        yield from self._log('  data/images/train  ← 放入训练图片 (.jpg/.png)')
        yield from self._log('  data/images/val    ← 放入验证图片')
        yield from self._log('  data/labels/train  ← 放入训练标签 (.txt，与图片同名)')
        yield from self._log('  data/labels/val    ← 放入验证标签')

    def _step(self, step_name, log_line=None):
        self._st_current(step_name)
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

    def install(self, version_info, use_gpu=False, python_version=None, pytorch_version=None, state_mgr=None, resume=False):
        """部署主流程。

        参数：
            state_mgr: TaskStateManager 实例（启用断点恢复时传入）。
            resume: True 时尝试从上次中断的步骤继续，跳过 completed_steps 中的步骤。
        """
        self._state_mgr = state_mgr
        if state_mgr is not None:
            st = state_mgr.load()
            if st and resume:
                self._completed = set(st.get('completed_steps') or [])
                try:
                    invalid = state_mgr.verify_finished_files()
                    if invalid:
                        yield from self._log(
                            f'⚠️ 检测到 {len(invalid)} 个已下载文件失效/损坏，将重新下载')
                except Exception:
                    pass

        mode = version_info.get('mode')
        env_name = version_info.get('env_name')
        if python_version is None:
            python_version = version_info.get('python_version', '3.10')
        if pytorch_version is None:
            pytorch_version = version_info.get('recommended_pytorch', 'latest')

        # ----- 创建工作目录 -----
        if self._st_done('创建工作目录'):
            yield from self._log('[恢复] 步骤"创建工作目录"已完成，跳过')
        else:
            yield from self._step('创建工作目录')
            self._ensure_workspace()
            yield from self._log(f'工作目录: {self.workspace_dir}')
            self._st_mark('创建工作目录')

        # ----- 创建 Conda 虚拟环境 -----
        if self._st_done('创建 Conda 虚拟环境'):
            yield from self._log('[恢复] 步骤"创建 Conda 虚拟环境"已完成，跳过')
        else:
            yield from self._step('创建 Conda 虚拟环境')
            yield from self._log(f'环境名称: {env_name}')
            yield from self._log(f'Python 版本: {python_version}')

            env_exists = self.conda.env_exists(env_name)
            if env_exists:
                yield from self._log(f'环境 {env_name} 已存在，跳过创建')
                actual_py = self.conda.get_env_python_version(env_name)
                if actual_py:
                    yield from self._log(f'环境内实际 Python 版本: {actual_py}')
                    actual_minor = '.'.join(actual_py.split('.')[:2])
                    if actual_minor != str(python_version):
                        yield from self._log(
                            f'❌ 环境 {env_name} 实际为 Python {actual_minor}，与您选择的 {python_version} 不一致'
                        )
                        yield from self._log(
                            f'继续安装会导致包版本不匹配（如本次 PyTorch {pytorch_version} 无法安装）'
                        )
                        yield from self._log(
                            f'解决办法：点击本页面的“管理虚拟环境”按钮，一键扫描后选中 {env_name} 删除；'
                            f'然后重新部署（将按 Python {python_version} 全新创建）'
                        )
                        yield {'type': 'error', 'log': '环境 Python 版本与选择不一致，请删除旧环境后重新部署'}
                        return
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
            self._st_mark('创建 Conda 虚拟环境')

        # ----- 配置 pip 镜像源 -----
        if self._st_done('配置 pip 镜像源'):
            yield from self._log('[恢复] 步骤"配置 pip 镜像源"已完成，跳过')
        else:
            yield from self._step('配置 pip 镜像源')
            yield from self._log('正在配置清华 pip 镜像源，加速下载...')
            for line in self.conda.config_pip_mirror(env_name):
                yield from self._log(line)
            self._st_mark('配置 pip 镜像源')

        # ----- 安装 PyTorch -----
        if self._st_done('安装 PyTorch'):
            yield from self._log('[恢复] 步骤"安装 PyTorch"已完成，跳过')
        else:
            yield from self._step('安装 PyTorch')

            # 写权限检测：环境 site-packages 不可写时 pip 会错误地改装到用户目录，破坏环境隔离
            try:
                py_exe = self.conda.get_python_path(env_name)
                if py_exe:
                    import subprocess as _sp
                    check_code = (
                        "import site,os,sys; "
                        "ps=site.getsitepackages() if hasattr(site,'getsitepackages') else []; "
                        "p=ps[0] if ps else os.path.join(sys.prefix,'Lib','site-packages'); "
                        "f=os.path.join(p,'.write_test'); "
                        "open(f,'w').close(); os.remove(f); print('OK')"
                    )
                    wres = _sp.run(
                        f'"{py_exe}" -c "{check_code}"',
                        capture_output=True, text=True, shell=True, timeout=30
                    )
                    if 'OK' not in (wres.stdout or ''):
                        yield from self._log(
                            f'❌ 环境 {env_name} 的 site-packages 目录不可写，pip 将无法把包装进该环境'
                        )
                        yield from self._log(
                            '解决办法：以管理员身份运行本程序；或将 Anaconda 改装到当前用户目录（如 C:\\Users\\用户名\\Anaconda3）'
                        )
                        yield {'type': 'error', 'log': '环境目录不可写，请以管理员身份运行或改装到用户目录'}
                        return
            except Exception:
                pass

            # 版本兼容保护：PyTorch 2.5+ 要求 Python >= 3.9，Python 3.8 自动降级到 2.4.1
            if pytorch_version != 'latest':
                try:
                    t_ver = tuple(int(x) for x in str(pytorch_version).split('.')[:2])
                    p_ver = tuple(int(x) for x in str(python_version).split('.')[:2])
                    if t_ver >= (2, 5) and p_ver < (3, 9):
                        old_ver = pytorch_version
                        pytorch_version = '2.4.1'
                        yield from self._log(
                            f'⚠  PyTorch {old_ver} 不支持 Python {python_version}（2.5+ 需 Python ≥ 3.9），'
                            f'已自动切换为 PyTorch {pytorch_version}'
                        )
                except Exception:
                    pass

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
            self._st_mark('安装 PyTorch')

        # ----- 源码 / pip 安装 -----
        if mode == 'source':
            yield from self._install_source(version_info, env_name)
        elif mode == 'pip':
            yield from self._install_pip(version_info, env_name)
        else:
            yield {'type': 'error', 'log': f'未知的安装模式: {mode}'}
            return

        # ----- 初始化数据集目录 -----
        if self._st_done('初始化数据集目录'):
            yield from self._log('[恢复] 步骤"初始化数据集目录"已完成，跳过')
        else:
            yield from self._step('初始化数据集目录')
            yield from self._scaffold_dataset()
            self._st_mark('初始化数据集目录')

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

        yield from self._log('第2步：重新安装源码依赖...')
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

    def _download_default_weight(self, version_info, target_dir):
        """部署时显式下载默认权重到 target_dir（多镜像 + 流式 + ZIP 校验）。

        权重下载失败不阻断部署（环境本身可用），仅给出警告和后续处理指引。
        """
        name = version_info.get('test_weight')
        repo = version_info.get('release_repo')
        tag = (version_info.get('release_tag') or '').strip()

        if not name or not repo:
            return
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        target = os.path.join(target_dir, name)
        if os.path.exists(target) and os.path.getsize(target) > 100000:
            yield from self._log(f'权重 {name} 已存在（{os.path.getsize(target) // 1024} KB），跳过下载')
            self._st_mark('下载模型权重')
            return

        if self._st_done('下载模型权重'):
            yield from self._log('[恢复] 步骤"下载模型权重"已完成，跳过')
            return

        yield from self._step('下载模型权重')
        yield from self._log(f'默认权重: {name}（来源 {repo}）')

        urls = build_github_release_urls(repo, tag, name)
        tmp = target + '.part'

        import socket
        socket.setdefaulttimeout(300)

        ok = False
        for idx, url in enumerate(urls, 1):
            label = url if len(url) <= 100 else url[:97] + '...'
            yield from self._log(f'[{idx}/{len(urls)}] 尝试下载: {label}')

            # 断点续传：保留上次未完成的 .part，通过 Range 从断点继续
            existing = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            if existing:
                yield from self._log(
                    f'   检测到未完成文件（{existing // 1024} KB），尝试断点续传')

            try:
                import re as _re
                from urllib.request import urlopen, Request

                headers = {'Range': f'bytes={existing}-'} if existing else {}
                response = urlopen(Request(url, headers=headers), timeout=300)

                mode = 'wb'
                total = 0
                if existing:
                    if response.status == 200:
                        # 镜像不支持 Range，只能重新下载
                        yield from self._log('   该源不支持断点续传，从头下载')
                        existing = 0
                    elif response.status == 206:
                        cr = response.headers.get('Content-Range', '')
                        m = _re.match(r'bytes (\d+)-\d+/(\d+)$', cr.strip())
                        if m and int(m.group(1)) == existing:
                            mode = 'ab'
                            total = int(m.group(2))
                        else:
                            # 断点与该文件对不上（.part 可能来自不同文件），丢弃重来
                            response.close()
                            os.remove(tmp)
                            response = urlopen(Request(url), timeout=300)
                            existing = 0
                    else:
                        raise IOError(f'意外的 HTTP 状态码 {response.status}')

                if not total:
                    cl = response.headers.get('Content-Length')
                    total = int(cl) if cl else 0

                downloaded = existing
                last_pct = -10
                with response, open(tmp, mode) as f:
                    while True:
                        chunk = response.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded * 100 / total)
                            if pct >= last_pct + 10:
                                yield from self._log(
                                    f'   下载进度: {pct}%（{downloaded // 1024} KB'
                                    f'/{total // 1024} KB）')
                                last_pct = pct
                        # 发送下载进度信号（供 GUI 进度条与断点状态记录使用）
                        yield {
                            'type': 'download_progress',
                            'current': downloaded,
                            'total': total,
                            'filename': name,
                            'path': tmp,
                        }

                # 短读（downloaded < total）= 下载中断，保留 .part 供下次续传；
                # 下完整后仍不是有效 zip 才算损坏，删除避免在坏点上续传
                import zipfile
                interrupted = bool(total) and downloaded < total
                if interrupted:
                    raise IOError(f'下载中断（{downloaded}/{total} 字节）')
                if (not os.path.exists(tmp) or os.path.getsize(tmp) < 100000
                        or not zipfile.is_zipfile(tmp)):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                    raise IOError('下载文件不完整或不是有效的模型权重')

                os.replace(tmp, target)
                yield from self._log(
                    f'✅ 权重下载完成: {target}（{os.path.getsize(target) // 1024} KB）')
                # 登记完成文件（SHA256 校验值），供断点恢复时做一致性校验
                self._st_mark('下载模型权重')
                if self._state_mgr is not None:
                    try:
                        from .task_state import sha256_of
                        self._state_mgr.record_finished_file(
                            name, target, os.path.getsize(target), sha256_of(target))
                    except Exception:
                        pass
                ok = True
                break
            except Exception as e:
                # 网络中断等失败：保留 .part，下一个源继续断点续传
                yield from self._log(f'   该源失败: {type(e).__name__}: {str(e)[:120]}')
                if os.path.exists(tmp):
                    yield from self._log(
                        f'   已保留断点（{os.path.getsize(tmp) // 1024} KB），切换源后续传')

        if not ok:
            yield from self._log('⚠️  所有下载源均未成功（可能网络受限）')
            if os.path.exists(tmp):
                yield from self._log('   断点已保留，重新部署时将从断点继续下载')
            yield from self._log(
                '   您也可以稍后在“一键训练”页点“全局扫描”旁手动重试，'
                '或自行下载权重后放入工作目录')

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
            self._st_mark('拉取源码')
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
                        _ = True  # 子进程已启动
                        for line in process.stdout:
                            line = clean_output(line)
                            if line:
                                yield from self._log(f'  {line}')
                        process.wait(timeout=600)

                        if process.returncode == 0 and os.path.exists(repo_path) and os.path.isdir(repo_path):
                            is_valid = self._validate_repo(repo_path)
                            if is_valid:
                                yield from self._log('✅ 克隆成功！')
                                clone_success = True
                                break
                            else:
                                yield from self._log('  ⚠️ 克隆的仓库为空或无效，切换到下一个源...')
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
                    yield from self._log('切换到下一个下载源...')

            if not clone_success:
                yield {'type': 'error', 'log': '所有下载源均克隆失败，请检查网络连接'}
                return

            self._st_mark('拉取源码')

        yield from self._step('安装依赖')
        if self._st_done('安装依赖'):
            yield from self._log('[恢复] 步骤"安装依赖"已完成，跳过')
        else:
            install_deps_ok = yield from self._install_source_deps(version_info, env_name, repo_path, install_method)
            if not install_deps_ok:
                return
            self._st_mark('安装依赖')

        yield from self._step('应用代码兼容补丁')
        yield from self._apply_patches_internal(repo_path)

        # 显式下载默认权重到仓库根目录（训练时仓库即工作目录）
        yield from self._download_default_weight(version_info, repo_path)

    def _install_source_deps(self, version_info, env_name, repo_path, install_method):
        """源码模式依赖安装。成功返回 True，失败已产出 error 事件并返回 False。"""
        if install_method == 'editable':
            yield from self._log('正在以可编辑模式安装仓库...')
            yield from self._log('执行: pip install -e .')
            install_success = True
            for line in self.conda.pip_install_editable(env_name, repo_path):
                if '[错误]' in line:
                    install_success = False
                yield from self._log(line)
            if not install_success:
                yield {'type': 'error', 'log': '可编辑模式安装失败'}
                return False
        else:
            req_path = os.path.join(repo_path, 'requirements.txt')
            if os.path.exists(req_path):
                yield from self._log('正在安装 requirements.txt 中的依赖...')
                req_success = True
                for line in self.conda.pip_install_requirements(env_name, req_path):
                    if '[错误]' in line:
                        req_success = False
                    yield from self._log(line)
                if not req_success:
                    yield {'type': 'error', 'log': '依赖安装失败'}
                    return False
            else:
                yield from self._log('未找到 requirements.txt，跳过依赖安装')

        yield from self._log('正在安装补充依赖 (setuptools 等)...')
        extra_pkgs = ['setuptools']
        for pkg in extra_pkgs:
            for line in self.conda.pip_install(env_name, pkg):
                yield from self._log(line)
        return True

    def _apply_patches_internal(self, repo_path):
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

        for log_msg in self._patch_v9_downloads(repo_path):
            if log_msg.get('patches_applied') is not None:
                patches_applied += log_msg['patches_applied']
            else:
                yield log_msg

        for log_msg in self._patch_torch_weights_only(repo_path):
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
            elif indent_str:
                indent_unit = ' '
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

            yield from self._log('  ✅ 已应用 pkg_resources 兼容补丁')
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

            import re

            # 从原函数签名提取真实的默认仓库，避免补丁把 v5 权重错指向 v7
            sig_match = re.search(r"def attempt_download\((?P<args>[^)]*)\)", content)
            orig_repo = None
            if sig_match:
                rm = re.search(r"repo\s*=\s*['\"]([^'\"]+)['\"]", sig_match.group('args'))
                if rm:
                    orig_repo = rm.group(1)
            if not orig_repo:
                orig_repo = 'ultralytics/yolov5'
            # 浅克隆无 git tag：v7 固定 v0.1，其他系列走 latest
            default_release = 'v0.1' if 'yolov7' in orig_repo else ''

            patch_template = '''

def _safe_attempt_download(file, repo='@@REPO@@', release='@@RELEASE@@'):
    """Mirror-aware download: gh-proxy / ghproxy / ddlc + github direct."""
    import os as _os
    import subprocess
    from urllib.request import urlopen

    file = Path(str(file).strip().replace("'", ''))
    if file.exists():
        return str(file)

    parent = file.parent.resolve()
    name = file.name
    parent.mkdir(parents=True, exist_ok=True)

    tag = release
    try:
        tags = subprocess.check_output('git tag', shell=True, stderr=subprocess.DEVNULL).decode().split()
        if tags:
            tag = tags[-1]
    except Exception:
        pass

    prefixes = ['https://gh-proxy.com/', 'https://ghproxy.net/', 'https://gh.ddlc.top/', '']
    if tag:
        base = f'https://github.com/{repo}/releases/download/{tag}/{name}'
    else:
        base = f'https://github.com/{repo}/releases/latest/download/{name}'

    tmp = str(file) + '.part'
    for prefix in prefixes:
        url = prefix + base
        try:
            print(f'Trying {url} ...')
            with urlopen(url, timeout=300) as r, open(tmp, 'wb') as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            if _os.path.getsize(tmp) < 100000:
                raise IOError('downloaded file too small')
            _os.replace(tmp, str(file))
            return str(file)
        except Exception as e:
            print(f'  failed: {e}')
            try:
                _os.remove(tmp)
            except Exception:
                pass

    raise FileNotFoundError(f'Failed to download {name} from all sources')
'''
            patch_code = patch_template.replace('@@REPO@@', orig_repo).replace(
                '@@RELEASE@@', default_release)

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

            yield from self._log('  ✅ 已应用 google_utils 下载兼容补丁')
            yield {'patches_applied': 1}
            return

        except Exception as e:
            yield from self._log(f'  ⚠️ 应用 google_utils 补丁失败: {e}')
            yield {'patches_applied': 0}
            return

    def _patch_v9_downloads(self, repo_path):
        """修正 v9 utils/downloads.py：默认仓库错指 v5，且无国内镜像。

        1. attempt_download 默认仓库改为 WongKinYiu/yolov9、release v0.1
        2. 默认资产列表补全 v9 权重，GitHub API 被墙时仍能尝试下载
        3. safe_download 走 gh-proxy/ghproxy 镜像
        """
        downloads_py = os.path.join(repo_path, 'utils', 'downloads.py')
        if not os.path.exists(downloads_py):
            yield {'patches_applied': 0}
            return

        try:
            with open(downloads_py, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'v9-mirror-patch' in content:
                yield from self._log('  v9 downloads 补丁已应用，跳过')
                yield {'patches_applied': 0}
                return

            if "repo='ultralytics/yolov5'" not in content:
                yield {'patches_applied': 0}
                return

            new_content = content.replace(
                "def attempt_download(file, repo='ultralytics/yolov5', release='v7.0'):",
                "# v9-mirror-patch\n"
                "def attempt_download(file, repo='WongKinYiu/yolov9', release='v0.1'):",
                1,
            )

            old_assets = (
                "        assets = [f'yolov5{size}{suffix}.pt' for size in 'nsmlx' "
                "for suffix in ('', '6', '-cls', '-seg')]  # default"
            )
            new_assets = (
                "        assets = [f'yolov5{size}{suffix}.pt' for size in 'nsmlx' "
                "for suffix in ('', '6', '-cls', '-seg')]  # default\n"
                "        assets += ['yolov9-t-converted.pt', 'yolov9-s-converted.pt', "
                "'yolov9-m-converted.pt', 'yolov9-c-converted.pt', 'yolov9-e-converted.pt',\n"
                "                     'yolov9-s.pt', 'yolov9-m.pt', 'yolov9-c.pt', 'yolov9-e.pt',\n"
                "                     'gelan-s.pt', 'gelan-m.pt', 'gelan-c.pt', 'gelan-e.pt']"
            )
            if old_assets in new_content:
                new_content = new_content.replace(old_assets, new_assets, 1)

            old_call = """        if name in assets:
            url3 = 'https://drive.google.com/drive/folders/1EFQTEUeXWSFww0luse2jB9M1QNZQGwNl'  # backup gdrive mirror
            safe_download(
                file,
                url=f'https://github.com/{repo}/releases/download/{tag}/{name}',
                min_bytes=1E5,
                error_msg=f'{file} missing, try downloading from https://github.com/{repo}/releases/{tag} or {url3}')"""
            new_call = """        if name in assets:
            url3 = 'https://drive.google.com/drive/folders/1EFQTEUeXWSFww0luse2jB9M1QNZQGwNl'  # backup gdrive mirror
            _gh_url = f'https://github.com/{repo}/releases/download/{tag}/{name}'
            safe_download(
                file,
                url=f'https://gh-proxy.com/{_gh_url}',
                url2=f'https://ghproxy.net/{_gh_url}',
                min_bytes=1E5,
                error_msg=f'{file} missing, try downloading from {_gh_url} or {url3}')"""
            if old_call in new_content:
                new_content = new_content.replace(old_call, new_call, 1)

            try:
                compile(new_content, downloads_py, 'exec')
            except SyntaxError as e:
                yield from self._log(f'  ⚠️ v9 downloads 补丁语法错误: {e}')
                yield {'patches_applied': 0}
                return

            with open(downloads_py, 'w', encoding='utf-8') as f:
                f.write(new_content)

            yield from self._log('  ✅ 已应用 v9 downloads 下载修正补丁')
            yield {'patches_applied': 1}
            return

        except Exception as e:
            yield from self._log(f'  ⚠️ 应用 v9 downloads 补丁失败: {e}')
            yield {'patches_applied': 0}
            return

    # sitecustomize 在解释器启动时自动导入（仓库根目录位于 sys.path），
    # 一处覆盖所有 torch.load 入口：models/experimental.py、models/yolo.py、
    # hubconf.py、train.py 的 resume 等。
    _WEIGHTS_ONLY_BLOCK = '''# weights-only-patch
# PyTorch >= 2.6 将 torch.load 的默认值改为 weights_only=True，
# 拒绝含自定义类的 YOLO checkpoint（UnpicklingError）。本项目中恢复旧默认值。
try:
    import torch as _torch
    _orig_torch_load = _torch.load

    def _yolo_compat_torch_load(f, *args, **kwargs):
        kwargs.setdefault('weights_only', False)
        return _orig_torch_load(f, *args, **kwargs)

    _torch.load = _yolo_compat_torch_load
except Exception:
    pass
'''

    def _patch_torch_weights_only(self, repo_path):
        """在仓库根目录写入 sitecustomize.py，兼容 PyTorch 2.6+ 的 weights_only 默认变更。"""
        target = os.path.join(repo_path, 'sitecustomize.py')
        try:
            if os.path.exists(target):
                with open(target, 'r', encoding='utf-8') as f:
                    existing = f.read()
                if 'weights-only-patch' in existing:
                    yield from self._log('  weights_only 补丁已应用，跳过')
                    yield {'patches_applied': 0}
                    return
                # 仓库自带 sitecustomize：在末尾追加而非覆盖
                content = existing.rstrip() + '\n\n' + self._WEIGHTS_ONLY_BLOCK
            else:
                content = self._WEIGHTS_ONLY_BLOCK

            compile(content, target, 'exec')
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)

            yield from self._log('  ✅ 已应用 weights_only 兼容补丁 (sitecustomize.py)')
            yield {'patches_applied': 1}
            return
        except Exception as e:
            yield from self._log(f'  ⚠️ 应用 weights_only 补丁失败: {e}')
            yield {'patches_applied': 0}
            return

    def _install_pip(self, version_info, env_name):
        pkg_name = version_info.get('pkg_name', 'ultralytics')

        yield from self._step('安装 YOLO 包')
        if self._st_done('安装 YOLO 包'):
            yield from self._log('[恢复] 步骤"安装 YOLO 包"已完成，跳过')
        else:
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
            self._st_mark('安装 YOLO 包')

        # pip 模式下权重放到工作目录根目录
        yield from self._download_default_weight(version_info, self.workspace_dir)
