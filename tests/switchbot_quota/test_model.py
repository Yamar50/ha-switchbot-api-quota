"""Run with stdlib unittest, no HA or live API required."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "switchbot_quota"
package = types.ModuleType("quota_test")
package.__path__ = [str(ROOT)]
sys.modules["quota_test"] = package
from quota_test.model import next_attempt, observe, parse_remaining


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 11, 11, 10, tzinfo=timezone.utc)

    def test_http_200_and_exhausted_429(self):
        for status, value in ((200, "9507"), (429, "0")):
            self.assertEqual(parse_remaining(status, {"X-RateLimit-Remaining": value}), int(value))

    def test_invalid_response_never_becomes_zero(self):
        for headers in ({}, {"x-ratelimit-remaining": "unknown"},
                        {"x-ratelimit-remaining": "-1"}, {"x-ratelimit-remaining": "1.5"}):
            with self.assertRaises(ValueError):
                parse_remaining(200, headers)
        for status in (301, 401, 403, 500):
            with self.assertRaises(ValueError):
                parse_remaining(status, {"x-ratelimit-remaining": "9000"})

    def test_first_sample_is_not_reset(self):
        data = observe({}, 9507, self.at, 200, "Wed, 11 Nov 2026 10:00:00 GMT")
        self.assertNotIn("last_increase_observed_at", data)
        self.assertEqual(data["server_date"], self.at.isoformat())

    def test_decrease_equal_then_increase_preserves_window(self):
        data = observe({}, 100, self.at, 200, "")
        for i, count in enumerate((50, 50), 1):
            data = observe(data, count, self.at + timedelta(hours=i), 200, "")
            self.assertNotIn("last_increase_observed_at", data)
        data = observe(data, 9999, self.at + timedelta(hours=3), 200, "")
        self.assertEqual(data["increase_window_start"], (self.at + timedelta(hours=2)).isoformat())
        self.assertEqual(data["remaining_before_increase"], 50)
        self.assertEqual(data["increases_observed"], 1)
        later = observe(data, 9800, self.at + timedelta(hours=4), 200, "")
        self.assertEqual(later["last_increase_observed_at"], data["last_increase_observed_at"])

    def test_failed_gap_uses_last_success_not_last_attempt(self):
        data = observe({}, 0, self.at, 429, "")
        data.update(last_attempt_at=(self.at + timedelta(hours=1)).isoformat(), last_error="timeout")
        result = observe(data, 9800, self.at + timedelta(hours=2), 200, "")
        self.assertEqual(result["increase_window_start"], self.at.isoformat())
        self.assertIsNone(result["last_error"])

    def test_persisted_attempt_guards_restart_and_manual_update(self):
        snapshot = {"last_attempt_at": self.at.isoformat()}
        for seconds in (0, 1, 3599):
            self.assertEqual(next_attempt(snapshot, self.at + timedelta(seconds=seconds)),
                             self.at + timedelta(hours=1))
        self.assertEqual(next_attempt(snapshot, self.at + timedelta(hours=2)),
                         self.at + timedelta(hours=2))


if __name__ == "__main__":
    unittest.main()
