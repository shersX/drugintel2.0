"""意图识别（任务 5.1）：规则优先，未知则归为 news_query。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


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
_CHITCHAT_HINTS = (
    "你好",
    "您好",
    "嗨",
    "hello",
    "hi ",
    "谢谢",
    "感谢",
    "你是谁",
    "你是什么",
    "介绍一下自己",
    "帮我介绍一下自己",
    "你可以干啥",
    "你能做什么",
    "你能干什么",
    "你会什么",
    "有什么功能",
    "怎么用",
    "如何使用",
    "在吗",
    "早上好",
    "晚安",
    "help",
)
# 短句能力/寒暄（避免整句误伤长查询）
_CHITCHAT_RE = re.compile(
    r"^("
    r"你(可以|能|会).{0,10}(干|做|帮|说)|"
    r"(帮(我)?|请)?介绍(一下)?(你|自己)|"
    r"你是谁|你叫什么|"
    r"你好啊?|您好啊?|在吗|"
    r"(怎么|如何)(用|使用)|"
    r"功能(介绍|说明)?"
    r")[\s\W]*$",
    re.IGNORECASE,
)


def classify_intent(query: str) -> IntentResult:
    q = (query or "").strip()
    if not q:
        return IntentResult(intent=Intent.CHITCHAT, confidence=0.5, raw=q)
    lo = q.lower()
    if len(q) <= 40 and _CHITCHAT_RE.match(q):
        return IntentResult(Intent.CHITCHAT, 0.9, q)
    if any(h in q or h in lo for h in _CHITCHAT_HINTS):
        return IntentResult(Intent.CHITCHAT, 0.85, q)
    if any(h in q or h in lo for h in _COMPARE_HINTS):
        return IntentResult(Intent.COMPARE, 0.75, q)
    if any(h in q or h in lo for h in _DRUG_HINTS):
        return IntentResult(Intent.DRUG_INFO, 0.7, q)
    if any(h in q or h in lo for h in _COMPANY_HINTS):
        return IntentResult(Intent.COMPANY_INFO, 0.7, q)
    return IntentResult(Intent.NEWS_QUERY, 0.6, q)
