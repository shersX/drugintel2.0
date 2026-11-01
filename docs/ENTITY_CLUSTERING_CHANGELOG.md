# 实体 / 流式聚类 / CI 评分 — 变更说明书（供 AI / 后续开发读取）

> **用途**：让后续 Agent 或开发者在不翻聊天记录的情况下，准确理解本轮改动的边界、文件、表结构、API 与不变量。  
> **关联**：实现细节见本文；优化 backlog 见 [CLUSTERING_MIGRATION.md](./CLUSTERING_MIGRATION.md)；评分边界见 [CI_SCORING_ROADMAP.md](./CI_SCORING_ROADMAP.md)；文献背景见 [CLUSTERING_PAPERS.md](./CLUSTERING_PAPERS.md)。  
> **实验原型目录**：仓库根旁 `聚类算法/`（demo）；生产实现在 `drugintel2.0/backend/src/`。

---

## 1. 一句话结论

在 `drugintel2.0` 中接入：**独立 NER 槽（默认 Qwen3-8B）→ alias 词典归一化 → 产品优先 StreamingClusterer（弱实体 0.90/0.80）→ 事件情报风险分 + 管线阶段先验 PoS**；新闻页具备实体分面/芯片；**不做** Cortellis 级临床 LoA。

---

## 2. 数据流（必须按此顺序理解）

```text
爬取 → 关键词过滤 → raw 入库
  → 相关性(对话模型) → 摘要(对话模型)
  → 实体抽取(实体槽 Qwen3-8B) → alias 归一化 + entity_lexicon 回流
  → 嵌入(嵌入槽) → news ready
  → StreamingClusterer 增量/批处理 → event 汇总字段 + ci_risk_score
```

- 对话槽 / 嵌入槽 / 实体槽 **分离**（`llm_profile`）。  
- 聚类强路径只认 **product（优先）/ drug**；**org / target / indication 不参与强并簇**，只服务展示与筛选。  
- 落库与聚类只认 **canonical**（小写预处理后）；LLM 原文进 `entity_raw`。

---

## 3. 数据库变更

### 3.1 新表

| 表 | 模型文件 | 说明 |
|----|----------|------|
| `entity_lexicon` | `backend/src/models/entity_lexicon.py` | `entity_type ∈ {product,drug,org,target,indication}`；`canonical`+`aliases`；`status ∈ {active,pending,merged,rejected}`；`seen_count`；`merged_into_id` |
| `entity_watchlist` | 同上 | `(user_id, entity_id)` 用户关注；FK → `app_user` / `entity_lexicon` |

唯一约束：`UNIQUE(entity_type, canonical)`。

### 3.2 既有表新增列

**`news`**（`models/news.py` + `db/schema.py` `_ensure_entity_and_news_columns`）

| 列 | 类型 | 含义 |
|----|------|------|
| `products` | JSONB `[]` | canonical 产品列表 |
| `drugs` | JSONB `[]` | canonical 成分 |
| `orgs` | JSONB `[]` | canonical 机构 |
| `targets` | JSONB `[]` | canonical 靶点 |
| `indications` | JSONB `[]` | canonical 适应症 |
| `entity_raw` | JSONB nullable | NER 原始输出快照 |
| `story_type` | VARCHAR(32) | `clinical\|regulatory\|deal\|financing\|pipeline\|conference\|safety\|other` |

**`event`**

| 列 | 类型 | 含义 |
|----|------|------|
| `products` / `orgs` / `story_types` | JSONB | 成员汇总 |
| `status` | VARCHAR(16) | 默认 `active` |
| `ci_risk_score` | float | 情报风险分 [0,1] |
| `burst_prob` | float nullable | 报道爆发概率（预留，趋势模型未默认 fit） |
| `score_components` | JSONB | 可解释拆解 |

**`llm_profile`**

| 列 | 默认 | 含义 |
|----|------|------|
| `entity_api_key` | 可回填对话 key | 实体槽密钥（加密同其他 key） |
| `entity_base_url` | 回填 `base_url` | 实体槽地址 |
| `entity_model` | `Qwen/Qwen3-8B` | 实体槽模型 |

启动：`ensure_schema()` → `create_all` + ALTER IF NOT EXISTS + `_seed_entity_lexicon()`（关键词公司/靶点 + YAML）。

测试清空（保留词典）：

```sql
TRUNCATE news, event RESTART IDENTITY CASCADE;
```

一次性脚本（可选）：`scripts/_migrate_entities_once.py`（需 `PYTHONPATH=drugintel2.0` 根）。

---

## 4. 新增 / 改动文件清单

### 4.1 新增（核心）

