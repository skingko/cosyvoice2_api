#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CosyVoice2 专用TTS服务
优化的高性能语音合成服务，专门针对CosyVoice2模型进行优化
"""

import asyncio
import os
import sys
import uuid
import tempfile
import json
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, AsyncGenerator, Union, Any
from dataclasses import dataclass
from enum import Enum
import logging
import librosa

# 添加CosyVoice模块路径
sys.path.append('CosyVoice')

# 音频处理
import torch
import torchaudio
import numpy as np

# 网络请求
import aiohttp
import aiofiles

# 配置
from config import get_config

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioFormat(Enum):
    """音频格式枚举"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"

class SynthesisMode(Enum):
    """合成模式枚举"""
    BASIC = "basic"           # 基础合成
    ZERO_SHOT = "zero_shot"   # 零样本音色克隆
    CROSS_LINGUAL = "cross_lingual"  # 跨语言合成
    INSTRUCT = "instruct"     # 指令式合成
    INSTRUCT2 = "instruct2"   # CosyVoice2自然语言控制
    VOICE_CONVERSION = "voice_conversion"  # 语音转换

@dataclass
class TTSRequest:
    """TTS请求类"""
    def __init__(self, text: str, mode: SynthesisMode = SynthesisMode.BASIC,
                 speaker: str = None, language: str = "zh", speed: float = 1.0,
                 format: AudioFormat = AudioFormat.WAV, sample_rate: int = None,
                 prompt_text: str = None, prompt_audio = None, instruct_text: str = None,
                 stream: bool = False, text_frontend: bool = True, zero_shot_spk_id: str = "",
                 seed: int = None):
        self.text = text
        self.mode = mode
        self.speaker = speaker
        self.language = language
        self.speed = speed
        self.format = format
        self.sample_rate = sample_rate or 22050
        self.prompt_text = prompt_text
        self.prompt_audio = prompt_audio
        self.instruct_text = instruct_text
        self.stream = stream
        self.text_frontend = text_frontend
        self.zero_shot_spk_id = zero_shot_spk_id
        self.seed = seed

@dataclass
class TTSResult:
    """TTS 结果数据类"""
    success: bool
    audio_file: Optional[str] = None
    audio_data: Optional[bytes] = None  # 用于流式传输
    duration: Optional[float] = None
    file_size: Optional[int] = None
    sample_rate: Optional[int] = None
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    mode_used: Optional[SynthesisMode] = None
    speaker_used: Optional[str] = None

