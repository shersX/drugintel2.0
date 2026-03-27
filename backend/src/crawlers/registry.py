from typing import AsyncIterator, Optional

from ..core.logging import get_logger
from .base import BaseCrawler, CrawlerConfig, NewsItem
from .bioon import BioonCrawler

logger = get_logger(__name__)


class CrawlerRegistry:
    _instance: Optional["CrawlerRegistry"] = None
    _crawlers: dict[str, type[BaseCrawler]] = {}
    _configs: dict[str, CrawlerConfig] = {}

    def __new__(cls) -> "CrawlerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.register("bioon", BioonCrawler, CrawlerConfig(
            name="bioon",
            base_url="https://news.bioon.com",
        ))

    @classmethod
    def register(cls, name: str, crawler_class: type[BaseCrawler], config: Optional[CrawlerConfig] = None) -> None:
        if not issubclass(crawler_class, BaseCrawler):
            raise TypeError(f"{crawler_class} must be a subclass of BaseCrawler")
        cls._crawlers[name] = crawler_class
        if config:
            cls._configs[name] = config
        logger.info(f"Registered crawler: {name}")

    @classmethod
    def unregister(cls, name: str) -> None:
        cls._crawlers.pop(name, None)
        cls._configs.pop(name, None)
        logger.info(f"Unregistered crawler: {name}")

    @classmethod
    def get_crawler(cls, name: str) -> BaseCrawler:
        if name not in cls._crawlers:
            raise KeyError(f"Crawler '{name}' not found. Available crawlers: {list(cls._crawlers.keys())}")
        crawler_class = cls._crawlers[name]
        config = cls._configs.get(name)
        return crawler_class(config)

    @classmethod
    def list_crawlers(cls) -> list[str]:
        return list(cls._crawlers.keys())

    @classmethod
    def get_config(cls, name: str) -> Optional[CrawlerConfig]:
        return cls._configs.get(name)

    @classmethod
    async def crawl_all(
        cls,
        max_pages: int = 5,
        max_items_per_crawler: Optional[int] = None,
        crawler_names: Optional[list[str]] = None,
    ) -> AsyncIterator[tuple[str, NewsItem]]:
        names = crawler_names or cls.list_crawlers()
        for name in names:
            try:
                crawler = cls.get_crawler(name)
                logger.info(f"Starting crawl for {name}")
                async for item in crawler.crawl(max_pages=max_pages, max_items=max_items_per_crawler):
                    yield name, item
                await crawler.close()
                logger.info(f"Completed crawl for {name}")
            except Exception as e:
                logger.error(f"Failed to crawl {name}: {e}")

    @classmethod
    async def crawl_single(
        cls,
        name: str,
        max_pages: int = 5,
        max_items: Optional[int] = None,
    ) -> AsyncIterator[NewsItem]:
        crawler = cls.get_crawler(name)
        try:
            async for item in crawler.crawl(max_pages=max_pages, max_items=max_items):
                yield item
        finally:
            await crawler.close()


def get_registry() -> CrawlerRegistry:
    return CrawlerRegistry()
