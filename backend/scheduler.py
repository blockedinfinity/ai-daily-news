"""定时任务 —— 纯 APScheduler，不依赖 threading。"""

import logging
from datetime import datetime

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
    # 用 APScheduler 的 date 触发器立即执行一次，不依赖 threading
    scheduler.add_job(_job, "date", run_date=datetime.now())
    return scheduler
