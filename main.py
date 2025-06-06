#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CosyVoice2 TTS API 服务
高性能语音合成API，专门针对CosyVoice2优化
支持REST API、WebSocket和Server-Sent Events (SSE)
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
# 认证相关导入已移除（简化版本不需要认证）
from fastapi import Depends
from pydantic import BaseModel, Field
import json
import random
import torch
import time

# 配置和服务
from config import get_config
from tts_service import (
    get_cosyvoice2_service, 
    TTSRequest, 
    TTSResult, 
    SynthesisMode, 
    AudioFormat,
    AudioFileHandler
)

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
config = get_config()

# FastAPI应用
app = FastAPI(
    title="CosyVoice2 TTS API",
    description="高性能语音合成API服务，基于CosyVoice2模型",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全配置（已禁用）
security = None  # 简化版本禁用认证

# 静态文件服务
if not os.path.exists(config.file.output_dir):
    os.makedirs(config.file.output_dir)
app.mount("/audio", StaticFiles(directory=config.file.output_dir), name="audio")

# 全局服务实例
tts_service = get_cosyvoice2_service()

# ===== API 模型定义 =====

class BasicTTSRequest(BaseModel):
    """基础TTS请求"""
    text: str = Field(..., description="要合成的文本", max_length=1000)
    speaker: Optional[str] = Field(None, description="说话人（可选）")
    language: str = Field("zh", description="语言代码")
    speed: float = Field(1.0, description="语速倍率", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="音频格式")
    sample_rate: Optional[int] = Field(None, description="采样率")

class ZeroShotTTSRequest(BaseModel):
    """零样本TTS请求"""
    text: str = Field(..., description="要合成的文本")
    prompt_text: str = Field(..., description="参考音频的文本内容")
    prompt_audio_url: Optional[str] = Field(None, description="参考音频URL")
    language: str = Field("zh", description="语言代码")
    speed: float = Field(1.0, description="语速倍率", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="音频格式")
    stream: bool = Field(False, description="是否流式传输")

class CrossLingualTTSRequest(BaseModel):
    """跨语言TTS请求"""
    text: str = Field(..., description="要合成的文本")
    prompt_audio_url: str = Field(..., description="参考音频URL")
    target_language: str = Field("zh", description="目标语言")
    speed: float = Field(1.0, description="语速倍率", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="音频格式")

class InstructTTSRequest(BaseModel):
    """指令式TTS请求"""
    text: str = Field(..., description="要合成的文本")
    instruct_text: str = Field(..., description="指令文本")
    speaker: Optional[str] = Field(None, description="说话人")
    speed: float = Field(1.0, description="语速倍率", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="音频格式")

class CustomSpeakerRequest(BaseModel):
    """自定义音色请求"""
    speaker_name: str = Field(..., description="音色名称")
    prompt_text: str = Field(..., description="参考音频的文本内容")
    prompt_audio_url: str = Field(..., description="参考音频URL")
    description: Optional[str] = Field(None, description="音色描述")

class TTSResponse(BaseModel):
    """TTS响应"""
    success: bool
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    sample_rate: Optional[int] = None
    request_id: Optional[str] = None
    error_message: Optional[str] = None

# ===== 认证和依赖 =====

async def verify_token():
    """验证API token（已禁用）"""
    return True

def get_auth_dependency():
    """获取认证依赖（已禁用）"""
    return None

auth_dependency = get_auth_dependency()

# ===== 工具函数 =====

def convert_result_to_response(result: TTSResult, request_id: str = None) -> TTSResponse:
    """转换TTSResult到TTSResponse"""
    if result.success and result.audio_file:
        # 生成音频访问URL
        filename = os.path.basename(result.audio_file)
        audio_url = f"/audio/{filename}"
        
        return TTSResponse(
            success=True,
            audio_url=audio_url,
            duration=result.duration,
            file_size=result.file_size,
            sample_rate=result.sample_rate,
            request_id=result.request_id or request_id
        )
    else:
        return TTSResponse(
            success=False,
            error_message=result.error_message,
            request_id=result.request_id or request_id
        )

# ===== 生命周期事件 =====

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("🚀 启动CosyVoice2 TTS API服务...")
    
    # 初始化TTS服务
    success = await tts_service.initialize()
    if not success:
        logger.error("❌ TTS服务初始化失败")
        raise RuntimeError("TTS服务初始化失败")
    
    logger.info("✅ CosyVoice2 TTS API服务启动成功")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("🔄 关闭TTS服务...")
    tts_service.cleanup()
    logger.info("✅ TTS服务关闭完成")

# ===== 基础API端点 =====

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "CosyVoice2 TTS API Service",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/api/v1/status")
async def get_status(auth: bool = auth_dependency):
    """获取服务状态"""
    status = tts_service.get_engine_status()
    return {
        "service": "CosyVoice2 TTS API",
        "version": "2.0.0",
        "status": "running" if status["initialized"] else "initializing",
        "engine": status,
        "available_speakers": tts_service.get_available_speakers()
    }

@app.get("/api/v1/speakers")
async def get_speakers(auth: bool = auth_dependency):
    """获取可用音色列表"""
    return {
        "speakers": tts_service.get_available_speakers(),
        "custom_speakers": tts_service.get_custom_speakers()
    }

# ===== TTS API端点 =====

@app.post("/api/v1/tts/basic", response_model=TTSResponse)
async def basic_tts(request: BasicTTSRequest, auth: bool = auth_dependency):
    """基础语音合成"""
    try:
        tts_request = TTSRequest(
            text=request.text,
            mode=SynthesisMode.BASIC,
            speaker=request.speaker,
            language=request.language,
            speed=request.speed,
            format=request.format,
            sample_rate=request.sample_rate
        )
        
        result = await tts_service.synthesize(tts_request)
        return convert_result_to_response(result)
        
    except Exception as e:
        logger.error(f"基础TTS失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tts/zero-shot", response_model=TTSResponse)
async def zero_shot_tts(request: ZeroShotTTSRequest, 
                       prompt_audio: Optional[UploadFile] = File(None),
                       auth: bool = auth_dependency):
    """零样本音色克隆"""
    try:
        # 处理音频输入
        prompt_audio_input = None
        if prompt_audio:
            audio_content = await prompt_audio.read()
            prompt_audio_input = audio_content
        elif request.prompt_audio_url:
            prompt_audio_input = request.prompt_audio_url
        else:
            raise HTTPException(status_code=400, detail="需要提供参考音频文件或URL")
        
        tts_request = TTSRequest(
            text=request.text,
            mode=SynthesisMode.ZERO_SHOT,
            prompt_text=request.prompt_text,
            prompt_audio=prompt_audio_input,
            language=request.language,
            speed=request.speed,
            format=request.format,
            stream=request.stream
        )
        
        if request.stream:
            # 流式响应
            return StreamingResponse(
                tts_service.synthesize_stream(tts_request),
                media_type="audio/wav"
            )
        else:
            result = await tts_service.synthesize(tts_request)
            return convert_result_to_response(result)
        
    except Exception as e:
        logger.error(f"零样本TTS失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tts/cross-lingual", response_model=TTSResponse)
async def cross_lingual_tts(request: CrossLingualTTSRequest,
                           prompt_audio: Optional[UploadFile] = File(None),
                           auth: bool = auth_dependency):
    """跨语言语音合成"""
    try:
        # 处理音频输入
        prompt_audio_input = None
        if prompt_audio:
            audio_content = await prompt_audio.read()
            prompt_audio_input = audio_content
        elif request.prompt_audio_url:
            prompt_audio_input = request.prompt_audio_url
        else:
            raise HTTPException(status_code=400, detail="需要提供参考音频文件或URL")
        
        tts_request = TTSRequest(
            text=request.text,
            mode=SynthesisMode.CROSS_LINGUAL,
            prompt_audio=prompt_audio_input,
            language=request.target_language,
            speed=request.speed,
            format=request.format
        )
        
        result = await tts_service.synthesize(tts_request)
        return convert_result_to_response(result)
        
    except Exception as e:
        logger.error(f"跨语言TTS失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tts/instruct", response_model=TTSResponse)
async def instruct_tts(request: InstructTTSRequest, auth: bool = auth_dependency):
    """指令式语音合成"""
    try:
        tts_request = TTSRequest(
            text=request.text,
            mode=SynthesisMode.INSTRUCT,
            instruct_text=request.instruct_text,
            speaker=request.speaker,
            speed=request.speed,
            format=request.format
        )
        
        result = await tts_service.synthesize(tts_request)
        return convert_result_to_response(result)
        
    except Exception as e:
        logger.error(f"指令式TTS失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 自定义音色管理 =====

@app.post("/api/v1/speakers/custom")
async def add_custom_speaker(request: CustomSpeakerRequest,
                           prompt_audio: Optional[UploadFile] = File(None),
                           auth: bool = auth_dependency):
    """添加自定义音色"""
    try:
        # 处理音频输入
        prompt_audio_input = None
        if prompt_audio:
            audio_content = await prompt_audio.read()
            prompt_audio_input = audio_content
        elif request.prompt_audio_url:
            prompt_audio_input = request.prompt_audio_url
        else:
            raise HTTPException(status_code=400, detail="需要提供参考音频文件或URL")
        
        result = await tts_service.add_custom_speaker(
            speaker_name=request.speaker_name,
            prompt_text=request.prompt_text,
            prompt_audio=prompt_audio_input,
            description=request.description
        )
        
        return result
        
    except Exception as e:
        logger.error(f"添加自定义音色失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/speakers/custom")
async def get_custom_speakers(auth: bool = auth_dependency):
    """获取自定义音色列表"""
    return {
        "custom_speakers": tts_service.get_custom_speakers()
    }

@app.delete("/api/v1/speakers/custom/{speaker_id}")
async def delete_custom_speaker(speaker_id: str, auth: bool = auth_dependency):
    """删除自定义音色"""
    try:
        result = await tts_service.delete_custom_speaker(speaker_id)
        return result
        
    except Exception as e:
        logger.error(f"删除自定义音色失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 全能TTS API =====

class UltimateTTSRequest(BaseModel):
    """全能TTS请求 - 支持CosyVoice2所有功能"""
    text: str = Field(..., description="要合成的文本")
    
    # 模式选择
    mode: str = Field("auto", description="合成模式: auto/sft/zero_shot/cross_lingual/instruct2")
    
    # 基础控制
    language: str = Field("zh", description="目标语言代码")
    speed: float = Field(1.0, description="语速倍率", ge=0.5, le=2.0)
    
    # 音色控制
    speaker: Optional[str] = Field(None, description="预训练音色ID（SFT模式）")
    
    # 零样本音色克隆
    prompt_text: Optional[str] = Field(None, description="参考音频的文本内容")
    prompt_audio_url: Optional[str] = Field(None, description="参考音频URL")
    
    # 自然语言指令控制（方言、情感等）
    instruct_text: Optional[str] = Field(None, description="自然语言指令，如'用四川话说'、'开心地说'、'低沉的声音'等")
    
    # 情感和风格控制（文本内标记）
    enable_emotion_markers: bool = Field(True, description="启用文本内情感标记如[laughter]")
    
    # 音频格式和质量
    format: AudioFormat = Field(AudioFormat.WAV, description="音频格式")
    sample_rate: Optional[int] = Field(None, description="采样率")
    
    # 流式控制
    stream: bool = Field(False, description="是否流式传输")
    
    # 高级控制
    seed: Optional[int] = Field(None, description="随机种子，用于可重现的合成")
    text_frontend: bool = Field(True, description="是否启用文本前端处理")
    
    # 音色存储和复用
    save_speaker_id: Optional[str] = Field(None, description="保存音色的ID，用于后续复用")
    use_saved_speaker: Optional[str] = Field(None, description="使用已保存的音色ID")

@app.post("/api/v1/tts/ultimate", response_model=TTSResponse)
async def ultimate_tts(request: UltimateTTSRequest, auth: bool = auth_dependency):
    """
    🚀 全能TTS API (纯JSON) - 支持CosyVoice2所有功能
    """
    return await _ultimate_tts_impl(request, None, auth)

@app.post("/api/v1/tts/ultimate-upload", response_model=TTSResponse)
async def ultimate_tts_with_upload(
    text: str = Form(...),
    mode: str = Form("auto"),
    language: str = Form("zh"),
    speed: float = Form(1.0),
    speaker: Optional[str] = Form(None),
    prompt_text: Optional[str] = Form(None),
    prompt_audio_url: Optional[str] = Form(None),
    instruct_text: Optional[str] = Form(None),
    enable_emotion_markers: bool = Form(True),
    format: str = Form("wav"),
    sample_rate: Optional[int] = Form(None),
    stream: bool = Form(False),
    seed: Optional[int] = Form(None),
    text_frontend: bool = Form(True),
    save_speaker_id: Optional[str] = Form(None),
    use_saved_speaker: Optional[str] = Form(None),
    prompt_audio: Optional[UploadFile] = File(None),
    auth: bool = auth_dependency
):
    """
    🚀 全能TTS API (带文件上传) - 支持CosyVoice2所有功能
    """
    # 构建UltimateTTSRequest对象
    try:
        audio_format = AudioFormat(format.lower())
    except ValueError:
        audio_format = AudioFormat.WAV
    
    request = UltimateTTSRequest(
        text=text,
        mode=mode,
        language=language,
        speed=speed,
        speaker=speaker,
        prompt_text=prompt_text,
        prompt_audio_url=prompt_audio_url,
        instruct_text=instruct_text,
        enable_emotion_markers=enable_emotion_markers,
        format=audio_format,
        sample_rate=sample_rate,
        stream=stream,
        seed=seed,
        text_frontend=text_frontend,
        save_speaker_id=save_speaker_id,
        use_saved_speaker=use_saved_speaker
    )
    
    return await _ultimate_tts_impl(request, prompt_audio, auth)

async def _ultimate_tts_impl(request: UltimateTTSRequest, 
                            prompt_audio: Optional[UploadFile] = None,
                            auth: bool = None):
    """
    🚀 全能TTS API 实现 - 支持CosyVoice2所有功能
    
    功能包括：
    - 自动模式选择
    - 多语言合成
    - 零样本音色克隆
    - 跨语言合成  
    - 自然语言指令控制（方言、情感等）
    - 文本内情感标记
    - 语速控制
    - 流式合成
    - 音色保存和复用
    """
    try:
        # 设置随机种子
        if request.seed is not None:
            random.seed(request.seed)
            torch.manual_seed(request.seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(request.seed)
        
        # 处理音频输入
        prompt_audio_input = None
        if prompt_audio:
            audio_content = await prompt_audio.read()
            prompt_audio_input = audio_content
        elif request.prompt_audio_url:
            prompt_audio_input = request.prompt_audio_url
        
        # 自动模式选择逻辑
        auto_mode = request.mode
        if request.mode == "auto":
            # 智能选择最适合的模式
            if request.instruct_text and prompt_audio_input:
                auto_mode = "instruct2"  # CosyVoice2的自然语言控制
            elif request.prompt_text and prompt_audio_input:
                # 检查是否为跨语言场景
                if request.language != "zh" or is_different_language(request.text, request.prompt_text):
                    auto_mode = "cross_lingual"
                else:
                    auto_mode = "zero_shot"
            elif request.speaker:
                auto_mode = "sft"  # 预训练音色
            else:
                auto_mode = "basic"  # 基础模式，不需要参考音频
        
        # 映射模式名称到SynthesisMode枚举
        mode_mapping = {
            "auto": SynthesisMode.BASIC,
            "sft": SynthesisMode.BASIC,  # SFT模式映射到BASIC
            "zero_shot": SynthesisMode.ZERO_SHOT,
            "cross_lingual": SynthesisMode.CROSS_LINGUAL,
            "instruct": SynthesisMode.INSTRUCT,
            "instruct2": SynthesisMode.INSTRUCT2,
            "voice_conversion": SynthesisMode.VOICE_CONVERSION
        }
        
        synthesis_mode = mode_mapping.get(auto_mode, SynthesisMode.BASIC)
        
        # 构建TTS请求
        tts_request = TTSRequest(
            text=request.text,
            mode=synthesis_mode,
            speaker=request.speaker,
            language=request.language,
            speed=request.speed,
            format=request.format,
            sample_rate=request.sample_rate,
            prompt_text=request.prompt_text,
            prompt_audio=prompt_audio_input,
            instruct_text=request.instruct_text,
            stream=request.stream,
            text_frontend=request.text_frontend
        )
        
        # 处理音色保存
        if request.save_speaker_id and prompt_audio_input and request.prompt_text:
            await tts_service.add_zero_shot_speaker(
                speaker_id=request.save_speaker_id,
                prompt_text=request.prompt_text,
                prompt_audio=prompt_audio_input
            )
        
        # 处理已保存音色
        if request.use_saved_speaker:
            tts_request.zero_shot_spk_id = request.use_saved_speaker
            # 清除prompt信息，使用保存的音色
            tts_request.prompt_text = ""
            tts_request.prompt_audio = None
        
        if request.stream:
            # 流式响应
            return StreamingResponse(
                tts_service.synthesize_stream(tts_request),
                media_type="audio/wav",
                headers={
                    "X-TTS-Mode": auto_mode,
                    "X-TTS-Language": request.language,
                    "X-TTS-Speed": str(request.speed)
                }
            )
        else:
            # 标准响应
            result = await tts_service.synthesize(tts_request)
            
            # 添加元数据
            response = convert_result_to_response(result)
            response.request_id = f"ultimate_{auto_mode}_{int(time.time())}"
            
            return response
            
    except Exception as e:
        logger.error(f"全能TTS失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def is_different_language(text1: str, text2: str) -> bool:
    """简单的语言检测，判断两个文本是否为不同语言"""
    import re
    
    # 检测中文
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    has_chinese_1 = bool(chinese_pattern.search(text1))
    has_chinese_2 = bool(chinese_pattern.search(text2))
    
    # 检测英文
    english_pattern = re.compile(r'[a-zA-Z]')
    has_english_1 = bool(english_pattern.search(text1))
    has_english_2 = bool(english_pattern.search(text2))
    
    # 简单判断：如果一个主要是中文，另一个主要是英文，则认为是不同语言
    if (has_chinese_1 and not has_english_1) and (has_english_2 and not has_chinese_2):
        return True
    if (has_english_1 and not has_chinese_1) and (has_chinese_2 and not has_english_2):
        return True
    
    return False

# ===== 通用流式端点 =====

@app.post("/api/v1/tts/stream")
async def universal_tts_stream(request: BasicTTSRequest, auth: bool = auth_dependency):
    """通用流式TTS端点，支持所有模式"""
    
    async def stream_generator():
        try:
            # 构建TTS请求
            tts_request = TTSRequest(
                text=request.text,
                mode=SynthesisMode.BASIC,  # 默认基础模式
                speaker=request.speaker,
                language=request.language,
                speed=request.speed,
                format=request.format,
                stream=True
            )
            
            # 流式合成并返回原始音频数据
            async for audio_chunk in tts_service.synthesize_stream(tts_request):
                yield audio_chunk
            
        except Exception as e:
            logger.error(f"流式合成失败: {e}")
            # 对于二进制流，我们无法发送错误消息
            return
    
    return StreamingResponse(stream_generator(), media_type="audio/wav")

# ===== WebSocket流式API =====

@app.websocket("/api/v1/tts/ws")
async def websocket_tts_stream(websocket: WebSocket):
    """WebSocket流式TTS"""
    await websocket.accept()
    
    try:
        while True:
            # 接收请求
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            # 验证请求
            if "text" not in request_data:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "缺少必要的text参数"
                }))
                continue
            
            # 构建TTS请求
            tts_request = TTSRequest(
                text=request_data["text"],
                mode=SynthesisMode(request_data.get("mode", "basic")),
                speaker=request_data.get("speaker"),
                language=request_data.get("language", "zh"),
                speed=request_data.get("speed", 1.0),
                format=AudioFormat(request_data.get("format", "wav")),
                prompt_text=request_data.get("prompt_text"),
                prompt_audio=request_data.get("prompt_audio_url"),
                instruct_text=request_data.get("instruct_text"),
                stream=True
            )
            
            # 流式合成
            try:
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "message": "开始合成..."
                }))
                
                async for audio_chunk in tts_service.synthesize_stream(tts_request):
                    # 发送音频块（Base64编码）
                    import base64
                    audio_b64 = base64.b64encode(audio_chunk).decode()
                    await websocket.send_text(json.dumps({
                        "type": "audio_chunk",
                        "data": audio_b64
                    }))
                
                await websocket.send_text(json.dumps({
                    "type": "end",
                    "message": "合成完成"
                }))
                
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"合成失败: {str(e)}"
                }))
    
    except WebSocketDisconnect:
        logger.info("WebSocket客户端断开连接")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            }))
        except:
            pass

