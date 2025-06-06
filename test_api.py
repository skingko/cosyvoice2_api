#!/usr/bin/env python3
"""
CosyVoice2 TTS API 简化测试脚本
"""

import requests
import json
import os
from pathlib import Path

# API 配置
API_BASE_URL = "http://localhost:8000"
ULTIMATE_URL = f"{API_BASE_URL}/api/v1/tts/ultimate"
UPLOAD_URL = f"{API_BASE_URL}/api/v1/tts/ultimate-upload"
STATUS_URL = f"{API_BASE_URL}/api/v1/status"

def test_api_status():
    """测试API状态"""
    print("\n🔍 1. 测试API状态...")
    try:
        response = requests.get(STATUS_URL)
        if response.status_code == 200:
            print("✅ API状态正常")
            return True
        else:
            print(f"❌ API状态异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API连接失败: {e}")
        return False

def test_basic_synthesis():
    """测试基础语音合成"""
    print("\n🔍 2. 测试基础语音合成...")
    
    data = {
        "text": "这是基础语音合成测试。",
        "mode": "auto",
        "language": "zh"
    }
    
    try:
        response = requests.post(ULTIMATE_URL, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 基础语音合成成功")
                print(f"   - 音频时长: {result.get('duration', 'N/A')}秒")
                return True
            else:
                print(f"❌ 合成失败: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_zero_shot_cloning():
    """测试零样本音色克隆"""
    print("\n🔍 3. 测试零样本音色克隆...")
    
    # 创建测试音频文件
    test_audio_path = "temp/test_reference.wav"
    os.makedirs("temp", exist_ok=True)
    
    # 这里应该有一个真实的音频文件，为演示目的创建一个空文件
    Path(test_audio_path).touch()
    
    try:
        with open(test_audio_path, 'rb') as f:
            files = {"reference_audio": f}
            data = {
                "text": "这是零样本音色克隆测试。",
                "prompt_text": "参考音频的文本内容"
            }
            response = requests.post(UPLOAD_URL, files=files, data=data)
            
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 零样本音色克隆成功")
                return True
            else:
                print(f"❌ 克隆失败: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)

def test_emotion_control():
    """测试情感控制"""
    print("\n🔍 4. 测试情感控制...")
    
    data = {
        "text": "这是一个有趣的故事[laughter]，让我笑一下。",
        "mode": "auto",
        "language": "zh"
    }
    
    try:
        response = requests.post(ULTIMATE_URL, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 情感控制测试成功")
                return True
            else:
                print(f"❌ 测试失败: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_speed_control():
    """测试语速控制"""
    print("\n🔍 5. 测试语速控制...")
    
    data = {
        "text": "这是语速控制测试。",
        "mode": "auto", 
        "language": "zh",
        "speed": 1.5
    }
    
    try:
        response = requests.post(ULTIMATE_URL, json=data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ 语速控制测试成功")
                return True
            else:
                print(f"❌ 测试失败: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def main():
    """运行核心功能测试"""
    print("🚀 开始CosyVoice2 API核心功能测试")
    print("=" * 50)
    
    tests = [
        test_api_status,
        test_basic_synthesis,
        test_zero_shot_cloning,
        test_emotion_control,
        test_speed_control
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 项测试通过")
    print(f"✅ 成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有核心功能测试通过！")
    else:
        print("⚠️  部分功能测试失败，请检查API服务")

if __name__ == "__main__":
    main() 