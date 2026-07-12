#!/bin/bash

# ============================================================
# YOLO AutoInstaller - Linux 一键安装脚本
# ============================================================
# 功能：
#   1. 自动安装系统依赖和 Python 库
#   2. 自动打包成单文件可执行程序
#   3. 自动创建桌面快捷方式和应用菜单项
#   4. 安装完成后可选择立即启动
# ============================================================

# 找到脚本所在目录（项目根目录）
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
PROJECT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

APP_NAME="YOLO_AutoInstaller"
SKIP_PIP_INSTALL=false

# 清屏
clear

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║      🚀 YOLO AutoInstaller - Linux 一键安装             ║"
echo "║                                                          ║"
echo "║      YOLO 全版本一键部署工具                             ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📁 项目目录: $PROJECT_DIR"
echo ""

# ============================================================
# 工具函数
# ============================================================

check_cmd() {
    command -v "$1" &> /dev/null
}

info() {
    echo -e "  \033[1;34mℹ\033[0m  $1"
}

success() {
    echo -e "  \033[1;32m✓\033[0m  $1"
}

warn() {
    echo -e "  \033[1;33m⚠\033[0m  $1"
}

error() {
    echo -e "  \033[1;31m✗\033[0m  $1"
}

step_title() {
    echo ""
    echo "┌──────────────────────────────────────────────────────────┐"
    echo "│  $1"
    echo "└──────────────────────────────────────────────────────────┘"
    echo ""
}

# 安装 Python 包（自动处理 PEP 668）
pip_install() {
    local pkg="$1"
    $PIP_CMD install "$pkg"
    if [ $? -ne 0 ]; then
        warn "普通安装失败，尝试添加 --break-system-packages..."
        $PIP_CMD install --break-system-packages "$pkg"
        return $?
    fi
    return 0
}

# ============================================================
# 检查是否在 Linux 下运行
# ============================================================

if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    error "此脚本只能在 Linux 系统下运行！"
    echo ""
    echo "当前系统: $OSTYPE"
    echo ""
    exit 1
fi

# ============================================================
# 网络诊断与修复
# ============================================================

# 测试 URL 访问
test_url() {
    local url="$1"
    if check_cmd curl; then
        curl -fsSL --connect-timeout 5 "$url" > /dev/null 2>&1
        return $?
    elif check_cmd wget; then
        wget --timeout=5 --spider "$url" > /dev/null 2>&1
        return $?
    else
        return 1
    fi
}

# 测试 DNS 解析
test_dns() {
    local host="$1"
    if check_cmd nslookup; then
        nslookup "$host" > /dev/null 2>&1
        return $?
    elif check_cmd dig; then
        dig +short "$host" > /dev/null 2>&1
        return $?
    elif check_cmd getent; then
        getent hosts "$host" > /dev/null 2>&1
        return $?
    else
        # 没有 DNS 工具，直接用 ping 测试
        if check_cmd ping; then
            ping -c 1 -W 2 "$host" > /dev/null 2>&1
            return $?
        fi
        return 1
    fi
}

# 测试网络连通性（用 IP 地址，绕过 DNS）
test_ip_connectivity() {
    # 测试一些知名的公共 IP
    local test_ips=("8.8.8.8" "114.114.114.114" "1.1.1.1")
    for ip in "${test_ips[@]}"; do
        if check_cmd ping; then
            if ping -c 1 -W 2 "$ip" > /dev/null 2>&1; then
                return 0
            fi
        fi
    done
    return 1
}

# DNS 修复函数
fix_dns() {
    info "尝试修复 DNS 配置..."
    echo ""

    local dns_servers="nameserver 114.114.114.114
nameserver 8.8.8.8
nameserver 223.5.5.5"

    if [ -f /etc/resolv.conf ]; then
        # 备份原配置
        sudo cp /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null

        # 尝试临时修改 DNS
        echo "$dns_servers" | sudo tee /etc/resolv.conf > /dev/null 2>&1

        # 测试是否修复
        sleep 1
        if test_dns "www.baidu.com"; then
            success "DNS 修复成功！"
            return 0
        fi
    fi

    # 尝试用 systemd-resolved
    if check_cmd resolvectl; then
        sudo resolvectl dns 0 114.114.114.114 8.8.8.8 2>/dev/null
        sleep 1
        if test_dns "www.baidu.com"; then
            success "DNS 修复成功！"
            return 0
        fi
    fi

    warn "DNS 修复失败，请检查网络连接"
    return 1
}

# 主网络检测
echo ""
info "检测网络连接..."
echo ""

