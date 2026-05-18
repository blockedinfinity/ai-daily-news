"""一次性脚本：为已有新闻回填 image_url（从 RSS 源匹配）。

用法：python backfill_images.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import psycopg2.extras

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from services import db, rss

logger = logging.getLogger(__name__)


def main():
    try:
        db.init_db()
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
        return

    # 1. 查询所有没有 image_url 的新闻
    conn = db._connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, url, title FROM news WHERE (image_url IS NULL OR image_url = '') AND url != ''"
        )
        news_items = cur.fetchall()
    finally:
        db._putback(conn)

    if not news_items:
        logger.info("所有新闻已有图片，无需回填")
        return

    logger.info("需要回填图片的新闻: %d 条", len(news_items))

    # 2. 抓取所有 RSS 源
    logger.info("开始抓取 RSS 源...")
    rss_items = rss.fetch_news()
    logger.info("RSS 抓取到 %d 条", len(rss_items))

    # 3. 按 URL 建立映射
    url_to_image = {}
    for item in rss_items:
        url = item.get("url", "").strip()
        if url and item.get("image_url"):
            url_to_image[url] = item["image_url"]

    # 4. 匹配并更新
    updated = 0
    for news in news_items:
        url = (news.get("url") or "").strip()
        image_url = url_to_image.get(url)
        if image_url:
            try:
                conn = db._connect()
                cur = conn.cursor()
                cur.execute("UPDATE news SET image_url = %s WHERE id = %s", (image_url, news["id"]))
                conn.commit()
                cur.close()
                db._putback(conn)
                updated += 1
                logger.info("  [%d] %s -> %s", news["id"], news["title"][:40], image_url[:60])
            except Exception as e:
                logger.warning("  [%d] 更新失败: %s", news["id"], e)

    logger.info("=== 回填完成: %d/%d 条新闻已更新图片 ===", updated, len(news_items))


if __name__ == "__main__":
    main()
