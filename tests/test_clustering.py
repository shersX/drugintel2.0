#!/usr/bin/env python3
"""事件聚类单元测试（不联网、不依赖真实库）。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.clustering.clusterer import (
    EventClusterer,
    IncrementalClusterer,
    NewsPoint,
    cosine_similarity,
    mean_centroid,
    update_centroid_weighted,
)
from backend.src.clustering.representative import (
    select_representative_news,
    should_replace_representative,
)


def _unit(vec: list[float]) -> list[float]:
    a = np.asarray(vec, dtype=np.float64)
    n = np.linalg.norm(a)
    return (a / n).tolist() if n > 0 else a.tolist()


class TestClustering(unittest.TestCase):
    def test_cosine_and_centroid(self) -> None:
        a = _unit([1.0, 0.0, 0.0])
        b = _unit([1.0, 0.0, 0.0])
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0, places=5)
        c = mean_centroid([a, _unit([0.0, 1.0, 0.0])])
        self.assertAlmostEqual(float(np.linalg.norm(c)), 1.0, places=5)

    def test_chain_cluster_merges_similar(self) -> None:
        base = _unit([1.0, 0.0, 0.0])
        near = _unit([0.99, 0.1, 0.0])
        far = _unit([0.0, 0.0, 1.0])
        points = [
            NewsPoint(id=1, embedding=base, title="a"),
            NewsPoint(id=2, embedding=near, title="b"),
            NewsPoint(id=3, embedding=far, title="c"),
        ]
        # 提高 mid，使 near 能并入；far 单独成簇
        drafts = EventClusterer(threshold_high=0.9, threshold_mid=0.7).cluster(points)
        self.assertEqual(len(drafts), 2)
        sizes = sorted(len(d.news_ids) for d in drafts)
        self.assertEqual(sizes, [1, 2])

    def test_incremental_assign(self) -> None:
        centroid = _unit([1.0, 0.0, 0.0])
        seed = centroid
        events = [(10, centroid, seed)]
        cl = IncrementalClusterer(threshold_high=0.9, threshold_mid=0.7)
        self.assertEqual(cl.assign(_unit([0.98, 0.1, 0.0]), events), 10)
        self.assertIsNone(cl.assign(_unit([0.0, 1.0, 0.0]), events))

    def test_representative_closest_to_centroid(self) -> None:
        a = NewsPoint(id=1, embedding=_unit([1.0, 0.0, 0.0]), title="a")
        b = NewsPoint(
            id=2,
            embedding=_unit([0.8, 0.6, 0.0]),
            title="b",
            publish_time=datetime(2026, 1, 2),
        )
        c = NewsPoint(
            id=3,
            embedding=_unit([0.95, 0.05, 0.0]),
            title="c",
            publish_time=datetime(2026, 1, 1),
        )
        rep = select_representative_news([a, b, c])
        assert rep is not None
        # a 与中心更近（对称时 a 接近均值方向）
        self.assertIn(rep.id, {1, 3})

    def test_replace_representative_by_time(self) -> None:
        older = NewsPoint(
            id=1,
            embedding=_unit([1.0, 0.0]),
            publish_time=datetime(2026, 1, 1),
        )
        newer = NewsPoint(
            id=2,
            embedding=_unit([1.0, 0.0]),
            publish_time=datetime(2026, 1, 1) + timedelta(days=1),
        )
        self.assertTrue(should_replace_representative(older, newer))
        self.assertFalse(should_replace_representative(newer, older))

    def test_update_centroid_weighted(self) -> None:
        c = _unit([1.0, 0.0])
        x = _unit([0.0, 1.0])
        updated = update_centroid_weighted(c, x, alpha=0.5)
        self.assertAlmostEqual(float(np.linalg.norm(updated)), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
