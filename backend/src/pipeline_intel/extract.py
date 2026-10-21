"""视觉模型抽取管线 JSON。"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.core.config import VisionEnvConfig
from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("pipeline_intel.extract")

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "config" / "prompts" / "pipeline_vision_extract.txt"


def _load_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    return (
        "从管线示意图中抽取资产与交易，只输出 JSON："
        '{"assets":[...],"deals":[...]}'
    )


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _parse_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("视觉模型返回空内容")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"无法解析视觉模型 JSON: {raw[:200]}")
        data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("视觉模型 JSON 根节点必须是对象")
    assets = data.get("assets")
    deals = data.get("deals")
    if assets is None:
        assets = []
    if deals is None:
        deals = []
    if not isinstance(assets, list) or not isinstance(deals, list):
        raise ValueError("assets/deals 必须是数组")
    return {"assets": assets, "deals": deals}


async def extract_from_images(
    image_paths: List[str],
    *,
    client: Optional[SiliconFlowClient] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """对一张或多张管线图片做视觉抽取，返回 {assets, deals, model_name, raw_text}。"""
    if not image_paths:
        raise ValueError("没有可分析的管线图片")

    cfg = VisionEnvConfig.load()
    if not cfg.api_key or not cfg.model:
        raise ValueError("请先在设置 → 大模型 中配置并启用视觉模型")

    llm = client or SiliconFlowClient(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
        timeout_sec=max(cfg.timeout_sec, 180.0),
    )
    used_model = model_name or cfg.model
    prompt = _load_prompt()

    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    for rel in image_paths:
        path = Path(rel)
        if not path.is_file():
            # 兼容相对项目根
            alt = Path.cwd() / rel
            path = alt if alt.is_file() else path
        if not path.is_file():
            logger.warning("图片不存在，跳过: %s", rel)
            continue
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{_mime_for(path)};base64,{b64}"},
            }
        )
    if len(content) == 1:
        raise ValueError("管线图片文件均不可读")

    messages = [{"role": "user", "content": content}]
    raw_text = await llm.chat_completion(messages)
    parsed = _parse_json(raw_text)
    return {
        "assets": parsed["assets"],
        "deals": parsed["deals"],
        "model_name": used_model,
        "raw_text": raw_text,
    }
