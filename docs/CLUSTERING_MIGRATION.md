# 聚类 / 实体 / 情报评分迁移说明

本文记录已落地的迁移范围，以及**后续优化**（产业对标裁剪项）。实现对应计划：实体词典 + StreamingClusterer + CI 风险分。

> **给 AI / 后续开发**：完整「改了哪些文件、表、API、不变量」见  
> **[ENTITY_CLUSTERING_CHANGELOG.md](./ENTITY_CLUSTERING_CHANGELOG.md)**（优先读这一份再改代码）。

## 已落地

1. **实体抽取独立槽位**：`llm_profile.entity_*`，默认 `Qwen/Qwen3-8B`；设置页「实体抽取」。
2. **`entity_lexicon` + alias 归一化**：产品 / 成分 / 机构 / 靶点 / 适应症；礼来↔Lilly 等靠 aliases。
3. **流水线**：摘要后 NER → normalize → 写 `news.products/drugs/orgs/targets/indications/story_type`。
4. **StreamingClusterer**：产品优先；弱实体余弦 0.90 / 0.80 全员复核；公司不当强并键。
5. **新闻分面**：story_type / product / org / target / indication / 关注列表。
6. **事件簇页** `/events`：风险分排序 + 成员时间线。
7. **Phase F 评分**：
   - 管线详情 `stage_prior`（文献量级阶段先验，**非临床 LoA**）
   - 事件 `ci_risk_score`（story_type + 量 + 实体完整度）

测试期可清空新闻/事件：

```sql
TRUNCATE news, event RESTART IDENTITY CASCADE;
```

词典与关键词、用户配置保留。启动时会种子导入 `filter_keyword` 公司/靶点 + `config/entity_seed.yaml`。

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/entity_seed.yaml` | 高优中英别名种子 |
| `config/phase_pos_priors.yaml` | 阶段先验 + story_type 权重 |

## 后续优化方案

按优先级排列；**不挡当前论文主线**（产品级流式聚类 + 弱实体三档）。

### P1 — 聚类质量

- **灰区二次 LLM（same_event）**：仅当 `0.80 ≤ cos < 0.90` 且全员复核未过时，调用对话模型判是否同事件；控制成本（限流 / 仅代表新闻对比）。
- **Medoid 持久化**：现用成员重建 medoid；可把 medoid news_id 写入 `event` 加速增量。
- **归档策略可视化**：按 `story_type` lifecycle 归档后，前端标记 archived 簇。

### P2 — 实体与本体

- **靶点/适应症 Roll-Up**：智慧芽式向上卷积（如 GLP-1 家族）；需简易父子表或外部 ontology 映射。
- **与管线 `drugs` 表对齐**：canonical ↔ `pipeline_asset` / `Drug` 外键，新闻芯片跳管线详情。
- **人工合并工作台**：列表勾选两实体一键 merge；冲突审计日志。
- **NER 小模型微调（可选）**：Qwen2B/3B 领域微调降低 8B 调用成本；需标注集。

### P3 — 监控与推送（对标智慧芽监控）

- 邮件 / 站内日报：按 watchlist + story_type 聚合。
- 微信/Webhook：超出首迁范围，可作为产品化项。
- 检索式监控差集（列表新增/减少），依赖稳定实体 ID。

### P4 — 成功概率深化（仍非 Cortellis DT&SR）

- 接入公开阶段转移率表（按治疗领域分层）更新 `phase_pos_priors.yaml`。
- 竞争密度 / 近期 safety 新闻自动修正（API 已留 `adjust_prior_with_signals` 钩子）。
- **`burst_prob`**：接入 `clustering/trend_predictor.py`，事件序列足够时训练；与 `ci_risk_score` 并列。
- **禁止**：在无结局金标时宣称「优于行业 LoA」；论文写清「CI 应用层 / 阶段先验」。

### P5 — 产业深链（大工程）

- 临床试验 / 专利 / 交易结构化库与新闻双向链（Cortellis / Synapse 核心能力）。
- BioWorld 式人工深度稿、情感分析、Agentic CI 工作流。

## 论文叙事建议

- **方法贡献**：产品级实体优先的流式聚类 + 弱实体余弦三档（可复现规则）。
- **应用层**：簇上情报风险分 + 管线阶段先验展示，说明聚类输出可支撑 CI 决策信号。
- **边界**：不做临床 LoA SOTA；不做全量医药情报平台复制。

## 相关代码与文档

- **变更说明书（AI）**：[ENTITY_CLUSTERING_CHANGELOG.md](./ENTITY_CLUSTERING_CHANGELOG.md)
- **评分边界**：[CI_SCORING_ROADMAP.md](./CI_SCORING_ROADMAP.md)
- **文献**：[CLUSTERING_PAPERS.md](./CLUSTERING_PAPERS.md)
- 代码：`backend/src/clustering/streaming.py`、`service.py`；`backend/src/entities/`；`backend/src/scoring/ci_risk.py`
