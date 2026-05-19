"""GitHub Actions / 手动执行:
   1. 三段精选 3 篇 AI 新闻（技术源 + 媒体源 + 开放竞争）
   2. 翻译英文新闻
   3. 入库 PostgreSQL
   4. 精选 1 个精品开源项目 + 三点介绍 + 配图 + 入库
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from datetime import date as _date

from services import db, dedup, rss
from services.ai import batch_summarize, batch_translate, deepseek_call, generate_summary

logger = logging.getLogger(__name__)

TOP_N = int(os.getenv("TOP_N", "3"))

# ── 三段精选 ─────────────────────────────────────────────────

SELECTION_PROMPT = """你是 AI 领域资深编辑，负责每日精选 3 篇高价值新闻。

【精选标准】（按优先级）
1. 原创性和首发性（非二手转载）
2. 技术/事件的行业影响力（大模型发布、重大融资、政策变化、明星产品）
3. 对读者的实际阅读价值（深度 vs 热度）
4. 可量化热度信号（HN points、Reddit upvotes 等）

【候选新闻列表】
{candidates}

【分组要求】
- 第一组（技术权威源）：选出最代表技术前沿的 1 篇
- 第二组（AI 媒体源）：选出最具 AI 媒体简报价值的 1 篇
- 第三组（开放竞争）：从前两组所有未入选的文章中选出综合最强的 1 篇

最终输出恰好 3 篇，不得重复、不得空缺。

