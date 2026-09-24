"""LLM 摘要生成（任务 2.4）。"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import List, MutableMapping, Optional, Sequence

from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("processors.summarizer")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SUMMARY_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "summary.txt"
DEFAULT_CONTENT_MAX_CHARS = 3000


@lru_cache(maxsize=1)
def _default_summary_prompt() -> str:
    if not DEFAULT_SUMMARY_PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到摘要 Prompt: {DEFAULT_SUMMARY_PROMPT_PATH}")
    return DEFAULT_SUMMARY_PROMPT_PATH.read_text(encoding="utf-8")


async def summarize_one(
    item: MutableMapping,
    llm: SiliconFlowClient,
    *,
    content_max_chars: int = DEFAULT_CONTENT_MAX_CHARS,
) -> MutableMapping:
    """为单条新闻写入 abstract 字段；失败时用 description 或正文截断兜底。"""
    title = str(item.get("title") or "")
    content = str(item.get("full_text") or "")[:content_max_chars]
    system_prompt = _default_summary_prompt()
    user_prompt = f"新闻标题：{title}\n新闻内容：{content}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        abstract = await llm.chat_completion(messages)
        abstract = (abstract or "").strip()
        if not abstract:
            raise ValueError("摘要为空")
        item["abstract"] = abstract
    except Exception as e:
        fallback = (item.get("description") or content[:200] or title).strip()
        item["abstract"] = fallback
        logger.warning("摘要失败 title=%s 使用兜底: %s", title[:60], e)
    return item


async def summarize_items(
    items: Sequence[MutableMapping],
    *,
    client: Optional[SiliconFlowClient] = None,
) -> List[MutableMapping]:
    """批量生成摘要（并发由 SiliconFlowClient Semaphore 限制）。"""
    if not items:
        return []
    llm = client or SiliconFlowClient.from_env()
    tasks = [asyncio.create_task(summarize_one(item, llm)) for item in items]
    results = await asyncio.gather(*tasks)
    return list(results)
