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

CONF_DEVICE_ID = 'deviceId'
CONF_TOKEN = 'token'
CONF_USER_ID = 'userId'
CONF_SLEEP = 'sleep_duration_on_exit'
CONF_AUTH_CODE = 'authCode'
CONF_MAP_PATH='map_path'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_USER_ID): cv.string,
    vol.Required(CONF_AUTH_CODE): cv.string,
    vol.Optional(CONF_SLEEP, default = 60): int,
    vol.Optional(CONF_MAP_PATH, default = '/tmp/proscenic_vacuum_map.svg'): cv.string,
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

ATTR_ERROR = "error"
ATTR_COMPONENT_PREFIX = "component_"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the 790T vacuums."""
    auth = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        CONF_TOKEN: config[CONF_TOKEN],
        CONF_USER_ID: config[CONF_USER_ID],
        CONF_AUTH_CODE: config[CONF_AUTH_CODE]
    }
    name = config[CONF_NAME] if CONF_NAME in config else '790T vacuum'
    device = Vacuum(config[CONF_HOST], auth, loop = hass.loop, config = {CONF_SLEEP: config[CONF_SLEEP], CONF_MAP_PATH: config[CONF_MAP_PATH]})
    vacuums = [ProscenicVacuum(device, name)]
    hass.loop.create_task(device.listen_state_change())
    hass.loop.create_task(device.start_map_generation())
    
    _LOGGER.debug("Adding 790T Vacuums to Home Assistant: %s", vacuums)
    async_add_entities(vacuums, update_before_add = False)

class ProscenicVacuum(VacuumEntity):
    """790T Vacuums such as Deebot."""

    def __init__(self, device, name):
        """Initialize the Ecovacs Vacuum."""
        self.device = device
        self.device.subcribe(lambda vacuum: self.schedule_update_ha_state(force_refresh = False))
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
        return self.device.device_id

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