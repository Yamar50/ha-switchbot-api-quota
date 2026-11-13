"""Select existing HA credentials without another login or validation request."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow

from .const import CLOUD_DOMAIN, CONF_SOURCE, DOMAIN


class SwitchBotQuotaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        sources = {entry.entry_id: entry.title
                   for entry in self.hass.config_entries.async_entries(CLOUD_DOMAIN)}
        if not sources:
            return self.async_abort(reason="no_cloud_entry")
        if user_input is not None and user_input.get(CONF_SOURCE) in sources:
            await self.async_set_unique_id(user_input[CONF_SOURCE])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="SwitchBot API", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_SOURCE, default=next(iter(sources))): vol.In(sources)
        }))
