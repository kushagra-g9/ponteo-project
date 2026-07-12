"""Unit checks for secret_redaction (run: python3 scripts/test_secret_redaction.py)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from secret_redaction import redact, register_secret  # noqa: E402


class SecretRedactionTests(unittest.TestCase):
    def test_registered_secret_is_redacted(self) -> None:
        register_secret("super-secret-token-value")
        text = "Error: auth failed with super-secret-token-value in URL"
        self.assertNotIn("super-secret-token-value", redact(text))
        self.assertIn("[REDACTED]", redact(text))

    def test_google_chat_webhook_pattern(self) -> None:
        url = "https://chat.googleapis.com/v1/spaces/AAA/messages?key=abc&token=xyz"
        self.assertEqual(redact(url), "[REDACTED]")

    def test_bearer_token_pattern(self) -> None:
        result = redact("Authorization: Bearer squ_abc123def456")
        self.assertNotIn("squ_abc123def456", result)
        self.assertIn("[REDACTED]", result)


if __name__ == "__main__":
    unittest.main()
