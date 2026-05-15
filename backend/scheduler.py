"""定时任务 —— 核心管道：RSS 抓取 → 去重 → AI 批量总结 → 写入数据库。"""

import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from services import db, dedup, rss
from services.ai import batch_summarize

logger = logging.getLogger(__name__)


def _job():
    news_list = rss.fetch_news()

    filtered = dedup.filter_new(news_list)
    if not filtered:
        logger.info("[每日任务] 无新新闻")
        return

    logger.info("[每日任务] 抓取 %d 条，新 %d 条", len(news_list), len(filtered))
    summarized, digest = batch_summarize(filtered)
    count = db.save_news(summarized, digest)
    logger.info("[每日任务] 入库 %d 条，日报摘要已生成", count)


def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(_job, "interval", hours=24, id="daily_news", replace_existing=True)
    scheduler.start()
    logger.info("定时任务已启动（每天执行一次）")

    # 后台线程执行首次任务，避免阻塞 WSGI 启动
    threading.Thread(target=_job, daemon=True).start()

    return scheduler
