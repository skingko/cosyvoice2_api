@echo off
chcp 65001 >nul
:: =============================================================================
:: CosyVoice2 TTS API Windows 安装脚本
:: 支持 Windows 10/11，自动检测环境并安装所需依赖
:: =============================================================================

setlocal enabledelayedexpansion

:: 颜色定义 (Windows Terminal)
set "RED=[31m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "BLUE=[34m"
set "PURPLE=[35m"
set "NC=[0m"

echo %BLUE%🚀 CosyVoice2 TTS API Windows 安装程序%NC%
echo ==========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% == 0 (
    echo %GREEN%[INFO]%NC% 检测到管理员权限
) else (
    echo %YELLOW%[WARNING]%NC% 建议以管理员身份运行以安装系统依赖
)

:: 检查Python
echo %BLUE%[STEP]%NC% 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo %RED%[ERROR]%NC% 未找到Python，请从 https://python.org 下载安装 Python 3.8+
        pause
        exit /b 1
    ) else (
        set "PYTHON_CMD=python3"
    )
) else (
    set "PYTHON_CMD=python"
)

for /f "tokens=2" %%i in ('%PYTHON_CMD% --version') do set "PYTHON_VERSION=%%i"
echo %GREEN%[SUCCESS]%NC% 发现Python版本: %PYTHON_VERSION%

:: 检查pip
echo %BLUE%[STEP]%NC% 检查pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARNING]%NC% 未找到pip，正在尝试安装...
    %PYTHON_CMD% -m ensurepip --upgrade
    set "PIP_CMD=%PYTHON_CMD% -m pip"
) else (
    set "PIP_CMD=pip"
)

echo %GREEN%[SUCCESS]%NC% pip检查完成

:: 安装系统依赖 (通过包管理器)
echo %BLUE%[STEP]%NC% 检查系统依赖...
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARNING]%NC% 未找到Git，请从 https://git-scm.com 下载安装
)

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[WARNING]%NC% 未找到FFmpeg，建议安装:
    echo   1. 通过 Chocolatey: choco install ffmpeg
    echo   2. 通过 Scoop: scoop install ffmpeg
    echo   3. 手动下载: https://ffmpeg.org/download.html
)

:: 创建虚拟环境
echo %BLUE%[STEP]%NC% 创建Python虚拟环境...
if not exist "venv" (
    echo %BLUE%[INFO]%NC% 创建虚拟环境...
    %PYTHON_CMD% -m venv venv
) else (
    echo %BLUE%[INFO]%NC% 虚拟环境已存在
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 升级pip
echo %BLUE%[STEP]%NC% 升级pip和基础工具...
%PIP_CMD% install --upgrade pip setuptools wheel

:: 检测GPU支持
echo %BLUE%[STEP]%NC% 检测GPU支持...
nvidia-smi >nul 2>&1
if %errorlevel% == 0 (
    echo %GREEN%[INFO]%NC% 检测到NVIDIA GPU，将安装CUDA版本PyTorch
    %PIP_CMD% install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
) else (
    echo %BLUE%[INFO]%NC% 未检测到NVIDIA GPU，安装CPU版本PyTorch
    %PIP_CMD% install torch torchaudio
)

:: 安装项目依赖
echo %BLUE%[STEP]%NC% 安装项目依赖...
if exist "requirements.txt" (
    %PIP_CMD% install -r requirements.txt
    echo %GREEN%[SUCCESS]%NC% requirements.txt安装完成
) else (
    echo %RED%[ERROR]%NC% 未找到requirements.txt文件
    pause
    exit /b 1
)

:: 克隆CosyVoice仓库
echo %BLUE%[STEP]%NC% 克隆CosyVoice仓库...
if not exist "CosyVoice" (
    echo %BLUE%[INFO]%NC% 正在克隆CosyVoice仓库...
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
    cd CosyVoice
    ..\venv\Scripts\python.exe -m pip install -e .
    cd ..
    echo %GREEN%[SUCCESS]%NC% CosyVoice仓库克隆并安装完成
) else (
    echo %BLUE%[INFO]%NC% CosyVoice仓库已存在，正在更新...
    cd CosyVoice
    git pull
    git submodule update --init --recursive
    ..\venv\Scripts\python.exe -m pip install -e .
    cd ..
    echo %GREEN%[SUCCESS]%NC% CosyVoice更新完成
)

:: 验证安装
echo %BLUE%[STEP]%NC% 验证安装...
venv\Scripts\python.exe -c "import torch; import torchaudio; import transformers; print('✅ 核心库导入成功')" >nul 2>&1
if %errorlevel% == 0 (
    echo %GREEN%[SUCCESS]%NC% 核心依赖验证通过
) else (
    echo %RED%[ERROR]%NC% 核心依赖验证失败
)

:: 创建启动脚本
echo %BLUE%[STEP]%NC% 创建启动脚本...
(
echo @echo off
echo chcp 65001 ^>nul
echo echo 🚀 启动CosyVoice2 TTS API...
echo.
echo :: 激活虚拟环境
echo if exist "venv\Scripts\activate.bat" ^(
echo     call venv\Scripts\activate.bat
echo ^)
echo.
echo :: 检查模型
echo if not exist "pretrained_models" ^(
echo     echo ⚠️  请下载CosyVoice模型到pretrained_models目录
echo     echo 推荐模型: CosyVoice2-0.5B
echo     echo 下载地址: https://github.com/FunAudioLLM/CosyVoice
echo ^)
echo.
echo :: 启动API服务
echo python main.py
echo pause
) > start_api.bat

echo %GREEN%[SUCCESS]%NC% 启动脚本创建完成: start_api.bat

:: 显示完成信息
echo.
echo %GREEN%🎉 CosyVoice2 TTS API 安装完成!%NC%
echo ========================================
echo.
echo %PURPLE%📋 下一步操作:%NC%
echo 1. 下载CosyVoice模型到 pretrained_models\ 目录
echo    推荐: CosyVoice2-0.5B
echo    下载: https://github.com/FunAudioLLM/CosyVoice
echo.
echo 2. 启动API服务:
echo    start_api.bat
echo    或者: python main.py
echo.
echo 3. 测试API:
echo    python test_api.py
echo.
echo 4. 访问API文档:
echo    http://localhost:8000/docs
echo.
echo %BLUE%📚 更多信息请查看 README.md 和 API_DOCS.md%NC%
echo.

pause 