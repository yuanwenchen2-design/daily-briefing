"""
每日简报 - 股票分析模块
使用财经新闻 + DeepSeek API 进行智能分析
覆盖三大市场：美股 / A股 / 港股
输出：高潜力股（上涨空间大/下跌空间小）+ 事件驱动机会
"""
import json
import logging
import re
from datetime import datetime

import feedparser
import requests

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    STOCK_MAX_RECOMMENDATIONS, STOCK_ANALYSIS_MAX_TOKENS,
    STOCK_NEWS_FEEDS, CHINA_STOCK_NEWS_FEEDS,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
}

STOCK_SYSTEM_PROMPT = """You are a senior equity strategist at a global investment bank, covering US, China A-share, and Hong Kong markets. Your task is to analyze financial news and market conditions to identify high-conviction stock ideas across all three markets.

**Your Knowledge:**
You have deep knowledge of global markets, individual stocks, sectors, and current events. Use this knowledge combined with the news headlines provided below.

═══════════════════════════════════════
**Part 1 — US Stocks (美股)**
═══════════════════════════════════════

**Task 1A — High Potential (上涨空间大 / 下跌空间小):**
Identify 3-5 US stocks where upside significantly outweighs downside risk. Criteria:
- Strong technical support, positive fundamentals, sector tailwinds
- Recent pullback creating attractive entry point
- risk_reward = upside_pct / downside_pct ≥ 1.5

**Task 1B — Event-Driven (突发事件利好):**
Identify 2-3 US stocks that may benefit from recent breaking events.

═══════════════════════════════════════
**Part 2 — A-Shares (A股)**
═══════════════════════════════════════

**A-Share Market Characteristics:**
- T+1 settlement, ±10% daily limit (±20% for ChiNext/STAR), no short-selling for retail
- Policy-driven: 政策面（国务院/发改委/央行/证监会）影响巨大
- Capital flows: 北向资金 (northbound via Stock Connect) is a key sentiment indicator
- Sector rotation: 金融/消费/科技/新能源/医药/军工 轮动明显
- Key indices: 上证指数(000001), 沪深300(000300), 中证500(000905), 科创50(000688), 创业板指(399006)

**Task 2A — High Potential A-Shares (上涨空间大 / 下跌空间小):**
Identify 3-5 A-share stocks. Focus on:
- Policy beneficiaries: 国家政策重点扶持行业（新能源、半导体、AI、高端制造）
- Attractive valuations: 低PE+高成长，或被市场错杀的白马股
- Technical setup: 关键支撑位附近企稳，量价配合良好
- Northbound inflow: 北向资金持续加仓的标的
- Sector catalysts: 行业景气度回升信号

**Task 2B — Event-Driven A-Shares (突发事件利好):**
Identify 2-3 A-shares. Look for:
- 政策催化：国务院/部委出台行业利好政策
- 业绩超预期：季报/年报大幅超预期的公司
- 重大合同/项目中标
- 行业供需变化带来的机会

═══════════════════════════════════════
**Part 3 — HK Stocks (港股)**
═══════════════════════════════════════

**HK Market Characteristics:**
- T+0 settlement, no price limits, short-selling allowed
- Southbound flow: 南向资金（港股通）是重要增量资金来源
- Valuation discount: A-H premium（A股相对港股溢价）提供套利思路
- Key indices: 恒生指数(^HSI), 恒生科技指数, 国企指数(^HSCE)
- Sectors: 互联网/科技, 金融, 地产, 消费, 医药

**Task 3A — High Potential HK Stocks (上涨空间大 / 下跌空间小):**
Identify 3-5 HK-listed stocks. Focus on:
- Deep value: 低PB/高股息率的国企股（银行/电信/能源）
- Tech recovery: 估值处于历史低位的互联网龙头
- Southbound favorites: 港股通资金持续流入标的
- A-H arbitrage: A-H溢价收窄机会

**Task 3B — Event-Driven HK Stocks (突发事件利好):**
Identify 2-3 HK stocks. Look for:
- 中概股回归/双重上市
- 港股通纳入预期
- 公司回购/大股东增持
- 行业监管放松信号

═══════════════════════════════════════
**Output MUST be valid JSON only:**
═══════════════════════════════════════
```json
{
  "market_overview": {
    "indices": [
      {"name": "S&P 500", "value": 5500, "change_pct": 0.45, "sentiment": "bullish"},
      {"name": "上证指数", "value": 3300, "change_pct": 0.32, "sentiment": "bullish"},
      {"name": "恒生指数", "value": 19500, "change_pct": -0.15, "sentiment": "neutral"}
    ],
    "market_sentiment": "全球偏多 / A股震荡 / 港股偏弱",
    "summary_zh": "美股科技领涨，A股等待政策信号，港股估值修复中...",
    "summary_en": "US tech leads; A-shares await policy signals; HK valuations recovering..."
  },
  "high_potential": [
    {
      "symbol": "AAPL", "name": "Apple Inc.", "price": 175.0,
      "upside_pct": 14.3, "downside_pct": 5.7, "risk_reward": 2.5,
      "catalyst_zh": "新款iPhone需求超预期", "catalyst_en": "New iPhone demand beats",
      "confidence": 4
    }
  ],
  "event_driven": [
    {
      "symbol": "LMT", "name": "Lockheed Martin", "price": 480.0,
      "event_zh": "国防预算增加", "event_en": "Defense budget increase",
      "expected_impact": "positive",
      "analysis_zh": "地缘紧张加剧国防开支...", "analysis_en": "Geopolitical tensions...",
      "confidence": 4
    }
  ],
  "a_shares": {
    "high_potential": [
      {
        "symbol": "600519", "name": "贵州茅台", "price": 1680.0,
        "upside_pct": 12.0, "downside_pct": 5.0, "risk_reward": 2.4,
        "catalyst_zh": "中秋国庆旺季备货启动，批价企稳回升", "catalyst_en": "Holiday stocking season starts; wholesale price stabilizing",
        "confidence": 4
      }
    ],
    "event_driven": [
      {
        "symbol": "688981", "name": "中芯国际", "price": 52.0,
        "event_zh": "国家大基金三期注资预期", "event_en": "National Semiconductor Fund Phase III expected",
        "expected_impact": "positive",
        "analysis_zh": "大基金三期规模或超3000亿，SMIC作为龙头直接受益...",
        "analysis_en": "Phase III fund may exceed 300B RMB; SMIC benefits as industry leader...",
        "confidence": 4
      }
    ]
  },
  "hk_stocks": {
    "high_potential": [
      {
        "symbol": "0700", "name": "腾讯控股", "price": 380.0,
        "upside_pct": 15.0, "downside_pct": 6.0, "risk_reward": 2.5,
        "catalyst_zh": "游戏版号常态化+视频号广告加速变现", "catalyst_en": "Game license normalization + video account ad acceleration",
        "confidence": 4
      }
    ],
    "event_driven": [
      {
        "symbol": "9988", "name": "阿里巴巴", "price": 85.0,
        "event_zh": "蚂蚁集团重启IPO预期升温", "event_en": "Ant Group IPO restart expectations rising",
        "expected_impact": "positive",
        "analysis_zh": "监管环境边际改善，蚂蚁上市将释放巨大价值...",
        "analysis_en": "Regulatory environment improving; Ant IPO would unlock significant value...",
        "confidence": 3
      }
    ]
  }
}
```

**RULES (MUST FOLLOW):**
- US stocks: symbol = ticker (e.g. "AAPL"), name in English
- A-shares: symbol = 6-digit code (e.g. "600519"), name in Chinese (公司全称)
- HK stocks: symbol = 4-digit code (e.g. "0700"), name in Chinese or English
- A-share price in RMB (¥), HK price in HKD (HK$), US price in USD ($)
- NO penny stocks: US <$5, A-shares <¥5, HK <HK$5
- confidence: 1-5 (5 = highest)
- risk_reward = upside_pct / downside_pct (≥ 1.5)
- ALL text fields must be bilingual (Chinese + English) — especially important for A-shares/HK stocks
- If insufficient data for a market, return empty arrays — DO NOT omit the market section
- Base analysis on provided news AND your knowledge of current conditions
"""


