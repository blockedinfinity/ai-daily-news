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
from psycopg2 import pool as pg_pool

_raw_url = os.getenv("DATABASE_URL", "")

# psycopg2 不支持 channel_binding 参数，需要移除
def _clean_url(raw):
    parsed = urlparse(raw)
    params = parse_qsl(parsed.query)
    params = [(k, v) for k, v in params if k != "channel_binding"]
    cleaned = parsed._replace(query=urlencode(params))
    return urlunparse(cleaned)

DATABASE_URL = _clean_url(_raw_url) if _raw_url else ""

# 连接池：避免频繁创建/销毁连接，防止耗尽 Neon 免费版连接数
_pool = None
_MAX_POOL = 5
_MIN_POOL = 1


def _init_pool():
    global _pool
    if _pool is None and DATABASE_URL:
        _pool = pg_pool.ThreadedConnectionPool(_MIN_POOL, _MAX_POOL, DATABASE_URL)
    return _pool


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 环境变量未设置")
    p = _init_pool()
    if p:
        conn = p.getconn()
        conn.autocommit = False
        return conn
    # 回退：无连接池时直接创建
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _putback(conn):
    """将连接归还连接池。"""
    if _pool and conn:
        try:
            _pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def _cn(d):
    """返回中文优先的 title/content（有翻译用翻译，否则用原文）。"""
    d = dict(d)
    if d.get("title_cn"):
        d["title"] = d["title_cn"]
    if d.get("content_cn"):
        d["content"] = d["content_cn"]
    return d


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
            image_url   TEXT DEFAULT '',
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
    # 迁移：为旧表添加 image_url 字段（忽略已存在）
    try:
        cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT ''")
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
    try:
        cur = conn.cursor()

        # 批量查询已有 URL 和 title，减少连接次数
        existing_urls = set()
        existing_titles = set()
        for item in items:
            if item.get("url"):
                existing_urls.add(item["url"])
            if item.get("title"):
                existing_titles.add(item["title"])

        if existing_urls:
            cur.execute("SELECT url FROM news WHERE url = ANY(%s)", (list(existing_urls),))
            existing_urls = {r[0] for r in cur.fetchall()}
        if existing_titles:
            cur.execute("SELECT title FROM news WHERE title = ANY(%s)", (list(existing_titles),))
            existing_titles = {r[0] for r in cur.fetchall()}

        for item in items:
            url = item.get("url", "")
            title = item.get("title", "")
            if url and url in existing_urls:
                continue
            if title and title in existing_titles:
                continue
            cur.execute(
                """INSERT INTO news (title, url, source, content, summary, title_cn, content_cn, image_url, published_at, date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (title, url, item.get("source", ""), item.get("content", ""),
                 item.get("summary", ""), item.get("title_cn", ""), item.get("content_cn", ""),
                 item.get("image_url", ""),
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
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass
        _putback(conn)
    return count


# ── news ─────────────────────────────────────────────────────

def get_news_by_date(date_str, page=1, per_page=20):
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        offset = (page - 1) * per_page
        cur.execute(
            "SELECT * FROM news WHERE date = %s ORDER BY published_at DESC LIMIT %s OFFSET %s",
            (date_str, per_page, offset),
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM news WHERE date = %s", (date_str,))
        total = cur.fetchone()["count"]
        return [_cn(r) for r in rows], total
    finally:
        _putback(conn)


def get_news(news_id):
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        row = cur.fetchone()
        return _cn(row) if row else None
    finally:
        _putback(conn)


def get_today_news():
    today = date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, title, title_cn, url, source, summary, image_url, published_at as time"
                " FROM news WHERE date = %s ORDER BY time DESC",
                (today,),
            )
        rows = cur.fetchall()
        return [_cn(r) for r in rows]
    finally:
        _putback(conn)


def get_news_by_url(url):
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM news WHERE url = %s", (url,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _putback(conn)


def get_news_by_title(title):
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM news WHERE title = %s", (title,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _putback(conn)


def create_news(title, date_str, url="", source="", content="", summary="", published_at=None):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO news (title, url, source, content, summary, published_at, date)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (title, url, source, content, summary, published_at or date_str, date_str),
        )
        nid = cur.fetchone()[0]
        conn.commit()
        return nid
    except Exception:
        conn.rollback()
        raise
    finally:
        _putback(conn)


def update_news_summary(news_id, summary):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE news SET summary = %s WHERE id = %s", (summary, news_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _putback(conn)


def delete_news(news_id):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _putback(conn)


def get_available_dates():
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT date, COUNT(*) as count FROM news GROUP BY date ORDER BY date DESC"
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        _putback(conn)


# ── daily_summary ────────────────────────────────────────────

def get_summary(date_str):
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM daily_summary WHERE date = %s", (date_str,)
        )
        row = cur.fetchone()
        if row:
            d = dict(row)
            d["news_ids"] = json.loads(d["news_ids"])
            return d
        return None
    finally:
        _putback(conn)


def upsert_summary(date_str, content, news_ids_json):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO daily_summary (date, content, news_ids)
               VALUES (%s, %s, %s)
               ON CONFLICT(date) DO UPDATE SET content=EXCLUDED.content, news_ids=EXCLUDED.news_ids""",
            (date_str, content, news_ids_json),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _putback(conn)


def has_summary(date_str):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM daily_summary WHERE date = %s", (date_str,)
        )
        row = cur.fetchone()
        return row is not None
    finally:
        _putback(conn)
