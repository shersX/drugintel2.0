# 爬虫日志优化方案（Bioon 及通用）

> 状态：草案，待实施  
> 范围：`backend/src/crawlers/bioon.py`、`base_async_crawler.py`、`registry.py` 及同类爬虫  
> 说明：本文仅描述方案，实施时再改代码。

---

## 1. 背景与问题

当前 Bioon 爬虫日志存在：

- **编排层与执行层重复汇报条数**（列表总数、详情批次总数、`采集完成` 总数）
- **成功路径 INFO 过多**（列表每页 2 条 INFO、批次开始/结束等）
- **缺少任务级关联 ID**，并发详情日志难以串联
- **缺少正文质量维度**（空正文/疑似验证码与网络错误混在一起）
- **调试方法**（`print_news_list`）若误用会产生大量 INFO

工业实践强调：**指标聚合数字、日志记录异常与阶段边界、追踪串联一次任务**。

---

## 2. 目标与原则

### 2.1 目标

1. 一次任务可用 `run_id` 串起全链路
2. 生产默认 INFO 克制（约 3～4 条/任务），排障时可开 DEBUG
3. 结束日志能回答：原始条数、新增条数、有效正文数、失败分类、耗时
4. 为后续接入 Loki/ELK、Prometheus 预留统一 event 名与字段

### 2.2 原则

| 层级 | 职责 |
|------|------|
| **编排层**（`crawl_*_async`） | 1× start + 1× finish（含过滤结果） |
| **列表/详情执行层** | 默认 DEBUG；WARNING/ERROR 仅异常与降级 |
| **基类批次层**（`run_fetch_details`） | 1× 批次汇总，或与 finish 合并，避免与编排层重复总数 |
| **调试工具** | `print_news_list` / `save_to_json` 仅本地 CLI，不走生产 INFO |

---

## 3. 统一事件模型

### 3.1 必打事件（INFO，生产默认）

| event | 触发位置 | 建议字段 |
|-------|----------|----------|
| `crawl_start` | `crawl_bioon_news_async` 入口 | `run_id`, `crawler`, `page_count`, `fetch_details`, `concurrency` |
| `crawl_finish` | 任意出口 | `run_id`, `crawler`, `duration_ms`, `raw_count`, `new_count`, `returned_count`, `outcome` |
| `list_done` | `fetch_news_list` 结束 | `run_id`, `pages_requested`, `pages_ok`, `pages_failed`, `raw_count` |
| `detail_batch_done` | `run_fetch_details` 结束 | `run_id`, `total`, `failed`, `empty_body`, `ok`, …（见第 5 节） |

**`outcome` 枚举：**

- `success` — 正常完成
- `empty_list` — 列表为空（`raw_count == 0`）
- `no_new_items` — 有列表但增量为 0
- `list_only` — 未抓详情
- `partial_detail` — 详情存在失败或空正文
- `failed` — 未捕获致命错误

**`crawl_finish` 合并原「增量过滤完成」字段：**

- `raw_count` — 列表原始条数
- `filtered_count` — `raw_count - new_count`
- `new_count` — 去重后新增条数

### 3.2 条件事件（WARNING / ERROR）

| event | 级别 | 触发条件 |
|-------|------|----------|
| `list_page_failed` | WARNING | 单页 `aiohttp.ClientError` |
| `list_page_error` | ERROR | 单页其它异常（带栈） |
| `list_item_parse_failed` | DEBUG 或 WARNING | 单条 item 解析失败（量大用 DEBUG） |
| `detail_skipped` | WARNING | 无 `detail_url` |
| `detail_fetch_failed` | WARNING | 详情网络错误 |
| `detail_parse_error` | ERROR | 详情未预期异常（带栈） |
| `detail_empty_body` | WARNING | HTTP 200 但无正文区 / `full_text` 过短（疑似验证码） |

每条 WARNING/ERROR 建议带：`run_id`, `detail_url` 或 `page`, `reason`（枚举）。