class AudioFileHandler:
    """音频文件处理器"""
    
    @staticmethod
    async def process_audio_input(audio_input: Union[str, bytes, Path]) -> str:
        """
        处理音频输入，统一转换为本地文件路径
        支持: 本地文件路径、网络URL、字节数据
        """
        if isinstance(audio_input, (str, Path)):
            audio_path = str(audio_input)
            
            # 检查是否为网络URL
            if audio_path.startswith(('http://', 'https://')):
                return await AudioFileHandler._download_audio(audio_path)
            
            # 检查是否为本地文件
            elif os.path.exists(audio_path):
                return os.path.abspath(audio_path)
            
            else:
                raise ValueError(f"音频文件不存在: {audio_path}")
        
        elif isinstance(audio_input, bytes):
            return await AudioFileHandler._save_audio_bytes(audio_input)
        
        else:
            raise ValueError(f"不支持的音频输入类型: {type(audio_input)}")

    @staticmethod
    async def _download_audio(url: str) -> str:
        """下载网络音频文件"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # 从URL或Content-Type推断文件扩展名
                        content_type = response.headers.get('content-type', '')
                        extension = mimetypes.guess_extension(content_type) or '.wav'
                        
                        # 创建临时文件
                        temp_file = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
                        async with aiofiles.open(temp_file.name, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        logger.info(f"音频下载成功: {url} -> {temp_file.name}")
                        return temp_file.name
                    else:
                        raise ValueError(f"下载失败: HTTP {response.status}")
        except Exception as e:
            raise ValueError(f"音频下载失败: {e}")

    @staticmethod
    async def _save_audio_bytes(audio_data: bytes) -> str:
        """保存音频字节数据到临时文件"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        async with aiofiles.open(temp_file.name, 'wb') as f:
            await f.write(audio_data)
        
        logger.info(f"音频数据保存成功: {len(audio_data)} 字节 -> {temp_file.name}")
        return temp_file.name

    @staticmethod
    def validate_audio_file(file_path: str) -> bool:
        """验证音频文件格式和质量"""
        try:
            waveform, sample_rate = torchaudio.load(file_path)
            
            # 检查基本参数
            if waveform.numel() == 0:
                return False
            
            # 检查时长 (建议3-30秒)
            duration = waveform.shape[1] / sample_rate
            if not (1.0 <= duration <= 60.0):
                logger.warning(f"音频时长异常: {duration:.2f}秒")
            
            return True
        except Exception as e:
            logger.error(f"音频文件验证失败: {e}")
            return False

    @staticmethod
    def load_wav(wav_path: str, target_sr: int = 16000):
        """
        加载音频文件 - 使用官方CosyVoice的方法
        参考: CosyVoice/cosyvoice/utils/file_utils.py::load_wav
        """
        try:
            import torchaudio
            
            speech, sample_rate = torchaudio.load(wav_path, backend='soundfile')
            speech = speech.mean(dim=0, keepdim=True)
            if sample_rate != target_sr:
                assert sample_rate > target_sr, f'wav sample rate {sample_rate} must be greater than {target_sr}'
                speech = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=target_sr)(speech)
            return speech
            
        except Exception as e:
            logger.error(f"音频文件加载失败: {e}")
            raise ValueError(f"音频文件加载失败: {str(e)}")

    @staticmethod
    def postprocess(speech, top_db=60, hop_length=220, win_length=440, max_val=0.8):
        """
        音频后处理 - 使用官方CosyVoice的方法
        参考: CosyVoice/webui.py::postprocess
        """
        try:
            import librosa
            import torch
            
            speech, _ = librosa.effects.trim(
                speech, top_db=top_db,
                frame_length=win_length,
                hop_length=hop_length
            )
            if speech.abs().max() > max_val:
                speech = speech / speech.abs().max() * max_val
            
            # 注意：这里不添加尾部静音，因为我们是用作参考音频
            return speech
            
        except Exception as e:
            logger.error(f"音频后处理失败: {e}")
            raise ValueError(f"音频后处理失败: {str(e)}")

    @staticmethod
    def load_audio_data(file_path: str, target_sample_rate: int = 16000):
        """加载并处理音频文件为CosyVoice2期望的格式"""
        try:
            # 使用官方的方法加载音频
            speech = AudioFileHandler.load_wav(file_path, target_sample_rate)
            
            # 使用官方的后处理方法
            speech = AudioFileHandler.postprocess(speech)
            
            return speech
            
        except Exception as e:
            logger.error(f"音频文件加载失败: {e}")
            raise ValueError(f"音频文件加载失败: {str(e)}")

