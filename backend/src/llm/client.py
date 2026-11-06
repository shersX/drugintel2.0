"""SiliconFlow OpenAI 兼容 Chat Completions 异步客户端（超时 + 重试）。"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Sequence, Union

import aiohttp

from backend.src.core.config import AnalystEnvConfig, LLMEnvConfig
from backend.src.core.logger import get_logger

logger = get_logger("llm.client")

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_DEFAULT_MAX_CONCURRENCY = 5
_NON_RETRYABLE_MARKERS = (
    "name resolution",
    "temporary failure in name resolution",
    "nodename nor servname",
    "getaddrinfo failed",
    "name or service not known",
    "no address associated with hostname",
    "network is unreachable",
    "no route to host",
)


def is_non_retryable_transport_error(exc: BaseException) -> bool:
    """DNS / 主机不可达等：再重试也只会拖死流水线。"""
    name = type(exc).__name__
    if "DNS" in name or name in {"ClientConnectorDNSError"}:
        return True
    msg = str(exc or "").lower()
    return any(marker in msg for marker in _NON_RETRYABLE_MARKERS)


class SiliconFlowClient:
    """调用 SiliconFlow `/v1/chat/completions`。"""

    # Celery worker 每轮 asyncio.run 会新建 loop；类级 Semaphore 必须按 loop 重建，
    # 否则 stop→restart 后出现 “bound to a different event loop”。
    _semaphore: Optional[asyncio.Semaphore] = None
    _semaphore_loop: Optional[asyncio.AbstractEventLoop] = None
    _max_concurrency: int = _DEFAULT_MAX_CONCURRENCY

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: float = 90.0,
        max_retries: int = 3,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ):
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY 未设置，无法调用 LLM")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec
        self._max_retries = max(1, max_retries)
        SiliconFlowClient._max_concurrency = max(1, max_concurrency)

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

    @classmethod
    def from_analyst_env(cls):
        cfg = AnalystEnvConfig.load()
        return cls(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model,
            timeout_sec=cfg.timeout_sec,
            max_retries=cfg.max_retries,
        )

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if cls._semaphore is None or cls._semaphore_loop is not loop:
            cls._semaphore = asyncio.Semaphore(cls._max_concurrency)
            cls._semaphore_loop = loop
        return cls._semaphore

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        tools: Optional[Sequence[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        return_message: bool = False,
    ):
        """默认返回 content 字符串；return_message=True 时返回完整 assistant message。"""
        async with self._get_semaphore():
            msg = await self._chat_completion_unlocked(
                messages,
                stream=False,
                temperature=temperature,
                enable_thinking=enable_thinking,
                tools=tools,
                tool_choice=tool_choice,
            )
            if return_message:
                return msg
            return (msg.get("content") or "").strip() if isinstance(msg, dict) else str(msg or "")

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
    ):
        """异步生成器：逐段产出 content delta。"""
        async with self._get_semaphore():
            async for chunk in self._chat_completion_stream_unlocked(
                messages, temperature=temperature
            ):
                yield chunk

    async def _chat_completion_unlocked(
        self,
        messages: List[Dict[str, Any]],
        *,
        stream: bool = False,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        tools: Optional[Sequence[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if enable_thinking is not None:
            payload["enable_thinking"] = bool(enable_thinking)
        if tools:
            payload["tools"] = list(tools)
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
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
                    return {"role": "assistant", "content": ""}
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if content is None and msg.get("reasoning_content"):
                    # thinking 模型偶发只回 reasoning；正文仍优先 content
                    content = ""
                out = {
                    "role": "assistant",
                    "content": (content or "").strip() if isinstance(content, str) else content,
                }
                if msg.get("tool_calls"):
                    out["tool_calls"] = msg["tool_calls"]
                return out
            except aiohttp.ClientResponseError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
                last_exc = e
                logger.warning(
                    "LLM 调用失败 attempt=%s/%s: %s: %s",
                    attempt,
                    self._max_retries,
                    type(e).__name__,
                    e or repr(e),
                )
                if is_non_retryable_transport_error(e):
                    raise
                if attempt < self._max_retries:
                    await asyncio.sleep(min(8, 2 ** attempt))
                else:
                    raise

        if last_exc:
            raise last_exc
        return {"role": "assistant", "content": ""}

    async def _chat_completion_stream_unlocked(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
    ):
        url = f"{self._base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
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
