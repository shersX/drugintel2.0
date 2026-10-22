"""阶段、分子类型与名称归一。"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.src.models.entities import Company

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

# 进度条可视化顺序（含申报）
STAGE_BAR_ORDER = ["preclinical", "phase1", "phase2", "phase3", "nda", "approved"]

MODALITY_LABELS = {
    "small_molecule": "小分子",
    "antibody": "抗体",
    "cell_therapy": "细胞治疗",
    "gene_therapy": "基因治疗",
    "nucleic_acid": "核酸药物",
    "other": "其他",
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

_MODALITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"小分子|small\s*mol|chemical|化合物", re.I), "small_molecule"),
    (re.compile(r"单克隆抗体|单抗|抗体|mab|antibody|双抗|adc", re.I), "antibody"),
    (re.compile(r"细胞治疗|car[- ]?t|tcr|cell\s*therap", re.I), "cell_therapy"),
    (re.compile(r"基因治疗|gene\s*therap|aav|viral\s*vector", re.I), "gene_therapy"),
    (re.compile(r"核酸|aso|sirna|mrna|oligonucleotide|核酸药物", re.I), "nucleic_acid"),
    (re.compile(r"多肽|peptide|复方", re.I), "other"),
]


def normalize_drug_code(name: str) -> str:
    text = (name or "").strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\s\-_/]+", "", text)
    if re.search(r"[A-Za-z0-9]", text):
        return text.upper()
    return text


def normalize_indication(text: str) -> str:
    value = unicodedata.normalize("NFKC", (text or "").strip())
    value = re.sub(r"\s+", "", value)
    return value[:500]


def normalize_target(text: Optional[str]) -> Optional[str]:
    value = unicodedata.normalize("NFKC", (text or "").strip())
    value = re.sub(r"\s+", " ", value)
    return value[:200] or None


def normalize_stage(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    code_key = text.upper().replace(" ", "").replace("-", "")
    aliases = {
        "PHASE1": "phase1",
        "PHASE2": "phase2",
        "PHASE3": "phase3",
        "MARKETED": "approved",
        "APPROVED": "approved",
        "PRECLINICAL": "preclinical",
        "NDA": "nda",
        "BLA": "nda",
    }
    if code_key in aliases:
        return aliases[code_key]
    for pattern, code in _STAGE_PATTERNS:
        if pattern.search(text):
            return code
    key = text.lower().replace(" ", "")
    if key in STAGE_LABELS:
        return key
    return "unknown"


def normalize_modality(raw: Optional[str]) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    key = text.lower().replace(" ", "_").replace("-", "_")
    if key in MODALITY_LABELS:
        return key
    for pattern, code in _MODALITY_PATTERNS:
        if pattern.search(text):
            return code
    return "unknown"


def stage_label(code: str) -> str:
    return STAGE_LABELS.get(code or "unknown", code or "未知")


def modality_label(code: str) -> str:
    return MODALITY_LABELS.get(code or "unknown", code or "未知")


def stage_bar_index(code: str) -> int:
    """进度条填充到的节点下标；未知不填满。"""
    c = code or "unknown"
    if c in STAGE_BAR_ORDER:
        return STAGE_BAR_ORDER.index(c)
    return -1


def company_name_key(text: Optional[str]) -> str:
    return unicodedata.normalize("NFKC", (text or "").strip()).casefold()


def looks_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def display_company_name(company: Optional["Company"]) -> Optional[str]:
    """前端优先中文：name_zh → name。"""
    if company is None:
        return None
    zh = (company.name_zh or "").strip()
    if zh:
        return zh
    return company.name
