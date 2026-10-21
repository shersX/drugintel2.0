"""爬虫注册表 DB 覆盖层。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.crawler_setting import CrawlerSetting

logger = get_logger("crawler.settings_store")


def _code_defaults() -> Dict[str, Dict[str, Any]]:
    from backend.src.crawlers.registry import CRAWLER_REGISTRY

    out: Dict[str, Dict[str, Any]] = {}
    for key, cfg in CRAWLER_REGISTRY.items():
        out[key] = {
            "name": cfg.get("name", key),
            "kind": cfg.get("kind", "news"),
            "enabled": bool(cfg.get("enabled", True)),
            "page_count": int(cfg.get("page_count", 1)),
            "concurrency": int(cfg.get("concurrency", 2)),
            "fetch_details": bool(cfg.get("fetch_details", True)),
        }
    return out


def seed_crawler_settings(session: Session) -> int:
    """为代码注册表中每个 key 插入默认行（已存在不覆盖）。"""
    created = 0
    for key, defaults in _code_defaults().items():
        existing = session.get(CrawlerSetting, key)
        if existing is not None:
            continue
        session.add(
            CrawlerSetting(
                crawler_key=key,
                enabled=defaults["enabled"],
                page_count=defaults["page_count"],
                concurrency=defaults["concurrency"],
                fetch_details=defaults["fetch_details"],
            )
        )
        created += 1
    if created:
        session.flush()
        logger.info("已写入 crawler_setting 默认行 %s 条", created)
    return created


def list_crawler_settings(session: Session) -> List[Dict[str, Any]]:
    defaults = _code_defaults()
    rows = {
        r.crawler_key: r
        for r in session.scalars(select(CrawlerSetting)).all()
    }
    items: List[Dict[str, Any]] = []
    for key, base in defaults.items():
        row = rows.get(key)
        items.append(
            {
                "crawler_key": key,
                "name": base["name"],
                "kind": base.get("kind", "news"),
                "enabled": bool(row.enabled) if row else base["enabled"],
                "page_count": int(row.page_count) if row else base["page_count"],
                "concurrency": int(row.concurrency) if row else base["concurrency"],
                "fetch_details": bool(row.fetch_details) if row else base["fetch_details"],
            }
        )
    return items


def update_crawler_setting(
    session: Session,
    crawler_key: str,
    *,
    enabled: bool,
    page_count: int,
    concurrency: int,
    fetch_details: bool,
) -> Dict[str, Any]:
    defaults = _code_defaults()
    if crawler_key not in defaults:
        raise KeyError(f"未知爬虫：{crawler_key}")
    row = session.get(CrawlerSetting, crawler_key)
    if row is None:
        row = CrawlerSetting(crawler_key=crawler_key)
        session.add(row)
    row.enabled = bool(enabled)
    row.page_count = max(1, min(50, int(page_count)))
    row.concurrency = max(1, min(20, int(concurrency)))
    row.fetch_details = bool(fetch_details)
    session.flush()
    base = defaults[crawler_key]
    return {
        "crawler_key": crawler_key,
        "name": base["name"],
        "kind": base.get("kind", "news"),
        "enabled": row.enabled,
        "page_count": row.page_count,
        "concurrency": row.concurrency,
        "fetch_details": row.fetch_details,
    }


def merged_crawler_registry(
    session: Optional[Session] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    返回可传给 run_all_crawlers 的配置：
    function 来自代码表，运行参数来自 DB（无则代码默认）。
    """
    from backend.src.crawlers.registry import CRAWLER_REGISTRY

    def _merge(sess: Session) -> Dict[str, Dict[str, Any]]:
        seed_crawler_settings(sess)
        rows = {
            r.crawler_key: r
            for r in sess.scalars(select(CrawlerSetting)).all()
        }
        out: Dict[str, Dict[str, Any]] = {}
        for key, cfg in CRAWLER_REGISTRY.items():
            row = rows.get(key)
            out[key] = {
                "name": cfg.get("name", key),
                "kind": cfg.get("kind", "news"),
                "function": cfg.get("function"),
                "enabled": bool(row.enabled) if row else bool(cfg.get("enabled", True)),
                "page_count": int(row.page_count) if row else int(cfg.get("page_count", 1)),
                "concurrency": int(row.concurrency)
                if row
                else int(cfg.get("concurrency", 2)),
                "fetch_details": bool(row.fetch_details)
                if row
                else bool(cfg.get("fetch_details", True)),
            }
        return out

    if session is not None:
        return _merge(session)
    try:
        with session_scope() as sess:
            return _merge(sess)
    except Exception as exc:
        logger.warning("合并 crawler_setting 失败，使用代码默认: %s", exc)
        return {
            key: {
                "name": cfg.get("name", key),
                "kind": cfg.get("kind", "news"),
                "function": cfg.get("function"),
                "enabled": bool(cfg.get("enabled", True)),
                "page_count": int(cfg.get("page_count", 1)),
                "concurrency": int(cfg.get("concurrency", 2)),
                "fetch_details": bool(cfg.get("fetch_details", True)),
            }
            for key, cfg in CRAWLER_REGISTRY.items()
        }
