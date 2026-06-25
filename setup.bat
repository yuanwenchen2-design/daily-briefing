@echo off
title 每日简报 Daily Briefing — Setup
echo ========================================
echo   每日简报 Daily Briefing
echo   AI 驱动 · 中英双语 · 语音播报
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [提示] 未找到 .env 文件
    echo 请复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY
    echo 没有 API Key 将使用纯文本模式（无 AI 摘要）
    echo.
    copy .env.example .env >nul 2>&1
)

:: Create venv if needed
if not exist ".venv\" (
    echo [1/2] 创建虚拟环境...
    python -m venv .venv
)

:: Activate venv and install deps
echo [2/2] 安装依赖...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: Launch
echo.
echo ========================================
echo   启动中... 浏览器访问 http://localhost:5200
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.
python main.py
pause
