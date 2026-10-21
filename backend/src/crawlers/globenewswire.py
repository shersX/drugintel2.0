import logging

from scrapling.fetchers import FetcherSession
from scrapling.spiders import Request, Response, Spider

from backend.src.crawlers.scrapling_support import (
    JsonSeen,
    canonicalize,
    et_to_beijing,
    fragment_html,
    html_to_text,
    quiet_item_logs,
    seen_for_crawler,
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
        self.seen = seen or seen_for_crawler("globenewswire")
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
        skip_count = 0
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
                skip_count += 1
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
        if skip_count:
            self.logger.info(
                "列表页增量跳过 page=%s 已见=%s 待抓详情=%s",
                page,
                skip_count,
                new_count,
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
        content_html = fragment_html(body) if body else ""
        # 有效稿：raw 落库成功后再 mark_seen_urls
        yield self._item(
            text(response.css("h1.article-headline")) or response.meta.get("title", ""),
            text(response.css("span.article-source a")) or response.meta.get("source", ""),
            response.url,
            et_to_beijing(text(response.css("span.article-published")), TIME_PATTERN),
            html_to_text(content_html),
            content_html,
        )

    @staticmethod
    def _item(
        title: str,
        source: str,
        detail_url: str,
        publish_time: str,
        full_text: str,
        content_html: str = "",
    ) -> dict:
        return {
            "title": title,
            "source": source,
            "detail_url": canonicalize(detail_url),
            "publish_time": publish_time,
            "full_text": full_text,
            "content_html": content_html or None,
            "crawler": "globenewswire",
        }
