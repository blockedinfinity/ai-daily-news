"""API 服务 —— 小程序后端。"""

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

# CORS: 只允许小程序请求和本地开发
_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
CORS(app, resources={r"/api/*": {"origins": _ALLOWED_ORIGINS.split(",") if _ALLOWED_ORIGINS != "*" else "*"}})

# 内部操作密钥（防止外部调用 /api/fetch 等端点）
_INTERNAL_KEY = os.getenv("INTERNAL_KEY", "")


# ── helpers ───────────────────────────────────────────────────

def success(data=None, message="ok"):
    resp = {"code": 0, "message": message}
    if data is not None:
        resp["data"] = data
    return jsonify(resp), 200


def error(message="error", code=-1, status=400):
    return jsonify({"code": code, "message": message}), status


def _check_internal():
    """校验内部操作密钥，防止外部调用管理端点。未设置 INTERNAL_KEY 时跳过检查。"""
    if not _INTERNAL_KEY:
        return None
    key = request.headers.get("X-Internal-Key", "") or request.args.get("key", "")
    if key != _INTERNAL_KEY:
        return error("无权限", code=403, status=403)
    return None


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
    db_ok = False
    try:
        conn = db._connect()
        db._putback(conn)
        db_ok = True
    except Exception:
        pass
    return success({"status": "ok" if db_ok else "db_error", "db": db_ok, "service": "ai-daily-news"})


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
    auth = _check_internal()
    if auth:
        return auth
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
    auth = _check_internal()
    if auth:
        return auth
    db.delete_news(news_id)
    return success(None, "删除成功")


@app.route("/api/news/<int:news_id>/summarize", methods=["POST"])
def summarize_news_route(news_id):
    """手动触发单条新闻 AI 摘要。"""
    auth = _check_internal()
    if auth:
        return auth
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
    auth = _check_internal()
    if auth:
        return auth
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


# ── backfill images ──────────────────────────────────────────

@app.route("/api/backfill-images", methods=["POST"])
def backfill_images():
    """为已有新闻回填 image_url（从文章页面提取 og:image）。"""
    auth = _check_internal()
    if auth:
        return auth
    import psycopg2.extras
    from services.rss import _extract_first_image
    import requests as _req

    try:
        conn = db._connect()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, url, title FROM news WHERE (image_url IS NULL OR image_url = '') AND url != '' ORDER BY id"
            )
            news_items = cur.fetchall()
        finally:
            db._putback(conn)

        if not news_items:
            return success({"total": 0, "updated": 0}, "所有新闻已有图片，无需回填")

        updated = 0
        failed = 0
        results = []
        for news in news_items:
            url = (news.get("url") or "").strip()
            if not url:
                continue
            try:
                resp = _req.get(
                    url, timeout=10,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Daily-News/1.0)"},
                )
                if resp.status_code == 200 and len(resp.text) > 200:
                    image = _extract_first_image(resp.text[:50000])
                    if image:
                        conn2 = db._connect()
                        try:
                            cur2 = conn2.cursor()
                            cur2.execute("UPDATE news SET image_url = %s WHERE id = %s", (image, news["id"]))
                            conn2.commit()
                        finally:
                            db._putback(conn2)
                        updated += 1
                        results.append({"id": news["id"], "title": news["title"][:40], "image": image[:80]})
                        app.logger.info("[backfill] [%d] %s -> %s", news["id"], news["title"][:30], image[:60])
                    else:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                app.logger.warning("[backfill] [%d] 获取失败: %s", news["id"], e)

        return success({
            "total": len(news_items),
            "updated": updated,
            "failed": failed,
            "results": results,
        }, f"回填完成: {updated}/{len(news_items)} 条")
    except Exception as e:
        import traceback
        app.logger.error("[backfill] %s\n%s", e, traceback.format_exc())
        return error(str(e), code=500, status=500)


# ── fetch (仅供内部测试) ────────────────────────────────────
# 完整流程（含翻译+摘要）请使用 GitHub Actions fetch_once.py。

@app.route("/api/fetch", methods=["GET", "POST"])
def trigger_fetch():
    """抓取 RSS + 精选 + 入库（仅供内部测试，完整流程走 GitHub Actions fetch_once.py）。"""
    auth = _check_internal()
    if auth:
        return auth
    try:
        from services import rss, dedup

        news_list = rss.fetch_news()
        filtered = dedup.filter_new(news_list)
        if not filtered:
            return success({"fetched": len(news_list), "filtered": 0, "saved": 0}, "无新新闻")

        count = db.save_news(filtered, "")
        return success({"fetched": len(news_list), "filtered": len(filtered), "saved": count}, f"入库 {count} 条")
    except Exception as e:
        import traceback
        app.logger.error("[fetch] %s\n%s", e, traceback.format_exc())
        return error(str(e), code=500, status=500)


# ── startup ──────────────────────────────────────────────────

# 确保 WSGI 导入时也初始化数据库
try:
    db.init_db()
except Exception as e:
    app.logger.error("数据库初始化失败: %s", e)

# 已改用 GitHub Actions (fetch_once.py)
# from scheduler import start_scheduler
# scheduler = start_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
