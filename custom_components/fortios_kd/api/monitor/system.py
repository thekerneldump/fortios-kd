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

    async def get_vdom_resources(self) -> dict[str, Any] | list[Any]:
        """Return resource utilization for every virtual domain."""
        return await self._http.get(
            "monitor/system/vdom-resource",
            params={"vdom": "*"},
            allow_list=True,
        )

    async def get_interfaces(
        self,
        vdom: str = "*",
    ) -> dict[str, Any] | list[Any]:
        """Return physical and VLAN interface statistics for selected VDOMs."""
        return await self._http.get(
            "monitor/system/interface",
            params={"include_vlan": "true", "vdom": vdom},
            allow_list=vdom == "*",
        )

    async def get_available_interfaces(self) -> dict[str, Any] | list[Any]:
        """Return interface types, relationships, and composite membership."""
        return await self._http.get(
            "monitor/system/available-interfaces",
            params={"vdom": "*"},
            allow_list=True,
        )
