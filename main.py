#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""统一入口：采集 → 处理流水线 → 入库 → 事件聚类。"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, List

from backend.src.clustering.service import run_clustering
from backend.src.crawlers.registry import CRAWLER_REGISTRY, run_all_crawlers
from backend.src.processors.pipeline import run_processing_pipeline

DEFAULT_PAGE_COUNT = 2
DEFAULT_FETCH_DETAILS = True
DEFAULT_CONCURRENCY = 2
PROJECT_ROOT = Path(__file__).resolve().parent


async def run_registry_crawlers() -> Dict[str, List[Dict]]:
    return await run_all_crawlers(
        crawler_configs=CRAWLER_REGISTRY,
        page_count=DEFAULT_PAGE_COUNT,
        fetch_details=DEFAULT_FETCH_DETAILS,
        concurrency=DEFAULT_CONCURRENCY,
    )


async def async_main(
    *,
    crawl: bool,
    process: bool,
    persist: bool,
    cluster: bool,
) -> None:
    out_dir = PROJECT_ROOT / "outjson"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"

    if crawl:
        results = await run_registry_crawlers()
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"爬虫结果已写入 {results_path}")
        for name, items in results.items():
            print(f"  {name}: {len(items or [])}")
    else:
        results = None
        if process:
            if not results_path.exists():
                raise SystemExit(f"未找到 {results_path}，请先 --crawl 或去掉 --no-crawl")
            with open(results_path, "r", encoding="utf-8") as f:
                results = json.load(f)

    if process:
        assert results is not None
        outcome = await run_processing_pipeline(results, persist=persist)
        print("处理流水线 stats:", outcome["stats"])

    if cluster:
        stats = run_clustering()
        print("事件聚类 stats:", stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="DrugIntel 采集 / 处理 / 聚类入口")
    parser.add_argument("--no-crawl", action="store_true", help="跳过爬虫，仅处理已有 results.json")
    parser.add_argument("--no-process", action="store_true", help="跳过处理流水线")
    parser.add_argument("--no-persist", action="store_true", help="处理但不入库")
    parser.add_argument(
        "--no-cluster",
        action="store_true",
        help="跳过事件聚类（默认在流程末尾对未归属新闻聚类）",
    )
    parser.add_argument(
        "--cluster-only",
        action="store_true",
        help="只跑事件聚类（不爬、不处理）",
    )
    args = parser.parse_args()

    if args.cluster_only:
        asyncio.run(
            async_main(crawl=False, process=False, persist=False, cluster=True)
        )
        return

    asyncio.run(
        async_main(
            crawl=not args.no_crawl,
            process=not args.no_process,
            persist=not args.no_persist,
            cluster=not args.no_cluster,
        )
    )


if __name__ == "__main__":
    main()
