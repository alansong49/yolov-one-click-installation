import os
import sys
import base64


TEST_IMAGE_BASE64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


class AutoTester:
    def __init__(self, conda_handler, workspace_dir='yolo_workspace'):
        self.conda = conda_handler
        self.workspace_dir = os.path.abspath(workspace_dir)

    def _log(self, line):
        yield {'type': 'log', 'log': line}

    def _step(self, step_name):
        yield {'type': 'step', 'step': step_name, 'log': f'=== {step_name} ==='}

    def _create_test_image(self):
        try:
            from PIL import Image
            import io
            img = Image.new('RGB', (640, 480), color=(73, 109, 137))
            test_img_path = os.path.join(self.workspace_dir, 'test_image.jpg')
            img.save(test_img_path, 'JPEG')
            return test_img_path
        except ImportError:
            pass

        try:
            test_img_path = os.path.join(self.workspace_dir, 'test_image.png')
            img_data = base64.b64decode(TEST_IMAGE_BASE64)
            os.makedirs(self.workspace_dir, exist_ok=True)
            with open(test_img_path, 'wb') as f:
                f.write(img_data)
            return test_img_path
        except Exception:
            return None

    def run_test(self, version_info):
        mode = version_info.get('mode')
        env_name = version_info.get('env_name')

        yield from self._step('开始自动化测试')

        if mode == 'source':
            yield from self._test_source(version_info, env_name)
        elif mode == 'pip':
            yield from self._test_pip(version_info, env_name)
        else:
            yield {'type': 'error', 'log': f'未知模式: {mode}'}
            return

    def _test_source(self, version_info, env_name):
        folder_name = version_info.get('folder_name')
        repo_path = os.path.join(self.workspace_dir, folder_name)
        install_method = version_info.get('install_method', 'requirements')

        detect_candidates = [
            os.path.join(repo_path, 'detect.py'),
            os.path.join(repo_path, 'predict.py'),
            os.path.join(repo_path, 'tools', 'detect.py'),
            os.path.join(repo_path, 'tools', 'predict.py'),
            os.path.join(repo_path, 'yolov10', 'detect.py'),
        ]

        detect_script = None
        for candidate in detect_candidates:
            if os.path.exists(candidate):
                detect_script = candidate
                break

        if install_method == 'editable':
            yield from self._test_ultralytics_source(version_info, env_name, repo_path)
        elif detect_script:
            yield from self._test_detect_script(version_info, env_name, detect_script)
        else:
            yield from self._log(f'未找到检测脚本 (detect.py/predict.py)，测试基础环境...')
            yield from self._test_basic_env(env_name, version_info)

    def _test_basic_env(self, env_name, version_info):
        yield from self._log('正在测试 PyTorch 和基础依赖...')

        test_code = '''
import sys
try:
    import torch
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU count: {torch.cuda.device_count()}")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
    import cv2
    print(f"OpenCV version: {cv2.__version__}")
    import numpy
    print(f"NumPy version: {numpy.__version__}")
    print("Basic environment test PASSED!")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"TestError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        test_script_path = os.path.join(self.workspace_dir, '_auto_test_basic.py')
        os.makedirs(self.workspace_dir, exist_ok=True)
        with open(test_script_path, 'w', encoding='utf-8') as f:
            f.write(test_code)

        test_success = True
        error_type = 'unknown'

        for line in self.conda.run_in_env(env_name, f'python "{test_script_path}"'):
            yield from self._log(line)
            if 'ImportError' in line or 'TestError' in line or 'No module named' in line:
                test_success = False
                if 'No module named' in line or 'ImportError' in line:
                    error_type = 'missing_module'
                if 'CUDA' in line or 'cuda' in line:
                    error_type = 'cuda_error'

        try:
            os.remove(test_script_path)
        except:
            pass

        if test_success:
            yield {'type': 'success', 'log': '环境测试通过！基础依赖（PyTorch/OpenCV/NumPy）可以正常加载'}
        else:
            error_msgs = {
                'missing_module': '环境测试失败：存在缺失的模块，请检查依赖安装',
                'cuda_error': '环境测试失败：CUDA 相关错误，请检查显卡驱动',
                'unknown': '环境测试失败：未知错误，请查看上方日志'
            }
            yield {'type': 'error', 'log': error_msgs.get(error_type, error_msgs['unknown'])}

    def _test_detect_script(self, version_info, env_name, detect_script):
        test_img = self._create_test_image()
        if not test_img:
            yield from self._log('无法创建测试图片，跳过测试')
            yield {'type': 'warning', 'log': '跳过测试：无法创建测试图片'}
            return

        test_weight = version_info.get('test_weight', 'yolov5s.pt')

        yield from self._log(f'测试图片: {test_img}')
        yield from self._log(f'测试权重: {test_weight}')
        yield from self._log('正在运行 detect.py 进行推理测试...')

        cmd = f'python "{detect_script}" --source "{test_img}" --weights {test_weight} --nosave'
        test_success = True
        error_type = 'unknown'
        full_output = []

        for line in self.conda.run_in_env(env_name, cmd):
            yield from self._log(line)
            full_output.append(line)
            if '[错误]' in line or 'ModuleNotFoundError' in line or 'ImportError' in line:
                test_success = False
                if 'ModuleNotFoundError' in line:
                    error_type = 'missing_module'
                elif 'CUDA' in line or 'cuda' in line:
                    error_type = 'cuda_error'
            if 'error' in line.lower() and 'erro' not in line.lower():
                test_success = False

        if not test_success:
            output_text = '\n'.join(full_output)
            download_error_keywords = [
                'Failed to download',
                'FileNotFoundError',
                'attempt_download',
                'google_utils',
                'git tag',
                'CalledProcessError',
                'No such file or directory',
                '找不到文件',
            ]
            is_download_error = any(kw in output_text for kw in download_error_keywords)
            is_module_error = 'ModuleNotFoundError' in output_text or 'No module named' in output_text

            if is_download_error and not is_module_error:
                yield from self._log('')
                yield from self._log('⚠️  权重文件下载失败，正在进行基础环境测试...')
                yield from self._test_basic_env(env_name, version_info)
                return

        if test_success:
            yield {'type': 'success', 'log': '环境测试通过！YOLO 可以正常运行推理'}
        else:
            error_msgs = {
                'missing_module': '环境测试失败：存在缺失的模块，请检查依赖安装',
                'cuda_error': '环境测试失败：CUDA 相关错误，请检查显卡驱动和 CUDA 版本',
                'unknown': '环境测试失败：未知错误，请查看上方日志'
            }
            yield {'type': 'error', 'log': error_msgs.get(error_type, error_msgs['unknown'])}

    def _test_ultralytics_source(self, version_info, env_name, repo_path):
        yield from self._log('正在测试 ultralytics 源码包加载...')

        test_code = '''
