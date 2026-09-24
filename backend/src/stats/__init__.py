"""统计模块导出。"""

from backend.src.stats.service import (
    development_stage_stats,
    hot_keywords_stats,
    news_trend_stats,
    overview_stats,
)

__all__ = [
    "overview_stats",
    "development_stage_stats",
    "news_trend_stats",
    "hot_keywords_stats",
]
