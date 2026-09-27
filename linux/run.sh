#!/bin/bash
# YOLO AutoInstaller Linux 启动脚本
# 功能：检测图形环境 → 选择正确的 QPA 平台插件 → 启动程序
#       启动失败时打印明确原因（不再静默失败）
#
# 用法：
#   bash linux/run.sh                # 自动检测平台（X11/Wayland）
#   bash linux/run.sh xcb            # 强制 X11
#   bash linux/run.sh wayland        # 强制 Wayland
#   DEBUG=1 bash linux/run.sh        # 输出 Qt 插件调试信息

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$HOME/YOLO_AutoInstaller_startup.log"
APP_BIN="$PROJECT_DIR/dist/YOLO_AutoInstaller_2.0"
APP_BIN_OLD="$PROJECT_DIR/dist/YOLO_AutoInstaller"

# 选择实际可执行目标
if [ -x "$APP_BIN" ]; then
    TARGET="$APP_BIN"
elif [ -x "$APP_BIN_OLD" ]; then
    TARGET="$APP_BIN_OLD"
else
    TARGET="python3"
    set -- "$PROJECT_DIR/main.py" "$@"
fi

echo "YOLO AutoInstaller 启动日志 ($(date))" > "$LOG_FILE"
echo "目标程序: $TARGET $*" >> "$LOG_FILE"

# ---- 1. 图形环境检测 -----------------------------------------------------
SESSION_TYPE="${XDG_SESSION_TYPE:-}"
HAS_DISPLAY=0
[ -n "${DISPLAY:-}" ] && HAS_DISPLAY=1
HAS_WAYLAND=0
[ -n "${WAYLAND_DISPLAY:-}" ] && HAS_WAYLAND=1

if [ $HAS_DISPLAY -eq 0 ] && [ $HAS_WAYLAND -eq 0 ]; then
    cat <<EOF

❌ 未检测到图形显示环境（DISPLAY 与 WAYLAND_DISPLAY 均未设置）。

常见原因与解决办法：
  1. 您正在通过 SSH 远程连接：
       方案 A（本机屏幕显示）：直接在这台 Linux 的物理显示器前操作；
       方案 B（SSH 转发 X 窗口）：退出后用「ssh -X 用户名@主机」重连，
                并确保服务器开启 X11Forwarding；
       方案 C（远程桌面）：在服务器上配置 VNC/xrdp 后再运行。
  2. 这台机器没有桌面环境：
       Debian/Ubuntu 可执行：sudo apt-get install ubuntu-desktop（或 xorg + xfce4）
       然后重启进入图形界面。

详细日志：$LOG_FILE
EOF
    echo "错误: 无图形环境" >> "$LOG_FILE"
    exit 1
fi

# ---- 2. 选择 QPA 平台插件 ------------------------------------------------
PLATFORM="${1:-}"
if [ -z "$PLATFORM" ]; then
    if [ "$SESSION_TYPE" = "wayland" ] && [ $HAS_WAYLAND -eq 1 ]; then
        PLATFORM="wayland"
    elif [ $HAS_DISPLAY -eq 1 ]; then
        PLATFORM="xcb"
    else
        PLATFORM="wayland"
    fi
fi

export QT_QPA_PLATFORM="$PLATFORM"
[ -n "${DEBUG:-}" ] && export QT_DEBUG_PLUGINS=1

echo "QPA 平台: $PLATFORM (session=${SESSION_TYPE:-unknown})" >> "$LOG_FILE"

# ---- 3. xcb 关键依赖检测 ------------------------------------------------
check_xcb_deps() {
    local missing=()
    command -v ldconfig >/dev/null 2>&1 || return 0
    local cache
    cache="$(ldconfig -p 2>/dev/null)"
    # Qt6 xcb 插件必需的库
    local need=(libxcb-cursor libxcb-xinerama libxcb-icccm libxcb-keysyms
                libxcb-image libxcb-shape libxcb-randr0 libxcb-render-util
                libxcb-xfixes libxcb-sync libxkbcommon-x11 libxkbcommon
                libGL libEGL libfontconfig libdbus-1)
    for lib in "${need[@]}"; do
        if ! echo "$cache" | grep -q "$lib"; then
            missing+=("$lib")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        cat <<EOF

❌ 缺少 Qt 平台插件「xcb」依赖的系统库：
   ${missing[*]}

这是「安装/启动后没有程序窗口」最常见的原因。请安装：

  Debian/Ubuntu:
    sudo apt-get update
    sudo apt-get install -y libxcb-cursor0 libxcb-xinerama0 \\
        libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \\
        libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \\
        libxcb-xkb1 libxkbcommon-x11-0 libgl1 libegl1 \\
        libfontconfig1 libdbus-1-3

  Fedora:        sudo dnf install libxcb libxkbcommon-x11 mesa-libGL
  Arch:          sudo pacman -S libxcb libxkbcommon mesa
  openSUSE:      sudo zypper install libxcb1 libxkbcommon-x11 Mesa-libGL

详细日志：$LOG_FILE
EOF
        echo "缺失库: ${missing[*]}" >> "$LOG_FILE"
        return 1
    fi
    return 0
}

if [ "$PLATFORM" = "xcb" ]; then
    if ! check_xcb_deps; then
        # xcb 依赖不全时，若存在 Wayland 则自动尝试
        if [ $HAS_WAYLAND -eq 1 ]; then
            echo "自动切换到 Wayland 平台重试..."
            export QT_QPA_PLATFORM="wayland"
            PLATFORM="wayland"
        else
            exit 1
        fi
    fi
fi

# ---- 4. 启动并验证进程存活 ----------------------------------------------
echo "启动命令: $TARGET $*" >> "$LOG_FILE"
"$TARGET" "$@" >> "$LOG_FILE" 2>&1 &
APP_PID=$!

# 等待 3 秒，若进程退出则说明启动失败
sleep 3
if ! kill -0 "$APP_PID" 2>/dev/null; then
    wait "$APP_PID" 2>/dev/null
    EXIT_CODE=$?
    cat <<EOF

❌ 程序启动后立即退出（退出码 $EXIT_CODE），窗口未能显示。

可能原因：
  - Qt 平台插件加载失败（缺少系统库，见上方检测）；
  - 显示服务异常或权限不足。

请将以下日志文件内容反馈以便排查：
  $LOG_FILE

日志最后 15 行：
EOF
    tail -n 15 "$LOG_FILE" | sed 's/^/    /'
    echo ""
    exit 1
fi

disown "$APP_PID" 2>/dev/null || true
echo "✅ 程序已启动（PID $APP_PID，平台 $PLATFORM），窗口应已显示。"
exit 0