### 3.3 降级为 DEBUG

| 现状 | 调整后 event |
|------|----------------|
| `列表抓取中 第X页` | `list_page_start` |
| `列表页完成 第X页` | `list_page_done` |
| `详情抓取中 地址=...` | 保持 DEBUG（`detail_request`） |
| `详情抓取开始`（基类） | 删除或改 DEBUG |
| `print_news_list` 全部 | 仅 CLI / `--verbose` |

### 3.4 日志格式示例（过渡期可用 key=value）

```text
event=crawl_finish run_id=8f2a1c crawler=bioon raw_count=10 new_count=8 returned_count=8 duration_ms=45230 outcome=success
```

后续可换 JSON 单行或 `structlog`，无需先引入新依赖。

---

## 4. run_id 传递方案

| 方案 | 说明 | 推荐阶段 |
|------|------|----------|
| **A. ContextVar** | `registry` 生成 `uuid4`，写入 context；子模块 `get_run_id()` 读取 | **P0 首选** |
| B. 显式参数 | `crawl_bioon_news_async(..., run_id=...)` 逐层传递 | 可选，最清晰但改动面大 |
| C. CrawlContext 对象 | 挂 `run_id` + `DetailStats` 在 crawler 实例 | P1 与统计合并 |

**ID 层级建议：**

- Registry 任务：`job_id`
- 单爬虫：`run_id = f"{job_id}:bioon"`

**注意：** `asyncio` 子 task 需验证 ContextVar 继承；写一条集成测试。

---

## 5. 详情质量统计（DetailStats）

在内存中累积，**不打逐条 INFO**：

| 字段 | 递增条件 |
|------|----------|
| `attempted` | 进入详情抓取 |
| `ok` | `full_text` 非空且长度 ≥ 阈值（建议 100 字符） |
| `empty_body` | 无内容 div 或正文为空且 HTTP 200 |
| `network_error` | `aiohttp.ClientError` |
| `parse_error` | 其它 `Exception` |
| `skipped` | 无 `detail_url` |

在 `detail_batch_done` / `crawl_finish` 中输出。  

**可选：** `empty_body` 时检测 HTML 关键词（验证码、访问频繁等）写入 `reason`，不实现打码。

**后续告警（P2）：** `empty_body / attempted > 0.3` 持续 5 分钟 → 降 `concurrency`、拉长 delay。

---

## 6. 分层职责（改后）

```text
registry
  ├─ registry_run_start（job_id, crawlers）
  ├─ crawler_failed（单源 3 次重试仍失败）
  └─ registry_run_finish

crawl_bioon_news_async          【编排】
  ├─ crawl_start
  └─ crawl_finish（含过滤字段，唯一结束 INFO）

fetch_news_list                 【列表】
  ├─ list_page_* → DEBUG
  ├─ list_page_failed / list_page_error
  └─ list_done（一条 INFO）

fetch_news_detail               【详情单条】
  ├─ detail_request → DEBUG
  └─ detail_empty_body / detail_fetch_failed / …

run_fetch_details               【详情批次】
  └─ detail_batch_done（或与 crawl_finish 合并）

save_visited_urls_union         【无日志或 DEBUG】
```

**合并规则：**

- 去掉编排层「采集完成 总数=」与基类「详情抓取完成 总数=」的重复
- 去掉单独「增量过滤完成」INFO，字段并入 `crawl_finish`

---

## 7. 当前日志时刻表（改造前基线）

> 便于对比；默认日志级别 INFO。

### 7.1 主路径 `crawl_bioon_news_async`（`fetch_details=True`）

