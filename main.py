import sys
import os
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QTextEdit, QGroupBox,
    QMessageBox, QProgressBar, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QFileDialog, QTabWidget, QScrollArea, QFrame,
    QSpinBox, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QFont, QTextCursor, QIcon, QDesktopServices, QColor


def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# 各 YOLO 系列的官方可用模型（与一键部署的版本一一对应，训练只允许选择对应系列）
YOLO_FAMILY_MODELS = {
    'v5':  ['yolov5n', 'yolov5s', 'yolov5m', 'yolov5l', 'yolov5x'],
    'v7':  ['yolov7-tiny', 'yolov7', 'yolov7x', 'yolov7-w6', 'yolov7-d6', 'yolov7-e6', 'yolov7-e6e'],
    'v8':  ['yolov8n', 'yolov8s', 'yolov8m', 'yolov8l', 'yolov8x'],
    # YOLOv9 官方权重真实文件名（WongKinYiu/yolov9 v0.1）：
    # - 带 -converted 的是纯模型权重，标准训练/推理使用（T/S 只有 converted 版）
    # - 不带后缀的 yolov9-s/m/c/e 是含优化器状态的完整 checkpoint，可恢复训练
    # - gelan-* 是 GELAN 架构权重
    'v9':  [
        'yolov9-t-converted',
        'yolov9-s-converted', 'yolov9-s',
        'yolov9-m-converted', 'yolov9-m',
        'yolov9-c-converted', 'yolov9-c',
        'yolov9-e-converted', 'yolov9-e',
        'gelan-s', 'gelan-m', 'gelan-c', 'gelan-e',
    ],
    'v10': ['yolov10n', 'yolov10s', 'yolov10m', 'yolov10b', 'yolov10l', 'yolov10x'],
    'v11': ['yolo11n', 'yolo11s', 'yolo11m', 'yolo11l', 'yolo11x'],
}


def detect_yolo_family(version_name='', env_name=''):
    """根据部署版本名/环境名识别 YOLO 系列，识别不出返回 None"""
    text = f'{version_name} {env_name}'.lower()
    # 顺序敏感：先匹配 v11/v10/v9/v8/v7/v5，避免子串误伤
    for key in ('v11', 'yolo11', 'v10', 'v9', 'v8', 'v7', 'v5'):
        if key in text:
            return key.replace('yolo11', 'v11')
    return None


from modules.env_scan import scan_environment
from modules.conda_handler import CondaHandler
from modules.yolo_installer import YoloInstaller
from modules.env_installer import install_all, MINICONDA_VERSIONS, ANACONDA_VERSIONS, GIT_VERSIONS
from modules.editor_deploy import detect_editors, configure_vscode, open_in_vscode, configure_pycharm, open_in_pycharm
from modules.platform_utils import get_runtime_dir


# ==================== 现代化全局样式 ====================
_APP_STYLE = """
/* 全局基础 */
QMainWindow, QDialog {
    background-color: #f5f7fa;
}
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #333333;
}

/* 分组框 */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e0e4ea;
    border-radius: 10px;
    margin-top: 8px;
    padding-top: 18px;
    font-weight: bold;
    font-size: 13px;
    color: #2c3e50;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px 0 6px;
    color: #1a73e8;
}

/* 标签页 */
QTabWidget::pane {
    border: 1px solid #e0e4ea;
    border-radius: 10px;
    background-color: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background-color: #eef1f6;
    color: #5f6368;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 20px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1a73e8;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #e3e8f0;
}

/* 按钮 - 基础 */
QPushButton {
    background-color: #eef1f6;
    color: #333333;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-height: 32px;
    /* 图标与文本间距 */
    text-align: center;
}
QPushButton:hover {
    background-color: #dfe5ee;
}
QPushButton:pressed {
    background-color: #cfd8e3;
}
QPushButton:disabled {
    background-color: #e8eaed;
    color: #9aa0a6;
}

/* 按钮 - 主要操作（蓝色） */
QPushButton[primary="true"] {
    background-color: #1a73e8;
    color: white;
    font-weight: bold;
}
QPushButton[primary="true"]:hover {
    background-color: #1557b0;
}
QPushButton[primary="true"]:pressed {
    background-color: #0f4a96;
}
QPushButton[primary="true"]:disabled {
    background-color: #a8c7fa;
    color: #e8f0fe;
}

/* 按钮 - 成功操作（绿色） */
QPushButton[success="true"] {
    background-color: #34a853;
    color: white;
    font-weight: bold;
}
QPushButton[success="true"]:hover {
    background-color: #2d9249;
}
QPushButton[success="true"]:pressed {
    background-color: #247a3d;
}
QPushButton[success="true"]:disabled {
    background-color: #b7dfc2;
    color: #e6f4ea;
}

/* 按钮 - 危险操作（红色） */
QPushButton[danger="true"] {
    background-color: #ea4335;
    color: white;
    font-weight: bold;
}
QPushButton[danger="true"]:hover {
    background-color: #d33426;
}
QPushButton[danger="true"]:pressed {
    background-color: #b52d20;
}
QPushButton[danger="true"]:disabled {
    background-color: #f5b7b1;
    color: #fce8e6;
}

/* 按钮 - 警告操作（橙色） */
QPushButton[warning="true"] {
    background-color: #f9ab00;
    color: white;
    font-weight: bold;
}
QPushButton[warning="true"]:hover {
    background-color: #e29900;
}
QPushButton[warning="true"]:pressed {
    background-color: #c98a00;
}
QPushButton[warning="true"]:disabled {
    background-color: #fde7b3;
    color: #fef7e0;
}

/* 输入框 */
QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 32px;
    selection-background-color: #1a73e8;
    selection-color: white;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid #1a73e8;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #f1f3f4;
    color: #9aa0a6;
}

/* 下拉框箭头 */
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #5f6368;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 6px;
    selection-background-color: #e8f0fe;
    selection-color: #1a73e8;
    outline: none;
}

/* 复选框 */
QCheckBox {
    spacing: 8px;
    color: #333333;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #dadce0;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
    image: none;
}
QCheckBox::indicator:hover {
    border-color: #1a73e8;
}

/* 单选框 */
QRadioButton {
    spacing: 8px;
    color: #333333;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #dadce0;
    border-radius: 9px;
    background-color: #ffffff;
}
QRadioButton::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
}

/* 进度条 */
QProgressBar {
    background-color: #e8eaed;
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #1a73e8;
    border-radius: 6px;
}

/* 滚动区域 */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar:vertical {
    background-color: #f1f3f4;
    width: 10px;
    border-radius: 5px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #c4c7c5;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a8acaa;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #f1f3f4;
    height: 10px;
    border-radius: 5px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #c4c7c5;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #a8acaa;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* 文本编辑区域（日志） */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e0e4ea;
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #1a73e8;
    selection-color: white;
}

/* 表格 */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e0e4ea;
    border-radius: 8px;
    gridline-color: #e8eaed;
    selection-background-color: #e8f0fe;
    selection-color: #1a73e8;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #f8f9fa;
    color: #5f6368;
    border: none;
    border-bottom: 1px solid #e0e4ea;
    padding: 8px;
    font-weight: bold;
}

/* 提示标签 */
QLabel[hint="true"] {
    color: #5f6368;
    font-size: 12px;
}
QLabel[success="true"] {
    color: #34a853;
}
QLabel[error="true"] {
    color: #ea4335;
}
QLabel[warning="true"] {
    color: #f9ab00;
}
QLabel[info="true"] {
    color: #1a73e8;
}
"""


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
    download_progress_signal = pyqtSignal(int, int, str)  # current, total, filename

    def __init__(self, conda_path, version_info, use_gpu, run_test=True,
                 python_version=None, pytorch_version=None, workspace_dir=None,
                 annotation_tool=None, resume=False):
        super().__init__()
        self.conda_path = conda_path
        self.version_info = version_info
        self.use_gpu = use_gpu
        self.run_test = run_test
        self.python_version = python_version
        self.pytorch_version = pytorch_version
        self.workspace_dir = workspace_dir
        self.annotation_tool = annotation_tool
        self.resume = resume

    def _on_download_progress(self, current, total, filename):
        """转发下载进度信号"""
        self.download_progress_signal.emit(current, total, filename)

    def run(self):
        from modules.task_state import TaskStateManager
        state_mgr = TaskStateManager()
        try:
            conda = CondaHandler(self.conda_path)
            config_path = get_resource_path('repos.yaml')
            if self.workspace_dir:
                installer = YoloInstaller(conda, workspace_dir=self.workspace_dir, config_path=config_path)
            else:
                installer = YoloInstaller(conda, config_path=config_path)

            # 断点状态：全新部署则建立新状态（覆盖旧档）；恢复部署则读取旧档
            if self.resume and state_mgr.has_pending():
                self.log_signal.emit('🔄 检测到未完成的部署任务，正在从断点继续...')
            else:
                state_mgr.begin_task(
                    version_info=self.version_info,
                    python_version=self.python_version,
                    pytorch_version=self.pytorch_version,
                    use_gpu=self.use_gpu,
                    run_test=self.run_test,
                    annotation_tool=self.annotation_tool,
                    workspace_dir=installer.workspace_dir,
                )

            for status in installer.install(
                self.version_info,
                self.use_gpu,
                python_version=self.python_version,
                pytorch_version=self.pytorch_version,
                state_mgr=state_mgr,
                resume=self.resume,
            ):
                if status['type'] == 'step':
                    self.step_signal.emit(status['step'])
                    self.log_signal.emit(status['log'])
                elif status['type'] == 'log':
                    self.log_signal.emit(status['log'])
                elif status['type'] == 'error':
                    self.log_signal.emit(status['log'])
                    self.log_signal.emit('💡 部署进度已保存，下次打开程序可选择继续部署')
                    self.finished_signal.emit(False, status['log'])
                    return
                elif status['type'] == 'success':
                    self.log_signal.emit(status['log'])
                elif status['type'] == 'download_progress':
                    self.download_progress_signal.emit(
                        status['current'], status['total'], status['filename'])
                    state_mgr.update_download(
                        status['filename'], status.get('path', ''),
                        status['current'], status['total'])

            if self.annotation_tool:
                completed = set((state_mgr.state or {}).get('completed_steps') or [])
                if '安装标注工具' in completed:
                    self.log_signal.emit('[恢复] 步骤"安装标注工具"已完成，跳过')
                else:
                    state_mgr.set_current_step('安装标注工具')
                    self._install_annotation_tools(conda, installer)
                    state_mgr.mark_step_done('安装标注工具')

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

            # 部署全部成功：清除断点状态文件
            state_mgr.clear()
            self.finished_signal.emit(True, '部署完成！')

        except Exception as e:
            self.log_signal.emit(f'[严重错误] {str(e)}')
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.log_signal.emit('💡 部署进度已保存，下次打开程序可选择继续部署')
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
            # 安装后兼容性加固；失败只警告，不阻断整体部署
            ok, fix_msg = apply_annotation_fixes(
                conda, env_name, pkg, self.log_signal.emit)
            if not ok:
                self.log_signal.emit(f'⚠️ {pkg} 兼容性加固未通过: {fix_msg}')
                self.log_signal.emit('   可稍后在「标注工具」页卸载重装或手动排查')

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


class TrainThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, conda_path, env_name, dataset_path, model, workers, batch,
                 epochs, imgsz, family, project_dir, run_name='train',
                 repo_cwd='', model_path=''):
        super().__init__()
        self.conda_path = conda_path
        self.env_name = env_name
        self.dataset_path = dataset_path
        self.model = model
        self.workers = workers
        self.batch = batch
        self.epochs = epochs
        self.imgsz = imgsz
        self.family = family            # v5/v7/v8/v9/v10/v11
        self.project_dir = project_dir  # <workspace>/runs/detect
        self.run_name = run_name
        self.repo_cwd = repo_cwd        # 源码仓库目录（v5/v7/v9 的工作目录）
        self.model_path = model_path    # 权重实际绝对路径（全局扫描可能来自任意目录）

    @property
    def _weight_spec(self):
        """训练命令中使用的权重：有绝对路径用路径，否则按模型名（依赖工作目录）"""
        if self.model_path:
            return self.model_path.replace('\\', '/')
        return f'{self.model}.pt'

    def _v9_cfg_spec(self):
        """为 YOLOv9 的 converted / GELAN 权重定位模型结构 yaml。

        converted 纯权重和 GELAN 权重不包含模型结构，训练时必须提供 --cfg；
        yolov9-s/m/c/e 完整 checkpoint 自带结构，无需 cfg。
        返回 cfg 绝对路径（正斜杠），找不到或不需要时返回 ''。
        """
        name = self.model  # 不含扩展名的权重名
        size = ''
        cfg_prefix = ''

        if name.startswith('gelan-'):
            cfg_prefix = 'gelan'
            size = name[len('gelan-'):]
        elif name.startswith('yolov9-') and name.endswith('-converted'):
            cfg_prefix = 'yolov9'
            size = name[len('yolov9-'):-len('-converted')]
        else:
            return ''  # 完整 checkpoint，不需要 cfg

        if not size:
            return ''

        cfg_rel = os.path.join('models', 'detect', f'{cfg_prefix}-{size}.yaml')
        # 优先在克隆的仓库目录中查找
        candidates = []
        if self.repo_cwd:
            candidates.append(os.path.join(self.repo_cwd, cfg_rel))
        # 兜底：模型所在目录
        if self.model_path:
            candidates.append(os.path.join(
                os.path.dirname(self.model_path), cfg_rel))
        for p in candidates:
            if os.path.exists(p):
                return p.replace('\\', '/')
        return ''

    # ---------- 命令构建 ----------
    def _build_command(self, data_yaml):
        """根据系列生成训练命令。

        - v5：仓库无 yolo 入口，直接调用 train.run()（参数名跨版本稳定）
        - v7/v9：使用仓库自带 train.py 的 argparse 接口
        - v8/v10/v11：使用 yolo CLI
        """
        project = self.project_dir.replace('\\', '/')
        weights = self._weight_spec

        if self.family == 'v5':
            code = (
                'from train import run; '
                f"run(weights=r'{weights}', data=r'{data_yaml}', "
                f'imgsz={self.imgsz}, batch={self.batch}, epochs={self.epochs}, '
                f"project=r'{self.project_dir}', name='{self.run_name}', "
                f'workers={self.workers})'
            )
            return f'python -c "{code}"'

        if self.family in ('v7', 'v9'):
            cfg_part = ''
            if self.family == 'v9':
                cfg_file = self._v9_cfg_spec()
                if cfg_file:
                    cfg_part = f' --cfg "{cfg_file}"'
            return (
                'python train.py '
                f"--weights \"{weights}\" --data \"{data_yaml}\"{cfg_part} "
                f'--epochs {self.epochs} --batch-size {self.batch} '
                f'--img-size {self.imgsz} --workers {self.workers} '
                f"--project \"{self.project_dir}\" --name '{self.run_name}'"
            )

        # yolo CLI 系列
        return (
            'yolo train '
            f'model="{weights}" data="{data_yaml}" '
            f'imgsz={self.imgsz} epochs={self.epochs} batch={self.batch} '
            f"workers={self.workers} project=\"{project}\" name='{self.run_name}'"
        )

    # ---------- 字体预置 ----------
    @staticmethod
    def _locate_system_fonts():
        """从 Windows Fonts 目录寻找可用字体源，返回 (Arial源, Unicode源)"""
        fonts_dir = os.environ.get('WINDIR', r'C:\Windows')
        fonts_dir = os.path.join(fonts_dir, 'Fonts')

        arial_src = ''
        for name in ('arial.ttf',):
            p = os.path.join(fonts_dir, name)
            if os.path.exists(p):
                arial_src = p
                break

        unicode_src = ''
        for name in ('ARIALUNI.TTF', 'simsun.ttc', 'msyh.ttc', 'simhei.ttf'):
            p = os.path.join(fonts_dir, name)
            if os.path.exists(p):
                unicode_src = p
                break
        return arial_src, unicode_src

    def _prepare_font_files(self, extra_dirs=None):
        """训练前把系统 Arial 字体复制到各 YOLO 配置目录。

        解决 ultralytics.com 的 Arial.ttf 返回 308 重定向（Python 3.8 urllib
        不自动跟随 308）或 GitHub release CDN 国内不可达导致训练直接中断。
        check_font 检测到文件已存在即跳过下载。
        """
        import shutil
        arial_src, unicode_src = self._locate_system_fonts()
        if not arial_src:
            return

        target_dirs = []
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            target_dirs.append(os.path.join(appdata, 'Ultralytics'))
        target_dirs.append(os.path.expanduser(os.path.join('~', '.config', 'Ultralytics')))
        if extra_dirs:
            target_dirs.extend(extra_dirs)

        for d in target_dirs:
            try:
                os.makedirs(d, exist_ok=True)
                arial_dst = os.path.join(d, 'Arial.ttf')
                if not os.path.exists(arial_dst):
                    shutil.copy2(arial_src, arial_dst)
                # 非 ASCII 类别名（如中文）时 v5 会要 Arial.Unicode.ttf
                if unicode_src:
                    uni_dst = os.path.join(d, 'Arial.Unicode.ttf')
                    if not os.path.exists(uni_dst):
                        shutil.copy2(unicode_src, uni_dst)
            except Exception:
                continue

    # ---------- 输出解析 ----------
    ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

    def _clean(self, text):
        return self.ANSI_RE.sub('', text).strip()

    def _format_tqdm(self, line):
        """把 tqdm 进度行压缩成一行紧凑进度，无法解析返回 None"""
        # 形如: 3/50  G  ...  48%|████▊   | 12/25 [00:15<00:16, 2.10it/s]
        m = re.search(
            r'(?:(\d+)/(\d+)\s+.*?)?'             # 可选 epoch x/y
            r'(\d+)%[^|]*\|[^|]*\|\s*(\d+)/(\d+)' # 百分比 + n/total
            r'\s*\[([^\]]+)\]',                   # 时间与速率
            line)
        if not m:
            return None
        ep_cur, ep_total, pct, n, total, timing = m.groups()
        prefix = f'Epoch {ep_cur}/{ep_total} | ' if ep_cur else ''
        return f'{prefix}{pct}% ({n}/{total}) [{timing}]'

    def _is_error_line(self, line):
        return any(k in line for k in (
            'Traceback (most recent call last)', 'RuntimeError:', 'OSError:',
            'ModuleNotFoundError:', 'ImportError:', 'CUDA out of memory',
            'FileNotFoundError:', 'ValueError:', 'AssertionError:',
            'Killed', 'ERROR:'))

    def run(self):
        import subprocess
        import time
        try:
            data_yaml = os.path.join(self.dataset_path, 'data.yaml')
            if not os.path.exists(data_yaml):
                for root, dirs, files in os.walk(self.dataset_path):
                    if 'data.yaml' in files:
                        data_yaml = os.path.join(root, 'data.yaml')
                        break
            if not os.path.exists(data_yaml):
                self.log_signal.emit(f'[错误] 未找到 data.yaml，请在 {self.dataset_path} 中放置 data.yaml')
                self.finished_signal.emit(False, '未找到 data.yaml')
                return

            os.makedirs(self.project_dir, exist_ok=True)
            inner_cmd = self._build_command(data_yaml)
            # --no-capture-output：输出实时透传，否则 conda run 会缓冲到训练结束
            full_cmd = f'"{self.conda_path}" run --no-capture-output -n {self.env_name} {inner_cmd}'

            self.log_signal.emit('=== 开始训练 ===')
            self.log_signal.emit(f'环境: {self.env_name}')
            self.log_signal.emit(f'模型: {self._weight_spec}')
            self.log_signal.emit(f'数据集: {data_yaml}')
            self.log_signal.emit(f'结果目录: {self.project_dir}')
            self.log_signal.emit('')

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            # Ultralytics 配置目录指向工作区内，避免系统盘权限问题
            extra_font_dirs = None
            if self.family in ('v8', 'v10', 'v11'):
                cfg_dir = os.path.join(os.path.dirname(self.project_dir), '.ultralytics')
                os.makedirs(cfg_dir, exist_ok=True)
                env['ULTRALYTICS_CONFIG_DIR'] = cfg_dir
                extra_font_dirs = [cfg_dir]

            # 预置 Arial 字体，避免训练时联网下载（308 重定向 / CDN 不可达）
            self._prepare_font_files(extra_dirs=extra_font_dirs)

            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=True,
                bufsize=1,
                env=env,
                cwd=self.repo_cwd or None
            )

            # 管道分块可能包含多条 tqdm 刷新（\r 分隔），显式按 \r/\n 拆分
            last_tqdm_emit = 0.0
            for raw_chunk in process.stdout:
                for raw_line in re.split(r'[\r\n]+', raw_chunk):
                    line = self._clean(raw_line)
                    if not line:
                        continue

                    if ('it/s]' in line or 's/it]' in line or '%|' in line):
                        compact = self._format_tqdm(line)
                        if not compact:
                            continue
                        now = time.time()
                        done_100 = compact.startswith('100%') or '| 100%' in compact
                        # 节流：进度行最多 1.5 秒一条，100% 必发
                        if done_100 or now - last_tqdm_emit >= 1.5:
                            self.log_signal.emit(compact)
                            last_tqdm_emit = now
                        continue

                    if self._is_error_line(line):
                        self.log_signal.emit(f'[错误] {line}')
                    else:
                        self.log_signal.emit(line)

            process.wait()

            if process.returncode != 0:
                self.log_signal.emit(f'[错误] 训练进程异常退出，返回码: {process.returncode}')
                self.finished_signal.emit(False, f'训练失败（返回码 {process.returncode}）')
                return

            # 定位本次真实输出目录与权重文件
            out_dir, best_weight = self._locate_output()
            if best_weight:
                self.log_signal.emit('')
                self.log_signal.emit(f'✅ 训练完成！最佳权重: {best_weight}')
                self.log_signal.emit(f'📁 结果已保存至: {out_dir}')
                self.finished_signal.emit(True, '训练完成')
            else:
                self.log_signal.emit('⚠ 训练进程结束，但未找到生成的 best 权重文件')
                self.finished_signal.emit(False, '未找到训练结果')

        except Exception as e:
            import traceback
            self.log_signal.emit(f'[严重错误] {str(e)}')
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False, f'训练异常: {str(e)}')

    def _locate_output(self):
        """在 project_dir 下找最新的 train* 目录及其中的 best 权重"""
        if not os.path.isdir(self.project_dir):
            return None, None
        candidates = []
        try:
            for entry in os.listdir(self.project_dir):
                full = os.path.join(self.project_dir, entry)
                if os.path.isdir(full) and entry.startswith(self.run_name):
                    candidates.append(full)
        except Exception:
            return None, None

        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for d in candidates:
            for rel in (os.path.join('weights', 'best.pt'), 'best.pt'):
                w = os.path.join(d, rel)
                if os.path.exists(w):
                    return d, w
        return (candidates[0] if candidates else None), None



class _GlobalModelScanWorker(QThread):
    """全盘扫描本机所有磁盘上的 YOLO 预训练权重（.pt）。

    智能跳过系统目录、Conda 安装目录、Program Files、AppData、回收站与
    开发环境目录，避免无意义遍历（这些位置不含用户下载的预训练权重；
    工作目录内的权重另有独立扫描机制兜底）。
    """
    progress = pyqtSignal(str)        # 当前正在扫描的目录
    finished_scan = pyqtSignal(dict)  # {模型名: 绝对路径}
    failed = pyqtSignal(str)

    # 确定不含用户 YOLO 权重的目录（小写匹配）
    SKIP_NAMES = {
        '$recycle.bin', 'system volume information', '$winreagent',
        'windows', 'programdata', 'perflogs', 'msocache', 'recovery',
        'node_modules', '__pycache__', '.git', '.svn', '.hg',
        'venv', '.venv', 'env', 'virtualenv',
        # Conda 安装目录（含 pkgs / Lib/site-packages，海量小文件）
        'anaconda3', 'miniconda3', 'anaconda', 'miniconda',
        'program files', 'program files (x86)',
        # 历史遗留 junction，会造成重复遍历
        'all users', 'default user', 'application data', 'documents and settings',
    }

    def __init__(self, extra_skip_prefixes=None):
        super().__init__()
        # 动态绝对路径剪枝（如检测到的真实 conda 根目录，即使目录名被自定义也能跳过）
        self._extra_prefixes = []
        for p in (extra_skip_prefixes or []):
            if p:
                self._extra_prefixes.append(os.path.normpath(p).lower())

    def _should_skip_prefix(self, root_lower):
        """按绝对路径前缀判断是否剪枝：AppData 三段 + 调用方指定路径"""
        for prefix in self._prefix_skip_cache:
            if root_lower.startswith(prefix):
                return True
        return False

    def run(self):
        import time
        try:
            all_names = set()
            for models in YOLO_FAMILY_MODELS.values():
                all_names.update(models)

            # 收集需要整段跳过的绝对路径前缀
            prefixes = list(self._extra_prefixes)
            local_app = os.environ.get('LOCALAPPDATA', '')
            roaming = os.environ.get('APPDATA', '')
            user_profile = os.environ.get('USERPROFILE', '')
            if local_app:
                prefixes.append(os.path.normpath(local_app).lower())
            if roaming:
                prefixes.append(os.path.normpath(roaming).lower())
            if user_profile:
                prefixes.append(os.path.normpath(
                    os.path.join(user_profile, 'AppData', 'LocalLow')).lower())
            self._prefix_skip_cache = prefixes

            found = {}
            last_emit = 0.0
            for drive in get_available_drives():
                for root, dirs, files in os.walk(drive):
                    root_lower = root.lower()

                    # 绝对路径剪枝：AppData / conda 根目录等
                    if self._should_skip_prefix(root_lower):
                        dirs[:] = []
                        continue

                    # 目录名剪枝：系统/缓存/联接点目录不进入
                    kept_dirs = []
                    for d in dirs:
                        dl = d.lower()
                        if dl in self.SKIP_NAMES or dl.startswith('$'):
                            continue
                        kept_dirs.append(d)
                    dirs[:] = kept_dirs

                    now = time.time()
                    if now - last_emit >= 0.5:
                        self.progress.emit(root)
                        last_emit = now

                    for f in files:
                        if f.lower().endswith('.pt'):
                            stem = os.path.splitext(f)[0]
                            if stem in all_names and stem not in found:
                                found[stem] = os.path.join(root, f)

            self.progress.emit('扫描完成')
            self.finished_scan.emit(found)
        except Exception as e:
            self.failed.emit(str(e))


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


def _env_python_run(python_exe, code, timeout=60):
    """在指定环境的 Python 解释器中执行代码片段，返回 (返回码, 合并输出)。"""
    import subprocess
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    try:
        r = subprocess.run(
            [python_exe, '-c', code],
            capture_output=True, text=True, timeout=timeout,
            env=env, encoding='utf-8', errors='ignore'
        )
    except Exception as e:
        return -1, f'执行异常: {e}'
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def apply_annotation_fixes(conda, env_name, tool_name, log_cb):
    """标注工具安装后兼容性加固。

    LabelImg：升级兼容版 PyQt5 → 导入冒烟测试 → numpy 2.x 不兼容时自动降级。
    LabelMe ：opencv-python（自带 Qt 插件冲突主因）替换为 headless 版 → 冒烟测试。

    返回 (是否成功, 失败原因)。
    """
    TUNA = 'https://pypi.tuna.tsinghua.edu.cn/simple'
    try:
        python_exe = conda.get_python_path(env_name)
    except Exception:
        python_exe = None
    if not python_exe or not os.path.exists(python_exe):
        return False, f'找不到环境 {env_name} 的 Python 解释器'

    if tool_name == 'labelImg':
        log_cb('🔧 加固 [1/3]: 升级兼容版 PyQt5（LabelImg 依赖 Qt5）...')
        for line in conda.pip_install(env_name, 'PyQt5', upgrade=True,
                                      index_url=TUNA):
            log_cb(line)

        log_cb('🔧 加固 [2/3]: LabelImg 导入冒烟测试...')
        rc, out = _env_python_run(
            python_exe,
            'from labelImg.labelImg import main; print("SMOKE_OK")')
        if 'SMOKE_OK' not in out:
            # numpy 2.x 移除了 np.float/np.int 等别名，旧版 LabelImg 会崩
            if 'numpy' in out and ("has no attribute" in out or "np.float" in out
                                   or "np.int" in out):
                log_cb('🔧 加固 [3/3]: 检测到 numpy 2.x 不兼容，降级 numpy<2 ...')
                for line in conda.pip_install(env_name, 'numpy<2',
                                              index_url=TUNA):
                    log_cb(line)
                rc, out = _env_python_run(
                    python_exe,
                    'from labelImg.labelImg import main; print("SMOKE_OK")')
            if 'SMOKE_OK' not in out:
                return False, f'LabelImg 冒烟测试失败:\n{out.strip()[-500:]}'
        log_cb('✅ LabelImg 冒烟测试通过')
        return True, ''

    if tool_name == 'labelme':
        # opencv-python 自带 Qt 插件，与 PyQt 冲突是 LabelMe 崩溃首因
        rc, out = _env_python_run(
            python_exe,
            'import subprocess, sys; '
            'r = subprocess.run([sys.executable, "-m", "pip", "show", '
            '"opencv-python"], capture_output=True); '
            'print("HAS_CV2_QT" if r.returncode == 0 else "NO")')
        if 'HAS_CV2_QT' in out:
            log_cb('🔧 加固 [1/2]: 检测到 opencv-python，替换为 headless 版（消除 Qt 插件冲突）...')
            for line in conda.pip_uninstall(env_name, 'opencv-python'):
                log_cb(line)
            for line in conda.pip_install(env_name, 'opencv-python-headless',
                                          index_url=TUNA):
                log_cb(line)
        else:
            log_cb('ℹ️ 未检测到冲突版 opencv-python，跳过替换')

        log_cb('🔧 加固 [2/2]: LabelMe 导入冒烟测试...')
        rc, out = _env_python_run(python_exe,
                                  'import labelme; print("SMOKE_OK")')
        if 'SMOKE_OK' not in out:
            return False, f'LabelMe 冒烟测试失败:\n{out.strip()[-500:]}'
        log_cb('✅ LabelMe 冒烟测试通过')
        return True, ''

    return True, ''


class AnnotationToolInstallThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, str, str)

    def __init__(self, conda_path, env_name, tool_name, is_install, force_reinstall=False):
        super().__init__()
        self.conda_path = conda_path
        self.env_name = env_name
        self.tool_name = tool_name
        self.is_install = is_install
        self.force_reinstall = force_reinstall

    def run(self):
        success = False
        error_msg = ''
        try:
            conda = CondaHandler(self.conda_path)
            action = '安装' if self.is_install else '卸载'
            self.log_signal.emit(f'正在{action} {self.tool_name}...')

            if self.is_install:
                for line in conda.pip_install(self.env_name, self.tool_name,
                                             force_reinstall=self.force_reinstall,
                                             index_url='https://pypi.tuna.tsinghua.edu.cn/simple'):
                    self.log_signal.emit(line)
                # 安装后兼容性加固（冒烟测试不通过则返回失败原因）
                ok, fix_msg = apply_annotation_fixes(
                    conda, self.env_name, self.tool_name,
                    self.log_signal.emit)
                if not ok:
                    success = False
                    error_msg = fix_msg
                else:
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


class AnnotationCrashWatchThread(QThread):
    """标注工具进程守护：输出落日志文件；启动即退 / 运行中崩溃均可被发现。"""
    started_ok = pyqtSignal(int)                     # pid
    start_failed = pyqtSignal(int, str)             # 返回码, 日志尾部
    crashed = pyqtSignal(int, str, str)             # 返回码, 日志尾部, 日志路径
    normal_exit = pyqtSignal()

    def __init__(self, cmd, env, log_path, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.env = env
        self.log_path = log_path

    @staticmethod
    def _read_tail(path, limit=1500):
        try:
            with open(path, 'rb') as f:
                return f.read().decode('utf-8', errors='ignore')[-limit:]
        except Exception:
            return ''

    def run(self):
        import subprocess
        import time
        try:
            logf = open(self.log_path, 'wb')
        except Exception as e:
            self.start_failed.emit(-1, f'无法写入日志文件: {e}')
            return
        try:
            p = subprocess.Popen(
                self.cmd, stdout=logf,
                stderr=subprocess.STDOUT, env=self.env)
        except Exception as e:
            logf.close()
            self.start_failed.emit(-1, str(e))
            return

        # 3 秒存活检查
        time.sleep(3)
        rc = p.poll()
        if rc is not None:
            logf.close()
            self.start_failed.emit(rc, self._read_tail(self.log_path))
            return

        self.started_ok.emit(p.pid)
        # 可中断轮询等待：主窗口关闭时可安全停止，子进程不受影响继续运行
        while not self.isInterruptionRequested():
            rc = p.poll()
            if rc is not None:
                break
            self.msleep(300)
        logf.close()
        if self.isInterruptionRequested():
            return
        tail = self._read_tail(self.log_path)
        if p.returncode == 0:
            self.normal_exit.emit()
        else:
            self.crashed.emit(p.returncode, tail, self.log_path)


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


class _EnvScanWorker(QThread):
    """后台扫描 conda 环境，避免界面卡顿"""
    progress = pyqtSignal(int, int, object)
    finished_scan = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, conda_handler):
        super().__init__()
        self._handler = conda_handler

    def run(self):
        try:
            result = self._handler.scan_envs(
                progress_callback=lambda i, t, info: self.progress.emit(i, t, info)
            )
            self.finished_scan.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class _EnvRemoveWorker(QThread):
    """后台删除 conda 环境"""
    done = pyqtSignal(bool, str)

    def __init__(self, conda_handler, env_name, as_admin=False, prefix=None):
        super().__init__()
        self._handler = conda_handler
        self._env_name = env_name
        self._as_admin = as_admin
        self._prefix = prefix

    def run(self):
        try:
            if self._as_admin:
                r = self._handler.remove_env_as_admin(self._env_name, prefix=self._prefix)
                self.done.emit(r.get('returncode') == 0, r.get('stderr', ''))
            else:
                ok, output = self._handler.remove_env(self._env_name, prefix=self._prefix)
                self.done.emit(ok, output)
        except Exception as e:
            self.done.emit(False, str(e))


class _BatchOrphanRemoveWorker(QThread):
    """后台批量删除所有残留环境目录"""
    progress_sig = pyqtSignal(int, int, str)
    done_sig = pyqtSignal(object)

    def __init__(self, conda_handler, paths, as_admin=False):
        super().__init__()
        self._handler = conda_handler
        self._paths = paths
        self._as_admin = as_admin

    def run(self):
        try:
            if self._as_admin:
                r = self._handler.remove_orphan_dirs_as_admin(self._paths)
                ok = (r.get('returncode') == 0)
                # 提权命令本身无逐条结果，标记成功与否，稍后重新扫描核对
                self.done_sig.emit({
                    'admin': True,
                    'success': ok,
                    'stderr': r.get('stderr', ''),
                })
            else:
                result = self._handler.remove_orphan_dirs(
                    self._paths,
                    progress_callback=lambda i, t, p: self.progress_sig.emit(i, t, p or '')
                )
                result['admin'] = False
                self.done_sig.emit(result)
        except Exception as e:
            self.done_sig.emit({'success': False, 'admin': self._as_admin,
                                'stderr': str(e), 'removed': [], 'failed': []})


class EnvManagerDialog(QDialog):
    """一键扫描、查看并删除 conda 虚拟环境"""

    def __init__(self, conda_handler, parent=None):
        super().__init__(parent)
        self._handler = conda_handler
        self._scan_worker = None
        self._remove_worker = None
        self._batch_worker = None
        self._pending_remove = None  # 正在删除的环境名
        self._expect_removed = None  # 等待扫描确认已删除的环境名
        self._envs_cache = []
        self._pending_prefix = None       # 正在删除的环境路径
        self._expect_removed_path = None  # 等待扫描确认已删除的环境路径
        self._batch_paths = []            # 正在批量清理的残留路径
        self._expect_orphan_paths = None  # 等待扫描核对的残留路径集合

        self.setWindowTitle('虚拟环境管理')
        self.setMinimumSize(720, 440)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        tip = QLabel('扫描本机所有 Conda 虚拟环境。选中一个环境后可删除，删除后不可恢复，请谨慎操作。')
        tip.setStyleSheet('color: #555;')
        tip.setWordWrap(True)
        layout.addWidget(tip)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton('↻ 一键扫描')
        self.scan_btn.setMinimumHeight(34)
        self.scan_btn.setMinimumWidth(120)
        self.scan_btn.clicked.connect(self.start_scan)
        btn_row.addWidget(self.scan_btn)

        self.remove_btn = QPushButton('× 删除选中环境')
        self.remove_btn.setMinimumHeight(34)
        self.remove_btn.setMinimumWidth(140)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setProperty('danger', True)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)
        btn_row.addWidget(self.remove_btn)

        self.clean_all_btn = QPushButton('× 一键清理所有残留')
        self.clean_all_btn.setMinimumHeight(34)
        self.clean_all_btn.setMinimumWidth(160)
        self.clean_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clean_all_btn.setProperty('warning', True)
        self.clean_all_btn.clicked.connect(self.clean_all_orphans)
        self.clean_all_btn.setEnabled(False)
        btn_row.addWidget(self.clean_all_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['环境名称', 'Python 版本', '安装路径'])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 110)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_remove_btn)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel('点击“一键扫描”开始检测环境')
        self.status_label.setStyleSheet('color: #666;')
        layout.addWidget(self.status_label)

        # 打开即自动扫描
        QTimer.singleShot(100, self.start_scan)

    # ---------- 扫描 ----------
    def start_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self.table.setRowCount(0)
        self._envs_cache = []
        self.scan_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clean_all_btn.setEnabled(False)
        self.status_label.setText('正在扫描环境，请稍候...')

        self._scan_worker = _EnvScanWorker(self._handler)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished_scan.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_progress(self, index, total, info):
        self.status_label.setText(f'正在扫描... ({index}/{total}) {info.get("name", "")}')

    def _on_scan_finished(self, envs):
        # 若刚执行过单个删除，以本次扫描结果确认环境是否真的消失
        removed_name = self._expect_removed
        removed_path = self._expect_removed_path
        verifying_removal = bool(removed_name)
        if verifying_removal:
            self._expect_removed = None
            self._expect_removed_path = None
            still_registered = any(e.get('name') == removed_name for e in envs)
            folder_remains = bool(removed_path and os.path.isdir(removed_path))
            if still_registered or folder_remains:
                self.status_label.setText(f'环境 {removed_name} 删除未生效')
                QMessageBox.warning(
                    self, '删除未生效',
                    f'环境 {removed_name} 仍然存在。\n'
                    '可能有程序正在使用该环境，请关闭相关 Python/终端进程后重试。'
                )

        # 若刚执行过批量清理，核对各残留目录是否真正消失
        batch_check = self._expect_orphan_paths
        verifying_batch = bool(batch_check)
        if verifying_batch:
            self._expect_orphan_paths = None
            remaining = [p for p in batch_check if p and os.path.isdir(p)]

        self._envs_cache = envs
        self.table.setRowCount(0)
        for env in envs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(env.get('name', ''))
            py_item = QTableWidgetItem(env.get('python', '') or ('—' if env.get('orphan') else '未知'))
            if env.get('orphan'):
                # 残留目录行用橙色提示
                name_item.setForeground(QColor('#e65100'))
                py_item.setForeground(QColor('#e65100'))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, py_item)
            self.table.setItem(row, 2, QTableWidgetItem(env.get('path', '')))
        self.scan_btn.setEnabled(True)

        orphan_count = sum(1 for e in envs if e.get('orphan'))
        valid_count = len(envs) - orphan_count
        # 有残留才允许一键清理
        self.clean_all_btn.setEnabled(orphan_count > 0)

        if verifying_batch:
            cleaned_n = len(batch_check) - len(remaining)
            if remaining:
                self.status_label.setText(
                    f'批量清理完成 {cleaned_n}/{len(batch_check)}，仍有 {len(remaining)} 个未删除')
                QMessageBox.warning(
                    self, '部分未删除',
                    f'已清理 {cleaned_n} 个，仍有 {len(remaining)} 个残留文件夹。\n'
                    '可能文件被占用，或仍需管理员权限，请重试。'
                )
            else:
                self.status_label.setText(f'✅ 已全部清理完成（共 {len(batch_check)} 个残留）')
        elif not verifying_removal:
            msg = f'扫描完成，共 {valid_count} 个环境'
            if orphan_count:
                msg += f'，另有 {orphan_count} 个残留文件夹可清理'
            self.status_label.setText(msg)
        self._update_remove_btn()

    def _on_scan_failed(self, msg):
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f'扫描失败: {msg}')
        QMessageBox.warning(self, '扫描失败', msg)

    # ---------- 删除 ----------
    def _selected_env(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._envs_cache):
            return None
        return self._envs_cache[row]

    def _update_remove_btn(self):
        env = self._selected_env()
        # base 环境不允许删除
        self.remove_btn.setEnabled(bool(env) and env.get('name') != 'base')

    def remove_selected(self):
        env = self._selected_env()
        if not env:
            return
        name = env.get('name', '')
        if name == 'base':
            QMessageBox.warning(self, '无法删除', 'base 是 Conda 的基础环境，不能删除。')
            return

        is_orphan = bool(env.get('orphan'))
        real_name = env.get('real_name', name)

        reply = QMessageBox()
        reply.setIcon(QMessageBox.Icon.Warning)
        reply.setWindowTitle('确认删除')
        py_info = env.get('python') or ('—（残留文件夹）' if is_orphan else '未知')
        reply.setText(f'确定要删除环境 “{real_name}” 吗？')
        reply.setInformativeText(
            f'Python 版本: {py_info}\n安装路径: {env.get("path", "")}\n\n'
            + ('该残留文件夹及其所有文件将被永久删除，此操作不可恢复！'
               if is_orphan else
               '该环境中的所有包和数据将被永久删除，此操作不可恢复！')
        )
        reply.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        reply.button(QMessageBox.StandardButton.Yes).setText('确认删除')
        reply.button(QMessageBox.StandardButton.No).setText('取消')
        if reply.exec() != QMessageBox.StandardButton.Yes:
            return

        self._do_remove(real_name, as_admin=False, prefix=env.get('path'))

    def _do_remove(self, name, as_admin=False, prefix=None):
        self.scan_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        action = '正在以管理员权限删除' if as_admin else '正在删除'
        self.status_label.setText(f'{action}环境 {name}，请稍候...')

        self._pending_remove = name
        self._pending_prefix = prefix
        self._remove_worker = _EnvRemoveWorker(self._handler, name, as_admin=as_admin, prefix=prefix)
        self._remove_worker.done.connect(self._on_remove_done)
        self._remove_worker.start()

    def _on_remove_done(self, ok, output):
        name = self._pending_remove
        prefix = self._pending_prefix
        self._pending_remove = None
        self._pending_prefix = None

        if ok:
            # 重新扫描确认环境已删除
            self._expect_removed = name
            self._expect_removed_path = prefix
            self.status_label.setText('删除指令已完成，正在重新扫描确认...')
            self.start_scan()
            return

        low_out = (output or '').lower()
        permission_like = any(k in low_out for k in ('permission', 'denied', 'access', 'winerror 5', '拒绝'))
        if permission_like:
            r = QMessageBox()
            r.setIcon(QMessageBox.Icon.Warning)
            r.setWindowTitle('权限不足')
            r.setText(f'删除环境 {name} 失败：权限不足。')
            r.setInformativeText('是否以管理员身份重新删除？\n点击“是”后将弹出 UAC 请求，请点击“是”。')
            r.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            r.button(QMessageBox.StandardButton.Yes).setText('管理员重试')
            r.button(QMessageBox.StandardButton.No).setText('取消')
            if r.exec() == QMessageBox.StandardButton.Yes:
                self._do_remove(name, as_admin=True, prefix=prefix)
                return
        else:
            QMessageBox.critical(
                self, '删除失败',
                f'环境 {name} 删除失败：\n\n{(output or "无详细信息")[-800:]}'
            )

        self.scan_btn.setEnabled(True)

    # ---------- 批量清理残留 ----------
    def _collect_orphan_paths(self):
        """从当前扫描缓存中提取残留目录路径（去重）"""
        seen = []
        for env in self._envs_cache:
            if env.get('orphan'):
                p = env.get('path', '')
                if p and p not in seen:
                    seen.append(p)
        return seen

    def clean_all_orphans(self):
        paths = self._collect_orphan_paths()
        if not paths:
            self.clean_all_btn.setEnabled(False)
            return

        # 列出全部残留路径，二次确认
        listing = '\n'.join(f'  • {p}' for p in paths)
        reply = QMessageBox()
        reply.setIcon(QMessageBox.Icon.Warning)
        reply.setWindowTitle('确认一键清理残留')
        reply.setText(f'检测到 {len(paths)} 个残留文件夹，将全部永久删除：')
        reply.setInformativeText(
            f'{listing}\n\n'
            '这些是 Conda 已注销但文件残留的目录，删除后不可恢复。\n'
            '是否继续？'
        )
        reply.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        reply.button(QMessageBox.StandardButton.Yes).setText('全部清理')
        reply.button(QMessageBox.StandardButton.No).setText('取消')
        if reply.exec() != QMessageBox.StandardButton.Yes:
            return

        self._do_batch_clean(paths, as_admin=False)

    def _do_batch_clean(self, paths, as_admin=False):
        self.scan_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clean_all_btn.setEnabled(False)
        action = '正在以管理员权限批量清理' if as_admin else '正在批量清理'
        self.status_label.setText(f'{action} {len(paths)} 个残留文件夹，请稍候...')

        self._batch_paths = paths
        self._batch_worker = _BatchOrphanRemoveWorker(self._handler, paths, as_admin=as_admin)
        self._batch_worker.progress_sig.connect(self._on_batch_progress)
        self._batch_worker.done_sig.connect(self._on_batch_clean_done)
        self._batch_worker.start()

    def _on_batch_progress(self, index, total, path):
        if total:
            base = f'正在批量清理... ({index}/{total})'
            self.status_label.setText(f'{base} {path}')

    def _on_batch_clean_done(self, result):
        paths = self._batch_paths
        self._batch_paths = []

        admin = result.get('admin')
        if admin:
            # 提权进程无逐条输出：以重新扫描的真实结果为准
            if result.get('success'):
                self._expect_orphan_paths = paths
                self.status_label.setText('管理员清理已完成，正在重新扫描核对...')
                self.start_scan()
                return
            low = (result.get('stderr') or '').lower()
            if 'cancelled' in low or 'cancel' in low or '1223' in low:
                # 用户在 UAC 点了取消
                self.status_label.setText('已取消管理员清理')
            else:
                QMessageBox.critical(self, '清理失败',
                                     f'管理员批量清理失败：\n\n{result.get("stderr") or "无详细信息"}')
            self.scan_btn.setEnabled(True)
            self.clean_all_btn.setEnabled(True)
            return

        failed = result.get('failed', [])
        removed = result.get('removed', [])

        if not failed:
            # 全部成功，仍重新扫描核对（同时刷新界面）
            self._expect_orphan_paths = paths
            self.status_label.setText('批量删除已完成，正在重新扫描核对...')
            self.start_scan()
            return

        # 有权限类失败：询问是否对失败项整体提权重试
        permission_like = result.get('permission_like')
        failed_paths = [p for p, _reason in failed]
        fail_detail = '\n'.join(f'  • {p}（{reason}）' for p, reason in failed)

        if permission_like:
            r = QMessageBox()
            r.setIcon(QMessageBox.Icon.Warning)
            r.setWindowTitle('权限不足')
            r.setText(f'{len(failed_paths)} 个残留目录删除失败（权限不足或被占用）。')
            r.setInformativeText(
                f'{fail_detail}\n\n'
                '是否以管理员身份重新清理这些目录？\n'
                '点击“是”后将弹出 UAC 请求，请点击“是”。'
            )
            r.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            r.button(QMessageBox.StandardButton.Yes).setText('管理员重试')
            r.button(QMessageBox.StandardButton.No).setText('取消')
            if r.exec() == QMessageBox.StandardButton.Yes:
                self._do_batch_clean(failed_paths, as_admin=True)
                return
        else:
            QMessageBox.warning(
                self, '部分清理失败',
                f'已清理 {len(removed)} 个，以下 {len(failed_paths)} 个失败：\n\n{fail_detail}'
            )

        self.scan_btn.setEnabled(True)
        self.clean_all_btn.setEnabled(True)


