#!/bin/bash

# CosyVoice 2.0 中文语音交互演示安装脚本
# 适用于 macOS 和 Linux 系统

echo "🚀 开始安装 CosyVoice 2.0 中文语音交互演示..."
echo "======================================================="

# 检查 Python 版本
echo "🔍 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | grep -o "[0-9]\+\.[0-9]\+")
if [ $? -ne 0 ]; then
    echo "❌ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

echo "✅ Python 版本: $(python3 --version)"

# 检查是否在正确的 conda 环境中
if [[ "$CONDA_DEFAULT_ENV" != "pytorch" ]]; then
    echo "⚠️  建议在 pytorch 环境中运行"
    echo "请运行: conda activate pytorch"
    read -p "是否继续在当前环境安装？(y/N): " continue_install
    if [[ $continue_install != "y" && $continue_install != "Y" ]]; then
        echo "❌ 安装已取消"
        exit 1
    fi
fi

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
pip install torch>=2.0.0 torchaudio>=2.0.0
pip install transformers>=4.30.0 speechrecognition pyaudio numpy soundfile scipy librosa modelscope

echo "✅ Python 依赖安装完成"

# 克隆 CosyVoice 仓库
echo "📥 克隆 CosyVoice 仓库..."
if [ ! -d "CosyVoice" ]; then
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
    echo "✅ CosyVoice 仓库克隆成功"
else
    echo "✅ CosyVoice 仓库已存在"
fi

echo "🎉 CosyVoice 2.0 安装完成！"
echo "使用方法: python3 cosyvoice_demo.py"