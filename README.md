# AI Daily News

每日 AI 行业新闻摘要小程序。用户可浏览每日 AI 新闻，并通过 DeepSeek API 一键生成 AI 日报摘要。

## 项目结构

```
ai-daily-news/
├── backend/                  # Python Flask 后端
│   ├── app.py                # Flask 入口
│   ├── config.py             # 配置（API Key、数据库路径等）
│   ├── requirements.txt      # Python 依赖
│   ├── .env                  # 环境变量配置
│   ├── seed_data.py          # 测试数据填充脚本
│   ├── database/
│   │   └── db.py             # SQLite 数据库初始化
│   ├── models/
│   │   ├── news.py           # 新闻数据层
│   │   └── summary.py        # 摘要数据层
│   ├── routes/
│   │   ├── __init__.py       # 蓝图注册
│   │   ├── news_routes.py    # 新闻 API 路由
│   │   └── summary_routes.py # 摘要 API 路由
│   ├── services/
│   │   ├── news_service.py   # 新闻业务逻辑
│   │   └── deepseek_service.py  # DeepSeek API 集成
│   └── utils/
│       └── response.py       # 统一响应格式
├── frontend/                 # 微信小程序前端
│   ├── app.js / app.json / app.wxss
│   ├── project.config.json
│   ├── sitemap.json
│   ├── utils/
│   │   ├── api.js            # API 请求封装
│   │   └── util.js           # 工具函数
│   ├── components/
│   │   └── news-card/        # 新闻卡片组件
│   └── pages/
│       ├── index/            # 首页（新闻列表）
│       ├── detail/           # 新闻详情页
│       └── summary/          # AI 摘要页
└── README.md
```

## 快速开始

### 1. 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
# 编辑 .env 文件，填入 DeepSeek API Key:
# DEEPSEEK_API_KEY=sk-your-key-here

# 可选：填充测试数据
python seed_data.py

# 启动服务
python app.py
```

启动后 API 运行在 `http://localhost:5000`。

### 2. 前端

用微信开发者工具打开 `frontend/` 目录。

连接后端：
- 本地开发：在 `frontend/utils/api.js` 中确认 `baseUrl` 指向 `http://localhost:5000/api`
- 真机调试：需将后端部署到公网或使用内网穿透，更新 `baseUrl`
- 微信开发者工具中需开启 "不校验合法域名" 选项

## API 文档

| 请求方式 | 路径 | 说明 |
|---------|------|------|
| GET | /api/news?date=2026-05-15 | 按日期获取新闻列表 |
| GET | /api/news/:id | 获取新闻详情 |
| POST | /api/news | 新增新闻 |
| DELETE | /api/news/:id | 删除新闻 |
| GET | /api/dates | 获取有新闻的日期列表 |
| GET | /api/summary?date=2026-05-15 | 获取指定日期的 AI 摘要 |
| POST | /api/summary/generate | 生成指定日期的 AI 摘要 |

## 扩展计划

- [ ] 定时任务：每日自动抓取新闻并生成摘要
- [ ] 用户收藏功能
- [ ] 新闻分类与标签
- [ ] 分享功能
- [ ] 云端部署指南
