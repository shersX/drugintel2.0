# 情报评分与「成功概率」后续路线

> 表结构 / API / 文件清单见 [ENTITY_CLUSTERING_CHANGELOG.md](./ENTITY_CLUSTERING_CHANGELOG.md) §3–§10。

## 当前实现（已上线）

| 指标 | 挂载位置 | 含义 |
|------|----------|------|
| `stage_prior` / `adjusted_pos` | 管线资产详情 | 按阶段查公开量级先验，规则小幅修正 |
| `ci_risk_score` | 事件簇 / 新闻侧栏 | 情报关注度·风险，非上市成功率 |
| `burst_prob` | 字段已预留 | 报道爆发概率；序列足够后再 fit |

UI 必须展示 disclaimer：**非临床 LoA / 非 DT&SR**。

## 与产业产品的关系

- **Clarivate DT&SR / Evaluate LoA**：依赖十几年带结局的管线金标 + 里程碑特征。本仓库**没有**对等数据，故不做同款 ML。
- **可对标的是「信号层」**：实体标签、事件类型、关注列表、催化剂时间线——已在新闻/事件页落地子集。

## 建议迭代顺序

1. 跑通 NER + 聚类后，用真实新闻校准 `story_type_weights` 与 `ci_risk_score` 权重。
2. 填充分治疗领域的阶段先验表（引用 BIO/CMR 等公开报告年份）。
3. 打开 `EventTrendPredictor`，在成员 ≥ N 的事件上产出 `burst_prob`。
4. 若导师需要「预测」字样：统一称为 **「阶段先验成功概率（文献基准）」** 与 **「事件情报风险分」**，避免与 LoA 混淆。

详见 [CLUSTERING_MIGRATION.md](./CLUSTERING_MIGRATION.md)「后续优化方案」。
