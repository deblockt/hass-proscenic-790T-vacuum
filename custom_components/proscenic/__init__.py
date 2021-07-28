from .const import DOMAIN, CONF_SLEEP, CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH, DEFAULT_CONF_SLEEP

async def async_setup_entry(hass, entry):
    """Test"""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = dict(entry.data)
    hass.data[DOMAIN][entry.entry_id][CONF_SLEEP] = entry.options.get(CONF_SLEEP, DEFAULT_CONF_SLEEP)
    hass.data[DOMAIN][entry.entry_id][CONF_MAP_PATH] = entry.options.get(CONF_MAP_PATH, DEFAULT_CONF_MAP_PATH)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, 'vacuum')
    )
    return True