| 序号 | 位置 | 级别 | 模板 |
|------|------|------|------|
| T0 | 入口 | INFO | 采集开始 页数/抓取详情/并发 |
| T2 | fetch_news_list 每页 | INFO×2 | 列表抓取中 / 列表页完成 |
| T3 | fetch_news_list 结束 | INFO | 列表抓取完成 页数/总数 |
| T4 | 过滤后 | INFO | 增量过滤完成 原始/过滤/新增 |
| T6 | run_fetch_details 开始 | INFO | 详情抓取开始 总数/并发 |
| T7 | fetch_news_detail | DEBUG/WARNING | 见单条详情 |
| T8 | run_fetch_details 结束 | INFO | 详情抓取完成 总数/失败 |
| T10 | 出口 | INFO | 采集完成 总数/耗时 |

### 7.2 提前结束

| 条件 | 日志 |
|------|------|
| `raw_count == 0` | T4 + 采集完成 总数=0 |
| `new_count == 0` | T4 + 采集完成 总数=0（与上相同文案，无法区分原因） |

### 7.3 未在主路径调用

- `save_to_json` → INFO 保存成功
- `print_news_list` → 每条新闻多条 INFO

### 7.4 改造后 INFO 目标（示例：1 页列表 + 8 条详情）

```text
crawl_start
list_done
detail_batch_done   # 可选，若字段已并入 crawl_finish 则省略
crawl_finish
```

约 **3～4 条 INFO**（不含 WARNING）。

---

## 8. 环境与配置

| 变量 | 说明 | 建议 |
|------|------|------|
| `LOG_LEVEL` | 全局级别 | prod/staging: INFO；local: DEBUG |
| `CRAWLER_LOG_LIST_PAGES` | 是否打每页 INFO | prod: false |
| `CRAWLER_LOG_SAMPLE_RATE` | 成功详情采样（可选） | 默认 0（不采样） |

---

## 9. 实施阶段

### P0（1～2 天，无新依赖）

- [ ] 本文 event / outcome / reason 定稿
- [ ] ContextVar + registry 写入 `run_id`
- [ ] 编排层：`crawl_start` + `crawl_finish`；合并增量过滤
- [ ] 列表：`list_done`；每页改 DEBUG
- [ ] 详情批次：保留 `detail_batch_done` 或合并；「详情抓取开始」删或 DEBUG
- [ ] 文档注明 `print_news_list` / `save_to_json` 仅调试

### P1（2～3 天）

- [ ] `DetailStats` + `detail_empty_body` 分类
- [ ] 基类 `run_fetch_details` 可选 stats 回调（兼容 globenewswire / prnewswire）
- [ ] 统一 formatter（key=value 或 JSON）

### P2（按需）

- [ ] Prometheus / OpenTelemetry 指标
- [ ] Loki + Grafana 面板（空正文率、耗时）
- [ ] 告警与自动降 bioon 并发配置

---

## 10. 验收标准

1. 生产 INFO：一次完整 bioon 任务 ≤ 4 条（无 WARNING 时）
2. 用 `run_id` 可检索单次任务全部 WARNING
3. `crawl_finish` 含 `raw_count` / `new_count` / `empty_body`（或等价字段）
4. 开启 DEBUG 后可看到每页、每 URL
5. `print_news_list` 不在 `crawl_bioon_news_async` 调用链上

---

## 11. 与指标的分工（P2）

| 用途 | 手段 |
|------|------|
| QPS、成功率、P99 延迟 | Metrics |
| 首次异常、样本 URL | Logs |
| 跨 crawler 一次调度 | Trace / job_id |

建议指标名（示例）：

- `crawler_duration_seconds{crawler="bioon",stage="total"}`
- `crawler_items_total{crawler="bioon",stage="list|detail",result="ok|empty|error"}`

同一件事不同时打 INFO 又记 metric；以 metric 为主，日志记样本。

---

## 12. 风险与注意

1. `DetailStats` 在 asyncio 单线程事件循环内递增即可
2. ContextVar 与 `asyncio.gather` 需集成测试验证
3. 基类改动保持可选参数，避免破坏其它爬虫
4. 热路径避免每条详情做重 JSON 序列化；仅在 finish 汇总

---

## 13. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-15 | 初稿：基于 bioon 日志梳理与工业实践整理 |
