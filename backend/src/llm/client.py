"""SiliconFlow OpenAI 兼容 Chat Completions 异步客户端（超时 + 重试）。"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import aiohttp

from backend.src.core.config import LLMEnvConfig
from backend.src.core.logger import get_logger

logger = get_logger("llm.client")

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_DEFAULT_MAX_CONCURRENCY = 5


class SiliconFlowClient:
    """调用 SiliconFlow `/v1/chat/completions`。"""

    _semaphore: Optional[asyncio.Semaphore] = None

    def __init__(self,*,api_key: str,base_url: str,model: str,timeout_sec: float = 90.0,max_retries: int = 3,max_concurrency: int = _DEFAULT_MAX_CONCURRENCY):
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY 未设置，无法调用 LLM")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        if SiliconFlowClient._semaphore is None:
            SiliconFlowClient._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    @classmethod
    def from_env(cls):
        cfg = LLMEnvConfig.load()
        return cls(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            timeout_sec=cfg.timeout_sec,
            max_retries=cfg.max_retries,
        )

    async def chat_completion(self, messages: List[Dict[str, str]]):
        assert self._semaphore is not None
        async with self._semaphore:
            return await self._chat_completion_unlocked(messages, stream=False)

    async def chat_completion_stream(self, messages: List[Dict[str, str]]):
        """异步生成器：逐段产出 content delta。"""
        assert self._semaphore is not None
        async with self._semaphore:
            async for chunk in self._chat_completion_stream_unlocked(messages):
                yield chunk

    async def _chat_completion_unlocked(self, messages: List[Dict[str, str]], *, stream: bool = False):
        url = f"{self._base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
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
                            raise aiohttp.ClientConnectionError(f"HTTP {resp.status}: {text[:300]}")
                        if resp.status >= 400:
                            resp.raise_for_status()
                        data = json.loads(text)
                choices = data.get("choices") or []
                if not choices:
                    logger.warning("LLM 响应无 choices: %s", str(data)[:300])
                    return ""
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                return (content or "").strip()
            except aiohttp.ClientResponseError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
                last_exc = e
                logger.warning(
                    "LLM 调用失败 attempt=%s/%s: %s", attempt, self._max_retries, e
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(4 ** attempt)
                else:
                    raise

        if last_exc:
            raise last_exc
        return ""

    async def _chat_completion_stream_unlocked(self, messages: List[Dict[str, str]]):
        url = f"{self._base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=text[:300],
                    )
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece


if __name__ == "__main__":
    client = SiliconFlowClient.from_env()
    print(
        asyncio.run(
            client.chat_completion(
                [
                    {"role": "system", "content": "你是一个数学老师，只回答数学问题"},
                    {"role": "user", "content": "9.8-9.11=？"},
                ]
            )
        )
    )