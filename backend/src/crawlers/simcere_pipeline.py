"""先声药业官方管线页：渲染后下载管线示意图，供视觉模型抽取。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp

from backend.src.core.logger import get_logger

logger = get_logger("crawler.simcere_pipeline")

DEFAULT_SOURCE_URL = "https://www.simcere.com/kxcx/yggx.aspx"
COMPANY_NAME = "先声药业"
COMPANY_NAME_EN = "Simcere"

# 先声管线示意图：页面上仅此一张是管线主图
_PIPELINE_IMG_SELECTOR = "#ab01 > div > div > img"
_SNAPSHOT_ROOT = Path("data/pipeline_snapshots")


def snapshot_root() -> Path:
    _SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    return _SNAPSHOT_ROOT


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _img_item(src: str, alt: str = "", w: int = 0, h: int = 0) -> Dict[str, Any]:
    return {"src": src, "alt": alt or "", "w": int(w or 0), "h": int(h or 0)}


async def _download(session: aiohttp.ClientSession, url: str) -> Optional[bytes]:
    try:
        async with session.get(url) as resp:
            if resp.status >= 400:
                logger.warning("下载图片失败 HTTP %s %s", resp.status, url[:120])
                return None
            return await resp.read()
    except Exception as exc:
        logger.warning("下载图片异常 %s: %s", url[:120], exc)
        return None


def _collect_pipeline_img_playwright_sync(page_url: str) -> tuple[str, List[Dict[str, Any]]]:
    """同步 Playwright：只取 #ab01 下管线主图。须在独立线程调用。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(page_url, wait_until="networkidle", timeout=90_000)
            page.wait_for_selector(_PIPELINE_IMG_SELECTOR, timeout=30_000)
            page.wait_for_timeout(800)
            html = page.content()
            item = page.evaluate(
                """(sel) => {
                  const img = document.querySelector(sel);
                  if (!img) return null;
                  const src = img.currentSrc || img.src || img.getAttribute('data-src') || '';
                  if (!src || src.startsWith('data:')) return null;
                  return {
                    src,
                    alt: img.alt || '',
                    w: img.naturalWidth || img.width || 0,
                    h: img.naturalHeight || img.height || 0,
                  };
                }""",
                _PIPELINE_IMG_SELECTOR,
            )
            if not item:
                logger.warning("Playwright 未找到管线图选择器: %s", _PIPELINE_IMG_SELECTOR)
                return html, []
            return html, [item]
        finally:
            browser.close()


async def _collect_pipeline_img(page_url: str) -> tuple[str, List[Dict[str, Any]]]:
    """返回 (html, [管线图])。优先 Playwright；失败则静态解析同一选择器。"""
    import asyncio

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        logger.warning("未安装 playwright，改用静态抓取")
        return await _collect_pipeline_img_static(page_url)

    try:
        return await asyncio.to_thread(_collect_pipeline_img_playwright_sync, page_url)
    except Exception as exc:
        logger.warning("Playwright 抓取失败，改用静态抓取: %s", exc)
        return await _collect_pipeline_img_static(page_url)


async def _collect_pipeline_img_static(page_url: str) -> tuple[str, List[Dict[str, Any]]]:
    from bs4 import BeautifulSoup

    timeout = aiohttp.ClientTimeout(total=60)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(page_url) as resp:
            html = await resp.text()
    soup = BeautifulSoup(html, "html.parser")
    # 等价于 #ab01 > div > div > img
    node = soup.select_one(_PIPELINE_IMG_SELECTOR)
    if node is None:
        logger.warning("静态页未找到管线图选择器: %s", _PIPELINE_IMG_SELECTOR)
        return html, []
    src = node.get("src") or node.get("data-src") or ""
    if not src or str(src).startswith("data:"):
        return html, []
    return html, [_img_item(str(src), alt=node.get("alt") or "")]


async def crawl_simcere_pipeline(
    *,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """抓取先声管线主图并落盘。返回 crawl 契约（非 news item）。"""
    page_url = (source_url or DEFAULT_SOURCE_URL).strip() or DEFAULT_SOURCE_URL
    fetched_at = datetime.now(timezone.utc)
    html, candidates = await _collect_pipeline_img(page_url)

    normalized: List[Dict[str, Any]] = []
    for item in candidates:
        src = urljoin(page_url, str(item.get("src") or ""))
        if not src or urlparse(src).scheme not in ("http", "https"):
            continue
        normalized.append(
            _img_item(
                src,
                alt=str(item.get("alt") or ""),
                w=int(item.get("w") or 0),
                h=int(item.get("h") or 0),
            )
        )
        break  # 只要一张管线主图

    day = fetched_at.strftime("%Y%m%d")
    snapshot_root().joinpath(day).mkdir(parents=True, exist_ok=True)

    image_paths: List[str] = []
    image_hashes: List[str] = []
    timeout = aiohttp.ClientTimeout(total=120)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": page_url,
    }

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for item in normalized:
            data = await _download(session, item["src"])
            if not data:
                continue
            digest = _content_hash(data)
            ext = ".png"
            path_hint = urlparse(item["src"]).path.lower()
            if path_hint.endswith(".jpg") or path_hint.endswith(".jpeg"):
                ext = ".jpg"
            elif path_hint.endswith(".webp"):
                ext = ".webp"
            elif path_hint.endswith(".gif"):
                ext = ".gif"
            rel = f"{day}/{digest[:16]}{ext}"
            abs_path = snapshot_root() / rel
            if not abs_path.exists():
                abs_path.write_bytes(data)
            image_paths.append(str(Path("data/pipeline_snapshots") / rel).replace("\\", "/"))
            image_hashes.append(digest)
            logger.info(
                "管线主图已保存 %s (%s bytes, %sx%s)",
                image_paths[-1],
                len(data),
                item.get("w") or "?",
                item.get("h") or "?",
            )

    if not image_paths:
        logger.warning(
            "未抓到管线主图（选择器 %s），请检查 source_url: %s",
            _PIPELINE_IMG_SELECTOR,
            page_url,
        )

    return {
        "company": COMPANY_NAME,
        "company_en": COMPANY_NAME_EN,
        "source_url": page_url,
        "fetched_at": fetched_at.isoformat(),
        "image_paths": image_paths,
        "image_hashes": image_hashes,
        "raw_html": html[:200_000] if html else None,
        "candidate_count": len(normalized),
    }
