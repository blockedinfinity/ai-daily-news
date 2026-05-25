"""项目精选：三维权衡评分 + 三点极简介绍生成。"""

import json
import logging
import os
import re

from .ai import deepseek_call

logger = logging.getLogger(__name__)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


# ── 三维权衡精选 ─────────────────────────────────────────────

SELECTION_PROMPT = """你是一位 AI 领域资深编辑，负责每日精选一个最具价值的开源项目。

【三维评分标准】
1. 技术先进性（35%）：是否代表 AI 前沿方向（多模态/Agent/长上下文/效率优化等），是否有技术突破或创新
2. 社区认可度（35%）：GitHub Stars 总量、今日新增 Stars、Trending 排名、HN/Reddit 讨论热度
3. 行业贡献度（30%）：对 AI 生态的推动（降低门槛/提升效率/开源协作/商业落地潜力）

【候选项目列表】
{candidates}

【输出要求】
从以上候选中选出 1 个最值得推荐的项目。只推荐 1 个，宁缺毋滥，如无优质项目可选请返回 {{"selected": null, "reason": "今日候选质量不足，建议改日再推荐"}}。

JSON 格式返回：
{{
  "selected": {{
    "index": <数字，来自候选列表的序号>,
    "name": "<项目名>",
    "reason": "<精选理由，100字以内，说明为何在三维标准上胜出>"
  }},
  "reasoning": "<简要分析你排除其他项目的理由，50字以内>"
}}
"""


def _extract_json(text):
    """从 AI 回复中健壮地提取 JSON 对象。"""
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        return json.loads(text[start:end+1])
    raise ValueError("未找到 JSON")


def _fallback_select(candidates):
    """DeepSeek 不可用时，按热度分数回退选择。"""
    scored = sorted(
        candidates,
        key=lambda x: (x.get("stars", 0) or 0) + (x.get("stars_today", 0) or 0) * 2,
        reverse=True,
    )
    best = dict(scored[0])
    best["ai_reason"] = "今日热门项目（AI 精选暂不可用，按社区热度回退）"
    logger.info("回退精选项目(按热度): %s", best.get("name"))
    return best


def rank_and_select_project(candidates):
    """从候选项目中 AI 精选 1 个。返回 dict 或 None。"""
    if not candidates:
        logger.warning("无候选项目，跳过精选")
        return None

    limited = candidates[:25]

    lines = []
    for i, item in enumerate(limited):
        stars_str = f"{item.get('stars', 0):,}" if item.get('stars', 0) else "?"
        today_str = f"{item.get('stars_today', 0):,}" if item.get('stars_today', 0) else "?"
        desc = _strip_html(item.get("description", ""))[:120]
        lines.append(
            f"[{i}] 项目: {item['name']}\n"
            f"    描述: {desc}\n"
            f"    语言: {item.get('language', '-')}\n"
            f"    ⭐ Stars: {stars_str}  |  🔥 今日: +{today_str}\n"
            f"    来源: {item.get('source', '-')}"
        )

    prompt = SELECTION_PROMPT.format(candidates="\n\n".join(lines))

    try:
        response = deepseek_call(
            prompt,
            system="你是一位严谨的 AI 开源项目评审专家。严格按三维标准评分，输出 JSON 格式。",
            temperature=0.2,
            max_tokens=1024,
        )
        result = _extract_json(response)

        sel = result.get("selected")
        if not sel or sel.get("selected") is None and sel.get("name") is None:
            logger.info("AI 判定今日候选质量不足，跳过项目推荐")
            return None

        idx = sel.get("index", 0)
        if idx < 0 or idx >= len(limited):
            idx = 0

        selected = dict(limited[idx])
        selected["ai_reason"] = sel.get("reason", "")
        selected["ai_reasoning"] = result.get("reasoning", "")
        logger.info("精选项目: %s | 理由: %s", selected["name"], selected["ai_reason"])
        return selected

    except Exception as e:
        logger.warning("DeepSeek 项目精选失败(%s)，回退到按热度选择", e)
        return _fallback_select(limited)


# ── 三点极简介绍生成 ─────────────────────────────────────────

INTRO_PROMPT = """为以下 AI 开源项目生成三点极简介绍，用于小程序展示。

【规则】
- 每点严格 ≤50 字（不含标点后的空格）
- 语言：中文
- 风格：极简、干练，像产品一句话介绍，不废话、不煽情
- 三点严格对应：做什么 / 为何关注 / 怎么用
- **文字中禁止出现任何 URL、域名、链接**，纯文字表述

【项目信息】
名称: {name}
描述: {description}
推荐理由: {reason}

【输出格式】（严格 JSON，无 markdown 标签）
{{
  "intro_what": "……（≤50字）",
  "intro_why": "……（≤50字）",
  "intro_how": "……（≤50字）"
}}
"""


def generate_project_intro(project):
    """为项目生成三点极简介绍，补充到 project dict 中。"""
    name = project.get("name", "")
    description = _strip_html(project.get("description", ""))[:300]
    reason = project.get("ai_reason", "")[:150]

    prompt = INTRO_PROMPT.format(
        name=name,
        description=description,
        reason=reason,
    )

    try:
        response = deepseek_call(
            prompt,
            system="你是 AI 产品文案专家，擅长用最少的字传达最多的价值。严格遵循字数限制和格式要求。",
            temperature=0.3,
            max_tokens=512,
        )
        result = _extract_json(response)

        project["intro_what"] = result.get("intro_what", "").strip()
        project["intro_why"] = result.get("intro_why", "").strip()
        project["intro_how"] = result.get("intro_how", "").strip()

        # 强制截断到 50 字
        for key in ("intro_what", "intro_why", "intro_how"):
            if len(project[key]) > 50:
                project[key] = project[key][:50]

        logger.info("三点介绍生成成功: what=%s", project["intro_what"][:30])
        return project

    except Exception as e:
        logger.error("三点介绍生成失败: %s", e)
        project.setdefault("intro_what", "内容生成中...")
        project.setdefault("intro_why", "")
        project.setdefault("intro_how", "")
        return project


# ── 图片 prompt 生成 ─────────────────────────────────────────

COVER_PROMPT = """为以下 AI 开源项目生成一张配图的英文 prompt，用于 AI 绘图。

【要求】
- 风格：科技感插画，参考 The Verge / Wired / TechCrunch 的 AI 板块
- 包含渐变背景（紫色/蓝色/青色系）
- 主体视觉元素要体现项目核心功能（如：机器人/代码流/神经网络/工具图标）
- 不要写实照片风格，更接近图形/插画设计感
- 英文，100-150 tokens，逗号分隔的描述短语
- 纯描述，无引号，无句子

【项目名称】{name}
【一句话介绍】{intro_what}

直接输出 prompt 文本，不需要 JSON。
"""


def generate_cover_prompt(project):
    """生成配图英文描述 prompt。"""
    name = project.get("name", "").split("/")[-1]
    intro = project.get("intro_what", project.get("description", ""))[:80]

    prompt = COVER_PROMPT.format(name=name, intro_what=intro)

    try:
        response = deepseek_call(
            prompt,
            system="你是一位 AI 艺术家和科技插画设计师。输出简洁的英文描述性 prompt。",
            temperature=0.7,
            max_tokens=256,
        )
        text = response.strip()
        logger.info("封面 prompt 生成: %s", text[:80])
        return text
    except Exception as e:
        logger.error("封面 prompt 生成失败: %s", e)
        return ""