import sys
import os
try:
    from ultralytics import YOLO
    print("Ultralytics 导入成功")
    import ultralytics
    print(f"版本: {ultralytics.__version__}")
    import torch
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU 数量: {torch.cuda.device_count()}")
        print(f"当前 GPU: {torch.cuda.get_device_name(0)}")
    print("环境测试通过!")
except ImportError as e:
    print(f"导入失败: {e}")
    sys.exit(1)
except Exception as e:
    print(f"测试异常: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
        test_script_path = os.path.join(self.workspace_dir, '_auto_test_ultralytics.py')
        os.makedirs(self.workspace_dir, exist_ok=True)
        with open(test_script_path, 'w', encoding='utf-8') as f:
            f.write(test_code)

        test_success = True
        error_type = 'unknown'

        for line in self.conda.run_in_env(env_name, f'python "{test_script_path}"'):
            yield from self._log(line)
            if '[错误]' in line or '导入失败' in line or '测试异常' in line:
                test_success = False
                if 'No module named' in line or '导入失败' in line:
                    error_type = 'missing_module'
                if 'CUDA' in line or 'cuda' in line:
                    error_type = 'cuda_error'

        try:
            os.remove(test_script_path)
        except:
            pass

        if test_success:
            yield {'type': 'success', 'log': '环境测试通过！Ultralytics 源码包可以正常加载'}
        else:
            error_msgs = {
                'missing_module': '环境测试失败：存在缺失的模块，请检查依赖安装',
                'cuda_error': '环境测试失败：CUDA 相关错误，请检查显卡驱动',
                'unknown': '环境测试失败：未知错误，请查看上方日志'
            }
            yield {'type': 'error', 'log': error_msgs.get(error_type, error_msgs['unknown'])}

    def _test_pip(self, version_info, env_name):
        yield from self._log('正在测试 ultralytics 库加载...')

        test_code = '''
import sys
try:
    from ultralytics import YOLO
    print("Ultralytics 导入成功")
    print(f"版本: {YOLO.__module__}")
    import torch
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU 数量: {torch.cuda.device_count()}")
        print(f"当前 GPU: {torch.cuda.get_device_name(0)}")
    print("环境测试通过!")
except ImportError as e:
    print(f"导入失败: {e}")
    sys.exit(1)
except Exception as e:
    print(f"测试异常: {e}")
    sys.exit(1)
'''
        test_script_path = os.path.join(self.workspace_dir, '_auto_test.py')
        os.makedirs(self.workspace_dir, exist_ok=True)
        with open(test_script_path, 'w', encoding='utf-8') as f:
            f.write(test_code)

        test_success = True
        error_type = 'unknown'

        for line in self.conda.run_in_env(env_name, f'python "{test_script_path}"'):
            yield from self._log(line)
            if '[错误]' in line or '导入失败' in line or '测试异常' in line:
                test_success = False
                if 'No module named' in line or '导入失败' in line:
                    error_type = 'missing_module'
                if 'CUDA' in line or 'cuda' in line:
                    error_type = 'cuda_error'

        try:
            os.remove(test_script_path)
        except:
            pass

        if test_success:
            yield {'type': 'success', 'log': '环境测试通过！Ultralytics 库可以正常加载'}
        else:
            error_msgs = {
                'missing_module': '环境测试失败：存在缺失的模块，请检查依赖安装',
                'cuda_error': '环境测试失败：CUDA 相关错误，请检查显卡驱动',
                'unknown': '环境测试失败：未知错误，请查看上方日志'
            }
            yield {'type': 'error', 'log': error_msgs.get(error_type, error_msgs['unknown'])}
