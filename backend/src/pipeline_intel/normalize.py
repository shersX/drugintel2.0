"""阶段与名称归一。"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

STAGE_LABELS = {
    "preclinical": "临床前",
    "phase1": "I 期",
    "phase2": "II 期",
    "phase3": "III 期",
    "nda": "申报上市",
    "approved": "已获批",
    "partner": "合作方推进",
    "unknown": "未知",
}

_STAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"合作|partner|licensee", re.I), "partner"),
    (re.compile(r"获批|上市|approved|marketed|commercial", re.I), "approved"),
    (re.compile(r"\bnda\b|\bbla\b|申报|申请上市|审评", re.I), "nda"),
    (re.compile(r"iii|Ⅲ|3\s*期|phase\s*iii|pivotal", re.I), "phase3"),
    (re.compile(r"ii|Ⅱ|2\s*期|phase\s*ii", re.I), "phase2"),
    (re.compile(r"i\b|Ⅰ|1\s*期|phase\s*i\b|ind", re.I), "phase1"),
    (re.compile(r"临床前|preclinical|ind\s*enabling", re.I), "preclinical"),
]


def normalize_drug_code(name: str) -> str:
    text = (name or "").strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\s\-_/]+", "", text)
    # 代号类转大写；纯中文保持原样
    if re.search(r"[A-Za-z0-9]", text):
        return text.upper()
    return text


def normalize_indication(text: str) -> str:
    value = unicodedata.normalize("NFKC", (text or "").strip())
    value = re.sub(r"\s+", "", value)
    return value[:500]


def normalize_stage(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    for pattern, code in _STAGE_PATTERNS:
        if pattern.search(text):
            return code
    key = text.lower().replace(" ", "")
    if key in STAGE_LABELS:
        return key
    return "unknown"


def stage_label(code: str) -> str:
    return STAGE_LABELS.get(code or "unknown", code or "未知")
