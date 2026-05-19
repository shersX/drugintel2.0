"""关键词筛选工具
根据 `config/keywords.yaml` 中的配置，筛选爬虫结果，只保留正文包含
任一目标关键词的新闻，并在结果上标注匹配到的关键词列表。

YAML 约定：
- 顶层仅 `靶点`、`公司` 两类；其下「规范名（主键）→ 别名列表」。
- 匹配词 = 主键 ∪ 别名；纯中文词条用子串匹配，含英文/数字/符号的词条
  用词界类匹配（预编译正则），中英混合词条辅以子串回退。
- 命中结果写入每条新闻的 `matched_keywords`：`{"靶点": "A,B", "公司": ""}`。

性能：KeywordMatcher 将词表拆为「纯中文 / 拉丁词界」两路预编译正则，每篇正文
仅做少量 findall，避免对数千词条逐条 re.search。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import yaml

# filter.py 位于 backend/src/processors/，向上 4 级到项目根
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KEYWORD_CONFIG = PROJECT_ROOT / "config" / "keywords.yaml"

_PURE_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_HAS_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _normalize_term(term: str) -> str:
    return term.strip()


def _is_pure_cjk(term: str) -> bool:
    if not term:
        return False
    return bool(_PURE_CJK_RE.fullmatch(term))


def _is_mixed_cjk_latin(term: str) -> bool:
    """同时含中文与非中文（如 抗PD-1），词界正则不可靠，走子串回退。"""
    if not term or _is_pure_cjk(term):
        return False
    return bool(_HAS_CJK_RE.search(term))


def _compile_alternation_pattern(
    terms: Sequence[str],
    *,
    prefix: str,
    suffix: str,
) -> Optional[re.Pattern[str]]:
    """将全部词条编译为单个预编译正则（长词在前）。"""
    if not terms:
        return None
    ordered = sorted(set(terms), key=lambda x: len(x), reverse=True)
    body = "|".join(re.escape(t) for t in ordered)
    return re.compile(f"{prefix}(?:{body}){suffix}")


def _collect_terms_from_map(
    keyword_map: Mapping[str, Sequence[str]],
) -> Tuple[Dict[str, str], List[str], List[str], List[str]]:
    """构建 term→canonical，并分出纯中文 / 拉丁 / 中英混合三类词条。"""
    term_to_canonical: Dict[str, str] = {}
    cjk_terms: List[str] = []
    latin_terms: List[str] = []
    mixed_terms: List[str] = []

    for canonical, aliases in keyword_map.items():
        if not isinstance(canonical, str) or not canonical.strip():
            continue
        key = canonical.strip()
        raw_terms = [key]
        if aliases:
            raw_terms.extend(aliases)
        for term in raw_terms:
            if not isinstance(term, str):
                continue
            clean = _normalize_term(term)
            if not clean:
                continue
            if clean not in term_to_canonical:
                term_to_canonical[clean] = key
            if _is_pure_cjk(clean):
                cjk_terms.append(clean)
            elif _is_mixed_cjk_latin(clean):
                mixed_terms.append(clean)
            else:
                latin_terms.append(clean)

    return term_to_canonical, cjk_terms, latin_terms, mixed_terms


@dataclass(frozen=True)
class KeywordLexicon:
    """扁平关键词表 + 规范名所属分类（供前端配色）。"""

    keyword_map: Mapping[str, Sequence[str]]
    category_by_canonical: Mapping[str, str]


@lru_cache(maxsize=1)
def load_keyword_lexicon(config_path: Optional[str | Path] = None) -> KeywordLexicon:
    """
    读取关键词 YAML，合并「靶点」「公司」及可选的旧版顶层 `keywords`。
    """
    path = Path(config_path) if config_path else DEFAULT_KEYWORD_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"未找到关键词配置文件: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, Mapping):
        raise ValueError("keywords.yaml 根节点应为字典")

    merged: Dict[str, List[str]] = {}
    category_by_canonical: Dict[str, str] = {}

    def _ingest_block(block: Mapping, category: str) -> None:
        for canonical, aliases in block.items():
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            key = canonical.strip()
            terms: List[str] = []
            for term in [key, *((aliases or []) if isinstance(aliases, list) else [])]:
                if isinstance(term, str):
                    clean = _normalize_term(term)
                    if clean:
                        terms.append(clean)
            if not terms:
                continue
            deduped = sorted(set(terms), key=terms.index)
            merged[key] = deduped
            category_by_canonical[key] = category

    for cat in ("靶点", "公司"):
        blk = data.get(cat)
        if isinstance(blk, Mapping):
            _ingest_block(blk, cat)

    legacy = data.get("keywords")
    if isinstance(legacy, Mapping):
        for canonical, aliases in legacy.items():
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            key = canonical.strip()
            terms: List[str] = []
            for term in [key, *((aliases or []) if isinstance(aliases, list) else [])]:
                if isinstance(term, str):
                    clean = _normalize_term(term)
                    if clean:
                        terms.append(clean)
            if terms:
                deduped = sorted(set(terms), key=terms.index)
                merged[key] = deduped
                category_by_canonical.setdefault(key, "未分类")

    if not merged:
        raise ValueError(
            "keywords.yaml 未解析到任何关键词，请检查是否包含「靶点」「公司」或顶层 keywords"
        )

    return KeywordLexicon(keyword_map=merged, category_by_canonical=category_by_canonical)


def load_keywords_config(config_path: Optional[str | Path] = None) -> Dict[str, List[str]]:
    """兼容旧接口：仅返回 canonical → 别名列表。"""
    return dict(load_keyword_lexicon(config_path).keyword_map)


@dataclass(frozen=True)
class KeywordMatcher:
    """根据配置匹配正文中的关键词（双通道预编译正则）。"""

    keyword_map: Mapping[str, Sequence[str]]

    def __post_init__(self) -> None:
        term_to_canonical, cjk_terms, latin_terms, mixed_terms = _collect_terms_from_map(
            self.keyword_map
        )
        cjk_pattern = _compile_alternation_pattern(cjk_terms, prefix="", suffix="")
        latin_pattern = _compile_alternation_pattern(
            latin_terms, prefix=r"(?<!\w)", suffix=r"(?!\w)"
        )
        object.__setattr__(self, "_term_to_canonical", term_to_canonical)
        object.__setattr__(self, "_cjk_pattern", cjk_pattern)
        object.__setattr__(self, "_latin_pattern", latin_pattern)
        object.__setattr__(self, "_mixed_terms", tuple(sorted(set(mixed_terms), key=len, reverse=True)))

    def _canonicals_from_pattern(self, text: str, pattern: Optional[re.Pattern[str]]) -> set[str]:
        if pattern is None:
            return set()
        matched: set[str] = set()
        term_map = self._term_to_canonical
        for term in pattern.findall(text):
            canonical = term_map.get(term)
            if canonical:
                matched.add(canonical)
        return matched

    def match_text(self, text: str) -> List[str]:
        """返回命中的规范名（canonical）列表，去重、排序。"""
        if not text or not isinstance(text, str):
            return []

        matched_canonicals = self._canonicals_from_pattern(text, self._cjk_pattern)
        matched_canonicals |= self._canonicals_from_pattern(text, self._latin_pattern)

        if self._mixed_terms:
            term_map = self._term_to_canonical
            for term in self._mixed_terms:
                if term in text:
                    canonical = term_map.get(term)
                    if canonical:
                        matched_canonicals.add(canonical)

        return sorted(matched_canonicals)


def _ensure_matcher(
    matcher: Optional[KeywordMatcher],
    keywords_config: Optional[Mapping[str, Sequence[str]]] = None,
) -> KeywordMatcher:
    if matcher:
        return matcher
    keywords = keywords_config or load_keywords_config()
    return KeywordMatcher(keywords)


_CATEGORY_KEYS = ("靶点", "公司")


def _combined_news_text(item: MutableMapping) -> str:
    """匹配用文本：标题 + 正文（不含简介）。"""
    title = item.get("title", "") or ""
    full_text = item.get("full_text", "") or ""
    return f"{title} {full_text}".strip()


def _annotate_matches(
    item: MutableMapping,
    matched: List[str],
    category_by_canonical: Mapping[str, str],
) -> None:
    by_category: Dict[str, List[str]] = {key: [] for key in _CATEGORY_KEYS}
    for canonical in matched:
        category = category_by_canonical.get(canonical, "")
        if category in by_category:
            by_category[category].append(canonical)
    item["matched_keywords"] = {
        key: ",".join(sorted(set(by_category[key]))) for key in _CATEGORY_KEYS
    }


def filter_news_items(
    news_items: Iterable[MutableMapping],
    matcher: Optional[KeywordMatcher] = None,
    keywords_config: Optional[Mapping[str, Sequence[str]]] = None,
    category_by_canonical: Optional[Mapping[str, str]] = None,
) -> List[MutableMapping]:
    """
    对单个爬虫的新闻列表进行关键词筛选。

    Args:
        news_items: 新闻列表，元素建议包含 title、full_text。
    """
    lex = load_keyword_lexicon()
    cats = category_by_canonical or lex.category_by_canonical

    keyword_matcher = _ensure_matcher(matcher, keywords_config)
    filtered: List[MutableMapping] = []

    for item in news_items or []:
        if not isinstance(item, MutableMapping):
            continue

        combined_text = _combined_news_text(item)
        if not combined_text:
            continue

        matched = keyword_matcher.match_text(combined_text)
        if matched:
            _annotate_matches(item, matched, cats)
            filtered.append(item)

    return filtered


def filter_results_by_keywords(
    crawler_results: Mapping[str, Sequence[MutableMapping]],
    matcher: Optional[KeywordMatcher] = None,
    keywords_config: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[MutableMapping]]:
    """
    针对 run_all_crawlers 的返回值做筛选。

    bioon：不丢弃新闻，仅标注 matched_keywords（按靶点/公司分组）；
    其他爬虫：仅保留至少命中一条关键词的条目。
    """
    lexicon = load_keyword_lexicon()
    keyword_matcher = _ensure_matcher(
        matcher, keywords_config or lexicon.keyword_map
    )
    cats = lexicon.category_by_canonical
    filtered_results: Dict[str, List[MutableMapping]] = {}

    for crawler_name, news_items in (crawler_results or {}).items():
        if crawler_name == "bioon" or crawler_name == "prnewswire":
            processed_items: List[MutableMapping] = []
            for item in news_items:
                if not isinstance(item, MutableMapping):
                    continue
                combined_text = _combined_news_text(item)
                matched = keyword_matcher.match_text(combined_text) if combined_text else []
                _annotate_matches(item, matched, cats)
                processed_items.append(item)
            filtered_results[crawler_name] = processed_items
        else:
            filtered_results[crawler_name] = filter_news_items(
                news_items=news_items,
                matcher=keyword_matcher,
                keywords_config=lexicon.keyword_map,
                category_by_canonical=cats,
            )

    return filtered_results
