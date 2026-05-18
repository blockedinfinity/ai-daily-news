"""去重逻辑 —— 基于数据库已有数据判断重复。"""

from . import db


def is_duplicate(title, url=""):
    """检查标题或链接是否已存在。"""
    if url and db.get_news_by_url(url):
        return True
    if db.get_news_by_title(title):
        return True
    return False


def filter_new(items):
    """从新闻列表中过滤出数据库中不存在的条目（批量查询，减少连接数）。"""
    if not items:
        return []

    conn = db._connect()
    cur = conn.cursor()

    urls = [item["url"] for item in items if item.get("url")]
    titles = [item["title"] for item in items if item.get("title")]

    existing_urls = set()
    existing_titles = set()
    if urls:
        cur.execute("SELECT url FROM news WHERE url = ANY(%s)", (urls,))
        existing_urls = {r[0] for r in cur.fetchall()}
    if titles:
        cur.execute("SELECT title FROM news WHERE title = ANY(%s)", (titles,))
        existing_titles = {r[0] for r in cur.fetchall()}

    cur.close()
    conn.close()

    return [
        item for item in items
        if item.get("url", "") not in existing_urls
        and item.get("title", "") not in existing_titles
    ]
