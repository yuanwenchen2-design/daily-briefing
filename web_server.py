"""
每日简报 - Web 服务器
Flask 驱动的双语简报仪表盘
"""
import json
import logging
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from config import BASE_DIR, AUDIO_DIR, CATEGORIES, LANGUAGES
from database import get_today_briefings, get_recent_dates, init_db, get_stock_recommendations

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

_current_briefing: dict = {
    "summary": {}, "plain_text": "", "html_text": "",
    "language": "chinese", "date": "", "audio_paths": {},
}

_current_stocks: dict = {
    "market_overview": {}, "high_potential": [], "event_driven": [],
}

# 后台刷新锁
_refresh_lock = threading.Lock()
_is_refreshing = False


def set_briefing(summary: dict, plain_text: str, html_text: str, language: str, audio_paths: dict):
    global _current_briefing
    _current_briefing = {
        "summary": summary,
        "plain_text": plain_text,
        "html_text": html_text,
        "language": language,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "audio_paths": audio_paths,
    }


def set_stock_data(data: dict):
    global _current_stocks
    _current_stocks = data


# ==================== 页面 ====================

@app.route("/")
def index():
    return render_template("index.html")


# ==================== API ====================

@app.route("/api/briefing")
def api_briefing():
    """返回简报 — summary 内已包含中英双语字段，前端按语言选择显示"""
    date = request.args.get("date", _current_briefing["date"])
    language = request.args.get("lang", _current_briefing["language"])

    # 内存中有今天的数据 → 直接返回（summary 已是双语，不限语言）
    if date == _current_briefing["date"] and _current_briefing["summary"]:
        # 按需重建对应语言的 plain_text / html_text
        from summarizer import build_briefing_text
        plain_text, html_text = build_briefing_text(_current_briefing["summary"], language)
        return jsonify({
            "success": True,
            "data": {
                "summary": _current_briefing["summary"],
                "html_text": html_text,
                "plain_text": plain_text,
                "language": language,
                "date": date,
                "audio_available": bool(_current_briefing["audio_paths"].get(language)),
                "stocks": _current_stocks,
            },
        })

    # 历史数据从数据库加载
    records = get_today_briefings(date, language)
    if not records:
        return jsonify({"success": False, "message": "No briefing found for this date"})

    summary = {}
    for rec in records:
        cat = rec["category"]
        if cat not in summary:
            summary[cat] = []
        summary[cat].append({
            "title": rec["title"], "title_en": rec["title"], "title_zh": rec["title"],
            "summary": rec["summary"], "summary_en": rec["summary"], "summary_zh": rec["summary"],
            "importance": rec["importance"],
        })

    return jsonify({
        "success": True,
        "data": {
            "summary": summary, "date": date, "language": language,
            "audio_available": False,
        },
    })


@app.route("/api/refresh")
def api_refresh():
    """强制重新采集简报"""
    global _is_refreshing
    lang = request.args.get("lang", _current_briefing["language"])

    if _is_refreshing:
        return jsonify({"success": False, "message": "刷新进行中，请稍候"})

    def _do_refresh():
        global _is_refreshing
        with _refresh_lock:
            _is_refreshing = True
        try:
            from main import run_full_pipeline
            run_full_pipeline(lang)
        except Exception as e:
            logger.error(f"后台刷新失败: {e}")
        finally:
            with _refresh_lock:
                _is_refreshing = False

    t = threading.Thread(target=_do_refresh, daemon=True)
    t.start()

    # 等待一小段时间让刷新开始
    time.sleep(2)
    return jsonify({"success": True, "message": "刷新已开始"})


@app.route("/api/dates")
def api_dates():
    return jsonify({"success": True, "dates": get_recent_dates(7)})


@app.route("/api/categories")
def api_categories():
    return jsonify({"success": True, "categories": {
        k: {"name_zh": v["name_zh"], "name_en": v["name_en"], "icon": v["icon"], "color": v["color"]}
        for k, v in CATEGORIES.items()
    }})


@app.route("/api/languages")
def api_languages():
    return jsonify({"success": True, "languages": {
        k: {"name": v["name"], "flag": v["flag"], "voice": v["voice"]}
        for k, v in LANGUAGES.items()
    }})


