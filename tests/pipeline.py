"""
数据处理流水线联调脚本（tests/pipeline.py）。

默认：读取 outjson/results.json，跑完整处理链（含摘要/向量/入库）。
环境变量：
  PIPELINE_PERSIST=0     不入库
  PIPELINE_SKIP_LLM=1    跳过摘要与向量（仅测过滤/相关性/去重）
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.processors.pipeline import run_processing_pipeline


def main() -> None:
    results_path = PROJECT_ROOT / "outjson" / "results.json"
    if not results_path.exists():
        print(f"缺少输入文件: {results_path}，请先运行 python main.py")
        sys.exit(1)

    with open(results_path, "r", encoding="utf-8") as f:
        crawler_results = json.load(f)

    persist = os.getenv("PIPELINE_PERSIST", "1").strip() not in {"0", "false", "False"}
    skip_llm = os.getenv("PIPELINE_SKIP_LLM", "0").strip() in {"1", "true", "True"}

    outcome = asyncio.run(
        run_processing_pipeline(
            crawler_results,
            persist=persist,
            skip_summary=skip_llm,
            skip_embedding=skip_llm,
        )
    )
    stats = outcome["stats"]
    print("流水线统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    out_path = PROJECT_ROOT / "outjson" / "results_processed.json"
    # 向量很大，落盘时去掉 embedding 明细
    slim = []
    for item in outcome["items"]:
        row = {k: v for k, v in item.items() if k != "embedding"}
        row["embedding_dim"] = len(item["embedding"]) if item.get("embedding") else 0
        slim.append(row)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    print(f"已写入: {out_path}")


if __name__ == "__main__":
    main()
