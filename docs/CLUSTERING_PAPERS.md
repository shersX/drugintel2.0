# 流式聚类与医药竞争情报：论文阅读清单

| 项目 | 内容 |
|------|------|
| 文档用途 | 支撑 `聚类算法/` 算法优化与后续替换 `backend/src/clustering` |
| 文档版本 | V1.0 |
| 创建日期 | 2026-10-25 |
| 核心判断 | Single-pass 本身非创新（Papka & Allan 1998）；创新点在医药实体先验、自适应阈值、时间生命周期与领域事件定义的交叉带 |

---

## 0. 背景与目标

当前 DrugIntel 线上聚类接近经典 **Single-pass（质心 + 阈值 θ）**；`聚类算法/` 目录是算法实验场，已叠加实体加权、Otsu 双阈、多 medoid、时间衰减与归档。

优化目标：在医药竞争情报场景下，改进流式事件聚类（尤其是**长周期静默**导致的误归档 / 误新建），成熟后回迁 DrugIntel。

文献空白：几乎没有「以药物/管线事件为单位的流式聚类」标杆工作；医药侧多为分类、本体 NER、竞品测绘。

---

## 1. 阅读优先级（建议顺序）

| 优先级 | 论文 | 理由 |
|--------|------|------|
| P0 | Papka & Allan 1998 | 钉死 Single-pass 根基，写相关工作必备 |
| P0 | Saravanakumar et al. 2021 | 实体感知 + 学习决策替代固定阈值，最接近下一版方向 |
| P0 | Jiang et al. 2024 | 时间感知嵌入；直接回应「医药 30 天不够」 |
| P1 | Pharma News Categorization 2022 | 事件类型体系（clinical / approval / M&A…）可对齐 |
| P1 | SCStory 2023 | 流分布漂移下的持续适应 |
| P2 | TDT Pilot / 综述、流聚类评估综述 | 任务定义与评估指标 |

---

## 2. A 类：奠基 — TDT / Single-pass

