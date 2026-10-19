import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, NavigableString, Tag

ET = ZoneInfo("America/New_York")
CN = ZoneInfo("Asia/Shanghai")
OUT_DIR = Path(__file__).resolve().parents[3] / "outjson"

_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "ul",
        "ol",
        "li",
        "h2",
        "h3",
        "h4",
        "b",
        "strong",
        "i",
        "em",
        "a",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "sup",
        "sub",
    }
)
_DROP_TAGS = frozenset({"script", "style", "iframe", "noscript", "svg", "form", "button"})
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


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


def looks_like_html(value: Any) -> bool:
    text_value = str(value or "")
    return bool(_TAG_RE.search(text_value))


def _node_html(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    content = getattr(node, "html_content", None)
    if content is not None:
        return str(content)
    return str(node)


def fragment_html(nodes_or_root: Any) -> str:
    """把 Scrapling 节点（或节点列表）序列化为消毒后的 HTML 片段。"""
    if nodes_or_root is None:
        return ""
    if isinstance(nodes_or_root, (list, tuple)):
        chunks = [_node_html(node) for node in nodes_or_root]
        return sanitize_html("".join(chunk for chunk in chunks if chunk))
    # SelectorList-like: first element is the root container
    if hasattr(nodes_or_root, "__iter__") and not hasattr(nodes_or_root, "html_content"):
        items = list(nodes_or_root)
        if not items:
            return ""
        return sanitize_html(_node_html(items[0]))
    return sanitize_html(_node_html(nodes_or_root))


def sanitize_html(html: str) -> str:
    """白名单清洗正文 HTML，去掉脚本/样式与危险属性。"""
    raw = (html or "").strip()
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in list(soup.find_all(True)):
        name = (tag.name or "").lower()
        if name in _DROP_TAGS:
            tag.decompose()
            continue
        if name not in _ALLOWED_TAGS:
            tag.unwrap()
            continue
        attrs = dict(tag.attrs)
        tag.attrs = {}
        if name == "a":
            href = str(attrs.get("href") or "").strip()
            if href.lower().startswith(("http://", "https://")):
                tag["href"] = href
                tag["rel"] = "noopener noreferrer"
                tag["target"] = "_blank"
            else:
                tag.unwrap()
    # 去掉空块
    for tag in list(soup.find_all(["p", "li", "h2", "h3", "h4"])):
        if not tag.get_text(strip=True) and not tag.find(["img", "br", "table"]):
            tag.decompose()
    return "".join(str(child) for child in soup.contents).strip()


def html_to_text(html: str) -> str:
    """供 LLM / 关键词 / 向量使用的纯文本。"""
    raw = (html or "").strip()
    if not raw:
        return ""
    if not looks_like_html(raw):
        return raw
    soup = BeautifulSoup(raw, "html.parser")
    lines: list[str] = []

    def walk(node: Any, list_prefix: str = "") -> None:
        if isinstance(node, NavigableString):
            text_value = str(node).strip()
            if text_value:
                lines.append(f"{list_prefix}{text_value}" if list_prefix else text_value)
            return
        if not isinstance(node, Tag):
            return
        name = (node.name or "").lower()
        if name in _DROP_TAGS:
            return
        if name in {"ul", "ol"}:
            for child in node.children:
                walk(child, list_prefix="- ")
            return
        if name == "li":
            parts = []
            for child in node.children:
                if isinstance(child, NavigableString):
                    chunk = str(child).strip()
                    if chunk:
                        parts.append(chunk)
                elif isinstance(child, Tag) and (child.name or "").lower() in {"ul", "ol"}:
                    if parts:
                        lines.append(f"{list_prefix}{' '.join(parts)}".rstrip())
                        parts = []
                    walk(child, list_prefix="  - ")
                elif isinstance(child, Tag):
                    chunk = child.get_text(" ", strip=True)
                    if chunk:
                        parts.append(chunk)
            if parts:
                lines.append(f"{list_prefix}{' '.join(parts)}".rstrip())
            return
        if name == "br":
            lines.append("")
            return
        if name in {"p", "h2", "h3", "h4", "tr"}:
            text_value = node.get_text(" ", strip=True)
            if text_value:
                lines.append(text_value)
            return
        if name == "table":
            for child in node.children:
                walk(child)
            return
        for child in node.children:
            walk(child, list_prefix)

    for child in soup.contents:
        walk(child)
    # 合并多余空行
    cleaned: list[str] = []
    for line in lines:
        line = " ".join(line.split())
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def plain_full_text(value: Any) -> str:
    """取 full_text 的纯文本视图（HTML 则去标签）。"""
    return html_to_text(str(value or ""))


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
    """美东发布时间 → 北京墙钟字符串（无时区后缀）。

    国内源（bioon / pharmcube）页面时间已是北京时间，不要走本函数。
    入库时由 CRUD 把无 tz 字符串标成 Asia/Shanghai，避免再被当成 UTC。
    """
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
