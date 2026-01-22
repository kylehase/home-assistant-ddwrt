"""Config flow for DD-WRT integration."""
from __future__ import annotations

import asyncio
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
                ports_to_try.append((port, False))
                ports_to_try.append((port, True))
            else:
                ports_to_try.append((80, False))
                ports_to_try.append((443, True))

            session = async_get_clientsession(self.hass, verify_ssl=False)

            for test_port, use_ssl in ports_to_try:
                protocol = "https" if use_ssl else "http"
                url = f"{protocol}://{ip}:{test_port}/Statusinfo.live.asp"
                
                try:
                    LOGGER.debug("Attempting connection to %s", url)
                    async with asyncio.timeout(5):
                        # Just checking connectivity, 401 is success for this step (auth required)
                        # or 200 if no auth.
                        async with session.get(url) as response:
                            LOGGER.debug("Connection to %s returned status %s", url, response.status)
                            if response.status < 500:
                                self._temp_config[CONF_ROUTER_IP] = ip
                                self._temp_config[CONF_ROUTER_PORT] = test_port
                                self._temp_config[CONF_USE_SSL] = use_ssl
                                return await self.async_step_auth()
                except Exception as err:
                    LOGGER.debug("Connection to %s failed: %s", url, err)
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
            LOGGER.debug("Testing credentials at %s", url)
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    text = await response.text()
                    # Basic check if it looks like DD-WRT data
                    if "{uptime::" in text or "{ipinfo::" in text:
                         return True
                LOGGER.debug("Credentials failed with status: %s", response.status)
                return False
        except Exception as err:
            LOGGER.debug("Credential check failed with error: %s", err)
            return False

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Friendly Name."""
        if user_input is not None:
            friendly_name = user_input[CONF_NAME]
            title = f"DD-WRT {friendly_name}"
            data = {**self._temp_config, **user_input}
            # Default to br0 (LAN bridge) for device tracking
            data[CONF_TRACKER_INTERFACES] = ["br0"]
            
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                }
            ),
        )