#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CosyVoice2 TTS 系统配置
简化的配置管理
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CosyVoiceConfig:
    """CosyVoice2 引擎配置"""
    # 模型路径 - 自动选择最佳可用模型
    model_path: str = field(default_factory=lambda: _get_best_cosyvoice_model())
    
    # 基础配置
    sample_rate: int = 22050
    device: str = "auto"  # auto/cpu/cuda/mps
    
    # 性能配置
    max_concurrent_requests: int = 4
    request_timeout: int = 300

@dataclass
class APIConfig:
    """API 服务配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # 请求限制
    max_text_length: int = 1000
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    
    # 安全配置
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

@dataclass
class FileConfig:
    """文件管理配置"""
    # 目录配置
    output_dir: str = "outputs"
    temp_dir: str = "temp"
    upload_dir: str = "uploads"
    
    # 清理配置
    auto_cleanup: bool = True
    cleanup_interval_hours: int = 24
    
    # 文件限制
    max_audio_duration: float = 60.0  # 最大音频时长(秒)
    allowed_audio_formats: List[str] = field(
        default_factory=lambda: ["wav", "mp3", "flac", "m4a", "ogg"]
    )

@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = "logs/cosyvoice2.log"
    enable_console: bool = True

@dataclass
class SystemConfig:
    """系统主配置"""
    cosyvoice: CosyVoiceConfig = field(default_factory=CosyVoiceConfig)
    api: APIConfig = field(default_factory=APIConfig)
    file: FileConfig = field(default_factory=FileConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def __post_init__(self):
        """配置后处理"""
        # 确保目录存在
        os.makedirs(self.file.output_dir, exist_ok=True)
        os.makedirs(self.file.temp_dir, exist_ok=True)
        os.makedirs(self.file.upload_dir, exist_ok=True)
        
        if self.logging.file_path:
            os.makedirs(os.path.dirname(self.logging.file_path), exist_ok=True)
        
        # 从环境变量更新配置
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # API配置
        self.api.host = os.getenv("COSYVOICE_HOST", self.api.host)
        self.api.port = int(os.getenv("COSYVOICE_PORT", self.api.port))
        self.api.debug = os.getenv("COSYVOICE_DEBUG", "false").lower() == "true"
        
        # 模型配置
        if os.getenv("COSYVOICE_MODEL_PATH"):
            self.cosyvoice.model_path = os.getenv("COSYVOICE_MODEL_PATH")
        
        # 设备配置
        self.cosyvoice.device = os.getenv("COSYVOICE_DEVICE", self.cosyvoice.device)

def _get_best_cosyvoice_model() -> str:
    """自动选择最佳的CosyVoice模型"""
    model_priorities = [
        "pretrained_models/CosyVoice2-0.5B",
        "pretrained_models/CosyVoice-300M-Instruct", 
        "pretrained_models/CosyVoice-300M",
        "pretrained_models/CosyVoice-300M-SFT"
    ]
    
    for model_path in model_priorities:
        if os.path.exists(model_path):
            return model_path
    
    # 如果没有找到预训练模型，返回默认路径
    return "pretrained_models/CosyVoice2-0.5B"

# 全局配置实例
_config = None

def get_config() -> SystemConfig:
    """获取系统配置"""
    global _config
    if _config is None:
        _config = SystemConfig()
    return _config

def set_config(config: SystemConfig):
    """设置系统配置"""
    global _config
    _config = config

# 导出默认配置
config = get_config()