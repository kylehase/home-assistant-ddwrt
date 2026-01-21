"""Config flow for DD-WRT integration."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ROUTER_IP,
    CONF_ROUTER_PORT,
    CONF_TRACKER_INTERFACES,
    CONF_USE_SSL,
    DOMAIN,
    LOGGER,
)
from .coordinator import DDWRTDataUpdateCoordinator

STEP_CONN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ROUTER_IP): str,
        vol.Optional(CONF_ROUTER_PORT): int,
    }
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default="root"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DD-WRT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._temp_config: dict[str, Any] = {}
        self._detected_interfaces: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ip = user_input[CONF_ROUTER_IP]
            port = user_input.get(CONF_ROUTER_PORT)

            # Determine protocol and port if not specified
            ports_to_try = []
            if port:
                # If port provided, we try http then https on that port (though usually specific)
                # But logic says: If Port provided: Try HTTP, then HTTPS.
                ports_to_try.append((port, False))
                ports_to_try.append((port, True))
            else:
                # Default ports
                ports_to_try.append((80, False))
                ports_to_try.append((443, True))

            session = async_get_clientsession(self.hass, verify_ssl=False)

            for test_port, use_ssl in ports_to_try:
                protocol = "https" if use_ssl else "http"
                url = f"{protocol}://{ip}:{test_port}/Statusinfo.live.asp"
                
                try:
                    async with aiohttp.ClientTimeout(total=5):
                        # Just checking connectivity, 401 is success for this step (auth required)
                        # or 200 if no auth.
                        async with session.get(url) as response:
                            if response.status < 500:
                                self._temp_config[CONF_ROUTER_IP] = ip
                                self._temp_config[CONF_ROUTER_PORT] = test_port
                                self._temp_config[CONF_USE_SSL] = use_ssl
                                return await self.async_step_auth()
                except Exception:
                    pass

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_CONN_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._temp_config.update(user_input)
            
            # Test credentials
            valid = await self._test_credentials(
                self._temp_config[CONF_ROUTER_IP],
                self._temp_config[CONF_ROUTER_PORT],
                self._temp_config[CONF_USERNAME],
                self._temp_config[CONF_PASSWORD],
                self._temp_config[CONF_USE_SSL],
            )

            if valid:
                return await self.async_step_config()
            
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
        )

    async def _test_credentials(self, ip, port, username, password, use_ssl):
        """Return true if credentials are valid."""
        session = async_get_clientsession(self.hass, verify_ssl=False)
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{ip}:{port}/Statusinfo.live.asp"
        auth = aiohttp.BasicAuth(username, password)
        
        try:
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    text = await response.text()
                    # Basic check if it looks like DD-WRT data
                    if "{uptime::" in text or "{ipinfo::" in text:
                         # While here, let's grab interfaces for the next step
                         # We'll try to fetch Networking.live.asp or Status_Wireless
                         await self._fetch_interfaces(session, ip, port, auth, use_ssl)
                         return True
                return False
        except Exception:
            return False

    async def _fetch_interfaces(self, session, ip, port, auth, use_ssl):
        """Fetch available interfaces for the selection list."""
        protocol = "https" if use_ssl else "http"
        # Try Networking first for bridges
        url = f"{protocol}://{ip}:{port}/Networking.live.asp"
        interfaces = set()
        
        try:
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    text = await response.text()
                    if "{bridges_table::" in text:
                        # Extract basic interface names approx
                        import re
                        # Look for 'br0', 'eth0' etc in the raw text
                        # This is a best effort scan
                        found = re.findall(r"'([a-z0-9\.]+)'", text)
                        for f in found:
                             if len(f) < 10 and not " " in f: # simple heuristic
                                 interfaces.add(f)
        except Exception:
            pass

        # Ensure we at least have some defaults if scan fails
        if not interfaces:
            interfaces.update(["br0", "eth0", "eth1", "wl0", "wl1"])
            
        self._detected_interfaces = sorted(list(interfaces))

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Friendly Name and Interfaces."""
        if user_input is not None:
            friendly_name = user_input[CONF_NAME]
            # Device name logic: ddwrt-skynet
            # We store the friendly name in title, use ddwrt prefix for internal ID generation
            
            title = f"DD-WRT {friendly_name}"
            data = {**self._temp_config, **user_input}
            
            return self.async_create_entry(title=title, data=data)

        # Default to all detected interfaces
        default_interfaces = self._detected_interfaces

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Optional(
                        CONF_TRACKER_INTERFACES, default=default_interfaces
                    ): vol.MultiSelect(self._detected_interfaces),
                }
            ),
        )