"""
Client safety invariants. No network.

These are the rules that stop a prototype quietly doing something expensive:
test-mode-only credentials, integer cents, a Current-Merchant header that
cannot be forgotten, and Time-Travel that cannot reach live.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pinch_client import (  # noqa: E402
    BASE_LIVE, BASE_TEST, MerchantScope, PinchClient, _cents,
    credential_or_none, load_dotenv)


class TestCredentialSafety(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("PINCH_APP_ID", "PINCH_SECRET")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_missing_credentials_say_what_to_do(self):
        os.environ["PINCH_APP_ID"] = ""
        os.environ["PINCH_SECRET"] = ""
        with self.assertRaises(RuntimeError) as cm:
            PinchClient.from_env(live=False)
        msg = str(cm.exception)
        self.assertIn("PINCH_APP_ID", msg)
        self.assertIn(".env", msg)

    def test_unfilled_template_counts_as_no_credentials(self):
        """Copying .env.example without editing it must degrade to the
        simulator, not authenticate with placeholder text and fail with an
        opaque 400 from Pinch."""
        os.environ["PINCH_APP_ID"] = "app_test_paste_yours_here"
        os.environ["PINCH_SECRET"] = "sk_test_paste_yours_here"
        self.assertIsNone(credential_or_none("PINCH_APP_ID"))
        self.assertIsNone(credential_or_none("PINCH_SECRET"))
        with self.assertRaises(RuntimeError):
            PinchClient.from_env()

    def test_real_looking_key_is_not_mistaken_for_a_placeholder(self):
        os.environ["PINCH_SECRET"] = "sk_test_9f3Ab2K"
        self.assertEqual(credential_or_none("PINCH_SECRET"),
                         "sk_test_9f3Ab2K")

    def test_live_secret_is_refused(self):
        """The portal issues both Live and Development keys. Pasting the
        wrong one must fail loudly, not quietly touch a real account."""
        os.environ["PINCH_APP_ID"] = "app_abc123"
        os.environ["PINCH_SECRET"] = "sk_live_abc123"
        with self.assertRaises(RuntimeError) as cm:
            PinchClient.from_env()
        self.assertIn("LIVE", str(cm.exception))

    def test_live_base_url_is_refused(self):
        os.environ["PINCH_APP_ID"] = "app_test_abc"
        os.environ["PINCH_SECRET"] = "sk_test_abc"
        with self.assertRaises(RuntimeError):
            PinchClient.from_env(live=True)

    def test_development_keys_are_accepted_and_point_at_test(self):
        os.environ["PINCH_APP_ID"] = "app_test_abc"
        os.environ["PINCH_SECRET"] = "sk_test_abc"
        pc = PinchClient.from_env()
        self.assertFalse(pc.live)
        self.assertEqual(pc.base, BASE_TEST)
        self.assertNotEqual(pc.base, BASE_LIVE)


class TestDotenv(unittest.TestCase):
    def test_real_environment_wins_over_file(self):
        """An explicit export must not be silently overridden by a stale
        .env left over from a previous session."""
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write("PINCH_APP_ID=from_file\nOTHER_KEY=from_file\n")
            path = fh.name
        os.environ["PINCH_APP_ID"] = "from_export"
        os.environ.pop("OTHER_KEY", None)
        try:
            load_dotenv(path)
            self.assertEqual(os.environ["PINCH_APP_ID"], "from_export")
            self.assertEqual(os.environ["OTHER_KEY"], "from_file")
        finally:
            os.environ.pop("OTHER_KEY", None)
            os.unlink(path)

    def test_missing_file_is_not_an_error(self):
        load_dotenv("/nonexistent/.env")

    def test_comments_and_quotes_are_handled(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write('# a comment\n\nQUOTED_KEY="value"\n')
            path = fh.name
        os.environ.pop("QUOTED_KEY", None)
        try:
            load_dotenv(path)
            self.assertEqual(os.environ["QUOTED_KEY"], "value")
        finally:
            os.environ.pop("QUOTED_KEY", None)
            os.unlink(path)


class TestMoney(unittest.TestCase):
    def test_floats_and_bools_rejected(self):
        for bad in (10.0, True, "10", None):
            with self.assertRaises(TypeError):
                _cents(bad)

    def test_ints_pass_through(self):
        self.assertEqual(_cents(3478), 3478)


class TestMerchantHeaderIsStructural(unittest.TestCase):
    def test_base_client_exposes_no_per_merchant_reads(self):
        """A per-merchant call must only be reachable via as_merchant(), so
        the Current-Merchant header cannot be omitted by accident."""
        for name in ("get_payers", "get_plans", "get_subscriptions",
                     "get_processed_payments", "create_payer",
                     "schedule_payment", "create_plan", "create_subscription"):
            self.assertFalse(
                hasattr(PinchClient, name),
                f"PinchClient.{name} would bypass Current-Merchant")
            self.assertTrue(hasattr(MerchantScope, name),
                            f"MerchantScope.{name} is missing")

    def test_as_merchant_rejects_a_non_merchant_id(self):
        pc = PinchClient(app_id="app_test_x", secret="sk_test_x")
        with self.assertRaises(ValueError):
            pc.as_merchant("pyr_wrong_prefix")

    def test_time_travel_cannot_reach_live(self):
        pc = PinchClient(app_id="app_test_x", secret="sk_test_x", live=True)
        with self.assertRaises(RuntimeError):
            pc._request("GET", "/payers", time_travel="2026-08-02T09:45:59Z")


if __name__ == "__main__":
    unittest.main(verbosity=2)
