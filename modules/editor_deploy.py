import os
import subprocess
import json
import glob
from .platform_utils import (
    get_vscode_search_paths, get_pycharm_search_patterns,
    has_registry_support, is_windows
)


def detect_editors():
    editors = {}

    vscode_paths = get_vscode_search_paths()
    for path in vscode_paths:
        if os.path.exists(path):
            editors['vscode'] = {
                'name': 'Visual Studio Code',
                'path': path,
                'icon': '📝'
            }
            break

    if 'vscode' not in editors:
        try:
            if is_windows():
                result = subprocess.run(['where', 'code'], capture_output=True, text=True)
            else:
                result = subprocess.run(['which', 'code'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                code_path = result.stdout.strip().split('\n')[0]
                if os.path.exists(code_path):
                    editors['vscode'] = {
                        'name': 'Visual Studio Code',
                        'path': code_path,
                        'icon': '📝'
                    }
        except Exception:
            pass

    pycharm_patterns = get_pycharm_search_patterns()
    for pattern in pycharm_patterns:
        matches = glob.glob(pattern)
        if matches:
            editors['pycharm'] = {
                'name': 'PyCharm',
                'path': matches[0],
                'icon': '🐍'
            }
            break

    if has_registry_support() and ('vscode' not in editors or 'pycharm' not in editors):
        try:
            import winreg
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
                )
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            display_name, _ = winreg.QueryValueEx(subkey, 'DisplayName')
                            install_location, _ = winreg.QueryValueEx(subkey, 'InstallLocation')
                            if 'Visual Studio Code' in display_name and 'vscode' not in editors:
                                code_exe = os.path.join(install_location, 'Code.exe')
                                if os.path.exists(code_exe):
                                    editors['vscode'] = {
                                        'name': 'Visual Studio Code',
                                        'path': code_exe,
                                        'icon': '📝'
                                    }
                            if 'PyCharm' in display_name and 'pycharm' not in editors:
                                bin_dir = os.path.join(install_location, 'bin')
                                if os.path.exists(bin_dir):
                                    for f in os.listdir(bin_dir):
                                        if f.startswith('pycharm') and f.endswith('64.exe'):
                                            editors['pycharm'] = {
                                                'name': 'PyCharm',
                                                'path': os.path.join(bin_dir, f),
                                                'icon': '🐍'
                                            }
                                            break
                        except Exception:
                            pass
                        winreg.CloseKey(subkey)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except Exception:
                pass
        except Exception:
            pass

    return editors


def configure_vscode(project_path, python_path, env_name=''):
    if not project_path or not os.path.exists(project_path):
        yield {'type': 'error', 'message': f'项目路径不存在: {project_path}'}
        return

    vscode_dir = os.path.join(project_path, '.vscode')
    os.makedirs(vscode_dir, exist_ok=True)

    settings_path = os.path.join(vscode_dir, 'settings.json')
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception:
            settings = {}

    settings['python.defaultInterpreterPath'] = python_path
    settings['python.terminal.activateEnvironment'] = True
    settings['python.terminal.activateEnvInCurrentTerminal'] = True
    settings['python.analysis.extraPaths'] = [project_path]
    settings['terminal.integrated.defaultProfile.linux'] = 'bash'
    settings['files.autoSave'] = 'afterDelay'
    settings['files.autoSaveDelay'] = 1000

    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        yield {'type': 'success', 'message': f'✅ 已写入 VSCode 配置: .vscode/settings.json'}
    except Exception as e:
        yield {'type': 'error', 'message': f'❌ 写入配置失败: {e}'}
        return

    launch_path = os.path.join(vscode_dir, 'launch.json')
    if not os.path.exists(launch_path):
        launch_config = {
            'version': '0.2.0',
            'configurations': [
                {
                    'name': 'Python: YOLO 调试',
                    'type': 'python',
                    'request': 'launch',
                    'program': '${file}',
                    'console': 'integratedTerminal',
                    'justMyCode': True,
                    'cwd': '${workspaceFolder}',
                    'env': {
                        'PYTHONIOENCODING': 'utf-8',
                        'PYTHONUTF8': '1'
                    }
                }
            ]
        }
        try:
            with open(launch_path, 'w', encoding='utf-8') as f:
                json.dump(launch_config, f, ensure_ascii=False, indent=4)
            yield {'type': 'success', 'message': '✅ 已创建调试配置: .vscode/launch.json'}
        except Exception as e:
            yield {'type': 'warning', 'message': f'⚠️  创建调试配置失败: {e}'}

    yield {'type': 'success', 'message': f'✅ VSCode 环境配置完成！\n   Python 解释器: {python_path}'}


def open_in_vscode(project_path, vscode_path):
    try:
        subprocess.Popen([vscode_path, project_path])
        return True, ''
    except Exception as e:
        return False, str(e)


def configure_pycharm(project_path, python_path, env_name=''):
    yield {'type': 'info', 'message': 'ℹ️  PyCharm 环境配置说明：'}
    yield {'type': 'info', 'message': ''}
    yield {'type': 'info', 'message': 'PyCharm 的 Python 解释器配置需要手动设置：'}
    yield {'type': 'info', 'message': ''}
    yield {'type': 'info', 'message': '方法一：首次打开项目时配置'}
    yield {'type': 'info', 'message': '  1. 点击下方「在 PyCharm 中打开」按钮'}
    yield {'type': 'info', 'message': '  2. PyCharm 打开项目后'}
    yield {'type': 'info', 'message': '  3. 右下角点击 Python 解释器版本号'}
    yield {'type': 'info', 'message': '  4. 选择「Add New Interpreter」→「Add Local Interpreter」'}
    yield {'type': 'info', 'message': '  5. 选择「Conda Environment」'}
    yield {'type': 'info', 'message': f'  6. 选择环境: {env_name}'}
    yield {'type': 'info', 'message': ''}
    yield {'type': 'info', 'message': f'Python 解释器路径: {python_path}'}

    # 尝试自动创建 .idea 配置
    idea_dir = os.path.join(project_path, '.idea')
    try:
        os.makedirs(idea_dir, exist_ok=True)

        # 创建 misc.xml（项目配置）
        misc_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectRootManager" version="2" project-jdk-name="Python 3 ({env_name})" project-jdk-type="Python SDK">
    <output url="file://$PROJECT_DIR$/out" />
  </component>
</project>
'''
        misc_path = os.path.join(idea_dir, 'misc.xml')
        if not os.path.exists(misc_path):
            with open(misc_path, 'w', encoding='utf-8') as f:
                f.write(misc_xml)
            yield {'type': 'success', 'message': '✅ 已创建 PyCharm 项目配置: .idea/misc.xml'}

        # 创建 modules.xml
        module_name = os.path.basename(project_path)
        modules_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectModuleManager">
    <modules>
      <module fileurl="file://$PROJECT_DIR$/.idea/{module_name}.iml" filepath="$PROJECT_DIR$/.idea/{module_name}.iml" />
    </modules>
  </component>
</project>
'''
        modules_path = os.path.join(idea_dir, 'modules.xml')
        if not os.path.exists(modules_path):
            with open(modules_path, 'w', encoding='utf-8') as f:
                f.write(modules_xml)
            yield {'type': 'success', 'message': '✅ 已创建模块配置: .idea/modules.xml'}

        # 创建 .iml 文件
        iml_path = os.path.join(idea_dir, f'{module_name}.iml')
        if not os.path.exists(iml_path):
            iml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<module type="PYTHON_MODULE" version="4">
  <component name="NewModuleRootManager">
    <content url="file://$MODULE_DIR$">
      <sourceFolder url="file://$MODULE_DIR$" isTestSource="false" />
      <excludeFolder url="file://$MODULE_DIR$/__pycache__" />
      <excludeFolder url="file://$MODULE_DIR$/.pytest_cache" />
    </content>
    <orderEntry type="inheritedJdk" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
</module>
'''
            with open(iml_path, 'w', encoding='utf-8') as f:
                f.write(iml_content)
            yield {'type': 'success', 'message': f'✅ 已创建模块文件: .idea/{module_name}.iml'}

        # 创建 workspace.xml（记录解释器路径提示）
        workspace_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="PythonCompatibilityInspectionAdvertiser">
    <option name="version" value="3" />
  </component>
</project>
'''
        workspace_path = os.path.join(idea_dir, 'workspace.xml')
        if not os.path.exists(workspace_path):
            with open(workspace_path, 'w', encoding='utf-8') as f:
                f.write(workspace_xml)

    except Exception as e:
        yield {'type': 'warning', 'message': f'⚠️  创建 PyCharm 配置文件失败: {e}'}
        yield {'type': 'info', 'message': '   （不影响使用，手动配置即可）'}

    yield {'type': 'success', 'message': '✅ 配置信息已准备好，请按照上述步骤操作'}


def open_in_pycharm(project_path, pycharm_path):
    try:
        subprocess.Popen([pycharm_path, project_path])
        return True, ''
    except Exception as e:
        return False, str(e)
