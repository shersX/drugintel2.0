"""LLM 医药相关性判断（任务 2.2）。"""

from functools import lru_cache
from pathlib import Path
from typing import List, Mapping, MutableMapping, Optional, Protocol, runtime_checkable

from backend.src.core.logging import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("processors.relevance")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RELEVANCE_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "relevance.txt"

@runtime_checkable
class SupportsChatCompletion(Protocol):
    async def chat_completion(
        self,
        messages: List[Mapping[str, str]]
    ) -> str: ...


@lru_cache(maxsize=1)
def _default_relevance_prompt() -> str:
    if not DEFAULT_RELEVANCE_PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到相关性 Prompt 文件: {DEFAULT_RELEVANCE_PROMPT_PATH}")
    return DEFAULT_RELEVANCE_PROMPT_PATH.read_text(encoding="utf-8")


def _relevance_prompt_text(prompt_path: Optional[str] = None) -> str:
    if prompt_path:
        return Path(prompt_path).read_text(encoding="utf-8")
    return _default_relevance_prompt()


def parse_relevance_reply(reply: str) -> bool:
    """
    将模型输出解析为是否相关。
    兼容 PRD「是 / 否」、否定前缀与简单英文。
    """
    if not reply:
        return False
    first = reply.strip().splitlines()[0].strip()
    if not first:
        return False
    if first.startswith("不是") or first.startswith("否"):
        return False
    if first == "是" or first.startswith("是"):
        return True
    lo = first.lower()
    if lo.startswith("yes"):
        return True
    if lo.startswith("no"):
        return False
    return False


async def check_relevance_async(title: str,content: str,*,client: Optional[SupportsChatCompletion] = None,prompt_path: Optional[str] = None):
    """
    判断新闻是否与医药行业相关（异步；可注入 client 便于单测）。

    Args:
        title: 标题（单独传入 Prompt 的「新闻标题」字段）
        content: 正文（对应 Prompt 的「新闻内容」）
        client: 默认 SiliconFlowClient.from_env()
        prompt_path: 覆盖默认 relevance.txt
    """
    tpl = _relevance_prompt_text(prompt_path)
    user_content = tpl.format(title=title or "", content=content or "")

    llm = client or SiliconFlowClient.from_env()
    messages = [
        {
            "role": "system",
            "content": "你是严谨的医药情报分类助手，只按要求输出是或否。",
        },
        {"role": "user", "content": user_content},
    ]
    reply = await llm.chat_completion(messages)
    result = parse_relevance_reply(reply)
    logger.info(
        "相关性判断 title=%s result=%s reply_preview=%s",
        (title or ""),
        result,
        (reply or "").replace("\n", " "),
    )
    return result


def check_relevance(title: str,content: str):
    """同步包装（脚本用）；流水线优先用 check_relevance_async。"""
    import asyncio

    return asyncio.run(
        check_relevance_async(title, content)
    )


async def annotate_relevance_for_items(items: List[MutableMapping],*,client: Optional[SupportsChatCompletion] = None):
    """
    逐条写入 relevance_ok。
    标题用 title；正文内容用 description + full_text（不重复标题），与过滤模块字段一致。
    """
    llm = client
    out: List[MutableMapping] = []
    for item in items:
        if not isinstance(item, MutableMapping):
            continue
        title = str(item.get("title", "") or "")
        desc = str(item.get("description", "") or "")
        full = str(item.get("full_text", "") or "")
        body = f"{desc}\n{full}".strip()
        if not body:
            body = title
        ok = await check_relevance_async(
            title,
            body,
            client=llm,
        )
        item["relevance_ok"] = ok
        out.append(item)
    return out
