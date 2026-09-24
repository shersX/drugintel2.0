#!/usr/bin/env python3
"""初始化数据库：启用 pgvector、建表、创建向量索引。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.session import create_vector_indexes, enable_pgvector, get_engine
from backend.src.models import Base  # noqa: F401 — 注册所有表
from backend.src.core.logger import get_logger

logger = get_logger("scripts.init_db")


def main() -> None:
    engine = get_engine()
    logger.info("连接数据库: %s", engine.url.render_as_string(hide_password=True))
    enable_pgvector(engine)
    logger.info("已确保 vector 扩展")
    Base.metadata.create_all(bind=engine)
    logger.info("已创建全部表")
    try:
        create_vector_indexes(engine)
        logger.info("已创建向量索引")
    except RuntimeError as e:
        logger.warning("%s（表为空时部分环境可稍后重试）", e)
    print("init_db OK")


if __name__ == "__main__":
    main()
