"""实体抽取连续失败断路，避免拖死整批。"""

from __future__ import annotations

import asyncio
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.core.config import EntityEnvConfig  # noqa: E402
from backend.src.entities import extract as extract_mod  # noqa: E402


class EntityCircuitTests(unittest.TestCase):
    def test_skips_rest_after_consecutive_failures(self):
        items = [
            {"title": f"t{i}", "abstract": "a", "full_text": "c"} for i in range(5)
        ]

        async def _boom(*_a, **_k):
            raise OSError(
                "Cannot connect to host api.siliconflow.cn:443 "
                "[Temporary failure in name resolution]"
            )

        @contextmanager
        def _scope():
            yield MagicMock()

        extract_one = AsyncMock(side_effect=_boom)
        with (
            patch.object(
                extract_mod.EntityEnvConfig,
                "load",
                return_value=EntityEnvConfig(
                    api_key="k",
                    base_url="https://example.com/v1",
                    model="m",
                    timeout_sec=1,
                    max_retries=1,
                ),
            ),
            patch.object(extract_mod, "extract_one", extract_one),
            patch.object(extract_mod, "_crawl_cancel_requested", return_value=False),
            patch.object(
                extract_mod,
                "normalize_and_feedback",
                return_value={
                    "products": [],
                    "drugs": [],
                    "orgs": [],
                    "targets": [],
                    "indications": [],
                    "entity_raw": {},
                },
            ),
            patch.object(extract_mod, "session_scope", _scope),
        ):
            out = asyncio.run(
                extract_mod.extract_and_normalize_items(items, max_concurrency=1)
            )

        self.assertEqual(len(out), 5)
        self.assertEqual(extract_one.await_count, 2)
        for item in out:
            self.assertEqual(item.get("story_type"), "other")
            self.assertEqual(item.get("products"), [])


if __name__ == "__main__":
    unittest.main()
