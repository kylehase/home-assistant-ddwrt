"""The DD-WRT integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ROUTER_IP,
    CONF_ROUTER_PORT,
    CONF_USE_SSL,
    DOMAIN,
    LOGGER,
)
from .coordinator import DDWRTDataUpdateCoordinator

# Added Platform.BINARY_SENSOR
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DD-WRT from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=False)

    coordinator = DDWRTDataUpdateCoordinator(
        hass,
        session=session,
        host=entry.data[CONF_ROUTER_IP],
        port=entry.data.get(CONF_ROUTER_PORT),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        use_ssl=entry.data[CONF_USE_SSL],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok