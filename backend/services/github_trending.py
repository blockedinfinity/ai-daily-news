"""GitHub Trending 爬取 + GitHub Search API，获取候选开源项目列表。"""

import logging
import os
import re
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REQUEST_TIMEOUT = 20

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "AI-Daily-News/2.0",
}
if GITHUB_TOKEN:
    _HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


def _strip_html(text):
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


# ── GitHub Trending ──────────────────────────────────────────

def fetch_trending_repos(limit=20, language="Python"):
    """爬取 GitHub Trending 页面，返回候选项目列表。"""
    url = f"https://github.com/trending/{language}?since=daily"
    logger.info("抓取 GitHub Trending: %s", url)
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-Daily-News/2.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("GitHub Trending 抓取失败: %s", e)
        return []

    return _parse_trending_html(resp.text, limit)


def _parse_trending_html(html, limit):
    """解析 GitHub Trending HTML，提取项目信息。"""
    import re

    items = []
    # 匹配每个仓库条目
    # <h2 class="h3"><a href="/user/repo">...
    repo_pattern = re.compile(
        r'<h2\s+class="[^"]*h3[^"]*">\s*<a\s+href="/([^"/]+)/([^"]+)"[^>]*>(?:[^<]*?)</a>',
        re.S,
    )
    # 匹配 description
    desc_pattern = re.compile(r'<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>(.*?)</p>', re.S)
    # 匹配语言标签
    lang_pattern = re.compile(r'<span[^>]+class="[^"]*color-fg-[^"]*[^"]*"[^>]*>\s*(\w+)\s*</span>')
    # 匹配今日 stars
    stars_today_pattern = re.compile(r'(\d[\d,]*(?:\.\d)?[kKmM]?)\s*stars\s+today', re.I)

    # 更通用的解析：找到所有 article 块
    article_pattern = re.compile(r'<article[^>]*>(.*?)</article>', re.S)
    for article in article_pattern.findall(html)[:limit]:
        repo_match = repo_pattern.search(article)
        if not repo_match:
            continue

        author, repo_name = repo_match.groups()
        name = f"{author}/{repo_name}"

        # description
        desc_match = desc_pattern.search(article)
        description = ""
        if desc_match:
            description = _strip_html(desc_match.group(1)).strip()

        # language
        lang_match = lang_pattern.search(article)
        language = lang_match.group(1) if lang_match else ""

        # stars_today
        stars_today = 0
        st_match = stars_today_pattern.search(article)
        if st_match:
            stars_today = _parse_count(st_match.group(1))

        # total stars（从 XML/rss 不返回，需要爬详情页或用 API）
        stars = 0

        items.append({
            "name": name,
            "description": description,
            "stars": stars,
            "stars_today": stars_today,
            "language": language,
            "url": f"https://github.com/{name}",
            "source": "GitHub Trending",
        })

    logger.info("GitHub Trending 解析出 %d 个项目", len(items))
    return items


def _parse_count(s):
    """解析 '1.2k', '500', '3.5M' 等格式为整数。"""
    s = s.strip().replace(",", "")
    if s.lower().endswith("k"):
        return int(float(s[:-1]) * 1000)
    if s.lower().endswith("m"):
        return int(float(s[:-1]) * 1_000_000)
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


# ── GitHub Search API ────────────────────────────────────────

def fetch_github_api_repos(limit=15):
    """用 GitHub Search API 搜索近 7 天新增 star 最多的 AI 相关仓库。"""
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>50 AI OR " \
            f"machine-learning OR LLM OR " \
            f"artificial-intelligence OR deep-learning"
    sort = "stars"
    order = "desc"

    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": sort, "order": order, "per_page": min(limit, 100)}

    logger.info("GitHub API 搜索: %s", url)
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 403:
            logger.warning("GitHub API 速率受限，跳过 API 搜索")
            return []
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("GitHub API 搜索失败: %s", e)
        return []

    data = resp.json()
    items = []
    for repo in (data.get("items") or [])[:limit]:
        items.append({
            "name": f"{repo.get('full_name', '')}",
            "description": repo.get("description") or "",
            "stars": repo.get("stargazers_count") or 0,
            "stars_today": 0,  # API 不返回今日增量
            "language": repo.get("language") or "",
            "url": repo.get("html_url") or "",
            "source": "GitHub API",
        })

    logger.info("GitHub API 返回 %d 个项目", len(items))
    return items


# ── HN / Reddit 项目发现 ────────────────────────────────────

def fetch_hn_projects(limit=10):
    """从 Hacker News 找高票 AI 相关链接，提取 GitHub 仓库。"""
    url = "https://hnrss.org/frontpage?points=100"
    logger.info("从 HN 抓取项目候选: %s", url)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Daily-News/2.0)"})
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("HN 抓取失败: %s", e)
        return []

    import feedparser
    feed = feedparser.parse(resp.text)

    items = []
    for entry in feed.entries[:limit]:
        link = (entry.get("link") or "").strip()
        if "github.com" not in link:
            continue
        m = re.match(r"https?://github\.com/([^/]+)/([^/?#]+)", link)
        if not m:
            continue
        author, repo_name = m.groups()
        name = f"{author}/{repo_name}"
        title = _strip_html(entry.get("title", ""))
        score = int(entry.get("hr_points") or 0)

        items.append({
            "name": name,
            "description": title,
            "stars": 0,
            "stars_today": 0,
            "language": "",
            "url": link,
            "source": f"HN (↑{score})",
        })

    logger.info("HN 提取 %d 个 GitHub 项目", len(items))
    return items


def fetch_reddit_projects(limit=10):
    """从 Reddit r/MachineLearning 找高赞 AI 相关 GitHub 链接。"""
    url = "https://www.reddit.com/r/MachineLearning/.rss"
    logger.info("从 Reddit 抓取项目候选: %s", url)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Daily-News/2.0)"})
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Reddit 抓取失败: %s", e)
        return []

    import feedparser
    feed = feedparser.parse(resp.text)

    items = []
    for entry in feed.entries[:limit]:
        link = (entry.get("link") or "").strip()
        if "github.com" not in link:
            continue
        m = re.match(r"https?://github\.com/([^/]+)/([^/?#]+)", link)
        if not m:
            continue
        author, repo_name = m.groups()
        name = f"{author}/{repo_name}"
        title = _strip_html(entry.get("title", ""))

        items.append({
            "name": name,
            "description": title,
            "stars": 0,
            "stars_today": 0,
            "language": "",
            "url": link,
            "source": "Reddit r/ML",
        })

    logger.info("Reddit 提取 %d 个 GitHub 项目", len(items))
    return items


# ── 统一入口 ─────────────────────────────────────────────────

def fetch_all_candidates():
    """抓取所有候选项目，合并去重。"""
    all_candidates = []
    seen = set()

    for func, label in [
        (fetch_trending_repos, "Trending"),
        (fetch_github_api_repos, "GitHub API"),
        (fetch_hn_projects, "HN"),
        (fetch_reddit_projects, "Reddit"),
    ]:
        try:
            items = func()
            for item in items:
                key = item["name"].lower()
                if key not in seen:
                    seen.add(key)
                    all_candidates.append(item)
            logger.info("[%s] 当前候选总计: %d", label, len(all_candidates))
        except Exception as e:
            logger.warning("[%s] 出错: %s", label, e)

    logger.info("候选项目总计: %d 个", len(all_candidates))
    return all_candidates