def _call_deepseek(system_prompt: str, user_message: str) -> dict:
    """调用 DeepSeek API，强制 JSON 输出"""
    from openai import OpenAI

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    logger.info(f"调用 DeepSeek API 进行股票分析 ({DEEPSEEK_MODEL})...")
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=STOCK_ANALYSIS_MAX_TOKENS,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    logger.info(f"DeepSeek 股票分析返回 {len(raw)} 字符")

    # 去除 markdown 代码块包裹
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"股票 JSON 解析失败: {e}，尝试修复...")
        from pathlib import Path
        from config import AUDIO_DIR
        debug_path = AUDIO_DIR / "_last_stock_response.txt"
        debug_path.write_text(raw, encoding="utf-8")
        logger.info(f"原始股票响应已保存至 {debug_path}")

    # 尝试提取最外层 {...}
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析股票分析 JSON，已保存原始响应")


def _try_fetch_yfinance_indices() -> list[dict]:
    """尝试通过 yfinance 获取指数数据（可能因网络限制失败）"""
    try:
        import yfinance as yf

        index_symbols = {
            "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones",
            "^HSI": "Hang Seng", "^HSCE": "HSCEI",
            "000300.SS": "CSI 300", "000001.SS": "SSE Composite",
        }

        data = yf.download(
            tickers=" ".join(index_symbols.keys()),
            period="2d",
            group_by="ticker",
            auto_adjust=True,
            threads=False,
            progress=False,
            timeout=10,
        )

        if data is None or data.empty:
            return []

        indices = []
        for symbol, name in index_symbols.items():
            try:
                if len(index_symbols) == 1:
                    series = data["Close"]
                elif symbol in data.columns.get_level_values(0):
                    series = data[symbol]["Close"]
                else:
                    continue

                series = series.dropna()
                if len(series) < 2:
                    continue

                current = float(series.iloc[-1])
                prev = float(series.iloc[-2])
                change_pct = ((current - prev) / prev) * 100 if prev else 0

                indices.append({
                    "name": name, "symbol": symbol,
                    "value": round(current, 2),
                    "change_pct": round(change_pct, 2),
                    "sentiment": "bullish" if change_pct > 0.3 else (
                        "bearish" if change_pct < -0.3 else "neutral"
                    ),
                })
            except Exception:
                continue

        return indices
    except Exception as e:
        logger.debug(f"yfinance 指数获取失败（将使用 AI 知识）: {e}")
        return []


