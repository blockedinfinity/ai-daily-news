"""API 服务 —— 只读优先，纯 DB 查询，不触发 RSS/AI。"""

import json
import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

load_dotenv()

from services import db
from services.ai import summarize_news

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ── helpers ───────────────────────────────────────────────────

def success(data=None, message="ok"):
    resp = {"code": 0, "message": message}
    if data is not None:
        resp["data"] = data
    return jsonify(resp), 200


def error(message="error", code=-1, status=400):
    return jsonify({"code": code, "message": message}), status


# ── error handler ─────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return jsonify({"code": e.code, "message": e.description}), e.code
    app.logger.error("未捕获的异常", exc_info=e)
    return jsonify({"code": 500, "message": "服务器内部错误"}), 500


# ── health ────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return success({"status": "ok", "service": "ai-daily-news"})


# ── news ──────────────────────────────────────────────────────

@app.route("/api/news", methods=["GET"])
def list_news():
    date = request.args.get("date", "")
    page = int(request.args.get("page", 1))
    if not date:
        return error("缺少 date 参数")
    items, total = db.get_news_by_date(date, page)
    return success({"items": items, "total": total, "page": page, "per_page": 20})


@app.route("/api/news/today", methods=["GET"])
def today_news():
    return success(db.get_today_news())


@app.route("/api/news/<int:news_id>", methods=["GET"])
def get_news(news_id):
    news = db.get_news(news_id)
    if not news:
        return error("新闻不存在", code=404, status=404)
    return success(news)


@app.route("/api/news", methods=["POST"])
def create_news():
    body = request.get_json(force=True)
    title = body.get("title", "").strip()
    date = body.get("date", "").strip()
    if not title or not date:
        return error("标题和日期不能为空")

    from services.dedup import is_duplicate
    if is_duplicate(title, body.get("url", "")):
        return error("标题或链接已存在", code=409, status=409)

    nid = db.create_news(
        title=title,
        date_str=date,
        url=body.get("url", ""),
        source=body.get("source", ""),
        content=body.get("content", ""),
        summary=body.get("summary", ""),
        published_at=body.get("published_at"),
    )
    return success({"id": nid}, "创建成功")


@app.route("/api/news/<int:news_id>", methods=["DELETE"])
def delete_news(news_id):
    db.delete_news(news_id)
    return success(None, "删除成功")


@app.route("/api/news/<int:news_id>/summarize", methods=["POST"])
def summarize_news_route(news_id):
    """手动触发单条新闻 AI 摘要。"""
    news = db.get_news(news_id)
    if not news:
        return error("新闻不存在", code=404, status=404)
    if news.get("summary"):
        return success({"id": news_id, "summary": news["summary"], "cached": True})
    try:
        result = summarize_news(news["title"], news["content"])
    except RuntimeError as e:
        return error(str(e), code=500, status=500)
    summary_text = (
        f"一句话总结：{result['one_sentence']}\n\n"
        f"中文解释：{result['explanation']}\n\n"
        f"为什么重要：{result['why_important']}"
    )
    db.update_news_summary(news_id, summary_text)
    return success({"id": news_id, "summary": summary_text, "raw": result})


# ── dates ─────────────────────────────────────────────────────

@app.route("/api/dates", methods=["GET"])
def list_dates():
    return success(db.get_available_dates())


# ── summary ───────────────────────────────────────────────────

@app.route("/api/summary", methods=["GET"])
def get_summary():
    date = request.args.get("date", "")
    if not date:
        return error("缺少 date 参数")
    data = db.get_summary(date)
    if not data:
        return error("该日期暂无摘要", code=404, status=404)
    return success(data)


@app.route("/api/summary/generate", methods=["POST"])
def generate_summary_route():
    """手动触发某日日报摘要。"""
    body = request.get_json(force=True) if request.is_json else {}
    date = body.get("date") or request.args.get("date", "")
    if not date:
        return error("缺少 date 参数")
    try:
        from services.ai import generate_summary as batch_summary
        news_list, _ = db.get_news_by_date(date, 1, 1000)
        if not news_list:
            return error("该日期无新闻", code=404, status=404)
        content = batch_summary(news_list)
        news_ids = json.dumps([n["id"] for n in news_list], ensure_ascii=False)
        db.upsert_summary(date, content, news_ids)
        return success({"date": date, "content": content, "news_ids": json.loads(news_ids)}, "摘要生成成功")
    except RuntimeError as e:
        return error(str(e), code=500, status=500)


# ── startup ──────────────────────────────────────────────────

# 确保 WSGI 导入时也初始化数据库
db.init_db()

# PythonAnywhere WSGI 导入时启动调度器
from scheduler import start_scheduler

scheduler = start_scheduler(app)

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
    finally:
        scheduler.shutdown(wait=False)
