#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫基类（异步）
提供通用能力：visited URL 读写、增量过滤、并发详情抓取
"""

import asyncio
import json
import os
from typing import Dict, List, Set, Callable, Awaitable, Optional
from backend.src.core.logging import get_logger


class BaseAsyncCrawler:
    """异步新闻爬虫基类"""

    @staticmethod
    def load_visited_urls(visited_file: str) -> Set[str]:
        """加载已抓取 URL 集合（文件不存在或损坏时返回空集合）"""
        if not os.path.exists(visited_file):
            return set()
        try:
            with open(visited_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(x) for x in data if x}
            return set()
        except Exception:
            return set()

    @staticmethod
    def filter_new_items(
        raw_news_list: List[Dict],
        visited_urls: Set[str],
        url_key: str = "detail_url",
    ) -> List[Dict]:
        """按 URL 过滤增量新闻"""
        return [news for news in raw_news_list if news.get(url_key) not in visited_urls]

    @staticmethod
    def save_visited_urls_union(
        visited_file: str,
        previous_urls: Set[str],
        raw_news_list: List[Dict],
        url_key: str = "detail_url",
    ) -> None:
        """将历史 visited 与本次列表页 URL 合并后写回"""
        os.makedirs(os.path.dirname(visited_file) or ".", exist_ok=True)
        current_urls = {news.get(url_key) for news in raw_news_list if news.get(url_key)}
        merged_urls = sorted(previous_urls.union(current_urls))
        with open(visited_file, "w", encoding="utf-8") as f:
            json.dump(merged_urls, f, ensure_ascii=False, indent=2)

    async def run_fetch_details(
        self,
        news_list: List[Dict],
        fetch_detail_func: Callable[[Dict], Awaitable[None]],
        concurrency: int,
        crawler_label: str,
        logger_name: Optional[str] = None,
    ) -> List[Dict]:
        """通用并发详情抓取执行器"""
        if not news_list:
            return news_list

        resolved_logger_name = logger_name or f"crawler.{crawler_label.lower()}"
        logger = get_logger(resolved_logger_name)
        total = len(news_list)
        limit = max(1, concurrency)
        sem = asyncio.Semaphore(limit)
        failed_count = 0
        logger.info(
            "详情抓取开始 总数=%s 并发=%s",
            total,
            limit,
        )

        async def _wrapped(idx: int, item: Dict):
            nonlocal failed_count
            async with sem:
                try:
                    await fetch_detail_func(item)
                except Exception as e:
                    failed_count += 1
                    logger.warning("%s抓取第 %s 条新闻详情失败: %s", crawler_label, idx, e)

        tasks = [
            asyncio.create_task(_wrapped(idx, news))
            for idx, news in enumerate(news_list, 1)
        ]
        await asyncio.gather(*tasks)
        logger.info(
            "详情抓取完成 总数=%s 失败=%s",
            total,
            failed_count,
        )
        return news_list
