# CosyVoice2 TTS API 安装指南

## 🎯 快速开始

### 自动安装 (推荐)

#### Linux/macOS
```bash
chmod +x setup_cosyvoice.sh
./setup_cosyvoice.sh
```

#### Windows
```cmd
setup_cosyvoice.bat
```

### 手动安装

#### 1. 系统要求

- **Python**: 3.8 - 3.11
- **操作系统**: Windows 10/11, macOS 10.15+, Linux (Ubuntu 18.04+, CentOS 7+, Arch Linux)
- **内存**: 最低 8GB RAM (推荐 16GB+)
- **存储**: 至少 10GB 可用空间
- **GPU**: NVIDIA GPU (可选，支持CUDA 11.8+)

#### 2. 系统依赖

##### Ubuntu/Debian
```bash
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
```

##### CentOS/RHEL
```bash
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
```

##### Arch Linux
```bash
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
```

##### macOS
```bash
# 安装 Homebrew (如果未安装)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install git curl wget ffmpeg libsndfile portaudio
```

##### Windows
- 安装 [Git for Windows](https://git-scm.com/download/win)
- 安装 [Python 3.8+](https://python.org/downloads/)
- 安装 [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- 安装 FFmpeg:
  - 通过 [Chocolatey](https://chocolatey.org/): `choco install ffmpeg`
  - 通过 [Scoop](https://scoop.sh/): `scoop install ffmpeg`
  - 或者手动下载: [FFmpeg官网](https://ffmpeg.org/download.html)

#### 3. Python环境设置

##### 创建虚拟环境
```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

##### 升级基础工具
```bash
pip install --upgrade pip setuptools wheel
```

#### 4. 安装PyTorch

##### CPU版本 (适用于所有系统)
```bash
pip install torch torchaudio
```

##### GPU版本 (NVIDIA CUDA)
```bash
# CUDA 11.8
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### 5. 安装项目依赖
```bash
pip install -r requirements.txt
```

#### 6. 安装CosyVoice
```bash
# 克隆仓库
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git

# 安装CosyVoice
cd CosyVoice
pip install -e .
cd ..
```

#### 7. 下载预训练模型

创建模型目录并下载模型：
```bash
mkdir -p pretrained_models
cd pretrained_models

# 下载CosyVoice2-0.5B模型 (推荐)
# 请从官方GitHub或ModelScope下载
# https://github.com/FunAudioLLM/CosyVoice
```

## 🔧 配置说明

### GPU支持

#### NVIDIA GPU
确保安装了合适的CUDA版本和驱动：
```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查CUDA版本
nvcc --version
```

#### Apple Silicon (M1/M2/M3)
PyTorch自动支持MPS (Metal Performance Shaders)，无需额外配置。

### 环境变量

创建 `.env` 文件：
```bash
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 模型路径
COSYVOICE_MODEL_PATH=./pretrained_models/CosyVoice2-0.5B

# GPU设置
CUDA_VISIBLE_DEVICES=0  # 指定GPU设备
TORCH_DEVICE=auto       # auto, cpu, cuda, mps

# 日志级别
LOG_LEVEL=INFO

# 音频输出格式
DEFAULT_AUDIO_FORMAT=wav
AUDIO_SAMPLE_RATE=22050
```

## 🚀 启动服务

### 使用启动脚本
```bash
# Linux/macOS
./start_api.sh

# Windows
start_api.bat
```

### 手动启动
```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 启动API服务
python main.py
```

## 🧪 验证安装

### 运行测试
```bash
python test_api.py
```

### 访问API文档
打开浏览器访问: http://localhost:8000/docs

## 🛠️ 故障排除

### 常见问题

#### 1. Python版本不兼容
```bash
# 检查Python版本
python --version

# 如果版本 < 3.8，请升级Python
```

#### 2. PyTorch安装失败
```bash
# 清除缓存
pip cache purge

# 重新安装
pip uninstall torch torchaudio
pip install torch torchaudio
```

#### 3. CosyVoice导入失败
```bash
# 检查子模块
cd CosyVoice
git submodule update --init --recursive

# 重新安装
pip install -e .
```

#### 4. 音频库错误 (Linux)
```bash
# Ubuntu/Debian
sudo apt-get install libasound2-dev portaudio19-dev

# CentOS/RHEL
sudo yum install alsa-lib-devel portaudio-devel
```

#### 5. GPU不可用
```bash
# 检查PyTorch GPU支持
python -c "import torch; print(torch.cuda.is_available())"

# 检查MPS支持 (macOS)
python -c "import torch; print(torch.backends.mps.is_available())"
```

### 性能优化

#### 内存优化
```python
# 在config.py中设置
TORCH_COMPILE_ENABLED = True
MEMORY_FRACTION = 0.8  # 限制GPU内存使用
```

#### 并发设置
```python
# 根据系统配置调整
MAX_WORKERS = 4        # CPU核心数
MAX_BATCH_SIZE = 8     # 批处理大小
```

## 📦 容器化部署 (可选)

### Docker
```bash
# 构建镜像
docker build -t cosyvoice2-api .

# 运行容器
docker run -p 8000:8000 -v ./pretrained_models:/app/pretrained_models cosyvoice2-api
```

### Docker Compose
```yaml
version: '3.8'
services:
  cosyvoice2-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./pretrained_models:/app/pretrained_models
    environment:
      - CUDA_VISIBLE_DEVICES=0
```

## 🔄 更新

### 更新代码
```bash
git pull origin main
```

### 更新依赖
```bash
pip install -r requirements.txt --upgrade
```

### 更新CosyVoice
```bash
cd CosyVoice
git pull
git submodule update --init --recursive
pip install -e .
cd ..
```

## 📞 技术支持

如果遇到问题，请：

1. 查看 [API文档](API_DOCS.md)
2. 检查 [故障排除](#故障排除) 部分
3. 在 [GitHub Issues](https://github.com/skingko/cosyvoice2_api/issues) 提交问题
4. 提供详细的错误信息和系统信息

## 🎯 下一步

安装完成后，建议：

1. 阅读 [README.md](README.md) 了解项目概述
2. 查看 [API_DOCS.md](API_DOCS.md) 学习API使用
3. 运行 `python test_api.py` 验证功能
4. 根据需要调整 `config.py` 配置 