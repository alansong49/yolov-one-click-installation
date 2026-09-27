#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="YOLO_AutoInstaller_2.0"
DESKTOP_NAME="YOLO_AutoInstaller"
DESKTOP_FILE="$DESKTOP_NAME.desktop"
EXEC_PATH=""
ICON_PATH="$PROJECT_DIR/assets/app.png"

echo "=========================================="
echo "  YOLO AutoInstaller - 创建桌面快捷方式"
echo "=========================================="
echo ""
echo "📁 项目目录: $PROJECT_DIR"
echo ""

# 执行路径统一走带环境检测的 run.sh（自动选择打包版/源码版，失败有可读提示）
EXEC_PATH="bash $PROJECT_DIR/linux/run.sh"
echo "✅ 快捷方式将通过 run.sh 启动（打包版优先，自动检测 X11/Wayland）"

echo ""
echo "📝 生成桌面快捷方式..."

# 创建 .desktop 文件内容
cat > "$SCRIPT_DIR/$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=YOLO AutoInstaller
Comment=YOLO 全版本一键部署工具
Exec=$EXEC_PATH
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Development;Utility;
StartupNotify=true
Path=$PROJECT_DIR
EOF

chmod +x "$SCRIPT_DIR/$DESKTOP_FILE"

# 复制到用户应用程序目录
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cp "$SCRIPT_DIR/$DESKTOP_FILE" "$APPS_DIR/"
chmod +x "$APPS_DIR/$DESKTOP_FILE"

echo "✅ 已添加到应用程序菜单: $APPS_DIR/$DESKTOP_FILE"

# 复制到桌面
if [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
elif [ -d "$HOME/桌面" ]; then
    DESKTOP_DIR="$HOME/桌面"
else
    DESKTOP_DIR=""
fi

if [ -n "$DESKTOP_DIR" ]; then
    cp "$SCRIPT_DIR/$DESKTOP_FILE" "$DESKTOP_DIR/"
    chmod +x "$DESKTOP_DIR/$DESKTOP_FILE"
    echo "✅ 已添加到桌面: $DESKTOP_DIR/$DESKTOP_FILE"
fi

echo ""
echo "=========================================="
echo "  ✅ 快捷方式创建完成！"
echo "=========================================="
echo ""
echo "💡 使用方法:"
echo "   - 在应用程序菜单中搜索 'YOLO AutoInstaller'"
echo "   - 或双击桌面上的图标"
echo ""
