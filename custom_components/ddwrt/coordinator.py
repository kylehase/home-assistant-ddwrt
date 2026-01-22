"""DataUpdateCoordinator for DD-WRT."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import re

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ENDPOINTS, LOGGER, DEFAULT_UPDATE_INTERVAL

# Regex to find {key::value} patterns
DDWRT_DATA_REGEX = re.compile(r"\{(\w+)::([^}]*)\}")


class DDWRTDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching DD-WRT data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.session = session
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.protocol = "https" if use_ssl else "http"
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"

    async def _async_update_data(self) -> dict[str, any]:
        """Fetch data from all endpoints."""
        data = {}
        auth = aiohttp.BasicAuth(self.username, self.password)

        for endpoint in ENDPOINTS:
            url = f"{self.base_url}/{endpoint}"
            try:
                async with asyncio.timeout(10):
                    async with self.session.get(url, auth=auth) as response:
                        response.raise_for_status()
                        text = await response.text()
                        
                        # Parse the custom format
                        parsed = self._parse_ddwrt_live_format(text)
                        data.update(parsed)
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                LOGGER.warning(f"Error fetching {endpoint} from {self.host}: {err}")
                # We continue to the next endpoint to get partial data if possible
                continue
            except Exception as err:
                raise UpdateFailed(f"Unexpected error: {err}") from err

        if not data:
            raise UpdateFailed("No data received from DD-WRT router")

        return data

    def _parse_ddwrt_live_format(self, text: str) -> dict[str, any]:
        """Parse the DD-WRT .live.asp format ({key::value})."""
        result = {}
        matches = DDWRT_DATA_REGEX.findall(text)
        
        for key, value in matches:
            value = value.strip()
            # If value starts with single quote, it's a list.
            # We preserve it as a string here (or robustly split) 
            # and let specific sensors handle precise parsing if needed (like mem_info)
            # However, for generic lists, we can try basic splitting.
            if value.startswith("'"):
                result[key] = self._parse_complex_value(value)
            else:
                result[key] = value
                
        return result

    def _parse_complex_value(self, value_str: str) -> list[str]:
        """Parse values like 'a','b','c' into a list."""
        parts = re.findall(r"'([^']*)'", value_str)
        if parts:
            return parts
        return [value_str]