def _fetch_all_news() -> tuple[str, str]:
    """采集财经新闻，返回 (global_news, china_news)"""
    global_lines = []
    china_lines = []

    # 1. 全球财经新闻
    for url in STOCK_NEWS_FEEDS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:12]:
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                summary = re.sub(r"<[^>]+>", "", summary)[:200]
                if title and len(title) > 15:
                    text = f"• {title}"
                    if summary:
                        text += f" — {summary}"
                    global_lines.append(text)
        except Exception as e:
            logger.debug(f"  全球新闻源 {url[:50]}... 失败: {e}")

    # 2. 额外全球财经
    extra_feeds = [
        "http://feeds.bbci.co.uk/news/business/rss.xml",
        "https://feeds.marketwatch.com/marketwatch/topstories",
    ]
    for url in extra_feeds:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:8]:
                title = (entry.get("title") or "").strip()
                if title and len(title) > 15:
                    global_lines.append(f"• {title}")
        except Exception as e:
            logger.debug(f"  备用新闻源 {url[:50]}... 失败: {e}")

    # 3. 中国财经新闻
    for url in CHINA_STOCK_NEWS_FEEDS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:10]:
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                summary = re.sub(r"<[^>]+>", "", summary)[:200]
                if title and len(title) > 10:
                    text = f"• {title}"
                    if summary and len(summary) > 20:
                        text += f" — {summary}"
                    china_lines.append(text)
        except Exception as e:
            logger.debug(f"  中国新闻源 {url[:50]}... 失败: {e}")

    return "\n".join(global_lines[:35]), "\n".join(china_lines[:25])


