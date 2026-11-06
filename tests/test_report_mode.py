"""report_mode 判定。"""

from __future__ import annotations

import unittest

from backend.src.agents.analyst import resolve_report_mode


class ReportModeTests(unittest.TestCase):
    def test_clinical(self):
        self.assertEqual(
            resolve_report_mode(
                products=["wegovy"], drugs=[], orgs=["novo"], story_types=["clinical", "deal"]
            ),
            "clinical_asset",
        )

    def test_deal(self):
        self.assertEqual(
            resolve_report_mode(products=[], drugs=[], orgs=["lilly"], story_types=["financing"]),
            "deal_capital",
        )

    def test_general(self):
        self.assertEqual(
            resolve_report_mode(products=[], drugs=[], orgs=[], story_types=["conference"]),
            "general_intel",
        )


if __name__ == "__main__":
    unittest.main()
