"""Shared HTTP transport for the FortiOS API."""

from collections.abc import Callable, Mapping
import json
import logging
from typing import Any, Literal, overload

from aiohttp import ClientError, ClientSession, ClientTimeout
from custom_components.fortios_kd.debug import FortiOSDebugCaptureStore

_LOGGER = logging.getLogger(__name__)


class FortiOSResponseError(ClientError):
    """Error raised when a FortiOS response cannot be decoded as JSON."""


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
        debug_capture_store: FortiOSDebugCaptureStore | None = None,
    ) -> None:
        """Initialize the authenticated HTTP client."""
        self._session = session
        self._base_url = f"https://{host}:{port}/api/v2"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)
        self._response_observer = response_observer
        self._debug_capture_store = debug_capture_store
        self._decode_warning_endpoints: set[str] = set()
        self._capture_limit_warning_logged = False

    @overload
    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
        allow_list: Literal[False] = False,
    ) -> dict[str, Any]: ...

    @overload
    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str] | None = None,
        allow_list: Literal[True],
    ) -> dict[str, Any] | list[Any]: ...

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
            body = (await response.read()).strip()
            get_encoding = getattr(response, "get_encoding", None)
            encoding = get_encoding() if callable(get_encoding) else "utf-8"
            try:
                response_text = body.decode(encoding)
            except UnicodeDecodeError as err:
                response_text = body.decode(encoding, errors="replace")
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as json_err:
                    self._capture_malformed_response(
                        endpoint=endpoint,
                        http_status=response.status,
                        body=body,
                        encoding=encoding,
                        error=err,
                        byte_start=err.start,
                        byte_end=err.end,
                        repaired_data=None,
                    )
                    raise FortiOSResponseError(
                        f"FortiOS API response from {endpoint} contains invalid "
                        "UTF-8 and could not be repaired"
                    ) from json_err

                self._capture_malformed_response(
                    endpoint=endpoint,
                    http_status=response.status,
                    body=body,
                    encoding=encoding,
                    error=err,
                    byte_start=err.start,
                    byte_end=err.end,
                    repaired_data=data,
                )
                if endpoint not in self._decode_warning_endpoints:
                    _LOGGER.warning(
                        "FortiOS API response from %s contained invalid %s at "
                        "byte %s; replaced the malformed data and continued",
                        endpoint,
                        encoding,
                        err.start,
                    )
                    self._decode_warning_endpoints.add(endpoint)
            else:
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as err:
                    byte_start = len(response_text[: err.pos].encode(encoding))
                    self._capture_malformed_response(
                        endpoint=endpoint,
                        http_status=response.status,
                        body=body,
                        encoding=encoding,
                        error=err,
                        byte_start=byte_start,
                        byte_end=min(len(body), byte_start + 1),
                        repaired_data=None,
                    )
                    raise FortiOSResponseError(
                        f"FortiOS API response from {endpoint} is not valid JSON"
                    ) from err
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

    def _capture_malformed_response(
        self,
        *,
        endpoint: str,
        http_status: int,
        body: bytes,
        encoding: str,
        error: UnicodeDecodeError | ValueError,
        byte_start: int,
        byte_end: int,
        repaired_data: Any | None,
    ) -> None:
        """Store one malformed response when opt-in capture is enabled."""
        store = self._debug_capture_store
        if store is None:
            return
        capture_number = store.capture(
            endpoint=endpoint,
            http_status=http_status,
            body=body,
            encoding=encoding,
            error=error,
            byte_start=byte_start,
            byte_end=byte_end,
            repaired_data=repaired_data,
        )
        if capture_number is not None:
            _LOGGER.warning(
                "Captured malformed response %s of %s from %s; download the "
                "FortiOS KD diagnostics to review it",
                capture_number,
                store.limit,
                endpoint,
            )
        elif (
            store.enabled
            and store.limit_reached
            and not self._capture_limit_warning_logged
        ):
            _LOGGER.warning(
                "Malformed-response capture limit of %s reached; additional "
                "responses will not be stored",
                store.limit,
            )
            self._capture_limit_warning_logged = True
