"""独立脚本：抓取 RSS + 翻译 + 摘要 + 入库。供 Render Cron Job 调用。"""

import sys
import os
import logging

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from services import db, dedup, rss
from services.ai import batch_summarize, batch_translate

logger = logging.getLogger(__name__)


def main():
    logger.info("=== 开始 RSS 抓取 ===")
    db.init_db()

    news_list = rss.fetch_news()
    logger.info("抓取到 %d 条新闻", len(news_list))

    filtered = dedup.filter_new(news_list)
    if not filtered:
        logger.info("无新新闻，退出")
        return

    logger.info("新新闻 %d 条，开始翻译...", len(filtered))
    translated = batch_translate(filtered)

    logger.info("开始生成摘要...")
    summarized, digest = batch_summarize(translated)

    count = db.save_news(summarized, digest)
    logger.info("=== 完成，入库 %d 条 ===", count)


if __name__ == "__main__":
    main()
