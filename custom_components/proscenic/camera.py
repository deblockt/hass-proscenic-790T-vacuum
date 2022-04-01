"""Support for proscenic 790T Vaccum map."""
import logging
import os

from .const import DOMAIN, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, CONF_DEVICE_ID
from homeassistant.components.camera import Camera


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 790T vacuums map camera."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    conf_map_path = config[CONF_MAP_PATH] if CONF_MAP_PATH in config else DEFAULT_CONF_MAP_PATH
    device_id = config[CONF_DEVICE_ID]

    _LOGGER.debug("Adding 790T Vacuums camera to Home Assistant")
    async_add_entities([ProscenicMapCamera(device_id, conf_map_path)], update_before_add = False)

class ProscenicMapCamera(Camera):
    """Representation of a local file camera."""

    def __init__(self, device_id, file_path):
        """Initialize Local File Camera component."""
        super().__init__()

        self._device_id = device_id
        self._file_path = file_path
        self.content_type = 'image/svg+xml'

    def camera_image(self, width = None, height = None):
        """Return image response."""
        try:
            with open(self._file_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.info("No map has been generated for the vacuum device %s", self._device_id)

        return b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    def update_file_path(self, file_path):
        """Update the file_path."""
        self._file_path = file_path
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._device_id + '_map'

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {"file_path": self._file_path}

    @property
    def device_info(self):
        """Return the device info."""
        return {"identifiers": {(DOMAIN, self._device_id)}}

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "camera" + self._device_id
