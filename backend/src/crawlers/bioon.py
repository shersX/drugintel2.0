import logging
import re

from scrapling.fetchers import FetcherSession
from scrapling.spiders import Request, Response, Spider

from bs4 import BeautifulSoup

from backend.src.crawlers.scrapling_support import (
    JsonSeen,
    canonicalize,
    html_to_text,
    quiet_item_logs,
    sanitize_html,
    seen_for_crawler,
    text,
)

SOURCE_RE = re.compile(
    r"^来源:(?P<source>.*?)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2})$"
)
SEEN_FILE = "BioonNews_url.json"


def list_url(page: int) -> str:
    return f"https://news.bioon.com/{page}.html"


class BioonSpider(Spider):
    """生物谷新闻。作者为「网络」或正文为空的条目不返回。"""

    name = "bioon"
    allowed_domains = {"bioon.com"}
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
        self.seen = seen or seen_for_crawler("bioon")
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
        skip_count = 0
        for card in response.css("div.item"):
            title = text(card.css("h2 a"))
            raw_href = card.css("h2 a::attr(href)").get("").strip()
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
                yield self._item(title, "", href, "", "")
                continue
            yield response.follow(
                href,
                callback=self.parse_detail,
                sid="http",
                meta={"title": title, "seen_url": href},
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
                sid="http",
                meta={"page": page + 1},
            )

    async def parse_detail(self, response: Response):
        source_raw = text(response.css("p.source_text")).replace("：", ":")
        matched = SOURCE_RE.match(source_raw)
        source = matched.group("source").strip() if matched else ""
        published_at = f"{matched.group('date')} {matched.group('time')}" if matched else ""
        body = response.css('div[style*="303a4e"]')
        content_html = ""
        if body:
            soup = BeautifulSoup(str(body[0].html_content), "html.parser")
            for node in soup.find_all("p"):
                style = (node.get("style") or "").lower()
                if "text-align" in style and "center" in style:
                    node.decompose()
            content_html = sanitize_html(str(soup))
        full_text = html_to_text(content_html)
        title = text(response.css("h1")) or response.meta.get("title", "")
        seen_url = response.meta.get("seen_url") or response.url
        if source == "网络":
            # 无效稿不入库，仍标记已见以免反复抓取
            self.seen.add(seen_url)
            self.logger.debug("已跳过 原因=作者为网络 标题=%s 地址=%s", title, seen_url)
            return
        if not full_text.strip():
            self.seen.add(seen_url)
            self.logger.debug("已跳过 原因=正文为空 标题=%s 地址=%s", title, seen_url)
            return
        # 有效稿：raw 落库成功后再 mark_seen_urls，避免「已见未入库」丢稿
        yield self._item(title, source, response.url, published_at, full_text, content_html)

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
            "crawler": "bioon",
        }
