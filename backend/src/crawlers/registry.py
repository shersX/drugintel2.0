#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医药情报AI平台 - 爬虫注册表
统一管理所有新闻爬虫的配置和启动
"""

import asyncio
import logging
import random
from typing import List, Dict, Callable, Optional, Tuple, Type
from datetime import datetime
from backend.src.core.logger import get_logger
from scrapling.spiders import Spider

from backend.src.crawlers.bioon import BioonSpider
from backend.src.crawlers.globenewswire import GlobeNewswireSpider
from backend.src.crawlers.pharmacube import PharmcubeSpider
from backend.src.crawlers.prnewswire import PrNewswireSpider

logger = get_logger("crawler.registry")
MAX_RETRY_ATTEMPTS = 3
_LOG_LINE_LIMIT = 150
_LOG_CHAR_LIMIT = 8000


def format_crawler_error(exc: BaseException | str) -> str:
    """把常见运行环境错误翻成可读中文，便于监控展示。"""
    raw = str(exc)
    lower = raw.lower()
    if (
        "executable doesn't exist" in lower
        or "ms-playwright" in lower
        or ("chromium" in lower and "chrome.exe" in lower)
    ):
        return (
            "未找到 Playwright Chromium 浏览器。"
            "请在项目根目录执行：uv run playwright install chromium"
            f"（原始错误：{raw}）"
        )
    if isinstance(exc, BaseException):
        return f"{type(exc).__name__}: {raw}"
    return raw


class CrawlerBatch(dict):
    """爬虫结果字典，并带上各源失败原因与日志。"""

    def __init__(self):
        super().__init__()
        self.failures: Dict[str, str] = {}
        self.logs: Dict[str, str] = {}


class _KeyFilter(logging.Filter):
    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == self.key:
            return True
        try:
            return self.key in record.getMessage()
        except Exception:
            return False


def _asctime_shanghai(seconds: float | None = None):
    """日志时间统一按 Asia/Shanghai，避免 Docker 容器默认 UTC 导致差 8 小时。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Shanghai")
    if seconds is None:
        return datetime.now(tz).timetuple()
    return datetime.fromtimestamp(seconds, tz).timetuple()


class _LineCapture(logging.Handler):
    def __init__(self, lines: List[str]):
        super().__init__(level=logging.INFO)
        self.lines = lines
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
        )
        formatter.converter = _asctime_shanghai
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        if len(self.lines) >= _LOG_LINE_LIMIT:
            return
        try:
            self.lines.append(self.format(record))
        except Exception:
            return


def _capture_crawler_logs(crawler_key: str):
    lines: List[str] = []
    handler = _LineCapture(lines)
    handler.addFilter(_KeyFilter(crawler_key))
    loggers = [logging.getLogger(crawler_key), logging.getLogger("crawler.registry")]
    for item in loggers:
        item.addHandler(handler)

    def finish() -> str:
        for item in loggers:
            item.removeHandler(handler)
        text = "\n".join(lines).strip()
        return text[:_LOG_CHAR_LIMIT]

    finish.lines = lines
    return finish
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
]


def _pick_rotating_user_agent(last_user_agent: Optional[str] = None) -> str:
    """从池中选择 UA，尽量避免与上一次重复。"""
    if len(USER_AGENT_POOL) <= 1:
        return USER_AGENT_POOL[0]
    candidates = [ua for ua in USER_AGENT_POOL if ua != last_user_agent]
    return random.choice(candidates)


# 爬虫注册表：每个爬虫的配置
# kind=news 走新闻流水线；kind=pipeline 走管线视觉抽取，不进新闻批处理
CRAWLER_REGISTRY = {
    "bioon": {
        "name": "Bioon新闻",
        "kind": "news",
        "function": BioonSpider,
        "enabled": True,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 2,
    },
    "globenewswire": {
        "name": "GlobeNewswire新闻",
        "kind": "news",
        "function": GlobeNewswireSpider,
        "enabled": True,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 2,
    },
    "prnewswire": {
        "name": "PrNewswire新闻",
        "kind": "news",
        "function": PrNewswireSpider,
        "enabled": True,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 2,
    },
    "pharmcube": {
        "name": "医药魔方新闻",
        "kind": "news",
        "function": PharmcubeSpider,
        "enabled": False,
        "page_count": 1,
        "fetch_details": True,
        "concurrency": 2,
    },
    "simcere_pipeline": {
        "name": "先声药业管线",
        "kind": "pipeline",
        "function": None,
        "enabled": True,
        "page_count": 1,
        "fetch_details": False,
        "concurrency": 1,
    },
}


def news_crawler_keys() -> List[str]:
    return [k for k, v in CRAWLER_REGISTRY.items() if v.get("kind", "news") == "news"]


def pipeline_crawler_keys() -> List[str]:
    return [k for k, v in CRAWLER_REGISTRY.items() if v.get("kind") == "pipeline"]


class _StatsCapture(logging.Handler):
    """只收下 Scrapling 收尾统计，避免请求日志占满行数上限。"""

    def __init__(self, lines: List[str]):
        super().__init__(level=logging.INFO)
        self.lines = lines

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            return
        if "items_scraped" not in message:
            return
        if len(self.lines) >= _LOG_LINE_LIMIT:
            return
        self.lines.append(message)


async def _start_spider(spider_cls: Type[Spider], lines: List[str], **kwargs) -> List[Dict]:
    """在独立线程里调用 Spider.start()，避免占住当前事件循环。"""

    def _run() -> List[Dict]:
        spider = spider_cls(
            pages=kwargs["page_count"],
            fetch_details=kwargs["fetch_details"],
            concurrency=kwargs["concurrency"],
            user_agent=kwargs.get("user_agent"),
        )
        spider.logger.addHandler(_StatsCapture(lines))
        return list(spider.start().items)

    return await asyncio.to_thread(_run)

