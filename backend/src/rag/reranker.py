"""重排序（任务 5.3）：优先调用 SiliconFlow /rerank，失败则按原分数回退。"""

from __future__ import annotations

import json
from typing import List, Sequence, Tuple

import aiohttp

from backend.src.core.config import EmbeddingEnvConfig, LLMEnvConfig
from backend.src.core.logger import get_logger
from backend.src.models.news import News

logger = get_logger("rag.reranker")


async def rerank(
    query: str,
    hits: Sequence[Tuple[News, float]],
    *,
    top_k: int = 5,
) -> List[Tuple[News, float]]:
    if not hits:
        return []
    if len(hits) == 1:
        return list(hits)[:top_k]

    llm = LLMEnvConfig.load()
    emb = EmbeddingEnvConfig.load()
    if not llm.api_key:
        return list(hits)[:top_k]

    documents = []
    for news, _ in hits:
        text = f"{news.title}\n{(news.abstract or news.content or '')[:1500]}"
        documents.append(text)

    url = f"{llm.base_url.rstrip('/')}/rerank"
    payload = {
        "model": emb.reranker_model,
        "query": query,
        "documents": documents,
        "top_n": min(top_k, len(documents)),
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {llm.api_key}",
        "Content-Type": "application/json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=llm.timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=text[:300],
                    )
                data = json.loads(text)
        results = data.get("results") or data.get("data") or []
        reranked: List[Tuple[News, float]] = []
        for row in results:
            idx = int(row.get("index", -1))
            score = float(row.get("relevance_score", row.get("score", 0.0)))
            if 0 <= idx < len(hits):
                reranked.append((hits[idx][0], score))
        if reranked:
            return reranked[:top_k]
    except Exception as e:
        logger.warning("重排序失败，回退原排序: %s", e)
    return list(hits)[:top_k]