class CosyVoice2Engine:
    """CosyVoice2 引擎 - 专门优化的高性能实现"""
    
    def __init__(self):
        self.config = get_config()
        self.cosyvoice = None
        self.model_type = None
        self.is_initialized = False
        self.capabilities = {
            'basic': False,
            'zero_shot': False,
            'cross_lingual': False,
            'instruct': False
        }
        
        # 性能优化
        self._audio_cache = {}  # 音频缓存
        self._speaker_cache = {}  # 说话人特征缓存
    
    async def initialize(self) -> bool:
        """初始化CosyVoice2引擎"""
        try:
            logger.info("🚀 初始化CosyVoice2引擎...")
            
            # 导入CosyVoice
            from cosyvoice.cli.cosyvoice import CosyVoice2
            
            model_path = self.config.cosyvoice.model_path
            logger.info(f"📁 加载模型: {model_path}")
            
            # 异步加载模型
            def _load_model():
                return CosyVoice2(model_path)
            
            self.cosyvoice = await asyncio.get_event_loop().run_in_executor(
                None, _load_model
            )
            
            # 检测模型能力
            self._detect_capabilities()
            
            self.is_initialized = True
            logger.info("✅ CosyVoice2引擎初始化成功")
            logger.info(f"🎯 支持的功能: {list(k for k, v in self.capabilities.items() if v)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ CosyVoice2引擎初始化失败: {e}")
            return False
    
    def _detect_capabilities(self):
        """检测模型支持的功能"""
        try:
            # CosyVoice2支持所有功能
            self.capabilities['basic'] = True
            self.capabilities['zero_shot'] = hasattr(self.cosyvoice, 'inference_zero_shot')
            self.capabilities['cross_lingual'] = hasattr(self.cosyvoice, 'inference_cross_lingual')
            
            # CosyVoice2使用inference_instruct2
            self.capabilities['instruct'] = hasattr(self.cosyvoice, 'inference_instruct2')
            
        except Exception as e:
            logger.error(f"功能检测失败: {e}")
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """主合成方法 - 根据模式分发到不同的处理函数"""
        if not self.is_initialized:
            return TTSResult(
                success=False,
                error_message="引擎未初始化",
                request_id=str(uuid.uuid4())
            )
        
        request_id = str(uuid.uuid4())
        
        try:
            # 处理参考音频
            if request.prompt_audio:
                prompt_audio_path = await AudioFileHandler.process_audio_input(request.prompt_audio)
                
                # 验证音频文件
                if not AudioFileHandler.validate_audio_file(prompt_audio_path):
                    return TTSResult(
                        success=False,
                        error_message="参考音频文件格式无效",
                        request_id=request_id
                    )
            else:
                prompt_audio_path = None
            
            # 根据合成模式选择处理方法
            if request.mode == SynthesisMode.BASIC:
                result = await self._basic_synthesis(request, request_id)
            elif request.mode == SynthesisMode.ZERO_SHOT:
                result = await self._zero_shot_synthesis(request, request_id, prompt_audio_path)
            elif request.mode == SynthesisMode.CROSS_LINGUAL:
                result = await self._cross_lingual_synthesis(request, request_id, prompt_audio_path)
            elif request.mode == SynthesisMode.INSTRUCT:
                result = await self._instruct_synthesis(request, request_id)
            elif request.mode == SynthesisMode.INSTRUCT2:
                result = await self._instruct2_synthesis(request, request_id)
            elif request.mode == SynthesisMode.VOICE_CONVERSION:
                result = await self._voice_conversion(request, request_id)
            else:
                return TTSResult(
                    success=False,
                    error_message=f"不支持的合成模式: {request.mode}",
                    request_id=request_id
                )
            
            # 清理临时文件
            if prompt_audio_path and prompt_audio_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(prompt_audio_path)
                except:
                    pass
            
            return result
            
        except Exception as e:
            logger.error(f"合成失败: {e}")
            return TTSResult(
                success=False,
                error_message=f"合成失败: {str(e)}",
                request_id=request_id
            )
    
    async def _basic_synthesis(self, request: TTSRequest, request_id: str) -> TTSResult:
        """基础语音合成 - 对于CosyVoice2，这实际上是零样本合成的默认版本"""
        def _synthesize():
            # CosyVoice2没有预定义说话人，需要使用零样本合成方式
            available_spks = self.cosyvoice.list_available_spks()
            
            # 检查是否为CosyVoice2模型
            from cosyvoice.cli.model import CosyVoice2Model
            is_cosyvoice2 = isinstance(self.cosyvoice.model, CosyVoice2Model)
            
            if available_spks and not is_cosyvoice2:
                # 传统CosyVoice，使用SFT模式
                speaker = request.speaker if request.speaker in available_spks else available_spks[0]
                for audio_output in self.cosyvoice.inference_sft(request.text, speaker):
                    return audio_output['tts_speech']
            else:
                # CosyVoice2或没有预定义说话人，使用默认音频进行零样本合成
                import os
                import numpy as np
                
                # 创建默认的静音音频作为参考（如果没有其他选择）
                default_audio_path = None
                
                # 首先尝试使用现有的测试音频
                for test_file in ["test_audio_better.wav", "test_audio_short.wav"]:
                    if os.path.exists(test_file):
                        default_audio_path = test_file
                        break
                
                if not default_audio_path:
                    # 如果没有测试音频，创建一个临时的静音音频
                    import tempfile
                    import torchaudio
                    
                    # 生成1秒的静音音频 (16kHz)
                    silent_audio = torch.zeros(1, 16000)  # 1秒静音
                    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                    torchaudio.save(temp_file.name, silent_audio, 16000)
                    default_audio_path = temp_file.name
                
                # 加载默认音频
                prompt_audio_data = AudioFileHandler.load_audio_data(default_audio_path)
                
                # 使用零样本合成，使用最小的提示文本
                for audio_output in self.cosyvoice.inference_zero_shot(
                    tts_text=request.text,
                    prompt_text="你好",  # 最小提示文本
                    prompt_speech_16k=prompt_audio_data,
                    zero_shot_spk_id=request.speaker or ''
                ):
                    return audio_output['tts_speech']
        
        audio_tensor = await asyncio.get_event_loop().run_in_executor(None, _synthesize)
        return await self._process_audio_result(audio_tensor, request, request_id, SynthesisMode.BASIC)
    
    async def _zero_shot_synthesis(self, request: TTSRequest, request_id: str, prompt_audio_path: str) -> TTSResult:
        """零样本音色克隆"""
        def _synthesize():
            # 加载音频数据
            prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
            
            for audio_output in self.cosyvoice.inference_zero_shot(
                tts_text=request.text,
                prompt_text=request.prompt_text,
                prompt_speech_16k=prompt_audio_data,  # 使用音频数据
                zero_shot_spk_id=request.speaker or ''
            ):
                return audio_output['tts_speech']
        
        audio_tensor = await asyncio.get_event_loop().run_in_executor(None, _synthesize)
        return await self._process_audio_result(audio_tensor, request, request_id, SynthesisMode.ZERO_SHOT)
    
    async def _cross_lingual_synthesis(self, request: TTSRequest, request_id: str, prompt_audio_path: str) -> TTSResult:
        """跨语言合成"""
        def _synthesize():
            # 加载音频数据
            prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
            
            for audio_output in self.cosyvoice.inference_cross_lingual(
                tts_text=request.text,
                prompt_speech_16k=prompt_audio_data,  # 使用音频数据
                zero_shot_spk_id=request.speaker or ''
            ):
                return audio_output['tts_speech']
        
        audio_tensor = await asyncio.get_event_loop().run_in_executor(None, _synthesize)
        return await self._process_audio_result(audio_tensor, request, request_id, SynthesisMode.CROSS_LINGUAL)
    
    async def _instruct_synthesis(self, request: TTSRequest, request_id: str) -> TTSResult:
        """指令式合成"""
        # 处理参考音频 (CosyVoice2的指令合成需要参考音频)
        prompt_audio_path = None
        if request.prompt_audio:
            prompt_audio_path = await AudioFileHandler.process_audio_input(request.prompt_audio)
        else:
            # 如果没有提供参考音频，创建一个空的音频文件或使用默认
            # 这里我们抛出错误要求用户提供参考音频
            raise ValueError("CosyVoice2的指令式合成需要提供参考音频")
        
        try:
            def _synthesize():
                # 加载音频数据
                prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
                
                # CosyVoice2使用inference_instruct2，参数: tts_text, instruct_text, prompt_speech_16k, zero_shot_spk_id, stream, speed, text_frontend
                for audio_output in self.cosyvoice.inference_instruct2(
                    tts_text=request.text,
                    instruct_text=request.instruct_text,
                    prompt_speech_16k=prompt_audio_data,  # 使用音频数据
                    zero_shot_spk_id=request.speaker or ''
                ):
                    return audio_output['tts_speech']
            
            audio_tensor = await asyncio.get_event_loop().run_in_executor(None, _synthesize)
            return await self._process_audio_result(audio_tensor, request, request_id, SynthesisMode.INSTRUCT)
        
        finally:
            # 清理临时文件 - 只清理真正的临时文件，保护测试文件
            if (prompt_audio_path and 
                prompt_audio_path.startswith(tempfile.gettempdir()) and
                not prompt_audio_path.endswith(('test_audio_better.wav', 'test_audio_short.wav'))):
                try:
                    os.unlink(prompt_audio_path)
                except:
                    pass
    
    async def _instruct2_synthesis(self, request: TTSRequest, request_id: str) -> TTSResult:
        """指令式语音合成 - CosyVoice2的自然语言控制模式"""
        def _synthesize():
            # 处理参考音频
            prompt_audio_data = self._get_prompt_audio(request.prompt_audio)
            
            # 使用CosyVoice2的inference_instruct2方法
            for audio_output in self.cosyvoice.inference_instruct2(
                tts_text=request.text,
                instruct_text=request.instruct_text,
                prompt_speech_16k=prompt_audio_data,
                zero_shot_spk_id=request.zero_shot_spk_id,
                stream=False,
                speed=request.speed,
                text_frontend=request.text_frontend
            ):
                return audio_output['tts_speech']
        
        return await self._run_synthesis(_synthesize, request, request_id)
    
    async def _voice_conversion(self, request: TTSRequest, request_id: str) -> TTSResult:
        """语音转换 - 将源音频转换为目标音色"""
        def _synthesize():
            # 需要源音频和目标音色参考音频
            source_audio = self._get_prompt_audio(request.prompt_audio)  # 源音频
            target_audio = self._get_prompt_audio(request.prompt_audio)  # 目标音色
            
            for audio_output in self.cosyvoice.inference_vc(
                source_speech_16k=source_audio,
                prompt_speech_16k=target_audio,
                stream=False,
                speed=request.speed
            ):
                return audio_output['tts_speech']
        
        return await self._run_synthesis(_synthesize, request, request_id)
    
    async def add_zero_shot_speaker(self, speaker_id: str, prompt_text: str, prompt_audio) -> bool:
        """添加零样本说话人 - 用于全能API"""
        try:
            prompt_audio_data = self._get_prompt_audio(prompt_audio)
            success = self.cosyvoice.add_zero_shot_spk(
                prompt_text=prompt_text,
                prompt_speech_16k=prompt_audio_data,
                spk_id=speaker_id
            )
            if success:
                # 保存说话人信息
                self.cosyvoice.save_spkinfo()
                logger.info(f"✅ 保存零样本说话人成功: {speaker_id}")
            return success
        except Exception as e:
            logger.error(f"添加零样本说话人失败: {e}")
            return False
    
    def get_saved_speakers(self):
        """获取已保存的说话人列表 - 用于全能API"""
        try:
            # 获取零样本说话人信息
            spk_info = getattr(self.cosyvoice.frontend, 'spk2info', {})
            saved_speakers = {}
            
            for spk_id, info in spk_info.items():
                if isinstance(spk_id, str) and not spk_id.isdigit():  # 排除预训练音色
                    saved_speakers[spk_id] = {
                        "id": spk_id,
                        "type": "zero_shot",
                        "embedding_shape": info.get('llm_embedding', torch.tensor([])).shape if 'llm_embedding' in info else None
                    }
            
            return saved_speakers
        except Exception as e:
            logger.error(f"获取保存说话人失败: {e}")
            return {}
    
    async def _process_audio_result(self, audio_tensor: torch.Tensor, request: TTSRequest, 
                                  request_id: str, mode: SynthesisMode) -> TTSResult:
        """处理音频结果，应用后处理和格式转换"""
        try:
            # 应用语速调整
            if request.speed != 1.0:
                try:
                    import scipy.signal
                    audio_np = audio_tensor.cpu().numpy()
                    new_length = int(audio_np.shape[1] / request.speed)
                    if new_length > 0:
                        resampled = scipy.signal.resample(audio_np, new_length, axis=1)
                        audio_tensor = torch.from_numpy(resampled).float()
                except Exception as e:
                    logger.warning(f"语速调整失败: {e}")
            
            # 重采样
            sample_rate = getattr(self.cosyvoice, 'sample_rate', 22050)
            target_sample_rate = request.sample_rate or sample_rate
            
            if sample_rate != target_sample_rate:
                try:
                    resampler = torchaudio.transforms.Resample(sample_rate, target_sample_rate)
                    audio_tensor = resampler(audio_tensor)
                    sample_rate = target_sample_rate
                except Exception as e:
                    logger.warning(f"重采样失败: {e}")
            
            # 保存音频文件
            output_file = os.path.join(
                self.config.file.output_dir,
                f"{request_id}.{request.format.value}"
            )
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 根据格式保存
            if request.format == AudioFormat.WAV:
                torchaudio.save(output_file, audio_tensor, sample_rate, format="wav")
            elif request.format == AudioFormat.MP3:
                torchaudio.save(output_file, audio_tensor, sample_rate, format="mp3")
            elif request.format == AudioFormat.FLAC:
                torchaudio.save(output_file, audio_tensor, sample_rate, format="flac")
            
            # 获取文件信息
            file_size = os.path.getsize(output_file)
            duration = audio_tensor.shape[1] / sample_rate
            
            return TTSResult(
                success=True,
                audio_file=output_file,
                duration=duration,
                file_size=file_size,
                sample_rate=sample_rate,
                request_id=request_id,
                mode_used=mode
            )
            
        except Exception as e:
            logger.error(f"音频处理失败: {e}")
            return TTSResult(
                success=False,
                error_message=f"音频处理失败: {str(e)}",
                request_id=request_id
            )
    
    async def synthesize_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """流式合成 - 返回音频数据流"""
        if not self.is_initialized:
            raise RuntimeError("引擎未初始化")
        
        # 处理参考音频
        prompt_audio_path = None
        if request.prompt_audio:
            prompt_audio_path = await AudioFileHandler.process_audio_input(request.prompt_audio)
        
        # 用于清理的路径变量
        cleanup_path = prompt_audio_path
        
        try:
            def _stream_synthesize():
                nonlocal cleanup_path, prompt_audio_path
                if request.mode == SynthesisMode.BASIC:
                    # 与基础合成相同的逻辑
                    available_spks = self.cosyvoice.list_available_spks()
                    
                    # 检查是否为CosyVoice2模型
                    from cosyvoice.cli.model import CosyVoice2Model
                    is_cosyvoice2 = isinstance(self.cosyvoice.model, CosyVoice2Model)
                    
                    if available_spks and not is_cosyvoice2:
                        # 传统CosyVoice，使用SFT模式
                        speaker = request.speaker if request.speaker in available_spks else available_spks[0]
                        return self.cosyvoice.inference_sft(request.text, speaker)
                    else:
                        # CosyVoice2或没有预定义说话人，使用默认音频进行零样本合成
                        import os
                        import numpy as np
                        
                        # 创建默认的静音音频作为参考（如果没有其他选择）
                        default_audio_path = None
                        
                        # 首先尝试使用现有的测试音频
                        for test_file in ["test_audio_better.wav", "test_audio_short.wav"]:
                            if os.path.exists(test_file):
                                default_audio_path = test_file
                                break
                        
                        if not default_audio_path:
                            # 如果没有测试音频，创建一个临时的静音音频
                            import tempfile
                            import torchaudio
                            
                            # 生成1秒的静音音频 (16kHz)
                            silent_audio = torch.zeros(1, 16000)  # 1秒静音
                            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                            torchaudio.save(temp_file.name, silent_audio, 16000)
                            default_audio_path = temp_file.name
                        
                        prompt_audio_data = AudioFileHandler.load_audio_data(default_audio_path)
                        return self.cosyvoice.inference_zero_shot(
                            tts_text=request.text,
                            prompt_text="你好",  # 最小提示文本
                            prompt_speech_16k=prompt_audio_data,
                            zero_shot_spk_id=request.speaker or ''
                        )
                elif request.mode == SynthesisMode.ZERO_SHOT:
                    # 确保有参考音频文件
                    if not prompt_audio_path:
                        import os
                        default_audio_path = "test_audio_better.wav"
                        if not os.path.exists(default_audio_path):
                            default_audio_path = "test_audio_short.wav"
                        if not os.path.exists(default_audio_path):
                            raise ValueError("零样本合成需要参考音频文件")
                        prompt_audio_path = default_audio_path
                    
                    prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
                    return self.cosyvoice.inference_zero_shot(
                        tts_text=request.text, 
                        prompt_text=request.prompt_text or "这是一个标准的中文语音。", 
                        prompt_speech_16k=prompt_audio_data,
                        zero_shot_spk_id=request.speaker or ''
                    )
                elif request.mode == SynthesisMode.CROSS_LINGUAL:
                    # 确保有参考音频文件
                    if not prompt_audio_path:
                        import os
                        default_audio_path = "test_audio_better.wav"
                        if not os.path.exists(default_audio_path):
                            default_audio_path = "test_audio_short.wav"
                        if not os.path.exists(default_audio_path):
                            raise ValueError("跨语言合成需要参考音频文件")
                        prompt_audio_path = default_audio_path
                    
                    prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
                    return self.cosyvoice.inference_cross_lingual(
                        tts_text=request.text, 
                        prompt_speech_16k=prompt_audio_data,
                        zero_shot_spk_id=request.speaker or ''
                    )
                elif request.mode == SynthesisMode.INSTRUCT:
                    # 确保有参考音频文件
                    if not prompt_audio_path:
                        import os
                        default_audio_path = "test_audio_better.wav"
                        if not os.path.exists(default_audio_path):
                            default_audio_path = "test_audio_short.wav"
                        if not os.path.exists(default_audio_path):
                            raise ValueError("指令式合成需要参考音频文件")
                        prompt_audio_path = default_audio_path
                    
                    prompt_audio_data = AudioFileHandler.load_audio_data(prompt_audio_path)
                    return self.cosyvoice.inference_instruct2(
                        tts_text=request.text, 
                        instruct_text=request.instruct_text or "请用自然的语调朗读。", 
                        prompt_speech_16k=prompt_audio_data,
                        zero_shot_spk_id=request.speaker or ''
                    )
            
            # 在线程池中执行流式合成
            audio_output = await asyncio.get_event_loop().run_in_executor(None, _stream_synthesize)
            
            # CosyVoice可能返回生成器或字典，需要处理
            if hasattr(audio_output, '__iter__') and not isinstance(audio_output, dict):
                # 如果是生成器，取第一个结果
                audio_output = next(iter(audio_output))
            
            audio_tensor = audio_output['tts_speech']
            
            # 转换为字节数据
            import io
            buffer = io.BytesIO()
            sample_rate = getattr(self.cosyvoice, 'sample_rate', 22050)
            torchaudio.save(buffer, audio_tensor, sample_rate, format="wav")
            
            # 分块返回音频数据（模拟流式）
            audio_bytes = buffer.getvalue()
            chunk_size = 8192  # 8KB 块
            
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i:i + chunk_size]
        
        finally:
            # 清理临时文件 - 只清理真正的临时文件，保护测试文件
            if (cleanup_path and 
                cleanup_path.startswith(tempfile.gettempdir()) and
                not cleanup_path.endswith(('test_audio_better.wav', 'test_audio_short.wav'))):
                try:
                    os.unlink(cleanup_path)
                except:
                    pass
    
    def get_available_speakers(self) -> List[str]:
        """获取可用音色列表"""
        # CosyVoice2采用零样本设计，返回建议的默认音色名称
        return ["neutral", "female", "male"]
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, '_audio_cache'):
            self._audio_cache.clear()
        if hasattr(self, '_speaker_cache'):
            self._speaker_cache.clear()

    def _get_prompt_audio(self, prompt_audio):
        """获取参考音频数据"""
        if prompt_audio is None:
            # 使用默认音频
            import os
            for test_file in ["test_audio_better.wav", "test_audio_short.wav"]:
                if os.path.exists(test_file):
                    return AudioFileHandler.load_audio_data(test_file)
            
            # 如果没有测试音频，创建静音音频
            import tempfile
            import torchaudio
            silent_audio = torch.zeros(1, 16000)  # 1秒静音
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            torchaudio.save(temp_file.name, silent_audio, 16000)
            return AudioFileHandler.load_audio_data(temp_file.name)
        
        if isinstance(prompt_audio, str):
            # 文件路径或URL
            return AudioFileHandler.load_audio_data(prompt_audio)
        elif isinstance(prompt_audio, bytes):
            # 音频字节数据
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file.write(prompt_audio)
            temp_file.close()
            return AudioFileHandler.load_audio_data(temp_file.name)
        else:
            raise ValueError(f"不支持的音频输入类型: {type(prompt_audio)}")
    
    async def _run_synthesis(self, synthesize_func, request: TTSRequest, request_id: str) -> TTSResult:
        """运行合成函数的通用方法"""
        try:
            audio_tensor = await asyncio.get_event_loop().run_in_executor(None, synthesize_func)
            return await self._process_audio_result(audio_tensor, request, request_id, request.mode)
        except Exception as e:
            logger.error(f"合成失败: {e}")
            return TTSResult(
                success=False,
                error_message=f"合成失败: {str(e)}",
                request_id=request_id
            )