NETWORK_OK=false
DNS_OK=false

# 先测试 DNS
if test_dns "www.baidu.com"; then
    DNS_OK=true
    success "DNS 解析正常"
else
    warn "DNS 解析失败"
fi

# 再测试网络连通性
if test_ip_connectivity; then
    success "网络连通正常（IP 层）"
    # IP 通但 DNS 不通，尝试修复 DNS
    if [ "$DNS_OK" = false ]; then
        echo ""
        warn "检测到：网络通但 DNS 不通"
        read -p "  是否尝试自动修复 DNS？(Y/n): " fix_dns_confirm
        if [[ ! "$fix_dns_confirm" =~ ^[Nn]$ ]]; then
            echo ""
            fix_dns
            if [ $? -eq 0 ]; then
                DNS_OK=true
            fi
        fi
    fi
else
    error "网络连接失败（IP 层也不通）"
    echo ""
    echo "  请检查："
    echo "    1. 网络电缆是否插好"
    echo "    2. WiFi 是否连接"
    echo "    3. 虚拟机网络设置是否正确"
    echo "    4. 路由器是否正常工作"
    echo ""
    warn "网络不通，将无法安装依赖，程序可能无法正常运行"
fi

# 如果 DNS 通了，测试 apt 源并切换
if [ "$DNS_OK" = true ] && check_cmd apt-get; then
    echo ""
    if ! test_url "http://cn.archive.ubuntu.com/"; then
        warn "默认软件源连接失败，尝试切换到国内镜像..."
        echo ""

        if test_url "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/"; then
            info "清华源可用，切换中..."
            sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 2>/dev/null
            sudo sed -i 's|http://cn.archive.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            sudo sed -i 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            sudo sed -i 's|http://security.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            success "已切换到清华源"
        elif test_url "https://mirrors.aliyun.com/ubuntu/"; then
            info "阿里源可用，切换中..."
            sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 2>/dev/null
            sudo sed -i 's|http://cn.archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            sudo sed -i 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            sudo sed -i 's|http://security.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list 2>/dev/null
            success "已切换到阿里源"
        else
            warn "国内镜像源也无法连接，将尝试使用现有配置"
        fi
    else
        success "默认软件源可用"
    fi
fi

# ============================================================
# 第一步：安装系统依赖
# ============================================================

step_title "步骤 1/3：安装系统依赖"

# 检查 python3
if ! check_cmd python3; then
    info "未找到 Python3，正在安装系统依赖..."
    echo ""

    if check_cmd apt-get; then
        info "检测到 Debian/Ubuntu 系统"
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv \
            libgl1-mesa-glx libegl1 libxkbcommon0 \
            libfontconfig1 libdbus-1-3 libxcb-icccm4 \
            libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
            libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
            libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 \
            libxkbcommon-x11-0
    elif check_cmd yum; then
        info "检测到 CentOS/RHEL 系统"
        sudo yum install -y python3 python3-pip \
            mesa-libGL fontconfig dbus-libs \
            libxkbcommon libxcb
    elif check_cmd dnf; then
        info "检测到 Fedora 系统"
        sudo dnf install -y python3 python3-pip \
            mesa-libGL fontconfig dbus-libs \
            libxkbcommon libxcb
    elif check_cmd pacman; then
        info "检测到 Arch Linux 系统"
        sudo pacman -S --noconfirm python python-pip \
            mesa fontconfig dbus libxkbcommon libxcb
    elif check_cmd zypper; then
        info "检测到 openSUSE 系统"
        sudo zypper install -y python3 python3-pip \
            Mesa-libGL fontconfig libxkbcommon0 libxcb1
    else
        error "未检测到支持的包管理器"
        echo ""
        echo "请手动安装以下依赖："
        echo "  - python3"
        echo "  - python3-pip"
        echo "  - PyQt6 (pip3 install PyQt6)"
        echo ""
        exit 1
    fi

    echo ""
    success "系统依赖安装完成"
else
    success "Python3 已安装: $(python3 --version 2>&1)"
fi

# 检查 pip
echo ""
info "检查 pip..."
echo ""

PIP_AVAILABLE=false

if check_cmd pip3; then
    PIP_CMD="pip3"
    PIP_AVAILABLE=true
    success "pip3 可用"
elif python3 -m pip --version &> /dev/null; then
    PIP_CMD="python3 -m pip"
    PIP_AVAILABLE=true
    success "python3 -m pip 可用"
fi

