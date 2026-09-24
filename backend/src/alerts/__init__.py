"""告警模块导出。"""

from backend.src.alerts.matcher import (
    create_watchlist,
    delete_watchlist,
    list_watchlists,
    match_news_to_watchlists,
    process_alerts_for_news,
    send_email,
)

__all__ = [
    "list_watchlists",
    "create_watchlist",
    "delete_watchlist",
    "match_news_to_watchlists",
    "process_alerts_for_news",
    "send_email",
]
