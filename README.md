# CosyVoice2 TTS API

> 基于CosyVoice2的高性能文本转语音API服务

## 🌟 特性

- ✅ **多种合成模式**：基础合成、零样本音色克隆、跨语言合成、自然语言控制
- 🎯 **智能模式选择**：根据输入参数自动选择最佳合成模式
- 🎭 **情感控制**：支持情感标记 `[laughter]`、`[breath]` 等
- 🌍 **多语言支持**：中文、英文及跨语言合成
- ⚡ **高性能**：GPU加速，并发处理，流式输出
- 🔧 **灵活配置**：语速控制、音色保存、批量处理

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd chat_tts_api

# 安装依赖
pip install -r requirements.txt

# 设置CosyVoice环境
bash setup_cosyvoice.sh
```

### 2. 模型下载

将CosyVoice2模型放到 `pretrained_models/` 目录：

```
pretrained_models/
├── CosyVoice2-0.5B/           # 推荐
├── CosyVoice-300M-Instruct/   # 备选
└── CosyVoice-300M/            # 备选
```

### 3. 启动服务

```bash
python main.py
```

服务启动后访问：
- API服务：http://localhost:8000
- API文档：http://localhost:8000/docs

## 📖 API使用指南

### 基础语音合成

```bash
curl -X POST "http://localhost:8000/api/v1/tts/ultimate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，这是语音合成测试。",
    "mode": "auto",
    "language": "zh"
  }'
```

### 零样本音色克隆

```bash
curl -X POST "http://localhost:8000/api/v1/tts/ultimate-upload" \
  -F "reference_audio=@reference.wav" \
  -F "text=这是克隆的声音" \
  -F "prompt_text=参考音频的文本内容"
```

### 情感控制

```bash
curl -X POST "http://localhost:8000/api/v1/tts/ultimate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这个笑话真好笑[laughter]，让我笑一下。",
    "mode": "auto"
  }'
```

### 语速控制

```bash
curl -X POST "http://localhost:8000/api/v1/tts/ultimate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是语速控制测试",
    "speed": 1.5,
    "mode": "auto"
  }'
```

## 🔧 参数说明

### 主要参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `text` | string | 要合成的文本 | **必填** |
| `mode` | string | 合成模式：`auto`/`sft`/`zero_shot`/`cross_lingual`/`instruct2` | `auto` |
| `language` | string | 语言：`zh`/`en`/`auto` | `auto` |
| `speed` | float | 语速：0.5-2.0 | 1.0 |
| `speaker` | string | 预设说话人 | 随机 |

### 合成模式

- **auto**：智能选择最佳模式
- **sft**：基础合成模式
- **zero_shot**：零样本音色克隆（需上传参考音频）
- **cross_lingual**：跨语言合成
- **instruct2**：自然语言控制

### 情感标记

支持的情感标记：
- `[laughter]` - 笑声
- `[breath]` - 换气
- 更多标记详见CosyVoice2官方文档

## 🧪 测试

运行核心功能测试：

```bash
python test_api.py
```

## ⚙️ 配置

### 环境变量

```bash
export COSYVOICE_HOST=0.0.0.0
export COSYVOICE_PORT=8000
export COSYVOICE_DEVICE=auto
export COSYVOICE_MODEL_PATH=pretrained_models/CosyVoice2-0.5B
```

### 配置文件

主要配置在 `config.py` 中：

```python
# API配置
host = "0.0.0.0"
port = 8000

# 模型配置
model_path = "pretrained_models/CosyVoice2-0.5B"
device = "auto"  # auto/cpu/cuda/mps

# 性能配置
max_concurrent_requests = 4
request_timeout = 300
```

## 📁 项目结构

```
chat_tts_api/
├── main.py              # API服务入口
├── tts_service.py       # TTS核心服务
├── config.py            # 配置文件
├── test_api.py          # API测试
├── requirements.txt     # 依赖包
├── setup_cosyvoice.sh   # 环境设置脚本
├── CosyVoice/          # CosyVoice源码
├── pretrained_models/   # 预训练模型
├── outputs/            # 音频输出
├── temp/               # 临时文件
└── uploads/            # 上传文件
```

## 🔍 常见问题

### Q: 模型加载失败？
A: 确保模型文件完整，检查路径配置，确认有足够的内存。

### Q: 合成速度慢？
A: 检查GPU是否可用，调整并发数，使用更小的模型。

### Q: 音色克隆效果不好？
A: 确保参考音频清晰，时长3-10秒，语言匹配。

### Q: API请求超时？
A: 调整 `request_timeout` 配置，检查文本长度。

## 📄 许可证

本项目基于MIT许可证开源。

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

📧 如有问题，请联系项目维护者。