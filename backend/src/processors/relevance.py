"""LLM 医药相关性判断（任务 2.2）。"""

from functools import lru_cache
from pathlib import Path
from typing import List, Mapping, MutableMapping, Optional, Protocol, runtime_checkable
import asyncio
from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("processors.relevance")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RELEVANCE_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "relevance.txt"

@lru_cache(maxsize=1)
def _default_relevance_prompt() -> str:
    if not DEFAULT_RELEVANCE_PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到相关性 Prompt 文件: {DEFAULT_RELEVANCE_PROMPT_PATH}")
    return DEFAULT_RELEVANCE_PROMPT_PATH.read_text(encoding="utf-8")


def _relevance_prompt_text(prompt_path: Optional[str] = None) -> str:
    if prompt_path:
        return Path(prompt_path).read_text(encoding="utf-8")
    return _default_relevance_prompt()

async def isrelated_for_item(items):
    """
    利用大模型判断文本是否与医药行业相关。

    结果返回：
    1. 相关：文本与医药行业相关（保留该新闻）
    2. 不相关：文本与医药行业不相关（去除该新闻）
    3. LLM 调用失败（超时、网络、接口错误等）：保守当作相关，保留该新闻

    Args:
        items: 要判断的新闻项，包含 full_text 等字段
    Returns:
        判定为相关或 LLM 失败而保留的新闻项列表
    """

    llm = SiliconFlowClient.from_env()
    tasks = [asyncio.create_task(check_single_relevance_async(item, llm)) for item in items]
    results=await asyncio.gather(*tasks)
    related_items=[item for item in results if item is not None]
    return related_items


async def check_single_relevance_async(item, llm: SiliconFlowClient):
    """
    判断单条新闻是否与医药行业相关。

    LLM 调用失败时记录 warning 并 return item（当作相关保留）。

    Args:
        item: 新闻项，含 title、full_text
        llm: SiliconFlowClient 实例（并发由 client 内 Semaphore 限制）
    """

    title = item["title"]
    content = item["full_text"]
    system_prompt = _relevance_prompt_text()
    user_prompt = f"新闻标题：{title}\n新闻内容：{content}"

    messages = [
        {"role": "system","content": system_prompt,},
        {"role": "user", "content": user_prompt},
    ]

    try:
        reply = await llm.chat_completion(messages)
    except Exception as e:
        logger.warning("标题为【%s】的新闻项 LLM 调用失败，当作相关保留: %s", title, e)
        return item
    cleaned_result=reply.strip().replace("\n","").replace(" ","")
    if cleaned_result=="相关":
        logger.info(f"标题为【{title}】的新闻项被判断为相关,保留")
        return item
    elif cleaned_result=="不相关":
        logger.info(f"标题为【{title}】的新闻项被判断为不相关，直接去除")
        return None
    else:
        return item



if __name__ == "__main__":
    item = [
        {
            "title": "Cell子刊：先降雄后化疗，复旦大学 团队分钟，优化多西他赛清除率，降低三联疗法严重中性粒细胞减少风险",
            "full_text": "该研究首次系统评估了先导ADT对三联疗法严重中性粒细胞减少的影响。先导ADT具有以下优势：无需额外注射，可整合至常规ADT给药流程；成本低，尤其适用于医疗资源有限的地区；不影响长期生存获益。",
        },
        {
            "title": "Nature：温俊豪团队发现最佳睡眠时长6-8小时；过长或过短均增加全身性疾病与死亡风险",
            "full_text": "这项研究首次描绘了睡眠时长与全身多器官生物衰老之间清晰、系统的“U型”图谱。它强有力地证明，维持适度的睡眠时长，是延缓整体生理衰老、预防多种年龄相关疾病、促进长寿的一个关键性、可改变的生活方式因素。",
        }
    ]
    print(asyncio.run(isrelated_for_item(item)))