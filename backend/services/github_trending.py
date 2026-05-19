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
    items = []

    # 匹配每个 article 块
    article_pattern = re.compile(r"<article[^>]*>(.*?)</article>", re.DOTALL)
    # 仓库名：两步走
    # 1. 找到 h2 块
    h2_pattern = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
    # 2. 在 h2 块中找到 repo href（/author/repo 格式，排除 login/forks 等）
    href_in_h2 = re.compile(r'href="(/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"')
    # 描述：<p class="...color-fg-muted...">文字</p>
    desc_pattern = re.compile(
        r'<p\s+class="[^"]*color-fg-muted[^"]*"[^>]*>(.*?)</p>',
        re.DOTALL,
    )
    # 语言：<span itemprop="programmingLanguage">Python</span>
    lang_pattern = re.compile(
        r'<span\s+itemprop="programmingLanguage"[^>]*>([^<]+)</span>',
    )
    # 今日 stars：...文字... 1,439 stars today
    stars_today_pattern = re.compile(
        r'([\d,]+)\s+stars\s+today',
        re.I,
    )
    # 总 stars：紧跟在 star SVG 后面的数字
    stars_pattern = re.compile(
        r'<svg[^>]+aria-label=["\']star["\'][^>]*>.*?</svg>\s*([\d,]+)',
        re.DOTALL,
    )

    for article in article_pattern.findall(html)[:limit]:
        h2_match = h2_pattern.search(article)
        if not h2_match:
            continue
        # 在 h2 块中找 /author/repo 格式的 href
        href_match = href_in_h2.search(h2_match.group(1))
        if not href_match:
            continue
        name = href_match.group(1).lstrip("/")
        url = f"https://github.com/{name}"

        # 描述
        desc_m = desc_pattern.search(article)
        description = _strip_html(desc_m.group(1)).strip() if desc_m else ""

        # 语言
        lang_m = lang_pattern.search(article)
        language = lang_m.group(1).strip() if lang_m else ""

        # 总 stars
        stars = 0
        st_m = stars_pattern.search(article)
        if st_m:
            stars = int(st_m.group(1).replace(",", ""))

        # 今日 stars
        stars_today = 0
        stoday_m = stars_today_pattern.search(article)
        if stoday_m:
            stars_today = int(stoday_m.group(1).replace(",", ""))

        items.append({
            "name": name,
            "description": description,
            "stars": stars,
            "stars_today": stars_today,
            "language": language,
            "url": url,
            "source": "GitHub Trending",
        })

    logger.info("GitHub Trending 解析出 %d 个项目", len(items))
    return items


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
