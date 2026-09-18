"""FortiOS system Monitor API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSSystemApi:
    """Provide system-related Monitor endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the system Monitor API."""
        self._http = http
        self._context = context

    async def get_status(self) -> dict[str, Any]:
        """Return FortiGate system status."""
        return await self._http.get("monitor/system/status")

    async def get_firmware(self) -> dict[str, Any]:
        """Return firmware and platform information."""
        return await self._http.get("monitor/system/firmware")

    async def get_dhcp_leases(self) -> dict[str, Any]:
        """Return current DHCP leases."""
        return await self._http.get("monitor/system/dhcp")
