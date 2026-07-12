# YOLO AutoInstaller - YOLO 全版本一键部署工具

## 📋 项目简介

YOLO AutoInstaller 是一款基于 PyQt6 开发的 YOLO 全版本一键部署 GUI 工具，支持 Windows 和 Linux 双平台。旨在帮助用户快速完成 YOLO 环境的安装、配置和部署，无需手动配置复杂的环境变量和依赖。

## 🛠️ 技术栈

| 类别         | 技术                         | 版本    | 说明             |
| ---------- | -------------------------- | ----- | -------------- |
| **开发语言**   | Python                     | 3.10+ | 主程序开发语言        |
| **GUI 框架** | PyQt6                      | 6.x   | 图形界面框架         |
| **配置管理**   | PyYAML                     | -     | YAML 配置文件解析    |
| **打包工具**   | PyInstaller                | -     | 打包为单文件可执行程序    |
| **环境管理**   | Conda (Miniconda/Anaconda) | -     | Python 虚拟环境管理  |
| **版本控制**   | Git                        | -     | YOLO 源码克隆      |
| **深度学习**   | PyTorch                    | -     | CPU/GPU 版本自动适配 |

## ✨ 功能特性

### 1. 一键环境安装

- 自动检测系统已安装的环境（Conda、Git、GPU）
- 支持自动安装 Miniconda3 / Anaconda（可选版本）
- 支持自动安装 Git
- 国内镜像源加速，下载成功率高
- 可选择安装位置和路径

### 2. YOLO 全版本支持

支持以下 YOLO 版本的一键部署：

| YOLO 版本 | 官方源码 | 镜像源          |
| ------- | ---- | ------------ |
| YOLOv5  | ✅    | 清华镜像 / Gitee |
| YOLOv7  | ✅    | 清华镜像 / Gitee |
| YOLOv8  | ✅    | 清华镜像 / Gitee |
| YOLOv9  | ✅    | 清华镜像 / Gitee |
| YOLOv10 | ✅    | 清华镜像 / Gitee |
| YOLO11  | ✅    | 清华镜像 / Gitee |

### 3. 灵活的配置选项

- 可选择 Python 版本
- 可选择 PyTorch 版本（CPU / GPU）
- 可选择 Conda 类型（Miniconda / Anaconda）
- 可选择 Conda 版本
- 可选择 Git 版本
- 可自定义环境名称
- 可自定义工作目录

### 4. 自动化测试

- 安装完成后自动运行推理测试
- 验证环境完整性
- 测试失败自动重试安装依赖
- 生成详细的错误日志文件

### 5. 标注工具管理

- 支持 LabelImg 标注工具的安装和卸载
- 支持 LabelMe 标注工具的安装和卸载
- 已安装环境自动检测
- 一键启动标注工具
- 环境与标注工具关联管理

### 6. 编辑器环境部署

- **VSCode**：全自动配置 Python 解释器、调试配置
- **PyCharm**：半自动配置，自动生成项目配置文件
- 支持多个环境快速切换
- 一键在编辑器中打开项目

### 7. 跨平台支持

- ✅ Windows 10/11
- ✅ Linux (Ubuntu / CentOS / Fedora / Arch / openSUSE 等)
- ✅ macOS（基础支持）

## 📁 项目结构

```
一键安装 yolov/
├── main.py                    # 主程序入口（GUI 界面）
├── repos.yaml                 # YOLO 版本配置（镜像源地址）
├── YOLO_AutoInstaller.spec    # PyInstaller 打包配置
├── build.bat                  # Windows 打包脚本
├── Linux一键安装.sh           # Linux 一键安装脚本（环境+打包+快捷方式）
├── linux/                     # Linux 辅助脚本目录
│   ├── setup.sh               # Linux 环境准备
│   ├── build.sh               # Linux 打包脚本
│   ├── install.sh             # Linux 桌面快捷方式安装
│   └── run.sh                 # Linux 一键运行脚本
├── modules/                   # 核心功能模块
│   ├── __init__.py
│   ├── platform_utils.py      # 平台工具（跨平台适配核心）
│   ├── env_scan.py            # 系统环境检测
│   ├── env_installer.py       # 环境安装器
│   ├── conda_handler.py       # Conda 操作封装
│   ├── yolo_installer.py      # YOLO 部署安装
│   ├── auto_test.py           # 自动化测试
│   └── editor_deploy.py       # 编辑器部署配置
├── dist/                      # 打包输出目录
│   └── YOLO_AutoInstaller.exe # Windows 可执行文件
└── venv/                      # 程序自身的虚拟环境
```

## 🚀 快速开始

### Windows 平台

#### 方式一：直接运行（推荐）

1. 进入 `dist` 目录
2. 双击 `YOLO_AutoInstaller.exe` 运行

