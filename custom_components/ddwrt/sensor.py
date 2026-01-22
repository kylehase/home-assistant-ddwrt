"""Sensor platform for DD-WRT."""
from __future__ import annotations

import re
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DDWRTDataUpdateCoordinator

# Keys to ignore (handled by other platforms or too complex)
IGNORED_KEYS = {
    "wan_status", # Binary Sensor
    "wl_radio",   # Binary Sensor
    "active_wireless", # Device Tracker
    "dhcp_leases",     # Device Tracker
    "arp_table",       # Device Tracker
    "bridges_table",   # Internal
    "mem_info",        # Handled by derived sensor
    "packet_info",     # Complex string, ignore
    "active_wds",      # Usually empty/complex
}

def format_name(key: str) -> str:
    """Format a key into a friendly name with correct capitalization."""
    name = key.replace("_", " ").title()
    replacements = {
        "Wl ": "Wireless ",
        "Wl": "Wireless",
        "Pppoe": "PPPoE",
        "Dhcp": "DHCP",
        "Ip": "IP",
        "Lan": "LAN",
        "Mac": "MAC",
        "Wan": "WAN",
        "Ssid": "SSID",
        "Gps": "GPS",
        "Ntp": "NTP",
        "Dns": "DNS",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.strip()

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "wan_ipaddr": SensorEntityDescription(
        key="wan_ipaddr",
        translation_key="wan_ipaddr",
        icon="mdi:ip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": SensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wan_uptime": SensorEntityDescription(
        key="wan_uptime",
        translation_key="wan_uptime",
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "load_avg_1min": SensorEntityDescription(
        key="load_avg_1min",
        translation_key="load_avg_1min",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "load_avg_5min": SensorEntityDescription(
        key="load_avg_5min",
        translation_key="load_avg_5min",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "load_avg_15min": SensorEntityDescription(
        key="load_avg_15min",
        translation_key="load_avg_15min",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ttraff_in": SensorEntityDescription(
        key="ttraff_in",
        translation_key="ttraff_in",
        icon="mdi:download-network",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "ttraff_out": SensorEntityDescription(
        key="ttraff_out",
        translation_key="ttraff_out",
        icon="mdi:upload-network",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # New Rate Sensors
    "wan_in_rate": SensorEntityDescription(
        key="wan_in_rate",
        translation_key="wan_in_rate",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "wan_out_rate": SensorEntityDescription(
        key="wan_out_rate",
        translation_key="wan_out_rate",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "cpu_temp0": SensorEntityDescription(
        key="cpu_temp0",
        translation_key="cpu_temp0",
        icon="mdi:thermometer",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "mem_total_kb": SensorEntityDescription(
        key="mem_total_kb",
        translation_key="mem_total_kb",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "mem_free_kb": SensorEntityDescription(
        key="mem_free_kb",
        translation_key="mem_free_kb",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "mem_used_percent": SensorEntityDescription(
        key="mem_used_percent",
        translation_key="mem_used_percent",
        icon="mdi:memory",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "wan_shortproto": SensorEntityDescription(
        key="wan_shortproto",
        translation_key="wan_shortproto",
        icon="mdi:network-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "assoc_count": SensorEntityDescription(
        key="assoc_count",
        translation_key="assoc_count",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ipinfo": SensorEntityDescription(
        key="ipinfo",
        translation_key="ipinfo",
        icon="mdi:web",
        entity_category=EntityCategory.DIAGNOSTIC,
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
    created_keys = set()
    
    # 1. Standard mapped keys
    for key, desc in SENSOR_TYPES.items():
        entity = DDWRTSensor(coordinator, device_name, desc)
        # Check availability immediately, but allow rates/derived to exist
        if key not in ["wan_in_rate", "wan_out_rate"] and (entity.native_value is None or entity.native_value == ""):
             entity._attr_entity_registry_enabled_default = False
        entities.append(entity)
        created_keys.add(key)

    # 2. Dynamic Scan
    for key, value in coordinator.data.items():
        if key in created_keys or key in IGNORED_KEYS:
            continue
        if isinstance(value, (list, dict)):
            continue
            
        friendly_name = format_name(key)
        desc = SensorEntityDescription(
            key=key,
            name=friendly_name,
            icon="mdi:information-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        entity = DDWRTSensor(coordinator, device_name, desc)
        if entity.native_value is None or entity.native_value == "":
            entity._attr_entity_registry_enabled_default = False
        entities.append(entity)
        created_keys.add(key)

    async_add_entities(entities)


class DDWRTSensor(CoordinatorEntity, SensorEntity):
    """Representation of a DD-WRT sensor."""

    def __init__(
        self,
        coordinator: DDWRTDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
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
            "name": entry_name_from_device_name(device_name),
            "manufacturer": "DD-WRT",
            "model": "Router",
        }
        # For rate calculation
        self._last_value = None
        self._last_time = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        key = self.entity_description.key
        
        # 1. Load Averages
        if key in ["load_avg_1min", "load_avg_5min", "load_avg_15min"]:
            if "uptime" in data:
                try:
                    parts = data["uptime"].split("load average:")
                    if len(parts) > 1:
                        loads = parts[1].split(",")
                        if key == "load_avg_1min": return float(loads[0].strip())
                        if key == "load_avg_5min": return float(loads[1].strip())
                        if key == "load_avg_15min": return float(loads[2].strip())
                except (ValueError, IndexError):
                    pass
            return None

        # 2. Bandwidth Rates (Calculated)
        if key in ["wan_in_rate", "wan_out_rate"]:
            source_key = "ttraff_in" if key == "wan_in_rate" else "ttraff_out"
            new_val = data.get(source_key)
            now = datetime.now()
            
            if new_val is None:
                return None
                
            try:
                new_val = float(new_val) # MB total
            except ValueError:
                return None

            # If this is the first update, just store state and return 0
            if self._last_value is None or self._last_time is None:
                self._last_value = new_val
                self._last_time = now
                return 0.0

            # Calculate rate
            time_delta = (now - self._last_time).total_seconds()
            if time_delta == 0:
                return 0.0
                
            diff = new_val - self._last_value
            
            # Reset detection (if router rebooted and counter is lower)
            if diff < 0:
                self._last_value = new_val
                self._last_time = now
                return 0.0

            # Convert MB to kB (1 MB = 1024 kB)
            diff_kb = diff * 1024
            rate_kbps = diff_kb / time_delta
            
            # Update history
            self._last_value = new_val
            self._last_time = now
            
            return round(rate_kbps, 1)

        # 3. Memory
        if key in ["mem_total_kb", "mem_free_kb", "mem_used_percent"]:
            mem_raw = data.get("mem_info")
            if not mem_raw: return None
            
            if isinstance(mem_raw, str):
                lst = re.findall(r"'([^']*)'", mem_raw)
            elif isinstance(mem_raw, list):
                lst = mem_raw
            else: return None

            def get_mem_value(label_start):
                for i, item in enumerate(lst):
                    if item.startswith(label_start):
                        if i + 1 < len(lst):
                            try: return int(lst[i + 1].strip())
                            except ValueError: pass
                return None

            total = get_mem_value("MemTotal")
            free = get_mem_value("MemFree")
            
            if key == "mem_total_kb": return total
            if key == "mem_free_kb": return free
            if key == "mem_used_percent":
                if total and free is not None and total > 0:
                    used = total - free
                    return round((used / total) * 100, 1)
                return None

        # 4. General Strings
        val = data.get(key)
        if isinstance(val, str):
            val = val.replace("&nbsp;", " ").strip()
            if val.lower() in ["n.a", "n.a.", "nan", "unknown"]:
                return None

        if key == "uptime" and val:
            if " up " in val:
                try:
                    val = val.split(" up ")[1]
                    return val.split(",")[0].strip()
                except IndexError: pass
            return val

        if key == "wan_uptime" and val:
            return val.split(",")[0].strip()

        if key == "wan_ipaddr" and val:
             return val.split("/")[0]

        if key == "ipinfo" and val:
             return val.replace("IP:", "").strip()
             
        if key.startswith("cpu_temp") and val:
             match = re.search(r"([\d\.]+)", val)
             if match: return match.group(1)
             return None

        return val

def entry_name_from_device_name(dev_name):
    return dev_name.replace("ddwrt-", "").replace("-", " ").title()