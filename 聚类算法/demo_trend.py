# -*- coding: utf-8 -*-
"""
端到端演示：流式聚类 → 事件趋势预测
生成若干“增长型 / 衰减型”事件，验证模型能否预测下一时间窗的报道量与爆发概率。
"""
import copy
import time
import numpy as np

from embedder import SiliconFlowEmbeddingClient
from streaming_clusterer import Article, StreamingClusterer
from trend_predictor import EventTrendPredictor, DAY

# 在线嵌入：与 drugintel / demo.py 相同配置
client = SiliconFlowEmbeddingClient.from_env()
print(f"嵌入模型: {client._model} @ {client._base_url}")

# 1) 生成事件：每个事件一种药物、一种报道量时间模式
orgs = ["辉瑞", "默沙东", "诺华", "罗氏", "阿斯利康", "礼来",
        "BMS", "吉利德", "赛诺菲", "安进", "渤健", "再生元"]
patterns = [
    [1, 1, 2, 3, 4, 5],   # 增长型
    [1, 2, 4, 5, 3, 2],   # 先爆发后衰减
    [4, 3, 2, 1, 1, 1],   # 衰减型
    [1, 2, 3, 2, 1, 1],   # 小峰型
]

now = time.time()
raw = []
aid = 0
for i in range(12):
    drug = f"drug_{i:02d}"
    org = orgs[i % len(orgs)]
    etype = "clinical" if i % 2 == 0 else "approval"
    pat = patterns[i % len(patterns)]
    for b, cnt in enumerate(pat):
        for k in range(cnt):
            aid += 1
            txt = f"{org}的{drug}相关{etype}事件，第{b}天进展报道{k}"
            ts = now - (len(pat) - b) * DAY
            raw.append((f"a{aid}", txt, ts, drug, org, etype))

# 2) 向量化并按时间顺序流式聚类
embs = client.encode([r[1] for r in raw], normalize=True)
arts = [Article(i, t, ts, np.asarray(e), {drug}, {org.lower()}, etype)
        for (i, t, ts, drug, org, etype), e in zip(raw, embs)]

clu = StreamingClusterer()
for a in sorted(arts, key=lambda x: x.timestamp):
    clu.ingest(a)
print(f"聚类得到 {len(clu.clusters)} 个事件簇\n")
for c in clu.clusters:
    d, o, _ = c.entity_sets()
    print(f"  簇{c.id:2d} 药物={sorted(d)} 企业={sorted(o)}")

# 3) 训练趋势预测器
pred = EventTrendPredictor()
pred.fit(clu.clusters)

# 4) 验证：截断到“最后一个真实桶之前”，预测最后一个桶的报道量
print("===== 趋势预测验证 =====")
errs = []
for c in clu.clusters:
    counts, _ = pred._series(c)
    nonzero = np.where(counts > 0)[0]
    if len(nonzero) < 3:
        continue
    last_b = int(nonzero[-1])
    truth = counts[last_b]

    cutoff = c.created_at + last_b * pred.bin
    trunc = copy.deepcopy(c)
    trunc.members = [m for m in trunc.members if m.timestamp < cutoff]
    trunc.updated_at = max(m.timestamp for m in trunc.members)
    trunc.update_medoids()

    out = pred.predict_cluster(trunc)
    errs.append(abs(out["next_count"] - truth))
    print(f"簇{c.id:2d} 成员{len(c.members):2d} | 预测下一桶={out['next_count']:.1f} "
          f"真实={truth:.0f} | 爆发概率={out['burst_prob']:.2f}")

print(f"\n平均绝对误差 MAE = {np.mean(errs):.2f}（桶报道量）")

# 5) 早期爆发预警：只给事件前 2 个桶，预测下一桶是否爆发
print("\n===== 早期爆发预警（仅前2桶）=====")
for c in clu.clusters:
    counts, _ = pred._series(c)
    if len(counts) < 3:
        continue
    cutoff = c.created_at + 2 * pred.bin
    trunc = copy.deepcopy(c)
    trunc.members = [m for m in trunc.members if m.timestamp < cutoff]
    if not trunc.members:
        continue
    trunc.updated_at = max(m.timestamp for m in trunc.members)
    trunc.update_medoids()

    out = pred.predict_cluster(trunc)
    truth = counts[2]
    print(f"簇{c.id:2d} 早期={int(counts[0])+int(counts[1]):2d}篇 | "
          f"预测下一桶={out['next_count']:.1f} 真实={truth:.0f} | "
          f"爆发概率={out['burst_prob']:.2f}")