class ResumeDialog(QDialog):
    """检测到未完成部署任务时的恢复选择对话框。

    选项：
      继续部署 —— 从上次中断的步骤/下载断点继续；
      放弃并清理 —— 删除未完成的下载文件与任务状态缓存；
      暂不处理 —— 保留进度，下次启动再次询问。
    """
    CONTINUE = 1
    DISCARD = 2
    LATER = 0

    def __init__(self, state, invalid_files=None, parent=None):
        super().__init__(parent)
        self.choice = self.LATER
        self.setWindowTitle('发现未完成的部署任务')
        self.setMinimumWidth(540)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel('⏸️ 检测到上次有未完成的下载 / 部署任务')
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        # ----- 任务信息 -----
        yolo_name = state.get('yolo_name', '')
        env_name = state.get('env_name', '')
        updated_at = state.get('updated_at', '')
        current_step = state.get('current_step', '') or '未知'
        done_steps = state.get('completed_steps') or []

        info_lines = [
            f'<b>YOLO 版本：</b>{yolo_name}',
            f'<b>环境名称：</b>{env_name}',
            f'<b>中断时间：</b>{updated_at}',
            f'<b>中断时正在执行：</b>{current_step}',
            f'<b>已完成步骤：</b>{len(done_steps)} 项'
            + (f'（{"、".join(done_steps)}）' if done_steps else ''),
        ]

        dl = state.get('download') or {}
        if dl.get('filename'):
            cur_mb = (dl.get('downloaded') or 0) / (1024 * 1024)
            total = dl.get('total') or 0
            if total > 0:
                pct = int((dl.get('downloaded') or 0) * 100 / total)
                info_lines.append(
                    f'<b>下载进度：</b>{dl["filename"]} 已下载 {pct}% '
                    f'（{cur_mb:.1f}/{total / (1024 * 1024):.1f} MB），恢复后从断点续传')
            else:
                info_lines.append(
                    f'<b>下载进度：</b>{dl["filename"]} 已下载 {cur_mb:.1f} MB，恢复后继续')

        info = QLabel('<br>'.join(info_lines))
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        info.setStyleSheet(
            'background-color: #eef1f6; border-radius: 8px; padding: 12px;')
        layout.addWidget(info)

        if invalid_files:
            warn = QLabel(
                f'⚠️ 以下已下载文件校验失败（损坏或缺失），恢复时将自动重新下载：<br>'
                f'{"、".join(invalid_files)}')
            warn.setWordWrap(True)
            warn.setStyleSheet(
                'color: #b06000; background-color: #fff7e6; border-radius: 8px; padding: 10px;')
            layout.addWidget(warn)

        hint = QLabel('请选择如何处理该任务：')
        layout.addWidget(hint)

        # ----- 选项按钮（清晰醒目 + 说明文字） -----
        btn_continue = QPushButton('▶ 继续部署')
        btn_continue.setProperty('success', True)
        btn_continue.setMinimumHeight(44)
        btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_continue.setToolTip('从断点继续，已完成的步骤和已下载的内容不会重复')
        btn_continue.clicked.connect(self._choose_continue)
        layout.addWidget(btn_continue)

        lbl_continue = QLabel('从上次中断的位置继续执行，自动跳过已完成步骤，下载支持断点续传')
        lbl_continue.setStyleSheet('color: #5f6368; padding-left: 4px;')
        layout.addWidget(lbl_continue)

        btn_discard = QPushButton('🗑 放弃并清理')
        btn_discard.setMinimumHeight(44)
        btn_discard.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_discard.setStyleSheet(
            'QPushButton { background-color: #fce8e6; color: #c5221f; border: 1px solid #f5c6c2; '
            'border-radius: 8px; font-weight: bold; }'
            'QPushButton:hover { background-color: #fad2cf; }'
            'QPushButton:pressed { background-color: #f5b8b3; }')
        btn_discard.setToolTip('删除未完成的下载文件和任务缓存，之后可重新部署')
        btn_discard.clicked.connect(self._choose_discard)
        layout.addWidget(btn_discard)

        lbl_discard = QLabel('删除本次任务已下载的实体文件与进度缓存（已创建的环境和源码保留，可在环境管理中删除）')
        lbl_discard.setWordWrap(True)
        lbl_discard.setStyleSheet('color: #5f6368; padding-left: 4px;')
        layout.addWidget(lbl_discard)

        btn_later = QPushButton('暂不处理，下次启动再问我')
        btn_later.setMinimumHeight(32)
        btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_later.clicked.connect(self._choose_later)
        layout.addWidget(btn_later)

    def _choose_continue(self):
        self.choice = self.CONTINUE
        self.accept()

    def _choose_discard(self):
        reply = QMessageBox.question(
            self, '确认放弃',
            '将删除该任务未完成的下载文件和进度缓存，确定放弃吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.choice = self.DISCARD
            self.accept()

    def _choose_later(self):
        self.choice = self.LATER
        self.reject()


class CloseConfirmDialog(QDialog):
    """关闭窗口时的选择对话框（部署/下载进行中）。

    选项：
      后台继续 —— 最小化到系统托盘，任务继续执行；
      关闭并保留进度 —— 退出程序，下次打开可从断点继续；
      取消 —— 返回主窗口。
    """
    BACKGROUND = 1
    CLOSE_KEEP = 2
    CANCEL = 0

    def __init__(self, deploy_busy=False, env_busy=False, training_busy=False, parent=None):
        super().__init__(parent)
        self.choice = self.CANCEL
        self.setWindowTitle('任务进行中')
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        running = []
        if deploy_busy:
            running.append('YOLO 环境部署 / 模型下载')
        if env_busy:
            running.append('Conda / Git 环境安装')
        if training_busy:
            running.append('模型训练')

        title = QLabel('⏳ 以下任务正在执行中')
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        info = QLabel('<br>'.join(f'• {name}' for name in running))
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet(
            'background-color: #eef1f6; border-radius: 8px; padding: 12px;')
        layout.addWidget(info)

        if deploy_busy or env_busy:
            desc = QLabel(
                '关闭窗口不会丢失进度：已完成的步骤和下载断点已保存，'
                '下次打开程序时可选择继续。')
        else:
            desc = QLabel('训练任务无法断点续传，直接关闭将终止本次训练。')
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_bg = QPushButton('🔽 最小化到后台继续')
        btn_bg.setProperty('primary', True)
        btn_bg.setMinimumHeight(44)
        btn_bg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bg.setToolTip('窗口隐藏到系统托盘，任务继续执行，完成后自动恢复窗口')
        btn_bg.clicked.connect(self._choose_bg)
        layout.addWidget(btn_bg)

        if deploy_busy or env_busy:
            btn_close = QPushButton('💾 关闭并保留进度')
            btn_close.setToolTip('退出程序；下载与部署进度已保存，下次启动可选择继续')
        else:
            btn_close = QPushButton('⛔ 直接关闭（终止训练）')
            btn_close.setToolTip('立即退出程序，本次训练进度不会保留')
        btn_close.setMinimumHeight(44)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self._choose_close)
        layout.addWidget(btn_close)

        btn_cancel = QPushButton('取消')
        btn_cancel.setMinimumHeight(32)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self._choose_cancel)
        layout.addWidget(btn_cancel)

    def _choose_bg(self):
        self.choice = self.BACKGROUND
        self.accept()

    def _choose_close(self):
        self.choice = self.CLOSE_KEEP
        self.accept()

    def _choose_cancel(self):
        self.choice = self.CANCEL
        self.reject()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.env_result = None
        self.install_thread = None
        self.env_scan_thread = None
        self.env_install_thread = None
        self._anno_scan_thread = None
        self._anno_install_thread = None
        self._anno_watchers = []          # 标注工具守护线程，运行期间持有引用
        self._anno_running = set()        # 正在运行的标注工具，防止重复启动
        self._relaunch_after_repair = None  # 修复完成后自动重启的工具名
        self._editor_deploy_thread = None
        # 操作页 val/predict/export/video 线程，运行期间持有引用，
        # 结束自动移除，避免被 GC 回收正在运行的 QThread 导致硬崩溃
        self._ops_threads = []
        self._editors = {}
        self._drives = get_available_drives()
        self._log_lines = []
        self._current_workspace = None
        self._current_env_name = None
        self._train_model_paths = {}
        self._train_deploy_info = None
        self._global_models_cache = None
        self.init_ui()
        QTimer.singleShot(300, self.show_about)
        QTimer.singleShot(800, self.auto_scan_env)
        # 启动后检测是否有未完成部署任务
        QTimer.singleShot(1200, self._check_resume_task)

    def _check_resume_task(self):
        from modules.task_state import TaskStateManager
        state_mgr = TaskStateManager()
        if not state_mgr.has_pending():
            return
        st = state_mgr.load()
        if not st:
            return
        try:
            invalid = state_mgr.verify_finished_files()
        except Exception:
            invalid = []
        dlg = ResumeDialog(st, invalid_files=invalid, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.choice == ResumeDialog.CONTINUE:
            self._do_resume_deploy(st)
        elif dlg.choice == ResumeDialog.DISCARD:
            removed = state_mgr.discard(log=lambda msg: self.append_log(msg))
            self.append_log(
                f'已放弃未完成任务，共清理 {len(removed)} 个文件/缓存')

    def _do_resume_deploy(self, state):
        vi = state.get('version_info')
        if not vi:
            QMessageBox.warning(self, '无法继续', '状态文件中缺少版本信息，无法恢复')
            return
        if not self.env_result or not self.env_result.get('conda_path'):
            QMessageBox.warning(
                self, '无法继续',
                '尚未检测到 Conda 环境。\n\n请先等待环境扫描完成（或点击「自动安装环境」安装 Conda），'
                '然后重新打开程序以继续未完成的部署。\n部署进度已保留，不会丢失。')
            return
        self.append_log('=' * 60)
        self.append_log('🔄 从断点继续部署...')
        self.append_log(f'YOLO 版本: {state.get("yolo_name", "")}')
        self.append_log(f'已完成步骤: {", ".join(state.get("completed_steps") or [])}')
        self.append_log('=' * 60)

        # 恢复下拉框选项到保存的值
        env_name = vi.get('env_name', '')
        for i in range(self.version_combo.count()):
            if self.version_combo.itemData(i).get('env_name') == env_name:
                self.version_combo.setCurrentIndex(i)
                break
        py_ver = state.get('python_version', '')
        for i in range(self.python_combo.count()):
            if str(self.python_combo.itemData(i)) == str(py_ver):
                self.python_combo.setCurrentIndex(i)
                break
        pt_ver = state.get('pytorch_version', '')
        for i in range(self.pytorch_combo.count()):
            if str(self.pytorch_combo.itemData(i)) == str(pt_ver):
                self.pytorch_combo.setCurrentIndex(i)
                break
        self.gpu_checkbox.setChecked(bool(state.get('use_gpu')))
        ws = state.get('workspace_dir', '')
        if ws:
            from modules.platform_utils import is_windows
            if is_windows():
                drive = os.path.splitdrive(ws)[0]
                if drive:
                    drive = drive[:-1] if drive.endswith(':') else drive
                    idx = self.workspace_drive_combo.findData(drive)
                    if idx >= 0:
                        self.workspace_drive_combo.setCurrentIndex(idx)
            else:
                # Linux/macOS：安装位置为绝对路径，直接选中并补齐目录层级
                idx = self.workspace_drive_combo.findData(ws)
                if idx >= 0:
                    self.workspace_drive_combo.setCurrentIndex(idx)
                else:
                    parent = os.path.dirname(ws)
                    idx = self.workspace_drive_combo.findData(parent)
                    if idx >= 0:
                        self.workspace_drive_combo.setCurrentIndex(idx)
            folder = os.path.basename(ws)
            if folder and folder != ws:
                self.workspace_folder_edit.setText(folder)

        self._set_controls_enabled(False)
        self.progress_widget.show()
        self.progress_bar.show()
        self.progress_label.setText('正在恢复部署...')
        self.progress_label.show()
        self._log_lines = []

        self.install_thread = InstallThread(
            self.env_result['conda_path'],
            vi,
            bool(state.get('use_gpu')),
            bool(state.get('run_test')),
            python_version=state.get('python_version'),
            pytorch_version=state.get('pytorch_version'),
            workspace_dir=state.get('workspace_dir'),
            annotation_tool=state.get('annotation_tool') or None,
            resume=True,
        )
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.step_signal.connect(self._on_step)
        self.install_thread.finished_signal.connect(self._on_install_finished)
        self.install_thread.download_progress_signal.connect(self._on_download_progress)
        self.install_thread.start()

    def init_ui(self):
        self.setWindowTitle('YOLO 全版本一键部署工具')
        self.setGeometry(100, 100, 920, 780)
        self.setMinimumSize(720, 600)
        self.setStyleSheet(_APP_STYLE)

        # 设置窗口图标
        icon_path = get_resource_path('assets/app.png')
        if not os.path.exists(icon_path):
            icon_path = get_resource_path('assets/app.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题区域
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        title_label = QLabel('YOLO 全版本一键部署工具')
        title_font = QFont('Microsoft YaHei', 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet('color: #1a73e8; padding: 4px;')
        title_layout.addWidget(title_label)

        subtitle_label = QLabel('支持 v5 / v7 / v8 / v9 / v10 / v11 | 自动环境配置 | 一键训练')
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet('color: #5f6368; font-size: 12px; padding-bottom: 4px;')
        title_layout.addWidget(subtitle_label)

        main_layout.addWidget(title_widget)

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
        btn_layout.setSpacing(8)
        self.scan_btn = QPushButton('↻ 重新扫描')
        self.scan_btn.setMinimumHeight(34)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.scan_environment)

        self.install_env_btn = QPushButton('⚙ 自动安装环境')
        self.install_env_btn.setMinimumHeight(34)
        self.install_env_btn.setProperty('primary', True)
        self.install_env_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_env_btn.clicked.connect(self.start_env_install)

        self.browse_conda_btn = QPushButton('▸ 指定 Conda 路径')
        self.browse_conda_btn.setMinimumHeight(34)
        self.browse_conda_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_conda_btn.clicked.connect(self._browse_conda_path)

        self.global_scan_btn = QPushButton('⊙ 全局扫描 Conda')
        self.global_scan_btn.setMinimumHeight(34)
        self.global_scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._ui_ready = False  # 构建期间不触发自动全盘扫描
        self._init_deploy_tab()
        self._init_training_tab()
        self._init_model_ops_tab()
        self._init_annotation_tab()
        self._init_editor_deploy_tab()
        # 切换页签时快速同步环境列表（仅读部署记录，不额外起进程）
        self.tab_widget.currentChanged.connect(lambda _i: self._refresh_conda_env_combos(scan_conda=False))
        main_layout.addWidget(self.tab_widget, stretch=3)

        log_group = QGroupBox('运行日志')
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Consolas', 9))
        self.log_text.setMinimumHeight(180)
        # 回放控件创建前缓存的早期日志
        if getattr(self, '_log_lines', None):
            self.log_text.append('\n'.join(self._log_lines))
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, stretch=2)
        self._ui_ready = True  # 界面就绪，之后的用户操作可触发自动扫描

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
        self.python_combo.currentIndexChanged.connect(self._on_python_changed)
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
        self.browse_btn = QPushButton('▸')
        self.browse_btn.setMinimumHeight(30)
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.clicked.connect(self._browse_workspace)
        folder_layout.addWidget(self.browse_btn)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_layout)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(folder_widget, 2, 3)

        model_size_label = QLabel('模型大小:')
        model_size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.deploy_model_combo = QComboBox()
        self.deploy_model_combo.setMinimumHeight(30)
        grid.addWidget(model_size_label, 3, 0)
        grid.addWidget(self.deploy_model_combo, 3, 1, 1, 3)

        annotation_label = QLabel('标注工具:')
        annotation_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.annotation_combo = QComboBox()
        self.annotation_combo.setMinimumHeight(30)
        grid.addWidget(annotation_label, 4, 0)
        grid.addWidget(self.annotation_combo, 4, 1, 1, 3)

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

        self.manage_env_btn = QPushButton('☰ 管理虚拟环境')
        self.manage_env_btn.setMinimumHeight(36)
        self.manage_env_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manage_env_btn.setProperty('warning', True)
        self.manage_env_btn.clicked.connect(self._open_env_manager)
        self.manage_env_btn.setEnabled(True)
        config_layout.addWidget(self.manage_env_btn)

        config_group.setLayout(config_layout)
        deploy_layout.addWidget(config_group)

        self.install_btn = QPushButton('▶ 开始一键安装部署')
        self.install_btn.setMinimumHeight(52)
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.setProperty('success', True)
        install_font = QFont('Microsoft YaHei', 14, QFont.Weight.Bold)
        self.install_btn.setFont(install_font)
        self.install_btn.clicked.connect(self.start_install)
        deploy_layout.addWidget(self.install_btn)

        # 进度区域：进度条 + 状态标签
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 0)
        progress_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel('')
        self.progress_label.setStyleSheet('color: #5f6368; font-size: 12px;')
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.hide()
        progress_layout.addWidget(self.progress_label)

        self.progress_widget = progress_widget
        self.progress_widget.hide()
        deploy_layout.addWidget(self.progress_widget)

        deploy_layout.addSpacing(8)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(deploy_tab, '▶ 一键部署')

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
        btn_row.setSpacing(8)
        self.refresh_anno_btn = QPushButton('↻ 刷新')
        self.refresh_anno_btn.setMinimumWidth(80)
        self.refresh_anno_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_anno_btn.clicked.connect(self._refresh_annotation_envs)
        btn_row.addWidget(self.refresh_anno_btn)

        self.add_env_btn = QPushButton('+ 添加')
        self.add_env_btn.setMinimumWidth(80)
        self.add_env_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_env_btn.clicked.connect(self._add_annotation_env)
        btn_row.addWidget(self.add_env_btn)

        self.remove_env_btn = QPushButton('− 移除')
        self.remove_env_btn.setMinimumWidth(80)
        self.remove_env_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_env_btn.setProperty('danger', True)
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
        launch_row.setSpacing(12)
        self.launch_labelimg_btn = QPushButton('◆ 启动 LabelImg')
        self.launch_labelimg_btn.setMinimumHeight(44)
        self.launch_labelimg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_labelimg_btn.setProperty('warning', True)
        anno_font = QFont('Microsoft YaHei', 13, QFont.Weight.Bold)
        self.launch_labelimg_btn.setFont(anno_font)
        self.launch_labelimg_btn.clicked.connect(lambda: self._launch_annotation_tool('labelImg'))
        self.launch_labelimg_btn.setEnabled(False)
        launch_row.addWidget(self.launch_labelimg_btn)

        self.launch_labelme_btn = QPushButton('◇ 启动 LabelMe')
        self.launch_labelme_btn.setMinimumHeight(44)
        self.launch_labelme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_labelme_btn.setProperty('primary', True)
        self.launch_labelme_btn.setFont(anno_font)
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

        labelimg_title = QLabel('◆ LabelImg')
        labelimg_title.setStyleSheet('font-weight: bold; color: #2c3e50;')
        grid.addWidget(labelimg_title, 0, 0)

        self.install_labelimg_btn = QPushButton('↓ 安装')
        self.install_labelimg_btn.setMinimumHeight(32)
        self.install_labelimg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_labelimg_btn.clicked.connect(lambda: self._install_annotation_tool('labelImg', True))
        self.install_labelimg_btn.setEnabled(False)
        grid.addWidget(self.install_labelimg_btn, 0, 1)

        self.uninstall_labelimg_btn = QPushButton('× 卸载')
        self.uninstall_labelimg_btn.setMinimumHeight(32)
        self.uninstall_labelimg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uninstall_labelimg_btn.setProperty('danger', True)
        self.uninstall_labelimg_btn.clicked.connect(lambda: self._install_annotation_tool('labelImg', False))
        self.uninstall_labelimg_btn.setEnabled(False)
        grid.addWidget(self.uninstall_labelimg_btn, 0, 2)

        labelme_title = QLabel('◇ LabelMe')
        labelme_title.setStyleSheet('font-weight: bold; color: #2c3e50;')
        grid.addWidget(labelme_title, 1, 0)

        self.install_labelme_btn = QPushButton('↓ 安装')
        self.install_labelme_btn.setMinimumHeight(32)
        self.install_labelme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_labelme_btn.clicked.connect(lambda: self._install_annotation_tool('labelme', True))
        self.install_labelme_btn.setEnabled(False)
        grid.addWidget(self.install_labelme_btn, 1, 1)

        self.uninstall_labelme_btn = QPushButton('× 卸载')
        self.uninstall_labelme_btn.setMinimumHeight(32)
        self.uninstall_labelme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uninstall_labelme_btn.setProperty('danger', True)
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
            '  • LabelMe：支持多边形标注，需转换为 YOLO 格式\n'
            '⚠️ 注意：图片路径与文件名请使用纯英文/数字，避免中文、空格，否则工具可能崩溃\n'
            '📄 崩溃排查：运行日志保存在 <程序目录>/logs/，崩溃时弹窗可一键自动修复'
        )
        hint_label.setStyleSheet('color: #666; font-size: 11px;')
        hint_label.setWordWrap(True)
        anno_layout.addWidget(hint_label)

        anno_layout.addSpacing(8)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(anno_tab, '◆ 标注工具')

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
        self.editor_browse_btn = QPushButton('▸ 浏览')
        self.editor_browse_btn.setMinimumHeight(30)
        self.editor_browse_btn.clicked.connect(self._browse_editor_project)
        grid.addWidget(self.editor_browse_btn, 1, 3)

        config_layout.addLayout(grid)

        self.editor_env_info = QLabel('请选择要部署的 YOLO 环境')
        self.editor_env_info.setStyleSheet('color: #666; padding-left: 98px;')
        self.editor_env_info.setWordWrap(True)
        config_layout.addWidget(self.editor_env_info)

        refresh_btn_row = QHBoxLayout()
        self.refresh_editor_btn = QPushButton('↻ 刷新环境')
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

        self.deploy_editor_btn = QPushButton('⚙ 配置环境')
        self.deploy_editor_btn.setMinimumHeight(42)
        self.deploy_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deploy_editor_btn.setProperty('primary', True)
        self.deploy_editor_btn.clicked.connect(self._deploy_to_editors)
        self.deploy_editor_btn.setEnabled(False)
        btn_row.addWidget(self.deploy_editor_btn, 1)

        btn_row.addSpacing(10)

        self.open_editor_btn = QPushButton('▶ 打开编辑器')
        self.open_editor_btn.setMinimumHeight(42)
        self.open_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_editor_btn.setProperty('success', True)
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
        self.tab_widget.addTab(deploy_tab, '⚙ 环境部署')

    def _init_model_ops_tab(self):
        ops_tab = QWidget()
        layout = QVBoxLayout(ops_tab)
        layout.setContentsMargins(0,0,0,0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)

        # 通用配置
        cfg_group = QGroupBox('通用配置')
        cfg_grid = QGridLayout()
        cfg_grid.setSpacing(10)

        env_label = QLabel('Conda 环境:')
        env_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.ops_env_combo = QComboBox()
        self.ops_env_combo.setMinimumHeight(30)
        envs = self._load_installed_envs()
        for name in envs:
            self.ops_env_combo.addItem(name)
        if self.ops_env_combo.count()==0:
            self.ops_env_combo.addItem('未检测到环境')

        self.ops_refresh_env_btn = QPushButton('↻')
        self.ops_refresh_env_btn.setMinimumHeight(30)
        self.ops_refresh_env_btn.setMaximumWidth(40)
        self.ops_refresh_env_btn.setToolTip('重新扫描 Conda 环境')
        self.ops_refresh_env_btn.clicked.connect(self._refresh_conda_env_combos)

        ops_env_box = QWidget()
        ops_env_layout = QHBoxLayout(ops_env_box)
        ops_env_layout.setContentsMargins(0, 0, 0, 0)
        ops_env_layout.setSpacing(6)
        ops_env_layout.addWidget(self.ops_env_combo, 1)
        ops_env_layout.addWidget(self.ops_refresh_env_btn)

        cfg_grid.addWidget(env_label,0,0)
        cfg_grid.addWidget(ops_env_box,0,1,1,3)

        model_label = QLabel('模型文件:')
        model_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        model_row = QHBoxLayout()
        self.ops_model_edit = QLineEdit()
        self.ops_model_edit.setMinimumHeight(30)
        self.ops_model_browse = QPushButton('▸')
        self.ops_model_browse.setMaximumWidth(40)
        self.ops_model_browse.clicked.connect(lambda: self._browse_file(self.ops_model_edit,'选择模型文件 (*.pt)'))
        model_row.addWidget(self.ops_model_edit)
        model_row.addWidget(self.ops_model_browse)
        model_widget = QWidget()
        model_widget.setLayout(model_row)
        cfg_grid.addWidget(model_label,1,0)
        cfg_grid.addWidget(model_widget,1,1,1,3)

        data_label = QLabel('数据集 data.yaml:')
        data_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        data_row = QHBoxLayout()
        self.ops_data_edit = QLineEdit()
        self.ops_data_edit.setMinimumHeight(30)
        self.ops_data_browse = QPushButton('▸')
        self.ops_data_browse.setMaximumWidth(40)
        self.ops_data_browse.clicked.connect(lambda: self._browse_file(self.ops_data_edit,'选择 data.yaml (*)'))
        data_row.addWidget(self.ops_data_edit)
        data_row.addWidget(self.ops_data_browse)
        data_widget = QWidget()
        data_widget.setLayout(data_row)
        cfg_grid.addWidget(data_label,2,0)
        cfg_grid.addWidget(data_widget,2,1,1,3)

        source_label = QLabel('推理源:')
        source_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        source_row = QHBoxLayout()
        self.ops_source_edit = QLineEdit()
        self.ops_source_edit.setMinimumHeight(30)
        self.ops_source_browse = QPushButton('▸')
        self.ops_source_browse.setMaximumWidth(40)
        self.ops_source_browse.clicked.connect(lambda: self._browse_file(self.ops_source_edit,'选择文件或文件夹'))
        source_row.addWidget(self.ops_source_edit)
        source_row.addWidget(self.ops_source_browse)
        source_widget = QWidget()
        source_widget.setLayout(source_row)
        cfg_grid.addWidget(source_label,3,0)
        cfg_grid.addWidget(source_widget,3,1,1,3)

        export_format_label = QLabel('导出格式:')
        export_format_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.ops_export_format = QComboBox()
        self.ops_export_format.addItems(['onnx','torchscript','coreml','saved_model','pb','tflite','tfjs','paddle'])
        cfg_grid.addWidget(export_format_label,4,0)
        cfg_grid.addWidget(self.ops_export_format,4,1)

        cfg_group.setLayout(cfg_grid)
        vbox.addWidget(cfg_group)

        # 操作按钮
        btn_group = QGroupBox('模型操作')
        btn_grid = QGridLayout()
        self.btn_validate = QPushButton('✓ 验证')
        self.btn_predict = QPushButton('⊙ 预测')
        self.btn_export = QPushButton('↑ 导出')
        self.btn_video = QPushButton('▶ 视频推理')
        for btn in [self.btn_validate, self.btn_predict, self.btn_export, self.btn_video]:
            btn.setMinimumHeight(48)
        btn_grid.addWidget(self.btn_validate,0,0)
        btn_grid.addWidget(self.btn_predict,0,1)
        btn_grid.addWidget(self.btn_export,1,0)
        btn_grid.addWidget(self.btn_video,1,1)
        self.btn_validate.clicked.connect(lambda: self._run_yolo_cmd('val'))
        self.btn_predict.clicked.connect(lambda: self._run_yolo_cmd('predict'))
        self.btn_export.clicked.connect(lambda: self._run_yolo_cmd('export'))
        self.btn_video.clicked.connect(lambda: self._run_yolo_cmd('video'))
        btn_group.setLayout(btn_grid)
        vbox.addWidget(btn_group)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.tab_widget.addTab(ops_tab, '⚙ 训练/验证/预测/导出/视频')

    def _browse_file(self, edit, title):
        path, _ = QFileDialog.getOpenFileName(self, title)
        if path:
            edit.setText(path)

    def _run_yolo_cmd(self, op):
        if not self.env_result or not self.env_result.get('conda_path'):
            QMessageBox.warning(self,'错误','未检测到 Conda')
            return
        env = self.ops_env_combo.currentText()
        if not env or env=='未检测到环境':
            QMessageBox.warning(self,'错误','请选择 Conda 环境')
            return
        model = self.ops_model_edit.text().strip()
        if not model or not os.path.exists(model):
            QMessageBox.warning(self,'错误','请选择有效的模型文件')
            return
        conda_path = self.env_result['conda_path']
        if op=='val':
            data = self.ops_data_edit.text().strip()
            if not data:
                QMessageBox.warning(self,'错误','验证需要 data.yaml')
                return
            cmd = f'yolo val model="{model}" data="{data}"'
        elif op=='predict':
            src = self.ops_source_edit.text().strip()
            if not src:
                QMessageBox.warning(self,'错误','预测需要推理源')
                return
            cmd = f'yolo predict model="{model}" source="{src}"'
        elif op=='export':
            fmt = self.ops_export_format.currentText()
            cmd = f'yolo export model="{model}" format={fmt}'
        elif op=='video':
            src = self.ops_source_edit.text().strip()
            if not src:
                QMessageBox.warning(self,'错误','视频推理需要视频文件')
                return
            cmd = f'yolo predict model="{model}" source="{src}"'
        else:
            return
        self.append_log(f'[{op}] {cmd}')
        self._exec_in_conda(conda_path, env, cmd, op)

    def _exec_in_conda(self, conda_path, env_name, cmd, tag):
        import subprocess
        # 复用训练线程逻辑 简化版
        class OpThread(QThread):
            log_signal = pyqtSignal(str)
            finished_signal = pyqtSignal(bool,str)
            def __init__(self, conda_path, env, cmd):
                super().__init__()
                self.conda_path = conda_path
                self.env = env
                self.cmd = cmd
            def run(self):
                try:
                    # 与训练线程一致：--no-capture-output 输出直通，
                    # UTF-8 环境变量避免中文路径/日志乱码
                    full = f'"{self.conda_path}" run --no-capture-output -n "{self.env}" {self.cmd}'
                    env = os.environ.copy()
                    env['PYTHONUNBUFFERED'] = '1'
                    env['PYTHONIOENCODING'] = 'utf-8'
                    env['PYTHONUTF8'] = '1'
                    proc = subprocess.Popen(full, shell=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, env=env)
                    for line in proc.stdout:
                        self.log_signal.emit(line.rstrip())
                    proc.wait()
                    self.finished_signal.emit(proc.returncode == 0, '完成')
                except Exception as e:
                    self.log_signal.emit(str(e))
                    self.finished_signal.emit(False, str(e))
        thread = OpThread(conda_path, env_name, cmd)
        thread.log_signal.connect(lambda t: self.append_log(f'[{tag}] {t}'))
        thread.finished_signal.connect(lambda ok,msg: self.append_log(f'[{tag}] {"成功" if ok else "失败"}: {msg}'))
        # 持有到线程真正结束后再释放
        self._ops_threads.append(thread)
        thread.finished.connect(
            lambda t=thread: self._ops_threads.remove(t) if t in self._ops_threads else None)
        thread.start()

    def _init_training_tab(self):
        train_tab = QWidget()
        tab_layout = QVBoxLayout(train_tab)
        tab_layout.setContentsMargins(0,0,0,0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)

        config_group = QGroupBox('训练配置')
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1,1)

        env_label = QLabel('Conda 环境:')
        env_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.train_env_combo = QComboBox()
        self.train_env_combo.setMinimumHeight(30)
        envs = self._load_installed_envs()
        for name in envs:
            self.train_env_combo.addItem(name)
        if self.train_env_combo.count()==0:
            self.train_env_combo.addItem('未检测到环境')
        self.train_env_combo.currentIndexChanged.connect(self._on_train_env_changed)

        self.train_refresh_env_btn = QPushButton('↻')
        self.train_refresh_env_btn.setMinimumHeight(30)
        self.train_refresh_env_btn.setMaximumWidth(40)
        self.train_refresh_env_btn.setToolTip('重新扫描 Conda 环境')
        self.train_refresh_env_btn.clicked.connect(self._refresh_conda_env_combos)

        train_env_box = QWidget()
        train_env_layout = QHBoxLayout(train_env_box)
        train_env_layout.setContentsMargins(0, 0, 0, 0)
        train_env_layout.setSpacing(6)
        train_env_layout.addWidget(self.train_env_combo, 1)
        train_env_layout.addWidget(self.train_refresh_env_btn)

        grid.addWidget(env_label,0,0)
        grid.addWidget(train_env_box,0,1,1,3)

        mode_label = QLabel('训练模式:')
        mode_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mode_group = QButtonGroup(self)
        self.mode_basic = QRadioButton('基础模式')
        self.mode_advanced = QRadioButton('高级模式')
        self.mode_basic.setChecked(True)
        mode_group.addButton(self.mode_basic)
        mode_group.addButton(self.mode_advanced)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_basic)
        mode_row.addWidget(self.mode_advanced)
        mode_row.addStretch()
        grid.addWidget(mode_label,1,0)
        mode_widget = QWidget()
        mode_widget.setLayout(mode_row)
        grid.addWidget(mode_widget,1,1,1,3)
        self.mode_basic.toggled.connect(self._on_train_mode_changed)
        self.mode_advanced.toggled.connect(self._on_train_mode_changed)

        dataset_label = QLabel('数据集文件夹:')
        dataset_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        dataset_row = QHBoxLayout()
        self.dataset_edit = QLineEdit()
        self.dataset_edit.setMinimumHeight(30)
        self.dataset_browse_btn = QPushButton('▸')
        self.dataset_browse_btn.setMaximumWidth(40)
        self.dataset_browse_btn.clicked.connect(self._browse_dataset_folder)
        dataset_row.addWidget(self.dataset_edit)
        dataset_row.addWidget(self.dataset_browse_btn)
        dataset_widget = QWidget()
        dataset_widget.setLayout(dataset_row)
        grid.addWidget(dataset_label,2,0)
        grid.addWidget(dataset_widget,2,1,1,3)

        model_label = QLabel('模型大小:')
        model_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(30)
        self.model_combo.addItem('请先选择部署环境')

        self.global_scan_btn = QPushButton('⊙ 全局扫描')
        self.global_scan_btn.setMinimumHeight(30)
        self.global_scan_btn.setMinimumWidth(110)
        self.global_scan_btn.setToolTip('扫描本机所有磁盘，查找以前下载过的 YOLO 权重')
        self.global_scan_btn.clicked.connect(self.start_global_model_scan)

        model_box = QWidget()
        model_box_layout = QHBoxLayout(model_box)
        model_box_layout.setContentsMargins(0, 0, 0, 0)
        model_box_layout.setSpacing(6)
        model_box_layout.addWidget(self.model_combo, 1)
        model_box_layout.addWidget(self.global_scan_btn)

        grid.addWidget(model_label,3,0)
        grid.addWidget(model_box,3,1,1,3)

        workers_label = QLabel('工作线程:')
        workers_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1,32)
        self.workers_spin.setValue(8)
        grid.addWidget(workers_label,4,0)
        grid.addWidget(self.workers_spin,4,1)

        batch_label = QLabel('每批样本数:')
        batch_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1,64)
        self.batch_spin.setValue(16)
        grid.addWidget(batch_label,4,2)
        grid.addWidget(self.batch_spin,4,3)

        epochs_label = QLabel('训练轮数:')
        epochs_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1,1000)
        self.epochs_spin.setValue(100)
        grid.addWidget(epochs_label,5,0)
        grid.addWidget(self.epochs_spin,5,1)

        imgsz_label = QLabel('图片尺寸:')
        imgsz_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(64,1280)
        self.imgsz_spin.setValue(640)
        grid.addWidget(imgsz_label,5,2)
        grid.addWidget(self.imgsz_spin,5,3)

        config_group.setLayout(grid)
        vbox.addWidget(config_group)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.train_start_btn = QPushButton('▶ 开始训练')
        self.train_start_btn.setMinimumHeight(48)
        self.train_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.train_start_btn.setProperty('success', True)
        train_font = QFont('Microsoft YaHei', 13, QFont.Weight.Bold)
        self.train_start_btn.setFont(train_font)
        self.train_start_btn.clicked.connect(self.start_training)

        self.train_stop_btn = QPushButton('■ 结束训练')
        self.train_stop_btn.setMinimumHeight(48)
        self.train_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.train_stop_btn.setProperty('danger', True)
        self.train_stop_btn.setFont(train_font)
        self.train_stop_btn.setEnabled(False)
        self.train_stop_btn.clicked.connect(self.stop_training)

        btn_row.addWidget(self.train_start_btn)
        btn_row.addWidget(self.train_stop_btn)
        vbox.addLayout(btn_row)

        scroll.setWidget(content)
        tab_layout.addWidget(scroll)
        self.tab_widget.addTab(train_tab, '◎ 一键训练')
        self._on_train_mode_changed()
        self._on_train_env_changed(self.train_env_combo.currentIndex())

    def _browse_dataset_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择数据集文件夹')
        if folder:
            self.dataset_edit.setText(folder)

    # ---------- 全局模型扫描 ----------
    def start_global_model_scan(self):
        if getattr(self, '_global_scan_thread', None) and self._global_scan_thread.isRunning():
            return
        self.global_scan_btn.setEnabled(False)
        self.global_scan_btn.setText('↻ 扫描中...')
        self.append_log('🔍 开始全盘扫描 YOLO 模型权重（后台执行，不影响其他操作）...')
        self._gs_last_progress_log = 0.0

        # 传入 conda 根目录用于剪枝（跳过 pkgs/site-packages 等海量文件目录）
        conda_root = ''
        if self.env_result and self.env_result.get('conda_path'):
            conda_root = os.path.dirname(os.path.dirname(self.env_result['conda_path']))

        self._global_scan_thread = _GlobalModelScanWorker(
            extra_skip_prefixes=[conda_root] if conda_root else None)
        self._global_scan_thread.progress.connect(self._on_global_scan_progress)
        self._global_scan_thread.finished_scan.connect(self._on_global_scan_finished)
        self._global_scan_thread.failed.connect(self._on_global_scan_failed)
        self._global_scan_thread.start()

    def _on_global_scan_progress(self, path):
        import time
        now = time.time()
        # 进度日志 5 秒一条，避免刷屏
        if path != '扫描完成' and now - self._gs_last_progress_log >= 5:
            self.append_log(f'   正在扫描: {path}')
            self._gs_last_progress_log = now

    def _on_global_scan_finished(self, models):
        # 先放入内存缓存：即使磁盘保存失败，本次运行也能立即识别扫描结果
        self._global_models_cache = dict(models or {})
        saved_path = self._save_global_models(models)
        if saved_path:
            self.append_log(f'模型缓存已保存: {saved_path}')
        else:
            self.append_log('⚠️ 模型缓存保存失败（不影响本次运行，但重启后需重新扫描）')
        self.global_scan_btn.setEnabled(True)
        self.global_scan_btn.setText('⊙ 全局扫描')

        self.append_log(f'✅ 全盘扫描完成，共找到 {len(models)} 个 YOLO 权重：')
        for name, path in sorted(models.items()):
            self.append_log(f'   {name}  ←  {path}')

        # 说明不属于当前环境系列的模型，避免用户疑惑"为什么下拉框里没有"
        info = getattr(self, '_train_deploy_info', None) or {}
        current_family = info.get('family')
        if current_family and models:
            for fam, names in self._group_models_by_family(models).items():
                if fam != current_family:
                    self.append_log(
                        f'ℹ️ 其中 {", ".join(sorted(names))} 属于 YOLO{fam} 系列，'
                        f'需在"一键部署"页部署 YOLO{fam} 后，在训练页选择该系列环境才能训练')

        # 用新结果刷新当前模型下拉框
        self._on_train_env_changed(self.train_env_combo.currentIndex())

    @staticmethod
    def _group_models_by_family(models):
        """按 YOLO 系列分组模型名 {family: [name, ...]}，未知系列归入 'unknown'。"""
        groups = {}
        for name in models:
            fam = 'unknown'
            for f, list_ in YOLO_FAMILY_MODELS.items():
                if name in list_:
                    fam = f
                    break
            groups.setdefault(fam, []).append(name)
        return groups

    def _on_global_scan_failed(self, msg):
        self.global_scan_btn.setEnabled(True)
        self.global_scan_btn.setText('⊙ 全局扫描')
        self.append_log(f'❌ 全盘扫描失败: {msg}')

    def start_training(self):
        # 部署进行中时忽略训练请求，避免日志串扰
        if self.install_thread is not None and self.install_thread.isRunning():
            return
        if not self.env_result or not self.env_result.get('conda_path'):
            self.append_log('❌ 未检测到 Conda，请先在系统环境检测中确认 conda 路径')
            QMessageBox.warning(self, '错误', '未检测到 Conda')
            return
        env_name = self.train_env_combo.currentText()
        if not env_name or env_name == '未检测到环境':
            self.append_log('❌ 请选择一个 Conda 环境')
            QMessageBox.warning(self, '错误', '请选择 Conda 环境')
            return
        dataset_path = self.dataset_edit.text().strip()
        if not dataset_path or not os.path.exists(dataset_path):
            self.append_log('❌ 请选择有效的数据集文件夹')
            QMessageBox.warning(self, '错误', '数据集文件夹不存在')
            return
        model = self.model_combo.currentText()
        # 解析该环境的部署信息：系列、工作目录、源码目录
        info = self._get_env_deploy_info(env_name)
        family = info.get('family')
        workspace = info.get('workspace', '')
        if not family:
            self.append_log('❌ 无法识别该环境对应的 YOLO 版本，请重新一键部署该环境')
            QMessageBox.warning(self, '错误', '未识别的部署环境')
            return

        # 模型必须是该系列且已真实下载的权重
        if model not in YOLO_FAMILY_MODELS[family]:
            self.append_log(f'❌ 未找到已下载的 {family} 模型权重，请先一键部署（部署时会自动下载模型）')
            QMessageBox.warning(self, '错误', '没有可用的已下载模型')
            return

        # 结果统一保存到 <工作目录>/runs/detect
        if not workspace:
            workspace = os.path.dirname(dataset_path)
        project_dir = os.path.join(workspace, 'runs', 'detect')

        # 源码仓库目录：v5/v7/v9 需要在仓库目录内启动
        repo_cwd = ''
        if info.get('folder_name') and workspace:
            candidate = os.path.join(workspace, info['folder_name'])
            if os.path.isdir(candidate):
                repo_cwd = candidate

        workers = self.workers_spin.value()
        batch = self.batch_spin.value()
        epochs = self.epochs_spin.value()
        imgsz = self.imgsz_spin.value()
        mode = '高级' if self.mode_advanced.isChecked() else '基础'
        self.append_log(f'开始训练: 模式={mode}, 模型={model}, 环境={env_name}')
        self.train_start_btn.setEnabled(False)
        self.train_stop_btn.setEnabled(True)
        self.train_thread = TrainThread(
            self.env_result['conda_path'],
            env_name,
            dataset_path,
            model,
            workers,
            batch,
            epochs,
            imgsz,
            family,
            project_dir,
            repo_cwd=repo_cwd,
            model_path=self._train_model_paths.get(model, '')
        )
        self.train_thread.log_signal.connect(self.append_log)
        self.train_thread.finished_signal.connect(self._on_train_finished)
        self.train_thread.start()

    def stop_training(self):
        if hasattr(self, 'train_thread') and self.train_thread.isRunning():
            self.append_log('正在停止训练...')
            self.train_thread.terminate()
            self.train_thread.wait()
            self.append_log('训练已停止')
        self.train_start_btn.setEnabled(True)
        self.train_stop_btn.setEnabled(False)

    def _on_train_finished(self, success, msg):
        self.append_log(f'{"✅" if success else "❌"} 训练结束: {msg}')
        self.train_start_btn.setEnabled(True)
        self.train_stop_btn.setEnabled(False)

    def _get_env_deploy_info(self, env_name):
        """汇总环境的部署信息：版本名、工作目录、源码文件夹、YOLO 系列。

        数据来源：installed_envs.json 部署记录 + repos.yaml 反查补充。
        """
        installed = self._load_installed_envs()
        record = installed.get(env_name, {})
        version_name = record.get('version_name', '')
        workspace = record.get('workspace', '')
        folder_name = ''

        # repos.yaml 反查
        try:
            config_path = get_resource_path('repos.yaml')
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            for v in config.get('yolo_versions', []):
                if v.get('env_name') == env_name:
                    if not version_name:
                        version_name = v.get('name', '')
                    if not workspace:
                        ws = config.get('workspace_dir', 'yolo_workspace')
                        workspace = os.path.abspath(ws)
                    folder_name = v.get('folder_name', '')
                    break
        except Exception:
            pass

        family = detect_yolo_family(version_name, env_name)
        return {
            'version_name': version_name,
            'workspace': workspace,
            'folder_name': folder_name,
            'family': family,
        }

    def _find_workspace_models(self, info):
        """扫描工作目录，返回该系列中真实存在的 {模型名: 绝对路径}。"""
        family = info.get('family')
        workspace = info.get('workspace', '')
        if not family or not workspace or not os.path.isdir(workspace):
            return {}

        family_models = YOLO_FAMILY_MODELS.get(family)
        if not family_models:
            return {}
        found = {}
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv'}

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if f.lower().endswith('.pt'):
                    stem = os.path.splitext(f)[0]
                    if stem in family_models and stem not in found:
                        found[stem] = os.path.join(root, f)
        return found

    def _collect_train_models(self, info):
        """合并全盘扫描缓存与工作目录，按系列官方顺序返回 [(模型名, 路径)]。"""
        family = info.get('family')
        if not family:
            return []

        order = YOLO_FAMILY_MODELS.get(family)
        if not order:
            return []
        merged = {}

        # 全盘扫描缓存（全局位置，如桌面、下载目录）
        for name, path in self._load_global_models().items():
            if name in order:
                merged[name] = path

        # 工作目录中的实际权重（同名校验以工作目录为准）
        merged.update(self._find_workspace_models(info))

        return [(name, merged[name]) for name in order if name in merged]

    def _on_train_env_changed(self, index):
        if index < 0:
            return
        env_name = self.train_env_combo.itemText(index)

        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        if not env_name or env_name in ('未检测到环境',):
            self.model_combo.addItem('请先选择部署环境')
            self._train_model_paths = {}
            self.model_combo.blockSignals(False)
            return

        info = self._get_env_deploy_info(env_name)
        self._train_deploy_info = info
        family = info.get('family')

        if not family:
            self.model_combo.addItem('未识别的环境，请重新一键部署')
            self._train_model_paths = {}
            self.model_combo.blockSignals(False)
            return

        # 合并全盘扫描结果 + 工作目录中实际存在的该系列权重
        models = self._collect_train_models(info)
        self._train_model_paths = dict(models)
        if models:
            self.model_combo.addItems([name for name, _ in models])
            self.model_combo.setCurrentIndex(0)
        else:
            # 界面构建期间（_ui_ready=False）只放占位，不启动后台线程
            if getattr(self, '_ui_ready', False) and not os.path.exists(self._get_global_models_file()):
                self.model_combo.addItem('未找到已下载模型，正在自动全盘扫描...')
                # 从未全盘扫描过（无缓存文件）时自动后台扫描；已扫过则尊重结果，
                # 用户可手动点“全局扫描”重新查找
                self.append_log('未在工作目录找到该系列模型，'
                                '自动开始全盘扫描以前下载的模型...')
                # 延迟启动，避免与界面切换抢占
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, self.start_global_model_scan)
            else:
                self.model_combo.addItem('未找到已下载模型，请点右侧全局扫描')
        self.model_combo.blockSignals(False)

        # 数据集框为空时自动填充标准路径 <工作目录>/data，避免首次点击误报
        workspace = info.get('workspace', '')
        if workspace and not self.dataset_edit.text().strip():
            default_data = os.path.join(workspace, 'data')
            if os.path.isdir(default_data):
                self.dataset_edit.setText(default_data)

    def _on_train_mode_changed(self):
        is_basic = self.mode_basic.isChecked()
        # 基础模式：隐藏高级控件，模型固定为最小
        self.workers_spin.setVisible(not is_basic)
        self.batch_spin.setVisible(not is_basic)
        self.epochs_spin.setVisible(not is_basic)
        self.imgsz_spin.setVisible(not is_basic)
        # 模型在基础模式下只显示最小且不可修改
        self.model_combo.setEnabled(not is_basic)
        if is_basic:
            # ponytail: 傻瓜模式固定参数
            self.workers_spin.setValue(8)
            self.batch_spin.setValue(16)
            self.epochs_spin.setValue(100)
            self.imgsz_spin.setValue(640)
            if self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
        # 保持模型列表与当前环境一致
        self._on_train_env_changed(self.train_env_combo.currentIndex())

    def _refresh_annotation_envs(self):
        if not self.env_result or not self.env_result['conda_path']:
            self.anno_env_label.setText('❌ 未检测到 Conda，请先在「一键部署」页面安装环境')
            self.anno_env_label.setStyleSheet('color: red;')
            self.refresh_anno_btn.setEnabled(True)
            return

        if self._anno_scan_thread and self._anno_scan_thread.isRunning():
            return

        self.anno_env_label.setText('⊙ 正在检测已安装环境...')
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

        is_repair = (self._relaunch_after_repair == tool_name)
        action = '修复' if is_repair else (
            '安装' if self._anno_install_thread and self._anno_install_thread.is_install
            else '操作')
        if success:
            self.anno_install_status.setText(f'✅ {tool_name} {action}成功')
            self.anno_install_status.setStyleSheet('color: green; font-size: 11px;')
            self._refresh_annotation_envs()
            # 修复成功 → 自动重启该工具
            if is_repair:
                self._relaunch_after_repair = None
                self.append_log(f'🔧 {tool_name} 修复完成，自动重启...')
                self._launch_annotation_tool(tool_name)
        else:
            self._relaunch_after_repair = None
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
        conda.get_python_path(env_name)

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
        if tool_name in self._anno_running:
            QMessageBox.information(
                self, '提示', f'{tool_name} 已经在运行中，请勿重复启动。')
            return
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

            # 日志文件：<运行目录>/logs/<工具>_<时间戳>.log
            from modules.platform_utils import get_runtime_dir
            import datetime
            log_dir = os.path.join(get_runtime_dir(), 'logs')
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                log_dir = os.path.expanduser('~')
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            tool_log = os.path.join(log_dir, f'{tool_name}_{ts}.log')

            self.append_log(f'📄 运行日志: {tool_log}')

            watcher = AnnotationCrashWatchThread(cmd, env, tool_log)
            watcher.started_ok.connect(
                lambda pid: self._on_anno_started_ok(tool_name, pid))
            watcher.start_failed.connect(
                lambda rc, tail: self._on_anno_start_failed(
                    tool_name, env_name, rc, tail))
            watcher.crashed.connect(
                lambda rc, tail, lp: self._on_anno_crashed(
                    tool_name, env_name, rc, tail, lp))
            watcher.normal_exit.connect(
                lambda tn=tool_name: (
                    self._anno_running.discard(tn),
                    self.append_log(f'ℹ️ {tn} 已正常关闭')))
            watcher.finished.connect(
                lambda w=watcher: self._remove_anno_watcher(w))
            self._anno_watchers.append(watcher)
            self._anno_running.add(tool_name)
            watcher.start()

        except Exception as e:
            self.append_log(f'❌ 启动 {tool_name} 失败: {e}')
            import traceback
            self.append_log(traceback.format_exc())
            QMessageBox.critical(self, '启动失败', f'启动 {tool_name} 失败:\n{e}')

    # ---- 标注工具守护信号处理 ----

    def _remove_anno_watcher(self, watcher):
        try:
            self._anno_watchers.remove(watcher)
        except ValueError:
            pass

    def _on_anno_started_ok(self, tool_name, pid):
        self.append_log(f'✅ {tool_name} 已启动 (PID: {pid})，如无窗口请查看任务栏')

    @staticmethod
    def _anno_diagnosis(error_msg):
        """根据错误文本返回 (病因说明, 是否可自动修复)。"""
        low = error_msg.lower()
        if 'cv2/qt/plugins' in error_msg or (
                'opencv' in low and ('qt' in low or 'plugin' in low)):
            return ('OpenCV 自带的 Qt 插件与 PyQt 冲突', True)
        if 'xcb' in low and ('could not load' in low or 'failed' in low
                             or 'plugin' in low):
            return ('Qt 平台插件 xcb 加载失败（系统库缺失或损坏）', True)
        if 'wayland' in low:
            return ('Wayland 显示服务器兼容性问题', True)
        if 'numpy' in low and 'has no attribute' in low:
            return ('numpy 2.x 与旧版工具不兼容', True)
        if 'unicode' in low or 'codec' in low or 'gbk' in low:
            return ('路径或文件名编码问题（中文/特殊字符）', False)
        if 'no module' in low or 'importerror' in low:
            return ('依赖组件缺失或安装不完整', True)
        return ('未识别的错误，请查看完整日志', False)

    def _on_anno_start_failed(self, tool_name, env_name, rc, tail):
        self._anno_running.discard(tool_name)
        self.append_log(f'❌ {tool_name} 启动失败，返回码: {rc}')
        cause, can_repair = self._anno_diagnosis(tail)
        self.append_log(f'   病因: {cause}')

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle('启动失败')
        box.setText(f'{tool_name} 启动失败\n\n病因：{cause}\n\n'
                    f'日志尾部：\n{tail[-600:]}')
        repair_btn = None
        if can_repair:
            repair_btn = box.addButton('🔧 自动修复',
                                       QMessageBox.ButtonRole.AcceptRole)
        box.addButton('关闭', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if repair_btn is not None and box.clickedButton() is repair_btn:
            self._repair_annotation_tool(tool_name, env_name)

    def _on_anno_crashed(self, tool_name, env_name, rc, tail, log_path):
        self._anno_running.discard(tool_name)
        self.append_log(f'💥 {tool_name} 运行中意外退出，返回码: {rc}')
        cause, can_repair = self._anno_diagnosis(tail)
        self.append_log(f'   病因: {cause} | 日志: {log_path}')

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle('标注工具已崩溃')
        box.setText(f'{tool_name} 在标注过程中意外关闭。\n\n'
                    f'可能病因：{cause}\n\n'
                    f'日志文件：{log_path}\n\n'
                    f'日志尾部：\n{tail[-600:]}')
        repair_btn = None
        if can_repair:
            repair_btn = box.addButton('🔧 自动修复并重启',
                                       QMessageBox.ButtonRole.AcceptRole)
        box.addButton('关闭', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if repair_btn is not None and box.clickedButton() is repair_btn:
            self._relaunch_after_repair = tool_name
            self._repair_annotation_tool(tool_name, env_name)

    def _repair_annotation_tool(self, tool_name, env_name):
        if self._anno_install_thread and self._anno_install_thread.isRunning():
            QMessageBox.warning(self, '提示', '已有修复任务在执行，请稍候。')
            return
        self.append_log(f'🔧 开始修复 {tool_name}（强制重装 + 兼容性加固）...')
        self._set_anno_buttons_enabled(False)
        self.anno_install_status.setText(f'⏳ 正在修复 {tool_name}...')
        self.anno_install_status.setStyleSheet(
            'color: #1976D2; font-size: 11px;')
        self._anno_install_thread = AnnotationToolInstallThread(
            self.env_result['conda_path'], env_name, tool_name,
            True, force_reinstall=True)
        self._anno_install_thread.log_signal.connect(self.append_log)
        self._anno_install_thread.finished_signal.connect(
            self._on_anno_tool_install_finished)
        self._anno_install_thread.start()

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
        self._refresh_conda_env_combos()
        # conda 就绪后显式联动一次训练页（填充数据集路径/模型列表）
        idx = self.train_env_combo.currentIndex()
        if idx >= 0:
            self._on_train_env_changed(idx)

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
            self.all_pytorch_versions = list(pytorch_versions)
            self._refresh_pytorch_combo()

            annotation_tools = config.get('annotation_tools', [])
            for tool in annotation_tools:
                self.annotation_combo.addItem(tool['name'], tool.get('pkg_name', ''))

            if self.version_combo.count() > 0:
                self._on_version_changed(0)

        except Exception as e:
            self.append_log(f'[错误] 加载版本配置失败: {e}')

    def _torch_supports_python(self, torch_ver, py_ver):
        # 'latest' 不锁版本，pip 会自动选择与当前 Python 兼容的最新版本
        if not torch_ver or torch_ver == 'latest':
            return True
        try:
            t_parts = torch_ver.split('.')
            torch_major, torch_minor = int(t_parts[0]), int(t_parts[1])
            py_parts = str(py_ver).split('.')
            py_major, py_minor = int(py_parts[0]), int(py_parts[1])
        except Exception:
            return True
        # PyTorch 2.5+ 要求 Python >= 3.9，不再支持 Python 3.8
        if (torch_major, torch_minor) >= (2, 5) and (py_major, py_minor) < (3, 9):
            return False
        return True

    def _refresh_pytorch_combo(self):
        py_ver = self.python_combo.currentData()
        all_versions = getattr(self, 'all_pytorch_versions', ['latest', '2.5.1', '2.4.1'])
        previous = self.pytorch_combo.currentData()

        self.pytorch_combo.blockSignals(True)
        self.pytorch_combo.clear()
        for v in all_versions:
            if self._torch_supports_python(v, py_ver):
                self.pytorch_combo.addItem(v, v)
        self.pytorch_combo.blockSignals(False)

        # 尽量保留原选择；原选择不兼容时自动选第一项
        keep_index = self.pytorch_combo.findData(previous)
        if keep_index >= 0:
            self.pytorch_combo.setCurrentIndex(keep_index)

    def _on_python_changed(self, index):
        if index < 0:
            return
        self._refresh_pytorch_combo()

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

        self._update_deploy_model_sizes(version_info)

    def _update_deploy_model_sizes(self, version_info):
        name = version_info.get('name','').lower()
        # 根据官网模型大小列表
        sizes = []
        if 'v5' in name:
            sizes = ['n','s','m','l','x']
        elif 'v8' in name or 'v11' in name:
            sizes = ['n','s','m','l','x']
        elif 'v7' in name:
            sizes = ['n','s','m','x']  # v7 常见
        elif 'v9' in name:
            sizes = ['n','s','m','l','x']
        elif 'v10' in name:
            sizes = ['n','s','m','l','x']
        else:
            sizes = ['n','s','m','l','x']
        self.deploy_model_combo.blockSignals(True)
        self.deploy_model_combo.clear()
        self.deploy_model_combo.addItems(sizes)
        if sizes:
            self.deploy_model_combo.setCurrentIndex(0)
        self.deploy_model_combo.blockSignals(False)

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
        import re
        text = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
        text = re.sub(r'\r', '', text)
        text = text.strip()
        if not text:
            return
        self._log_lines.append(text)
        # 初始化早期日志控件可能还未创建，先缓存到 _log_lines，不报错
        if not hasattr(self, 'log_text'):
            return
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
        self.progress_widget.show()
        self.progress_bar.show()
        self.progress_label.setText('正在安装环境...')
        self.progress_label.show()
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
        self.progress_widget.hide()
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
        self.progress_widget.show()
        self.progress_bar.show()
        self.progress_label.setText('正在部署...')
        self.progress_label.show()
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
        self.install_thread.download_progress_signal.connect(self._on_download_progress)
        self.install_thread.start()

    def _on_download_progress(self, current, total, filename):
        """处理下载进度信号：更新进度条、标签、下载速度与预计剩余时间。

        界面刷新节流为约 1 秒一次，避免过度刷新。
        """
        import time as _time
        now = _time.monotonic()

        # 新文件开始下载时重置采样
        if getattr(self, '_dl_name', None) != filename:
            self._dl_name = filename
            self._dl_prev_ts = None
            self._dl_prev_bytes = 0
            self._dl_ui_ts = 0.0

        finished = bool(total) and current >= total
        last_ui = getattr(self, '_dl_ui_ts', 0.0)
        if not finished and now - last_ui < 1.0:
            return
        self._dl_ui_ts = now

        # 估算速度与剩余时间
        speed = 0.0
        prev_ts = getattr(self, '_dl_prev_ts', None)
        prev_bytes = getattr(self, '_dl_prev_bytes', 0)
        if prev_ts is not None and now > prev_ts and current >= prev_bytes:
            speed = (current - prev_bytes) / (now - prev_ts)
        self._dl_prev_ts = now
        self._dl_prev_bytes = current

        if total > 0:
            pct = int(current * 100 / total)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            text = f'正在下载 {filename}: {pct}% ({current_mb:.1f}/{total_mb:.1f} MB)'
            if speed > 0:
                remain = (total - current) / speed
                text += f'  {speed / (1024 * 1024):.1f} MB/s，预计剩余 {self._fmt_duration(remain)}'
            elif not finished:
                text += '  正在估算速度...'
            self.progress_label.setText(text)
        else:
            self.progress_bar.setRange(0, 0)
            current_mb = current / (1024 * 1024)
            text = f'正在下载 {filename}: {current_mb:.1f} MB'
            if speed > 0:
                text += f'  {speed / (1024 * 1024):.1f} MB/s'
            self.progress_label.setText(text)
        # 确保进度区域可见
        if not self.progress_widget.isVisible():
            self.progress_widget.show()
            self.progress_bar.show()
            self.progress_label.show()

    @staticmethod
    def _fmt_duration(seconds):
        """秒数格式化为 mm:ss 或 hh:mm:ss"""
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f'{h}:{m:02d}:{s:02d}'
        return f'{m:02d}:{s:02d}'

    def _on_step(self, step_name):
        self.setWindowTitle(f'YOLO 全版本一键部署工具 - [{step_name}]')
        self.progress_label.setText(f'当前步骤: {step_name}')
        self.progress_label.show()

    def _on_install_finished(self, success, message):
        self.progress_widget.hide()
        self._set_controls_enabled(True)
        self.setWindowTitle('YOLO 全版本一键部署工具')
        # 若当前处于托盘后台模式，自动恢复主窗口
        if getattr(self, '_tray_icon', None) is not None and self.isHidden():
            self._restore_from_tray()

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
                self._refresh_conda_env_combos()

                # 一键训练页数据集文件夹默认指向刚创建的 data 目录（不覆盖用户已选路径）
                default_data_dir = os.path.join(workspace, 'data')
                if workspace and os.path.isdir(default_data_dir) and not self.dataset_edit.text().strip():
                    self.dataset_edit.setText(default_data_dir)

            QMessageBox.information(self, '完成', final_msg)
        else:
            final_msg = message
            final_msg += '\n\n💡 部署进度已保存，下次打开程序时可选择从中断处继续。'
            if log_file:
                final_msg += f'\n\n详细日志已保存至:\n{log_file}'
            QMessageBox.critical(self, '失败', final_msg)

    # ---------- 关闭保护 / 后台托盘 ----------

    def closeEvent(self, event):
        """关闭窗口时：若有任务进行中，给出「后台继续 / 保留进度退出 / 取消」选择。"""
        deploy_busy = bool(self.install_thread and self.install_thread.isRunning())
        env_busy = bool(self.env_install_thread and self.env_install_thread.isRunning())
        training_busy = bool(
            getattr(self, 'train_thread', None) and self.train_thread.isRunning())
        repair_busy = bool(self._anno_install_thread
                          and self._anno_install_thread.isRunning())

        if not (deploy_busy or env_busy or training_busy or repair_busy):
            self._stop_anno_watchers()
            event.accept()
            return

        dlg = CloseConfirmDialog(
            deploy_busy=deploy_busy or repair_busy, env_busy=env_busy,
            training_busy=training_busy, parent=self)
        dlg.exec()

        if dlg.choice == CloseConfirmDialog.BACKGROUND:
            event.ignore()
            self._minimize_to_tray()
        elif dlg.choice == CloseConfirmDialog.CLOSE_KEEP:
            if repair_busy:
                # 修复执行中退出会销毁 QThread 导致硬崩溃，阻止关闭
                QMessageBox.information(
                    self, '请稍候',
                    '标注工具正在修复中，请等待修复完成后再关闭（约 1 分钟）。')
                event.ignore()
                return
            # 安全停止守护线程；标注工具子进程继续独立运行
            self._stop_anno_watchers()
            # 进度已通过状态文件持续保存，直接退出即可
            if deploy_busy:
                self.append_log('程序已关闭，部署进度已保存，下次启动可继续')
            event.accept()
        else:
            event.ignore()

    def _stop_anno_watchers(self):
        """中断并等待全部标注守护线程结束，避免 QThread 运行中被销毁而崩溃。"""
        for w in list(self._anno_watchers):
            w.requestInterruption()
        for w in list(self._anno_watchers):
            if not w.wait(2000):
                self.append_log('⚠️ 标注守护线程未能在 2 秒内结束，继续等待...')
                w.wait(3000)

    def _minimize_to_tray(self):
        """隐藏主窗口到系统托盘，任务在后台继续执行。"""
        app = QApplication.instance()
        if app:
            app.setQuitOnLastWindowClosed(False)

        if QSystemTrayIcon.isSystemTrayAvailable():
            if getattr(self, '_tray_icon', None) is None:
                self._tray_icon = QSystemTrayIcon(self.windowIcon(), self)
                menu = QMenu()
                act_show = menu.addAction('打开主窗口')
                act_show.triggered.connect(self._restore_from_tray)
                act_quit = menu.addAction('退出')
                act_quit.triggered.connect(self._tray_quit)
                self._tray_icon.setContextMenu(menu)
                self._tray_icon.activated.connect(self._on_tray_activated)
            self._tray_icon.setToolTip('YOLO 部署工具 - 任务进行中')
            self._tray_icon.show()
            self.hide()
            self._tray_icon.showMessage(
                'YOLO 部署工具',
                '任务正在后台继续执行，完成后窗口将自动恢复。\n双击托盘图标可随时查看进度。',
                QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            # 无系统托盘时退化为最小化到任务栏
            self.showMinimized()
            self.append_log('系统托盘不可用，已最小化到任务栏，任务继续执行')

    def _restore_from_tray(self):
        """从托盘恢复主窗口。"""
        self.showNormal()
        self.activateWindow()
        self.raise_()
        app = QApplication.instance()
        if app:
            app.setQuitOnLastWindowClosed(True)
        if getattr(self, '_tray_icon', None) is not None:
            self._tray_icon.hide()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _tray_quit(self):
        """托盘菜单退出：恢复窗口并走正常关闭流程（含关闭确认）。"""
        self._restore_from_tray()
        self.close()

    def _get_installed_envs_file(self):
        return os.path.join(get_runtime_dir(), 'installed_envs.json')

    def _get_global_models_file(self):
        return os.path.join(get_runtime_dir(), 'global_models.json')

    def _get_global_models_fallback_file(self):
        """ exe 所在目录不可写时的兜底缓存位置（%APPDATA%）。"""
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
        return os.path.join(appdata, 'YOLO_AutoInstaller', 'global_models.json')

    def _load_global_models(self):
        """读取全盘扫描缓存，返回 {模型名: 绝对路径}；记录中的文件已删除则剔除。

        兼容两种历史格式：
        1) {'scan_time': ..., 'models': {name: path}}
        2) 直接保存 {name: path}
        并合并本次运行扫描得到的内存缓存，避免磁盘保存失败导致下拉框为空。
        """
        models = {}
        for file_path in (self._get_global_models_file(), self._get_global_models_fallback_file()):
            if not file_path or not os.path.exists(file_path):
                continue
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    raw = data.get('models')
                    if not isinstance(raw, dict):
                        raw = {k: v for k, v in data.items() if isinstance(v, str)}
                    models.update(raw)
                break
            except Exception:
                continue

        cache = getattr(self, '_global_models_cache', None)
        if cache:
            models.update(cache)

        return {name: path for name, path in models.items() if path and os.path.exists(path)}

    def _save_global_models(self, models):
        """保存模型缓存，返回实际保存路径；都失败返回 None。"""
        import json
        import time
        data = {
            'scan_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'models': models,
        }
        candidates = [self._get_global_models_file(), self._get_global_models_fallback_file()]
        for file_path in candidates:
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return file_path
            except Exception:
                continue
        return None

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

    def _collect_env_names(self, scan_conda=True):
        """汇总环境名称：本程序部署记录优先，合并 Conda 实际环境（排除 base）。

        scan_conda=False 时仅读取本地部署记录（无额外进程开销，用于 tab 切换）。
        """
        names = []
        seen = set()

        saved = self._load_installed_envs()
        for name in saved:
            if name and name not in seen:
                names.append(name)
                seen.add(name)

        if scan_conda and self.env_result and self.env_result.get('conda_path'):
            try:
                conda = CondaHandler(self.env_result['conda_path'])
                for e in conda.list_envs():
                    n = e.get('name', '')
                    if n and n != 'base' and n not in seen:
                        names.append(n)
                        seen.add(n)
            except Exception:
                pass

        return names

    def _refresh_conda_env_combos(self, scan_conda=True):
        names = self._collect_env_names(scan_conda=scan_conda)

        for combo in (self.ops_env_combo, self.train_env_combo):
            previous = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            if names:
                combo.addItems(names)
                keep = combo.findText(previous)
                if keep >= 0:
                    combo.setCurrentIndex(keep)
            else:
                combo.addItem('未检测到环境')
            combo.blockSignals(False)

        # 同步一键训练页的环境信息显示
        self._on_train_env_changed(self.train_env_combo.currentIndex())

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
                'YOLO 部署日志',
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

    def _open_env_manager(self):
        if not self.env_result or not self.env_result.get('conda_path'):
            QMessageBox.warning(self, '提示', '尚未检测到 Conda，请先完成系统环境扫描。')
            return
        try:
            conda = CondaHandler(self.env_result['conda_path'])
        except Exception as e:
            QMessageBox.warning(self, '错误', f'无法连接 Conda：{e}')
            return

        dialog = EnvManagerDialog(conda, self)
        dialog.exec()

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
        self.manage_env_btn.setEnabled(enabled)
        self.install_btn.setEnabled(enabled)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
