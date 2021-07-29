"""Support for proscenic 790T Vaccum map."""
import logging

from .const import DOMAIN, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, CONF_DEVICE_ID
from homeassistant.components.local_file.camera import LocalFile

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 790T vacuums map camera."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    conf_map_path = config[CONF_MAP_PATH] if CONF_MAP_PATH in config else DEFAULT_CONF_MAP_PATH
    device_id = config[CONF_DEVICE_ID]

    _LOGGER.debug("Adding 790T Vacuums camera to Home Assistant")
    async_add_entities([ProscenicMapCamera(device_id, conf_map_path)], update_before_add = False)


class ProscenicMapCamera(LocalFile):
    """Representation of a proscenic vacuum map camera."""

    def __init__(self, device_id, file_path):
        super().__init__(device_id + '_map', file_path)
        self.device_id = device_id

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "camera" + self.device_id

    @property
    def device_info(self):
        """Return the device info."""
        return {"identifiers": {(DOMAIN, self.device_id)}}