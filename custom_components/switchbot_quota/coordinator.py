"""Hourly sampling with persisted attempts and no rapid retries."""

from datetime import timedelta
import logging

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import fetch_quota
from .const import CLOUD_DOMAIN, CONF_SOURCE, DOMAIN, INTERVAL_SECONDS
from .model import next_attempt, observe

_LOGGER = logging.getLogger(__name__)


class QuotaCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry):
        # Own timer: normal HA refresh/reload cannot bypass the persisted throttle.
        super().__init__(hass, _LOGGER, config_entry=entry, name="SwitchBot API quota")
        self.entry = entry
        self.snapshot = {}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}", atomic_writes=True)
        self._cancel_timer = None
        self._stopped = False

    async def async_start(self):
        self.snapshot = await self.store.async_load() or {}
        # Unlike async_config_entry_first_refresh, failures do not cause setup retry.
        await self.async_refresh()

    def stop_timer(self):
        self._stopped = True
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None

    def _arm_timer(self):
        if self._cancel_timer:
            self._cancel_timer()
        if self._stopped or self.hass.is_stopping:
            return
        now = dt_util.utcnow()
        when = next_attempt(self.snapshot, now)
        if when <= now:  # E.g. local storage failed before an attempt was persisted.
            when = now + timedelta(seconds=INTERVAL_SECONDS)
        self._cancel_timer = async_track_point_in_utc_time(self.hass, self._on_timer, when)

    async def _on_timer(self, _now):
        self._cancel_timer = None
        await self.async_refresh()

    async def _async_update_data(self):
        try:
            now = dt_util.utcnow()
            if next_attempt(self.snapshot, now) > now:
                if self.snapshot.get("last_error") or "remaining" not in self.snapshot:
                    raise UpdateFailed(self.snapshot.get("last_error") or "Awaiting hourly sample")
                return dict(self.snapshot)

            # Persist before I/O: even a restart during the request cannot cause a burst.
            self.snapshot.update(last_attempt_at=now.isoformat(), last_error="Sample incomplete")
            await self.store.async_save(self.snapshot)
            try:
                source = self.hass.config_entries.async_get_entry(self.entry.data[CONF_SOURCE])
                if source is None or source.domain != CLOUD_DOMAIN:
                    raise ValueError("Source SwitchBot Cloud entry is missing")
                token, secret = source.data.get("api_token"), source.data.get("api_key")
                if not token or not secret:
                    raise ValueError("Source SwitchBot Cloud credentials are missing")
                remaining, status, date = await fetch_quota(
                    async_get_clientsession(self.hass), token, secret
                )
                self.snapshot = observe(self.snapshot, remaining, dt_util.utcnow(), status, date)
            except ValueError as err:
                self.snapshot["last_error"] = str(err)
                await self.store.async_save(self.snapshot)
                raise UpdateFailed(str(err)) from None
            await self.store.async_save(self.snapshot)
            return dict(self.snapshot)
        finally:
            self._arm_timer()
