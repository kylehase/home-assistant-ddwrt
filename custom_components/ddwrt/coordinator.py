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
        
        # We need to preserve session auth cookies/basic auth across requests if needed,
        # but aiohttp with BasicAuth object usually handles it per request.
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
            # Clean up value
            value = value.strip()
            
            # Check if it is a list/complex string (starts with single quote)
            if value.startswith("'"):
                result[key] = self._parse_complex_value(value)
            else:
                result[key] = value
                
        return result

    def _parse_complex_value(self, value_str: str) -> list[str]:
        """Parse values like 'a','b','c' into a list."""
        # This is a naive split by comma, but handles quoted strings mostly.
        # Since DD-WRT outputs JavaScript-like arrays, we can strip quotes and split.
        # A more robust regex for quoted strings:
        
        items = []
        # Find all content inside single quotes
        # This regex matches 'content' ignoring commas inside
        parts = re.findall(r"'([^']*)'", value_str)
        if parts:
            return parts
        return [value_str] # Fallback