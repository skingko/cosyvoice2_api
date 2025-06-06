#!/bin/bash

# =============================================================================
# CosyVoice2 TTS API 一键安装脚本
# 支持 Windows(WSL)/macOS/Linux，自动检测系统环境并安装所需依赖
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if grep -q Microsoft /proc/version 2>/dev/null; then
            OS="wsl"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
    echo $OS
}

# 检测系统架构
detect_arch() {
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) echo "x64" ;;
        arm64|aarch64) echo "arm64" ;;
        *) echo "unknown" ;;
    esac
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查Python版本
check_python() {
    log_step "检查Python环境..."
    
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        log_error "未找到Python，请先安装Python 3.8+"
        return 1
    fi
    
    # 获取Python版本
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | grep -o "[0-9]\+\.[0-9]\+")
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    log_info "发现Python版本: $($PYTHON_CMD --version)"
    
    # 检查版本是否满足要求 (>= 3.8)
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        log_error "Python版本需要 >= 3.8，当前版本: $PYTHON_VERSION"
        return 1
    fi
    
    log_success "Python版本检查通过"
    return 0
}

# 检查pip
check_pip() {
    log_step "检查pip..."
    
    if command_exists pip3; then
        PIP_CMD="pip3"
    elif command_exists pip; then
        PIP_CMD="pip"
    else
        log_error "未找到pip，正在尝试安装..."
        $PYTHON_CMD -m ensurepip --upgrade
        PIP_CMD="$PYTHON_CMD -m pip"
    fi
    
    log_info "pip命令: $PIP_CMD"
    log_success "pip检查完成"
}

# 安装系统依赖
install_system_deps() {
    log_step "安装系统依赖..."
    
    OS=$(detect_os)
    case $OS in
        "linux"|"wsl")
            if command_exists apt-get; then
                log_info "检测到 Ubuntu/Debian 系统"
                sudo apt-get update
                sudo apt-get install -y \
                    build-essential \
                    git \
                    curl \
                    wget \
                    ffmpeg \
                    libsndfile1 \
                    libsndfile1-dev \
                    libasound2-dev \
                    portaudio19-dev \
                    python3-dev \
                    python3-pip
            elif command_exists yum; then
                log_info "检测到 CentOS/RHEL 系统"
                sudo yum groupinstall -y "Development Tools"
                sudo yum install -y \
                    git \
                    curl \
                    wget \
                    ffmpeg \
                    libsndfile-devel \
                    alsa-lib-devel \
                    portaudio-devel \
                    python3-devel \
                    python3-pip
            elif command_exists pacman; then
                log_info "检测到 Arch Linux 系统"
                sudo pacman -Sy --noconfirm \
                    base-devel \
                    git \
                    curl \
                    wget \
                    ffmpeg \
                    libsndfile \
                    alsa-lib \
                    portaudio \
                    python \
                    python-pip
            else
                log_warning "未识别的Linux发行版，请手动安装：git, curl, ffmpeg, libsndfile, portaudio"
            fi
            ;;
        "macos")
            log_info "检测到 macOS 系统"
            if command_exists brew; then
                brew install git curl wget ffmpeg libsndfile portaudio
            else
                log_warning "建议安装Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                log_warning "然后运行: brew install git curl wget ffmpeg libsndfile portaudio"
            fi
            ;;
        "windows")
            log_info "检测到 Windows 系统"
            log_warning "请确保已安装: Git, Visual Studio Build Tools, ffmpeg"
            ;;
        *)
            log_warning "未识别的操作系统，请手动安装系统依赖"
            ;;
    esac
    
    log_success "系统依赖安装完成"
}

# 创建虚拟环境
create_venv() {
    log_step "检查Python虚拟环境..."
    
    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        $PYTHON_CMD -m venv venv
    else
        log_info "虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    if [[ "$OS" == "windows" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    log_success "虚拟环境准备完成"
}

# 升级pip和基础工具
upgrade_pip() {
    log_step "升级pip和基础工具..."
    
    $PIP_CMD install --upgrade pip setuptools wheel
    log_success "pip升级完成"
}

# 安装PyTorch
install_pytorch() {
    log_step "安装PyTorch..."
    
    # 检测GPU支持
    GPU_SUPPORT="cpu"
    if command_exists nvidia-smi; then
        log_info "检测到NVIDIA GPU，将安装CUDA版本"
        GPU_SUPPORT="cu118"  # CUDA 11.8
    elif [[ "$OS" == "macos" ]]; then
        ARCH=$(detect_arch)
        if [[ "$ARCH" == "arm64" ]]; then
            log_info "检测到Apple Silicon Mac，将安装MPS版本"
            GPU_SUPPORT="cpu"  # MPS通过CPU版本支持
        fi
    fi
    
    # 安装PyTorch
    if [[ "$GPU_SUPPORT" == "cu118" ]]; then
        $PIP_CMD install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
        $PIP_CMD install torch torchaudio
    fi
    
    log_success "PyTorch安装完成"
}

