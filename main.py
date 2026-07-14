import sys
import os
import string
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QTextEdit, QGroupBox,
    QMessageBox, QProgressBar, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QFileDialog, QTabWidget, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QFont, QTextCursor, QIcon, QDesktopServices


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


from modules.env_scan import scan_environment
from modules.conda_handler import CondaHandler
from modules.yolo_installer import YoloInstaller
from modules.auto_test import AutoTester
from modules.env_installer import install_all, MINICONDA_VERSIONS, ANACONDA_VERSIONS, GIT_VERSIONS
from modules.editor_deploy import detect_editors, configure_vscode, open_in_vscode, configure_pycharm, open_in_pycharm
from modules.platform_utils import get_runtime_dir


def get_available_drives():
    from modules.platform_utils import get_available_install_locations, is_windows
    if is_windows():
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive = f'{letter}:\\'
            if os.path.exists(drive):
                drives.append(drive)
        return drives
    else:
        return get_available_install_locations()


class InstallThread(QThread):
    log_signal = pyqtSignal(str)
    step_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, conda_path, version_info, use_gpu, run_test=True,
                 python_version=None, pytorch_version=None, workspace_dir=None,
                 annotation_tool=None):
        super().__init__()
        self.conda_path = conda_path
        self.version_info = version_info
        self.use_gpu = use_gpu
        self.run_test = run_test
        self.python_version = python_version
        self.pytorch_version = pytorch_version
        self.workspace_dir = workspace_dir
        self.annotation_tool = annotation_tool

    def run(self):
        try:
            conda = CondaHandler(self.conda_path)
            config_path = get_resource_path('repos.yaml')
            if self.workspace_dir:
                installer = YoloInstaller(conda, workspace_dir=self.workspace_dir, config_path=config_path)
            else:
                installer = YoloInstaller(conda, config_path=config_path)

            for status in installer.install(
                self.version_info,
                self.use_gpu,
                python_version=self.python_version,
                pytorch_version=self.pytorch_version
            ):
                if status['type'] == 'step':
                    self.step_signal.emit(status['step'])
                    self.log_signal.emit(status['log'])
                elif status['type'] == 'log':
                    self.log_signal.emit(status['log'])
                elif status['type'] == 'error':
                    self.log_signal.emit(status['log'])
                    self.finished_signal.emit(False, status['log'])
                    return
                elif status['type'] == 'success':
                    self.log_signal.emit(status['log'])

            if self.annotation_tool:
                self._install_annotation_tools(conda, installer)

            if self.run_test:
                test_passed = self._run_test(conda, installer)
                if not test_passed:
                    self.log_signal.emit('检测到依赖缺失，正在自动重新安装依赖...')
                    self.step_signal.emit('重新安装依赖')
                    for status in installer.reinstall_dependencies(
                        self.version_info,
                        self.version_info.get('env_name'),
                        pytorch_version=self.pytorch_version,
                        use_gpu=self.use_gpu
                    ):
                        if status['type'] == 'step':
                            self.step_signal.emit(status['step'])
                            self.log_signal.emit(status['log'])
                        elif status['type'] == 'log':
                            self.log_signal.emit(status['log'])

                    self.log_signal.emit('依赖重新安装完成，正在重新运行测试...')
                    test_passed = self._run_test(conda, installer)
                    if not test_passed:
                        self.log_signal.emit('依赖重装后仍失败，正在尝试代码兼容补丁...')
                        for status in installer.apply_compat_patches(self.version_info):
                            if status['type'] == 'step':
                                self.step_signal.emit(status['step'])
                                self.log_signal.emit(status['log'])
                            elif status['type'] == 'log':
                                self.log_signal.emit(status['log'])

                        self.log_signal.emit('补丁应用完成，正在第三次运行测试...')
                        test_passed = self._run_test(conda, installer)
                        if not test_passed:
                            env_name = self.version_info.get('env_name', '')
                            ws_dir = installer.workspace_dir
                            self.log_signal.emit('')
                            self.log_signal.emit('=' * 60)
                            self.log_signal.emit('❌ 部署失败！详细信息如下：')
                            self.log_signal.emit('=' * 60)
                            self.log_signal.emit(f'环境名称: {env_name}')
                            self.log_signal.emit(f'工作目录: {ws_dir}')
                            self.log_signal.emit(f'YOLO 版本: {self.version_info.get("name", "")}')
                            self.log_signal.emit(f'Python 版本: {self.python_version or "默认"}')
                            self.log_signal.emit(f'PyTorch 版本: {self.pytorch_version or "默认"}')
                            self.log_signal.emit(f'模式: {"GPU" if self.use_gpu else "CPU"}')
                            self.log_signal.emit('')
                            self.log_signal.emit('已尝试的修复措施:')
                            self.log_signal.emit('  1. 重新安装依赖 (--force-reinstall)')
                            self.log_signal.emit('  2. 升级 pip/setuptools/wheel')
                            self.log_signal.emit('  3. 应用代码兼容补丁 (pkg_resources)')
                            self.log_signal.emit('')
                            self.log_signal.emit('常见问题排查:')
                            self.log_signal.emit('  1. 缺失模块 (ModuleNotFoundError):')
                            self.log_signal.emit(f'     可手动执行: conda activate {env_name} && pip install 缺失的包名')
                            self.log_signal.emit('  2. 网络问题导致下载失败:')
                            self.log_signal.emit('     检查网络连接，或使用国内镜像源')
                            self.log_signal.emit('  3. 查看上方日志，搜索 [错误] 或 Error 关键字')
                            self.log_signal.emit('')
                            self.log_signal.emit('请查看上方运行日志了解具体错误原因。')
                            self.log_signal.emit('=' * 60)
                            self.finished_signal.emit(
                                False,
                                f'环境测试失败：已尝试重新安装依赖和代码补丁，仍无法通过测试。\n\n'
                                f'环境名称: {env_name}\n'
                                f'工作目录: {ws_dir}\n\n'
                                f'请查看程序界面中的运行日志了解具体错误原因。'
                            )
                            return

            self.finished_signal.emit(True, '部署完成！')

        except Exception as e:
            self.log_signal.emit(f'[严重错误] {str(e)}')
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False, f'安装异常: {str(e)}')

    def _install_annotation_tools(self, conda, installer):
        self.step_signal.emit('安装标注工具')
        self.log_signal.emit('=== 安装标注工具 ===')
        tool = self.annotation_tool
        env_name = self.version_info.get('env_name')

        if not tool or tool == 'none':
            self.log_signal.emit('未选择标注工具，跳过安装')
            return

        packages = []
        if tool == 'labelImg':
            packages = ['labelImg']
        elif tool == 'labelme':
            packages = ['labelme']
        elif tool == 'both':
            packages = ['labelImg', 'labelme']

        if not packages:
            return

        for pkg in packages:
            self.log_signal.emit(f'正在安装 {pkg}...')
            for line in conda.pip_install(env_name, pkg):
                self.log_signal.emit(line)

        self.log_signal.emit('标注工具安装完成')

    def _run_test(self, conda, installer):
        from modules.auto_test import AutoTester
        self.step_signal.emit('自动化测试')
        self.log_signal.emit('=== 自动化测试 ===')
        tester = AutoTester(conda, workspace_dir=installer.workspace_dir)
        test_passed = False
        for status in tester.run_test(self.version_info):
            if status['type'] == 'step':
                self.step_signal.emit(status['step'])
                self.log_signal.emit(status['log'])
            elif status['type'] == 'log':
                self.log_signal.emit(status['log'])
            elif status['type'] == 'error':
                self.log_signal.emit(status['log'])
                test_passed = False
            elif status['type'] == 'warning':
                self.log_signal.emit(status['log'])
            elif status['type'] == 'success':
                self.log_signal.emit(status['log'])
                test_passed = True
        return test_passed


class EnvScanThread(QThread):
    finished_signal = pyqtSignal(dict)

    def run(self):
        result = scan_environment()
        self.finished_signal.emit(result)


class EnvInstallThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, conda_type='miniconda', conda_version=None, git_version=None, conda_install_path=None):
        super().__init__()
        self.conda_type = conda_type
        self.conda_version = conda_version
        self.git_version = git_version
        self.conda_install_path = conda_install_path

    def run(self):
        def log_cb(msg):
            self.log_signal.emit(msg)

        results = install_all(
            conda_type=self.conda_type,
            conda_version=self.conda_version,
            git_version=self.git_version,
            conda_install_path=self.conda_install_path,
            progress_log=log_cb
        )
        self.finished_signal.emit(results)


class AnnotationScanThread(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, conda_path, installed_envs):
        super().__init__()
        self.conda_path = conda_path
        self.installed_envs = installed_envs

    def run(self):
        result = {
            'success': False,
            'envs': [],
            'tools': {}
        }
        try:
            conda = CondaHandler(self.conda_path)
            all_envs = conda.list_envs()
            env_path_map = {e.get('name', ''): e.get('path', '') for e in all_envs}

            yolo_envs = []
            tools_info = {}

            for env_name, env_info in self.installed_envs.items():
                if env_name not in env_path_map:
                    continue
                env_path = env_path_map[env_name]
                env_data = {'name': env_name, 'path': env_path}
                env_data['version_name'] = env_info.get('version_name', '')
                yolo_envs.append(env_data)

                has_labelimg = False
                has_labelme = False
                if env_path and os.path.exists(env_path):
                    from modules.platform_utils import is_windows
                    if is_windows():
                        scripts_dir = os.path.join(env_path, 'Scripts')
                        labelimg_exe = 'labelImg.exe'
                        labelme_exe = 'labelme.exe'
                    else:
                        scripts_dir = os.path.join(env_path, 'bin')
                        labelimg_exe = 'labelImg'
                        labelme_exe = 'labelme'
                    if os.path.exists(scripts_dir):
                        has_labelimg = os.path.exists(os.path.join(scripts_dir, labelimg_exe))
                        has_labelme = os.path.exists(os.path.join(scripts_dir, labelme_exe))
                    # 额外检查：用 Python 导入方式检测
                    python_exe = os.path.join(env_path, 'bin', 'python') if not is_windows() else os.path.join(env_path, 'python.exe')
                    if not has_labelimg and os.path.exists(python_exe):
                        import subprocess
                        try:
                            r = subprocess.run(
                                [python_exe, '-c', 'import labelImg; print(labelImg.__file__)'],
                                capture_output=True, text=True, timeout=10
                            )
                            has_labelimg = r.returncode == 0
                        except Exception:
                            pass
                    if not has_labelme and os.path.exists(python_exe):
                        import subprocess
                        try:
                            r = subprocess.run(
                                [python_exe, '-c', 'import labelme; print(labelme.__file__)'],
                                capture_output=True, text=True, timeout=10
                            )
                            has_labelme = r.returncode == 0
                        except Exception:
                            pass
                tools_info[env_name] = {
                    'labelImg': has_labelimg,
                    'labelme': has_labelme
                }

            result['success'] = True
            result['envs'] = yolo_envs
            result['tools'] = tools_info
        except Exception as e:
            result['error'] = str(e)

        self.finished_signal.emit(result)


class AnnotationToolInstallThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, str, str)

    def __init__(self, conda_path, env_name, tool_name, is_install):
        super().__init__()
        self.conda_path = conda_path
        self.env_name = env_name
        self.tool_name = tool_name
        self.is_install = is_install

    def run(self):
        success = False
        error_msg = ''
        try:
            conda = CondaHandler(self.conda_path)
            action = '安装' if self.is_install else '卸载'
            self.log_signal.emit(f'正在{action} {self.tool_name}...')

            if self.is_install:
                for line in conda.pip_install(self.env_name, self.tool_name, index_url='https://pypi.tuna.tsinghua.edu.cn/simple'):
                    self.log_signal.emit(line)
                success = True
            else:
                for line in conda.pip_uninstall(self.env_name, self.tool_name):
                    self.log_signal.emit(line)
                success = True

            if success:
                self.log_signal.emit(f'✅ {self.tool_name} {action}成功')
        except Exception as e:
            error_msg = str(e)
            self.log_signal.emit(f'❌ {action}失败: {e}')

        action = '安装' if self.is_install else '卸载'
        self.finished_signal.emit(success, self.env_name, self.tool_name, error_msg)


class EnvInstallDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('自动安装环境配置')
        self.setMinimumWidth(520)
        self._drives = get_available_drives()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.conda_type_combo = QComboBox()
        self.conda_type_combo.addItem('Miniconda3（推荐，体积小，约 100MB）', 'miniconda')
        self.conda_type_combo.addItem('Anaconda3（完整版，约 1GB）', 'anaconda')
        self.conda_type_combo.currentIndexChanged.connect(self._on_conda_type_changed)
        form_layout.addRow('Conda 类型:', self.conda_type_combo)

        self.conda_version_combo = QComboBox()
        self._update_conda_versions('miniconda')
        form_layout.addRow('Conda 版本:', self.conda_version_combo)

        self.git_version_combo = QComboBox()
        for v in GIT_VERSIONS:
            self.git_version_combo.addItem(v, v)
        form_layout.addRow('Git 版本:', self.git_version_combo)

        conda_path_group = QGroupBox('Conda 安装路径')
        conda_path_layout = QVBoxLayout()

        drive_layout = QHBoxLayout()
        from modules.platform_utils import is_windows
        if is_windows():
            drive_label_text = '安装盘符:'
        else:
            drive_label_text = '安装位置:'
        drive_label = QLabel(drive_label_text)
        self.conda_drive_combo = QComboBox()
        for d in self._drives:
            self.conda_drive_combo.addItem(d, d)
        if self._drives:
            self.conda_drive_combo.setCurrentIndex(0)
        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.conda_drive_combo)

        folder_layout = QHBoxLayout()
        folder_label = QLabel('文件夹名:')
        self.conda_folder_edit = QLineEdit('Miniconda3')
        self.conda_drive_combo.currentIndexChanged.connect(self._update_path_preview)
        self.conda_folder_edit.textChanged.connect(self._update_path_preview)
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.conda_folder_edit)

        self.conda_path_preview = QLabel()
        self.conda_path_preview.setStyleSheet('color: #666; font-size: 11px;')
        self._update_path_preview()

        conda_path_layout.addLayout(drive_layout)
        conda_path_layout.addLayout(folder_layout)
        conda_path_layout.addWidget(self.conda_path_preview)
        conda_path_group.setLayout(conda_path_layout)

        layout.addLayout(form_layout)
        layout.addWidget(conda_path_group)

        hint_label = QLabel(
            '💡 提示：\n'
            '  • 选择 Miniconda3 即可满足 YOLO 运行需求，安装速度快\n'
            '  • Anaconda3 包含完整的科学计算包，体积较大\n'
            '  • 默认版本都是经过测试的稳定版本，建议保持默认\n'
            '  • 建议安装在 C 盘以外的盘符，节省系统盘空间'
        )
        hint_label.setStyleSheet('color: #666; font-size: 11px;')
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_conda_type_changed(self, index):
        conda_type = self.conda_type_combo.currentData()
        self._update_conda_versions(conda_type)
        if conda_type == 'anaconda':
            self.conda_folder_edit.setText('Anaconda3')
        else:
            self.conda_folder_edit.setText('Miniconda3')

    def _update_conda_versions(self, conda_type):
        self.conda_version_combo.clear()
        if conda_type == 'miniconda':
            for v in MINICONDA_VERSIONS:
                self.conda_version_combo.addItem(v, v)
        else:
            for v in ANACONDA_VERSIONS:
                self.conda_version_combo.addItem(v, v)

    def _update_path_preview(self):
        drive = self.conda_drive_combo.currentData()
        folder = self.conda_folder_edit.text().strip()
        if drive and folder:
            from modules.platform_utils import normalize_path
            path = normalize_path(os.path.join(drive, folder))
            self.conda_path_preview.setText(f'完整路径: {path}')

    def get_config(self):
        drive = self.conda_drive_combo.currentData()
        folder = self.conda_folder_edit.text().strip()
        install_path = None
        if drive and folder:
            from modules.platform_utils import normalize_path
            install_path = normalize_path(os.path.join(drive, folder))
        return {
            'conda_type': self.conda_type_combo.currentData(),
            'conda_version': self.conda_version_combo.currentData(),
            'git_version': self.git_version_combo.currentData(),
            'conda_install_path': install_path,
        }


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('关于 YOLO AutoInstaller')
        self.setFixedSize(420, 380)
        self.setModal(True)

        icon_path = get_resource_path('assets/app.png')
        if not os.path.exists(icon_path):
            icon_path = get_resource_path('assets/app.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        icon_label = QLabel()
        if os.path.exists(icon_path):
            pixmap = QIcon(icon_path).pixmap(80, 80)
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel('YOLO 全版本一键部署工具')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        info_text = QLabel()
        info_text.setTextFormat(Qt.TextFormat.RichText)
        info_text.setAlignment(Qt.AlignmentFlag.AlignLeft)
        info_text.setWordWrap(True)
        info_text.setText('''
<div style="font-size: 13px; line-height: 1.8;">
<p style="margin: 4px 0;"><b>作者：</b>JockerSilas</p>
<p style="margin: 4px 0;"><b>个人博客：</b><a href="https://songnas.dpdns.org/" style="color: #165DFF; text-decoration: none;">songnas.dpdns.org</a></p>
<p style="margin: 4px 0;"><b>GitHub：</b><a href="https://github.com/alansong49/" style="color: #165DFF; text-decoration: none;">github.com/alansong49</a></p>
</div>
''')
        info_text.setOpenExternalLinks(True)
        info_text.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        layout.addWidget(info_text)

        thanks_label = QLabel(
            '🎉 感谢您的使用与支持！\n'
            '您的每一份支持都是我持续前进的动力！'
        )
        thanks_font = QFont()
        thanks_font.setPointSize(11)
        thanks_label.setFont(thanks_font)
        thanks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks_label.setStyleSheet('color: #666; padding: 8px;')
        layout.addWidget(thanks_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton('我知道了')
        ok_btn.setMinimumWidth(120)
        ok_btn.setMinimumHeight(32)
        ok_btn.setStyleSheet('''
            QPushButton {
                background-color: #165DFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #0F42C9;
            }
        ''')
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.env_result = None
        self.install_thread = None
        self.env_scan_thread = None
        self.env_install_thread = None
        self._anno_scan_thread = None
        self._anno_install_thread = None
        self._editor_deploy_thread = None
        self._editors = {}
        self._drives = get_available_drives()
        self._log_lines = []
        self._current_workspace = None
        self._current_env_name = None
        self.init_ui()
        QTimer.singleShot(300, self.show_about)
        QTimer.singleShot(800, self.auto_scan_env)

    def init_ui(self):
        self.setWindowTitle('YOLO 全版本一键部署工具')
        self.setGeometry(100, 100, 850, 720)
        self.setMinimumSize(680, 560)

        # 设置窗口图标
        icon_path = get_resource_path('assets/app.png')
        if not os.path.exists(icon_path):
            icon_path = get_resource_path('assets/app.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        title_label = QLabel('YOLO 全版本一键部署 GUI 工具')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        env_group = QGroupBox('系统环境检测')
        env_layout = QVBoxLayout()
        env_layout.setSpacing(8)

        info_grid = QGridLayout()
        info_grid.setSpacing(6)

        self.conda_label = QLabel('Conda: 未检测')
        self.git_label = QLabel('Git: 未检测')
        self.gpu_label = QLabel('显卡: 未检测')

        info_grid.addWidget(self.conda_label, 0, 0)
        info_grid.addWidget(self.git_label, 0, 1)
        info_grid.addWidget(self.gpu_label, 1, 0)

        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton('🔄 重新扫描')
        self.scan_btn.setMinimumHeight(30)
        self.scan_btn.clicked.connect(self.scan_environment)
        self.install_env_btn = QPushButton('🔧 自动安装环境')
        self.install_env_btn.setMinimumHeight(30)
        self.install_env_btn.setStyleSheet(
            'QPushButton { background-color: #2196F3; color: white; border: none; border-radius: 4px; padding: 6px 12px; }'
            'QPushButton:hover { background-color: #1976D2; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.install_env_btn.clicked.connect(self.start_env_install)
        self.browse_conda_btn = QPushButton('📁 指定 Conda 路径')
        self.browse_conda_btn.setMinimumHeight(30)
        self.browse_conda_btn.clicked.connect(self._browse_conda_path)
        self.global_scan_btn = QPushButton('🔍 全局扫描 Conda')
        self.global_scan_btn.setMinimumHeight(30)
        self.global_scan_btn.clicked.connect(self._global_scan_conda)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addWidget(self.install_env_btn)
        btn_layout.addWidget(self.browse_conda_btn)
        btn_layout.addWidget(self.global_scan_btn)
        btn_layout.addStretch()

        env_layout.addLayout(info_grid)
        env_layout.addLayout(btn_layout)
        env_group.setLayout(env_layout)
        main_layout.addWidget(env_group)

        self.tab_widget = QTabWidget()
        self._init_deploy_tab()
        self._init_annotation_tab()
        self._init_editor_deploy_tab()
        main_layout.addWidget(self.tab_widget, stretch=3)

        log_group = QGroupBox('运行日志')
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Consolas', 9))
        self.log_text.setMinimumHeight(180)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, stretch=2)

    def _init_deploy_tab(self):
        deploy_tab = QWidget()
        tab_layout = QVBoxLayout(deploy_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        deploy_layout = QVBoxLayout(content)
        deploy_layout.setSpacing(12)

        config_group = QGroupBox('部署配置')
        config_layout = QVBoxLayout()
        config_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnMinimumWidth(0, 90)
        grid.setColumnMinimumWidth(2, 90)

        version_label = QLabel('YOLO 版本:')
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(30)
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        grid.addWidget(version_label, 0, 0)
        grid.addWidget(self.version_combo, 0, 1, 1, 3)

        py_label = QLabel('Python 版本:')
        py_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.python_combo = QComboBox()
        self.python_combo.setMinimumHeight(30)
        grid.addWidget(py_label, 1, 0)
        grid.addWidget(self.python_combo, 1, 1)

        torch_label = QLabel('PyTorch 版本:')
        torch_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.pytorch_combo = QComboBox()
        self.pytorch_combo.setMinimumHeight(30)
        grid.addWidget(torch_label, 1, 2)
        grid.addWidget(self.pytorch_combo, 1, 3)

        from modules.platform_utils import is_windows
        if is_windows():
            drive_label_text = '安装盘符:'
        else:
            drive_label_text = '安装位置:'
        drive_label = QLabel(drive_label_text)
        drive_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.workspace_drive_combo = QComboBox()
        self.workspace_drive_combo.setMinimumHeight(30)
        for d in self._drives:
            self.workspace_drive_combo.addItem(d, d)
        if is_windows():
            default_workspace_drive = 'E:' if 'E:' in self._drives else ('D:' if 'D:' in self._drives else 'C:')
            idx = self.workspace_drive_combo.findData(default_workspace_drive)
            if idx >= 0:
                self.workspace_drive_combo.setCurrentIndex(idx)
        elif self._drives:
            self.workspace_drive_combo.setCurrentIndex(0)
        grid.addWidget(drive_label, 2, 0)
        grid.addWidget(self.workspace_drive_combo, 2, 1)

        folder_label = QLabel('工作目录:')
        folder_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.workspace_folder_edit = QLineEdit('yolo_workspace')
        self.workspace_folder_edit.setMinimumHeight(30)
        grid.addWidget(folder_label, 2, 2)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.workspace_folder_edit)
        self.browse_btn = QPushButton('📁')
        self.browse_btn.setMinimumHeight(30)
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.clicked.connect(self._browse_workspace)
        folder_layout.addWidget(self.browse_btn)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_layout)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(folder_widget, 2, 3)

        annotation_label = QLabel('标注工具:')
        annotation_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.annotation_combo = QComboBox()
        self.annotation_combo.setMinimumHeight(30)
        grid.addWidget(annotation_label, 3, 0)
        grid.addWidget(self.annotation_combo, 3, 1, 1, 3)

        config_layout.addLayout(grid)

        self.workspace_path_preview = QLabel()
        self.workspace_path_preview.setStyleSheet('color: #666; font-size: 11px;')
        self.workspace_drive_combo.currentIndexChanged.connect(self._update_workspace_preview)
        self.workspace_folder_edit.textChanged.connect(self._update_workspace_preview)
        self._update_workspace_preview()
        config_layout.addWidget(self.workspace_path_preview)

        self.gpu_checkbox = QCheckBox('使用 CUDA GPU 版本（需要 NVIDIA 显卡）')
        config_layout.addWidget(self.gpu_checkbox)

        self.test_checkbox = QCheckBox('安装完成后自动运行测试')
        self.test_checkbox.setChecked(True)
        config_layout.addWidget(self.test_checkbox)

        config_group.setLayout(config_layout)
        deploy_layout.addWidget(config_group)

        self.install_btn = QPushButton('🚀 开始一键安装部署')
        self.install_btn.setMinimumHeight(48)
        install_font = QFont()
        install_font.setPointSize(13)
        install_font.setBold(True)
        self.install_btn.setFont(install_font)
        self.install_btn.setStyleSheet(
            'QPushButton { background-color: #4CAF50; color: white; border: none; border-radius: 6px; }'
            'QPushButton:hover { background-color: #45a049; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.install_btn.clicked.connect(self.start_install)
        deploy_layout.addWidget(self.install_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        deploy_layout.addWidget(self.progress_bar)

        deploy_layout.addSpacing(8)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(deploy_tab, '🚀 一键部署')

    def _init_annotation_tab(self):
        anno_tab = QWidget()
        tab_layout = QVBoxLayout(anno_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        anno_layout = QVBoxLayout(content)
        anno_layout.setSpacing(12)

        env_group = QGroupBox('环境管理')
        env_layout = QVBoxLayout()
        env_layout.setSpacing(8)

        env_select_row = QHBoxLayout()
        env_label = QLabel('已安装环境:')
        env_label.setMinimumWidth(90)
        env_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.anno_env_combo = QComboBox()
        self.anno_env_combo.setMinimumHeight(32)
        self.anno_env_combo.currentIndexChanged.connect(self._on_anno_env_changed)
        env_select_row.addWidget(env_label)
        env_select_row.addSpacing(8)
        env_select_row.addWidget(self.anno_env_combo, 1)
        env_layout.addLayout(env_select_row)

        env_layout.addSpacing(4)

        self.anno_env_label = QLabel('暂无已安装环境')
        self.anno_env_label.setStyleSheet('color: #666; padding-left: 98px;')
        self.anno_env_label.setWordWrap(True)
        env_layout.addWidget(self.anno_env_label)

        self.anno_tools_info = QLabel('标注工具: 未检测')
        self.anno_tools_info.setStyleSheet('color: #666; padding-left: 98px;')
        self.anno_tools_info.setWordWrap(True)
        env_layout.addWidget(self.anno_tools_info)

        env_layout.addSpacing(6)

        btn_row = QHBoxLayout()
        self.refresh_anno_btn = QPushButton('🔄 刷新')
        self.refresh_anno_btn.setMinimumWidth(80)
        self.refresh_anno_btn.clicked.connect(self._refresh_annotation_envs)
        btn_row.addWidget(self.refresh_anno_btn)

        self.add_env_btn = QPushButton('➕ 添加')
        self.add_env_btn.setMinimumWidth(80)
        self.add_env_btn.clicked.connect(self._add_annotation_env)
        btn_row.addWidget(self.add_env_btn)

        self.remove_env_btn = QPushButton('➖ 移除')
        self.remove_env_btn.setMinimumWidth(80)
        self.remove_env_btn.setStyleSheet('QPushButton { color: #d32f2f; }')
        self.remove_env_btn.clicked.connect(self._remove_annotation_env)
        self.remove_env_btn.setEnabled(False)
        btn_row.addWidget(self.remove_env_btn)

        btn_row.addStretch()
        env_layout.addLayout(btn_row)

        env_group.setLayout(env_layout)
        anno_layout.addWidget(env_group)

        tools_group = QGroupBox('启动标注工具')
        tools_layout = QVBoxLayout()
        tools_layout.setSpacing(10)

        launch_row = QHBoxLayout()
        self.launch_labelimg_btn = QPushButton('🎨 启动 LabelImg')
        self.launch_labelimg_btn.setMinimumHeight(42)
        self.launch_labelimg_btn.setStyleSheet(
            'QPushButton { background-color: #FF9800; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; }'
            'QPushButton:hover { background-color: #F57C00; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.launch_labelimg_btn.clicked.connect(lambda: self._launch_annotation_tool('labelImg'))
        self.launch_labelimg_btn.setEnabled(False)
        launch_row.addWidget(self.launch_labelimg_btn)

        self.launch_labelme_btn = QPushButton('🖌️  启动 LabelMe')
        self.launch_labelme_btn.setMinimumHeight(42)
        self.launch_labelme_btn.setStyleSheet(
            'QPushButton { background-color: #9C27B0; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; }'
            'QPushButton:hover { background-color: #7B1FA2; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.launch_labelme_btn.clicked.connect(lambda: self._launch_annotation_tool('labelme'))
        self.launch_labelme_btn.setEnabled(False)
        launch_row.addWidget(self.launch_labelme_btn)

        tools_layout.addLayout(launch_row)

        tools_group.setLayout(tools_layout)
        anno_layout.addWidget(tools_group)

        install_group = QGroupBox('安装 / 卸载标注工具')
        install_layout = QVBoxLayout()
        install_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        labelimg_title = QLabel('🎨 LabelImg')
        labelimg_title.setStyleSheet('font-weight: bold;')
        grid.addWidget(labelimg_title, 0, 0)

        self.install_labelimg_btn = QPushButton('📦 安装')
        self.install_labelimg_btn.setMinimumHeight(30)
        self.install_labelimg_btn.clicked.connect(lambda: self._install_annotation_tool('labelImg', True))
        self.install_labelimg_btn.setEnabled(False)
        grid.addWidget(self.install_labelimg_btn, 0, 1)

        self.uninstall_labelimg_btn = QPushButton('🗑️  卸载')
        self.uninstall_labelimg_btn.setMinimumHeight(30)
        self.uninstall_labelimg_btn.setStyleSheet(
            'QPushButton { color: #d32f2f; }'
            'QPushButton:disabled { color: #999; }'
        )
        self.uninstall_labelimg_btn.clicked.connect(lambda: self._install_annotation_tool('labelImg', False))
        self.uninstall_labelimg_btn.setEnabled(False)
        grid.addWidget(self.uninstall_labelimg_btn, 0, 2)

        labelme_title = QLabel('🖌️  LabelMe')
        labelme_title.setStyleSheet('font-weight: bold;')
        grid.addWidget(labelme_title, 1, 0)

        self.install_labelme_btn = QPushButton('📦 安装')
        self.install_labelme_btn.setMinimumHeight(30)
        self.install_labelme_btn.clicked.connect(lambda: self._install_annotation_tool('labelme', True))
        self.install_labelme_btn.setEnabled(False)
        grid.addWidget(self.install_labelme_btn, 1, 1)

        self.uninstall_labelme_btn = QPushButton('🗑️  卸载')
        self.uninstall_labelme_btn.setMinimumHeight(30)
        self.uninstall_labelme_btn.setStyleSheet(
            'QPushButton { color: #d32f2f; }'
            'QPushButton:disabled { color: #999; }'
        )
        self.uninstall_labelme_btn.clicked.connect(lambda: self._install_annotation_tool('labelme', False))
        self.uninstall_labelme_btn.setEnabled(False)
        grid.addWidget(self.uninstall_labelme_btn, 1, 2)

        install_layout.addLayout(grid)

        self.anno_install_status = QLabel('选择环境后可安装或卸载标注工具')
        self.anno_install_status.setStyleSheet('color: #666; font-size: 11px;')
        install_layout.addWidget(self.anno_install_status)

        install_group.setLayout(install_layout)
        anno_layout.addWidget(install_group)

        hint_label = QLabel(
            '💡 说明：\n'
            '  • LabelImg：适合矩形框标注，直接输出 YOLO 格式\n'
            '  • LabelMe：支持多边形标注，需转换为 YOLO 格式'
        )
        hint_label.setStyleSheet('color: #666; font-size: 11px;')
        hint_label.setWordWrap(True)
        anno_layout.addWidget(hint_label)

        anno_layout.addSpacing(8)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(anno_tab, '🏷️  标注工具')

    def _init_editor_deploy_tab(self):
        deploy_tab = QWidget()
        tab_layout = QVBoxLayout(deploy_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        deploy_layout = QVBoxLayout(content)
        deploy_layout.setSpacing(12)

        config_group = QGroupBox('部署配置')
        config_layout = QVBoxLayout()
        config_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnMinimumWidth(0, 90)
        grid.setColumnMinimumWidth(2, 90)

        env_label = QLabel('已安装环境:')
        env_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.editor_env_combo = QComboBox()
        self.editor_env_combo.setMinimumHeight(30)
        self.editor_env_combo.currentIndexChanged.connect(self._on_editor_env_changed)
        grid.addWidget(env_label, 0, 0)
        grid.addWidget(self.editor_env_combo, 0, 1, 1, 3)

        project_label = QLabel('项目目录:')
        project_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.editor_project_edit = QLineEdit()
        self.editor_project_edit.setMinimumHeight(30)
        self.editor_project_edit.setPlaceholderText('选择 YOLO 项目目录')
        grid.addWidget(project_label, 1, 0)
        grid.addWidget(self.editor_project_edit, 1, 1, 1, 2)
        self.editor_browse_btn = QPushButton('📁 浏览')
        self.editor_browse_btn.setMinimumHeight(30)
        self.editor_browse_btn.clicked.connect(self._browse_editor_project)
        grid.addWidget(self.editor_browse_btn, 1, 3)

        config_layout.addLayout(grid)

        self.editor_env_info = QLabel('请选择要部署的 YOLO 环境')
        self.editor_env_info.setStyleSheet('color: #666; padding-left: 98px;')
        self.editor_env_info.setWordWrap(True)
        config_layout.addWidget(self.editor_env_info)

        refresh_btn_row = QHBoxLayout()
        self.refresh_editor_btn = QPushButton('🔄 刷新环境')
        self.refresh_editor_btn.setMinimumWidth(100)
        self.refresh_editor_btn.clicked.connect(self._refresh_editor_envs)
        refresh_btn_row.addWidget(self.refresh_editor_btn)
        refresh_btn_row.addStretch()
        config_layout.addLayout(refresh_btn_row)

        config_group.setLayout(config_layout)
        deploy_layout.addWidget(config_group)

        editor_group = QGroupBox('编辑器选择')
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(10)

        editor_row = QHBoxLayout()
        self.editor_vscode_check = QCheckBox('📝 Visual Studio Code')
        self.editor_vscode_check.setChecked(True)
        self.editor_vscode_check.setMinimumHeight(28)
        editor_row.addWidget(self.editor_vscode_check)
        editor_row.addSpacing(20)
        self.editor_pycharm_check = QCheckBox('🐍 PyCharm')
        self.editor_pycharm_check.setMinimumHeight(28)
        editor_row.addWidget(self.editor_pycharm_check)
        editor_row.addStretch()
        editor_layout.addLayout(editor_row)

        self.editor_status_label = QLabel('检测中...')
        self.editor_status_label.setStyleSheet('color: #666; padding-left: 4px;')
        editor_layout.addWidget(self.editor_status_label)

        editor_group.setLayout(editor_layout)
        deploy_layout.addWidget(editor_group)

        action_group = QGroupBox('操作')
        action_layout = QVBoxLayout()
        action_layout.setSpacing(10)

        btn_row = QHBoxLayout()

        self.deploy_editor_btn = QPushButton('⚙️  配置环境')
        self.deploy_editor_btn.setMinimumHeight(42)
        self.deploy_editor_btn.setStyleSheet(
            'QPushButton { background-color: #2196F3; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; }'
            'QPushButton:hover { background-color: #1976D2; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.deploy_editor_btn.clicked.connect(self._deploy_to_editors)
        self.deploy_editor_btn.setEnabled(False)
        btn_row.addWidget(self.deploy_editor_btn, 1)

        btn_row.addSpacing(10)

        self.open_editor_btn = QPushButton('🚀 打开编辑器')
        self.open_editor_btn.setMinimumHeight(42)
        self.open_editor_btn.setStyleSheet(
            'QPushButton { background-color: #4CAF50; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; }'
            'QPushButton:hover { background-color: #45a049; }'
            'QPushButton:disabled { background-color: #cccccc; color: #666666; }'
        )
        self.open_editor_btn.clicked.connect(self._open_in_editors)
        self.open_editor_btn.setEnabled(False)
        btn_row.addWidget(self.open_editor_btn, 1)

        action_layout.addLayout(btn_row)

        action_group.setLayout(action_layout)
        deploy_layout.addWidget(action_group)

        tip_label = QLabel(
            '💡 说明：\n'
            '  • VSCode：自动配置 Python 解释器和调试配置\n'
            '  • PyCharm：提供配置说明，需手动设置解释器'
        )
        tip_label.setStyleSheet('color: #666; font-size: 11px;')
        tip_label.setWordWrap(True)
        deploy_layout.addWidget(tip_label)

        deploy_layout.addSpacing(8)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(deploy_tab, '🔧 环境部署')

    def _refresh_annotation_envs(self):
        if not self.env_result or not self.env_result['conda_path']:
            self.anno_env_label.setText('❌ 未检测到 Conda，请先在「一键部署」页面安装环境')
            self.anno_env_label.setStyleSheet('color: red;')
            self.refresh_anno_btn.setEnabled(True)
            return

        if self._anno_scan_thread and self._anno_scan_thread.isRunning():
            return

        self.anno_env_label.setText('🔍 正在检测已安装环境...')
        self.anno_env_label.setStyleSheet('color: #1976D2;')
        self.refresh_anno_btn.setEnabled(False)
        self.anno_env_combo.clear()
        self.anno_tools_info.setText('标注工具: 检测中...')
        self.launch_labelimg_btn.setEnabled(False)
        self.launch_labelme_btn.setEnabled(False)

        self._anno_scan_thread = AnnotationScanThread(
            self.env_result['conda_path'],
            self._load_installed_envs()
        )
        self._anno_scan_thread.finished_signal.connect(self._on_anno_scan_finished)
        self._anno_scan_thread.start()

    def _on_anno_scan_finished(self, result):
        self.refresh_anno_btn.setEnabled(True)

        if not result.get('success'):
            error = result.get('error', '未知错误')
            self.anno_env_label.setText(f'❌ 检测失败: {error}')
            self.anno_env_label.setStyleSheet('color: red;')
            self.anno_tools_info.setText('标注工具: 检测失败')
            return

        envs = result.get('envs', [])
        tools = result.get('tools', {})
        self._annotation_envs = tools

        if not envs:
            self.anno_env_label.setText('⚠️  暂无已安装环境，请先在「一键部署」页面安装')
            self.anno_env_label.setStyleSheet('color: orange;')
            self.anno_tools_info.setText('标注工具: 未检测')
            self.remove_env_btn.setEnabled(False)
            return

        for env in envs:
            env_name = env.get('name', '')
            if not env_name:
                continue
            tool_info = tools.get(env_name, {})
            has_labelimg = tool_info.get('labelImg', False)
            has_labelme = tool_info.get('labelme', False)
            version_name = env.get('version_name', '')
            display = env_name
            if version_name:
                display += f'  ({version_name})'
            tool_names = []
            if has_labelimg:
                tool_names.append('LabelImg')
            if has_labelme:
                tool_names.append('LabelMe')
            if tool_names:
                display += f'  [有: {", ".join(tool_names)}]'
            else:
                display += '  [无标注工具]'
            self.anno_env_combo.addItem(display, env_name)

        self.anno_env_label.setText(f'✅ 已检测到 {len(envs)} 个已安装环境')
        self.anno_env_label.setStyleSheet('color: green;')

        if self.anno_env_combo.count() > 0:
            self.remove_env_btn.setEnabled(True)
            self._on_anno_env_changed(0)

    def _on_anno_env_changed(self, index):
        if index < 0:
            return
        env_name = self.anno_env_combo.itemData(index)
        if not env_name or env_name not in self._annotation_envs:
            return

        tools = self._annotation_envs[env_name]
        has_labelimg = tools.get('labelImg', False)
        has_labelme = tools.get('labelme', False)

        tool_list = []
        if has_labelimg:
            tool_list.append('✅ LabelImg')
        else:
            tool_list.append('❌ LabelImg')
        if has_labelme:
            tool_list.append('✅ LabelMe')
        else:
            tool_list.append('❌ LabelMe')

        self.anno_tools_info.setText('标注工具: ' + '  |  '.join(tool_list))
        self.launch_labelimg_btn.setEnabled(has_labelimg)
        self.launch_labelme_btn.setEnabled(has_labelme)
        self.install_labelimg_btn.setEnabled(not has_labelimg)
        self.uninstall_labelimg_btn.setEnabled(has_labelimg)
        self.install_labelme_btn.setEnabled(not has_labelme)
        self.uninstall_labelme_btn.setEnabled(has_labelme)
        self.remove_env_btn.setEnabled(True)
        self.anno_install_status.setText('选择环境后可安装或卸载标注工具')
        self.anno_install_status.setStyleSheet('color: #666; font-size: 11px;')

    def _install_annotation_tool(self, tool_name, is_install):
        if not self.env_result or not self.env_result['conda_path']:
            QMessageBox.warning(self, '提示', '未检测到 Conda 环境。')
            return

        index = self.anno_env_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '提示', '请先选择 YOLO 环境。')
            return

        env_name = self.anno_env_combo.itemData(index)
        if not env_name:
            return

        action = '安装' if is_install else '卸载'
        reply = QMessageBox.question(
            self, f'确认{action}',
            f'确定要{action} {tool_name} 吗？\n\n环境: {env_name}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._anno_install_thread and self._anno_install_thread.isRunning():
            QMessageBox.warning(self, '提示', '正在执行其他安装/卸载操作，请稍候。')
            return

        self._set_anno_buttons_enabled(False)
        self.anno_install_status.setText(f'⏳ 正在{action} {tool_name}...')
        self.anno_install_status.setStyleSheet('color: #1976D2; font-size: 11px;')

        self._anno_install_thread = AnnotationToolInstallThread(
            self.env_result['conda_path'],
            env_name,
            tool_name,
            is_install
        )
        self._anno_install_thread.log_signal.connect(self.append_log)
        self._anno_install_thread.finished_signal.connect(self._on_anno_tool_install_finished)
        self._anno_install_thread.start()

    def _on_anno_tool_install_finished(self, success, env_name, tool_name, error_msg):
        self._set_anno_buttons_enabled(True)

        action = '安装' if self._anno_install_thread and self._anno_install_thread.is_install else '操作'
        if success:
            self.anno_install_status.setText(f'✅ {tool_name} {action}成功')
            self.anno_install_status.setStyleSheet('color: green; font-size: 11px;')
            self._refresh_annotation_envs()
        else:
            self.anno_install_status.setText(f'❌ {tool_name} {action}失败')
            self.anno_install_status.setStyleSheet('color: red; font-size: 11px;')
            if error_msg:
                QMessageBox.critical(self, f'{action}失败', f'{tool_name} {action}失败:\n{error_msg}')

    def _set_anno_buttons_enabled(self, enabled):
        if not enabled:
            self.install_labelimg_btn.setEnabled(False)
            self.uninstall_labelimg_btn.setEnabled(False)
            self.install_labelme_btn.setEnabled(False)
            self.uninstall_labelme_btn.setEnabled(False)
            self.refresh_anno_btn.setEnabled(False)
        else:
            index = self.anno_env_combo.currentIndex()
            if index >= 0:
                env_name = self.anno_env_combo.itemData(index)
                if env_name and env_name in self._annotation_envs:
                    tools = self._annotation_envs[env_name]
                    has_labelimg = tools.get('labelImg', False)
                    has_labelme = tools.get('labelme', False)
                    self.install_labelimg_btn.setEnabled(not has_labelimg)
                    self.uninstall_labelimg_btn.setEnabled(has_labelimg)
                    self.install_labelme_btn.setEnabled(not has_labelme)
                    self.uninstall_labelme_btn.setEnabled(has_labelme)
            self.refresh_anno_btn.setEnabled(True)

    def _add_annotation_env(self):
        if not self.env_result or not self.env_result['conda_path']:
            QMessageBox.warning(self, '提示', '未检测到 Conda 环境。')
            return

        conda = CondaHandler(self.env_result['conda_path'])
        all_envs = conda.list_envs()
        installed = self._load_installed_envs()

        available_envs = []
        for env in all_envs:
            name = env.get('name', '')
            if not name or name == 'base':
                continue
            available_envs.append(env)

        if not available_envs:
            QMessageBox.information(self, '提示', '没有找到 Conda 环境。')
            return

        dialog = QDialog(self)
        dialog.setWindowTitle('添加环境到列表')
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        label = QLabel('选择要添加到标注工具列表的 Conda 环境：')
        layout.addWidget(label)

        combo = QComboBox()
        combo.setMinimumHeight(30)
        for env in available_envs:
            name = env.get('name', '')
            path = env.get('path', '')
            is_added = name in installed
            display = name
            if is_added:
                display += '  [已添加]'
            if path:
                display += f'  -  {path}'
            combo.addItem(display, name)
        layout.addWidget(combo)

        version_label = QLabel('版本名称（可选）:')
        layout.addWidget(version_label)
        version_input = QLineEdit()
        version_input.setMinimumHeight(28)
        version_input.setPlaceholderText('如：YOLOv5、YOLOv7、YOLOv8 等')
        layout.addWidget(version_input)

        hint = QLabel('💡 提示：选择之前安装的 YOLO 环境，添加后就可以使用标注工具功能')
        hint.setStyleSheet('color: #666; font-size: 11px;')
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText('添加')
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            env_name = combo.currentData()
            version_name = version_input.text().strip()
            if not version_name:
                if env_name in installed:
                    version_name = installed[env_name].get('version_name', '手动添加')
                else:
                    version_name = '手动添加'
            env_path = ''
            for env in available_envs:
                if env.get('name') == env_name:
                    env_path = env.get('path', '')
                    break
            self._save_installed_env(env_name, version_name, env_path)
            self._refresh_annotation_envs()
            QMessageBox.information(self, '添加成功', f'环境 {env_name} 已添加到列表。')

    def _remove_annotation_env(self):
        index = self.anno_env_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '提示', '请先选择要移除的环境。')
            return

        env_name = self.anno_env_combo.itemData(index)
        if not env_name:
            return

        reply = QMessageBox.question(
            self, '确认移除',
            f'确定要从列表中移除环境 {env_name} 吗？\n\n'
            '注意：这只是从列表中移除，不会删除实际的 Conda 环境。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._remove_installed_env(env_name)
        self._refresh_annotation_envs()
        QMessageBox.information(self, '移除成功', f'环境 {env_name} 已从列表中移除。')

    def _refresh_editor_envs(self):
        if not self.env_result or not self.env_result['conda_path']:
            self.editor_env_info.setText('❌ 未检测到 Conda')
            self.editor_env_info.setStyleSheet('color: red;')
            return

        installed = self._load_installed_envs()
        conda = CondaHandler(self.env_result['conda_path'])
        all_envs = conda.list_envs()
        env_path_map = {e.get('name', ''): e.get('path', '') for e in all_envs}

        self.editor_env_combo.clear()
        count = 0
        for env_name, env_info in installed.items():
            if env_name in env_path_map:
                version_name = env_info.get('version_name', '')
                display = env_name
                if version_name:
                    display += f'  ({version_name})'
                self.editor_env_combo.addItem(display, env_name)
                count += 1

        if count > 0:
            self.editor_env_info.setText(f'✅ 已找到 {count} 个已安装环境')
            self.editor_env_info.setStyleSheet('color: green;')
            self.deploy_editor_btn.setEnabled(True)
            self.open_editor_btn.setEnabled(True)
            self._on_editor_env_changed(0)
        else:
            self.editor_env_info.setText('⚠️  暂无已安装环境，请先在「一键部署」页面安装')
            self.editor_env_info.setStyleSheet('color: orange;')
            self.deploy_editor_btn.setEnabled(False)
            self.open_editor_btn.setEnabled(False)

        self._detect_editors()

    def _detect_editors(self):
        self._editors = detect_editors()
        vscode_found = 'vscode' in self._editors
        pycharm_found = 'pycharm' in self._editors

        self.editor_vscode_check.setEnabled(vscode_found)
        self.editor_pycharm_check.setEnabled(pycharm_found)

        if vscode_found:
            self.editor_vscode_check.setChecked(True)

        status_parts = []
        if vscode_found:
            status_parts.append('✅ VSCode 已安装')
        else:
            status_parts.append('❌ 未检测到 VSCode')

        if pycharm_found:
            status_parts.append('✅ PyCharm 已安装')
        else:
            status_parts.append('❌ 未检测到 PyCharm')

        self.editor_status_label.setText('  |  '.join(status_parts))

    def _on_editor_env_changed(self, index):
        if index < 0:
            return

        env_name = self.editor_env_combo.itemData(index)
        if not env_name or not self.env_result:
            return

        conda = CondaHandler(self.env_result['conda_path'])
        python_path = conda.get_python_path(env_name)

        installed = self._load_installed_envs()
        env_info = installed.get(env_name, {})
        workspace = env_info.get('workspace', '')
        if workspace and os.path.exists(workspace):
            if not self.editor_project_edit.text():
                self.editor_project_edit.setText(workspace)

    def _browse_editor_project(self):
        directory = QFileDialog.getExistingDirectory(self, '选择项目目录')
        if directory:
            self.editor_project_edit.setText(directory)

    def _deploy_to_editors(self):
        index = self.editor_env_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '提示', '请先选择 YOLO 环境。')
            return

        env_name = self.editor_env_combo.itemData(index)
        if not env_name:
            return

        project_path = self.editor_project_edit.text().strip()
        if not project_path or not os.path.exists(project_path):
            QMessageBox.warning(self, '提示', '请选择有效的项目目录。')
            return

        if not self.editor_vscode_check.isChecked() and not self.editor_pycharm_check.isChecked():
            QMessageBox.warning(self, '提示', '请至少选择一个编辑器。')
            return

        if not self.env_result:
            return

        conda = CondaHandler(self.env_result['conda_path'])
        python_path = conda.get_python_path(env_name)

        self.append_log('=' * 60)
        self.append_log('🔧 开始配置编辑器环境...')
        self.append_log(f'   环境: {env_name}')
        self.append_log(f'   项目: {project_path}')
        self.append_log(f'   Python: {python_path}')
        self.append_log('')

        if self.editor_vscode_check.isChecked():
            if 'vscode' in self._editors:
                self.append_log('📝 配置 VSCode...')
                for status in configure_vscode(project_path, python_path, env_name):
                    self.append_log(f'   {status.get("message", "")}')
                self.append_log('')
            else:
                self.append_log('⚠️  未检测到 VSCode，跳过')
                self.append_log('')

        if self.editor_pycharm_check.isChecked():
            if 'pycharm' in self._editors:
                self.append_log('🐍 配置 PyCharm...')
                for status in configure_pycharm(project_path, python_path, env_name):
                    msg = status.get('message', '')
                    msg_type = status.get('type', 'info')
                    prefix = ''
                    if msg_type == 'success':
                        prefix = '✅ '
                    elif msg_type == 'error':
                        prefix = '❌ '
                    elif msg_type == 'warning':
                        prefix = '⚠️  '
                    self.append_log(f'   {prefix}{msg}')
                self.append_log('')
            else:
                self.append_log('⚠️  未检测到 PyCharm，跳过')
                self.append_log('')

        self.append_log('✅ 编辑器环境配置完成！')
        self.append_log('=' * 60)
        QMessageBox.information(self, '完成', '编辑器环境配置完成！\n查看运行日志了解详情。')

    def _open_in_editors(self):
        index = self.editor_env_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '提示', '请先选择 YOLO 环境。')
            return

        project_path = self.editor_project_edit.text().strip()
        if not project_path or not os.path.exists(project_path):
            QMessageBox.warning(self, '提示', '请选择有效的项目目录。')
            return

        opened = False

        if self.editor_vscode_check.isChecked() and 'vscode' in self._editors:
            success, error = open_in_vscode(project_path, self._editors['vscode']['path'])
            if success:
                self.append_log(f'📝 已在 VSCode 中打开: {project_path}')
                opened = True
            else:
                self.append_log(f'❌ VSCode 打开失败: {error}')

        if self.editor_pycharm_check.isChecked() and 'pycharm' in self._editors:
            success, error = open_in_pycharm(project_path, self._editors['pycharm']['path'])
            if success:
                self.append_log(f'🐍 已在 PyCharm 中打开: {project_path}')
                opened = True
            else:
                self.append_log(f'❌ PyCharm 打开失败: {error}')

        if opened:
            QMessageBox.information(self, '完成', '已在选中的编辑器中打开项目！')
        else:
            QMessageBox.warning(self, '提示', '没有成功打开任何编辑器。\n请确保已选择编辑器且编辑器已安装。')

    def _launch_annotation_tool(self, tool_name):
        if not self.env_result or not self.env_result['conda_path']:
            QMessageBox.warning(self, '提示', '未检测到 Conda 环境。')
            return

        index = self.anno_env_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '提示', '请先选择 YOLO 环境。')
            return

        env_name = self.anno_env_combo.itemData(index)
        if not env_name:
            return

        conda = CondaHandler(self.env_result['conda_path'])
        self.append_log(f'正在启动 {tool_name} (环境: {env_name})...')

        import subprocess
        try:
            python_exe = conda.get_python_path(env_name)
            if not python_exe or not os.path.exists(python_exe):
                self.append_log(f'❌ 找不到环境 {env_name} 的 Python 解释器')
                QMessageBox.critical(self, '启动失败', f'找不到环境 {env_name} 的 Python 解释器。')
                return

            env_dir = os.path.dirname(python_exe)
            from modules.platform_utils import is_windows
            if is_windows():
                scripts_dir = os.path.join(env_dir, 'Scripts')
                labelimg_exe_name = 'labelImg.exe'
                labelme_exe_name = 'labelme.exe'
            else:
                scripts_dir = os.path.join(env_dir, 'bin')
                labelimg_exe_name = 'labelImg'
                labelme_exe_name = 'labelme'

            cmd = None
            cmd_desc = ''

            if tool_name == 'labelImg':
                labelimg_exe = os.path.join(scripts_dir, labelimg_exe_name)
                if os.path.exists(labelimg_exe):
                    cmd = [labelimg_exe]
                    cmd_desc = labelimg_exe
                else:
                    cmd = [python_exe, '-c',
                           'import sys; from labelImg.labelImg import main; sys.exit(main())']
                    cmd_desc = 'python -c "from labelImg.labelImg import main"'
            else:
                labelme_exe = os.path.join(scripts_dir, labelme_exe_name)
                if os.path.exists(labelme_exe):
                    cmd = [labelme_exe]
                    cmd_desc = labelme_exe
                else:
                    cmd = [python_exe, '-m', 'labelme']
                    cmd_desc = 'python -m labelme'

            self.append_log(f'执行命令: {cmd_desc}')

            # 准备环境变量
            env = os.environ.copy()

            if not is_windows():
                # Linux 下修复 OpenCV Qt 插件冲突问题
                # 用 Python 动态检测正确的 Qt 插件路径
                qt_plugin_path = None
                try:
                    detect_script = '''
import sys
import os

# 先尝试 PyQt5
try:
    import PyQt5
    from PyQt5.QtCore import QLibraryInfo
    path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    if path and os.path.exists(path):
        print(path)
        sys.exit(0)
except ImportError:
    pass

# 再尝试 PyQt6
try:
    import PyQt6
    from PyQt6.QtCore import QLibraryInfo
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    if path and os.path.exists(path):
        print(path)
        sys.exit(0)
except ImportError:
    pass

print('')
'''
                    r = subprocess.run(
                        [python_exe, '-c', detect_script],
                        capture_output=True, text=True, timeout=10,
                        env=env
                    )
                    detected = r.stdout.strip()
                    if detected and os.path.exists(detected):
                        qt_plugin_path = detected
                        self.append_log(f'ℹ️  检测到 Qt 插件路径: {qt_plugin_path}')
                except Exception as e:
                    self.append_log(f'⚠️  Qt 插件路径检测失败: {e}')

                # 设置环境变量，确保不使用 cv2 自带的 Qt 插件
                if qt_plugin_path:
                    env['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugin_path
                    env['QT_PLUGIN_PATH'] = qt_plugin_path
                    # 同时设置库路径，确保加载正确版本的 Qt 库
                    qt_lib_dir = os.path.dirname(qt_plugin_path)  # Qt 库目录通常是 plugins 的父目录
                    if os.path.exists(qt_lib_dir):
                        ld_path = env.get('LD_LIBRARY_PATH', '')
                        if qt_lib_dir not in ld_path:
                            env['LD_LIBRARY_PATH'] = qt_lib_dir + ':' + ld_path if ld_path else qt_lib_dir
                else:
                    # 如果没检测到，就删除这两个变量，让 Qt 自己找系统默认的
                    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
                    env.pop('QT_PLUGIN_PATH', None)
                    self.append_log('⚠️  未检测到 Qt 插件路径，使用系统默认')

                # 修复 Wayland 兼容性问题
                if 'WAYLAND_DISPLAY' in env:
                    env['QT_QPA_PLATFORM'] = 'xcb'
                    self.append_log('ℹ️  Wayland 环境，强制使用 XCB 模式')

                # 增加调试输出
                env['QT_DEBUG_PLUGINS'] = '0'  # 设为 1 可调试插件加载问题

            popen_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'env': env,
            }
            if is_windows():
                popen_kwargs['creationflags'] = 0

            process = subprocess.Popen(cmd, **popen_kwargs)

            import time
            time.sleep(2)

            if process.poll() is not None:
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore') or stdout.decode('utf-8', errors='ignore')
                self.append_log(f'❌ 启动失败，进程已退出，返回码: {process.returncode}')
                if error_msg:
                    self.append_log(f'错误信息: {error_msg[:500]}')

                # 检查是否是 Qt 插件冲突问题
                fix_suggestion = ''
                if 'cv2/qt/plugins' in error_msg and 'xcb' in error_msg:
                    fix_suggestion = (
                        '\n\n🔧 常见原因：OpenCV 自带的 Qt 插件与 PyQt 冲突\n'
                        '\n解决方案（在终端执行）：\n'
                        f'  conda activate {env_name}\n'
                        f'  pip uninstall opencv-python -y\n'
                        f'  pip install opencv-python-headless\n'
                        '\n安装 headless 版本后重新启动即可。'
                    )
                elif 'wayland' in error_msg.lower() or 'XDG_SESSION_TYPE' in error_msg:
                    fix_suggestion = (
                        '\n\n🔧 常见原因：Wayland 显示服务器兼容性问题\n'
                        '\n解决方案：设置环境变量后重新启动\n'
                        '  export QT_QPA_PLATFORM=xcb'
                    )

                QMessageBox.critical(
                    self, '启动失败',
                    f'{tool_name} 启动失败！\n\n返回码: {process.returncode}\n\n错误信息:\n{error_msg[:800]}{fix_suggestion}'
                )
                return

            self.append_log(f'✅ {tool_name} 已启动 (PID: {process.pid})')
            QMessageBox.information(
                self, '启动成功',
                f'{tool_name} 已在环境 {env_name} 中启动。\n\n'
                '如果窗口没有显示，请检查任务栏或稍等几秒。'
            )
        except Exception as e:
            self.append_log(f'❌ 启动 {tool_name} 失败: {e}')
            import traceback
            self.append_log(traceback.format_exc())
            QMessageBox.critical(self, '启动失败', f'启动 {tool_name} 失败:\n{e}')

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def auto_scan_env(self):
        self.scan_environment()

    def scan_environment(self):
        self.scan_btn.setEnabled(False)
        self.install_env_btn.setEnabled(False)
        self.append_log('正在扫描系统环境...')
        self.env_scan_thread = EnvScanThread()
        self.env_scan_thread.finished_signal.connect(self.on_env_scan_finished)
        self.env_scan_thread.start()

    def _browse_conda_path(self):
        from modules.platform_utils import is_windows, save_conda_install_path, normalize_path
        from PyQt6.QtWidgets import QFileDialog

        if is_windows():
            filters = '可执行文件 (*.exe);;所有文件 (*.*)'
        else:
            filters = '可执行文件 (*);;所有文件 (*.*)'

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择 Conda 可执行文件',
            '',
            filters
        )

        if not file_path:
            return

        file_path = normalize_path(file_path)

        try:
            import subprocess
            result = subprocess.run(
                f'"{file_path}" --version',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                timeout=30
            )

            if result.returncode == 0:
                save_conda_install_path(file_path)
                self.conda_label.setText(f'Conda: ✅ 已手动指定 ({os.path.dirname(file_path)})')
                self.conda_label.setStyleSheet('color: green;')
                self.append_log(f'[手动指定] Conda 路径验证通过: {file_path}')
                self.append_log(f'Conda 版本: {result.stdout.strip()}')
                self.env_result = {
                    'conda_path': file_path,
                    'conda_version': result.stdout.strip(),
                    'git_available': self.env_result.get('git_available', False) if hasattr(self, 'env_result') else False,
                    'has_gpu': self.env_result.get('has_gpu', False) if hasattr(self, 'env_result') else False,
                    'log': f'[手动指定] 已设置 Conda 路径: {file_path}'
                }
                self._load_versions()
                self._refresh_annotation_envs()
                self._refresh_editor_envs()
            else:
                QMessageBox.warning(self, '验证失败', f'无法验证此路径是否为有效的 Conda 可执行文件\n错误信息: {result.stderr}')
        except Exception as e:
            QMessageBox.warning(self, '操作失败', f'指定 Conda 路径时发生错误: {str(e)}')

    def _global_scan_conda(self):
        from PyQt6.QtCore import QThread, pyqtSignal

        class GlobalScanThread(QThread):
            finished_signal = pyqtSignal(object)

            def run(self):
                from modules.env_scan import global_scan_conda
                conda_path, log = global_scan_conda()
                self.finished_signal.emit({'conda_path': conda_path, 'log': log})

        self.global_scan_btn.setEnabled(False)
        self.append_log('🔍 开始全局扫描 Conda，请耐心等待...')

        self.global_scan_thread = GlobalScanThread()
        self.global_scan_thread.finished_signal.connect(self.on_global_scan_finished)
        self.global_scan_thread.start()

    def on_global_scan_finished(self, result):
        self.global_scan_btn.setEnabled(True)
        self.append_log(result['log'])

        if result['conda_path']:
            from modules.platform_utils import save_conda_install_path, normalize_path
            conda_path = normalize_path(result['conda_path'])
            save_conda_install_path(conda_path)
            self.conda_label.setText(f'Conda: ✅ 全局扫描找到 ({os.path.dirname(conda_path)})')
            self.conda_label.setStyleSheet('color: green;')
            self.env_result = {
                'conda_path': conda_path,
                'git_available': self.env_result.get('git_available', False) if hasattr(self, 'env_result') else False,
                'has_gpu': self.env_result.get('has_gpu', False) if hasattr(self, 'env_result') else False,
                'log': result['log']
            }
            self._load_versions()
            self._refresh_annotation_envs()
            self._refresh_editor_envs()
        else:
            self.conda_label.setText('Conda: ❌ 全局扫描未找到，请尝试手动指定或自动安装')
            self.conda_label.setStyleSheet('color: red;')

    def on_env_scan_finished(self, result):
        self.env_result = result
        self.append_log(result['log'])

        if result['conda_path']:
            self.conda_label.setText(f'Conda: ✅ 已找到 ({os.path.dirname(result["conda_path"])})')
            self.conda_label.setStyleSheet('color: green;')
        else:
            self.conda_label.setText('Conda: ❌ 未找到，可点击右侧「自动安装环境」')
            self.conda_label.setStyleSheet('color: red;')

        if result['git_available']:
            self.git_label.setText('Git: ✅ 已安装')
            self.git_label.setStyleSheet('color: green;')
        else:
            self.git_label.setText('Git: ❌ 未安装，可点击右侧「自动安装环境」')
            self.git_label.setStyleSheet('color: red;')

        if result['has_gpu']:
            self.gpu_label.setText('显卡: ✅ 检测到 NVIDIA GPU')
            self.gpu_label.setStyleSheet('color: green;')
            self.gpu_checkbox.setChecked(True)
        else:
            self.gpu_label.setText('显卡: ⚠️ 未检测到 NVIDIA GPU，将使用 CPU')
            self.gpu_label.setStyleSheet('color: orange;')
            self.gpu_checkbox.setChecked(False)

        self._load_versions()
        self.scan_btn.setEnabled(True)
        self.install_env_btn.setEnabled(True)
        self._refresh_annotation_envs()
        self._refresh_editor_envs()

    def _load_versions(self):
        self.version_combo.clear()
        self.python_combo.clear()
        self.pytorch_combo.clear()
        self.annotation_combo.clear()
        try:
            config_path = get_resource_path('repos.yaml')
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            versions = config.get('yolo_versions', [])
            for v in versions:
                self.version_combo.addItem(v['name'], v)

            python_versions = config.get('python_versions', ['3.10', '3.9', '3.11', '3.8'])
            for v in python_versions:
                self.python_combo.addItem(v, v)

            pytorch_versions = config.get('pytorch_versions', ['latest', '2.5.1', '2.4.1'])
            for v in pytorch_versions:
                self.pytorch_combo.addItem(v, v)

            annotation_tools = config.get('annotation_tools', [])
            for tool in annotation_tools:
                self.annotation_combo.addItem(tool['name'], tool.get('pkg_name', ''))

        except Exception as e:
            self.append_log(f'[错误] 加载版本配置失败: {e}')

    def _on_version_changed(self, index):
        if index < 0:
            return
        version_info = self.version_combo.itemData(index)
        if not version_info:
            return

        recommended_py = version_info.get('python_version')
        recommended_torch = version_info.get('recommended_pytorch')

        if recommended_py:
            py_index = self.python_combo.findData(recommended_py)
            if py_index >= 0:
                self.python_combo.setCurrentIndex(py_index)

        if recommended_torch:
            torch_index = self.pytorch_combo.findData(recommended_torch)
            if torch_index >= 0:
                self.pytorch_combo.setCurrentIndex(torch_index)

    def _update_workspace_preview(self):
        drive = self.workspace_drive_combo.currentData()
        folder = self.workspace_folder_edit.text().strip()
        if drive and folder:
            from modules.platform_utils import normalize_path
            path = normalize_path(os.path.join(drive, folder))
            self.workspace_path_preview.setText(f'完整路径: {path}')

    def _browse_workspace(self):
        drive = self.workspace_drive_combo.currentData()
        from modules.platform_utils import is_windows
        if is_windows():
            start_dir = drive + '\\' if drive else ''
        else:
            start_dir = drive + '/' if drive else ''
        directory = QFileDialog.getExistingDirectory(self, '选择工作目录', start_dir)
        if directory:
            from modules.platform_utils import is_windows
            if is_windows():
                drive_letter = os.path.splitdrive(directory)[0]
                if drive_letter:
                    idx = self.workspace_drive_combo.findData(drive_letter[:-1] if drive_letter.endswith(':') else drive_letter)
                    if idx >= 0:
                        self.workspace_drive_combo.setCurrentIndex(idx)
            folder = os.path.basename(directory)
            if folder:
                self.workspace_folder_edit.setText(folder)

    def _get_workspace_dir(self):
        drive = self.workspace_drive_combo.currentData()
        folder = self.workspace_folder_edit.text().strip()
        if drive and folder:
            from modules.platform_utils import normalize_path
            return normalize_path(os.path.join(drive, folder))
        return None

    def append_log(self, text):
        self._log_lines.append(text)
        self.log_text.append(text)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def start_env_install(self):
        dialog = EnvInstallDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        config = dialog.get_config()
        conda_type = config['conda_type']
        conda_version = config['conda_version']
        git_version = config['git_version']
        conda_install_path = config['conda_install_path']

        conda_name = 'Anaconda3' if conda_type == 'anaconda' else 'Miniconda3'
        time_estimate = '15-30 分钟' if conda_type == 'anaconda' else '5-15 分钟'

        path_info = f'安装路径: {conda_install_path}\n' if conda_install_path else ''

        reply = QMessageBox.question(
            self, '确认自动安装',
            f'即将自动下载并安装以下环境：\n\n'
            f'  • {conda_name} {conda_version}（Python 环境管理器）\n'
            f'  • Git {git_version}（版本控制工具，克隆源码用）\n\n'
            f'{path_info}'
            f'安装过程可能需要 {time_estimate}，取决于网络速度。\n'
            f'是否继续？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._set_controls_enabled(False)
        self.progress_bar.show()
        self.append_log('=' * 60)
        self.append_log('开始自动安装运行环境')
        self.append_log('=' * 60)

        self.env_install_thread = EnvInstallThread(
            conda_type=conda_type,
            conda_version=conda_version,
            git_version=git_version,
            conda_install_path=conda_install_path
        )
        self.env_install_thread.log_signal.connect(self.append_log)
        self.env_install_thread.finished_signal.connect(self._on_env_install_finished)
        self.env_install_thread.start()

    def _on_env_install_finished(self, results):
        self.progress_bar.hide()
        self._set_controls_enabled(True)

        self.append_log('=' * 60)
        conda_ok = results.get('conda', False)
        git_ok = results.get('git', False)
        conda_type = results.get('conda_type', 'miniconda')
        conda_name = 'Anaconda3' if conda_type == 'anaconda' else 'Miniconda3'

        if conda_ok and git_ok:
            self.append_log('✅ 所有环境安装成功！')
            QMessageBox.information(self, '安装完成', f'{conda_name} 和 Git 安装成功！\n\n点击「重新扫描环境」检测新安装的环境。\n\n注意：Git 可能需要重启电脑后才能完全生效。')
        elif conda_ok:
            self.append_log(f'⚠️ {conda_name} 安装成功，Git 安装失败')
            QMessageBox.warning(self, '部分完成', f'{conda_name} 安装成功，但 Git 安装失败。\n请手动安装 Git 后重试。')
        elif git_ok:
            self.append_log(f'⚠️ Git 安装成功，{conda_name} 安装失败')
            QMessageBox.warning(self, '部分完成', f'Git 安装成功，但 {conda_name} 安装失败。\n请手动安装 {conda_name} 后重试。')
        else:
            self.append_log('❌ 环境安装失败')
            QMessageBox.critical(self, '安装失败', f'{conda_name} 和 Git 均安装失败，请查看日志。')
        self.append_log('=' * 60)

    def start_install(self):
        if not self.env_result or not self.env_result['conda_path']:
            reply = QMessageBox.question(
                self, '提示',
                '未检测到 Conda。\n\n是否现在自动安装 Miniconda3 和 Git？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_env_install()
            return

        if not self.env_result['git_available']:
            reply = QMessageBox.question(
                self, '确认',
                '未检测到 Git，源码模式的 YOLO 版本将无法克隆。\n是否继续（仅 pip 模式可用）？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        current_index = self.version_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, '提示', '请选择要部署的 YOLO 版本。')
            return

        version_info = self.version_combo.itemData(current_index)
        use_gpu = self.gpu_checkbox.isChecked()
        run_test = self.test_checkbox.isChecked()
        python_version = self.python_combo.currentData()
        pytorch_version = self.pytorch_combo.currentData()
        workspace_dir = self._get_workspace_dir()
        annotation_tool = self.annotation_combo.currentData()

        if use_gpu and not self.env_result['has_gpu']:
            reply = QMessageBox.question(
                self, '确认',
                '未检测到 NVIDIA 显卡，GPU 版本可能无法正常工作。\n是否继续使用 GPU 版本安装？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        workspace_info = f'工作目录: {workspace_dir}\n' if workspace_dir else ''
        annotation_name = self.annotation_combo.currentText()
        annotation_info = f'标注工具: {annotation_name}\n' if annotation_tool else ''

        reply = QMessageBox.question(
            self, '确认安装',
            f'即将部署: {version_info["name"]}\n'
            f'Python 版本: {python_version}\n'
            f'PyTorch 版本: {pytorch_version}\n'
            f'模式: {"GPU" if use_gpu else "CPU"}\n'
            f'环境名: {version_info["env_name"]}\n'
            f'{workspace_info}'
            f'{annotation_info}\n'
            f'确认开始安装？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._set_controls_enabled(False)
        self.progress_bar.show()
        self._current_workspace = workspace_dir
        self._current_env_name = version_info.get('env_name', '')
        self._log_lines = []
        self.append_log('=' * 60)
        self.append_log(f'开始部署: {version_info["name"]}')
        self.append_log(f'Python: {python_version} | PyTorch: {pytorch_version} | {"GPU" if use_gpu else "CPU"}')
        if workspace_dir:
            self.append_log(f'工作目录: {workspace_dir}')
        self.append_log('=' * 60)

        self.install_thread = InstallThread(
            self.env_result['conda_path'],
            version_info,
            use_gpu,
            run_test,
            python_version=python_version,
            pytorch_version=pytorch_version,
            workspace_dir=workspace_dir,
            annotation_tool=annotation_tool
        )
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.step_signal.connect(self._on_step)
        self.install_thread.finished_signal.connect(self._on_install_finished)
        self.install_thread.start()

    def _on_step(self, step_name):
        self.setWindowTitle(f'YOLO 全版本一键部署工具 - [{step_name}]')

    def _on_install_finished(self, success, message):
        self.progress_bar.hide()
        self._set_controls_enabled(True)
        self.setWindowTitle('YOLO 全版本一键部署工具')

        self.append_log('=' * 60)
        if success:
            self.append_log(f'✅ {message}')
        else:
            self.append_log(f'❌ {message}')
        self.append_log('=' * 60)

        log_file = self._save_log_file(success)
        if log_file:
            self.append_log(f'📄 日志已保存至: {log_file}')

        if success:
            final_msg = message
            if log_file:
                final_msg += f'\n\n日志已保存至:\n{log_file}'

            if self.install_thread and self.install_thread.version_info:
                env_name = self.install_thread.version_info.get('env_name', '')
                version_name = self.install_thread.version_info.get('name', '')
                workspace = self._current_workspace or ''
                env_path = ''
                if self.env_result and self.env_result.get('conda_path'):
                    conda = CondaHandler(self.env_result['conda_path'])
                    all_envs = conda.list_envs()
                    for e in all_envs:
                        if e.get('name') == env_name:
                            env_path = e.get('path', '')
                            break
                self._save_installed_env(env_name, version_name, env_path, workspace)
                self._refresh_annotation_envs()
                self._refresh_editor_envs()

            QMessageBox.information(self, '完成', final_msg)
        else:
            final_msg = message
            if log_file:
                final_msg += f'\n\n详细日志已保存至:\n{log_file}'
            QMessageBox.critical(self, '失败', final_msg)

    def _get_installed_envs_file(self):
        return os.path.join(get_runtime_dir(), 'installed_envs.json')

    def _load_installed_envs(self):
        file_path = self._get_installed_envs_file()
        if not os.path.exists(file_path):
            return {}
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_installed_env(self, env_name, version_name, env_path='', workspace=''):
        envs = self._load_installed_envs()
        import time
        envs[env_name] = {
            'name': env_name,
            'version_name': version_name,
            'path': env_path,
            'workspace': workspace,
            'install_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        file_path = self._get_installed_envs_file()
        try:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(envs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _remove_installed_env(self, env_name):
        envs = self._load_installed_envs()
        if env_name in envs:
            del envs[env_name]
            file_path = self._get_installed_envs_file()
            try:
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(envs, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _save_log_file(self, success):
        if not self._current_workspace or not self._log_lines:
            return None

        try:
            import datetime
            os.makedirs(self._current_workspace, exist_ok=True)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            status_str = 'success' if success else 'failed'
            env_name = self._current_env_name or 'yolo'
            log_filename = f'{env_name}_{status_str}_{timestamp}.log'
            log_path = os.path.join(self._current_workspace, log_filename)

            header = [
                '=' * 60,
                f'YOLO 部署日志',
                f'时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                f'状态: {"成功" if success else "失败"}',
                f'环境: {self._current_env_name}',
                f'工作目录: {self._current_workspace}',
                '=' * 60,
                ''
            ]

            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(header))
                f.write('\n')
                f.write('\n'.join(self._log_lines))
                f.write('\n')

            return log_path
        except Exception as e:
            self.append_log(f'保存日志失败: {e}')
            return None

    def _set_controls_enabled(self, enabled):
        self.scan_btn.setEnabled(enabled)
        self.install_env_btn.setEnabled(enabled)
        self.browse_conda_btn.setEnabled(enabled)
        self.global_scan_btn.setEnabled(enabled)
        self.version_combo.setEnabled(enabled)
        self.python_combo.setEnabled(enabled)
        self.pytorch_combo.setEnabled(enabled)
        self.workspace_drive_combo.setEnabled(enabled)
        self.workspace_folder_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.gpu_checkbox.setEnabled(enabled)
        self.test_checkbox.setEnabled(enabled)
        self.install_btn.setEnabled(enabled)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
