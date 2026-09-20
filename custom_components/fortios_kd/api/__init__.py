"""FortiOS API facade."""

import logging
from typing import Any

from aiohttp import ClientSession

from .client import FortiOSHttpClient
from .configuration import FortiOSConfigurationApi
from .context import FortiOSApiContext
from .monitor import FortiOSMonitorApi
from .version import FortiOSVersion
from .versions import async_enrich_system_status

_LOGGER = logging.getLogger(__name__)


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
        self.context = FortiOSApiContext()
        self._status: dict[str, Any] | None = None
        self._http = FortiOSHttpClient(
            session,
            host,
            port,
            api_key,
            verify_ssl,
            request_timeout,
            self._observe_response,
        )
        self.configuration = FortiOSConfigurationApi(self._http, self.context)
        self.monitor = FortiOSMonitorApi(self._http, self.context)

    def _observe_response(self, response: dict[str, Any]) -> None:
        """Refresh the cached FortiOS version from any API response."""
        version_text = response.get("version")
        if not isinstance(version_text, str):
            return

        try:
            version = FortiOSVersion.parse(version_text)
        except ValueError:
            _LOGGER.debug("Ignoring invalid FortiOS response version %r", version_text)
            return

        previous_version = self.context.version
        self.context.version = version
        self.context.version_text = version_text.strip()
        if self._status is not None:
            self._status["version"] = self.context.version_text

        if previous_version is not None and previous_version != version:
            _LOGGER.info(
                "FortiOS version changed from %s.%s.%s to %s",
                previous_version.major,
                previous_version.minor,
                previous_version.patch,
                self.context.version_text,
            )

    @property
    def version(self) -> FortiOSVersion | None:
        """Return the detected FortiOS version."""
        return self.context.version

    @property
    def version_text(self) -> str | None:
        """Return the latest FortiOS version text reported by the API."""
        return self.context.version_text

    @property
    def supports_network_arp(self) -> bool:
        """Return whether this FortiOS release provides the ARP monitor."""
        return self.version is not None and self.version >= FortiOSVersion(6, 4, 0)

    async def async_initialize(self) -> dict[str, Any]:
        """Read and store the FortiOS version."""
        status = await self.monitor.system.get_status()
        version = status.get("version")

        if not isinstance(version, str):
            raise TypeError("FortiOS status response version must be a string")

        fortios_version = FortiOSVersion.parse(version)
        self.context.version = fortios_version
        self.context.version_text = version.strip()

        status = await async_enrich_system_status(
            status,
            self.context,
            self.configuration,
            self.monitor,
        )
        self._status = status
        return status
