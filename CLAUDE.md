# 每日简报 Daily Briefing

DeepSeek AI 驱动的全球新闻聚合与双语简报系统。自动采集四大领域新闻（政治/经济/军事/科技），AI 摘要 + 翻译（中/英/粤），TTS 语音播报，股票分析。

## Quick Recall

```
项目目标: 每日自动生成中英双语新闻简报 + 股票分析
启动命令: python main.py
访问地址: http://localhost:5200
技术栈: Flask + DeepSeek API + edge-tts + yfinance
```

## Tech Stack

- **Language**: Python 3.9+
- **Framework**: Flask (web server + API)
- **AI**: DeepSeek API (OpenAI-compatible) for summarization & stock analysis
- **TTS**: Microsoft Edge TTS (edge-tts) — Chinese, English, Cantonese
- **Data**: RSS feedparser, yfinance, requests
- **Storage**: SQLite (briefings.db) + JSON cache

## Project Structure

```
daily-briefing/
├── main.py              # CLI entry + pipeline orchestrator
├── config.py            # All configuration (API keys, feeds, languages)
├── database.py          # SQLite persistence
├── news_fetcher.py      # Multi-threaded RSS fetcher + spam filter
├── summarizer.py        # DeepSeek AI summarization + fallback
├── tts_engine.py        # Edge TTS voice generation (3 languages)
├── stock_analyzer.py    # 3-market stock analysis (US/HK/CN)
├── web_server.py        # Flask web dashboard + API
├── templates/
│   └── index.html       # Dark theme dashboard
├── static/
│   ├── style.css        # Dashboard styles
│   └── script.js        # Frontend JS (fetch, render, audio)
├── requirements.txt
├── .env.example         # Environment variable template
└── setup.bat / setup.sh # One-click setup scripts
```

## Common Commands

```bash
# Full pipeline: fetch → summarize → TTS → serve
python main.py

# Force re-fetch today's news
python main.py --force

# Specific language
python main.py --lang english

# Fetch only (no server)
python main.py --fetch-only

# No browser auto-open
python main.py --no-browser
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY=sk-your-key
```

The app uses **DeepSeek API** (not Anthropic). Set `DEEPSEEK_API_KEY` in `.env`.
Without a key, the app falls back to plain text mode (no AI summarization).

## Portability

- All paths relative via `Path(__file__).parent`
- No hardcoded absolute paths
- Cross-platform: Windows / macOS / Linux
- `setup.bat` (Windows) and `setup.sh` (macOS/Linux) for one-click setup
