from sqlalchemy import text
from backend.src.db.session import get_engine

e = get_engine()
with e.connect() as c:
    print("lexicon", c.execute(text("select entity_type, count(*) from entity_lexicon group by 1")).fetchall())
    print("keywords", c.execute(text("select category, count(*) from filter_keyword group by 1")).fetchall())
