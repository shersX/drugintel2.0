#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from typing import Dict, List

from backend.src.crawlers.registry import CRAWLER_REGISTRY, run_all_crawlers


DEFAULT_PAGE_COUNT = 2
DEFAULT_FETCH_DETAILS = True
DEFAULT_CONCURRENCY = 3


async def run_registry_crawlers() -> Dict[str, List[Dict]]:
    """通过注册表统一启动全部已启用爬虫。"""
    return await run_all_crawlers(
        crawler_configs=CRAWLER_REGISTRY,
        page_count=DEFAULT_PAGE_COUNT,
        fetch_details=DEFAULT_FETCH_DETAILS,
        concurrency=DEFAULT_CONCURRENCY,
    )


def main() -> None:
    results = asyncio.run(run_registry_crawlers())

if __name__ == "__main__":
    main()
