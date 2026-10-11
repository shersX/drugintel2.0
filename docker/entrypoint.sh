#!/bin/sh
# 先确保表存在，再执行镜像 CMD（API / worker / beat 共用）。
set -e
i=0
until python -c "from backend.src.db.schema import ensure_schema; ensure_schema()"; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "ensure_schema failed"
    exit 1
  fi
  echo "waiting for database..."
  sleep 2
done
exec "$@"