| 论文 | 年份 | 要点 | 链接 |
|------|------|------|------|
| Ron Papka, James Allan. *On-Line New Event Detection using Single Pass Clustering* | 1998 | 严格在线、单遍、事件感知阈值模型 | [CiteSeer](http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.42.8942) |
| James Allan, Ron Papka, Victor Lavrenko. *On-line new event detection and tracking* | SIGIR 1998 | 新事件检测 + 事件跟踪 | [ACM DOI](https://doi.org/10.1145/290941.290954) · [DBLP](https://dblp.org/rec/conf/sigir/AllanPL98) |
| Allan et al. *Topic Detection and Tracking Pilot Study Final Report* | 1998 | 分割 / 新事件 / 跟踪三任务定义 | [PDF](https://www.cs.cmu.edu/~jgc/publication/Topic_Detection_Tracking_Pilot_DARPA_1998.pdf) |
| Marek Gajewski et al. *Topic Detection and Tracking: A Focused Survey and a New Variant* | 2014 | TDT 概念、术语与变体综述 | [PDF](https://www.wit.edu.pl/dokumenty/wydawnictwa_naukowe/informatyka-stosowana/2014-1/133_ZNWI-01-2014-gajewski-kacprzyk-zadrozny.pdf) |

**与本项目**：线上 `EventClusterer` / 质心增量属于这一支；相关工作应写清「非创新根基」，再强调领域增强。

---

## 3. B 类：流式新闻聚类（与 `streaming_clusterer.py` 最贴近）

| 论文 | 年份 | 与现状的关系 | 链接 |
|------|------|--------------|------|
| Kailash Karthik Saravanakumar et al. *Event-Driven News Stream Clustering using Entity-Aware Contextual Embeddings* | EACL 2021 | **强烈推荐**：稀疏+稠密、实体感知；用神经网络/学习模型做归入·新建决策，替代静态 θ | [ACL](https://aclanthology.org/2021.eacl-main.198/) · [PDF](https://aclanthology.org/2021.eacl-main.198.pdf) · [arXiv](https://arxiv.org/pdf/2101.11059) |
| Todor Staykovski et al. *Dense vs. Sparse Representations for News Stream Clustering* | 2019 | 稠密表示未必优于 TF-IDF；后被 2021 文挑战 | [PDF](https://ceur-ws.org/Vol-2342/paper6.pdf) |
| Hang Jiang et al. *Topic Detection and Tracking with Time-Aware Document Embeddings* | LREC 2024 | **强烈推荐**：时间尺度随事件类型变化（风暴短、电影长）→ 对应医药长静默 | [ACL PDF](https://aclanthology.org/2024.lrec-main.1416.pdf) · [arXiv HTML](https://arxiv.org/html/2112.06166v2) |
| Susik Yoon et al. *SCStory: Self-supervised and Continual Online Story Discovery* | 2023 | 故事指示性嵌入 + 持续学习；默认置信阈值 ≈ 0.5 | [arXiv](https://arxiv.org/abs/2312.03725) · [HTML](https://arxiv.org/html/2312.03725v1) |
| Joel Azzopardi, Christopher Staff. *Incremental Clustering of News Reports* | 2012 | 增量 k-means 变体，固定相似度阈值约 0.4 | [DOI](https://doi.org/10.3390/a5030364) |
| Nicola Stokes et al. *First Story Detection using a Composite Document Representation* | 2001 | 多表示融合相似度 + 单遍 FSD | [ACL](https://aclanthology.org/H01-1030.pdf) |
| Panagiotis Panagiotou et al. / News Monitor 框架（含 REL-EFSD） | 2022 | 实体与关系特征 + 分类器做 First Story Detection | [MDPI](https://www.mdpi.com/2306-5729/7/1/3) |

### 可直接借鉴的方向

1. **实体感知表示 / 多表示融合**：现有药物·机构·事件类型 Jaccard 可升级为可学习权重。
2. **事件类型相关的时间建模**：clinical / approval 长窗，safety 短窗；弱化或关闭强实体匹配时的时间衰减。
3. **学习决策替代手调 Otsu 灰区**：保留 Otsu 作无监督基线。

---

## 4. C 类：通用数据流聚类（理论背景）

| 论文 | 年份 | 要点 | 链接 |
|------|------|------|------|
| Jonathan A. Silva et al. *Data stream clustering: A survey* | ACM CSUR 2013 | 流聚类设计组件与实验方法综述 | [ACM](https://dl.acm.org/doi/10.1145/2522968.2522981) |
| Mohammed Ghesmoune et al. *State-of-the-art on clustering data streams* | 2016 | CluStream / DenStream 等在线摘要 + 离线成簇 | [DOI](https://doi.org/10.1186/s41044-016-0011-3) |
| Christian Nordahl et al. *On Evaluation of Data Stream Clustering Algorithms: A Survey* | IEEE Access 2025 | 评估方法、衰减窗、过期簇 | [DOI](https://doi.org/10.1109/access.2025.3596435) |

**注意**：CluStream / DenStream 面向数值流；新闻事件更常用 TDT / 单遍 + 文本表示。引用时区分「通用流挖掘」与「新闻事件流」。

---

## 5. D 类：医药竞争情报 / 医药新闻 NLP（领域侧）

| 论文 / 材料 | 年份 | 做什么 | 与事件流聚类的距离 | 链接 |
|-------------|------|--------|-------------------|------|
| *Automatic Pharma News Categorization* | 2022 | 23 类医药新闻分类（临床阶段、获批、M&A 等） | 分类 ≠ 事件聚类；**event_type 体系可借鉴** | [arXiv](https://arxiv.org/abs/2201.00688) · [HTML](https://ar5iv.labs.arxiv.org/html/2201.00688) |
| *Unleashing Competitive Intelligence: News Mining Analysis on Technology Trends and Digital Health…* | IEEE TEM 2023 | 新闻挖掘 + NER + 图关系做 CI 趋势 | 主题/关系网络，非流式事件簇 | [DOI](https://doi.org/10.1109/tem.2023.3326233) |
| *Identifying Early Warning Signals from News Using Network Community Detection* | AAAI 2022 | 寿险/健康：窗口内图社区 + 新颖性/传播性打分 | 批处理社区 ≠ 在线单遍；「信号」定义有用 | [DOI](https://doi.org/10.1609/aaai.v36i11.21503) |
| *Comparative study of LDA and Louvain… Pharma News* | 2020 | 医药新闻主题抽取对比 | 离线主题 | [DBS eSource](https://esource.dbs.ie/handle/10788/4214) |
| *LLM-Based Agents for Competitive Landscape Mapping in Drug Asset Due Diligence* | 2025 | 适应症竞品发现 Agent | 情报任务，非聚类 | [arXiv](https://arxiv.org/html/2508.16571v4) |
| *Hunt Globally: Wide Search AI Agents for Drug Asset Scouting…* | 2026 | 多语言资产侦察 CI | 同上 | [arXiv](https://arxiv.org/html/2602.15019v2) |
| SciBite. *Comprehensive competitive intelligence monitoring in real time*（产业用例） | — | 本体/同义词 NER 实时监控 | **实体归一化实践参考** | [PDF](https://scibite.com/wp-content/uploads/2024/10/SciBite-Use-Case_Comprehensive-Competitive-Intelligence_UC004v3.pdf) |

**领域空白**：缺少以药物/管线**事件**为单位的流式聚类标杆；产业侧多为监控 + 分类 + 本体检索。交叉带可作为毕业设计创新论述点。

---

## 6. 与当前实现的对照

| `聚类算法/` 已有机制 | 文献中更成熟的对应 |
|----------------------|-------------------|
| Single-pass + 阈值 | Papka & Allan 1998；现代多用学习决策（Saravanakumar 2021） |
| 药物 / 机构 Jaccard + 事件类型 | Entity-aware embeddings（2021） |
| 固定 τ（14 天）/ 归档 30 天 | Time-aware / 事件类型相关时间尺度（Jiang 2024） |
| Otsu 双阈 + 灰区规则 | 可作无监督基线；文献更偏学习决策 |
| 医药垂直场景 | 分类与 CI 监控文献多，**事件流聚类几乎空白** |

算法实验代码目录：仓库根目录旁的 `聚类算法/`（优化主场）。  
线上待替换模块：`backend/src/clustering/`。

---

## 7. 后续行动（建议）

- [ ] 精读 P0 三篇，整理 1 页「可迁移改动」对照表写入本目录或 `聚类算法/`
- [ ] 将归档窗口 / τ 改为按 `event_type` 配置（或强实体匹配时关闭衰减）
- [ ] 设计医药事件流小基准（样例 JSONL → 人工簇标签），用 B-Cubed 等指标评估
- [ ] 优化稳定后，替换 `backend/src/clustering/clusterer.py` 等实现

---

## 8. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1.0 | 2026-10-25 | 初版：按 TDT / 流式新闻 / 流挖掘 / 医药 CI 四类整理 |
