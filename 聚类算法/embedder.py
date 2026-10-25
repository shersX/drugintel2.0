# -*- coding: utf-8 -*-
"""
SiliconFlow OpenAI 兼容 Embeddings 客户端（与 drugintel processors/embedding 对齐）。
环境变量优先读本目录 .env，其次 ../drugintel2.0/.env：
  SILICONFLOW_API_KEY / SILICONFLOW_EMBEDDING_API_KEY
  SILICONFLOW_BASE_URL / SILICONFLOW_EMBEDDING_BASE_URL
  SILICONFLOW_EMBEDDING_MODEL（默认 BAAI/bge-m3）
  SILICONFLOW_EMBEDDING_DIM（默认 1024）
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional, Sequence

import aiohttp
import numpy as np

_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_HERE = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (_HERE / ".env", _HERE.parent / "drugintel2.0" / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class SiliconFlowEmbeddingClient:
    """调用 `/v1/embeddings`，风格对齐 drugintel SiliconFlowEmbeddingClient。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "BAAI/bge-m3",
        timeout_sec: float = 90.0,
        max_retries: int = 3,
        expected_dim: int = 1024,
    ):
        if not api_key:
            raise ValueError(
                "嵌入 API Key 未设置。请在 drugintel2.0/.env 或本目录 .env 填写 "
                "SILICONFLOW_API_KEY / SILICONFLOW_EMBEDDING_API_KEY"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        self.expected_dim = expected_dim

    @classmethod
    def from_env(cls) -> "SiliconFlowEmbeddingClient":
        _load_dotenv()
        chat_key = _env("SILICONFLOW_API_KEY")
        chat_url = _env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        return cls(
            api_key=_env("SILICONFLOW_EMBEDDING_API_KEY") or chat_key,
            base_url=(_env("SILICONFLOW_EMBEDDING_BASE_URL") or chat_url).rstrip("/"),
            model=_env("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"),
            timeout_sec=float(_env("LLM_TIMEOUT_SEC", "90") or 90),
            max_retries=int(_env("LLM_MAX_RETRIES", "3") or 3),
            expected_dim=int(_env("SILICONFLOW_EMBEDDING_DIM", "1024") or 1024),
        )

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self._base_url}/embeddings"
        payload = {
            "model": self._model,
            "input": list(texts),
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
                        body = await resp.text()
                        if resp.status in _RETRYABLE:
                            raise aiohttp.ClientConnectionError(
                                f"HTTP {resp.status}: {body[:300]}"
                            )
                        if resp.status >= 400:
                            raise aiohttp.ClientResponseError(
                                resp.request_info,
                                resp.history,
                                status=resp.status,
                                message=body[:300],
                            )
                        data = json.loads(body)
                items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
                vectors = [[float(x) for x in (row.get("embedding") or [])] for row in items]
                if len(vectors) != len(texts):
                    raise ValueError(
                        f"embedding 条数不匹配: got={len(vectors)} expect={len(texts)}"
                    )
                return vectors
            except aiohttp.ClientResponseError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError) as e:
                last_exc = e
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise
        if last_exc:
            raise last_exc
        return []

    def encode(
        self,
        texts: Sequence[str],
        *,
        normalize: bool = True,
        batch_size: int = 16,
    ) -> np.ndarray:
        """同步批量编码，接口近似 SentenceTransformer.encode。"""
        if not texts:
            return np.zeros((0, self.expected_dim), dtype=np.float64)

        async def _run() -> List[List[float]]:
            out: List[List[float]] = []
            for i in range(0, len(texts), batch_size):
                out.extend(await self.embed(texts[i : i + batch_size]))
            return out

        vectors = asyncio.run(_run())
        arr = np.asarray(vectors, dtype=np.float64)
        if normalize and len(arr):
            norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
            arr = arr / norms
        return arr
