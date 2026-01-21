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

    # We need to track entities created to avoid duplicates
    # Since devices come and go, we might dynamically add them?
    # For now, we scan once at setup and then rely on coordinator updates.
    # Actually, proper behavior for dynamic trackers is usually to check on every update,
    # but ScannerEntity works well if we instantiate all we see.
    # To simplify, we will assume devices don't change often or we add them initially.
    # However, for a robust solution, we should probably check periodically or
    # just add everything we find in the first batch and let the coordinator update states.
    
    # NOTE: In a real advanced integration, we'd use a listener to add new entities.
    # Here we will add all currently found devices.
    
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
    # Format: MAC, ?, Interface, Uptime, Tx, Rx, Info...
    # active_wireless is a flat list
    if KEY_ACTIVE_WIRELESS in data and isinstance(data[KEY_ACTIVE_WIRELESS], list):
        raw = data[KEY_ACTIVE_WIRELESS]
        # Chunks of 22 items per client (based on observation of Status_Wireless.live.asp)
        # '24:D7:EB:92:59:F4','','wl0','8:20:00','5.500M','6.0M','HT40SGI[PS]','-52','-91','39','960','-52','-56','-54','0','0','0','0','0','','eth1'
        # That is 21 items?
        # Let's count items in snippet: 
        # 1:MAC, 2:?, 3:IF, 4:Time, 5:Rate, 6:Rate, 7:Info, 8:RSSI...
        # It's safer to identify by MAC pattern (XX:XX:XX:XX:XX:XX)
        
        # Heuristic parser: Iterate list, if item looks like MAC, start new device
        current_mac = None
        current_data = []
        
        for item in raw:
            if len(item) == 17 and ":" in item and len(item.split(":")) == 6:
                # Save previous
                if current_mac:
                    _add_device(devices, current_mac, "wireless", current_data, interfaces)
                current_mac = item
                current_data = []
            else:
                current_data.append(item)
        
        if current_mac:
             _add_device(devices, current_mac, "wireless", current_data, interfaces)

    # 2. DHCP Leases
    # 'slzb-06','192.168.10.102','14:2B:2F:D9:A5:33','Static','102','br0',''
    # Name, IP, MAC, Type, ?, Interface, ?
    if KEY_DHCP_LEASES in data and isinstance(data[KEY_DHCP_LEASES], list):
        raw = data[KEY_DHCP_LEASES]
        # Groups of 7?
        # Let's iterate. MAC is usually 3rd item (index 2)
        # Scan for MACs
        for i, item in enumerate(raw):
            if len(item) == 17 and ":" in item:
                # Found MAC.
                # Assuming structure: Name(i-2), IP(i-1), MAC(i), Type(i+1), ?(i+2), IF(i+3)
                try:
                    mac = item
                    name = raw[i-2] if i >= 2 else "Unknown"
                    ip = raw[i-1] if i >= 1 else None
                    iface = raw[i+3] if i+3 < len(raw) else None
                    
                    if iface in interfaces or not interfaces: # Empty interfaces list means all? Prompt said Default All.
                        if mac not in devices:
                            devices[mac] = {"name": name, "source": "dhcp", "ip": ip, "interface": iface}
                except IndexError:
                    pass

    return devices

def _add_device(devices, mac, source, data_list, allowed_interfaces):
    # Check interface (usually index 1 in the data list capture for wireless: 'wl0')
    iface = data_list[1] if len(data_list) > 1 else None
    
    # Filter
    if allowed_interfaces and iface and iface not in allowed_interfaces:
        return

    devices[mac] = {
        "name": f"Device {mac}", # Placeholder, wireless list doesn't have hostnames usually
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
        # Check if MAC exists in current coordinator data
        # We need to re-run the existence check on the fresh data
        # This is slightly inefficient but safe
        # Check active wireless
        data = self.coordinator.data
        if KEY_ACTIVE_WIRELESS in data and isinstance(data[KEY_ACTIVE_WIRELESS], list):
             if self._mac in data[KEY_ACTIVE_WIRELESS]:
                 return True
        
        # Check DHCP/ARP? DHCP is just a lease, doesn't mean connected.
        # ARP is better for "connected" state on wired.
        if KEY_ARP_TABLE in data and isinstance(data[KEY_ARP_TABLE], list):
             # ARP format: Name, IP, MAC...
             if self._mac in data[KEY_ARP_TABLE]:
                 return True

        # Wireless is the strongest indicator of "Online" for wifi devices.
        # For wired, ARP is key.
        return False

    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return self._source_type