"""
每日简报 · Daily Briefing — 生产入口（Render / gunicorn）
"""
import os
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wsgi")

from database import init_db

init_db()

# 尝试从缓存加载今日简报
try:
    from main import load_briefing_from_db
    from config import DEFAULT_LANGUAGE

    load_briefing_from_db(DEFAULT_LANGUAGE)
    logger.info("缓存简报已加载")
except Exception as e:
    logger.warning(f"加载缓存简报失败: {e}")

# 后台自动刷新今日简报
def _background_refresh():
    """启动后延迟 3 秒，如果没有今日简报则自动生成"""
    import time
    time.sleep(3)
    try:
        from main import today_has_briefing, run_full_pipeline
        from config import DEFAULT_LANGUAGE
        if not today_has_briefing(DEFAULT_LANGUAGE):
            logger.info("未找到今日简报，自动生成...")
            run_full_pipeline(DEFAULT_LANGUAGE)
    except Exception as e:
        logger.error(f"后台刷新失败: {e}")

t = threading.Thread(target=_background_refresh, daemon=True)
t.start()

# 暴露 Flask app 给 gunicorn
from web_server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5200))
    app.run(host="0.0.0.0", port=port)
