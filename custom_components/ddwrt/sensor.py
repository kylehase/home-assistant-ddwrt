"""Sensor platform for DD-WRT."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DDWRTDataUpdateCoordinator

# Map known DD-WRT keys to entity descriptions
SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "wan_ipaddr": SensorEntityDescription(
        key="wan_ipaddr",
        name="WAN IP",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": SensorEntityDescription(
        key="uptime",
        name="Uptime String",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "load_average": SensorEntityDescription(
        key="load_average", # Derived key
        name="Load Average (1min)",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ttraff_in": SensorEntityDescription(
        key="ttraff_in",
        name="Total Traffic In",
        icon="mdi:download",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "ttraff_out": SensorEntityDescription(
        key="ttraff_out",
        name="Total Traffic Out",
        icon="mdi:upload",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "cpu_temp0": SensorEntityDescription(
        key="cpu_temp0",
        name="CPU Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "mem_free_kb": SensorEntityDescription(
        key="mem_free_kb", # Derived
        name="Memory Free",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DD-WRT sensors."""
    coordinator: DDWRTDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name = f"ddwrt-{entry.data['name']}"
    
    entities = []
    
    # Check data for keys and create entities
    # 1. Standard mapped keys
    for key, desc in SENSOR_TYPES.items():
        # logic: if key exists in data or is derived, create it
        # For direct keys:
        if key in coordinator.data or key in ["load_average", "mem_free_kb"]:
             entities.append(DDWRTSensor(coordinator, device_name, desc))
    
    # 2. Generic fallback for other useful keys found in data
    # Removed "wan_status" as it is now a binary sensor
    generic_keys = ["wan_shortproto", "lan_ip", "wl_ssid", "wl_channel"]
    for key in generic_keys:
        if key in coordinator.data:
            desc = SensorEntityDescription(
                key=key,
                name=key.replace("_", " ").title(),
                icon="mdi:information-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
            entities.append(DDWRTSensor(coordinator, device_name, desc))

    async_add_entities(entities)


class DDWRTSensor(CoordinatorEntity, SensorEntity):
    """Representation of a DD-WRT sensor."""

    def __init__(
        self,
        coordinator: DDWRTDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = device_name
        self._attr_unique_id = f"{device_name}_{description.key}"
        self._attr_has_entity_name = True # uses device name
        
        # ddwrt_skynet_wan_ip format via entity naming
        # Entity ID format: ddwrt_[device_name]_[sensor_name]
        # e.g. sensor.ddwrt_skynet_wan_ip
        # HA handles the "sensor." and domain, we just need unique IDs and correct Device Info
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_name)},
            "name": entry_name_from_device_name(device_name),
            "manufacturer": "DD-WRT",
            "model": "Router",
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        key = self.entity_description.key
        
        # Derived values
        if key == "load_average":
            # parse from uptime string: "12:17:59 up 134 days, ... load average: 0.00, 0.00, 0.00"
            if "uptime" in data:
                try:
                    parts = data["uptime"].split("load average:")
                    if len(parts) > 1:
                        loads = parts[1].split(",")
                        return float(loads[0].strip())
                except (ValueError, IndexError):
                    pass
            return None

        if key == "mem_free_kb":
            # mem_info is a list of strings. We need to find 'MemFree:' and the value after it.
            if "mem_info" in data and isinstance(data["mem_info"], list):
                try:
                    lst = data["mem_info"]
                    if "MemFree:" in lst:
                        idx = lst.index("MemFree:")
                        return int(lst[idx + 1])
                except (ValueError, IndexError):
                    pass
            return None

        val = data.get(key)
        
        # Cleanup specific values
        if key == "wan_ipaddr" and val:
             return val.split("/")[0] # remove cidr
             
        if key.startswith("cpu_temp") and val:
             return val.replace("°C", "").strip()

        return val

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Check if data exists; if null/empty/invalid as per requirements
        val = self.native_value
        if val is None or val == "":
             return False
        return super().available

def entry_name_from_device_name(dev_name):
    # ddwrt-skynet -> skynet
    return dev_name.replace("ddwrt-", "").replace("-", " ").title()