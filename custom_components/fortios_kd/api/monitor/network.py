"""FortiOS network Monitor API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSNetworkApi:
    """Provide network-related Monitor endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the network Monitor API."""
        self._http = http
        self._context = context

    async def get_arp_table(self) -> dict[str, Any]:
        """Return the IPv4 ARP table."""
        return await self._http.get("monitor/network/arp")

    async def get_dns_latency(self) -> dict[str, Any] | list[Any]:
        """Return runtime DNS latency for every virtual domain."""
        return await self._http.get(
            "monitor/network/dns/latency",
            params={"vdom": "*"},
            allow_list=True,
        )
