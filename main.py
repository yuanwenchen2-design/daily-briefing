#!/usr/bin/env python3
"""
每日简报 · Daily Briefing
==========================
双击桌面快捷方式即可打开。开机自动运行。
DeepSeek AI 驱动 · 中英双语 · 语音播报
"""
import argparse
import logging
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily-briefing")

sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_LANGUAGE, LANGUAGES, DEEPSEEK_API_KEY, AUDIO_DIR, STOCK_ANALYSIS_ENABLED
from database import init_db, save_briefing, clear_old_briefings, clear_today_briefings, get_today_briefings, save_stock_recommendations, clear_today_stocks, get_stock_recommendations
from news_fetcher import fetch_all_news, format_headlines
from summarizer import summarize, build_briefing_text
from tts_engine import generate_briefing_audio_sync
from stock_analyzer import analyze_stocks

HOST = "127.0.0.1"
PORT = 5200
BROWSER_URL = f"http://{HOST}:{PORT}"


def today_has_briefing(language: str) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    return len(get_today_briefings(today, language)) > 0


def run_full_pipeline(language: str = DEFAULT_LANGUAGE) -> bool:
    """采集→AI摘要(双语)→TTS→保存"""
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    is_en = language == "english"

    if DEEPSEEK_API_KEY:
        logger.info(f"══════ 每日简报 · {lang_name} (AI 增强) ══════")
    else:
        logger.info(f"══════ 每日简报 · {lang_name} ══════")

    # 1. 采集新闻
    logger.info("[1/5] 采集全球新闻...")
    try:
        news_data = fetch_all_news()
    except Exception as e:
        logger.error(f"采集失败: {e}")
        return False
    total = sum(len(v) for v in news_data.values())
    if total == 0:
        logger.error("未采集到新闻")
        return False
    logger.info(f"  采集 {total} 条（已过滤广告）")

    # 2. AI 摘要（DeepSeek 自动完成翻译）
    logger.info("[2/5] AI 摘要 + 翻译...")
    news_text = format_headlines(news_data)
    summary = summarize(news_text, language)

    ai_total = sum(len(v) for v in summary.values())
    logger.info(f"  提取 {ai_total} 条重要新闻")

    # 2.5 股票分析
    stock_data = None
    if STOCK_ANALYSIS_ENABLED:
        logger.info("[2.5/5] 股票分析 (AI)...")
        try:
            # 提取经济类新闻文本供股票分析参考
            economic_news = news_text  # format_headlines 已包含所有分类
            stock_data = analyze_stocks(economic_news)
            if stock_data and (stock_data.get("high_potential") or stock_data.get("event_driven")):
                logger.info(f"  高潜力股 {len(stock_data.get('high_potential', []))} | 事件驱动 {len(stock_data.get('event_driven', []))}")
            else:
                logger.info("  股票分析: 暂无推荐")
        except Exception as e:
            logger.warning(f"  股票分析跳过: {e}")
            stock_data = None

    # 3. 构建简报文本
    logger.info("[3/5] 构建双语简报...")
    plain_text, html_text = build_briefing_text(summary, language)

    # 打印文本预览
    preview = plain_text[:1000]
    print(f"\n{preview}\n{'...' if len(plain_text) > 1000 else ''}\n")

    # 4. TTS 语音合成（三种语言全部生成）
    logger.info("[4/5] 生成语音（中文+英文+粤语）...")
    audio_paths = {}

    # 中文语音
    try:
        path = generate_briefing_audio_sync(plain_text, "chinese")
        if path:
            audio_paths["chinese"] = path
    except Exception as e:
        logger.warning(f"  中文语音跳过: {e}")

    # 英文语音
    try:
        en_plain, _ = build_briefing_text(summary, "english")
        path = generate_briefing_audio_sync(en_plain, "english")
        if path:
            audio_paths["english"] = path
    except Exception as e:
        logger.warning(f"  英文语音跳过: {e}")

    # 粤语语音（用中文文本 + 粤语 TTS）
    try:
        path = generate_briefing_audio_sync(plain_text, "cantonese")
        if path:
            audio_paths["cantonese"] = path
    except Exception as e:
        logger.warning(f"  粤语语音跳过: {e}")

    logger.info(f"  语音就绪: {list(audio_paths.keys())}")

    # 5. 保存到数据库
    logger.info("[5/5] 保存...")
    today = datetime.now().strftime("%Y-%m-%d")
    clear_today_briefings(language, today)  # 清理旧数据
    for cat_key, items in summary.items():
        for item in items:
            # 根据语言选择存储的标题/摘要
            if is_en:
                title = item.get("title_en") or item.get("title", "")
                s = item.get("summary_en") or item.get("summary", "")
            else:
                title = item.get("title_zh") or item.get("title_en") or item.get("title", "")
                s = item.get("summary_zh") or item.get("summary_en") or item.get("summary", "")
            save_briefing({
                "date": today, "language": language,
                "category": cat_key,
                "title": title, "summary": s,
                "importance": item.get("importance", 3),
                "source_url": "", "audio_path": audio_paths.get(language, ""),
            })
    clear_old_briefings(30)

    # 持久化完整双语 JSON（避免重启丢失）
    import json
    cache_file = AUDIO_DIR / "_current_summary.json"
    cache_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 持久化股票分析数据
    if stock_data:
        today = datetime.now().strftime("%Y-%m-%d")
        clear_today_stocks(today)

        # 美股
        hp = stock_data.get("high_potential", [])
        ed = stock_data.get("event_driven", [])
        if hp:
            save_stock_recommendations(today, "high_potential", hp)
        if ed:
            save_stock_recommendations(today, "event_driven", ed)

        # A股
        a_shares = stock_data.get("a_shares", {})
        a_hp = a_shares.get("high_potential", [])
        a_ed = a_shares.get("event_driven", [])
        if a_hp:
            save_stock_recommendations(today, "a_high_potential", a_hp)
        if a_ed:
            save_stock_recommendations(today, "a_event_driven", a_ed)

        # 港股
        hk_stocks = stock_data.get("hk_stocks", {})
        hk_hp = hk_stocks.get("high_potential", [])
        hk_ed = hk_stocks.get("event_driven", [])
        if hk_hp:
            save_stock_recommendations(today, "hk_high_potential", hk_hp)
        if hk_ed:
            save_stock_recommendations(today, "hk_event_driven", hk_ed)

        # 缓存股票 JSON
        stock_cache = AUDIO_DIR / "_current_stocks.json"
        stock_cache.write_text(json.dumps(stock_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 注入到 Web 服务器
    from web_server import set_briefing, set_stock_data
    set_briefing(summary, plain_text, html_text, language, audio_paths)
    if stock_data:
        set_stock_data(stock_data)

    logger.info("简报完成！")
    return True


def load_briefing_from_db(language: str):
    """从缓存文件恢复完整双语简报（供快速启动）"""
    from web_server import set_briefing, set_stock_data
    from summarizer import build_briefing_text
    import json

    # 尝试从缓存加载完整双语 JSON
    summary = None
    cache_file = AUDIO_DIR / "_current_summary.json"
    if cache_file.exists():
        try:
            summary = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            summary = None

    # 缓存不可用则从 DB 重建（仅单语言）
    if summary is None:
        today = datetime.now().strftime("%Y-%m-%d")
        records = get_today_briefings(today, language)
        summary = {}
        for r in records:
            cat = r["category"]
            if cat not in summary:
                summary[cat] = []
            summary[cat].append({
                "title": r["title"], "title_en": r["title"],
                "title_zh": r["title"],
                "summary": r["summary"], "summary_en": r["summary"],
                "summary_zh": r["summary"],
                "importance": r["importance"],
            })

    plain_text, html_text = build_briefing_text(summary, language)
    audio_paths = {}
    for lang_key in ["chinese", "english", "cantonese"]:
        ap = AUDIO_DIR / f"briefing_{lang_key}.mp3"
        if ap.exists():
            audio_paths[lang_key] = str(ap)
    set_briefing(summary, plain_text, html_text, language, audio_paths)

    # 加载缓存的股票数据
    stock_cache = AUDIO_DIR / "_current_stocks.json"
    if stock_cache.exists():
        try:
            stock_data = json.loads(stock_cache.read_text(encoding="utf-8"))
            set_stock_data(stock_data)
        except Exception:
            pass


def start_server():
    """启动 Flask + 打开浏览器"""
    from web_server import app

    def _run():
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(1.5)
    webbrowser.open(BROWSER_URL)
    logger.info(f"仪表盘 → {BROWSER_URL}")
    return t


def main():
    parser = argparse.ArgumentParser(description="每日简报 · Daily Briefing")
    parser.add_argument("--lang", "-l", default=DEFAULT_LANGUAGE,
                        choices=["chinese", "english", "cantonese"])
    parser.add_argument("--fetch-only", "-f", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--force", action="store_true", help="强制重新采集")
    args = parser.parse_args()

    init_db()

    if args.fetch_only:
        news_data = fetch_all_news()
        print(format_headlines(news_data))
        return

    need_fetch = args.force or not today_has_briefing(args.lang)

    if need_fetch:
        logger.info("生成今日简报...")
        ok = run_full_pipeline(args.lang)
        if not ok:
            logger.error("简报生成失败")
            sys.exit(1)
    else:
        logger.info("今日简报已存在，快速启动...")
        load_briefing_from_db(args.lang)

    if args.no_browser:
        logger.info("完成（--no-browser）")
        return

    start_server()

    lang_name = LANGUAGES[args.lang]["name"]
    print(f"""
╔════════════════════════════════╗
║   📡 每日简报 · {lang_name}      ║
║   {BROWSER_URL}          ║
║   1=中文 2=English 3=粵語    ║
║   空格=播报                   ║
║   关闭此窗口 = 退出          ║
╚════════════════════════════════╝
""")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("已退出")


if __name__ == "__main__":
    main()
