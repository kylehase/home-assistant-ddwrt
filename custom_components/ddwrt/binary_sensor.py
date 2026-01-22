"""Binary sensor platform for DD-WRT."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DDWRTDataUpdateCoordinator

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "wan_status": BinarySensorEntityDescription(
        key="wan_status",
        name="Internet Connection",
        translation_key="wan_status",
        icon="mdi:router-network",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wl_radio": BinarySensorEntityDescription(
        key="wl_radio",
        name="Wi-Fi Radio",
        translation_key="wl_radio",
        icon="mdi:wifi",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DD-WRT binary sensors."""
    coordinator: DDWRTDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name = f"ddwrt-{entry.data['name']}"

    entities = []

    for key, desc in BINARY_SENSOR_TYPES.items():
        entity = DDWRTBinarySensor(coordinator, device_name, desc)
        if key not in coordinator.data:
             entity._attr_entity_registry_enabled_default = False
        entities.append(entity)

    async_add_entities(entities)


class DDWRTBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a DD-WRT binary sensor."""

    def __init__(
        self,
        coordinator: DDWRTDataUpdateCoordinator,
        device_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = device_name
        self._attr_unique_id = f"{device_name}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_name)},
            "name": device_name.replace("ddwrt-", "").replace("-", " ").title(),
            "manufacturer": "DD-WRT",
            "model": "Router",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        val = self.coordinator.data.get(self.entity_description.key)
        if val is None:
            return None

        if self.entity_description.key == "wan_status":
            return val.strip().lower().startswith("connected")

        if self.entity_description.key == "wl_radio":
            return val.strip().lower() == "active"

        return bool(val)