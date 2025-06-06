#!/bin/bash

# Chatterbox TTS 语音交互演示安装脚本
# 适用于 macOS 和 Linux 系统

echo "🚀 开始安装 Chatterbox TTS 语音交互演示..."
echo "=================================================="

# 检查 Python 版本
echo "🔍 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | grep -o "[0-9]\+\.[0-9]\+")
if [ $? -ne 0 ]; then
    echo "❌ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

echo "✅ Python 版本: $(python3 --version)"

# 检查 pip
echo "🔍 检查 pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ 未找到 pip3，请先安装 pip"
    exit 1
fi

echo "✅ pip 可用"

# 检查操作系统并安装系统依赖
echo "🔍 检查操作系统..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "✅ 检测到 macOS"
    
    # 检查是否安装了 Homebrew
    if ! command -v brew &> /dev/null; then
        echo "⚠️  未找到 Homebrew，正在安装..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    echo "📦 安装 portaudio (如果需要)..."
    brew install portaudio 2>/dev/null || echo "portaudio 可能已经安装"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✅ 检测到 Linux"
    
    # 检测发行版
    if command -v apt-get &> /dev/null; then
        echo "📦 安装系统依赖 (Ubuntu/Debian)..."
        sudo apt-get update
        sudo apt-get install -y portaudio19-dev python3-pyaudio
    elif command -v yum &> /dev/null; then
        echo "📦 安装系统依赖 (CentOS/RHEL)..."
        sudo yum install -y portaudio-devel
    elif command -v pacman &> /dev/null; then
        echo "📦 安装系统依赖 (Arch Linux)..."
        sudo pacman -S portaudio
    else
        echo "⚠️  无法自动安装系统依赖，请手动安装 portaudio"
    fi
else
    echo "⚠️  不支持的操作系统: $OSTYPE"
    echo "请手动安装 portaudio 依赖"
fi

# 创建虚拟环境 (可选)
read -p "🤔 是否创建 Python 虚拟环境？(y/N): " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    
    echo "🔧 激活虚拟环境..."
    source venv/bin/activate
    
    echo "✅ 虚拟环境已创建并激活"
    echo "💡 下次使用时请运行: source venv/bin/activate"
fi

# 升级 pip
echo "🔧 升级 pip..."
python3 -m pip install --upgrade pip

# 安装 Python 依赖
echo "📦 安装 Python 依赖包..."
pip3 install -r requirements.txt

# 检查 CUDA 支持
echo "🔍 检查 CUDA 支持..."
if command -v nvidia-smi &> /dev/null; then
    echo "✅ 检测到 NVIDIA GPU，建议安装 CUDA 版本的 PyTorch"
    echo "💡 如需 GPU 加速，请访问: https://pytorch.org/get-started/locally/"
else
    echo "ℹ️  未检测到 NVIDIA GPU，将使用 CPU 版本"
fi

# 测试导入
echo "🧪 测试关键库导入..."
python3 -c "
try:
    import torch
    import torchaudio
    import speech_recognition
    import pyaudio
    print('✅ 所有依赖库导入成功')
except ImportError as e:
    print(f'❌ 依赖库导入失败: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 安装完成！"
    echo "=================================================="
    echo "📖 使用说明："
    echo "1. 运行演示：python3 tts_demo.py"
    echo "2. 首次运行会下载 TTS 模型，请耐心等待"
    echo "3. 确保麦克风权限已开启"
    echo "4. 建议在安静环境中使用"
    echo ""
    echo "💡 如果遇到问题，请查看 README.md 文件"
else
    echo "❌ 安装过程中出现错误，请检查上述输出"
    exit 1
fi 