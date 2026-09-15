"""FortiOS wifi configuration API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSWifiConfigurationApi:
    """Provide wifi-related configuration endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the wifi configuration API."""
        self._http = http
        self._context = context

    async def get_vaps(self) -> dict[str, Any]:
        """Return configured wireless VAPs and their broadcast SSIDs."""
        return await self._http.get(
            "cmdb/wireless-controller/vap?format=name|ssid|local-bridging"
        )

    async def get_wtp_profiles(self) -> dict[str, Any]:
        """Return configured FortiAP profiles and their VAP assignments."""
        return await self._http.get("cmdb/wireless-controller/wtp-profile")
