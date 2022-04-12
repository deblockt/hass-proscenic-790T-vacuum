from homeassistant import config_entries
from .const import DOMAIN

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import SelectSelector

from .const import LOCAL_MODE, CLOUD_MODE, CONF_CONNECTION_MODE, CONF_DEVICE_ID, CONF_TARGET_ID, CONF_TOKEN, CONF_USER_ID, CONF_AUTH_CODE, CONF_SLEEP, DEFAULT_CONF_SLEEP

class ProscenicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get option flow."""
        return ProscenicOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        schema = {
            vol.Required(CONF_CONNECTION_MODE):  vol.In(['cloud', 'local'])
        }

        return self.async_show_form(
            step_id='config_mode_selection', data_schema=vol.Schema(schema)
        )

    async def async_step_config_mode_selection(self, user_input=None):
        if user_input is not None:
            mode = user_input[CONF_CONNECTION_MODE]
            schema = {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_TOKEN): str,
                vol.Required(CONF_USER_ID): str,
                vol.Required(CONF_AUTH_CODE): str
            }

            if mode == 'cloud':
                schema[vol.Required(CONF_TARGET_ID)] = str

            return self.async_show_form(
                step_id='config_connection_info', data_schema=vol.Schema(schema)
            )

        return self.async_step_user(user_input)

    async def async_step_config_connection_info(self, user_input=None):
        if user_input is not None and CONF_DEVICE_ID in user_input:
            return self.async_create_entry(
                title="proscenic vacuum configuration",
                data= {
                    CONF_CONNECTION_MODE: CLOUD_MODE if CONF_TARGET_ID in user_input else LOCAL_MODE,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_TARGET_ID: user_input[CONF_TARGET_ID] if CONF_TARGET_ID in user_input else None,
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_USER_ID: user_input[CONF_USER_ID],
                    CONF_AUTH_CODE: user_input[CONF_AUTH_CODE]
                }
            )

        return self.async_step_user(user_input)

class ProscenicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry):
        """Initialize the options flow."""
        self.config_entry = config_entry
        self._sleep_duration_on_exit = self.config_entry.options.get(
            CONF_SLEEP, DEFAULT_CONF_SLEEP
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        options_schema = vol.Schema(
            {
                vol.Required(CONF_SLEEP, default = self._sleep_duration_on_exit): int
            },
        )

        if user_input is not None:
            return self.async_create_entry(title='proscenic vacuum configuration', data=user_input)

        return self.async_show_form(step_id='init', data_schema=options_schema)