# 安装项目依赖
install_requirements() {
    log_step "安装项目依赖..."
    
    if [ -f "requirements.txt" ]; then
        $PIP_CMD install -r requirements.txt
        log_success "requirements.txt安装完成"
    else
        log_error "未找到requirements.txt文件"
        return 1
    fi
}

# 克隆CosyVoice仓库
clone_cosyvoice() {
    log_step "克隆CosyVoice仓库..."
    
    if [ ! -d "CosyVoice" ]; then
        log_info "正在克隆CosyVoice仓库..."
        git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
        
        # 进入CosyVoice目录并安装
        cd CosyVoice
        $PIP_CMD install -e .
        cd ..
        
        log_success "CosyVoice仓库克隆并安装完成"
    else
        log_info "CosyVoice仓库已存在，正在更新..."
        cd CosyVoice
        git pull
        git submodule update --init --recursive
        $PIP_CMD install -e .
        cd ..
        log_success "CosyVoice更新完成"
    fi
}

# 验证安装
verify_installation() {
    log_step "验证安装..."
    
    # 测试Python导入
    if $PYTHON_CMD -c "import torch; import torchaudio; import transformers; print('✅ 核心库导入成功')"; then
        log_success "核心依赖验证通过"
    else
        log_error "核心依赖验证失败"
        return 1
    fi
    
    # 检查CosyVoice
    if [ -d "CosyVoice" ] && $PYTHON_CMD -c "import sys; sys.path.append('CosyVoice'); from cosyvoice.cli.model import CosyVoice; print('✅ CosyVoice导入成功')"; then
        log_success "CosyVoice验证通过"
    else
        log_warning "CosyVoice验证失败，可能需要手动安装"
    fi
}

# 创建启动脚本
create_start_script() {
    log_step "创建启动脚本..."
    
    cat > start_api.sh << 'EOF'
#!/bin/bash
# CosyVoice2 TTS API 启动脚本

echo "🚀 启动CosyVoice2 TTS API..."

# 激活虚拟环境
if [ -d "venv" ]; then
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
fi

# 检查模型
if [ ! -d "pretrained_models" ] || [ -z "$(ls -A pretrained_models 2>/dev/null)" ]; then
    echo "⚠️  请下载CosyVoice模型到pretrained_models目录"
    echo "推荐模型: CosyVoice2-0.5B"
    echo "下载地址: https://github.com/FunAudioLLM/CosyVoice"
fi

# 启动API服务
python main.py
EOF

    chmod +x start_api.sh
    log_success "启动脚本创建完成: start_api.sh"
}

# 显示安装完成信息
show_completion_info() {
    echo ""
    echo "🎉 CosyVoice2 TTS API 安装完成!"
    echo "========================================"
    echo ""
    echo "📋 下一步操作:"
    echo "1. 下载CosyVoice模型到 pretrained_models/ 目录"
    echo "   推荐: CosyVoice2-0.5B"
    echo "   下载: https://github.com/FunAudioLLM/CosyVoice"
    echo ""
    echo "2. 启动API服务:"
    echo "   ./start_api.sh"
    echo "   或者: python main.py"
    echo ""
    echo "3. 测试API:"
    echo "   python test_api.py"
    echo ""
    echo "4. 访问API文档:"
    echo "   http://localhost:8000/docs"
    echo ""
    echo "📚 更多信息请查看 README.md 和 API_DOCS.md"
    echo ""
}

# 主函数
main() {
    echo "🚀 CosyVoice2 TTS API 安装程序"
    echo "==============================="
    echo ""
    
    OS=$(detect_os)
    ARCH=$(detect_arch)
    log_info "检测到系统: $OS ($ARCH)"
    echo ""
    
    # 执行安装步骤
    check_python || exit 1
    check_pip || exit 1
    
    # 询问是否安装系统依赖
    read -p "是否安装系统依赖? (建议首次安装选择y) [y/N]: " install_sys_deps
    if [[ $install_sys_deps == "y" || $install_sys_deps == "Y" ]]; then
        install_system_deps
    fi
    
    create_venv
    upgrade_pip
    install_pytorch
    install_requirements
    clone_cosyvoice
    verify_installation
    create_start_script
    
    show_completion_info
    
    log_success "安装完成！"
}

# 错误处理
trap 'log_error "安装过程中发生错误，请检查上面的错误信息"' ERR

# 运行主函数
main "$@"