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
    text,
)

SEEN_FILE = "Prnewswire_url.json"
TIME_PATTERN = "%b %d, %Y, %H:%M"


def list_url(page: int) -> str:
    return (
        "https://www.prnewswire.com/news-releases/health-latest-news/"
        f"health-latest-news-list/?page={page}&pagesize=25"
    )


class PrNewswireSpider(Spider):
    """PR Newswire 健康新闻。"""

    name = "prnewswire"
    allowed_domains = {"prnewswire.com"}
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
        yield Request(list_url(1), sid="http", callback=self.parse, meta={"page": 1})

    async def parse(self, response: Response):
        page = int(response.meta.get("page", 1))
        new_count = 0
        for card in response.css("div.row.newsCards"):
            title = " ".join(
                " ".join(str(part).split())
                for part in card.css("h3::text").getall()
                if str(part).strip()
            )
            raw_href = card.css("a.newsreleaseconsolidatelink::attr(href)").get("").strip()
            if not raw_href:
                continue
            href = canonicalize(response.urljoin(raw_href))
            if not href:
                continue
            if href in self.seen:
                self.logger.debug("已跳过 原因=已抓取过 地址=%s", href)
                continue
            new_count += 1
            if not self.fetch_details:
                yield self._item(title, "", href, "", "")
                continue
            yield response.follow(
                href,
                callback=self.parse_detail,
                sid="http",
                meta={"title": title, "seen_url": href},
            )
        if new_count and page < self.pages:
            yield response.follow(
                list_url(page + 1),
                callback=self.parse,
                sid="http",
                meta={"page": page + 1},
            )

    async def parse_detail(self, response: Response):
        body = response.css("section.release-body")
        content_html = fragment_html(body) if body else ""
        # 有效稿：raw 落库成功后再 mark_seen_urls
        yield self._item(
            text(response.css("h1")) or response.meta.get("title", ""),
            text(response.css("div.swaping-class-left strong")),
            response.url,
            et_to_beijing(text(response.css("div.swaping-class-left p.mb-no")), TIME_PATTERN),
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
            "crawler": "prnewswire",
        }
