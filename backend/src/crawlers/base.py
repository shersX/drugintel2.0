from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional

import aiohttp
from aiohttp import ClientTimeout

from ..core.logging import get_logger

logger = get_logger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@dataclass
class CrawlerConfig:
    name: str
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    delay_between_requests: float = 1.0
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class NewsItem:
    title: str
    content: str
    url: str
    published_at: Optional[datetime] = None
    source: str = ""
    author: Optional[str] = None
    summary: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source": self.source,
            "author": self.author,
            "summary": self.summary,
            "raw_data": self.raw_data,
        }


class BaseCrawler(ABC):
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._user_agent_index = 0

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    async def parse_list_page(self, html: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def parse_detail_page(self, html: str, url: str) -> dict[str, Any]:
        pass

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENTS[self._user_agent_index % len(USER_AGENTS)],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        headers.update(self.config.headers)
        return headers

    def _rotate_user_agent(self) -> None:
        self._user_agent_index = (self._user_agent_index + 1) % len(USER_AGENTS)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return self._session

    async def _fetch_with_retry(self, url: str, session: Optional[aiohttp.ClientSession] = None) -> str:
        if session is None:
            session = await self._get_session()

        headers = self._get_headers()
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries):
            try:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    self._rotate_user_agent()
                    return await response.text()
            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(
                    f"Crawl attempt {attempt + 1}/{self.config.max_retries} failed for {url}: {e}"
                )
                if attempt < self.config.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        raise last_error or Exception(f"Failed to fetch {url} after {self.config.max_retries} attempts")

    async def _delay(self) -> None:
        import asyncio
        await asyncio.sleep(self.config.delay_between_requests)

    async def crawl_list_page(self, page: int = 1) -> list[str]:
        url = self._build_list_url(page)
        logger.info(f"Crawling list page: {url}")
        html = await self._fetch_with_retry(url)
        parsed = await self.parse_list_page(html)
        return [self._normalize_url(item.get("url", "")) for item in parsed if item.get("url")]

    async def crawl_detail_page(self, url: str) -> Optional[NewsItem]:
        try:
            logger.info(f"Crawling detail page: {url}")
            html = await self._fetch_with_retry(url)
            data = await self.parse_detail_page(html, url)
            return NewsItem(
                title=data.get("title", ""),
                content=data.get("content", ""),
                url=url,
                published_at=data.get("published_at"),
                source=self.source_name,
                author=data.get("author"),
                summary=data.get("summary"),
                raw_data=data,
            )
        except Exception as e:
            logger.error(f"Failed to crawl detail page {url}: {e}")
            return None

    async def crawl(self, max_pages: int = 5, max_items: Optional[int] = None) -> AsyncIterator[NewsItem]:
        collected = 0
        for page in range(1, max_pages + 1):
            if max_items and collected >= max_items:
                break

            detail_urls = await self.crawl_list_page(page)
            for url in detail_urls:
                if max_items and collected >= max_items:
                    break

                item = await self.crawl_detail_page(url)
                if item:
                    await self._delay()
                    yield item
                    collected += 1

            await self._delay()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_list_url(self, page: int) -> str:
        return f"{self.config.base_url}?page={page}"

    def _normalize_url(self, url: str) -> str:
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.config.base_url.rstrip("/") + url
        return url
