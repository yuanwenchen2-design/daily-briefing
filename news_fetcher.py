"""
每日简报 - 新闻采集模块
从多个 RSS 源采集过去 24 小时的新闻标题，过滤广告/垃圾内容
"""
import concurrent.futures
import logging
import re
from datetime import datetime, timedelta

import feedparser
import requests

from config import CATEGORIES, MAX_NEWS_PER_CATEGORY, SPAM_KEYWORDS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
TIMEOUT = 15


def _is_spam(title: str, summary: str = "") -> bool:
    """检查标题/摘要是否包含广告或垃圾内容"""
    text = (title + " " + summary).lower()
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return True
    return False


def _clean_html(text: str) -> str:
    """去除 HTML 标签"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_single_feed(url: str) -> list[dict]:
    """抓取单个 RSS 源"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        logger.warning(f"RSS 抓取失败 [{url[:60]}]: {e}")
        return []

    cutoff = datetime.now() - timedelta(hours=24)
    entries = []

    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        if not title or len(title) < 10:
            continue

        summary_raw = (entry.get("summary") or entry.get("description") or "")
        summary = _clean_html(summary_raw)[:300]

        # 过滤广告/垃圾
        if _is_spam(title, summary):
            continue

        # 解析时间
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                from time import mktime
                published = datetime.fromtimestamp(mktime(entry.published_parsed))
            except Exception:
                pass
        if published and published < cutoff:
            continue

        entries.append({
            "title": title,
            "summary": summary,
            "url": (entry.get("link") or "").strip(),
            "published": published.isoformat() if published else "",
            "source": feed.feed.get("title", url),
        })

    return entries


def fetch_all_news() -> dict[str, list[dict]]:
    """并发抓取所有类别的新闻"""
    all_news: dict[str, list[dict]] = {}
    all_urls: list[tuple[str, str]] = []

    for cat_key, cat_info in CATEGORIES.items():
        for feed_url in cat_info["feeds"]:
            all_urls.append((cat_key, feed_url))

    logger.info(f"开始抓取 {len(all_urls)} 个 RSS 源...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_fetch_single_feed, url): (cat_key, url)
            for cat_key, url in all_urls
        }
        for future in concurrent.futures.as_completed(futures):
            cat_key, url = futures[future]
            try:
                entries = future.result()
                if cat_key not in all_news:
                    all_news[cat_key] = []
                all_news[cat_key].extend(entries)
                logger.info(f"  ✓ [{cat_key}] {url[:60]}... → {len(entries)} 条")
            except Exception as e:
                logger.error(f"  ✗ [{cat_key}] {url[:60]}... → {e}")

    # 去重 & 限制数量
    for cat_key in all_news:
        seen: set[str] = set()
        unique = []
        for entry in all_news[cat_key]:
            key = re.sub(r"[^a-z0-9]", "", entry["title"][:50].lower())
            if key and key not in seen:
                seen.add(key)
                unique.append(entry)
        # 优先有摘要的、标题更长的
        unique.sort(key=lambda e: (len(e.get("summary", "")), len(e["title"])), reverse=True)
        all_news[cat_key] = unique[:MAX_NEWS_PER_CATEGORY]

    total = sum(len(v) for v in all_news.values())
    logger.info(f"新闻抓取完成，共 {total} 条（已过滤广告、已去重）")
    return all_news


def format_headlines(news_dict: dict[str, list[dict]]) -> str:
    """将新闻字典格式化为文本，供 AI 摘要使用"""
    lines = []
    for cat_key, cat_info in CATEGORIES.items():
        entries = news_dict.get(cat_key, [])
        if not entries:
            continue
        lines.append(f"\n## {cat_info['name_en']} / {cat_info['name_zh']} ({len(entries)} articles)")
        lines.append("-" * 50)
        for i, entry in enumerate(entries, 1):
            lines.append(f"{i}. {entry['title']}")
            if entry.get("summary"):
                lines.append(f"   {entry['summary'][:200]}")
        lines.append("")
    return "\n".join(lines)
