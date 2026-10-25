# -*- coding: utf-8 -*-
"""数据采集：从 RSS 源或本地 JSON 读取原始新闻"""
import time
import hashlib
import json


def _hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]


def fetch_rss(url: str, limit: int = 100):
    """从 RSS 源拉取（医药行业如 FiercePharma、Endpoints、FierceBiotech 等均有 RSS）"""
    import feedparser
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:limit]:
        tt = e.get("published_parsed")
        items.append({
            "id": _hash(e.get("link", e.get("title", ""))),
            "title": e.get("title", ""),
            "content": e.get("summary", ""),
            "url": e.get("link", ""),
            "published": time.mktime(tt) if tt else time.time(),
        })
    return items


def load_jsonl(path: str):
    """读取本地 JSONL：每行 {id?,title,content,url?,published?}"""
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            d.setdefault("id", _hash(d.get("url", d.get("title", ""))))
            d.setdefault("published", time.time())
            d.setdefault("url", "")
            items.append(d)
    return items