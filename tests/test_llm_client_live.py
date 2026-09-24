#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实联网测试：SiliconFlow + relevance.txt 提示词。

依赖环境变量：SILICONFLOW_API_KEY（未设置则跳过全部用例）。
可选：SILICONFLOW_BASE_URL、SILICONFLOW_MODEL、LLM_TIMEOUT_SEC、LLM_MAX_RETRIES

运行：
  python -m unittest tests.test_llm_client_live -v
或：
  python tests/test_llm_client_live.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RELEVANCE_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "relevance.txt"


def _has_api_key() -> bool:
    return bool(os.getenv("SILICONFLOW_API_KEY", "").strip())


@unittest.skipUnless(_has_api_key(), "SILICONFLOW_API_KEY 未设置，跳过真实 LLM 测试")
class TestLLMClientLive(unittest.IsolatedAsyncioTestCase):
    """使用 relevance.txt 与 SiliconFlowClient 做端到端调用。"""

    async def test_chat_completion_uses_relevance_txt(self) -> None:
        """客户端 + relevance.txt 模板，应返回非空且可解析为布尔。"""
        from backend.src.llm.client import SiliconFlowClient
        from backend.src.processors.relevance import parse_relevance_reply

        self.assertTrue(
            RELEVANCE_PROMPT_PATH.is_file(),
            msg=f"缺少提示词文件: {RELEVANCE_PROMPT_PATH}",
        )
        tpl = RELEVANCE_PROMPT_PATH.read_text(encoding="utf-8")
        user_content = tpl.format(
            title="FDA approves supplemental indication for oncology therapy",
            content=(
                "The US Food and Drug Administration approved an expanded label "
                "for combination therapy in advanced solid tumors."
            ),
        )
        client = SiliconFlowClient.from_env()
        messages = [
            {
                "role": "system",
                "content": "你是严谨的医药情报分类助手，只按要求输出是或否。",
            },
            {"role": "user", "content": user_content},
        ]
        reply = await client.chat_completion(messages, temperature=0.0, max_tokens=16)
        self.assertTrue((reply or "").strip(), msg=f"模型返回为空: {reply!r}")
        parsed = parse_relevance_reply(reply)
        self.assertIsInstance(parsed, bool)
        self.assertTrue(
            parsed,
            msg=f"预期医药相关为「是」，解析={parsed}，原始回复={reply!r}",
        )

    async def test_check_relevance_async_pharma_positive(self) -> None:
        """明显医药新闻：经 relevance 流程应为相关。"""
        from backend.src.processors.relevance import check_relevance_async

        ok = await check_relevance_async(
            "诺和诺德公布司美格鲁肽三期临床主要终点数据",
            "Novo Nordisk 公布 semaglutide 三期试验主要终点，涉及心血管结局与体重管理。",
        )
        self.assertTrue(ok, msg="预期 relevance_ok=True")

    async def test_check_relevance_async_sports_negative(self) -> None:
        """明显非医药：经 relevance 流程应为不相关。"""
        from backend.src.processors.relevance import check_relevance_async

        ok = await check_relevance_async(
            "世界杯小组赛战报",
            "本场比赛双方九十分钟互交白卷，加时赛后进入点球大战。",
        )
        self.assertFalse(ok, msg="预期 relevance_ok=False")


if __name__ == "__main__":
    unittest.main()
