"""RSS 抓取 —— 可替换为真实 RSS/API 源。"""

from datetime import datetime

SOURCES = [
    {
        "title": "DeepSeek 发布全新 MoE 架构模型，推理效率提升 3 倍",
        "url": "https://example.com/deepseek-moe",
        "source": "机器之心",
        "content": (
            "DeepSeek 今日发布了其最新研发的混合专家（MoE）架构大语言模型。"
            "该模型采用了创新的路由算法，在保持模型性能的同时，将推理速度提升了 3 倍，"
            "显著降低了推理成本。新模型在多项基准测试中均达到了业界领先水平。"
        ),
    },
    {
        "title": "OpenAI 宣布 GPT-5 即将进入公开测试阶段",
        "url": "https://example.com/gpt5",
        "source": "TechCrunch",
        "content": (
            "OpenAI 首席执行官 Sam Altman 今日在开发者大会上宣布，GPT-5 已进入最后的内部测试阶段，"
            "预计将在下月开放公开测试。GPT-5 在推理能力、多模态理解和长上下文处理方面均有重大突破。"
            "据悉，新模型将支持 1M token 的上下文窗口。"
        ),
    },
    {
        "title": "Google 将 Gemini 深度整合至 Android 系统层",
        "url": "https://example.com/gemini-android",
        "source": "The Verge",
        "content": (
            "Google 在 I/O 大会上宣布，将在下一版 Android 系统中将 Gemini AI 助手深度整合至操作系统层。"
            "用户将可以通过全新的系统级 AI 接口调用 Gemini 的能力，"
            "包括屏幕理解、实时翻译、智能摘要等功能。"
        ),
    },
    {
        "title": "Anthropic 发布 Claude 安全框架新版本",
        "url": "https://example.com/claude-safety",
        "source": "Anthropic Blog",
        "content": (
            "Anthropic 今日发布了其 AI 安全框架的最新版本，"
            "引入了更严格的红队测试标准和部署前评估流程。"
            "新框架要求所有模型在发布前必须通过多轮独立安全评估。"
        ),
    },
    {
        "title": "Meta 开源全新多模态模型 ImageBind 2.0",
        "url": "https://example.com/imagebind",
        "source": "Meta AI",
        "content": (
            "Meta 今日正式开源 ImageBind 2.0，这是迄今为止最强大的多模态 AI 模型之一。"
            "新版本在原有六种模态的基础上，新增了对触觉信号和嗅觉数据的理解能力。"
        ),
    },
]


def fetch_news():
    """抓取新闻列表。返回 [dict, ...]，每条含 title/url/source/content 字段。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return [
        {"title": s["title"], "url": s["url"], "source": s["source"],
         "content": s["content"], "published_at": now}
        for s in SOURCES
    ]