JSON 格式：
{{
  "tech_pick": {{"index": <数字>, "reason": "<50字以内理由>"}},
  "media_pick": {{"index": <数字>, "reason": "<50字以内理由>"}},
  "open_pick": {{"index": <数字>, "reason": "<50字以内理由>"}}
}}
"""


def _build_candidate_lines(news_list):
    lines = []
    for i, item in enumerate(news_list):
        content = (item.get("content") or "")[:200]
        lines.append(
            f"[{i}] 来源组: {item.get('source_group', '?')} | "
            f"标题: {item['title']}\n"
            f"    摘要: {content}\n"
            f"    热度: score={item.get('score', 0)} comments={item.get('comments', 0)}"
        )
    return lines


def _three_stage_select(tech_news, media_news):
    """三段分组精选：技术1 + 媒体1 + 开放竞争1，返回 3 篇最终列表。"""
    # 给每条新闻打上来源组标签
    for n in tech_news:
        n["source_group"] = "TECH"
    for n in media_news:
        n["source_group"] = "MEDIA"

    all_news = tech_news + media_news
    if not all_news:
        return []

    # 候选不足时降低要求
    if len(all_news) <= TOP_N:
        logger.info("候选不足 %d 篇，直接全量返回", TOP_N)
        return all_news

    lines = _build_candidate_lines(all_news)
    prompt = SELECTION_PROMPT.format(candidates="\n\n".join(lines))

    try:
        response = deepseek_call(
            prompt,
            system="你是 AI 新闻精选专家，严格按分组标准输出 JSON 格式。",
            temperature=0.2,
            max_tokens=1024,
        )
        text = response.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(text)

        selected = []
        for key in ("tech_pick", "media_pick", "open_pick"):
            entry = result.get(key, {})
            idx = entry.get("index", -1)
            if 0 <= idx < len(all_news):
                news_item = dict(all_news[idx])
                news_item["pick_reason"] = entry.get("reason", "")
                selected.append(news_item)

        if len(selected) == TOP_N:
            logger.info("三段精选成功: %s", [n["title"][:30] for n in selected])
            return selected
        else:
            logger.warning("AI 返回不足 3 篇，回退降序策略")

    except Exception as e:
        logger.warning("三段精选失败，回退降序策略: %s", e)

    # 回退：各组取最热的前几条
    scored = sorted(all_news, key=lambda x: (x.get("score", 0) + x.get("comments", 0) * 0.5), reverse=True)
    return scored[:TOP_N]


# ── 项目精选流程 ─────────────────────────────────────────────

def fetch_and_save_project():
    """抓取候选项目 → AI 精选 → 生成三点介绍 → 生图上传 → 入库。"""
    try:
        from services.github_trending import fetch_all_candidates
        from services.project_ranker import generate_project_intro, rank_and_select_project
        from services.image_gen import generate_and_upload_cover
    except ImportError as e:
        logger.warning("项目精选模块导入失败，跳过: %s", e)
        return

    logger.info("=== 开始精品项目抓取 ===")
    candidates = fetch_all_candidates()
    if not candidates:
        logger.warning("无候选项目，跳过")
        return

    project = rank_and_select_project(candidates)
    if not project:
        logger.info("AI 判定今日无优质项目，跳过")
        return

    project = generate_project_intro(project)
    cover_url = generate_and_upload_cover(project)
    if cover_url:
        project["cover_image_url"] = cover_url

    db.save_project(project)
    logger.info("=== 精品项目入库: %s ===", project.get("name"))


# ── 主流程 ───────────────────────────────────────────────────

def main():
    logger.info("=== 开始每日精选抓取 (新闻目标 %d 篇) ===", TOP_N)
    today_str = _date.today().isoformat()

    try:
        db.init_db()
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
        return

    # 1. 分组抓取
    logger.info("抓取技术权威源...")
    tech_news = rss.fetch_tech_news()
    logger.info("技术源抓取 %d 条", len(tech_news))

    logger.info("抓取 AI 媒体源...")
    media_news = rss.fetch_media_news()
    logger.info("AI 媒体源抓取 %d 条", len(media_news))

    all_news = tech_news + media_news
    if not all_news:
        logger.info("无新闻可处理，退出")
        return

    # 2. 去重
    filtered = dedup.filter_new(all_news)
    if not filtered:
        logger.info("无新新闻（全部已入库），退出")
        return
    logger.info("去重后 %d 条新新闻", len(filtered))

    # 重新标记分组
    tech_filtered = [n for n in filtered if n in tech_news]
    media_filtered = [n for n in filtered if n in media_news]
    # 补齐：从 all_news 的 tech_news/media_news 中取 filtered 里的
    tech_filtered = [n for n in filtered if n.get("source_group") == "TECH"]
    media_filtered = [n for n in filtered if n.get("source_group") == "MEDIA"]
    # 兜底：没 source_group 的全部归入 media
    if not tech_filtered and not media_filtered:
        tech_filtered = filtered[:len(filtered)//2]
        media_filtered = filtered[len(filtered)//2:]

    # 3. 三段精选
    selected = _three_stage_select(tech_filtered, media_filtered)
    logger.info("精选 %d 条: %s", len(selected), [n["title"][:40] for n in selected])

    # 4. 翻译
    logger.info("开始翻译英文新闻...")
    translated = batch_translate(selected)

    # 5. 摘要 + 日报
    logger.info("开始生成摘要和日报...")
    summarized, digest = batch_summarize(translated)

    # 6. 入库
    count = db.save_news(summarized, digest)
    logger.info("=== 完成，新闻入库 %d 条 ===", count)

    # 7. 自动生成 AI 精华总结
    if count > 0:
        try:
            news_for_summary, _ = db.get_news_by_date(today_str, 1, 1000)
            if news_for_summary:
                summary_text = generate_summary(news_for_summary)
                news_ids = json.dumps([n["id"] for n in news_for_summary], ensure_ascii=False)
                db.upsert_summary(today_str, summary_text, news_ids)
                logger.info("=== AI 精华总结已自动生成 ===")
        except Exception as e:
            logger.warning("自动生成总结失败: %s", e)

    # 8. 精品项目
    fetch_and_save_project()

    logger.info("=== 每日抓取全部完成 ===")


if __name__ == "__main__":
    main()
