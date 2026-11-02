"""独立实体抽取客户端（默认 Qwen/Qwen3-8B）。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, MutableMapping, Sequence

from backend.src.core.config import EntityEnvConfig
from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.entities.lexicon import normalize_and_feedback
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("entities.extract")

# 连续传输失败达到该阈值后，跳过本批剩余条目（空实体），避免卡死整轮
_CIRCUIT_BREAK_AFTER = 2

STORY_TYPES = (
    "clinical",
    "regulatory",
    "deal",
    "financing",
    "pipeline",
    "conference",
    "safety",
    "other",
)

_SYSTEM = """你是医药竞争情报实体抽取助手。从新闻标题与摘要中抽取结构化实体，只输出 JSON，不要解释。
字段：
- products: 品牌药/管线代号列表（英文小写优先，如 wegovy、cagrisema）
- drugs: 成分/INN 列表（英文小写，如 semaglutide）
- orgs: 公司/机构（尽量英文常用名，如 Eli Lilly）
- targets: 靶点（如 GLP-1）
- indications: 适应症（英文常用名优先）
- story_type: 只能是 clinical|regulatory|deal|financing|pipeline|conference|safety|other 之一
无法判断的字段用空数组；story_type 无法判断用 other。"""


def _client() -> SiliconFlowClient:
    cfg = EntityEnvConfig.load()
    return SiliconFlowClient(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
        timeout_sec=cfg.timeout_sec,
        max_retries=cfg.max_retries,
    )


def _parse_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out = []
        for x in value:
            s = str(x or "").strip()
            if s:
                out.append(s)
        return out
    return []


def _normalize_story_type(value: Any) -> str:
    t = str(value or "other").strip().lower()
    return t if t in STORY_TYPES else "other"


def _empty_raw() -> Dict[str, Any]:
    return {
        "products": [],
        "drugs": [],
        "orgs": [],
        "targets": [],
        "indications": [],
        "story_type": "other",
    }


def apply_empty_entities(item: MutableMapping) -> None:
    item.setdefault("products", [])
    item.setdefault("drugs", [])
    item.setdefault("orgs", [])
    item.setdefault("targets", [])
    item.setdefault("indications", [])
    item.setdefault("story_type", "other")
    item.setdefault("entity_raw", {})


def _crawl_cancel_requested() -> bool:
    try:
        from backend.src.crawl.schedule import is_crawl_cancel_requested

        return is_crawl_cancel_requested()
    except Exception:
        return False


async def extract_one(title: str, abstract: str = "", content: str = "") -> Dict[str, Any]:
    body = f"标题: {title or ''}\n摘要: {abstract or ''}\n"
    snippet = (content or "")[:1200]
    if snippet:
        body += f"正文节选: {snippet}\n"
    cfg = EntityEnvConfig.load()
    client = SiliconFlowClient(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
        timeout_sec=cfg.timeout_sec,
        max_retries=cfg.max_retries,
    )
    # Qwen3 默认开启 thinking，单条常 >30s；实体抽取关掉思考模式
    thinking = False if "qwen3" in (cfg.model or "").lower() else None
    resp = await client.chat_completion(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": body},
        ],
        temperature=0.1,
        enable_thinking=thinking,
    )
    content_text = ""
    if isinstance(resp, dict):
        choices = resp.get("choices") or []
        if choices:
            content_text = ((choices[0] or {}).get("message") or {}).get("content") or ""
    elif isinstance(resp, str):
        content_text = resp
    data = _parse_json(content_text)
    return {
        "products": _as_list(data.get("products")),
        "drugs": _as_list(data.get("drugs")),
        "orgs": _as_list(data.get("orgs")),
        "targets": _as_list(data.get("targets")),
        "indications": _as_list(data.get("indications")),
        "story_type": _normalize_story_type(data.get("story_type")),
    }


async def extract_and_normalize_items(
    items: Sequence[MutableMapping],
) -> List[MutableMapping]:
    """就地写入实体字段；词典回流在同一会话完成。

    传输类连续失败会断路跳过剩余条目；前端 abandon 会置取消位，本函数每条前检查。
    """
    if not items:
        return []
    cfg = EntityEnvConfig.load()
    if not cfg.api_key:
        logger.warning("实体抽取 API Key 未配置，跳过 NER")
        for item in items:
            apply_empty_entities(item)
        return list(items)

    consecutive_transport_failures = 0
    skip_rest = False

    for index, item in enumerate(items):
        if _crawl_cancel_requested():
            logger.warning(
                "实体抽取收到取消信号，跳过剩余 %s 条",
                len(items) - index,
            )
            for rest in items[index:]:
                apply_empty_entities(rest)
            break

        if skip_rest:
            apply_empty_entities(item)
            continue

        title = str(item.get("title") or "")
        abstract = str(item.get("abstract") or item.get("description") or "")
        content = str(item.get("full_text") or item.get("content") or "")
        try:
            raw = await extract_one(title, abstract, content)
            consecutive_transport_failures = 0
        except Exception as exc:
            logger.warning("实体抽取失败: %s", exc)
            raw = _empty_raw()
            consecutive_transport_failures += 1
            if consecutive_transport_failures >= _CIRCUIT_BREAK_AFTER:
                remaining = len(items) - index - 1
                logger.error(
                    "实体抽取连续失败 %s 次，跳过剩余 %s 条并继续流水线",
                    consecutive_transport_failures,
                    remaining,
                )
                skip_rest = True

        with session_scope() as session:
            norm = normalize_and_feedback(
                session,
                products=raw.get("products") or [],
                drugs=raw.get("drugs") or [],
                orgs=raw.get("orgs") or [],
                targets=raw.get("targets") or [],
                indications=raw.get("indications") or [],
            )
        item["products"] = norm["products"]
        item["drugs"] = norm["drugs"]
        item["orgs"] = norm["orgs"]
        item["targets"] = norm["targets"]
        item["indications"] = norm["indications"]
        item["entity_raw"] = {
            **(norm.get("entity_raw") or {}),
            "story_type": raw.get("story_type"),
        }
        item["story_type"] = raw.get("story_type") or "other"
    return list(items)
