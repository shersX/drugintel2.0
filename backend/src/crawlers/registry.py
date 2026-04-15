#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医药情报AI平台 - 爬虫注册表
统一管理所有新闻爬虫的配置和启动
"""

import asyncio
import random
from typing import List, Dict, Callable, Optional, Tuple
from datetime import datetime
from backend.src.core.logging import get_logger

# 导入所有爬虫模块
from backend.src.crawlers.bioon import crawl_bioon_news_async
from backend.src.crawlers.globenewswire import crawl_globenewswire_async
from backend.src.crawlers.prnewswire import crawl_prnewswire_async

logger = get_logger("crawler.registry")
MAX_RETRY_ATTEMPTS = 3
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:137.0) Gecko/20100101 Firefox/137.0",
]


def _pick_rotating_user_agent(last_user_agent: Optional[str] = None) -> str:
    """从池中选择 UA，尽量避免与上一次重复。"""
    if len(USER_AGENT_POOL) <= 1:
        return USER_AGENT_POOL[0]
    candidates = [ua for ua in USER_AGENT_POOL if ua != last_user_agent]
    return random.choice(candidates)


# 爬虫注册表：每个爬虫的配置
CRAWLER_REGISTRY = {
    "bioon": {
        "name": "Bioon新闻",
        "function": crawl_bioon_news_async,
        "enabled": True,  # 是否启用该爬虫
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 3,
    },
    "globenewswire": {
        "name": "GlobeNewswire新闻",
        "function": crawl_globenewswire_async,
        "enabled": True,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 3,
    },
    "prnewswire":{
        "name": "PrNewswire新闻",
        "function": crawl_prnewswire_async,
        "enabled": True,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 3,
    }
}


async def run_all_crawlers(
    crawler_configs: Optional[Dict] = None,
    fetch_details: bool = True,
    page_count: Optional[int] = None,
    concurrency: Optional[int] = None,
) -> Dict[str, List[Dict]]:
    """
    并发运行所有启用的爬虫
    
    Args:
        crawler_configs: 自定义爬虫配置，如果为None则使用默认配置
        fetch_details: 全局设置是否抓取详情（可被单个爬虫配置覆盖）
        page_count: 全局设置页数（可被单个爬虫配置覆盖）
        concurrency: 全局设置并发数（可被单个爬虫配置覆盖）
    
    Returns:
        Dict[str, List[Dict]]: 每个爬虫名称对应的新闻列表
    """
    if crawler_configs is None:
        crawler_configs = CRAWLER_REGISTRY
    
    # 筛选启用的爬虫
    enabled_crawlers = {
        name: config
        for name, config in crawler_configs.items()
        if config.get("enabled", True)
    }
    
    if not enabled_crawlers:
        logger.warning("没有启用的爬虫")
        return {}

    async def _run_crawler_with_retry(
        crawler_key: str,
        crawler_func: Callable,
        kwargs: Dict,
    ) -> Tuple[List[Dict], Optional[Exception]]:
        """
        统一重试执行器：所有异常都重试，最多 3 次。
        """
        last_exception: Optional[Exception] = None
        last_user_agent: Optional[str] = None
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                current_kwargs = dict(kwargs)
                current_user_agent = _pick_rotating_user_agent(last_user_agent)
                current_kwargs["user_agent"] = current_user_agent
                last_user_agent = current_user_agent
                if attempt > 1:
                    logger.warning(
                        "爬虫 %s 开始第 %s/%s 次尝试",
                        crawler_key,
                        attempt,
                        MAX_RETRY_ATTEMPTS,
                    )
                logger.info("爬虫 %s 使用 User-Agent: %s", crawler_key, current_user_agent)
                result = await crawler_func(**current_kwargs)
                if attempt > 1:
                    logger.info("爬虫 %s 在第 %s 次尝试成功", crawler_key, attempt)
                return result or [], None
            except Exception as exc:
                last_exception = exc
                logger.error(
                    "爬虫 %s 第 %s/%s 次执行失败: %s",
                    crawler_key,
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    str(exc),
                )
                logger.error("异常类型: %s", type(exc).__name__)
                if attempt < MAX_RETRY_ATTEMPTS:
                    delay_seconds = 2 ** (attempt - 1)
                    logger.warning("爬虫 %s 将在 %s 秒后重试", crawler_key, delay_seconds)
                    await asyncio.sleep(delay_seconds)
        return [], last_exception
    
    logger.info("%s", "=" * 80)
    logger.info("开始并发运行 %s 个爬虫", len(enabled_crawlers))
    logger.info("%s", "=" * 80)
    
    # 构建任务列表
    tasks = []
    crawler_names = []
    
    for name, config in enabled_crawlers.items():
        crawler_func: Callable = config["function"]
        crawler_name = config.get("name", name)
        
        # 使用全局设置或单个爬虫配置
        final_page_count = page_count if page_count is not None else config.get("page_count", 1)
        final_fetch_details = config.get("fetch_details", fetch_details) if "fetch_details" in config else fetch_details
        final_concurrency = concurrency if concurrency is not None else config.get("concurrency", 5)
        
        logger.info("配置爬虫: %s", crawler_name)
        logger.info("  - 页数: %s", final_page_count)
        logger.info("  - 抓取详情: %s", final_fetch_details)
        logger.info("  - 并发数: %s", final_concurrency)
        
        task_kwargs = {
            "page_count": final_page_count,
            "fetch_details": final_fetch_details,
            "concurrency": final_concurrency,
        }
        # 创建包含重试策略的任务
        task = _run_crawler_with_retry(
            crawler_key=name,
            crawler_func=crawler_func,
            kwargs=task_kwargs,
        )
        tasks.append(task)
        crawler_names.append(name)
    
    # 并发运行所有爬虫
    logger.info("%s", "=" * 80)
    logger.info("开始并发执行所有爬虫...")
    logger.info("%s", "=" * 80)
    
    start_time = datetime.now()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = datetime.now()
    
    # 处理结果
    crawler_results = {}
    failed_crawlers: Dict[str, str] = {}
    total_news = 0
    
    for name, result in zip(crawler_names, results):
        if isinstance(result, Exception):
            error_msg = str(result)
            logger.error("爬虫 %s 执行失败: %s", name, error_msg)
            logger.error("异常类型: %s", type(result).__name__)
            failed_crawlers[name] = f"{type(result).__name__}: {error_msg}"
            crawler_results[name] = []
        else:
            crawler_data, error = result
            if error is not None:
                error_msg = str(error)
                failed_crawlers[name] = f"{type(error).__name__}: {error_msg}"
                logger.error(
                    "爬虫 %s 重试 %s 次后仍失败",
                    name,
                    MAX_RETRY_ATTEMPTS,
                )
                crawler_results[name] = []
            else:
                news_count = len(crawler_data) if crawler_data else 0
                total_news += news_count
                logger.info("爬虫 %s 完成，获取 %s 条新闻", name, news_count)
                crawler_results[name] = crawler_data
    
    elapsed = (end_time - start_time).total_seconds()
    logger.info("%s", "=" * 80)
    if failed_crawlers:
        logger.warning(
            "爬虫执行结束（部分失败） 成功=%s 失败=%s",
            len(enabled_crawlers) - len(failed_crawlers),
            len(failed_crawlers),
        )
        logger.warning("失败爬虫列表: %s", ", ".join(sorted(failed_crawlers.keys())))
        for crawler_name, failure in failed_crawlers.items():
            logger.warning("失败详情 %s: %s", crawler_name, failure)
    else:
        logger.info("所有爬虫执行完成")
    logger.info("总耗时: %.2f 秒", elapsed)
    logger.info("总计获取: %s 条新闻", total_news)
    logger.info("%s", "=" * 80)

    
    return crawler_results

