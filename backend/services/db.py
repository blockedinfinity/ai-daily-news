"""数据库操作 —— PostgreSQL（Render / Neon / Supabase 等兼容）。

通过环境变量 DATABASE_URL 连接，无需本地 SQLite 文件。
示例：postgresql://user:pass@host:5432/dbname
"""

import json
import os
from datetime import date
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import psycopg2
import psycopg2.extras

_raw_url = os.getenv("DATABASE_URL", "")

# psycopg2 不支持 channel_binding 参数，需要移除
def _clean_url(raw):
    parsed = urlparse(raw)
    params = parse_qsl(parsed.query)
    params = [(k, v) for k, v in params if k != "channel_binding"]
    cleaned = parsed._replace(query=urlencode(params))
    return urlunparse(cleaned)

DATABASE_URL = _clean_url(_raw_url) if _raw_url else ""


def _cn(d):
    """返回中文优先的 title/content（有翻译用翻译，否则用原文）。"""
    d = dict(d)
    if d.get("title_cn"):
        d["title"] = d["title_cn"]
    if d.get("content_cn"):
        d["content"] = d["content_cn"]
    return d


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 环境变量未设置")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id          SERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            url         TEXT DEFAULT '',
            source      TEXT DEFAULT '',
            content     TEXT DEFAULT '',
            summary     TEXT DEFAULT '',
            title_cn    TEXT DEFAULT '',
            content_cn  TEXT DEFAULT '',
            published_at TIMESTAMP,
            date        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            id          SERIAL PRIMARY KEY,
            date        TEXT UNIQUE NOT NULL,
            content     TEXT NOT NULL,
            news_ids    TEXT DEFAULT '[]',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # 创建索引（忽略已存在）
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_news_date ON news(date)",
        "CREATE INDEX IF NOT EXISTS idx_news_url ON news(url)",
        "CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summary(date)",
    ]:
        try:
            cur.execute(idx_sql)
        except psycopg2.Error:
            pass
    conn.commit()
    cur.close()
    conn.close()


# ── batch ────────────────────────────────────────────────────

def save_news(items, daily_digest=""):
    """批量存入新闻 + 日报摘要。自动去重。返回新增条数。"""
    today = date.today().isoformat()
    count = 0
    conn = _connect()
    cur = conn.cursor()
    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")
        if url:
            cur.execute("SELECT 1 FROM news WHERE url = %s", (url,))
            if cur.fetchone():
                continue
        if title:
            cur.execute("SELECT 1 FROM news WHERE title = %s", (title,))
            if cur.fetchone():
                continue
        cur.execute(
            """INSERT INTO news (title, url, source, content, summary, title_cn, content_cn, published_at, date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (title, url, item.get("source", ""), item.get("content", ""),
             item.get("summary", ""), item.get("title_cn", ""), item.get("content_cn", ""),
             item.get("published_at", today), today),
        )
        count += 1

    if daily_digest:
        cur.execute(
            "SELECT id FROM news WHERE date = %s ORDER BY id", (today,)
        )
        ids = [r[0] for r in cur.fetchall()]
        ids_json = json.dumps(ids, ensure_ascii=False)
        cur.execute(
            """INSERT INTO daily_summary (date, content, news_ids) VALUES (%s, %s, %s)
               ON CONFLICT(date) DO UPDATE SET content=EXCLUDED.content, news_ids=EXCLUDED.news_ids""",
            (today, daily_digest, ids_json),
        )

    conn.commit()
    cur.close()
    conn.close()
    return count


# ── news ─────────────────────────────────────────────────────

def get_news_by_date(date_str, page=1, per_page=20):
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    offset = (page - 1) * per_page
    cur.execute(
        "SELECT * FROM news WHERE date = %s ORDER BY published_at DESC LIMIT %s OFFSET %s",
        (date_str, per_page, offset),
    )
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM news WHERE date = %s", (date_str,))
    total = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return [_cn(r) for r in rows], total


def get_news(news_id):
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return _cn(row) if row else None


def get_today_news():
    today = date.today().isoformat()
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, title, title_cn, url, source, summary, published_at as time"
        " FROM news WHERE date = %s ORDER BY time DESC",
        (today,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_cn(r) for r in rows]


def get_news_by_url(url):
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM news WHERE url = %s", (url,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_news_by_title(title):
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM news WHERE title = %s", (title,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def create_news(title, date_str, url="", source="", content="", summary="", published_at=None):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO news (title, url, source, content, summary, published_at, date)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (title, url, source, content, summary, published_at or date_str, date_str),
    )
    nid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return nid


def update_news_summary(news_id, summary):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE news SET summary = %s WHERE id = %s", (summary, news_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_news(news_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_available_dates():
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT date, COUNT(*) as count FROM news GROUP BY date ORDER BY date DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# ── daily_summary ────────────────────────────────────────────

def get_summary(date_str):
    conn = _connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM daily_summary WHERE date = %s", (date_str,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        d = dict(row)
        d["news_ids"] = json.loads(d["news_ids"])
        return d
    return None


def upsert_summary(date_str, content, news_ids_json):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO daily_summary (date, content, news_ids)
           VALUES (%s, %s, %s)
           ON CONFLICT(date) DO UPDATE SET content=EXCLUDED.content, news_ids=EXCLUDED.news_ids""",
        (date_str, content, news_ids_json),
    )
    conn.commit()
    cur.close()
    conn.close()


def has_summary(date_str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM daily_summary WHERE date = %s", (date_str,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None
