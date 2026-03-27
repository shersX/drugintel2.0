# DrugIntel.ai 项目文件布局

## 文档信息

| 项目 | 内容 |
|------|------|
| 项目名称 | DrugIntel.ai - 医药情报AI平台 |
| 文档版本 | V1.0 |
| 创建日期 | 2026-03-26 |
| 关联文档 | [PRD.md](./PRD.md) |

---

## 项目根目录

```
drugintel-ai/
├── backend/                 # 后端服务
├── frontend/                # 前端应用
├── config/                  # 配置文件
├── docker/                  # Docker配置
├── docker-compose.yml       # Docker Compose编排
├── PRD.md                   # 产品需求文档
├── IMPLEMENTATION_PLAN.md   # 实现计划
├── PROJECT_STRUCTURE.md     # 项目文件布局（本文档）
└── README.md                # 项目说明
```

---

## 后端目录结构

```
backend/
├── src/
│   ├── api/                      # API层
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI入口
│   │   ├── dependencies.py       # 依赖注入
│   │   ├── middleware.py         # 中间件
│   │   └── routes/               # 路由模块
│   │       ├── __init__.py
│   │       ├── news.py           # 新闻相关API
│   │       ├── events.py         # 事件相关API
│   │       ├── search.py         # 搜索API
│   │       ├── chat.py           # RAG问答API
│   │       ├── watchlist.py      # 告警订阅API
│   │       ├── stats.py          # 统计数据API
│   │       ├── monitor.py        # 监控API
│   │       └── drug_rd.py        # 研发进度API
│   │
│   ├── crawlers/                 # 数据采集模块
│   │   ├── __init__.py
│   │   ├── base.py               # 爬虫基类
│   │   ├── bioon.py              # Bioon爬虫
│   │   ├── globenewswire.py      # GlobeNewswire爬虫
│   │   ├── prnewswire.py         # PRNewswire爬虫
│   │   ├── businesswire.py       # BusinessWire爬虫
│   │   └── registry.py           # 爬虫注册表
│   │
│   ├── processors/               # 数据处理模块
│   │   ├── __init__.py
│   │   ├── cleaner.py            # 文本清洗
│   │   ├── filter.py             # 关键词过滤
│   │   ├── relevance.py          # LLM相关性判断
│   │   ├── deduplicator.py       # 标题去重
│   │   ├── summarizer.py         # LLM摘要生成
│   │   └── embedding.py          # 向量生成
│   │
│   ├── clustering/               # 事件聚类模块
│   │   ├── __init__.py
│   │   ├── clusterer.py          # 聚类算法
│   │   └── representative.py     # 代表新闻选择
│   │
│   ├── rag/                      # RAG问答模块
│   │   ├── __init__.py
│   │   ├── intent.py             # 意图识别
│   │   ├── retriever.py          # 检索器
│   │   ├── reranker.py           # 重排序
│   │   ├── generator.py          # LLM生成
│   │   ├── conversation.py       # 对话管理
│   │   └── prompts.py            # 提示词模板
│   │
│   ├── search/                   # 搜索检索模块
│   │   ├── __init__.py
│   │   ├── fulltext.py           # 全文搜索
│   │   ├── vector.py             # 向量检索
│   │   └── hybrid.py             # 混合搜索
│   │
│   ├── alerts/                   # 告警通知模块
│   │   ├── __init__.py
│   │   ├── matcher.py            # 规则匹配
│   │   ├── email_sender.py       # 邮件发送
│   │   └── templates/            # 邮件模板
│   │       └── alert_email.html
│   │
│   ├── monitor/                  # 监控模块
│   │   ├── __init__.py
│   │   ├── crawler_monitor.py    # 爬虫监控
│   │   ├── processing_monitor.py # 处理监控
│   │   └── health.py             # 健康检查
│   │
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   ├── base.py               # 基础模型
│   │   ├── news.py               # 新闻模型
│   │   ├── event.py              # 事件模型
│   │   ├── company.py            # 公司模型
│   │   ├── drug.py               # 药物模型
│   │   ├── watchlist.py          # Watchlist模型
│   │   └── crawler_task.py       # 爬虫任务模型
│   │
│   ├── schemas/                  # Pydantic模式
│   │   ├── __init__.py
│   │   ├── news.py
│   │   ├── event.py
│   │   ├── chat.py
│   │   └── watchlist.py
│   │
│   ├── db/                       # 数据库
│   │   ├── __init__.py
│   │   ├── session.py            # 会话管理
│   │   ├── crud/                 # CRUD操作
│   │   │   ├── __init__.py
│   │   │   ├── news.py
│   │   │   ├── event.py
│   │   │   └── watchlist.py
│   │   └── migrations/           # 数据库迁移
│   │
│   ├── core/                     # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py             # 配置管理
│   │   ├── logging.py            # 日志配置
│   │   └── exceptions.py         # 异常定义
│   │
│   └── llm/                      # LLM服务
│       ├── __init__.py
│       └── client.py             # LLM客户端
│
├── tasks/                        # Celery任务
│   ├── __init__.py
│   ├── celery_app.py             # Celery配置
│   ├── crawl_tasks.py            # 爬虫任务
│   ├── process_tasks.py          # 处理任务
│   ├── cluster_tasks.py          # 聚类任务
│   └── alert_tasks.py            # 告警任务
│
├── scripts/                      # 脚本
│   ├── init_db.py                # 初始化数据库
│   ├── create_indexes.py         # 创建索引
│   └── seed_data.py              # 种子数据
│
├── tests/                        # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_crawlers/
│   ├── test_processors/
│   ├── test_rag/
│   └── test_api/
│
├── pyproject.toml                # 项目配置
├── requirements.txt              # 依赖
└── .env.example                  # 环境变量示例
```

