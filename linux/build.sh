#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="YOLO_AutoInstaller"
MAIN_FILE="$PROJECT_DIR/main.py"

echo "=========================================="
echo "  YOLO AutoInstaller - Linux 打包脚本"
echo "=========================================="
echo ""
echo "📁 项目目录: $PROJECT_DIR"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3"
    exit 1
fi

echo "📦 检查 PyInstaller..."
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "   PyInstaller 未安装，正在安装..."
    pip3 install pyinstaller
fi

echo "🔍 检查 PyQt6..."
if ! python3 -c "import PyQt6" &> /dev/null; then
    echo "   PyQt6 未安装，正在安装..."
    pip3 install PyQt6
fi

echo "🔍 检查 requests..."
if ! python3 -c "import requests" &> /dev/null; then
    echo "   requests 未安装，正在安装..."
    pip3 install requests
fi

echo "🔍 检查 pyyaml..."
if ! python3 -c "import yaml" &> /dev/null; then
    echo "   pyyaml 未安装，正在安装..."
    pip3 install pyyaml
fi

echo ""
echo "🚀 开始打包..."
echo ""

cd "$PROJECT_DIR"

pyinstaller --noconfirm --onefile --windowed \
    --name "$APP_NAME" \
    --icon "$PROJECT_DIR/assets/app.png" \
    --clean \
    --add-data "repos.yaml:." \
    --add-data "modules:modules" \
    --add-data "assets:assets" \
    "$MAIN_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ✅ 打包成功！"
    echo "=========================================="
    echo ""
    echo "📁 输出文件: $PROJECT_DIR/dist/$APP_NAME"
    echo ""
    echo "▶️  运行方式:"
    echo "   $PROJECT_DIR/dist/$APP_NAME"
    echo ""
    chmod +x "$PROJECT_DIR/dist/$APP_NAME"
else
    echo ""
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi
