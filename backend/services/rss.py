"""RSS 抓取 —— 真实 RSS/Atom 源，可扩展。"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from time import mktime

import feedparser
import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
PER_SOURCE_LIMIT = 6
MAX_CONTENT_LENGTH = 2000

SOURCES = [
    # 国内源
    {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss"},
    {"name": "极客公园", "url": "https://www.geekpark.net/rss"},
    # 海外源
    {"name": "arXiv AI 论文", "url": "https://export.arxiv.org/rss/cs.AI"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage?points=100"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "Google AI", "url": "https://blog.google/innovation-and-ai/technology/ai/rss/"},
    {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
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
    """并行抓取所有 RSS 源。返回 [dict, ...]，每条含 title/url/source/content/published_at。"""
    all_news = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        fut_map = {pool.submit(fetch_source, s): s for s in SOURCES}
        for future in as_completed(fut_map, timeout=25):
            try:
                items = future.result()
                all_news.extend(items)
            except Exception as e:
                s = fut_map[future]
                logger.warning("抓取失败 %s: %s", s["name"], e)
    logger.info("本次共抓取 %d 条新闻", len(all_news))
    return all_news
