# YOLO AutoInstaller 2.0 - YOLO 全版本一键部署工具

## 📋 项目简介

YOLO AutoInstaller 是一款基于 PyQt6 开发的 YOLO 全版本一键部署 GUI 工具，支持 Windows 和 Linux 双平台。用户通过图形界面选择 YOLO 版本与硬件配置，程序自动完成 Conda 环境、PyTorch、YOLO 源码/依赖的完整部署，全程无需手动输入终端命令。2.0 版本新增**断点恢复**能力：部署中断后进度不丢失，下次启动可继续。

---

## � 操作方法

> 本节为完整操作说明：安装 → 配置 → 使用。首次使用请按顺序阅读。

### 1. 安装步骤

#### Windows 平台

> ⛔ **必须以管理员身份运行**：请右键 `YOLO_AutoInstaller_2.0.exe` 并选择「以管理员身份运行」。
> 程序需要向系统盘受保护目录（如 `C:\Program Files`、`C:\Anaconda3`）写入文件、修改环境变量并执行 UAC 提权操作，
> 普通用户权限会导致环境写入测试失败、安装程序异常退出（返回码 2）或 pip 静默改装到用户目录破坏环境隔离。

**方式一：直接运行（推荐）**

1. 前置条件：Windows 10/11（64 位）。Conda、Git 无需预装，程序可自动安装。
2. 从 [Releases](https://github.com/alansong49/yolov-one-click-installation/releases) 下载 `YOLO_AutoInstaller_2.0.exe`。
3. **右键以管理员身份运行**。程序启动后自动扫描系统环境（Conda / Git / NVIDIA 显卡）。
4. 若系统未安装 Conda 或 Git，在「一键部署」页选择版本后点击安装，程序自动完成安装（内置国内镜像加速）。

**方式二：源码运行**

```bash
# 1. 进入项目目录
cd "一键安装 yolov"

# 2. 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install PyQt6 requests pyyaml

# 4. 运行
python main.py
```

#### Linux 平台

**方式一：一键安装（推荐）**

```bash
# 1. 进入项目根目录
cd "一键安装 yolov"

# 2. 执行一键安装脚本（自动安装系统依赖 + 打包 + 创建快捷方式）
chmod +x Linux一键安装.sh
bash Linux一键安装.sh
```

脚本自动完成：
- 网络诊断与 DNS 修复（支持自动切换清华/阿里 apt 镜像源）
- 安装系统依赖与 Python 库（自动处理 PEP 668 限制）
- 打包生成 `dist/YOLO_AutoInstaller_2.0`
- 创建桌面快捷方式与应用菜单项（固定命名 `YOLO_AutoInstaller.desktop`）
- 询问是否立即启动

**方式二：仅打包**

```bash
chmod +x linux/build.sh
bash linux/build.sh        # 产物: dist/YOLO_AutoInstaller_2.0
bash linux/install.sh      # 可选：创建桌面快捷方式
```

**方式三：源码运行**

```bash
pip3 install PyQt6 requests pyyaml
python3 main.py
```

### 2. 配置流程

程序启动后进入「一键部署」页，按以下顺序配置：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| YOLO 版本 | 下拉选择 v5 / v7 / v8 / v9 / v10 / v11 | YOLOv8 |
| Conda 类型 | Miniconda（轻量）或 Anaconda（完整） | Miniconda3 |
| Python 版本 | 环境内 Python 版本 | 3.10 |
| PyTorch 版本 | `latest` 为最新稳定版；Python 3.8 自动降级兼容 | latest |
| GPU/CPU | 勾选使用 CUDA GPU 版本（需 NVIDIA 显卡，程序自动检测） | ☑ |
| 安装位置 | 工作目录所在盘符（Windows）或可写目录（Linux） | E: |
| 工作目录 | 部署产物与数据集的根目录，默认 `yolo_workspace` | yolo_workspace |
| 标注工具 | 可选同时安装 LabelImg / LabelMe | 不安装 |

最终工作路径预览格式：`<安装位置>\<工作目录>`（如 `E:\yolo_workspace`）。

确认无误后点击「一键安装部署」，弹窗二次确认后开始部署。

### 3. 使用说明

#### 3.1 一键部署（核心流程）

```
选择配置 → 确认安装 → 创建 Conda 环境 → 配置 pip 镜像 → 安装 PyTorch
    → 拉取源码 / 安装 ultralytics → 安装依赖 → 初始化数据集目录
    → 下载默认权重 → 自动化测试 → 部署完成 ✅
```

- 全程日志实时回显；下载显示进度百分比、速度与预计剩余时间。
- 部署耗时约 15–40 分钟，取决于网络与硬件。
- 部署成功后自动创建标准 YOLO 数据集结构（见「项目目录结构」一节），并保存环境记录供标注工具/编辑器部署页使用。

#### 3.2 断点恢复

- **中断后恢复**：部署中误关程序或系统重启后，再次打开程序会弹出「发现未完成的部署任务」对话框，可选择：
  - **▶ 继续部署**：自动跳过已完成步骤，下载从断点续传；
  - **🗑 放弃并清理**：删除未完成的下载文件与进度缓存（已创建的 Conda 环境保留）；
  - **暂不处理**：下次启动再次询问。
- **关闭保护**：部署/训练进行中点击窗口 × 时弹出三选一：
  - **🔽 最小化到后台继续**：隐藏到系统托盘，完成后自动恢复窗口；
  - **💾 关闭并保留进度**：退出程序，下次启动可继续（训练任务不支持，显示为"终止训练"）；
  - **取消**：返回主窗口。
- 托盘图标支持双击恢复窗口、右键菜单（打开主窗口 / 退出）。

#### 3.3 一键训练

1. 切换到「◎ 一键训练」页。
2. 选择已部署的环境与对应系列模型（下拉框仅显示当前环境系列已下载的 `.pt` 权重；未找到时先完成部署或点击「⊙ 全局扫描」搜索全盘权重）。
3. 数据集路径默认自动填充为 `<工作目录>\data`，也可手动修改（手动选择后不会被覆盖）。
4. 配置训练参数后点击开始，Epoch 进度、批次信息与耗时实时显示。
5. 训练结果统一保存到 `<工作目录>/runs/detect`，多次训练自动生成 `train`、`train2`、`train3` 等子目录，不会互相覆盖。

#### 3.4 标注工具

「◆ 标注工具」页支持为已部署环境安装 LabelImg / LabelMe，一键启动，并支持卸载。环境列表自动刷新，也可手动刷新。

#### 3.5 环境部署（编辑器集成）

「⚙ 环境部署」页将 Conda 环境配置到编辑器：
- **VSCode**：全自动生成 `.vscode/settings.json` 与 `launch.json`，解释器路径自动设置；
- **PyCharm**：自动生成 `.idea` 项目配置，首次打开后手动确认 Conda 解释器即可。

#### 3.6 训练/验证/预测/导出/视频

「⚙ 训练/验证/预测/导出/视频」操作页提供逐条命令式操作，适合对 YOLO 已有使用经验的用户执行细分任务。

---

## 📁 项目目录结构

### 程序目录

```
一键安装 yolov/
├── main.py                    # 主程序入口（GUI 界面、线程调度、断点恢复对话框）
├── repos.yaml                 # YOLO 版本静态配置（镜像源地址）
├── YOLO_AutoInstaller.spec    # PyInstaller 打包配置（Windows）
├── build.bat                  # Windows 打包脚本
├── Linux一键安装.sh           # Linux 一键安装脚本（依赖+打包+快捷方式）
├── assets/                    # 程序图标资源（固定命名，勿改名）
│   ├── app.ico                #   Windows 窗口/exe 图标
│   └── app.png                #   Linux 窗口/快捷方式图标
├── linux/                     # Linux 辅助脚本
│   ├── setup.sh / build.sh / install.sh / run.sh
├── modules/                   # 核心功能模块（见"代码模块介绍"）
├── docs/                      # 项目文档
│   ├── 断点恢复-开发文档.md
│   ├── 断点恢复-用户操作指南.md
│   └── 项目完整开发手册.md
├── dist/                      # 打包输出
└── venv/                      # 程序自身虚拟环境
```

### 数据集目录（部署后自动生成）

部署成功后在 `<工作目录>`（默认 `yolo_workspace`）下自动创建标准 YOLO 数据集结构：

```
<工作目录>/                        # 例如 E:\yolo_workspace
├── data/                         # 数据集根目录
│   ├── data.yaml                 # 数据集配置（自动生成模板，已存在时不覆盖）
│   ├── images/                   # 📷 图片资源存放目录（支持 .jpg / .jpeg / .png）
│   │   ├── train/                #    训练集图片
│   │   └── val/                  #    验证集图片
│   ├── labels/                   # 📄 TXT 标签数据文件存放目录
│   │   ├── train/                #    训练集标签
│   │   └── val/                  #    验证集标签
├── runs/detect/                  # 训练输出（train / train2 / train3 …自动编号）
└── yolov8/ 等                    # 克隆的 YOLO 源码仓库
```

#### 图片资源规范

| 项目 | 规范 |
|------|------|
| 支持格式 | `.jpg`、`.jpeg`、`.png` |
| 存放路径 | 训练图片放 `data/images/train/`，验证图片放 `data/images/val/` |
| 命名规范 | 建议使用英文小写+数字（如 `img_0001.jpg`），**避免中文与空格**，防止部分 YOLO 版本读取失败 |
| 数量要求 | `train` 与 `val` 均不能为空；val 一般取总量的 10%–20% |

#### TXT 标签文件规范（YOLO 格式）

| 项目 | 规范 |
|------|------|
| 存放路径 | 与图片一一对应：`data/labels/train/`、`data/labels/val/` |
| 命名规范 | **与图片文件同名仅扩展名不同**：`img_0001.jpg` ↔ `img_0001.txt` |
| 文件内容 | 每行一个目标，5 个空格分隔的数值：`class_id x_center y_center width height` |
| 坐标系 | 后 4 项为**归一化值**（0–1，相对于图片宽高），非像素值 |

标签文件示例（`img_0001.txt`，图片中有一个目标，类别 0）：

```text
0 0.512 0.480 0.250 0.380
```

多目标示例（两个目标，类别 0 和 1）：

```text
0 0.512 0.480 0.250 0.380
1 0.150 0.700 0.100 0.200
```

#### data.yaml 配置示例（自动生成模板）

```yaml
# YOLO 数据集配置文件（自动生成模板，请按您的实际数据集修改）
path: E:/yolo_workspace/data      # 数据集根目录（正斜杠）
train: images/train               # 训练集图片目录（相对 path）
val: images/val                   # 验证集图片目录（相对 path）
nc: 1                             # ⚠️ 类别数量，必须按实际修改
names:                            # ⚠️ 类别名称，顺序与标签中的编号一致
  0: object
```

> ⚠️ 注意：`nc` 与 `names` 必须与实际数据一致；`path` 使用正斜杠；重复部署不会覆盖您已修改的 `data.yaml`。

#### 程序图标资源规范

`assets/` 目录存放程序图标，**固定命名**：`app.ico`（Windows 打包与窗口图标）、`app.png`（Linux 打包与桌面快捷方式图标）。重新生成可运行 `python generate_icons.py`。

---

## ✨ 核心功能说明

### 1. 一键环境安装
- 自动检测系统已安装的 Conda、Git、NVIDIA GPU；
- 自动安装 Miniconda3 / Anaconda（可选版本，多镜像源：北大 → 清华 → 官方）；
- Git 安装五级策略（winget → npmmirror 镜像 → 自动装 winget → conda → 本地包兜底）；
- PyTorch 优先上海交大镜像，失败自动切换官方源；pip 读超时 300 秒、失败自动重试 5 次。

### 2. YOLO 全版本支持

| YOLO 版本 | 部署模式 | 源码镜像 |
|-----------|----------|----------|
| YOLOv5 / v7 / v9 / v10 | source（克隆源码 + requirements） | 清华镜像 / Gitee 多源重试 |
| YOLOv8 / YOLO11 | pip（`ultralytics` 库） | 清华 pip 镜像 |

### 3. 断点恢复（2.0 新增）
- 部署状态 JSON 持久化（原子写入，程序目录 + 系统 AppData/XDG 双路径兜底）；
- 9 个部署步骤级跳过恢复；HTTP Range 断点续传；
- 已下载文件 SHA256 校验，损坏自动重下；
- 启动恢复对话框、关闭保护三选一、系统托盘后台运行。

### 4. 自动化测试
- 部署完成自动运行推理测试验证环境；
- 检测到依赖缺失自动重装并重试；
- 生成详细错误日志文件。

### 5. 标注工具与编辑器集成
- LabelImg / LabelMe 安装、卸载、启动；
- VSCode 全自动 / PyCharm 半自动环境部署。

### 6. 一键训练
- 按环境系列筛选已下载权重，全盘扫描模型缓存；
- Epoch 实时进度、自动编号保存结果、数据集路径自动填充。

---

## 🏗️ 技术架构

### 整体架构

```
GUI 界面层 (main.py, PyQt6 主线程)
    │  信号槽通信
    ├── InstallThread / OpsThread 等后台线程（QThread）
    │       │
    │       ├── env_scan.py        → 系统环境检测
    │       ├── env_installer.py   → Conda/Git 安装
    │       ├── conda_handler.py   → Conda/pip 命令封装
    │       ├── yolo_installer.py  → YOLO 部署流水线（生成器事件协议）
    │       ├── task_state.py      → 断点状态持久化
    │       ├── auto_test.py       → 自动化测试
    │       └── editor_deploy.py   → 编辑器配置
    │               │
    │               └── platform_utils.py → 跨平台适配（Windows/Linux/macOS）
    └── 静态配置 repos.yaml（6 个 YOLO 版本定义）
```

### 关键技术点

- **生成器事件协议**：安装器通过 `yield {'type': 'step'/'log'/'error'/'success'/'download_progress'}` 推送事件，线程层转发为 Qt 信号更新 UI；
- **线程模型**：GUI 主线程 + 后台 QThread；所有操作线程由窗口级列表持有并在结束后自动移除，防止垃圾回收导致崩溃；
- **跨平台**：平台差异全部封装在 `platform_utils.py`（路径、盘符、包管理器、注册表等），单一代码库双平台运行；
- **断点恢复机制**：详见 [docs/断点恢复-开发文档.md](docs/断点恢复-开发文档.md)；
- **兼容性补丁**：部署时自动写入 `sitecustomize.py` 全局覆盖 `torch.load` 的 `weights_only=True`（PyTorch ≥ 2.6 兼容旧版权重）。

---

## 🧩 代码模块介绍

| 模块 | 职责 |
|------|------|
| `main.py` | GUI 入口；5 个页签（一键部署/标注工具/环境部署/训练操作/一键训练）；后台线程调度；恢复与关闭对话框；系统托盘 |
| `modules/platform_utils.py` | 跨平台适配核心：运行目录定位、路径规范化、安装位置枚举、Conda/编辑器搜索路径 |
| `modules/env_scan.py` | 扫描系统 Conda（多路径）、Git、NVIDIA GPU/CUDA |
| `modules/env_installer.py` | Miniconda/Anaconda/Git 自动安装，多镜像源重试 |
| `modules/conda_handler.py` | Conda 环境创建/删除/扫描、pip 安装（`--progress-bar raw`、UTF-8 环境变量）、残留目录清理与提权删除 |
| `modules/yolo_installer.py` | 部署流水线核心：环境创建 → PyTorch → 源码/依赖 → 权重下载（断点续传 + SHA256）→ 兼容补丁 |
| `modules/task_state.py` | 断点状态管理器：原子写入、下载节流落盘、文件校验、放弃清理 |
| `modules/auto_test.py` | 部署后推理自检，失败自动重装依赖 |
| `modules/editor_deploy.py` | VSCode / PyCharm 项目配置生成 |
| `repos.yaml` | YOLO 版本静态配置：名称、模式、镜像地址、推荐 Python/PyTorch 版本、默认权重 |

---

## ❓ 常见问题

### Q1: 下载速度慢怎么办？
A: 程序已内置多个国内镜像源（北大、清华、上海交大、Gitee 等），自动选择可用源；权重下载支持断点续传，中断后重试不会从头下载。

### Q2: 安装失败怎么排查？
A: 查看程序工作目录下生成的 `{环境名}_failed_{时间}.log`，搜索 `Error` 或 `[错误]` 关键字；界面日志会给出针对性解决办法。

### Q3: 部署中断后进度会丢吗？
A: 不会。2.0 版本自动保存进度，重新打开程序后选择"继续部署"即可从中断处继续；详见 [docs/断点恢复-用户操作指南.md](docs/断点恢复-用户操作指南.md)。

### Q4: 训练报错找不到验证集图片？
A: 确保 `data/images/val` 与 `data/labels/val` 中的文件一一对应（同名不同扩展名），且 `data.yaml` 的 `path/train/val` 指向正确。

### Q5: Linux 下 LabelMe/LabelImg 启动失败？
A: 常见原因是 OpenCV 的 Qt 插件冲突：

```bash
conda activate yolov5_env
pip uninstall opencv-python -y
pip install opencv-python-headless
```

### Q6: 支持 GPU 版本吗？
A: 支持。程序自动检测 NVIDIA 显卡并默认推荐 GPU 版本 PyTorch（CUDA 12.1）；无显卡时安装 CPU 版本。

---

## ⚠️ 注意事项

1. **权限**：Windows 下**必须以管理员身份运行**程序，否则 Conda/pip 无法写入受保护目录，导致部署失败。
2. **环境版本一致性**：环境已存在但 Python 版本与所选不符时，程序会拦截并指引删除旧环境后重新部署，请勿强行继续。
3. **base 环境保护**：「管理虚拟环境」中 base 环境禁止删除。
4. **数据安全**：删除环境前会二次确认；"放弃并清理"不会删除已创建的 Conda 环境和源码目录。
5. **中文路径**：标签与图片文件名避免中文和空格；训练日志已强制 UTF-8 输出。

## 📄 许可证

制作者 JockerSilas，本项目仅供学习和研究使用。

## 📞 反馈

如遇到问题或有改进建议，欢迎在 GitHub Issues 中反馈。
