"""DeepSeek API 调用 —— 纯函数，无状态。"""

import json
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
        _client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30.0, max_retries=2)
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
    """批量总结：一次 DeepSeek 调用，返回 (items_with_summary, daily_digest)。"""
    if not news_list:
        return [], "今天还没有新闻。"

    prompt = ""
    for n in news_list:
        prompt += f"""
标题：{n['title']}
内容：{n.get('content', '')[:300]}
---
"""
    prompt += f"""

请对以上 {len(news_list)} 条新闻逐条总结，并生成今日日报。
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

    summary_map = {s["title"]: s for s in items}
    items_with_summary = []
    for n in news_list:
        s = summary_map.get(n["title"], {})
        if s:
            summary = (
                f"一句话总结：{s.get('one_sentence', '')}\n\n"
                f"中文解释：{s.get('explanation', '')}\n\n"
                f"为什么重要：{s.get('why_important', '')}"
            )
        else:
            summary = ""
        items_with_summary.append({**n, "summary": summary})

    return items_with_summary, digest


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
    """批量新闻日报摘要。返回纯文本。"""
    if not news_list:
        return "今天还没有新闻。"

    news_text = "\n\n".join(
        f"标题：{n['title']}\n来源：{n['source']}\n摘要：{n['summary'] or n['content'][:200]}"
        for n in news_list
    )

    prompt = f"""你是一个AI新闻编辑。请根据以下今日AI行业新闻，生成一份结构清晰的中文日报摘要。

要求：
1. 先用一两句话总结今天的整体趋势
2. 然后按主题分类（如：大模型、AI应用、行业动态等）
3. 每类下列出相关新闻及一句话点评
4. 最后给出你的观察与展望

今日新闻：
{news_text}"""

    return deepseek_call(
        prompt,
        system="你是一个专业的AI新闻编辑，擅长撰写简洁、有洞察力的日报摘要。",
        temperature=0.7,
        max_tokens=2048,
    )
