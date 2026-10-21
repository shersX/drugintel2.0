import logging

from scrapling.fetchers import AsyncStealthySession
from scrapling.spiders import Request, Response, Spider

from backend.src.crawlers.scrapling_support import (
    JsonSeen,
    canonicalize,
    fragment_html,
    html_to_text,
    quiet_item_logs,
    seen_for_crawler,
    text,
)

SEEN_FILE = "pharmcube_url.json"


def list_url(page: int) -> str:
    return f"https://bydrug.pharmcube.com/news?searchKey=&page={page}"


class PharmcubeSpider(Spider):
    """医药魔方新闻。页码来自注册表的 page_count，某一页没有新链接时停止。"""

    name = "pharmcube"
    allowed_domains = {"bydrug.pharmcube.com"}
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
        self.seen = seen or seen_for_crawler("pharmcube")
        super().__init__(**kwargs)

    def configure_sessions(self, manager) -> None:
        quiet_item_logs(self)
        session_kwargs = {"headless": True, "network_idle": True, "timeout": 60_000}
        if self.user_agent:
            session_kwargs["useragent"] = self.user_agent
        manager.add("browser", AsyncStealthySession(**session_kwargs))

    async def start_requests(self):
        yield Request(
            list_url(1),
            sid="browser",
            callback=self.parse,
            meta={"page": 1},
            wait_selector="div.item-news",
        )

    async def parse(self, response: Response):
        page = int(response.meta.get("page", 1))
        new_count = 0
        skip_count = 0
        for card in response.css("div.item-news"):
            title = text(card.css("a.news-title"))
            source = text(card.css('a[href*="/news/summary/source/"]'))
            raw_href = card.css("a.news-title::attr(href)").get("").strip()
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
                sid="browser",
                meta={"title": title, "source": source, "seen_url": href},
                wait_selector="div.news-detail-page div.desc span.text",
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
                list_url(page + 1),
                callback=self.parse,
                sid="browser",
                meta={"page": page + 1},
                wait_selector="div.item-news",
            )

    async def parse_detail(self, response: Response):
        # 有效稿：raw 落库成功后再 mark_seen_urls
        content_html = fragment_html(response.css("div.news-detail-page div.content"))
        yield self._item(
            response.meta.get("title", ""),
            response.meta.get("source", ""),
            response.url,
            text(response.css("div.news-detail-page div.desc span.text")),
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
            "crawler": "pharmcube",
        }
