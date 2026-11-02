"""LLM 传输错误是否应重试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.llm.client import is_non_retryable_transport_error  # noqa: E402


class RetryPolicyTests(unittest.TestCase):
    def test_dns_errors_are_fatal(self):
        self.assertTrue(
            is_non_retryable_transport_error(
                OSError(
                    "Cannot connect to host api.siliconflow.cn:443 ssl:default "
                    "[Temporary failure in name resolution]"
                )
            )
        )
        self.assertTrue(
            is_non_retryable_transport_error(Exception("getaddrinfo failed"))
        )

    def test_timeout_is_retryable(self):
        self.assertFalse(is_non_retryable_transport_error(TimeoutError()))
        self.assertFalse(is_non_retryable_transport_error(Exception("HTTP 503")))


if __name__ == "__main__":
    unittest.main()
