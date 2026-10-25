# -*- coding: utf-8 -*-
"""
最小闭环演示：用示例医药新闻跑通 融合相似度 + 自适应阈值 + medoid 在线聚类
嵌入走 SiliconFlow 在线 API（与 drugintel embedding 配置一致）。
"""
import time
import numpy as np

from embedder import SiliconFlowEmbeddingClient
from streaming_clusterer import Article, StreamingClusterer

# 1) 在线嵌入：默认 BAAI/bge-m3，密钥读 drugintel2.0/.env 或本目录 .env
client = SiliconFlowEmbeddingClient.from_env()
print(f"嵌入模型: {client._model} @ {client._base_url}")

# 2) 示例新闻（真实场景由爬虫+摘要+实体抽取产生），实体已归一化到标准名
now = time.time()
day = 24 * 3600
raw = [
    # (id, 摘要, 时间偏移天, 药物实体, 企业实体, 事件类型)
    ("n1", "辉瑞宣布其在研肺癌新药III期临床达到主要终点，无进展生存期显著延长", 0.1, {"drug_lung"}, {"pfizer"}, "clinical"),
    ("n2", "Pfizer的非小细胞肺癌候选药物三期试验成功，公司计划提交上市申请", 0.8, {"drug_lung"}, {"pfizer"}, "clinical"),
    ("n3", "辉瑞肺癌疗法三期数据积极，预计明年向监管机构申报审批", 2.0, {"drug_lung"}, {"pfizer"}, "clinical"),
    ("n4", "默沙东口服降糖药获FDA批准用于2型糖尿病治疗", 1.0, {"drug_dm"}, {"merck"}, "approval"),
    ("n5", "Merck的糖尿病新药通过美国监管审批，即将上市销售", 2.5, {"drug_dm"}, {"merck"}, "approval"),
    ("n6", "诺华宣布收购一家生物科技初创公司，强化基因治疗管线布局", 3.0, set(), {"novartis"}, "m&a"),
]

# 3) 向量化并构造 Article
texts = [r[1] for r in raw]
embs = client.encode(texts, normalize=True)
articles = [
    Article(aid, text, now - off * day, np.asarray(emb), drugs, orgs, etype)
    for (aid, text, off, drugs, orgs, etype), emb in zip(raw, embs)
]

# 4) 流式逐篇聚类
clu = StreamingClusterer()
for art in articles:
    before = len(clu.clusters)
    clu.ingest(art)
    action = "新建事件簇" if len(clu.clusters) > before else "归入已有簇"
    print(f"[{art.id}] {action} | 阈值 高={clu.threshold.theta_high:.3f} 低={clu.threshold.theta_low:.3f}")

# 5) 输出最终事件簇
print("\n===== 最终事件簇 =====")
for c in clu.clusters:
    print(f"\n事件簇 {c.id}（{c.status}，成员 {len(c.members)}）:")
    for m in c.members:
        print(f"   - {m.id}: {m.text}")
