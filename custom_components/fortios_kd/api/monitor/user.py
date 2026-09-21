"""FortiOS user Monitor API."""

from typing import Any

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext


class FortiOSUserApi:
    """Provide user and detected-device Monitor endpoints."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the user Monitor API."""
        self._http = http
        self._context = context

    async def get_devices(self) -> dict[str, Any]:
        """Return devices detected by the FortiGate."""
        return await self._http.get("monitor/user/device")
