import logging

from scrapling.fetchers import FetcherSession
from scrapling.spiders import Request, Response, Spider

from backend.src.crawlers.scrapling_support import (
    JsonSeen,
    canonicalize,
    et_to_beijing,
    joined_text,
    quiet_item_logs,
    text,
)

LIST_URL = "https://www.globenewswire.com/en/news/heathcare/load/more?page={page}&pageSize=10"
SEEN_FILE = "Globenewswire_url.json"
TIME_PATTERN = "%B %d, %Y %H:%M"


class GlobeNewswireSpider(Spider):
    """GlobeNewswire Healthcare 新闻。"""

    name = "globenewswire"
    allowed_domains = {"globenewswire.com"}
    concurrent_requests = 1
    download_delay = 1
    logging_level = logging.INFO

    def __init__(
        self,
        pages: int = 1,
        fetch_details: bool = True,
        concurrency: int = 1,
        user_agent: str | None = None,
        seen: JsonSeen | None = None,
        **kwargs,
    ):
        self.pages = max(1, pages)
        self.fetch_details = fetch_details
        self.concurrent_requests = max(1, concurrency)
        self.user_agent = user_agent
        self.seen = seen or JsonSeen(SEEN_FILE)
        super().__init__(**kwargs)

    def configure_sessions(self, manager) -> None:
        quiet_item_logs(self)
        headers = {"User-Agent": self.user_agent} if self.user_agent else None
        manager.add("http", FetcherSession(headers=headers))

    async def start_requests(self):
        yield Request(LIST_URL.format(page=1), sid="http", callback=self.parse, meta={"page": 1})

    async def parse(self, response: Response):
        page = int(response.meta.get("page", 1))
        new_count = 0
        for card in response.css("li.row"):
            title = text(card.css("div.mainLink a"))
            source = text(card.css("a.sourceLink"))
            raw_href = card.css("div.mainLink a::attr(href)").get("").strip()
            if not raw_href:
                continue
            href = canonicalize(response.urljoin(raw_href))
            if not href:
                continue
            if href in self.seen:
                self.logger.info("已跳过 原因=已抓取过 地址=%s", href)
                continue
            new_count += 1
            if not self.fetch_details:
                yield self._item(title, source, href, "", "")
                continue
            yield response.follow(
                href,
                callback=self.parse_detail,
                sid="http",
                meta={"title": title, "source": source, "seen_url": href},
            )
        if new_count and page < self.pages:
            yield response.follow(
                LIST_URL.format(page=page + 1),
                callback=self.parse,
                sid="http",
                meta={"page": page + 1},
            )

    async def parse_detail(self, response: Response):
        body = response.css("div.main-body-container")
        full_text = joined_text(body[0].css("p")) if body else ""
        if not full_text:
            full_text = text(body)
        seen_url = response.meta.get("seen_url") or response.url
        self.seen.add(seen_url)
        yield self._item(
            text(response.css("h1.article-headline")) or response.meta.get("title", ""),
            text(response.css("span.article-source a")) or response.meta.get("source", ""),
            response.url,
            et_to_beijing(text(response.css("span.article-published")), TIME_PATTERN),
            full_text,
        )

    @staticmethod
    def _item(title: str, source: str, detail_url: str, publish_time: str, full_text: str) -> dict:
        return {
            "title": title,
            "source": source,
            "detail_url": canonicalize(detail_url),
            "publish_time": publish_time,
            "full_text": full_text,
            "crawler": "globenewswire",
        }
