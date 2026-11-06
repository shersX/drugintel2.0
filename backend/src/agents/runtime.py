"""OpenAI 兼容 tools 循环运行时。"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("agents.runtime")

ToolHandler = Callable[[Dict[str, Any]], Awaitable[Any] | Any]


class ToolSpec:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: ToolHandler,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


async def run_tool_loop(
    client: SiliconFlowClient,
    *,
    system: str,
    user: str,
    tools: Sequence[ToolSpec],
    max_steps: int = 6,
    temperature: float = 0.25,
    enable_thinking: bool = True,
) -> Dict[str, Any]:
    """返回 {content, tool_trace, steps}。"""
    tool_map = {t.name: t for t in tools}
    openai_tools = [t.openai_tool() for t in tools]
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    trace: List[Dict[str, Any]] = []
    collected_bits: List[str] = []

    for step in range(max_steps):
        msg = await client.chat_completion(
            messages,
            temperature=temperature,
            enable_thinking=enable_thinking,
            tools=openai_tools,
            tool_choice="auto",
            return_message=True,
        )
        if not isinstance(msg, dict):
            msg = {"role": "assistant", "content": str(msg or "")}

        tool_calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()
        if content:
            collected_bits.append(content)

        if not tool_calls:
            return {
                "content": content,
                "tool_trace": trace,
                "steps": step + 1,
            }

        # 回灌 assistant（含 tool_calls）
        messages.append(msg)
        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            spec = tool_map.get(name)
            result: Any
            if spec is None:
                result = {"error": f"unknown tool: {name}"}
            else:
                try:
                    maybe = spec.handler(args)
                    if hasattr(maybe, "__await__"):
                        result = await maybe  # type: ignore[misc]
                    else:
                        result = maybe
                except Exception as exc:
                    logger.warning("工具失败 %s: %s", name, exc)
                    result = {"error": str(exc)[:400]}
            payload = result if isinstance(result, (dict, list)) else {"result": result}
            # 截断过大返回
            text = json.dumps(payload, ensure_ascii=False)
            if len(text) > 6000:
                text = text[:6000] + "…"
            trace.append({"name": name, "args": args, "ok": "error" not in payload})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": (tc or {}).get("id") or name,
                    "content": text,
                }
            )

    # 步数耗尽：无工具收尾写作
    logger.warning("工具循环步数耗尽，降级一次无工具收尾")
    messages.append(
        {
            "role": "user",
            "content": "请根据已收集的工具结果，直接输出最终研报正文，不要再调用工具。",
        }
    )
    final = await client.chat_completion(
        messages,
        temperature=temperature,
        enable_thinking=enable_thinking,
        return_message=True,
    )
    content = ""
    if isinstance(final, dict):
        content = (final.get("content") or "").strip()
    else:
        content = str(final or "").strip()
    if not content and collected_bits:
        content = collected_bits[-1]
    return {"content": content, "tool_trace": trace, "steps": max_steps}
