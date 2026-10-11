#!/usr/bin/env python3
"""初始化数据库：启用 pgvector、建表、创建向量索引。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.schema import ensure_schema


def main() -> None:
    ensure_schema()
    print("init_db OK")


if __name__ == "__main__":
    main()
