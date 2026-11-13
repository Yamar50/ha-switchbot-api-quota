"""Remaining allowance and last observed increase, recorded by HA history."""

from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SOURCE, DOMAIN, INTERVAL_SECONDS
from .model import next_attempt


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([QuotaSensor(entry.runtime_data, "remaining"),
                        QuotaSensor(entry.runtime_data, "last_increase")])


class QuotaSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        source = coordinator.entry.data[CONF_SOURCE]
        self._attr_unique_id = f"{source}_{key}"
        # A stable suggestion; HA's registry resolves collisions and keeps user renames.
        self.entity_id = f"sensor.switchbot_api_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, source)}, name="SwitchBot API", manufacturer="SwitchBot",
            model="OpenAPI request allowance",
        )
        if key == "remaining":
            self._attr_icon = "mdi:counter"
            self._attr_native_unit_of_measurement = "回"
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_force_update = True
        else:
            self._attr_icon = "mdi:clock-check-outline"
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def available(self):
        # Historical observation remains valid even if today's request fails.
        return self.key == "last_increase" or super().available

    @property
    def native_value(self):
        data = self.coordinator.snapshot
        if self.key == "remaining":
            return data.get("remaining")
        value = data.get("last_increase_observed_at")
        return datetime.fromisoformat(value) if value else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.snapshot
        if self.key == "last_increase":
            return {key: data.get(key) for key in (
                "increase_window_start", "last_increase_observed_at",
                "remaining_before_increase", "remaining_after_increase", "increases_observed"
            )}
        attrs = {key: data.get(key) for key in (
            "observed_at", "last_attempt_at", "http_status", "server_date", "last_error"
        )}
        attrs["poll_interval_seconds"] = INTERVAL_SECONDS
        if data.get("last_attempt_at"):
            at = datetime.fromisoformat(data["last_attempt_at"])
            attrs["next_attempt_at"] = next_attempt(data, at).isoformat()
        return attrs
