import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CN = ZoneInfo("Asia/Shanghai")
OUT_DIR = Path(__file__).resolve().parents[3] / "outjson"


def text(selector) -> str:
    if not selector:
        return ""
    return " ".join(selector[0].get_all_text().split())


def joined_text(nodes) -> str:
    parts = []
    for node in nodes:
        chunk = " ".join(node.get_all_text().split())
        if chunk:
            parts.append(chunk)
    return "\n".join(parts)


def canonicalize(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


class JsonSeen:
    """已见详情链接。读入旧的 JSON 列表，成功处理后再并入，不覆盖历史。"""

    def __init__(self, filename: str):
        self.path = OUT_DIR / filename
        self._urls: set[str] = set()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = []
            if isinstance(data, list):
                self._urls = {canonicalize(str(item)) for item in data if item}

    def __contains__(self, url: str) -> bool:
        return canonicalize(url) in self._urls

    def add(self, url: str) -> None:
        url = canonicalize(url)
        if not url or url in self._urls:
            return
        self._urls.add(url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(self._urls), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def et_to_beijing(raw: str, pattern: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        return ""
    tokens = cleaned.split()
    if tokens and tokens[-1] in {"ET", "EST", "EDT"}:
        cleaned = " ".join(tokens[:-1])
    try:
        moment = datetime.strptime(cleaned, pattern).replace(tzinfo=ET)
    except ValueError:
        return raw.strip()
    return moment.astimezone(CN).strftime("%Y-%m-%d %H:%M")


def quiet_item_logs(spider) -> None:
    """保留收尾统计，不打印单条新闻的完整字段。"""
    spider.logger.setLevel(logging.INFO)
