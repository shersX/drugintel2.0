# -*- coding: utf-8 -*-
"""
真实数据聚类（LLM 增强版）：
读取 drugintel2.0/outjson/results.json，
用 DeepSeek 抽取摘要+药物/企业实体，用 bge-m3 对摘要做嵌入，
再做流式聚类。验证实体抽取能否纠正模板化新闻稿的误并。
"""
import json
import os
import time
from datetime import datetime
import numpy as np
from dotenv import load_dotenv

from embedder import SiliconFlowEmbeddingClient
from enricher import Enricher
from streaming_clusterer import Article, StreamingClusterer

SRC = r"E:\desktop\theis\drugintel2.0\outjson\results.json"
ENV_MODEL = r"E:\desktop\theis\drugintel2.0\.env"
ENV_KEY = r"E:\desktop\theis\聚类算法\.env"


def parse_ts(s: str) -> float:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M").timestamp()
    except Exception:
        return time.time()


def main():
    load_dotenv(ENV_MODEL)          # model / base_url
    load_dotenv(ENV_KEY, override=True)  # 真正的 API key
    data = json.load(open(SRC, encoding="utf-8"))

    records = []
    for src, items in data.items():
        for x in items:
            title = x.get("title", "")
            body = x.get("full_text", "") or ""
            records.append({
                "id": x.get("detail_url", title),
                "title": title,
                "text": (title + "。" + body[:1500]).strip("。"),
                "ts": parse_ts(x.get("publish_time", "")),
                "src": src,
            })
    print(f"真实新闻共 {len(records)} 条")

    # 1) LLM 抽取摘要 + 实体
    en = Enricher(base_url=os.getenv("SILICONFLOW_BASE_URL"),
                  api_key=os.getenv("SILICONFLOW_API_KEY"),
                  model=os.getenv("SILICONFLOW_MODEL"))
    for i, r in enumerate(records):
        try:
            e = en.enrich(r["title"], r["text"])
        except Exception as ex:
            print(f"  enrich失败 {i}: {ex}")
            e = {"summary": r["title"], "drugs": [], "orgs": [],
                 "event_type": "other"}
        r["summary"] = e["summary"] or r["title"]
        r["drugs"] = set(e["drugs"])
        r["orgs"] = set(e["orgs"])
        r["event_type"] = e["event_type"]
    print("实体抽取完成")

    # 缓存 enrich 结果，供调试复用
    cache = [{"id": r["id"], "title": r["title"], "summary": r["summary"],
              "ts": r["ts"], "src": r["src"], "event_type": r["event_type"],
              "drugs": list(r["drugs"]), "orgs": list(r["orgs"])}
             for r in records]
    json.dump(cache, open("real_records_cache.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 2) 对摘要做嵌入
    client = SiliconFlowEmbeddingClient.from_env()
    embs = client.encode([r["summary"] for r in records], normalize=True)

    # 3) 流式聚类
    clu = StreamingClusterer()
    order = sorted(range(len(records)), key=lambda i: records[i]["ts"])
    for i in order:
        r, e = records[i], embs[i]
        clu.ingest(Article(r["id"], r["summary"], r["ts"], np.asarray(e),
                           r["drugs"], r["orgs"], r["event_type"]))

    print(f"得到 {len(clu.clusters)} 个事件簇\n")
    multi = 0
    for c in clu.clusters:
        if len(c.members) > 1:
            multi += 1
            print(f"--- 簇{c.id}（{len(c.members)} 条）---")
            for m in c.members:
                rec = next(r for r in records if r["id"] == m.id)
                print(f"    [{rec['src']:12s}] {rec['title'][:78]}")
    print(f"\n含多篇报道的事件簇 {multi} 个")


if __name__ == "__main__":
    main()
