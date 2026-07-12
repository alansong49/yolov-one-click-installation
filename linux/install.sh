#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="YOLO_AutoInstaller"
DESKTOP_FILE="$APP_NAME.desktop"
EXEC_PATH=""
ICON_PATH="$PROJECT_DIR/assets/app.png"

echo "=========================================="
echo "  YOLO AutoInstaller - 创建桌面快捷方式"
echo "=========================================="
echo ""
echo "📁 项目目录: $PROJECT_DIR"
echo ""

# 查找可执行文件
if [ -f "$PROJECT_DIR/dist/$APP_NAME" ]; then
    EXEC_PATH="$PROJECT_DIR/dist/$APP_NAME"
    echo "✅ 找到打包好的可执行文件: $EXEC_PATH"
elif [ -f "$PROJECT_DIR/$APP_NAME" ]; then
    EXEC_PATH="$PROJECT_DIR/$APP_NAME"
    echo "✅ 找到可执行文件: $EXEC_PATH"
elif command -v "$APP_NAME" &> /dev/null; then
    EXEC_PATH="$APP_NAME"
    echo "✅ 找到系统路径中的可执行文件: $(which $APP_NAME)"
else
    echo "⚠️  未找到打包好的可执行文件"
    echo "   将使用源码运行方式 (python3 main.py)"
    if [ -f "$PROJECT_DIR/main.py" ]; then
        EXEC_PATH="python3 $PROJECT_DIR/main.py"
    else
        echo "❌ 未找到 main.py，无法创建快捷方式"
        exit 1
    fi
fi

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