def analyze_stocks(economic_news: str = "") -> dict:
    """
    主入口：采集财经新闻 + AI 分析 → 返回三大市场股票推荐。

    返回:
        {
          "market_overview": {...},
          "high_potential": [...],     # 美股高潜力
          "event_driven": [...],       # 美股事件驱动
          "a_shares": {
            "high_potential": [...],   # A股高潜力
            "event_driven": [...]      # A股事件驱动
          },
          "hk_stocks": {
            "high_potential": [...],   # 港股高潜力
            "event_driven": [...]      # 港股事件驱动
          }
        }
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("未配置 DEEPSEEK_API_KEY，跳过股票分析")
        return {
            "market_overview": {},
            "high_potential": [], "event_driven": [],
            "a_shares": {"high_potential": [], "event_driven": []},
            "hk_stocks": {"high_potential": [], "event_driven": []},
        }

    logger.info("═══ 股票分析（美股/A股/港股） ═══")

    # 1. 尝试获取实时指数
    logger.info("[股票 1/2] 采集市场数据...")
    indices = _try_fetch_yfinance_indices()
    if indices:
        logger.info(f"  yfinance 获取 {len(indices)} 个指数数据")
    else:
        logger.info("  yfinance 不可用，使用 AI 市场知识")

    # 2. 采集财经新闻
    global_news, china_news = _fetch_all_news()
    logger.info(f"  采集 {len(global_news.split(chr(10)))} 条全球财经新闻")
    logger.info(f"  采集 {len(china_news.split(chr(10)))} 条中国财经新闻")

    # 3. 构建 AI 分析请求
    index_lines = []
    if indices:
        for idx in indices:
            arrow = "↑" if idx["change_pct"] > 0 else ("↓" if idx["change_pct"] < 0 else "→")
            index_lines.append(
                f"  {idx['name']}: {idx['value']} ({arrow}{abs(idx['change_pct']):.2f}%)"
            )
    index_text = "\n".join(index_lines) if index_lines else "（请根据你的知识估算当前主要指数点位，包括上证指数、沪深300、恒生指数）"

    # 合并经济类新闻
    combined_global = global_news
    if economic_news:
        combined_global = (
            global_news + "\n\n[Additional Economic Headlines]\n" + economic_news[:1500]
        )

    user_message = f"""Today is {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC (Beijing: +8h).

**Current Index Data (real-time where available):**
{index_text}

**Global Financial News:**
{combined_global[:3000]}

**China/HK Financial News:**
{china_news[:2000]}

Please analyze ALL THREE markets and provide recommendations in the required JSON format:
1. US stocks: high potential + event-driven
2. A-shares (中国A股): high potential + event-driven — MUST include this section
3. HK stocks (港股): high potential + event-driven — MUST include this section

For A-shares and HK stocks, pay special attention to:
- China policy directions (中央经济政策、行业监管变化)
- Northbound/Southbound capital flows (北向/南向资金)
- Sector rotation and valuation levels
- Upcoming earnings or economic data releases"""

    # 4. 调用 AI 分析
    try:
        result = _call_deepseek(STOCK_SYSTEM_PROMPT, user_message)

        # 确保所有字段完整
        _ensure_field(result, "market_overview", {})
        _ensure_field(result, "high_potential", [])
        _ensure_field(result, "event_driven", [])

        # A股
        if "a_shares" not in result:
            result["a_shares"] = {}
        _ensure_field(result["a_shares"], "high_potential", [])
        _ensure_field(result["a_shares"], "event_driven", [])

        # 港股
        if "hk_stocks" not in result:
            result["hk_stocks"] = {}
        _ensure_field(result["hk_stocks"], "high_potential", [])
        _ensure_field(result["hk_stocks"], "event_driven", [])

        # 限制推荐数量
        for market_key in ["high_potential", "event_driven"]:
            result[market_key] = result[market_key][:STOCK_MAX_RECOMMENDATIONS]
        for mkt in ["a_shares", "hk_stocks"]:
            for key in ["high_potential", "event_driven"]:
                result[mkt][key] = result[mkt][key][:STOCK_MAX_RECOMMENDATIONS]

        # 注入实际指数数据
        if indices and not result["market_overview"].get("indices"):
            result["market_overview"]["indices"] = indices

        # 统计
        us_hp = len(result["high_potential"])
        us_ed = len(result["event_driven"])
        a_hp = len(result["a_shares"]["high_potential"])
        a_ed = len(result["a_shares"]["event_driven"])
        hk_hp = len(result["hk_stocks"]["high_potential"])
        hk_ed = len(result["hk_stocks"]["event_driven"])

        logger.info(
            f"股票分析完成: "
            f"美股({us_hp}HP/{us_ed}ED) | "
            f"A股({a_hp}HP/{a_ed}ED) | "
            f"港股({hk_hp}HP/{hk_ed}ED)"
        )

        return result

    except Exception as e:
        logger.error(f"股票分析失败: {e}")
        return {
            "market_overview": {
                "indices": indices,
                "market_sentiment": "数据暂缺",
                "summary_zh": "股票分析暂时不可用，请稍后重试",
                "summary_en": "Stock analysis temporarily unavailable, please retry later",
            },
            "high_potential": [], "event_driven": [],
            "a_shares": {"high_potential": [], "event_driven": []},
            "hk_stocks": {"high_potential": [], "event_driven": []},
        }


def _ensure_field(d: dict, key: str, default):
    """确保字典中存在指定字段"""
    if key not in d:
        d[key] = default
