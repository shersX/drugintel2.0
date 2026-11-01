"""一次性：ensure_schema + TRUNCATE news/event。"""
from sqlalchemy import text

from backend.src.db.schema import ensure_schema
from backend.src.db.session import get_engine

ensure_schema()
eng = get_engine()
with eng.begin() as c:
    c.execute(text("TRUNCATE news, event RESTART IDENTITY CASCADE"))
    n = c.execute(text("SELECT count(*) FROM entity_lexicon")).scalar()
    cols = c.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='news' AND column_name IN ('products','story_type')"
        )
    ).fetchall()
    print("truncate ok; lexicon=", n, "news_cols=", cols)
