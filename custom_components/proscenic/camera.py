"""Support for proscenic 790T Vaccum map."""
import logging
import os

from .const import DOMAIN, CONF_DEVICE_ID
from .vacuum_proscenic import WorkState

from homeassistant.components.camera import Camera


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 790T vacuums map camera."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    device = config['device']

    _LOGGER.debug("Adding 790T Vacuums camera to Home Assistant")
    async_add_entities([ProscenicMapCamera(device)], update_before_add = False)

class ProscenicMapCamera(Camera):
    """Representation of a local file camera."""

    def __init__(self, device):
        """Initialize Local File Camera component."""
        super().__init__()

        self._device = device
        self.content_type = 'image/svg+xml'

    def camera_image(self, width = None, height = None):
        """Return image response."""
        if self._device.map_svg:
            return self._device.map_svg

        return b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    @property
    def name(self):
        """Return the name of this camera."""
        return self._device.device_id + '_map'

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {}

    @property
    def device_info(self):
        """Return the device info."""
        return {"identifiers": {(DOMAIN, self._device.device_id)}}

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return "camera" + self._device.device_id
