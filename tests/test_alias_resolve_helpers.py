"""别名合并辅助逻辑（不打外网）。"""

from __future__ import annotations

import unittest

from backend.src.entities.alias_resolve import (
    _cjk_latin_pair,
    _cosine,
    _ordered_ids,
    _has_cjk,
    _is_latinish,
)


class AliasResolveHelperTests(unittest.TestCase):
    def test_cjk_latin(self):
        self.assertTrue(_has_cjk("礼来"))
        self.assertTrue(_is_latinish("Lilly"))
        self.assertTrue(_cjk_latin_pair("礼来", "Lilly"))
        self.assertFalse(_cjk_latin_pair("礼来", "辉瑞"))

    def test_ordered_ids(self):
        self.assertEqual(_ordered_ids(3, 1), (1, 3))
        self.assertEqual(_ordered_ids(2, 2), (2, 2))

    def test_cosine(self):
        self.assertAlmostEqual(_cosine([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(_cosine([1, 0], [0, 1]), 0.0)


if __name__ == "__main__":
    unittest.main()
