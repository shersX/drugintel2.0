"""基于检索结果的回答生成（支持流式）。"""

from __future__ import annotations

from typing import AsyncIterator, List, Optional, Sequence, Tuple

from backend.src.llm.client import SiliconFlowClient
from backend.src.models.news import News
from backend.src.rag.intent import Intent, IntentResult

SYSTEM_PROMPT = """你是医药情报助手。请仅依据提供的新闻摘要与对话上下文回答用户问题。
要求：
1. 回答简洁、事实准确，使用中文
2. 若检索结果不足以回答，明确说明资料不足
3. 在关键结论后用 [n] 标注来源编号（与给定资料编号一致）
4. 若资料中含「当前阅读」标记的文章，优先依据该篇作答，其它资料仅作补充
不要编造检索结果中不存在的数据。"""

CHITCHAT_SYSTEM_PROMPT = """你是 DrugIntel.ai 的医药情报助手。当前用户是闲聊或在询问你的能力，不需要检索新闻。
用简洁友好的中文回答：
- 你可以基于已入库的医药新闻做问答、公司/管线动态解读、简单对比等
- 不能编造具体新闻事实；若用户想查情报，请引导他们给出公司、药物或关键词
保持简短，不要假装已经检索到了新闻。"""

_EMPTY_RAG_REPLY = (
    "未检索到相关医药新闻，请换个关键词再试，或先运行采集与处理流水线入库。"
)

_PAGE_CTX_LIMIT = 2400
_DEFAULT_CTX_LIMIT = 800


def _format_contexts(
    hits: Sequence[Tuple[News, float]],
    *,
    page_news_id: Optional[int] = None,
) -> str:
    blocks: List[str] = []
    for i, (news, score) in enumerate(hits, start=1):
        is_page = page_news_id is not None and news.id == page_news_id
        limit = _PAGE_CTX_LIMIT if is_page else _DEFAULT_CTX_LIMIT
        abstract = (news.abstract or news.content or "")[:limit]
        label = "当前阅读" if is_page else "检索"
        blocks.append(
            f"[{i}] ({label}) 标题: {news.title}\n"
            f"来源: {news.source or news.crawler or '-'} | 相关度: {score:.3f}\n"
            f"摘要: {abstract}"
        )
    return "\n\n".join(blocks)


def _history_block(history: Sequence[dict] | None) -> str:
    hist_lines = []
    for m in history or []:
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        hist_lines.append(f"{role}: {m.get('content')}")
    return "\n".join(hist_lines[-6:]) if hist_lines else "（无）"


def _is_chitchat(intent: Intent | IntentResult | None) -> bool:
    if intent is None:
        return False
    if isinstance(intent, IntentResult):
        return intent.intent == Intent.CHITCHAT
    return intent == Intent.CHITCHAT


def build_messages(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    history: Sequence[dict] | None = None,
    intent: Intent | IntentResult | None = None,
    page_news_id: Optional[int] = None,
) -> List[dict]:
    hist_block = _history_block(history)
    if _is_chitchat(intent):
        user = (
            f"对话历史：\n{hist_block}\n\n"
            f"用户说：{query}\n\n"
            "请直接回答（无需引用新闻资料）："
        )
        return [
            {"role": "system", "content": CHITCHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    user = (
        f"对话历史：\n{hist_block}\n\n"
        f"用户问题：{query}\n\n"
        f"检索资料：\n"
        f"{_format_contexts(hits, page_news_id=page_news_id) if hits else '（无检索结果）'}\n\n"
        "请作答："
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


async def generate_answer(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    client: SiliconFlowClient | None = None,
    history: Sequence[dict] | None = None,
    intent: Intent | IntentResult | None = None,
    page_news_id: Optional[int] = None,
) -> str:
    if not hits and not _is_chitchat(intent):
        return _EMPTY_RAG_REPLY
    llm = client or SiliconFlowClient.from_env()
    return await llm.chat_completion(
        build_messages(
            query,
            hits,
            history=history,
            intent=intent,
            page_news_id=page_news_id,
        )
    )


async def generate_answer_stream(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    client: SiliconFlowClient | None = None,
    history: Sequence[dict] | None = None,
    intent: Intent | IntentResult | None = None,
    page_news_id: Optional[int] = None,
) -> AsyncIterator[str]:
    if not hits and not _is_chitchat(intent):
        yield _EMPTY_RAG_REPLY
        return
    llm = client or SiliconFlowClient.from_env()
    async for piece in llm.chat_completion_stream(
        build_messages(
            query,
            hits,
            history=history,
            intent=intent,
            page_news_id=page_news_id,
        )
    ):
        yield piece
