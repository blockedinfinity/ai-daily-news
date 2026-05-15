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
    """从新闻列表中过滤出数据库中不存在的条目。"""
    result = []
    for item in items:
        if not is_duplicate(item["title"], item.get("url", "")):
            result.append(item)
    return result
