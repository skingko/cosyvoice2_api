# CosyVoice2 TTS API 接口文档

## 概述

CosyVoice2 TTS API 提供强大的文本转语音服务，支持多种合成模式和灵活的配置选项。

## 基础信息

- **基础URL**: `http://localhost:8000`
- **API版本**: `v1`
- **数据格式**: `JSON` / `multipart/form-data`
- **认证**: 无需认证（可配置）

## 接口列表

### 1. 服务状态

#### GET `/api/v1/status`

获取API服务状态和能力信息。

**响应示例:**
```json
{
  "service": "CosyVoice2 TTS API",
  "version": "2.0.0",
  "status": "running",
  "engine": {
    "initialized": true,
    "capabilities": {
      "basic": true,
      "zero_shot": true,
      "cross_lingual": true,
      "instruct": true
    }
  }
}
```

### 2. 终极语音合成 (推荐)

#### POST `/api/v1/tts/ultimate`

智能语音合成接口，根据参数自动选择最佳合成模式。

**请求体 (JSON):**
```json
{
  "text": "要合成的文本",
  "mode": "auto",
  "language": "auto",
  "speed": 1.0,
  "speaker": "",
  "instruction": "",
  "seed": 42,
  "stream": false
}
```

**参数说明:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | ✅ | - | 要合成的文本 |
| `mode` | string | ❌ | `auto` | 合成模式: `auto`/`sft`/`zero_shot`/`cross_lingual`/`instruct2` |
| `language` | string | ❌ | `auto` | 语言: `zh`/`en`/`auto` |
| `speed` | float | ❌ | `1.0` | 语速: 0.5-2.0 |
| `speaker` | string | ❌ | `""` | 预设说话人 |
| `instruction` | string | ❌ | `""` | 自然语言指令（用于instruct2模式） |
| `seed` | integer | ❌ | `-1` | 随机种子，-1为随机 |
| `stream` | boolean | ❌ | `false` | 是否流式输出 |

**响应示例:**
```json
{
  "success": true,
  "message": "合成成功",
  "data": {
    "audio_url": "/outputs/abc123.wav",
    "audio_base64": "UklGRv...",
    "duration": 3.5,
    "sample_rate": 22050,
    "mode_used": "sft"
  }
}
```

### 3. 文件上传合成

#### POST `/api/v1/tts/ultimate-upload`

支持上传参考音频的语音合成接口，用于零样本音色克隆和跨语言合成。

**请求体 (multipart/form-data):**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | ✅ | 要合成的文本 |
| `reference_audio` | file | ✅ | 参考音频文件 |
| `prompt_text` | string | ❌ | 参考音频对应文本 |
| `mode` | string | ❌ | 合成模式 |
| `language` | string | ❌ | 目标语言 |
| `speed` | float | ❌ | 语速 |
| `instruction` | string | ❌ | 自然语言指令 |
| `speaker_name` | string | ❌ | 保存音色的名称 |

**cURL示例:**
```bash
curl -X POST "http://localhost:8000/api/v1/tts/ultimate-upload" \
  -F "text=这是克隆的声音测试" \
  -F "reference_audio=@reference.wav" \
  -F "prompt_text=参考音频的文本" \
  -F "mode=zero_shot"
```

## 合成模式详解

### 1. auto - 智能模式
自动根据输入参数选择最佳合成模式：
- 有参考音频 → `zero_shot`
- 有指令文本 → `instruct2`
- 跨语言 → `cross_lingual`
- 默认 → `sft`

### 2. sft - 基础合成
标准的文本转语音合成，质量高，速度快。

### 3. zero_shot - 零样本克隆
使用参考音频克隆音色，需要：
- 参考音频文件 (3-10秒为佳)
- 参考音频对应文本

### 4. cross_lingual - 跨语言合成
保持音色特征进行跨语言合成，需要：
- 参考音频
- 目标语言设置

### 5. instruct2 - 自然语言控制
使用自然语言指令控制合成效果：
```json
{
  "text": "今天天气真好",
  "instruction": "请用四川话，开心的语调来说"
}
```

## 情感标记

支持在文本中嵌入情感标记：

| 标记 | 效果 | 示例 |
|------|------|------|
| `[laughter]` | 笑声 | `这个笑话很好笑[laughter]` |
| `[breath]` | 换气 | `这是一个很长的句子[breath]需要换气` |

## 预设说话人

系统内置多个说话人音色：
- `中性` - 标准中性音色
- `男性` - 男性音色
- `女性` - 女性音色
- 更多音色详见API状态接口

## 语速控制

支持灵活的语速调节：
- **最慢**: 0.5倍速
- **正常**: 1.0倍速（默认）
- **最快**: 2.0倍速
- **建议**: 0.8-1.5倍速区间效果最佳

## 错误处理

### 常见错误码

| 状态码 | 错误类型 | 说明 |
|--------|----------|------|
| 400 | 参数错误 | 请求参数不正确 |
| 413 | 文件过大 | 上传文件超过大小限制 |
| 422 | 验证错误 | 数据验证失败 |
| 500 | 服务错误 | 内部服务错误 |

### 错误响应格式

```json
{
  "success": false,
  "message": "错误描述",
  "error_code": "ERROR_TYPE",
  "details": {
    "field": "具体错误信息"
  }
}
```

## 使用建议

### 1. 性能优化
- 文本长度控制在500字以内
- 参考音频时长3-10秒最佳
- 避免过高的并发请求

### 2. 音质优化
- 参考音频使用高质量WAV格式
- 确保参考音频清晰无噪音
- 参考文本与音频内容匹配

### 3. 批量处理
```python
import requests
import concurrent.futures

def synthesize_text(text):
    response = requests.post(
        "http://localhost:8000/api/v1/tts/ultimate",
        json={"text": text, "mode": "auto"}
    )
    return response.json()

texts = ["文本1", "文本2", "文本3"]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(synthesize_text, texts))
```

## Python SDK 示例

```python
import requests
import base64

class CosyVoiceTTS:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def synthesize(self, text, **kwargs):
        """基础合成"""
        data = {"text": text, **kwargs}
        response = requests.post(f"{self.base_url}/api/v1/tts/ultimate", json=data)
        return response.json()
    
    def clone_voice(self, text, audio_file, prompt_text=""):
        """音色克隆"""
        with open(audio_file, 'rb') as f:
            files = {"reference_audio": f}
            data = {"text": text, "prompt_text": prompt_text}
            response = requests.post(
                f"{self.base_url}/api/v1/tts/ultimate-upload",
                files=files, data=data
            )
        return response.json()
    
    def save_audio(self, audio_base64, filename):
        """保存音频"""
        audio_data = base64.b64decode(audio_base64)
        with open(filename, 'wb') as f:
            f.write(audio_data)

# 使用示例
tts = CosyVoiceTTS()

# 基础合成
result = tts.synthesize("你好世界", speed=1.2)
if result["success"]:
    tts.save_audio(result["data"]["audio_base64"], "output.wav")

# 音色克隆
result = tts.clone_voice("这是克隆的声音", "reference.wav", "参考文本")
```

## 更新日志

### v2.0.0
- ✅ 新增终极API接口
- ✅ 支持智能模式选择
- ✅ 增强情感控制
- ✅ 优化性能和稳定性

### v1.0.0
- ✅ 基础TTS功能
- ✅ 多种合成模式
- ✅ 文件上传支持

---

有问题？查看 [README.md](README.md) 或提交Issue。 