if [ "$PIP_AVAILABLE" = false ]; then
    warn "未找到 pip，正在尝试安装..."
    echo ""

    # 方式 1：系统包管理器安装
    install_pip_via_package_manager() {
        if check_cmd apt-get; then
            info "尝试通过 apt 安装 python3-pip..."
            sudo apt-get install -y python3-pip 2>/dev/null
            return $?
        elif check_cmd yum; then
            info "尝试通过 yum 安装 python3-pip..."
            sudo yum install -y python3-pip 2>/dev/null
            return $?
        elif check_cmd dnf; then
            info "尝试通过 dnf 安装 python3-pip..."
            sudo dnf install -y python3-pip 2>/dev/null
            return $?
        elif check_cmd pacman; then
            info "尝试通过 pacman 安装 python-pip..."
            sudo pacman -S --noconfirm python-pip 2>/dev/null
            return $?
        elif check_cmd zypper; then
            info "尝试通过 zypper 安装 python3-pip..."
            sudo zypper install -y python3-pip 2>/dev/null
            return $?
        fi
        return 1
    }

    # 方式 2：get-pip.py 安装（轻量，不依赖系统源）
    install_pip_via_getpip() {
        info "尝试通过 get-pip.py 安装 pip（轻量方式）..."
        echo ""

        local get_pip_urls=(
            "https://pypi.tuna.tsinghua.edu.cn/packages/get-pip.py"
            "https://mirrors.aliyun.com/pypi/get-pip.py"
            "https://bootstrap.pypa.io/get-pip.py"
        )

        local tmp_file=$(mktemp /tmp/get-pip.XXXXXX.py)

        for url in "${get_pip_urls[@]}"; do
            info "从 $url 下载..."
            if curl -fsSL "$url" -o "$tmp_file" 2>/dev/null; then
                python3 "$tmp_file" --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null
                if [ $? -eq 0 ]; then
                    rm -f "$tmp_file"
                    return 0
                fi
            fi
            if wget -q "$url" -O "$tmp_file" 2>/dev/null; then
                python3 "$tmp_file" --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null
                if [ $? -eq 0 ]; then
                    rm -f "$tmp_file"
                    return 0
                fi
            fi
        done

        rm -f "$tmp_file"
        return 1
    }

    # 方式 3：ensurepip
    install_pip_via_ensurepip() {
        info "尝试通过 ensurepip 安装 pip..."
        python3 -m ensurepip --upgrade 2>/dev/null
        return $?
    }

    # 依次尝试各种安装方式
    installed=false

    install_pip_via_package_manager
    if [ $? -eq 0 ]; then
        installed=true
    else
        warn "系统包管理器安装失败，尝试其他方式..."
        echo ""
    fi

    if [ "$installed" = false ]; then
        install_pip_via_getpip
        if [ $? -eq 0 ]; then
            installed=true
        else
            warn "get-pip.py 安装失败，尝试 ensurepip..."
            echo ""
        fi
    fi

    if [ "$installed" = false ]; then
        install_pip_via_ensurepip
        if [ $? -eq 0 ]; then
            installed=true
        fi
    fi

    echo ""
    if [ "$installed" = true ]; then
        if check_cmd pip3; then
            PIP_CMD="pip3"
            PIP_AVAILABLE=true
        elif python3 -m pip --version &> /dev/null; then
            PIP_CMD="python3 -m pip"
            PIP_AVAILABLE=true
        fi
        if [ "$PIP_AVAILABLE" = true ]; then
            success "pip 安装成功: $($PIP_CMD --version 2>&1 | head -1)"
        else
            installed=false
        fi
    fi

    if [ "$installed" = false ]; then
        echo ""
        error "pip 自动安装失败！"
        echo ""

        # 检查是否已经有 PyQt6 了（可能用户之前手动装过）
        if python3 -c "import PyQt6" &> /dev/null; then
            success "检测到 PyQt6 已存在，跳过 pip 安装，直接运行程序"
            echo ""
            PIP_AVAILABLE=false
            SKIP_PIP_INSTALL=true
        else
            echo "  ┌─────────────────────────────────────────┐"
            echo "  │  🔍 可能的原因：                          │"
            echo "  │                                         │"

            if [ "$DNS_OK" = false ]; then
                echo "  │  ⚠  DNS 解析失败（域名无法解析）           │"
                echo "  │     请检查网络连接和 DNS 设置             │"
                echo "  │                                         │"
            fi

            if [ "$NETWORK_OK" = false ]; then
                echo "  │  ⚠  网络连接失败                          │"
                echo "  │     请检查网络是否正常连接                 │"
                echo "  │                                         │"
            fi

            echo "  └─────────────────────────────────────────┘"
            echo ""
            echo "  💡 解决方案："
            echo ""
            echo "  1. 检查网络是否正常连接"
            echo "  2. 如果是虚拟机，检查网络适配器设置"
            echo "     - VMware/VirtualBox: 设置为 NAT 模式"
            echo "     - WSL: 在 Windows 执行 wsl --shutdown 后重启"
            echo ""
            echo "  3. 尝试手动设置 DNS："
            echo "     sudo tee /etc/resolv.conf << 'EOF'"
            echo "     nameserver 114.114.114.114"
            echo "     nameserver 8.8.8.8"
            echo "     EOF"
            echo ""
            echo "  4. 手动安装依赖（需要网络）："
            echo "     sudo apt-get install python3-pip python3-pyqt6"
            echo "     pip3 install requests pyyaml"
            echo ""
            echo "  5. 网络恢复后，重新运行此脚本"
            echo ""
            exit 1
        fi
    fi
