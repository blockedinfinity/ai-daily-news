"""RSS 抓取 —— 真实 RSS/Atom 源，可扩展。"""

import logging
import re
from datetime import datetime
from time import mktime

import feedparser
import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
PER_SOURCE_LIMIT = 10
MAX_CONTENT_LENGTH = 2000

SOURCES = [
    {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss"},
    {"name": "量子位", "url": "https://www.qbitai.com/feed"},
    {"name": "极客公园", "url": "https://www.geekpark.net/rss"},
    {"name": "arXiv AI 论文", "url": "https://export.arxiv.org/rss/cs.AI"},
]


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _entry_time(entry):
    tt = entry.get("published_parsed")
    if tt:
        try:
            return datetime.fromtimestamp(mktime(tt))
        except Exception:
            pass
    return datetime.now()


def _entry_content(entry):
    if entry.get("content"):
        raw = entry.content[0].get("value", "")
        if raw:
            return _strip_html(raw)[:MAX_CONTENT_LENGTH]
    if entry.get("summary"):
        return _strip_html(entry.summary)[:MAX_CONTENT_LENGTH]
    return ""


def fetch_source(source):
    name, feed_url = source["name"], source["url"]
    logger.info("抓取 %s", name)
    try:
        resp = requests.get(
            feed_url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Daily-News/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("抓取失败 %s: %s", name, e)
        return []

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        logger.warning("解析失败 %s: %s", name, feed.bozo_exception)
        return []

    items = []
    for entry in feed.entries[:PER_SOURCE_LIMIT]:
        title = _strip_html(entry.get("title", ""))
        url = (entry.get("link") or "").strip()
        if not title:
            continue
        pub = _entry_time(entry)
        items.append(
            {
                "title": title,
                "url": url,
                "source": name,
                "content": _entry_content(entry) or title,
                "published_at": pub.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    logger.info("成功 %s %d 条", name, len(items))
    return items


def fetch_news():
    """抓取所有 RSS 源。返回 [dict, ...]，每条含 title/url/source/content/published_at。"""
    all_news = []
    for s in SOURCES:
        all_news.extend(fetch_source(s))
    logger.info("本次共抓取 %d 条新闻", len(all_news))
    return all_news
