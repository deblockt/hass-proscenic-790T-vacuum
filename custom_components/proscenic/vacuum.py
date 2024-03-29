"""Support for proscenic 790T Vaccums."""
import logging

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    VacuumEntity,
    PLATFORM_SCHEMA
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME
)

from homeassistant.helpers.icon import icon_for_battery_level

from .vacuum_proscenic import Vacuum, WorkState

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import get_or_default, LOCAL_MODE, DOMAIN, CONF_CONNECTION_MODE, CONF_DEVICE_ID, CONF_TOKEN, CONF_USER_ID, CONF_SLEEP, CONF_AUTH_CODE, DEFAULT_CONF_SLEEP, CONF_TARGET_ID

_LOGGER = logging.getLogger(__name__)

SUPPORT_PROSCENIC = (
    SUPPORT_RETURN_HOME
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_STATUS
    | SUPPORT_BATTERY
    # | SUPPORT_LOCATE
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_USER_ID): cv.string,
    vol.Required(CONF_AUTH_CODE): cv.string,
    vol.Optional(CONF_SLEEP, default = DEFAULT_CONF_SLEEP): int,
    vol.Optional(CONF_NAME): cv.string
})

WORK_STATE_TO_STATE = {
    WorkState.RETURN_TO_BASE: STATE_RETURNING,
    WorkState.CLEANING: STATE_CLEANING,
    WorkState.PENDING: STATE_IDLE,
    WorkState.UNKNONW3: STATE_ERROR,
    WorkState.ERROR: STATE_ERROR,
    WorkState.NEAR_BASE: STATE_DOCKED,
    WorkState.POWER_OFF: 'off',
    WorkState.OTHER_POWER_OFF: 'off',
    WorkState.CHARGING: STATE_DOCKED,
    None: STATE_ERROR
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 790T vacuums."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    device = config['device']

    vacuums = [ProscenicVacuum(device, config[CONF_DEVICE_ID])]
    hass.loop.create_task(device.listen_state_change())

    _LOGGER.debug("Adding 790T Vacuums to Home Assistant: %s", vacuums)
    async_add_entities(vacuums, update_before_add = False)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the 790T vacuums."""
    _LOGGER.warn("Proscenic vacuum integration yaml configuration is now deprecated. You should configure the integration using the UI.")
    auth = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        CONF_TOKEN: config[CONF_TOKEN],
        CONF_USER_ID: config[CONF_USER_ID],
        CONF_AUTH_CODE: config[CONF_AUTH_CODE],
        CONF_TARGET_ID: config[CONF_TARGET_ID] if CONF_TARGET_ID in config else config[CONF_DEVICE_ID]
    }
    name = config[CONF_NAME] if CONF_NAME in config else '790T vacuum'
    ip = config[CONF_HOST] if CONF_HOST in config else None
    device = Vacuum(auth, ip, loop = hass.loop, config = {CONF_SLEEP: config[CONF_SLEEP]})
    vacuums = [ProscenicVacuum(device, name)]
    hass.loop.create_task(device.listen_state_change())
    hass.loop.create_task(device.start_map_generation())
    _LOGGER.debug("Adding 790T Vacuums to Home Assistant: %s", vacuums)
    async_add_entities(vacuums, update_before_add = False)


class ProscenicVacuum(VacuumEntity):
    """790T Vacuums such as Deebot."""

    def __init__(self, device, name):
        """Initialize the Proscenic Vacuum."""
        self.device = device
        self.device.subcribe(lambda vacuum: self.schedule_update_ha_state(force_refresh = False))
        self._name = name
        self._fan_speed = None
        self._error = None
        self._is_on = False
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "vacuum" + self.device.device_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device.device_id)},
            "name": "Proscenic vacuum",
            "manufacturer": "Proscenic"
        }

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        return self.device.work_state == WorkState.CLEANING

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        return self.device.work_state == WorkState.CHARGING

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_PROSCENIC

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return WORK_STATE_TO_STATE[self.device.work_state]

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return WORK_STATE_TO_STATE[self.device.work_state]

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self.device.return_to_base()

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.is_charging
        )

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.device.battery

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self.device.fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return []

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        await self.device.clean()

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        await self.async_return_to_base()

    async def async_start(self, **kwargs):
        await self.device.clean()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.device.stop()

    async def async_pause(self, **kwargs):
        """Pause the vacuum cleaning process."""
        await self.device.stop()

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes of this vacuum."""
        return {
            'clear_area': self.device.last_clear_area,
            'clear_duration': None if not self.device.last_clear_duration else (self.device.last_clear_duration // 60),
            'error_code': self.device.error_code,
            'error_detail': self.device.error_detail
        }