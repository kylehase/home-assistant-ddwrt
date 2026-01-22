"""Button platform for DD-WRT."""
from __future__ import annotations

import aiohttp
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import DDWRTDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DD-WRT buttons."""
    coordinator: DDWRTDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name = f"ddwrt-{entry.data['name']}"
    
    entities = [
        DDWRTButton(
            coordinator,
            device_name,
            ButtonEntityDescription(
                key="reboot",
                translation_key="reboot",
                icon="mdi:restart",
                entity_category=EntityCategory.CONFIG,
            ),
        )
    ]
    
    async_add_entities(entities)


class DDWRTButton(CoordinatorEntity, ButtonEntity):
    """Representation of a DD-WRT button."""

    def __init__(
        self,
        coordinator: DDWRTDataUpdateCoordinator,
        device_name: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = device_name
        self._attr_unique_id = f"{device_name}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_name)},
            "name": device_name.replace("ddwrt-", "").replace("-", " ").title(),
            "manufacturer": "DD-WRT",
            "model": "Router",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.key == "reboot":
            await self._reboot_router()

    async def _reboot_router(self) -> None:
        """Send reboot command to router."""
        url = f"{self.coordinator.base_url}/apply.cgi"
        data = {"action": "Reboot"}
        auth = aiohttp.BasicAuth(self.coordinator.username, self.coordinator.password)
        
        try:
            LOGGER.info("Sending reboot command to DD-WRT router")
            async with self.coordinator.session.post(url, data=data, auth=auth) as response:
                if response.status != 200:
                    LOGGER.error("Reboot failed with status: %s", response.status)
        except Exception as err:
            LOGGER.error("Failed to send reboot command: %s", err)