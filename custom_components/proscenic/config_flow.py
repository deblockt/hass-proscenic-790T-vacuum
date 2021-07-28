from homeassistant import config_entries
from .const import DOMAIN

import voluptuous as vol

from homeassistant.core import callback

from homeassistant.const import CONF_HOST
from .const import CONF_DEVICE_ID, CONF_TOKEN, CONF_USER_ID, CONF_AUTH_CODE, CONF_SLEEP, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, DEFAULT_CONF_SLEEP

class ProscenicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get option flow."""
        return ProscenicOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # See next section on create entry usage
            return self.async_create_entry(
                title="proscenic vacuum configuration",
                data= {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_USER_ID: user_input[CONF_USER_ID],
                    CONF_AUTH_CODE: user_input[CONF_AUTH_CODE]
                }
            )


        schema = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_TOKEN): str,
            vol.Required(CONF_USER_ID): str,
            vol.Required(CONF_AUTH_CODE): str
        }

        return self.async_show_form(
            step_id='user', data_schema=vol.Schema(schema)
        )

class ProscenicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry):
        """Initialize the options flow."""
        self.config_entry = config_entry
        self._sleep_duration_on_exit = self.config_entry.options.get(
            CONF_SLEEP, DEFAULT_CONF_SLEEP
        )
        self._map_path = self.config_entry.options.get(
            CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        options_schema = vol.Schema(
            {
                vol.Required(CONF_SLEEP, default = self._sleep_duration_on_exit): int,
                vol.Required(CONF_MAP_PATH, default = self._map_path): str,
            },
        )

        if user_input is not None:
            return self.async_create_entry(title='proscenic vacuum configuration', data=user_input)

        return self.async_show_form(step_id='init', data_schema=options_schema)
