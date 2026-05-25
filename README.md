# AI Daily News (Mindisphere)

每日 AI 行业新闻摘要 + GitHub 热门项目精选小程序。自动抓取全球 AI 新闻，DeepSeek 生成中文摘要，硅基流动生成新闻封面图，GitHub Trending 精选当日热门开源项目。

## 功能

- **AI 日报**：浏览每日 AI 新闻，AI 自动生成中文摘要与封面图
- **GitHub 热门项目**：每日精选 GitHub Trending 热门开源项目，AI 生成三点极简介绍
- **AI 摘要**：一键生成当日 AI 日报摘要，快速了解行业动态
- **分享**：支持分享新闻和摘要到微信好友及朋友圈
- **WebView 内嵌阅读**：点击新闻跳转 WebView 查看原文

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | 微信小程序（原生 WXML / WXSS / JS） |
| 后端 | Python Flask + Gunicorn |
| 数据库 | PostgreSQL（psycopg2 连接池） |
| AI | DeepSeek API（摘要生成、翻译、项目评分） |
| 图片生成 | 硅基流动 flux-schnell + 腾讯云 COS 存储 |
| 数据源 | RSS 订阅（多个 AI/科技源）+ GitHub Trending / Search API |
| 部署 | Render（后端）+ GitHub Actions（定时抓取） |

## 项目结构

```
ai-daily-news/
├── .github/workflows/
│   └── daily-fetch.yml         # GitHub Actions 每日定时抓取（北京时间 10:00）
├── backend/
│   ├── app.py                  # Flask 入口 & API 路由
│   ├── scheduler.py            # APScheduler 定时任务（可选）
│   ├── fetch_once.py           # 单次执行抓取 + 摘要 + 项目精选
│   ├── backfill_images.py      # 批量回填新闻封面图
│   ├── requirements.txt        # Python 依赖
│   ├── .env.example            # 环境变量模板
│   └── services/
│       ├── db.py               # PostgreSQL 连接池 & 数据操作
│       ├── rss.py              # RSS 新闻抓取
│       ├── ai.py               # DeepSeek API（摘要、翻译、评分）
│       ├── github_trending.py  # GitHub Trending 爬取
│       ├── project_ranker.py   # 项目三维评分 & 介绍生成
│       ├── image_gen.py        # 硅基流动图片生成 + COS 上传
│       └── dedup.py            # 新闻去重
├── frontend/
│   ├── app.js / app.json / app.wxss
│   ├── project.config.json     # 小程序项目配置
│   ├── sitemap.json            # 微信搜索索引配置
│   ├── utils/
│   │   ├── api.js              # 统一请求封装（TTL 缓存、超时、鉴权）
│   │   └── util.js             # 工具函数（日期格式化等）
│   └── pages/
│       ├── index/              # 首页（新闻列表 + GitHub 热门项目）
│       ├── summary/            # AI 摘要页（日报摘要 + 项目精选）
│       ├── detail/             # 新闻详情页
│       └── webview/            # WebView 内嵌浏览器
├── render.yaml                 # Render 部署配置
└── README.md
```

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/news?date=2026-05-15 | 按日期获取新闻列表 |
| GET | /api/news/today | 获取今日新闻（快捷接口） |
| GET | /api/news/:id | 获取新闻详情 |
| POST | /api/news | 新增新闻 |
| DELETE | /api/news/:id | 删除新闻 |
| POST | /api/news/:id/summarize | 对单条新闻生成摘要 |
| GET | /api/dates | 获取有新闻的日期列表 |
| GET | /api/summary-dates | 获取有 AI 摘要的日期列表 |
| GET | /api/summary?date=2026-05-15 | 获取指定日期的 AI 日报摘要 |
| POST | /api/summary/generate | 生成指定日期的 AI 日报摘要 |
| GET | /api/project?date=2026-05-15 | 获取指定日期精选项目列表 |
| GET | /api/project-dates | 获取有精选项目的日期列表 |
| GET | /api/fetch | 手动触发抓取（需内部密钥） |
| POST | /api/backfill-images | 批量回填封面图（需内部密钥） |

## 快速开始

### 1. 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DATABASE_URL、DEEPSEEK_API_KEY 等

# 启动服务（开发模式）
python app.py
```

启动后 API 运行在 `http://localhost:5000`。

### 2. 前端

用微信开发者工具打开 `frontend/` 目录。

连接后端：
- 本地开发：在 `frontend/utils/api.js` 中确认 `BASE_URL` 指向 `http://localhost:5000`
- 微信开发者工具中需开启 "不校验合法域名" 选项

## 部署

### 后端（Render）

项目已配置 `render.yaml`，可直接导入 Render：
- 运行时：Python，新加坡节点
- 构建命令：`pip install -r requirements.txt`
- 启动命令：`gunicorn app:app`
- 需配置环境变量：`DATABASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`GITHUB_TOKEN`、`SILICONFLOW_API_KEY`、`COS_*` 等

### 定时抓取（GitHub Actions）

`.github/workflows/daily-fetch.yml` 每日北京时间 10:00 自动执行：
1. RSS 抓取新闻 → 去重 → DeepSeek 翻译为中文
2. 生成当日 AI 日报摘要
3. 爬取 GitHub Trending → AI 评分精选 → 生成项目介绍
4. 生成新闻封面图 → 上传至腾讯云 COS

支持手动触发（workflow_dispatch）。
