"""数据库操作 —— 所有 SQL 集中于此，直接管理连接，不依赖 Flask g。"""

import json
import os
import sqlite3
from datetime import date

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "news.db")


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS news (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            url         TEXT,
            source      TEXT DEFAULT '',
            content     TEXT DEFAULT '',
            summary     TEXT DEFAULT '',
            published_at DATETIME,
            date        TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT UNIQUE NOT NULL,
            content     TEXT NOT NULL,
            news_ids    TEXT DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_news_date ON news(date);
        CREATE INDEX IF NOT EXISTS idx_news_url ON news(url);
        CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summary(date);
    """)
    conn.commit()
    conn.close()


# ── batch ────────────────────────────────────────────────────

def save_news(items, daily_digest=""):
    """批量存入新闻 + 日报摘要。自动去重。返回新增条数。"""
    today = date.today().isoformat()
    count = 0
    conn = _connect()
    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")
        if url:
            exists = conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone()
            if exists:
                continue
        if title:
            exists = conn.execute("SELECT 1 FROM news WHERE title = ?", (title,)).fetchone()
            if exists:
                continue
        conn.execute(
            """INSERT INTO news (title, url, source, content, summary, published_at, date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, url, item.get("source", ""), item.get("content", ""),
             item.get("summary", ""), item.get("published_at", today), today),
        )
        count += 1

    if daily_digest:
        news_ids = conn.execute(
            "SELECT id FROM news WHERE date = ? ORDER BY id", (today,)
        ).fetchall()
        ids_json = json.dumps([r["id"] for r in news_ids], ensure_ascii=False)
        conn.execute(
            """INSERT INTO daily_summary (date, content, news_ids) VALUES (?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET content=excluded.content, news_ids=excluded.news_ids""",
            (today, daily_digest, ids_json),
        )

    conn.commit()
    conn.close()
    return count


# ── news ─────────────────────────────────────────────────────

def get_news_by_date(date_str, page=1, per_page=20):
    conn = _connect()
    offset = (page - 1) * per_page
    rows = conn.execute(
        "SELECT * FROM news WHERE date = ? ORDER BY published_at DESC LIMIT ? OFFSET ?",
        (date_str, per_page, offset),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM news WHERE date = ?", (date_str,)
    ).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_news(news_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_today_news():
    today = date.today().isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, url, summary, published_at as time FROM news WHERE date = ? ORDER BY time DESC",
        (today,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_news_by_url(url):
    conn = _connect()
    row = conn.execute("SELECT id FROM news WHERE url = ?", (url,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_news_by_title(title):
    conn = _connect()
    row = conn.execute("SELECT id FROM news WHERE title = ?", (title,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_news(title, date_str, url="", source="", content="", summary="", published_at=None):
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO news (title, url, source, content, summary, published_at, date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, url, source, content, summary, published_at or date_str, date_str),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def update_news_summary(news_id, summary):
    conn = _connect()
    conn.execute("UPDATE news SET summary = ? WHERE id = ?", (summary, news_id))
    conn.commit()
    conn.close()


def delete_news(news_id):
    conn = _connect()
    conn.execute("DELETE FROM news WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()


def get_available_dates():
    conn = _connect()
    rows = conn.execute(
        "SELECT date, COUNT(*) as count FROM news GROUP BY date ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── daily_summary ────────────────────────────────────────────

def get_summary(date_str):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM daily_summary WHERE date = ?", (date_str,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["news_ids"] = json.loads(d["news_ids"])
        return d
    return None


def upsert_summary(date_str, content, news_ids_json):
    conn = _connect()
    conn.execute(
        """INSERT INTO daily_summary (date, content, news_ids)
           VALUES (?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET content=excluded.content, news_ids=excluded.news_ids""",
        (date_str, content, news_ids_json),
    )
    conn.commit()
    conn.close()


def has_summary(date_str):
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM daily_summary WHERE date = ?", (date_str,)
    ).fetchone()
    conn.close()
    return row is not None
