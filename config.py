"""
每日简报 - 配置文件
Daily Briefing - Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# --- 大模型 API（DeepSeek，OpenAI 兼容接口）---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek-V3

# --- 默认设置 ---
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "chinese")
AUTO_PLAY = os.getenv("AUTO_PLAY", "true").lower() == "true"

# --- 支持的语言 ---
LANGUAGES = {
    "chinese": {
        "name": "中文",
        "voice": "zh-CN-XiaoxiaoNeural",
        "flag": "🇨🇳",
        "locale": "zh-CN",
    },
    "english": {
        "name": "English",
        "voice": "en-US-JennyNeural",
        "flag": "🇺🇸",
        "locale": "en-US",
    },
    "cantonese": {
        "name": "粵語",
        "voice": "zh-HK-HiuMaanNeural",
        "flag": "🇭🇰",
        "locale": "zh-HK",
    },
}

# --- 四大领域 ---
CATEGORIES = {
    "political": {
        "name_zh": "政治",
        "name_en": "Politics",
        "icon": "🏛️",
        "color": "#e74c3c",
        "feeds": [
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://feeds.npr.org/1004/rss.xml",
            "https://www.theguardian.com/world/rss",
            "http://rss.cnn.com/rss/edition_world.rss",
        ],
    },
    "economic": {
        "name_zh": "经济",
        "name_en": "Economy",
        "icon": "💰",
        "color": "#f39c12",
        "feeds": [
            "http://feeds.bbci.co.uk/news/business/rss.xml",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://feeds.marketwatch.com/marketwatch/topstories",
            "http://rss.cnn.com/rss/money_latest.rss",
        ],
    },
    "military": {
        "name_zh": "军事",
        "name_en": "Military",
        "icon": "⚔️",
        "color": "#27ae60",
        "feeds": [
            "https://breakingdefense.com/feed/",
            "https://taskandpurpose.com/feed/",
        ],
    },
    "technology": {
        "name_zh": "科技",
        "name_en": "Technology",
        "icon": "🔬",
        "color": "#3498db",
        "feeds": [
            "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://www.wired.com/feed/rss",
        ],
    },
}

MAX_NEWS_PER_CATEGORY = 25
SUMMARY_MAX_TOKENS = 4000

# --- 股票分析 ---
STOCK_ANALYSIS_ENABLED = os.getenv("STOCK_ANALYSIS_ENABLED", "true").lower() == "true"
STOCK_INDICES = {
    "us": ["^GSPC", "^IXIC", "^DJI"],       # S&P 500, NASDAQ, Dow Jones
    "hk": ["^HSI", "^HSCE"],                 # 恒生指数, 国企指数
    "cn": ["000300.SS", "000001.SS"],        # 沪深300, 上证指数
}
STOCK_MAX_RECOMMENDATIONS = 5   # 每类最多推荐数
STOCK_ANALYSIS_MAX_TOKENS = 6000  # 需覆盖美股+A股+港股三个市场

# 股票分析专用财经 RSS（美股）
STOCK_NEWS_FEEDS = [
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "http://rss.cnn.com/rss/money_latest.rss",
]

# 中国A股/港股财经 RSS
CHINA_STOCK_NEWS_FEEDS = [
    "https://www.yicai.com/feed/",               # 第一财经
    "https://rss.huxiu.com/",                     # 虎嗅
    "https://www.36kr.com/feed",                  # 36氪
    "http://finance.sina.com.cn/rss/fund.xml",    # 新浪财经
]

# --- 广告/垃圾过滤关键词 ---
SPAM_KEYWORDS = [
    "credit card", "apr", "cash back", "home equity", "dream big",
    "0% intro", "insurance", "best card", "refinance", "mortgage rates",
    "sponsored", "advertorial", "promoted", "partner content",
    "lotto", "lottery", "casino", "betting",
    "this is the best", "you won't believe", "shocking",
    "click here", "subscribe now", "free trial",
    "act now", "limited time", "exclusive offer",
]