| 路径 | 职责 |
|------|------|
| `backend/src/models/entity_lexicon.py` | ORM：词典 + 关注表 |
| `backend/src/entities/normalize.py` | 预处理 + `AliasIndex` |
| `backend/src/entities/lexicon.py` | CRUD / merge / pending 升格(N=3) / 种子导入 / `normalize_and_feedback` |
| `backend/src/entities/extract.py` | NER 客户端；`extract_and_normalize_items` |
| `backend/src/clustering/streaming.py` | 自 `聚类算法/streaming_clusterer.py` 移植 |
| `backend/src/clustering/trend_predictor.py` | 爆发预测原型（未强制接入主路径） |
| `backend/src/scoring/ci_risk.py` | `stage_prior_pos` / `adjust_prior_with_signals` / `compute_ci_risk_score` |
| `config/entity_seed.yaml` | 礼来/Lilly、Wegovy 等高优别名 |
| `config/phase_pos_priors.yaml` | 阶段先验 + story_type 权重 |
| `frontend/.../EntityLexiconPanel.vue` | 设置 → 实体词典 |
| `frontend/src/views/Events.vue` | 事件簇列表 + 时间线抽屉 |
| `docs/CLUSTERING_MIGRATION.md` | 迁移说明 + 后续优化 |
| `docs/CI_SCORING_ROADMAP.md` | 评分边界 |
| `docs/ENTITY_CLUSTERING_CHANGELOG.md` | **本文** |

### 4.2 主要修改

| 路径 | 改了什么 |
|------|----------|
| `backend/src/models/news.py` / `event.py` / `llm_profile.py` / `__init__.py` | 字段与导出 |
| `backend/src/db/schema.py` | 列补齐、加密 entity key、种子词典 |
| `backend/src/core/config.py` | `EntityEnvConfig`；profile 读 entity_* |
| `backend/src/llm/profiles.py` | 创建/更新/公开字段含实体槽；`DEFAULT_ENTITY_MODEL` |
| `backend/src/api/schemas.py` | `LlmProfileWrite` entity 字段；`EntityCreate/Update/Merge/Watch` |
| `backend/src/api/app.py` | 新闻分面；事件详情；实体/关注 API；cluster/score；管线详情挂 `stage_prior` |
| `backend/src/processors/pipeline.py` | `_enrich_items`：摘要后 NER |
| `backend/src/db/crud/news.py` | `update_news_enrichment` 写实体字段 |
| `backend/src/clustering/service.py` | **替换**为 StreamingClusterer 落库 + `_aggregate_event_fields` |
| `frontend/.../SystemConfigPanel.vue` | 「实体抽取」槽 UI |
| `frontend/src/views/Settings.vue` | tab=`entities` |
| `frontend/src/views/NewsList.vue` / `NewsDetail.vue` | 分面、芯片、风险分侧栏 |
| `frontend/src/views/PipelineDetail.vue` | 阶段先验展示 |
| `frontend/src/api.js` / `router.js` / `nav.config.js` | API 与 `/events`、词典导航 |

### 4.3 刻意未改 / 保留

- 旧 `clustering/clusterer.py` 仍在仓库（代表新闻 `NewsPoint` 仍被 service 引用）；**主路径不再用 0.85/0.75 质心增量**。  
- 邮件告警 `Watchlist`（alerts）与 `entity_watchlist` **两套**：前者关键词订阅，后者词典实体关注。  
- 灰区二次 LLM、2B 微调、邮件监控报告：**未做**（见 CLUSTERING_MIGRATION P1–P3）。

---

## 5. 聚类不变量（改算法前必读）

实现：`backend/src/clustering/streaming.py` + `service.py`。

1. **产品冲突**：双方都有 product 且 `entity_match==0` → 禁止并入（新建簇）。  
2. **强实体**：`products` 或「少量成分」存在时走产品/成分匹配；`pmatch>=0.7` 可归入。  
3. **弱实体**（无产品/强成分或仅公司）：按 medoid 余弦  
   - `cos ≥ 0.90` → 归入  
   - `0.80 ≤ cos < 0.90` → 与簇内**全部成员**比，任一 `≥ 0.90` 才归入  
   - `cos < 0.80` → 新建  
4. **公司不是强并键**（避免「只有 Pfizer」泛合并）。  
5. 落库后刷新：`event.products/orgs/story_types/news_count/ci_risk_score/score_components/centroid`。

---

## 6. 实体归一化不变量

实现：`entities/normalize.py` + `lexicon.py`。

1. `preprocess`：NFKC、小写、去 ®™、压缩空白。  
2. 仅 **`status=active`** 参与强路径 canonical 映射；未命中 → 快照可留 raw 小写串 + `upsert_pending`。  
3. `seen_count >= 3` 且 pending → 自动 `active`。  
4. `merge(keep, drop)`：同 type；drop → `merged`，aliases 并入 keep。  
5. 种子：`filter_keyword` 中「公司」→ org、「靶点」→ target；再合并 `config/entity_seed.yaml`。

