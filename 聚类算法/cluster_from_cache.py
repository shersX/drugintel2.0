# -*- coding: utf-8 -*-
"""从 enrich 缓存直接聚类，用于快速验证规则改动。"""
import json
import numpy as np
from embedder import SiliconFlowEmbeddingClient
from streaming_clusterer import Article, StreamingClusterer

cache = json.load(open("real_records_cache.json", encoding="utf-8"))
client = SiliconFlowEmbeddingClient.from_env()
embs = client.encode([r["summary"] for r in cache], normalize=True)

clu = StreamingClusterer()
order = sorted(range(len(cache)), key=lambda i: cache[i]["ts"])
for i in order:
    r, e = cache[i], embs[i]
    clu.ingest(Article(r["id"], r["summary"], r["ts"], np.asarray(e),
                       set(r["drugs"]), set(r["orgs"]), r["event_type"]))

print(f"得到 {len(clu.clusters)} 个事件簇\n")
for c in clu.clusters:
    if len(c.members) > 1:
        print(f"--- 簇{c.id}（{len(c.members)} 条）---")
        for m in c.members:
            rec = next(r for r in cache if r["id"] == m.id)
            print(f"    [{rec['src']:12s}] {rec['title'][:78]}")