@app.route("/audio/<language>")
def serve_audio(language: str):
    audio_path = AUDIO_DIR / f"briefing_{language}.mp3"
    if audio_path.exists():
        return send_file(str(audio_path), mimetype="audio/mpeg")
    return jsonify({"success": False, "message": "Audio not found"}), 404


@app.route("/api/stocks")
def api_stocks():
    """返回今日股票推荐"""
    date = request.args.get("date", _current_briefing["date"])

    # 内存中有今天的数据 → 直接返回
    if date == _current_briefing["date"] and _current_stocks:
        return jsonify({
            "success": True,
            "data": _current_stocks,
        })

    # 历史数据从数据库加载
    stocks = get_stock_recommendations(date)
    if not stocks.get("high_potential") and not stocks.get("event_driven"):
        return jsonify({"success": False, "message": "No stock data found for this date", "data": stocks})

    return jsonify({"success": True, "data": stocks})


@app.route("/api/status")
def api_status():
    return jsonify({
        "success": True,
        "has_briefing": bool(_current_briefing["summary"]),
        "has_stocks": bool(_current_stocks.get("high_potential") or _current_stocks.get("event_driven")),
        "date": _current_briefing["date"],
        "language": _current_briefing["language"],
    })


@app.route("/api/debug")
def api_debug():
    """诊断端点：检查 API 配置、数据加载状态"""
    from config import DEEPSEEK_API_KEY, BASE_DIR
    import subprocess, os

    # Git 版本
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        git_hash = "unknown"

    # API Key 状态
    key_masked = ""
    if DEEPSEEK_API_KEY:
        key_masked = DEEPSEEK_API_KEY[:8] + "..." + DEEPSEEK_API_KEY[-4:]

    # 测试 API 连通性
    api_test = "not_tested"
    if DEEPSEEK_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            r = client.chat.completions.create(
                model="deepseek-chat", max_tokens=5,
                messages=[{"role": "user", "content": "say hi"}],
            )
            api_test = "ok" if r.choices else "no_response"
        except Exception as e:
            api_test = f"error: {str(e)[:100]}"

    # 缓存文件
    cache_files = {}
    for name in ["_current_summary.json", "_current_stocks.json"]:
        p = BASE_DIR / "audio" / name
        cache_files[name] = {
            "exists": p.exists(),
            "size": p.stat().st_size if p.exists() else 0,
        }

    # 数据状态
    briefing_summary = _current_briefing.get("summary", {})
    briefing_cats = {k: len(v) for k, v in briefing_summary.items()} if briefing_summary else {}
    first_item = None
    for items in briefing_summary.values():
        if items:
            first_item = {
                "has_title_en": bool(items[0].get("title_en")),
                "has_title_zh": bool(items[0].get("title_zh")),
                "title_en": (items[0].get("title_en") or "")[:60],
                "title_zh": (items[0].get("title_zh") or "")[:60],
            }
            break

    stock_status = {
        "has_high_potential": bool(_current_stocks.get("high_potential")),
        "has_event_driven": bool(_current_stocks.get("event_driven")),
        "has_a_shares": bool(_current_stocks.get("a_shares")),
        "has_hk": bool(_current_stocks.get("hk_stocks")),
    }

    return jsonify({
        "success": True,
        "git": git_hash,
        "api_key": {
            "configured": bool(DEEPSEEK_API_KEY),
            "masked": key_masked,
            "test": api_test,
        },
        "briefing": {
            "categories": briefing_cats,
            "total_items": sum(briefing_cats.values()),
            "sample": first_item,
        },
        "stocks": stock_status,
        "cache": cache_files,
        "env": {
            "DEEPSEEK_API_KEY_set": bool(os.getenv("DEEPSEEK_API_KEY")),
            "DEFAULT_LANGUAGE": os.getenv("DEFAULT_LANGUAGE", "(default)"),
        },
    })


def start_server(host: str = "127.0.0.1", port: int = 5200, open_browser: bool = True):
    init_db()
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    logger.info(f"Web 服务器启动: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_server()
