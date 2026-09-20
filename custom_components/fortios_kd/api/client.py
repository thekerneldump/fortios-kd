"""Shared HTTP transport for the FortiOS API."""

from collections.abc import Callable, Mapping
from typing import Any, Literal, overload

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
        response_observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the authenticated HTTP client."""
        self._session = session
        self._base_url = f"https://{host}:{port}/api/v2"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)
        self._response_observer = response_observer

    @overload
    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
        allow_list: Literal[False] = False,
    ) -> dict[str, Any]:
        ...

    @overload
    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
        allow_list: Literal[True],
    ) -> dict[str, Any] | list[Any]:
        ...

    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
        allow_list: bool = False,
    ) -> dict[str, Any] | list[Any]:
        """Return JSON from a FortiGate GET endpoint."""
        async with self._session.get(
            f"{self._base_url}/{endpoint.lstrip('/')}",
            headers=self._headers,
            params=params,
            ssl=self._verify_ssl,
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            data = await response.json()
            if not isinstance(data, (dict, list)):
                raise TypeError("FortiOS API response must be an object or list")
            if isinstance(data, list) and not allow_list:
                raise TypeError("FortiOS API returned an unexpected list response")
            if self._response_observer is not None:
                if isinstance(data, dict):
                    self._response_observer(data)
                else:
                    for item in data:
                        if isinstance(item, dict):
                            self._response_observer(item)
            return data
