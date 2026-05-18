"""清理数据库中的测试/调试数据，并查看各日期新闻数量。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from services import db
import psycopg2
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

RAW = os.getenv("DATABASE_URL", "")
if not RAW:
    print("DATABASE_URL 未设置")
    sys.exit(1)

# 清理 channel_binding 参数（与 db.py 一致）
parsed = urlparse(RAW)
params = [(k, v) for k, v in parse_qsl(parsed.query) if k != "channel_binding"]
cleaned = parsed._replace(query=urlencode(params))
DATABASE_URL = urlunparse(cleaned)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # 1. 删除测试/调试条目
    cur.execute("DELETE FROM news WHERE title = 'test' OR title LIKE '%test%' OR source = 'debug'")
    print(f"删除测试新闻: {cur.rowcount} 条")

    # 2. 查看当前各日期数据量
    cur.execute("SELECT date, COUNT(*) AS cnt FROM news GROUP BY date ORDER BY date DESC")
    rows = cur.fetchall()
    print("\n各日期新闻数量:")
    for r in rows:
        print(f"  {r[0]}: {r[1]} 条")

    # 3. 询问是否只保留今天的数据
    today = db.date.today().isoformat()
    conn.commit()
    cur.close()
    conn.close()
    print(f"\n清理完成。今天 ({today}) 的新闻已在数据库中。")


if __name__ == "__main__":
    main()
