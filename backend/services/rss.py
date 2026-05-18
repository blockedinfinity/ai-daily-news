"""RSS 抓取 —— 真实 RSS/Atom 源，可扩展。"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from time import mktime

import feedparser
import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
PER_SOURCE_LIMIT = 10
MAX_CONTENT_LENGTH = 2000

SOURCES = [
    # 中文源
    {"name": "量子位", "url": "https://www.qbitai.com/feed"},
    {"name": "少数派", "url": "https://sspai.com/feed"},
    # 海外源
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage?points=100"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "Google AI Blog", "url": "https://blog.google/innovation-and-ai/technology/ai/rss/"},
    {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
]


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_first_image(html):
    """从 HTML 内容中提取第一张图片 URL。优先 og:image / twitter:image，其次 <img src>。"""
    if not html:
        return ""
    # 优先取 og:image 或 twitter:image
    og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if og:
        return og.group(1).strip()
    og2 = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
    if og2:
        return og2.group(1).strip()
    tw = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if tw:
        return tw.group(1).strip()
    # 其次取 <img src>
    img = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
    if img:
        return img.group(1).strip()
    return ""


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

        # 提取热度信号（Hacker News 的 points/comments）
        score = 0
        comments = 0
        try:
            score = int(entry.get("hr_points") or 0)
        except (ValueError, TypeError):
            pass
        try:
            comments = int(entry.get("hr_comments") or 0)
        except (ValueError, TypeError):
            pass

        # 从原始 HTML 内容中提取图片
        raw_html = ""
        if entry.get("content"):
            raw_html = entry.content[0].get("value", "")
        elif entry.get("summary_detail"):
            raw_html = entry.summary_detail.get("value", "")
        elif entry.get("summary"):
            raw_html = entry.summary if "<" in (entry.summary or "") else ""

        image_url = _extract_first_image(raw_html)

        items.append(
            {
                "title": title,
                "url": url,
                "source": name,
                "content": _entry_content(entry) or title,
                "image_url": image_url,
                "published_at": pub.strftime("%Y-%m-%d %H:%M:%S"),
                "score": score,
                "comments": comments,
            }
        )

    logger.info("成功 %s %d 条", name, len(items))
    return items


def fetch_news():
    """并行抓取所有 RSS 源。返回 [dict, ...]，每条含 title/url/source/content/published_at。"""
    all_news = []
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            fut_map = {pool.submit(fetch_source, s): s for s in SOURCES}
            for future in as_completed(fut_map, timeout=60):
                try:
                    items = future.result(timeout=20)
                    all_news.extend(items)
                except Exception as e:
                    s = fut_map[future]
                    logger.warning("抓取失败 %s: %s", s["name"], e)
    except Exception as e:
        logger.error("RSS 抓取总错误: %s", e)
    logger.info("本次共抓取 %d 条新闻", len(all_news))
    return all_news
