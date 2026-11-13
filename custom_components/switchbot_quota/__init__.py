"""Observe the server-reported SwitchBot request allowance."""

from homeassistant.const import Platform
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import QuotaCoordinator


async def async_setup_entry(hass, entry):
    coordinator = QuotaCoordinator(hass, entry)
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.stop_timer)
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR]):
        entry.runtime_data.stop_timer()
        return True
    return False


async def async_remove_entry(hass, entry):
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
