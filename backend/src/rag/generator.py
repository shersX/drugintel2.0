"""基于检索结果的回答生成（支持流式）。"""

from __future__ import annotations

from typing import AsyncIterator, List, Sequence, Tuple

from backend.src.llm.client import SiliconFlowClient
from backend.src.models.news import News

SYSTEM_PROMPT = """你是医药情报助手。请仅依据提供的新闻摘要与对话上下文回答用户问题。
要求：
1. 回答简洁、事实准确，使用中文
2. 若检索结果不足以回答，明确说明资料不足
3. 在关键结论后用 [n] 标注来源编号（与给定资料编号一致）
不要编造检索结果中不存在的数据。"""


def _format_contexts(hits: Sequence[Tuple[News, float]]) -> str:
    blocks: List[str] = []
    for i, (news, score) in enumerate(hits, start=1):
        abstract = (news.abstract or news.content or "")[:800]
        blocks.append(
            f"[{i}] 标题: {news.title}\n"
            f"来源: {news.source or news.crawler or '-'} | 相关度: {score:.3f}\n"
            f"摘要: {abstract}"
        )
    return "\n\n".join(blocks)


def build_messages(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    history: Sequence[dict] | None = None,
) -> List[dict]:
    hist_lines = []
    for m in history or []:
        role = m.get("role")
        if role not in {"user", "assistant"}:
            continue
        hist_lines.append(f"{role}: {m.get('content')}")
    hist_block = "\n".join(hist_lines[-6:]) if hist_lines else "（无）"
    user = (
        f"对话历史：\n{hist_block}\n\n"
        f"用户问题：{query}\n\n"
        f"检索资料：\n{_format_contexts(hits) if hits else '（无检索结果）'}\n\n"
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
) -> str:
    if not hits:
        return "未检索到相关医药新闻，请换个关键词再试，或先运行采集与处理流水线入库。"
    llm = client or SiliconFlowClient.from_env()
    return await llm.chat_completion(build_messages(query, hits, history=history))


async def generate_answer_stream(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    client: SiliconFlowClient | None = None,
    history: Sequence[dict] | None = None,
) -> AsyncIterator[str]:
    if not hits:
        yield "未检索到相关医药新闻，请换个关键词再试，或先运行采集与处理流水线入库。"
        return
    llm = client or SiliconFlowClient.from_env()
    async for piece in llm.chat_completion_stream(
        build_messages(query, hits, history=history)
    ):
        yield piece
