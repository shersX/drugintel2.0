#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过注册表统一执行真实联网爬取测试。

测试目标：
1) 清空去重文件，避免增量逻辑导致 0 条新增。
2) 通过 registry.run_all_crawlers 统一拉起 3 个爬虫。
3) 统一参数：page_count=2, fetch_details=True, concurrency=3。
4) 断言 3 个爬虫均返回非空结果，且包含 title/detail_url。
5) 首轮全量抓取；未通过校验的源在后续轮次仅重试该子集（最多共 3 轮校验）。
6) 校验通过后写入 outjson/results.json。
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.crawlers.registry import CRAWLER_REGISTRY, run_all_crawlers


EXPECTED_CRAWLERS = {"bioon", "globenewswire", "prnewswire"}
DEDUP_FILES = [
    PROJECT_ROOT / "outjson" / "BioonNews_url.json",
    PROJECT_ROOT / "outjson" / "Globenewswire_url.json",
    PROJECT_ROOT / "outjson" / "Prnewswire_url.json",
]
RESULTS_JSON = PROJECT_ROOT / "outjson" / "results.json"


def reset_dedup_files() -> None:
    """测试前重置去重文件，保证本次测试可抓到新增内容。"""
    for file_path in DEDUP_FILES:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("[]", encoding="utf-8")


CRAWL_KWARGS = {
    "page_count": 2,
    "fetch_details": True,
    "concurrency": 3,
}


def failing_crawlers(results: Dict[str, List[Dict]]) -> Set[str]:
    """返回未满足校验的预期爬虫 key 集合（空集表示全部通过）。"""
    failed: Set[str] = set()
    for crawler_name in EXPECTED_CRAWLERS:
        items = results.get(crawler_name)
        if items is None:
            failed.add(crawler_name)
            continue
        if not isinstance(items, list):
            failed.add(crawler_name)
            continue
        if len(items) == 0:
            failed.add(crawler_name)
            continue
        bad = False
        for item in items:
            if not item.get("title"):
                bad = True
                break
            detail_url = item.get("detail_url")
            if not isinstance(detail_url, str) or not detail_url.strip():
                bad = True
                break
        if bad:
            failed.add(crawler_name)
    return failed


def save_results_to_json(results: Dict[str, List[Dict]]) -> None:
    """将本次抓取结果写入 outjson/results.json。"""
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_results(results: Dict[str, List[Dict]]) -> None:
    """校验统一爬取结果。"""
    failed = failing_crawlers(results)
    assert not failed, f"以下爬虫未通过校验: {sorted(failed)}"


async def run_live_registry_test() -> Dict[str, List[Dict]]:
    """执行真实联网测试并返回结果。"""
    reset_dedup_files()

    start = time.perf_counter()
    results = await run_all_crawlers(
        crawler_configs=CRAWLER_REGISTRY,
        **CRAWL_KWARGS,
    )

    for attempt in range(1, 4):
        failed = failing_crawlers(results)
        if not failed:
            elapsed = time.perf_counter() - start
            validate_results(results)
            counts = {name: len(results.get(name, [])) for name in sorted(EXPECTED_CRAWLERS)}
            total = sum(counts.values())
            print("注册表统一爬取测试通过")
            print(f"轮次: {attempt}/3")
            print(f"耗时: {elapsed:.2f}s")
            print(f"抓取条数: {json.dumps(counts, ensure_ascii=False)}")
            print(f"总条数: {total}")
            save_results_to_json(results)
            print(f"已保存至: {RESULTS_JSON}")
            return results

        counts = {name: len(results.get(name, [])) for name in sorted(EXPECTED_CRAWLERS)}
        print(f"第{attempt}轮校验未通过，未通过源: {sorted(failed)}")
        print(f"当前各源条数: {json.dumps(counts, ensure_ascii=False)}")

        if attempt >= 3:
            break

        await asyncio.sleep(2 * attempt)
        subset = {name: CRAWLER_REGISTRY[name] for name in sorted(failed)}
        print(f"仅重试: {sorted(failed)}")
        partial = await run_all_crawlers(crawler_configs=subset, **CRAWL_KWARGS)
        for name in failed:
            results[name] = partial.get(name, results.get(name, []))

    still = failing_crawlers(results)
    raise AssertionError(f"连续3轮后仍有未通过校验的源: {sorted(still)}")


def test_registry_live_crawlers() -> None:
    """
    可被 pytest 直接执行的测试函数。
    注意：该测试会访问真实网站，受网络与目标站稳定性影响。
    """
    asyncio.run(run_live_registry_test())


if __name__ == "__main__":
    asyncio.run(run_live_registry_test())
