# -*- coding: utf-8 -*-
"""
完整管线：采集 → (LLM摘要+实体) → 在线向量化 → 流式聚类 → 输出 JSON
用法：
  无LLM，本地JSONL：python run_pipeline.py --source jsonl:sample_news.jsonl
  RSS+本地LLM：      python run_pipeline.py --source rss:https://... --llm
嵌入默认 SiliconFlow（与 drugintel .env 一致），可用 --embed-model 覆盖模型名。
"""
import argparse
import json
import numpy as np

from collector import fetch_rss, load_jsonl
from embedder import SiliconFlowEmbeddingClient
from enricher import Enricher
from streaming_clusterer import Article, StreamingClusterer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="rss:URL 或 jsonl:PATH")
    ap.add_argument("--llm", action="store_true", help="启用 LLM 摘要/实体抽取")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--embed-model", default="", help="覆盖 SILICONFLOW_EMBEDDING_MODEL，默认 BAAI/bge-m3")
    ap.add_argument("--output", default="clusters.json")
    args = ap.parse_args()

    kind, _, loc = args.source.partition(":")
    raw = fetch_rss(loc) if kind == "rss" else load_jsonl(loc)
    print(f"采集到 {len(raw)} 条原始新闻")

    enricher = Enricher(args.base_url, "ollama", args.model) if args.llm else None

    records = []
    for d in raw:
        if enricher:
            e = enricher.enrich(d["title"], d["content"])
        else:
            # 无 LLM 兜底：直接用标题+正文，不做实体抽取
            e = {"summary": (d["title"] + "。" + d["content"]).strip("。"),
                 "drugs": [], "orgs": [], "event_type": "other"}
        records.append({**d, **e})

    client = SiliconFlowEmbeddingClient.from_env()
    if args.embed_model:
        client._model = args.embed_model
    print(f"嵌入模型: {client._model}")
    embs = client.encode([r["summary"] for r in records], normalize=True)

    clu = StreamingClusterer()
    for r, e in zip(records, embs):
        clu.ingest(Article(
            r["id"], r["summary"], r["published"], np.asarray(e),
            set(r["drugs"]), set(r["orgs"]), r["event_type"],
        ))

    out = [
        {"cluster_id": c.id, "status": c.status, "size": len(c.members),
         "members": [{"id": m.id, "text": m.text} for m in c.members]}
        for c in clu.clusters
    ]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"得到 {len(clu.clusters)} 个事件簇，结果已写入 {args.output}")


if __name__ == "__main__":
    main()
#（注：内容由AI生成）