#### 方式二：源码运行

```bash
# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 2. 安装依赖
pip install PyQt6 requests pyyaml

# 3. 运行程序
python main.py
```

#### 方式三：自行打包

```bash
build.bat
# 打包完成后在 dist 目录生成 YOLO_AutoInstaller.exe
```

### Linux 平台

#### 方式一：一键安装（推荐）

```bash
# 1. 进入项目目录
cd "一键安装 yolov"

# 2. 执行一键安装脚本
chmod +x Linux一键安装.sh
bash Linux一键安装.sh
```

脚本会自动完成：

- 安装系统依赖和 Python 库
- 打包为单文件可执行程序
- 创建桌面快捷方式和应用菜单项
- 询问是否立即启动

#### 方式二：源码运行

```bash
# 1. 安装依赖
pip3 install PyQt6 requests pyyaml

# 2. 运行
python3 main.py
```

#### 方式三：分步操作

```bash
cd linux

# 准备环境
bash setup.sh

# 打包
bash build.sh

# 创建快捷方式
bash install.sh

# 运行
bash run.sh
```

## 📖 使用指南

### 主界面介绍

程序分为四个标签页：

| 标签页      | 功能                           |
| -------- | ---------------------------- |
| **一键部署** | YOLO 环境的一键安装部署               |
| **标注工具** | 标注工具的安装、管理和启动                |
| **环境部署** | 将环境部署到 VSCode / PyCharm 等编辑器 |
| **系统检测** | 系统环境扫描和信息查看                  |

### 1. 一键部署操作流程

```
启动程序
    ↓
选择 YOLO 版本
    ↓
选择 Conda 类型（Miniconda / Anaconda）
    ↓
选择 Python 版本
    ↓
选择 PyTorch 版本（CPU / GPU）
    ↓
选择安装位置和环境名称
    ↓
点击「一键安装部署」
    ↓
等待安装完成（15-40 分钟）
    ↓
自动运行测试
    ↓
部署完成 ✅
```

### 2. 标注工具使用

```
切换到「标注工具」标签页
    ↓
选择已安装的 YOLO 环境
    ↓
选择要安装的标注工具（LabelImg / LabelMe）
    ↓
点击「安装标注工具」
    ↓
等待安装完成
    ↓
点击「启动标注工具」
```

### 3. 编辑器环境部署

#### VSCode（全自动）

```
切换到「环境部署」标签页
    ↓
选择 YOLO 环境和项目目录
    ↓
点击「部署到 VSCode」
    ↓
自动生成 .vscode/settings.json 和 launch.json
    ↓
点击「在 VSCode 中打开」
```

#### PyCharm（半自动）

```
切换到「环境部署」标签页
    ↓
选择 YOLO 环境和项目目录
    ↓
点击「部署到 PyCharm」
    ↓
自动生成 .idea 项目配置
    ↓
在 PyCharm 中手动选择 Conda 解释器
```

## 🏗️ 架构设计

### 模块化设计

项目采用模块化架构，各模块职责清晰：

```
main.py (GUI 层)
    │
    ├── env_scan.py      → 系统环境检测
    ├── env_installer.py → 环境安装
    ├── conda_handler.py → Conda 操作
    ├── yolo_installer.py → YOLO 部署
    ├── auto_test.py     → 自动化测试
    └── editor_deploy.py → 编辑器部署
          │
          └── platform_utils.py → 平台适配（Windows/Linux/macOS）
```

### 跨平台适配设计

核心思想：**单一代码库，平台差异封装**

- 所有平台相关的代码集中在 `platform_utils.py`
- 其他模块通过调用 `platform_utils` 中的函数实现跨平台
- 运行时自动检测系统类型，选择对应实现

### 平台差异封装

| 功能         | Windows         | Linux                |
| ---------- | --------------- | -------------------- |
| Conda 路径检测 | 注册表 + 常用路径      | 常用路径 + home 目录扫描     |
| Conda 安装   | .exe 静默安装       | .sh 脚本静默安装           |
| Git 安装     | 下载 .exe 安装包     | 系统包管理器 (apt/yum/dnf) |
| Python 路径  | `python.exe`    | `bin/python`         |
| 脚本目录       | `Scripts`       | `bin`                |
| 盘符选择       | 盘符列表 (C:\ D:)   | 可写目录列表               |
| VSCode 检测  | 注册表 + 常用路径      | 常用路径 + which 检测      |
| 子进程创建      | `creationflags` | 标准参数                 |

## 🔧 核心模块说明 

### platform\_utils.py - 平台工具模块

跨平台支持的核心模块，提供：