---

## 7. API 一览（本轮相关）

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/api/news` | 可匿名 | 新增 query：`story_type,product,org,target,indication,watched_only`；item 含实体字段 |
| GET | `/api/news/{id}` | 可匿名 | 含实体、`entity_raw`、`event{ci_risk_score,...}`、时间线 related |
| GET | `/api/events` | 可匿名 | 按 `ci_risk_score` 降序 |
| GET | `/api/events/{id}` | 可匿名 | `timeline[]` |
| POST | `/api/cluster/run` | admin | 跑 StreamingClusterer |
| POST | `/api/cluster/score` | admin | 重算事件风险分 |
| GET/POST/PATCH | `/api/entities`… | admin | 词典 CRUD |
| POST | `/api/entities/merge` | admin | body: `keep_id,drop_id` |
| POST | `/api/entities/import-keywords` | admin | 重新种子 |
| GET/POST/DELETE | `/api/entity-watchlist`… | login | 实体关注 |
| GET | `/api/pipeline/assets/{id}` | login | 响应增 `stage_prior` |
| LLM profile | create/update | admin | body 增 `entity_*` |

前端封装：`frontend/src/api.js`（`entities` / `eventDetail` / `clusterRun` / `entityWatchlist` 等）。

---

## 8. 前端路由与设置

| 路由 / Tab | 文件 |
|------------|------|
| `/news` | 分面筛选 + 芯片摘要 |
| `/news/:id` | 实体芯片跳转 query；侧栏风险分 |
| `/events` | 事件簇（挂在「情报流」侧栏） |
| `/settings?tab=system` | 模型含「实体抽取」 |
| `/settings?tab=entities` | 实体词典管理 |
| `/pipeline/:id` | 阶段先验 PoS 文案 |

---

## 9. 配置与环境变量

| 来源 | 键 / 文件 | 默认 |
|------|-----------|------|
| profile / env | `SILICONFLOW_ENTITY_MODEL` 等 | `Qwen/Qwen3-8B`；key/url 可回落对话槽 |
| `config/entity_seed.yaml` | 高优别名 | 礼来、Wegovy… |
| `config/phase_pos_priors.yaml` | `priors` + `story_type_weights` | 阶段先验与风险权重 |

`EntityEnvConfig.load()`：`backend/src/core/config.py`。

---

## 10. 评分公式（实现真值）

文件：`backend/src/scoring/ci_risk.py`。

**管线**：`stage_prior_pos(current_stage)` → 查 YAML；可选 `adjust_prior_with_signals(competition, safety_news, deal_news)`（±0.05～0.10 量级）。  
**事件**（无 burst 时）：

```text
ci_risk = 0.40*story_type_w + 0.35*volume + 0.25*entity
```

有 `burst_prob` 时改为 0.35/0.25/0.20/0.20。  
**禁止**在 UI/论文把该分数写成「临床上市成功率模型」。

---

## 11. 给后续 AI 的操作提示

1. **改聚类阈值**：只动 `streaming.py` 的 `COS_HIGH`/`COS_MID` 与 `service.py` 调用；同步更新本文 §5。  
2. **改 NER 字段**：同步 `extract.py` prompt、`news` 列、`update_news_enrichment`、前端芯片与 `/api/news` query。  
3. **接灰区 LLM**：在弱实体灰区分支调用对话槽；不要占用实体槽。  
4. **接 burst_prob**：用 `clustering/trend_predictor.py`，在 `_aggregate_event_fields` 写入后再算 `ci_risk_score`。  
5. **不要**把 `filter_keyword` 直接当 product 强并键；关键词只种子 org/target。  
6. 实验目录 `聚类算法/` 与生产可能漂移；**以 `backend/src/clustering/streaming.py` 为准**，改完可回拷 demo。

---

## 12. 验收清单（回归用）

- [ ] 设置可保存/测试实体槽；默认模型名含 Qwen3-8B  
- [ ] 「礼来」与「Lilly」经 aliases 归一为同一 org canonical  
- [ ] 新闻详情有五类实体芯片 + story_type；列表可按实体筛  
- [ ] Wegovy 与 CagriSema 不因共有 semaglutide 被强并（产品冲突）  
- [ ] 无产品新闻走余弦三档  
- [ ] `/events` 有风险分与时间线；管线详情有阶段先验 disclaimer  
- [ ] `TRUNCATE news,event` 后空库可再跑采集链路；词典仍在  

---

## 13. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-04-01 | 首迁落地：实体+StreamingClusterer+CI 评分+文档；本 CHANGELOG 供 AI 读取 |
