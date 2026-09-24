"""意图识别（任务 5.1）：规则优先，未知则归为 news_query。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Intent(str, Enum):
    NEWS_QUERY = "news_query"
    DRUG_INFO = "drug_info"
    COMPANY_INFO = "company_info"
    COMPARE = "compare"
    CHITCHAT = "chitchat"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    raw: str


_DRUG_HINTS = ("药物", "药品", "疗法", "适应症", "临床试验", "管线", "glp", "抑制剂", "抗体")
_COMPANY_HINTS = ("公司", "药企", "并购", "融资", "财报", "novartis", "诺和", "礼来", "辉瑞")
_COMPARE_HINTS = ("对比", "比较", "哪个更好", "vs", "versus", "差异")
_CHITCHAT_HINTS = ("你好", "谢谢", "你是谁", "帮我介绍一下自己")


def classify_intent(query: str) -> IntentResult:
    q = (query or "").strip()
    if not q:
        return IntentResult(intent=Intent.CHITCHAT, confidence=0.5, raw=q)
    lo = q.lower()
    if any(h in q or h in lo for h in _CHITCHAT_HINTS):
        return IntentResult(Intent.CHITCHAT, 0.8, q)
    if any(h in q or h in lo for h in _COMPARE_HINTS):
        return IntentResult(Intent.COMPARE, 0.75, q)
    if any(h in q or h in lo for h in _DRUG_HINTS):
        return IntentResult(Intent.DRUG_INFO, 0.7, q)
    if any(h in q or h in lo for h in _COMPANY_HINTS):
        return IntentResult(Intent.COMPANY_INFO, 0.7, q)
    return IntentResult(Intent.NEWS_QUERY, 0.6, q)
