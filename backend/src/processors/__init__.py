"""数据处理模块。"""

from backend.src.processors.deduplicator import deduplicate_by_title, normalize_title
from backend.src.processors.embedding import embed_items
from backend.src.processors.filter import (
    filter_news_items,
    filter_results_by_keywords,
    load_keyword_lexicon,
    load_keywords_config,
)
from backend.src.processors.pipeline import run_processing_pipeline
from backend.src.processors.relevance import (
    SKIP_RELEVANCE_CRAWLERS,
    isrelated_for_item,
)
from backend.src.processors.summarizer import summarize_items

__all__ = [
    "filter_news_items",
    "filter_results_by_keywords",
    "load_keyword_lexicon",
    "load_keywords_config",
    "isrelated_for_item",
    "SKIP_RELEVANCE_CRAWLERS",
    "deduplicate_by_title",
    "normalize_title",
    "summarize_items",
    "embed_items",
    "run_processing_pipeline",
]