async def _run_crawler_with_retry(
    crawler_key: str,
    crawler_func: Callable,
    kwargs: Dict,
) -> Tuple[List[Dict], Optional[Exception], str]:
    """统一重试执行器：所有异常都重试，最多 3 次，并收下该爬虫日志。"""
    finish_logs = _capture_crawler_logs(crawler_key)
    last_exception: Optional[Exception] = None
    last_user_agent: Optional[str] = None
    data: List[Dict] = []
    try:
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
                result = await _start_spider(crawler_func, finish_logs.lines, **current_kwargs)
                if attempt > 1:
                    logger.info("爬虫 %s 在第 %s 次尝试成功", crawler_key, attempt)
                data = result or []
                last_exception = None
                break
            except Exception as exc:
                last_exception = exc
                data = []
                logger.error(
                    "爬虫 %s 第 %s/%s 次执行失败: %s",
                    crawler_key,
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    format_crawler_error(exc),
                )
                if attempt < MAX_RETRY_ATTEMPTS:
                    delay_seconds = 2 ** (attempt - 1)
                    logger.warning("爬虫 %s 将在 %s 秒后重试", crawler_key, delay_seconds)
                    await asyncio.sleep(delay_seconds)
    finally:
        log_text = finish_logs()
    return data, last_exception, log_text

async def run_all_crawlers(
    crawler_configs: Optional[Dict] = None,
    fetch_details: bool = True,
    page_count: Optional[int] = None,
    concurrency: Optional[int] = None,
    on_crawler_done: Optional[Callable] = None,
) -> CrawlerBatch:
    """
    并发运行所有启用的爬虫。

    on_crawler_done(name, *, items, error, log_text, done, total) 在每个源结束时回调。
    """
    if crawler_configs is None:
        try:
            from backend.src.crawlers.settings_store import merged_crawler_registry

            crawler_configs = merged_crawler_registry()
        except Exception:
            crawler_configs = CRAWLER_REGISTRY

    enabled_crawlers = {
        name: config
        for name, config in crawler_configs.items()
        if config.get("enabled", True)
        and config.get("kind", "news") == "news"
        and config.get("function") is not None
    }

    if not enabled_crawlers:
        logger.warning("没有启用的新闻爬虫")
        return CrawlerBatch()

    logger.info("%s", "=" * 80)
    logger.info("开始并发运行 %s 个爬虫", len(enabled_crawlers))
    logger.info("%s", "=" * 80)

    task_map: Dict[asyncio.Task, str] = {}
    for name, config in enabled_crawlers.items():
        crawler_func: Callable = config["function"]
        crawler_name = config.get("name", name)
        final_page_count = page_count if page_count is not None else config.get("page_count", 1)
        final_fetch_details = (
            config.get("fetch_details", fetch_details)
            if "fetch_details" in config
            else fetch_details
        )
        final_concurrency = (
            concurrency if concurrency is not None else config.get("concurrency", 5)
        )
        logger.info("配置爬虫: %s", crawler_name)
        logger.info("  - 页数: %s", final_page_count)
        logger.info("  - 抓取详情: %s", final_fetch_details)
        logger.info("  - 并发数: %s", final_concurrency)
        task_kwargs = {
            "page_count": final_page_count,
            "fetch_details": final_fetch_details,
            "concurrency": final_concurrency,
        }
        task = asyncio.create_task(
            _run_crawler_with_retry(
                crawler_key=name,
                crawler_func=crawler_func,
                kwargs=task_kwargs,
            )
        )
        task_map[task] = name

    logger.info("%s", "=" * 80)
    logger.info("开始并发执行所有爬虫...")
    logger.info("%s", "=" * 80)

    start_time = datetime.now()
    batch = CrawlerBatch()
    failed_crawlers: Dict[str, str] = {}
    total_news = 0
    total = len(task_map)
    done_count = 0
    # 注意：as_completed() 产出的不是原始 Task，不能做 task_map 反查；用 wait 保留 Task 身份
    pending: set[asyncio.Task] = set(task_map.keys())

    while pending:
        done_set, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done_set:
            name = task_map[task]
            done_count += 1
            try:
                result = task.result()
            except Exception as exc:
                result = exc

            if isinstance(result, Exception):
                error_msg = format_crawler_error(result)
                logger.error("爬虫 %s 执行失败: %s", name, error_msg)
                failed_crawlers[name] = error_msg
                batch[name] = []
                batch.failures[name] = failed_crawlers[name]
                log_text = ""
                items: List = []
                err: Optional[str] = error_msg
            else:
                crawler_data, error, log_text = result
                if log_text:
                    batch.logs[name] = log_text
                if error is not None:
                    error_msg = format_crawler_error(error)
                    failed_crawlers[name] = error_msg
                    logger.error(
                        "爬虫 %s 重试 %s 次后仍失败: %s",
                        name,
                        MAX_RETRY_ATTEMPTS,
                        error_msg,
                    )
                    batch[name] = []
                    batch.failures[name] = failed_crawlers[name]
                    items = []
                    err = error_msg
                else:
                    news_count = len(crawler_data) if crawler_data else 0
                    total_news += news_count
                    logger.info("爬虫 %s 完成，获取 %s 条新闻", name, news_count)
                    batch[name] = crawler_data or []
                    items = list(batch[name])
                    err = None

            if on_crawler_done is not None:
                try:
                    on_crawler_done(
                        name,
                        items=items,
                        error=err,
                        log_text=log_text or batch.logs.get(name) or "",
                        done=done_count,
                        total=total,
                    )
                except Exception:
                    logger.exception("爬虫完成回调失败 key=%s", name)

    end_time = datetime.now()
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

    return batch

