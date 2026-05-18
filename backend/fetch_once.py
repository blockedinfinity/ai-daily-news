"""Render Cron Job: 每日精选 ~5 条 AI 新闻 -> 翻译 + 摘要 + 入库。

使用流程：
1. 并行抓取所有 RSS 源
2. 数据库去重
3. AI 根据热度/影响力精选 top N
4. 翻译英文新闻
5. 生成中文摘要 + 日报
6. 入库 PostgreSQL
"""

import json
import logging
import os
import sys

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from services import db, dedup, rss
from services.ai import batch_summarize, batch_translate, deepseek_call

logger = logging.getLogger(__name__)

TOP_N = int(os.getenv("TOP_N", "5"))


def rank_and_select(news_list):
    """用 AI 从候选新闻中精选 top N 高影响力文章。

    优先使用 HN points/comments 等客观数据排序；
    对无热度数据的源，用 AI 按行业影响力评分。
    """
    if len(news_list) <= TOP_N:
        return news_list

    # 有热度数据的文章（如 Hacker News），按分数降序排前面
    scored = [n for n in news_list if (n.get("score", 0) > 0 or n.get("comments", 0) > 0)]
    unscored = [n for n in news_list if n not in scored]

    # 如果有热度的文章已经足够，直接取 top N
    if len(scored) >= TOP_N:
        scored.sort(key=lambda x: (x.get("score", 0) + x.get("comments", 0) * 0.5), reverse=True)
        return scored[:TOP_N]

    # 热度不够，用 AI 对剩余文章评分补齐
    if unscored:
        selected_from_scored = scored  # 有热度的全要
        need_more = TOP_N - len(selected_from_scored)

        lines = []
        for i, item in enumerate(unscored):
            content_preview = (item.get("content") or "")[:300]
            lines.append(f"[{i}] 标题: {item['title']}\n来源: {item['source']}\n摘要: {content_preview}")

        prompt = (
            f"你是 AI 新闻编辑。从以下 {len(unscored)} 条新闻中选出最值得关注的 {need_more} 条。\n\n"
            "选择标准（按优先级）：\n"
            "1. 行业影响力大（大模型发布、重大融资、政策变化、明星产品）\n"
            "2. 技术突破或创新\n"
            "3. 对普通人有实际影响\n"
            "4. 热门话题（预期阅读量高、讨论度高）\n"
            "5. 信息密度高，有实质性内容\n\n"
            + "\n---\n\n".join(lines)
            + f"\n\n只返回 JSON 数组: [{{\"index\": 0, \"reason\": \"简短理由\"}}, ...]"
        )

        try:
            response = deepseek_call(prompt, system="AI news curator. Return JSON only.", temperature=0.2)
            text = response.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            selections = json.loads(text)
            indices = {s["index"] for s in selections}
            ai_selected = [unscored[i] for i in sorted(indices) if i < len(unscored)]
            logger.info("AI 从 %d 条中精选 %d 条", len(unscored), len(ai_selected))
            result = selected_from_scored + ai_selected
        except Exception as e:
            logger.warning("AI 排序失败，回退按源取前几条: %s", e)
            # 简单策略：每个源取前 2 条
            from collections import defaultdict
            by_source = defaultdict(list)
            for n in unscored:
                by_source[n["source"]].append(n)
            picked = []
            for src, items in sorted(by_source.items()):
                picked.extend(items[:2])
                if len(selected_from_scored) + len(picked) >= TOP_N:
                    break
            result = selected_from_scored + picked[:need_more]

        return result[:TOP_N]

    # 全都有热度数据
    scored.sort(key=lambda x: (x.get("score", 0) + x.get("comments", 0) * 0.5), reverse=True)
    return scored[:TOP_N]


def main():
    logger.info("=== 开始每日精选抓取 (目标 %d 条) ===", TOP_N)

    try:
        db.init_db()
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
        return

    # 1. 抓取
    news_list = rss.fetch_news()
    logger.info("RSS 抓取到 %d 条新闻", len(news_list))

    if not news_list:
        logger.info("无新闻可处理，退出")
        return

    # 2. 去重
    filtered = dedup.filter_new(news_list)
    if not filtered:
        logger.info("无新新闻（全部已入库），退出")
        return
    logger.info("去重后 %d 条新新闻", len(filtered))

    # 3. AI 精选
    selected = rank_and_select(filtered)
    logger.info("精选 %d 条: %s", len(selected), [n["title"][:40] for n in selected])

    # 4. 翻译
    logger.info("开始翻译英文新闻...")
    translated = batch_translate(selected)

    # 5. 摘要 + 日报
    logger.info("开始生成摘要和日报...")
    summarized, digest = batch_summarize(translated)

    # 6. 入库
    count = db.save_news(summarized, digest)
    logger.info("=== 完成，入库 %d 条 ===", count)


if __name__ == "__main__":
    main()