---

## 前端目录结构

```
frontend/
├── src/
│   ├── views/                    # 页面
│   │   ├── HomeView.vue          # 首页
│   │   ├── NewsListView.vue      # 新闻列表
│   │   ├── NewsDetailView.vue    # 新闻详情
│   │   ├── ChatView.vue          # RAG问答
│   │   ├── WatchlistView.vue     # 告警管理
│   │   ├── MonitorView.vue       # 系统监控
│   │   └── DrugRDView.vue        # 研发进度
│   │
│   ├── components/               # 组件
│   │   ├── common/               # 通用组件
│   │   │   ├── Header.vue
│   │   │   ├── Sidebar.vue
│   │   │   └── Loading.vue
│   │   ├── news/                 # 新闻组件
│   │   │   ├── NewsList.vue
│   │   │   ├── NewsCard.vue
│   │   │   └── RelatedNews.vue
│   │   ├── chat/                 # 问答组件
│   │   │   ├── ChatWindow.vue
│   │   │   ├── MessageBubble.vue
│   │   │   └── SourceList.vue
│   │   ├── stats/                # 统计组件
│   │   │   ├── StatsCard.vue
│   │   │   └── TrendChart.vue
│   │   └── monitor/              # 监控组件
│   │       └── CrawlerStatus.vue
│   │
│   ├── api/                      # API调用
│   │   ├── index.ts
│   │   ├── news.ts
│   │   ├── chat.ts
│   │   ├── watchlist.ts
│   │   └── monitor.ts
│   │
│   ├── stores/                   # Pinia状态管理
│   │   ├── index.ts
│   │   ├── news.ts
│   │   ├── chat.ts
│   │   └── monitor.ts
│   │
│   ├── router/                   # 路由
│   │   └── index.ts
│   │
│   ├── styles/                   # 样式
│   │   ├── main.css
│   │   └── variables.css
│   │
│   ├── App.vue
│   └── main.ts
│
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── .env.example
```

---

## 配置目录结构

```
config/
├── keywords.py                   # 关键词配置
└── prompts/                      # 提示词配置
    ├── summary.txt               # 摘要生成提示词
    ├── intent.txt                # 意图识别提示词
    └── system.txt                # 系统提示词
```

---

## Docker目录结构

```
docker/
├── Dockerfile.backend            # 后端Dockerfile
├── Dockerfile.frontend           # 前端Dockerfile
└── nginx.conf                    # Nginx配置
```

---

## 模块与目录对应关系

| PRD模块 | 后端目录 | 前端目录 |
|---------|----------|----------|
| 数据采集 | `src/crawlers/` | - |
| 数据处理 | `src/processors/` | - |
| 数据存储 | `src/models/`, `src/db/` | - |
| 事件聚类 | `src/clustering/` | - |
| RAG问答 | `src/rag/` | `views/ChatView.vue`, `components/chat/` |
| 搜索检索 | `src/search/` | - |
| 告警通知 | `src/alerts/` | `views/WatchlistView.vue` |
| 核心数据展示 | `src/api/routes/stats.py` | `components/stats/` |
| 轻量级监控 | `src/monitor/` | `views/MonitorView.vue`, `components/monitor/` |
| API服务 | `src/api/` | `api/` |
| 前端应用 | - | `views/`, `components/` |

---

## 关键文件说明

### 后端核心文件

| 文件 | 说明 |
|------|------|
| `src/api/main.py` | FastAPI应用入口，路由注册 |
| `src/core/config.py` | 环境变量、配置项管理 |
| `src/db/session.py` | 数据库连接池、会话管理 |
| `src/crawlers/base.py` | 爬虫抽象基类 |
| `src/rag/retriever.py` | RAG检索核心逻辑 |
| `tasks/celery_app.py` | Celery应用配置 |

### 前端核心文件

| 文件 | 说明 |
|------|------|
| `src/main.ts` | Vue应用入口 |
| `src/router/index.ts` | 路由配置 |
| `src/api/index.ts` | Axios实例、请求拦截器 |
| `src/stores/index.ts` | Pinia状态管理配置 |

---

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-03-26 | V1.0 | 初始版本 |
