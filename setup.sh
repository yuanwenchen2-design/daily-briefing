#!/bin/bash
set -e
echo "========================================"
echo "  每日简报 Daily Briefing"
echo "  AI 驱动 · 中英双语 · 语音播报"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] 未找到 Python3，请先安装 Python 3.9+"
    exit 1
fi

# Check .env
if [ ! -f ".env" ]; then
    echo "[提示] 未找到 .env 文件"
    echo "请复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY"
    echo "没有 API Key 将使用纯文本模式（无 AI 摘要）"
    echo ""
    cp .env.example .env
fi

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo "[1/2] 创建虚拟环境..."
    python3 -m venv .venv
fi

# Activate venv and install deps
echo "[2/2] 安装依赖..."
source .venv/bin/activate
pip install -r requirements.txt -q

# Launch
echo ""
echo "========================================"
echo "  启动中... 浏览器访问 http://localhost:5200"
echo "  按 Ctrl+C 停止服务器"
echo "========================================"
echo ""
python main.py
