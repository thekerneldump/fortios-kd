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
