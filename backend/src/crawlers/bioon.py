from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup

from .base import BaseCrawler, CrawlerConfig


class BioonCrawler(BaseCrawler):
    def __init__(self, config: Optional[CrawlerConfig] = None):
        if config is None:
            config = CrawlerConfig(
                name="bioon",
                base_url="https://news.bioon.com",
                timeout=30,
                max_retries=3,
                delay_between_requests=2.0,
            )
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "bioon"

    async def parse_list_page(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        articles = []

        article_elements = soup.select("div.article-list > div.article-item, ul.news-list > li.news-item")

        for element in article_elements:
            title_elem = element.select_one("h3.title, h2.title, a.news-title")
            link_elem = element.select_one("a")
            date_elem = element.select_one("span.date, span.time, .publish-time")
            summary_elem = element.select_one("p.summary, .desc, .abstract")

            if title_elem and link_elem:
                url = link_elem.get("href", "")
                if not url.startswith("http"):
                    url = self.config.base_url.rstrip("/") + "/" + url.lstrip("/")

                articles.append({
                    "title": title_elem.get_text(strip=True),
                    "url": url,
                    "published_at": self._parse_date(date_elem.get_text(strip=True) if date_elem else ""),
                    "summary": summary_elem.get_text(strip=True) if summary_elem else None,
                })

        return articles

    async def parse_detail_page(self, html: str, url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.select_one("h1.article-title, h1.news-title, .article-header h1")
        content_elem = soup.select_one("div.article-content, div.news-content, .article-body")
        author_elem = soup.select_one("span.author, .author-name, .news-author")
        date_elem = soup.select_one("span.publish-time, .publish-date, .article-date")
        source_elem = soup.select_one("span.source, .news-source")

        content = ""
        if content_elem:
            for p in content_elem.find_all("p"):
                text = p.get_text(strip=True)
                if text:
                    content += text + "\n\n"

        title = title_elem.get_text(strip=True) if title_elem else ""
        published_at = self._parse_date(date_elem.get_text(strip=True) if date_elem else "")

        return {
            "title": title,
            "content": content.strip(),
            "author": author_elem.get_text(strip=True) if author_elem else None,
            "published_at": published_at,
            "source": source_elem.get_text(strip=True) if source_elem else self.source_name,
            "url": url,
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        import re
        if not date_str:
            return None

        date_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        year_match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", date_str)
        if year_match:
            try:
                return datetime(
                    int(year_match.group(1)),
                    int(year_match.group(2)),
                    int(year_match.group(3)),
                )
            except ValueError:
                pass

        return None
