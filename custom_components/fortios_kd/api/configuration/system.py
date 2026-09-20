"""FortiOS system configuration API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSSystemConfigurationApi:
    """Provide system-related configuration endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the system configuration API."""
        self._http = http
        self._context = context

    async def get_global(self) -> dict[str, Any]:
        """Return global system configuration."""
        return await self._http.get("cmdb/system/global?format=hostname")

    async def get_vdoms(self) -> dict[str, Any] | list[Any]:
        """Return every configured virtual domain."""
        return await self._http.get(
            "cmdb/system/vdom",
            params={"vdom": "*"},
            allow_list=True,
        )

    async def get_vdom_global_settings(self) -> dict[str, Any]:
        """Return the global settings that identify the management VDOM."""
        return await self._http.get("cmdb/system/global?format=management-vdom")

    async def get_global_dns(self, vdom: str) -> dict[str, Any]:
        """Return the global DNS configuration from one VDOM context."""
        return await self._http.get(
            "cmdb/system/dns",
            params={"vdom": vdom},
        )

    async def get_vdom_dns(self) -> dict[str, Any] | list[Any]:
        """Return DNS overrides for every virtual domain."""
        return await self._http.get(
            "cmdb/system/vdom-dns",
            params={"vdom": "*"},
            allow_list=True,
        )
