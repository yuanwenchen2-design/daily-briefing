"""
每日简报 - 数据库模块
SQLite 存储历史简报
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from config import BASE_DIR

DB_PATH = BASE_DIR / "briefings.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            language TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            importance INTEGER DEFAULT 3,
            source_url TEXT,
            audio_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_briefings_date ON briefings(date);
        CREATE INDEX IF NOT EXISTS idx_briefings_category ON briefings(category);

        CREATE TABLE IF NOT EXISTS stock_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL,
            upside_pct REAL,
            downside_pct REAL,
            risk_reward REAL,
            catalyst TEXT,
            confidence INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_stocks_date ON stock_recommendations(date);
        CREATE INDEX IF NOT EXISTS idx_stocks_type ON stock_recommendations(type);
    """)
    conn.commit()
    conn.close()


def save_briefing(briefing_data: dict) -> int:
    """保存一条简报记录"""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO briefings (date, language, category, title, summary, importance, source_url, audio_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            briefing_data["date"],
            briefing_data["language"],
            briefing_data["category"],
            briefing_data["title"],
            briefing_data["summary"],
            briefing_data.get("importance", 3),
            briefing_data.get("source_url", ""),
            briefing_data.get("audio_path", ""),
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def clear_today_briefings(language: str = "chinese", date_str: str = None):
    """删除当天指定语言的旧简报（用于强制刷新）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("DELETE FROM briefings WHERE date = ? AND language = ?",
                 (date_str, language))
    conn.commit()
    conn.close()


def get_today_briefings(date_str: str = None, language: str = "chinese") -> list:
    """获取指定日期的简报"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM briefings
           WHERE date = ? AND language = ?
           ORDER BY category, importance DESC""",
        (date_str, language),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_dates(days: int = 7) -> list:
    """获取最近有简报的日期列表"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT date FROM briefings WHERE date >= ? ORDER BY date DESC",
        (since,),
    ).fetchall()
    conn.close()
    return [r["date"] for r in rows]


def clear_old_briefings(days: int = 30):
    """清理旧简报"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("DELETE FROM briefings WHERE date < ?", (cutoff,))
    conn.execute("DELETE FROM stock_recommendations WHERE date < ?", (cutoff,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  股票推荐数据库操作
# ═══════════════════════════════════════════

def save_stock_recommendations(date: str, rec_type: str, stocks: list):
    """保存股票推荐。rec_type 格式: "high_potential" (美股) / "a_high_potential" (A股) / "hk_high_potential" (港股) 等"""
    conn = get_db()
    for s in stocks:
        # 事件驱动股：将主要事件文本存入 catalyst 字段
        catalyst = s.get("catalyst", "") or s.get("catalyst_zh", "") or s.get("event_zh", "")
        if not catalyst:
            catalyst = s.get("catalyst_en", "") or s.get("event_en", "")

        conn.execute(
            """INSERT INTO stock_recommendations
               (date, type, symbol, name, price, upside_pct, downside_pct, risk_reward, catalyst, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date, rec_type,
                s.get("symbol", ""), s.get("name", ""),
                s.get("price"), s.get("upside_pct"),
                s.get("downside_pct"), s.get("risk_reward"),
                catalyst,
                s.get("confidence", 3),
            ),
        )
    conn.commit()
    conn.close()


def clear_today_stocks(date: str = None):
    """删除当天股票推荐（用于强制刷新）"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("DELETE FROM stock_recommendations WHERE date = ?", (date,))
    conn.commit()
    conn.close()


def get_stock_recommendations(date: str = None) -> dict:
    """获取指定日期的股票推荐，按市场分组"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM stock_recommendations
           WHERE date = ? ORDER BY type, confidence DESC""",
        (date,),
    ).fetchall()
    conn.close()

    result = {
        "market_overview": {},
        "high_potential": [], "event_driven": [],
        "a_shares": {"high_potential": [], "event_driven": []},
        "hk_stocks": {"high_potential": [], "event_driven": []},
    }

    for r in rows:
        d = dict(r)
        rec_type = d.pop("type", "high_potential")
        d.pop("id", None)
        d.pop("date", None)
        d.pop("created_at", None)

        # 按 type 前缀分组
        if rec_type.startswith("a_"):
            sub = rec_type[2:]  # "high_potential" or "event_driven"
            if sub in result["a_shares"]:
                result["a_shares"][sub].append(d)
        elif rec_type.startswith("hk_"):
            sub = rec_type[3:]  # "high_potential" or "event_driven"
            if sub in result["hk_stocks"]:
                result["hk_stocks"][sub].append(d)
        elif rec_type in result:
            result[rec_type].append(d)

    return result