- `is_windows()` / `is_linux()` / `is_macos()` - 系统检测
- `get_home_dir()` - 获取用户主目录
- `get_conda_search_paths()` - Conda 搜索路径
- `get_conda_scripts_dir()` - Conda 脚本目录
- `get_python_exe_name()` - Python 可执行文件名
- `get_vscode_search_paths()` - VSCode 搜索路径
- `get_pycharm_search_patterns()` - PyCharm 搜索模式
- `get_labelimg_exe_path()` - LabelImg 路径
- `get_git_search_paths()` - Git 搜索路径

### env\_scan.py - 环境检测模块

扫描系统已安装的环境：

- Conda 检测（路径 + 版本）
- Git 检测（路径 + 版本）
- GPU 检测（NVIDIA 显卡 + CUDA 版本）
- 多路径扫描，确保找到所有可能的安装位置

### env\_installer.py - 环境安装模块

自动安装运行环境：

- Git 安装（Windows 下载安装包 / Linux 系统包管理器）
- Conda 安装（Miniconda / Anaconda，可选版本）
- 国内镜像源加速下载
- 多源重试机制，提高成功率
- 安装进度和日志输出

### conda\_handler.py - Conda 操作模块

封装 Conda 的常用操作：

- 环境创建
- 环境删除
- 环境列表
- Python 路径获取
- 包安装/卸载
- 环境激活命令构造

### yolo\_installer.py - YOLO 部署模块

YOLO 环境的一键部署：

- Conda 环境创建
- PyTorch 安装（CPU/GPU 自动适配）
- YOLO 源码克隆（多镜像源重试）
- 依赖安装
- 代码补丁修复（兼容性处理）

### auto\_test.py - 自动化测试模块

部署完成后自动验证环境：

- 自动生成测试图片
- 运行 detect.py 推理测试
- 检测常见错误（缺失模块等）
- 失败自动重试安装依赖
- 生成错误日志文件

### editor\_deploy.py - 编辑器部署模块

将 Python 环境配置到编辑器中：

- VSCode：生成 settings.json、launch.json
- PyCharm：生成 .idea 项目配置
- 解释器路径自动设置
- 一键在编辑器中打开项目

## ⚙️ 配置文件

### repos.yaml

YOLO 版本配置文件，包含各版本的源码地址和镜像源：

```yaml
yolov5:
  name: "YOLOv5"
  official: "https://github.com/ultralytics/yolov5.git"
  mirrors:
    - "https://gitee.com/ultralytics/yolov5.git"
    - "https://gitclone.com/github.com/ultralytics/yolov5.git"
  ...
```

可自行添加新的 YOLO 版本或镜像源。

### installed\_envs.json

程序安装的环境记录文件，自动生成：

- 记录通过本程序安装的环境
- 用于标注工具页面的环境列表
- 存储环境名称、路径、YOLO 版本等信息

## 📝 日志文件

程序运行过程中产生的日志：

| 日志类型   | 命名格式                          | 位置    |
| ------ | ----------------------------- | ----- |
| 安装失败日志 | `{env_name}_failed_{时间}.log`  | 程序根目录 |
| 安装成功日志 | `{env_name}_success_{时间}.log` | 程序根目录 |

## ❓ 常见问题

### Q1: 下载速度慢怎么办？

A: 程序已内置多个国内镜像源（清华、阿里、Gitee 等），会自动选择可用的镜像源。

### Q2: 安装失败怎么排查？

A: 查看程序根目录下生成的失败日志文件，搜索 `Error` 或 `错误` 关键字。

### Q3: Linux 下 LabelMe/LabelImg 启动失败？

A: 常见原因是 OpenCV 的 Qt 插件冲突，解决方案：

```bash
conda activate yolov5_env
pip uninstall opencv-python -y
pip install opencv-python-headless
```

### Q4: Linux 下 Conda 检测不到？

A: 确保 Conda 安装在标准路径（如 \~/anaconda3、\~/miniconda3），或在程序中手动指定路径。

### Q5: 支持 GPU 版本吗？

A: 支持，程序会自动检测 NVIDIA 显卡，如果检测到 GPU 会默认安装 GPU 版本 PyTorch。

## 🤝 技术说明

### 依赖管理

- 程序自身使用独立的虚拟环境（venv）
- 部署的 YOLO 环境使用 Conda 管理
- 两者互不干扰

### 线程模型

- GUI 运行在主线程
- 环境扫描、安装等耗时操作在后台线程执行
- 通过信号槽机制更新 UI，避免界面卡顿

### 错误处理

- 多层 try-catch 异常捕获
- 详细的错误日志输出
- 友好的错误提示和解决方案

## 📄 许可证

制作者JockerSilas，本项目仅供学习和研究使用。

## 📞 反馈

如遇到问题或有改进建议，欢迎反馈。
