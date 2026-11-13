"""Run in an isolated HA Python process: fake HTTP, store, clock and scheduler only."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "switchbot_quota"
package = types.ModuleType("quota_runtime_test")
package.__path__ = [str(ROOT)]
sys.modules["quota_runtime_test"] = package
from quota_runtime_test import api, coordinator
from quota_runtime_test.model import observe


class FakeStore:
    def __init__(self):
        self.saved = []

    async def async_save(self, value):
        self.saved.append(dict(value))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.at = datetime(2026, 11, 11, 10, tzinfo=timezone.utc)
        self.c = coordinator.QuotaCoordinator.__new__(coordinator.QuotaCoordinator)
        self.c.snapshot = {}
        self.c.store = FakeStore()
        source = types.SimpleNamespace(domain="switchbot_cloud", data={"api_token": "test", "api_key": "test"})
        self.c.hass = types.SimpleNamespace(is_stopping=False,
            config_entries=types.SimpleNamespace(async_get_entry=lambda _: source))
        self.c.entry = types.SimpleNamespace(data={"source_entry_id": "test"})
        self.c._cancel_timer = None
        self.c._stopped = False
        self.clock = patch.object(coordinator.dt_util, "utcnow", return_value=self.at).start()
        self.fetch = patch.object(coordinator, "fetch_quota", AsyncMock(return_value=(500, 200, ""))).start()
        patch.object(coordinator, "async_get_clientsession", return_value=object()).start()
        self.timer = patch.object(coordinator, "async_track_point_in_utc_time", return_value=Mock()).start()
        self.addCleanup(patch.stopall)

    async def test_one_request_persist_before_io_and_next_hour(self):
        async def response(*args):
            self.assertEqual(len(self.c.store.saved), 1)
            self.assertEqual(self.c.store.saved[0]["last_attempt_at"], self.at.isoformat())
            return 500, 200, ""
        self.fetch.side_effect = response
        await self.c._async_update_data()
        await self.c._async_update_data()  # manual refresh/reload cache
        self.fetch.assert_awaited_once()
        self.assertEqual(self.timer.call_args.args[2], self.at + timedelta(hours=1))

    async def test_failure_does_not_zero_or_retry_and_recovers(self):
        self.c.snapshot = observe({}, 400, self.at - timedelta(hours=1), 200, "")
        self.fetch.side_effect = ValueError("Missing or invalid X-RateLimit-Remaining header")
        for _ in range(2):
            with self.assertRaises(coordinator.UpdateFailed):
                await self.c._async_update_data()
        self.fetch.assert_awaited_once()
        self.assertEqual(self.c.snapshot["remaining"], 400)
        self.assertNotIn("last_increase_observed_at", self.c.snapshot)
        self.clock.return_value = self.at + timedelta(hours=1)
        self.fetch.side_effect = None
        await self.c._async_update_data()
        self.assertEqual(self.fetch.await_count, 2)
        self.assertEqual(self.c.snapshot["increase_window_start"], (self.at - timedelta(hours=1)).isoformat())

    async def test_restart_while_request_incomplete_waits(self):
        self.c.snapshot = {"last_attempt_at": self.at.isoformat(), "last_error": "Sample incomplete"}
        with self.assertRaises(coordinator.UpdateFailed):
            await self.c._async_update_data()
        self.fetch.assert_not_awaited()
        self.assertEqual(self.timer.call_args.args[2], self.at + timedelta(hours=1))

    async def test_credentials_are_read_each_time_and_removal_fails_closed(self):
        self.c.hass.config_entries.async_get_entry = lambda _: None
        with self.assertRaises(coordinator.UpdateFailed):
            await self.c._async_update_data()
        self.fetch.assert_not_awaited()

    async def test_storage_failure_prevents_http(self):
        self.c.store.async_save = AsyncMock(side_effect=OSError("fixture storage failure"))
        with self.assertRaises(OSError):
            await self.c._async_update_data()
        self.fetch.assert_not_awaited()

    async def test_unload_cancels_timer(self):
        self.c._arm_timer()
        cancel = self.c._cancel_timer
        self.c.stop_timer()
        cancel.assert_called_once()
        self.timer.reset_mock()
        self.c._arm_timer()
        self.timer.assert_not_called()

    async def test_http_call_has_no_redirect_or_retry_and_ignores_body(self):
        response = Mock(status=429, headers={"X-RateLimit-Remaining": "0"})
        context = AsyncMock()
        context.__aenter__.return_value = response
        session = Mock()
        session.get.return_value = context
        result = await api.fetch_quota(session, "fixture-token", "fixture-secret")
        self.assertEqual(result[:2], (0, 429))
        session.get.assert_called_once()
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])
        response.json.assert_not_called()
        response.text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
