#!/bin/bash

echo "=========================================="
echo "  YOLO AutoInstaller - Linux 环境准备"
echo "=========================================="
echo ""

if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
    echo "📦 检测到 Debian/Ubuntu 系统 (apt)"
    echo ""
    echo "正在安装系统依赖..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv \
        python3-pyqt6 python3-pyqt6.qtwebengine \
        libgl1-mesa-glx libegl1 libxkbcommon0 \
        libfontconfig1 libdbus-1-3 libxcb-icccm4 \
        libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
        libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
        libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 \
        libxkbcommon-x11-0
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
    echo "📦 检测到 CentOS/RHEL 系统 (yum)"
    echo ""
    echo "正在安装系统依赖..."
    sudo yum install -y python3 python3-pip \
        mesa-libGL fontconfig dbus-libs \
        libxkbcommon libxcb
    sudo pip3 install PyQt6
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    echo "📦 检测到 Fedora 系统 (dnf)"
    echo ""
    echo "正在安装系统依赖..."
    sudo dnf install -y python3 python3-pip python3-qt6 \
        mesa-libGL fontconfig dbus-libs \
        libxkbcommon libxcb
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
    echo "📦 检测到 Arch Linux 系统 (pacman)"
    echo ""
    echo "正在安装系统依赖..."
    sudo pacman -S --noconfirm python python-pip \
        python-pyqt6 mesa fontconfig dbus \
        libxkbcommon libxcb
elif command -v zypper &> /dev/null; then
    PKG_MANAGER="zypper"
    echo "📦 检测到 openSUSE 系统 (zypper)"
    echo ""
    echo "正在安装系统依赖..."
    sudo zypper install -y python3 python3-pip \
        python3-qt6 Mesa-libGL fontconfig \
        libxkbcommon0 libxcb1
else
    echo "❌ 未检测到支持的包管理器"
    echo "请手动安装 Python3、pip3、PyQt6"
    exit 1
fi

echo ""
echo "🐍 安装 Python 依赖..."
pip3 install PyQt6 requests pyyaml pyinstaller

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "=========================================="
echo "  ✅ 环境准备完成！"
echo "=========================================="
echo ""
echo "接下来可以执行:"
echo "  bash $SCRIPT_DIR/build.sh        # 打包成单文件可执行程序"
echo "  bash $SCRIPT_DIR/install.sh      # 创建桌面快捷方式"
echo "  python3 $PROJECT_DIR/main.py     # 直接运行源码"
echo ""