fi

echo ""
info "检查 Python 依赖..."
echo ""

# 通用检查函数
check_python_dep() {
    local name="$1"
    local import_name="$2"
    local critical="$3"

    python3 -c "import $import_name" &> /dev/null
    if [ $? -eq 0 ]; then
        success "$name 已安装"
        return 0
    fi

    if [ "$SKIP_PIP_INSTALL" = true ]; then
        if [ "$critical" = true ]; then
            error "$name 未安装，且无法自动安装（网络不可用）"
            return 1
        else
            warn "$name 未安装，部分功能可能受限"
            return 0
        fi
    fi

    info "正在安装 $name..."
    pip_install "$name"
    if [ $? -eq 0 ]; then
        success "$name 安装完成"
        return 0
    else
        if [ "$critical" = true ]; then
            error "$name 安装失败"
            return 1
        else
            warn "$name 安装失败，部分功能可能受限"
            return 0
        fi
    fi
}

# 检查 PyQt6（核心依赖）
check_python_dep "PyQt6" "PyQt6" true
if [ $? -ne 0 ]; then
    echo ""
    error "缺少核心依赖 PyQt6，无法运行程序"
    echo ""
    echo "  请先连接网络，然后重新运行此脚本"
    echo ""
    exit 1
fi

# 检查 requests（非核心，缺失时部分功能受限）
check_python_dep "requests" "requests" false

# 检查 pyyaml（核心依赖）
check_python_dep "pyyaml" "yaml" true
if [ $? -ne 0 ]; then
    echo ""
    error "缺少核心依赖 pyyaml，无法运行程序"
    echo ""
    echo "  请先连接网络，然后重新运行此脚本"
    echo ""
    exit 1
fi

# 检查 pyinstaller（非核心，打包用）
HAS_PYINSTALLER=false
if [ "$SKIP_PIP_INSTALL" != true ]; then
    python3 -c "import PyInstaller" &> /dev/null
    if [ $? -ne 0 ]; then
        info "正在安装 pyinstaller..."
        pip_install pyinstaller
        if [ $? -eq 0 ]; then
            success "pyinstaller 安装完成"
            HAS_PYINSTALLER=true
        else
            warn "pyinstaller 安装失败，将使用源码运行方式"
        fi
    else
        success "pyinstaller 已安装"
        HAS_PYINSTALLER=true
    fi
else
    python3 -c "import PyInstaller" &> /dev/null
    if [ $? -eq 0 ]; then
        success "pyinstaller 已安装"
        HAS_PYINSTALLER=true
    else
        warn "pyinstaller 未安装，将使用源码运行方式"
    fi
fi

# ============================================================
# 第二步：打包程序
# ============================================================

step_title "步骤 2/3：打包成单文件可执行程序"

BUILD_SUCCESS=false

if [ "$HAS_PYINSTALLER" = true ]; then
    if [ -f "$PROJECT_DIR/dist/$APP_NAME" ]; then
        echo ""
        echo "  检测到已打包的可执行文件:"
        echo "  $PROJECT_DIR/dist/$APP_NAME"
        echo ""
        read -p "  是否重新打包？(y/N): " rebuild
        echo ""
        if [[ "$rebuild" =~ ^[Yy]$ ]]; then
            DO_BUILD=true
        else
            DO_BUILD=false
            BUILD_SUCCESS=true
            success "使用已有的可执行文件"
        fi
    else
        DO_BUILD=true
    fi

    if [ "$DO_BUILD" = true ]; then
        info "开始打包（这可能需要几分钟，请耐心等待）..."
        echo ""

        cd "$PROJECT_DIR"

        python3 -m PyInstaller --noconfirm --onefile --windowed \
            --name "$APP_NAME" \
            --clean \
            --add-data "repos.yaml:." \
            --add-data "modules:modules" \
            "main.py"

        if [ $? -eq 0 ]; then
            chmod +x "$PROJECT_DIR/dist/$APP_NAME"
            BUILD_SUCCESS=true
            echo ""
            success "打包成功！"
            echo ""
            echo "  📦 输出文件: $PROJECT_DIR/dist/$APP_NAME"
            FILE_SIZE=$(du -h "$PROJECT_DIR/dist/$APP_NAME" | cut -f1)
            echo "  📏 文件大小: $FILE_SIZE"
        else
            echo ""
            warn "打包失败，将使用源码运行方式"
            echo "  （不影响使用，只是启动稍慢）"
        fi
    fi
