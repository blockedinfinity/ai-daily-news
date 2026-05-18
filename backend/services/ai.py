"""DeepSeek API 调用 —— 纯函数，无状态。"""

import json
import logging
import os

from openai import OpenAI

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            _client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30.0, max_retries=2)
        except Exception:
            _client = None
    return _client


def deepseek_call(prompt, system="", temperature=0.3, max_tokens=4096):
    """底层 API 调用：发文本，收文本。"""
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages.insert(0, {"role": "system", "content": system})
    try:
        resp = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"DeepSeek API 调用失败: {e}")


def parse_batch_result(text):
    """解析 AI 返回的 JSON，提取每条新闻的摘要 + 日报。"""
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return data.get("items", []), data.get("daily_digest", "")


def _is_english(text):
    """检测文本是否为英文（>50% 的字母字符是 ASCII）。"""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return False
    en = sum(1 for c in alpha if c.isascii())
    return en / len(alpha) > 0.5


def batch_translate(items):
    """批量翻译英文新闻为中文。为 items 添加 title_cn/content_cn 字段。"""
    en_idx = [i for i, item in enumerate(items) if _is_english(item.get("title", "") + item.get("content", ""))]

    if not en_idx:
        for item in items:
            item["title_cn"] = item.get("title", "")
            item["content_cn"] = item.get("content", "")
        return items

    lines = []
    for i in en_idx:
        item = items[i]
        lines.append(f"[{i}] Title: {item['title']}\nContent: {(item.get('content', '') or '')[:800]}")

    prompt = (
        "Translate the following English AI news to Chinese.\n"
        "Rules:\n"
        "- Keep technical terms (GPT-5, MoE, Transformer, LLM, etc.) unchanged\n"
        "- Keep company/product/model names unchanged\n"
        "- Output natural Chinese\n\n"
        + "\n\n---\n\n".join(lines)
        + "\n\nReturn JSON array only: [{\"index\": 0, \"title_cn\": \"...\", \"content_cn\": \"...\"}, ...]"
    )

    try:
        response = deepseek_call(prompt, system="Professional translator for AI/tech content.", temperature=0.1)
        text = response.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        translations = json.loads(text)
        tmap = {t["index"]: t for t in translations}
    except Exception as e:
        logger.warning("翻译失败: %s", e)
        tmap = {}

    for i, item in enumerate(items):
        if i in en_idx and i in tmap:
            item["title_cn"] = tmap[i].get("title_cn", item["title"])
            item["content_cn"] = tmap[i].get("content_cn", item.get("content", ""))
        else:
            item["title_cn"] = item.get("title", "")
            item["content_cn"] = item.get("content", "")
    return items


def batch_summarize(news_list):
    """批量总结：跳过已有摘要的新闻，只对新内容调用 DeepSeek。"""
    if not news_list:
        return [], "今天还没有新闻。"

    # 优先使用翻译后的中文内容，已翻译的用翻译内容，未翻译的用原文
    def _content(n):
        return (n.get("content_cn") or n.get("content") or "")[:500]

    # 只摘要尚未生成摘要的新闻
    need_summary = [n for n in news_list if not n.get("summary")]
    already_done = [n for n in news_list if n.get("summary")]

    if not need_summary:
        return news_list, "今日所有新闻已有摘要"

    prompt = ""
    for n in need_summary:
        prompt += f"""
标题：{n.get('title_cn') or n['title']}
内容：{_content(n)}
---
"""

    prompt += f"""

请对以上 {len(need_summary)} 条新闻逐条总结，并生成今日日报。
严格按照 JSON 格式返回（不要 markdown 代码块）：
{{
  "items": [
    {{
      "title": "新闻标题（必须与输入完全一致）",
      "one_sentence": "一句话总结（20字以内）",
      "explanation": "中文解释（100字以内，通俗易懂）",
      "why_important": "为什么重要（100字以内，对行业或普通人的影响）"
    }}
  ],
  "daily_digest": "今日AI行业日报（300字以内，整体趋势+要点概述）"
}}"""

    response = deepseek_call(
        prompt,
        system="你是一个AI新闻分析师，用JSON格式返回结构化分析结果。",
    )
    items, digest = parse_batch_result(response)

    # 用标题匹配：支持中文标题（翻译后）或原始英文标题
    summary_map = {s["title"]: s for s in items}

    for n in need_summary:
        key = (n.get("title_cn") or n["title"])
        s = summary_map.get(key, {})
        if s:
            n["summary"] = (
                f"一句话总结：{s.get('one_sentence', '')}\n\n"
                f"中文解释：{s.get('explanation', '')}\n\n"
                f"为什么重要：{s.get('why_important', '')}"
            )

    return news_list, digest


def summarize_news(title, content):
    """单条新闻摘要。返回结构化 dict。"""
    prompt = f"""你是一个专业的AI新闻分析师。请对以下新闻进行分析，并严格按照JSON格式输出。

新闻标题：{title}
新闻内容：{content}

请分析并返回JSON（不要markdown代码块），格式如下：
{{
  "one_sentence": "一句话总结（20字以内）",
  "explanation": "中文解释（100字以内，通俗易懂）",
  "why_important": "为什么重要（100字以内，对行业或普通人的影响）"
}}"""

    response = deepseek_call(
        prompt,
        system="你是一个AI新闻分析师，用JSON格式返回结构化分析结果。",
        max_tokens=1024,
    )
    return json.loads(response)


def generate_summary(news_list):
    """从每日精华文章中提炼最核心的洞察与要点。返回纯文本。"""
    if not news_list:
        return "今天还没有新闻。"

    news_text = "\n\n".join(
        f"标题：{n['title']}\n来源：{n['source']}\n摘要：{n['summary'] or n['content'][:200]}"
        for n in news_list
    )

    prompt = f"""你是一位资深的 AI 行业分析师。以下是今天从全网筛选出的 {len(news_list)} 篇精华文章。

你的任务是从这些文章中提炼出最核心、最重要的洞察，帮读者用最短时间抓住要点。

请按以下结构输出（使用 emoji 作为视觉标记，保持简洁有力）：

📌 今日核心（1-2 句话概括今天最重要的趋势或事件）

🔥 精华提炼（每条 1-2 句，不超过 5 条，只写最重要的）
- 用一句话说明事件 + 为什么值得关注

💡 关键洞察（1-2 条深层次的观察，不是重复新闻内容，而是你的独立判断）

今日文章：
{news_text}"""

    return deepseek_call(
        prompt,
        system="你是一位资深 AI 行业分析师，擅长从海量信息中提炼最核心的洞察。语言简洁有力，直击要害，避免空话套话。",
        temperature=0.5,
        max_tokens=1500,
    )
