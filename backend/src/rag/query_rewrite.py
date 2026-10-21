"""查询改写与澄清反问。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient
from backend.src.rag.intent import Intent, IntentResult

logger = get_logger("rag.query_rewrite")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REWRITE_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "query_rewrite.txt"
CLARIFY_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "clarify.txt"

_JSON_RE = re.compile(r"\{[\s\S]*\}")


@dataclass
class RewriteResult:
    search_query: str
    need_clarify: bool = False
    clarify_question: Optional[str] = None
    confidence: float = 0.5


def _load_prompt(path: Path, fallback: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    return fallback


def _history_block(history: Sequence[dict] | None, *, limit: int = 6) -> str:
    lines: list[str] = []
    for m in history or []:
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    if not lines:
        return "（无）"
    return "\n".join(lines[-limit:])


def _intent_label(intent: Intent | IntentResult | None) -> str:
    if intent is None:
        return "news_query"
    if isinstance(intent, IntentResult):
        return intent.intent.value
    return intent.value


def _parse_rewrite_json(raw: str, *, fallback_query: str) -> RewriteResult:
    text = (raw or "").strip()
    match = _JSON_RE.search(text)
    payload: dict[str, Any] = {}
    if match:
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            payload = {}
    search_query = str(payload.get("search_query") or "").strip() or fallback_query
    need = bool(payload.get("need_clarify"))
    question = payload.get("clarify_question")
    clarify_question = str(question).strip() if question else None
    if need and not clarify_question:
        clarify_question = "能否补充一下具体的公司、药物或适应症？这样我可以更准确地检索。"
    if not need:
        clarify_question = None
    try:
        confidence = float(payload.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    return RewriteResult(
        search_query=search_query,
        need_clarify=need,
        clarify_question=clarify_question,
        confidence=confidence,
    )


async def rewrite_query(
    user_query: str,
    *,
    history: Sequence[dict] | None = None,
    intent: Intent | IntentResult | None = None,
    empty_retry: bool = False,
    client: SiliconFlowClient | None = None,
) -> RewriteResult:
    """改写检索问句；empty_retry 表示上次检索无结果，请换关键词。"""
    q = (user_query or "").strip()
    if not q:
        return RewriteResult(search_query="", need_clarify=False, confidence=0.0)

    system = _load_prompt(
        REWRITE_PROMPT_PATH,
        "根据对话改写检索短句，输出 JSON："
        '{"search_query":"...","need_clarify":false,"clarify_question":null,"confidence":0.5}',
    )
    extra = ""
    if empty_retry:
        extra = (
            "\n上次按当前问法检索医药新闻库无足够结果。"
            "请换用别名、公司全称/简称、药名代号或更具体适应症；"
            "若仍无法确定对象，设 need_clarify=true。\n"
        )
    user = (
        f"意图标签：{_intent_label(intent)}\n"
        f"对话历史：\n{_history_block(history)}\n\n"
        f"用户当前问题：{q}\n"
        f"{extra}\n"
        "请输出 JSON："
    )
    try:
        llm = client or SiliconFlowClient.from_env()
        raw = await llm.chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        result = _parse_rewrite_json(str(raw or ""), fallback_query=q)
        logger.info(
            "query_rewrite search=%r clarify=%s conf=%.2f",
            result.search_query[:80],
            result.need_clarify,
            result.confidence,
        )
        return result
    except Exception as exc:
        logger.warning("query_rewrite 失败，回退原句: %s", exc)
        return RewriteResult(search_query=q, need_clarify=False, confidence=0.3)


async def clarify_after_empty(
    user_query: str,
    *,
    history: Sequence[dict] | None = None,
    search_query: str = "",
    client: SiliconFlowClient | None = None,
) -> str:
    """检索仍空时生成收窄反问。"""
    q = (user_query or "").strip()
    system = _load_prompt(
        CLARIFY_PROMPT_PATH,
        "检索无结果。用一两句中文向用户反问以收窄公司/药物/适应症，不要编造新闻。",
    )
    user = (
        f"对话历史：\n{_history_block(history)}\n\n"
        f"用户问题：{q}\n"
        f"曾用检索词：{search_query or q}\n\n"
        "请直接给出反问："
    )
    fallback = (
        "目前库里没有足够相关的新闻。能否补充更具体的公司名、药物名/研发代号，"
        "或适应症与时间范围？"
    )
    try:
        llm = client or SiliconFlowClient.from_env()
        raw = await llm.chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        text = str(raw or "").strip()
        return text or fallback
    except Exception as exc:
        logger.warning("clarify_after_empty 失败: %s", exc)
        return fallback