# ===== Server-Sent Events (SSE) API =====

@app.post("/api/v1/tts/sse")
async def sse_tts_stream(request: ZeroShotTTSRequest, auth: bool = auth_dependency):
    """Server-Sent Events流式TTS"""
    
    async def event_generator():
        try:
            # 构建TTS请求
            tts_request = TTSRequest(
                text=request.text,
                mode=SynthesisMode.ZERO_SHOT,
                prompt_text=request.prompt_text,
                prompt_audio=request.prompt_audio_url,
                language=request.language,
                speed=request.speed,
                format=request.format,
                stream=True
            )
            
            yield f"data: {json.dumps({'status': 'processing', 'message': '开始合成...'})}\n\n"
            
            async for audio_chunk in tts_service.synthesize_stream(tts_request):
                # 发送音频块（Base64编码）
                import base64
                audio_b64 = base64.b64encode(audio_chunk).decode()
                yield f"data: {json.dumps({'type': 'audio_chunk', 'data': audio_b64})}\n\n"
            
            yield f"data: {json.dumps({'status': 'completed', 'message': '合成完成'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': f'合成失败: {str(e)}'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ===== 健康检查 =====

@app.get("/health")
async def health_check():
    """健康检查"""
    status = tts_service.get_engine_status()
    return {
        "status": "healthy" if status["initialized"] else "unhealthy",
        "timestamp": str(asyncio.get_event_loop().time())
    }

if __name__ == "__main__":
    # 运行服务
    uvicorn.run(
        "main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        workers=1,  # CosyVoice2不支持多worker
        log_level="info"
    )