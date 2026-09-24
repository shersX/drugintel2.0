# DrugIntel.ai 用户指南

## 功能概览

1. **采集**：多源新闻爬取（bioon / globenewswire / prnewswire）
2. **处理**：关键词过滤 → 相关性 → 去重 → 摘要 → 向量化 → 入库
3. **聚类**：将相似新闻归并为事件簇并选出代表新闻
4. **问答**：基于混合检索的医药情报问答（支持多轮与导出报告）
5. **告警**：Watchlist 关键词命中后邮件通知（需配置 SMTP）
6. **监控**：健康检查、处理状态、爬虫任务记录

## 前端页面

- 仪表盘：总量与趋势
- 新闻：列表与详情（含同事件簇）
- 问答：多轮会话、PDF 导出
- 告警：订阅管理
- 监控：系统健康

## 环境变量

| 变量 | 说明 |
|------|------|
| SILICONFLOW_API_KEY | 大模型密钥 |
| SILICONFLOW_MODEL | Chat 模型 |
| SILICONFLOW_EMBEDDING_MODEL | 默认 BAAI/bge-m3 |
| SILICONFLOW_RERANKER_MODEL | 默认 BAAI/bge-reranker-v2-m3 |
| DATABASE_URL | PostgreSQL（Windows 用 127.0.0.1） |
| REDIS_URL | 对话与 Celery |
| SMTP_* | 告警邮件 |

## 常见问题

- **DB 容器 Restarting**：不要把数据目录挂在 `/mnt/d`（NTFS），改用 `$HOME/drugintel-pgdata`
- **连接卡住**：把 `localhost` 改为 `127.0.0.1`
- **问答无结果**：先跑 `main.py` 入库并确认 `news.embedding` 非空
