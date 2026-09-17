"""FortiOS wifi Monitor API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSWifiApi:
    """Provide wifi-related Monitor endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the wifi Monitor API."""
        self._http = http
        self._context = context

    async def get_managed_access_points(self) -> dict[str, Any]:
        """Return managed FortiAP information."""
        return await self._http.get("monitor/wifi/managed_ap")

    async def get_clients(self) -> dict[str, Any]:
        """Return connected wifi clients."""
        return await self._http.get("monitor/wifi/client")

    async def get_meta(self) -> dict[str, Any]:
        """Return wifi metadata and lookup tables."""
        return await self._http.get("monitor/wifi/meta")
