"""FortiOS API facade."""

from typing import Any

from aiohttp import ClientSession

from .client import FortiOSHttpClient
from .configuration import FortiOSConfigurationApi
from .context import FortiOSApiContext
from .monitor import FortiOSMonitorApi
from .version import FortiOSVersion
from .versions import async_enrich_system_status


class FortiOSApi:
    """Provide access to the organized FortiOS APIs."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        api_key: str,
        verify_ssl: bool,
        request_timeout: int = 60,
    ) -> None:
        """Initialize the FortiOS API."""
        self._http = FortiOSHttpClient(
            session,
            host,
            port,
            api_key,
            verify_ssl,
            request_timeout,
        )
        self.context = FortiOSApiContext()
        self.configuration = FortiOSConfigurationApi(self._http, self.context)
        self.monitor = FortiOSMonitorApi(self._http, self.context)

    @property
    def version(self) -> FortiOSVersion | None:
        """Return the detected FortiOS version."""
        return self.context.version

    async def async_initialize(self) -> dict[str, Any]:
        """Read and store the FortiOS version."""
        status = await self.monitor.system.get_status()
        version = status.get("version")

        if not isinstance(version, str):
            raise TypeError("FortiOS status response version must be a string")

        fortios_version = FortiOSVersion.parse(version)
        self.context.version = fortios_version

        return await async_enrich_system_status(
            status,
            self.context,
            self.configuration,
            self.monitor,
        )
