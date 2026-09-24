"""向量生成（任务 2.5）：调用 SiliconFlow Embeddings API（BAAI/bge-m3，1024 维）。"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, MutableMapping, Optional, Sequence

import aiohttp

from backend.src.core.config import EmbeddingEnvConfig, LLMEnvConfig
from backend.src.core.logger import get_logger

logger = get_logger("processors.embedding")

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
EXPECTED_DIM = 1024


class SiliconFlowEmbeddingClient:
    """调用 SiliconFlow `/v1/embeddings`。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: float = 90.0,
        max_retries: int = 3,
        max_concurrency: int = 5,
    ):
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY 未设置，无法调用 Embedding")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    @classmethod
    def from_env(cls) -> "SiliconFlowEmbeddingClient":
        llm = LLMEnvConfig.load()
        emb = EmbeddingEnvConfig.load()
        return cls(
            api_key=llm.api_key,
            base_url=llm.base_url,
            model=emb.model,
            timeout_sec=llm.timeout_sec,
            max_retries=llm.max_retries,
            max_concurrency=emb.max_concurrency,
        )

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """批量编码；返回与 texts 等长的向量列表。"""
        if not texts:
            return []
        async with self._semaphore:
            return await self._embed_unlocked(list(texts))

    async def embed_one(self, text: str) -> List[float]:
        vectors = await self.embed([text])
        return vectors[0] if vectors else []

    async def _embed_unlocked(self, texts: List[str]) -> List[List[float]]:
        url = f"{self._base_url}/embeddings"
        payload: Dict[str, Any] = {
            "model": self._model,
            "input": texts,
            "encoding_format": "float",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout_sec)
        last_exc: Optional[BaseException] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        text = await resp.text()
                        if resp.status in _RETRYABLE_STATUS:
                            raise aiohttp.ClientConnectionError(
                                f"HTTP {resp.status}: {text[:300]}"
                            )
                        if resp.status >= 400:
                            resp.raise_for_status()
                        data = json.loads(text)
                items = data.get("data") or []
                # OpenAI 兼容：按 index 排序
                items = sorted(items, key=lambda x: x.get("index", 0))
                vectors: List[List[float]] = []
                for row in items:
                    emb = row.get("embedding") or []
                    vectors.append([float(x) for x in emb])
                if len(vectors) != len(texts):
                    raise ValueError(
                        f"embedding 条数不匹配: got={len(vectors)} expect={len(texts)}"
                    )
                return vectors
            except aiohttp.ClientResponseError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError) as e:
                last_exc = e
                logger.warning(
                    "Embedding 调用失败 attempt=%s/%s: %s",
                    attempt,
                    self._max_retries,
                    e,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise
        if last_exc:
            raise last_exc
        return []


def _text_for_embed(item: MutableMapping) -> str:
    title = str(item.get("title") or "").strip()
    abstract = str(item.get("abstract") or "").strip()
    if abstract:
        return f"{title}\n{abstract}"
    content = str(item.get("full_text") or "")[:2000]
    return f"{title}\n{content}".strip()


async def embed_items(
    items: Sequence[MutableMapping],
    *,
    client: Optional[SiliconFlowEmbeddingClient] = None,
    batch_size: int = 16,
) -> List[MutableMapping]:
    """为新闻写入 embedding 字段（list[float]，期望 1024 维）。"""
    if not items:
        return []
    emb_client = client or SiliconFlowEmbeddingClient.from_env()
    result: List[MutableMapping] = list(items)

    for start in range(0, len(result), batch_size):
        batch = result[start : start + batch_size]
        texts = [_text_for_embed(item) for item in batch]
        try:
            vectors = await emb_client.embed(texts)
        except Exception as e:
            logger.error("批量向量化失败 start=%s: %s", start, e)
            for item in batch:
                item["embedding"] = None
            continue
        for item, vec in zip(batch, vectors):
            if len(vec) != EXPECTED_DIM:
                logger.warning(
                    "向量维度异常 title=%s dim=%s expect=%s",
                    str(item.get("title") or "")[:40],
                    len(vec),
                    EXPECTED_DIM,
                )
            item["embedding"] = vec

    ok = sum(1 for i in result if i.get("embedding"))
    logger.info("向量生成 完成=%s/%s model 维=%s", ok, len(result), EXPECTED_DIM)
    return result