else
    warn "PyInstaller 不可用，跳过打包"
    echo "  将使用源码运行方式"
fi

# ============================================================
# 第三步：创建桌面快捷方式
# ============================================================

step_title "步骤 3/3：创建桌面快捷方式"

# 确定执行路径
if [ "$BUILD_SUCCESS" = true ] && [ -f "$PROJECT_DIR/dist/$APP_NAME" ]; then
    EXEC_PATH="$PROJECT_DIR/dist/$APP_NAME"
    RUN_MODE="打包版"
elif [ -f "$PROJECT_DIR/$APP_NAME" ]; then
    EXEC_PATH="$PROJECT_DIR/$APP_NAME"
    RUN_MODE="打包版"
else
    EXEC_PATH="python3 $PROJECT_DIR/main.py"
    RUN_MODE="源码版"
fi

info "运行方式: $RUN_MODE"
info "执行命令: $EXEC_PATH"
echo ""

# 生成 .desktop 文件
ICON_PATH="$PROJECT_DIR/assets/app.png"
DESKTOP_CONTENT="[Desktop Entry]
Name=YOLO AutoInstaller
Comment=YOLO 全版本一键部署工具
Exec=$EXEC_PATH
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Development;Utility;
StartupNotify=true
Path=$PROJECT_DIR"

# 保存到项目目录
echo "$DESKTOP_CONTENT" > "$PROJECT_DIR/$APP_NAME.desktop"
chmod +x "$PROJECT_DIR/$APP_NAME.desktop"

# 复制到应用程序菜单
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
echo "$DESKTOP_CONTENT" > "$APPS_DIR/$APP_NAME.desktop"
chmod +x "$APPS_DIR/$APP_NAME.desktop"
success "已添加到应用程序菜单"

# 复制到桌面
DESKTOP_DIR=""
if [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
elif [ -d "$HOME/桌面" ]; then
    DESKTOP_DIR="$HOME/桌面"
fi

if [ -n "$DESKTOP_DIR" ]; then
    echo "$DESKTOP_CONTENT" > "$DESKTOP_DIR/$APP_NAME.desktop"
    chmod +x "$DESKTOP_DIR/$APP_NAME.desktop"
    success "已添加到桌面: $DESKTOP_DIR/$APP_NAME.desktop"
else
    warn "未找到桌面目录，已跳过桌面快捷方式"
fi

# ============================================================
# 完成
# ============================================================

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║      ✅  安装完成！                                      ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  💡 使用方法："
echo ""
echo "     📋 方式一：在应用程序菜单中搜索 'YOLO AutoInstaller'"
echo "     🖥️  方式二：双击桌面上的图标"
if [ "$BUILD_SUCCESS" = true ]; then
echo "     📦 方式三：直接运行: $PROJECT_DIR/dist/$APP_NAME"
else
echo "     🐍 方式三：直接运行: python3 $PROJECT_DIR/main.py"
fi
echo ""
echo "  📝 配置文件和日志将保存在程序运行目录"
echo ""

# 询问是否立即启动
read -p "  是否现在启动程序？(Y/n): " start_now
echo ""

if [[ ! "$start_now" =~ ^[Nn]$ ]]; then
    info "正在启动 YOLO AutoInstaller..."
    sleep 1

    if [ "$BUILD_SUCCESS" = true ] && [ -f "$PROJECT_DIR/dist/$APP_NAME" ]; then
        nohup "$PROJECT_DIR/dist/$APP_NAME" > /dev/null 2>&1 &
    else
        cd "$PROJECT_DIR"
        nohup python3 main.py > /dev/null 2>&1 &
    fi

    sleep 2
    success "程序已启动！"
fi

echo ""
echo "  👋 感谢使用 YOLO AutoInstaller！"
echo ""
