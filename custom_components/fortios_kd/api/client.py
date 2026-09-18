"""Shared HTTP transport for the FortiOS API."""

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientSession, ClientTimeout


class FortiOSHttpClient:
    """Make authenticated HTTP requests to a FortiGate."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        api_key: str,
        verify_ssl: bool,
        request_timeout: int = 60,
    ) -> None:
        """Initialize the authenticated HTTP client."""
        self._session = session
        self._base_url = f"https://{host}:{port}/api/v2"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)

    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return JSON from a FortiGate GET endpoint."""
        async with self._session.get(
            f"{self._base_url}/{endpoint.lstrip('/')}",
            headers=self._headers,
            params=params,
            ssl=self._verify_ssl,
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            return await response.json()
