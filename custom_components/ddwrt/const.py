"""Constants for the DD-WRT integration."""
from logging import getLogger

LOGGER = getLogger(__package__)

DOMAIN = "ddwrt"
DEFAULT_PORT = 80
DEFAULT_SSL = False
DEFAULT_USERNAME = "root"
DEFAULT_UPDATE_INTERVAL = 60

CONF_ROUTER_IP = "router_ip"
CONF_ROUTER_PORT = "router_port"
CONF_USE_SSL = "use_ssl"
CONF_TRACKER_INTERFACES = "tracker_interfaces"

# Endpoints to poll in sequence
# Status_Router: cpu_temp, mem_info, router_time
# Status_Internet: wan_status, ttraff_in/out
# Status_Lan: arp_table, dhcp_leases
# Status_Wireless: active_wireless, assoc_count
ENDPOINTS = [
    "Status_Router.live.asp",
    "Status_Internet.live.asp",
    "Status_Lan.live.asp",
    "Status_Wireless.live.asp",
]

# Keys that identify device lists for tracking
KEY_ACTIVE_WIRELESS = "active_wireless"
KEY_DHCP_LEASES = "dhcp_leases"
KEY_ARP_TABLE = "arp_table"