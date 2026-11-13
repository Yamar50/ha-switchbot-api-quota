"""Sensor semantics against real Home Assistant classes, without network I/O."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "switchbot_quota"
package = types.ModuleType("quota_entity_test")
package.__path__ = [str(ROOT)]
sys.modules["quota_entity_test"] = package
from quota_entity_test.sensor import QuotaSensor


class EntityTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = types.SimpleNamespace(
            entry=types.SimpleNamespace(data={"source_entry_id": "fixture-account"}),
            snapshot={},
            last_update_success=True,
        )

    def test_no_initial_sample_is_not_zero_or_reset(self):
        self.assertIsNone(QuotaSensor(self.coordinator, "remaining").native_value)
        self.assertIsNone(QuotaSensor(self.coordinator, "last_increase").native_value)

    def test_failure_keeps_historical_increase_available(self):
        self.coordinator.last_update_success = False
        self.coordinator.snapshot = {
            "remaining": 8000,
            "last_increase_observed_at": "2026-11-12T01:00:00+00:00",
        }
        self.assertFalse(QuotaSensor(self.coordinator, "remaining").available)
        increase = QuotaSensor(self.coordinator, "last_increase")
        self.assertTrue(increase.available)
        self.assertEqual(increase.native_value,
                         datetime(2026, 11, 12, 1, tzinfo=timezone.utc))

    def test_distinct_accounts_have_distinct_registry_identity(self):
        first = QuotaSensor(self.coordinator, "remaining")
        self.coordinator.entry = types.SimpleNamespace(
            data={"source_entry_id": "second-fixture-account"}
        )
        second = QuotaSensor(self.coordinator, "remaining")
        self.assertNotEqual(first.unique_id, second.unique_id)
        self.assertNotEqual(first.device_info["identifiers"],
                            second.device_info["identifiers"])

    def test_private_installation_identity_and_unit_are_preserved(self):
        sensor = QuotaSensor(self.coordinator, "remaining")
        self.assertEqual(sensor.unique_id, "fixture-account_remaining")
        self.assertEqual(sensor.entity_id, "sensor.switchbot_api_remaining")
        self.assertEqual(sensor.native_unit_of_measurement, "回")
        self.assertEqual(sensor.translation_key, "remaining")

    def test_attribute_allowlist_does_not_expose_arbitrary_snapshot_fields(self):
        self.coordinator.snapshot = {
            "remaining": 0, "http_status": 429,
            "last_attempt_at": "2026-11-12T01:00:00+00:00",
            "api_token": "fixture-do-not-expose",
            "deviceList": ["fixture-private-device"],
        }
        sensor = QuotaSensor(self.coordinator, "remaining")
        self.assertEqual(sensor.native_value, 0)
        self.assertEqual(sensor.extra_state_attributes["next_attempt_at"],
                         "2026-11-12T02:00:00+00:00")
        self.assertNotIn("api_token", sensor.extra_state_attributes)
        self.assertNotIn("deviceList", sensor.extra_state_attributes)


if __name__ == "__main__":
    unittest.main()
