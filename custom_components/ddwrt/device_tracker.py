"""Device tracker platform for DD-WRT."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_TRACKER_INTERFACES,
    DOMAIN,
    KEY_ACTIVE_WIRELESS,
    KEY_ARP_TABLE,
    KEY_DHCP_LEASES,
    LOGGER,
)
from .coordinator import DDWRTDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device trackers."""
    coordinator: DDWRTDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_name = f"ddwrt-{entry.data['name']}"
    monitored_interfaces = entry.data.get(CONF_TRACKER_INTERFACES, [])
    
    trackers = []
    seen_macs = set()
    
    # Helper to process devices
    devices = _get_devices_from_data(coordinator.data, monitored_interfaces)
    
    for mac, info in devices.items():
        trackers.append(DDWRTDeviceTracker(coordinator, device_name, mac, info["name"], info["source"]))
        seen_macs.add(mac)
        
    async_add_entities(trackers)


def _get_devices_from_data(data, interfaces):
    """Parse raw data into a dict of mac -> {name, source, ip, interface}."""
    devices = {}
    
    # 1. Wireless Active Clients
    if KEY_ACTIVE_WIRELESS in data and isinstance(data[KEY_ACTIVE_WIRELESS], list):
        raw = data[KEY_ACTIVE_WIRELESS]
        current_mac = None
        current_data = []
        
        for item in raw:
            if len(item) == 17 and ":" in item and len(item.split(":")) == 6:
                if current_mac:
                    _add_device(devices, current_mac, "wireless", current_data, interfaces)
                current_mac = item
                current_data = []
            else:
                current_data.append(item)
        
        if current_mac:
             _add_device(devices, current_mac, "wireless", current_data, interfaces)

    # 2. DHCP Leases
    if KEY_DHCP_LEASES in data and isinstance(data[KEY_DHCP_LEASES], list):
        raw = data[KEY_DHCP_LEASES]
        for i, item in enumerate(raw):
            if len(item) == 17 and ":" in item:
                try:
                    mac = item
                    name = raw[i-2] if i >= 2 else "Unknown"
                    ip = raw[i-1] if i >= 1 else None
                    iface = raw[i+3] if i+3 < len(raw) else None
                    
                    if iface in interfaces or not interfaces:
                        if mac not in devices:
                            devices[mac] = {"name": name, "source": "dhcp", "ip": ip, "interface": iface}
                except IndexError:
                    pass

    return devices

def _add_device(devices, mac, source, data_list, allowed_interfaces):
    iface = data_list[1] if len(data_list) > 1 else None
    
    if allowed_interfaces and iface and iface not in allowed_interfaces:
        return

    devices[mac] = {
        "name": f"Device {mac}",
        "source": source,
        "interface": iface
    }


class DDWRTDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Represent a tracked device."""

    def __init__(self, coordinator, device_name, mac, hostname, source_type):
        """Initialize."""
        super().__init__(coordinator)
        self._mac = mac
        self._hostname = hostname
        self._source_type = SourceType.ROUTER
        self._parent_device = device_name
        self._attr_unique_id = f"{device_name}_{mac}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_name)},
        }

    @property
    def mac_address(self) -> str:
        """Return mac."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return hostname."""
        return self._hostname

    @property
    def is_connected(self) -> bool:
        """Return true if connected."""
        data = self.coordinator.data
        if KEY_ACTIVE_WIRELESS in data and isinstance(data[KEY_ACTIVE_WIRELESS], list):
             if self._mac in data[KEY_ACTIVE_WIRELESS]:
                 return True
        
        if KEY_ARP_TABLE in data and isinstance(data[KEY_ARP_TABLE], list):
             if self._mac in data[KEY_ARP_TABLE]:
                 return True

        return False

    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return self._source_type