class CosyVoice2Service:
    """CosyVoice2 高性能TTS服务"""
    
    def __init__(self):
        self.engine = CosyVoice2Engine()
        self.custom_speakers = {}  # 自定义音色存储
        self.config = get_config()
    
    async def initialize(self) -> bool:
        """初始化服务"""
        logger.info("🚀 初始化CosyVoice2服务...")
        success = await self.engine.initialize()
        
        if success:
            # 确保输出目录存在
            os.makedirs(self.config.file.output_dir, exist_ok=True)
            logger.info("✅ CosyVoice2服务初始化成功")
        
        return success
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """语音合成"""
        return await self.engine.synthesize(request)
    
    async def synthesize_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """流式语音合成"""
        async for chunk in self.engine.synthesize_stream(request):
            yield chunk
    
    async def add_custom_speaker(self, speaker_name: str, prompt_text: str, 
                               prompt_audio: Union[str, bytes], description: str = None) -> dict:
        """添加自定义音色"""
        try:
            # 处理音频输入
            prompt_audio_path = await AudioFileHandler.process_audio_input(prompt_audio)
            
            # 验证音频
            if not AudioFileHandler.validate_audio_file(prompt_audio_path):
                # 清理临时文件
                if prompt_audio_path and prompt_audio_path.startswith(tempfile.gettempdir()):
                    try:
                        os.unlink(prompt_audio_path)
                    except:
                        pass
                return {"success": False, "error": "音频文件格式无效"}
            
            # 生成音色ID
            speaker_id = hashlib.md5(f"{speaker_name}_{prompt_text}".encode()).hexdigest()[:16]
            
            # 如果是固定测试文件，不需要复制
            if isinstance(prompt_audio, str) and not prompt_audio.startswith(('http://', 'https://')):
                # 直接使用本地文件路径
                if os.path.exists(prompt_audio):
                    final_audio_path = prompt_audio
                else:
                    final_audio_path = prompt_audio_path
            else:
                # 为上传的音频创建永久副本
                import shutil
                permanent_path = f"custom_speakers/{speaker_id}.wav"
                os.makedirs("custom_speakers", exist_ok=True)
                shutil.copy2(prompt_audio_path, permanent_path)
                final_audio_path = permanent_path
                
                # 清理临时文件
                if prompt_audio_path.startswith(tempfile.gettempdir()):
                    try:
                        os.unlink(prompt_audio_path)
                    except:
                        pass
            
            # 保存自定义音色信息
            self.custom_speakers[speaker_id] = {
                "speaker_name": speaker_name,
                "speaker_id": speaker_id,
                "prompt_text": prompt_text,
                "prompt_audio_path": final_audio_path,
                "description": description or f"自定义音色: {speaker_name}",
                "created_at": str(uuid.uuid4())
            }
            
            logger.info(f"✅ 自定义音色添加成功: {speaker_name} -> {speaker_id}")
            return {"success": True, "speaker_id": speaker_id}
            
        except Exception as e:
            logger.error(f"❌ 添加自定义音色失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_custom_speakers(self) -> list:
        """获取自定义音色列表"""
        return list(self.custom_speakers.values())
    
    async def delete_custom_speaker(self, speaker_id: str) -> dict:
        """删除自定义音色"""
        try:
            if speaker_id in self.custom_speakers:
                speaker_info = self.custom_speakers[speaker_id]
                
                # 清理音频文件 - 但不删除测试文件
                audio_path = speaker_info.get("prompt_audio_path")
                if (audio_path and os.path.exists(audio_path) and
                    not audio_path.endswith(('test_audio_better.wav', 'test_audio_short.wav'))):
                    try:
                        os.unlink(audio_path)
                    except:
                        pass
                
                # 删除记录
                del self.custom_speakers[speaker_id]
                
                logger.info(f"✅ 自定义音色删除成功: {speaker_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "音色不存在"}
                
        except Exception as e:
            logger.error(f"❌ 删除自定义音色失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_engine_status(self) -> dict:
        """获取引擎状态"""
        return {
            "initialized": self.engine.is_initialized,
            "capabilities": self.engine.capabilities,
            "model_path": self.config.cosyvoice.model_path,
            "custom_speakers_count": len(self.custom_speakers)
        }
    
    def get_available_speakers(self) -> List[str]:
        """获取可用音色"""
        return self.engine.get_available_speakers()
    
    def cleanup(self):
        """清理资源"""
        self.engine.cleanup()
        
        # 清理自定义音色文件 - 但不删除测试文件
        for speaker_info in self.custom_speakers.values():
            audio_path = speaker_info.get("prompt_audio_path")
            if (audio_path and os.path.exists(audio_path) and
                not audio_path.endswith(('test_audio_better.wav', 'test_audio_short.wav'))):
                try:
                    os.unlink(audio_path)
                except:
                    pass
        
        self.custom_speakers.clear()

    async def add_zero_shot_speaker(self, speaker_id: str, prompt_text: str, prompt_audio) -> bool:
        """添加零样本说话人 - 用于全能API"""
        return await self.engine.add_zero_shot_speaker(speaker_id, prompt_text, prompt_audio)
    
    def get_saved_speakers(self):
        """获取已保存的说话人列表 - 用于全能API"""
        return self.engine.get_saved_speakers()

# 全局服务实例
_service_instance = None

def get_cosyvoice2_service() -> CosyVoice2Service:
    """获取CosyVoice2服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = CosyVoice2Service()
    return _service_instance

# 兼容性函数
def get_tts_service() -> CosyVoice2Service:
    """兼容性函数"""
    return get_cosyvoice2_service()

if __name__ == "__main__":
    async def test_service():
        """测试服务"""
        service = get_cosyvoice2_service()
        
        # 初始化
        success = await service.initialize()
        if not success:
            print("❌ 服务初始化失败")
            return
        
        # 基础合成测试
        request = TTSRequest(
            text="这是CosyVoice2的基础语音合成测试。",
            mode=SynthesisMode.BASIC
        )
        
        result = await service.synthesize(request)
        if result.success:
            print(f"✅ 基础合成成功: {result.audio_file}")
        else:
            print(f"❌ 基础合成失败: {result.error_message}")
    
    asyncio.run(test_service())