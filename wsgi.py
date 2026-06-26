"""
每日简报 · Daily Briefing — 生产入口（Render / gunicorn）
"""
import os
import sys
import threading
import logging
import traceback
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wsgi")

from database import init_db
init_db()

# ── 使用 web_server 的 pipeline_status（同一进程共享）──
from web_server import pipeline_status


def _set_pipeline_state(state: str, error: str = None, step: str = None):
    now = datetime.now().isoformat()
    pipeline_status["state"] = state
    if state == "running":
        pipeline_status["started_at"] = now
    elif state in ("done", "failed"):
        pipeline_status["finished_at"] = now
    if error:
        pipeline_status["last_error"] = error
    if step:
        pipeline_status["steps_completed"].append(step)


# ── 尝试从缓存加载 ──
try:
    from main import load_briefing_from_db
    from config import DEFAULT_LANGUAGE
    load_briefing_from_db(DEFAULT_LANGUAGE)
    logger.info("缓存简报已加载")
except Exception as e:
    logger.warning(f"加载缓存失败: {e}")


# ── 后台自动生成今日简报 ──
def _background_refresh():
    import time
    time.sleep(5)  # 等 gunicorn 完全就绪
    try:
        from main import today_has_briefing, run_full_pipeline
        from config import DEFAULT_LANGUAGE

        if today_has_briefing(DEFAULT_LANGUAGE):
            logger.info("今日简报已存在，跳过生成")
            _set_pipeline_state("done", step="from_cache")
            return

        logger.info("=== 开始自动生成今日简报 ===")
        _set_pipeline_state("running", step="start")

        ok = run_full_pipeline(DEFAULT_LANGUAGE)
        if ok:
            _set_pipeline_state("done", step="pipeline_complete")
            logger.info("=== 简报自动生成完成 ===")
        else:
            _set_pipeline_state("failed", error="run_full_pipeline 返回 False")
            logger.error("简报生成失败")
    except Exception as e:
        tb = traceback.format_exc()
        _set_pipeline_state("failed", error=f"{e}\n{tb[-500:]}")
        logger.error(f"后台刷新异常: {e}\n{tb}")


t = threading.Thread(target=_background_refresh, daemon=True)
t.start()

# 暴露 Flask app 给 gunicorn
from web_server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5200))
    app.run(host="0.0.0.0", port=port)
