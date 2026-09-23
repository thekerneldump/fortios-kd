"""Tests for bounded malformed-response diagnostics."""

from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock, Mock, patch

import pytest


class _FakeResponse:
    """Minimal aiohttp response used by the transport tests."""

    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        """Represent a successful response."""

    async def read(self) -> bytes:
        """Return the configured response bytes."""
        return self._body

    def get_encoding(self) -> str:
        """Return the JSON response encoding."""
        return "utf-8"


class _FakeSession:
    """Minimal aiohttp session returning one reusable response."""

    def __init__(self, body: bytes) -> None:
        self.response = _FakeResponse(body)
        self.request_headers: dict[str, str] | None = None

    def get(self, _url: str, **kwargs: Any) -> _FakeResponse:
        """Return the configured response context manager."""
        self.request_headers = kwargs.get("headers")
        return self.response


@pytest.mark.asyncio
async def test_invalid_utf8_is_repaired_and_context_is_bounded() -> None:
    """Test one invalid byte is replaced without rejecting valid JSON."""
    from custom_components.fortios_kd.api.client import (  # noqa: PLC0415
        FortiOSHttpClient,
    )
    from custom_components.fortios_kd.debug import (  # noqa: PLC0415
        DEBUG_CAPTURE_MODE_CONTEXT,
        FortiOSDebugCaptureStore,
    )

    prefix = b'{"results":[{"hostname":"' + (b"a" * 150)
    suffix = b'","serial":"FGT70FSECRET","padding":"' + (b"b" * 150) + b'"}]}'
    body = prefix + b"\xff" + suffix
    session = _FakeSession(body)
    store = FortiOSDebugCaptureStore(
        enabled=True,
        mode=DEBUG_CAPTURE_MODE_CONTEXT,
        limit=3,
    )
    store.set_fortigate_serial("FGT70FSECRET")
    client = FortiOSHttpClient(
        session,  # type: ignore[arg-type]
        "fortigate.example",
        443,
        "secret-api-key",
        False,
        debug_capture_store=store,
    )

    result = await client.get("monitor/wifi/client")

    assert "�" in result["results"][0]["hostname"]
    diagnostics = store.diagnostics()
    assert diagnostics["capture_count"] == 1
    capture = diagnostics["captures"][0]
    context = capture["response_context"]
    assert context["end"] - context["start"] == 201
    assert "ff" in context["hex"].split()
    assert "secret-api-key" not in str(diagnostics)
    assert "FGT70FSECRET" not in str(diagnostics)
    assert b"FGT70FSECRET" not in bytes.fromhex(context["hex"])
    assert session.request_headers == {"Authorization": "Bearer secret-api-key"}


@pytest.mark.asyncio
async def test_full_capture_redacts_serial_and_stops_at_limit() -> None:
    """Test full captures are parsed, redacted, and bounded."""
    from custom_components.fortios_kd.api.client import (  # noqa: PLC0415
        FortiOSHttpClient,
    )
    from custom_components.fortios_kd.debug import (  # noqa: PLC0415
        DEBUG_CAPTURE_MODE_FULL,
        REDACTED,
        FortiOSDebugCaptureStore,
    )

    body = b'{"results":[{"hostname":"bad\xffname"}],"serial":"FGT70FSECRET"}'
    store = FortiOSDebugCaptureStore(
        enabled=True,
        mode=DEBUG_CAPTURE_MODE_FULL,
        limit=3,
    )
    client = FortiOSHttpClient(
        _FakeSession(body),  # type: ignore[arg-type]
        "fortigate.example",
        443,
        "secret-api-key",
        False,
        debug_capture_store=store,
    )

    for _ in range(4):
        await client.get("monitor/wifi/client")

    diagnostics = store.diagnostics()
    assert diagnostics["capture_count"] == 3
    assert diagnostics["capture_limit_reached"] is True
    assert all(
        capture["response"]["serial"] == REDACTED for capture in diagnostics["captures"]
    )


@pytest.mark.asyncio
async def test_unrepairable_response_raises_controlled_error() -> None:
    """Test invalid bytes outside a JSON string raise a transport error."""
    from custom_components.fortios_kd.api.client import (  # noqa: PLC0415
        FortiOSHttpClient,
        FortiOSResponseError,
    )
    from custom_components.fortios_kd.debug import (  # noqa: PLC0415
        DEBUG_CAPTURE_MODE_CONTEXT,
        FortiOSDebugCaptureStore,
    )

    store = FortiOSDebugCaptureStore(
        enabled=True,
        mode=DEBUG_CAPTURE_MODE_CONTEXT,
        limit=3,
    )
    client = FortiOSHttpClient(
        _FakeSession(b'{"results":\xff}'),  # type: ignore[arg-type]
        "fortigate.example",
        443,
        "secret-api-key",
        False,
        debug_capture_store=store,
    )

    with pytest.raises(FortiOSResponseError, match="could not be repaired"):
        await client.get("monitor/wifi/client")

    assert store.count == 1


@pytest.mark.asyncio
async def test_wifi_client_failure_does_not_block_other_coordinator_data() -> None:
    """Test a wifi-client failure does not reject an otherwise valid refresh."""
    from aiohttp import ClientConnectionError  # noqa: PLC0415
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.supports_network_arp = True
    client.monitor.wifi.get_managed_access_points = AsyncMock(
        return_value={"results": []}
    )
    client.monitor.wifi.get_clients = AsyncMock(
        side_effect=ClientConnectionError("malformed response")
    )
    client.configuration.wifi.get_vaps = AsyncMock(return_value={"results": []})

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = FortiOSKDCoordinator(
            Mock(),
            client,
            include_unassigned_ssids=True,
        )

    coordinator._async_load_wifi_meta = AsyncMock()  # noqa: SLF001
    coordinator._async_load_ap_names = AsyncMock()  # noqa: SLF001
    coordinator._async_load_ap_channel_capabilities = AsyncMock()  # noqa: SLF001
    coordinator._async_get_arp_table = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "supported": False}
    )
    coordinator._async_get_dhcp_leases = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "available": False}
    )
    coordinator._async_get_device_inventory = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "available": False}
    )
    coordinator._async_get_vdom_inventory = AsyncMock(  # noqa: SLF001
        return_value={
            "results": [{"name": "root"}],
            "available": True,
            "management_vdom": "root",
        }
    )
    coordinator._async_get_interfaces = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "available": False}
    )
    coordinator._async_get_available_interfaces = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "available": False}
    )
    coordinator._async_get_vdom_resources = AsyncMock(  # noqa: SLF001
        return_value={"results": {}, "available": True}
    )
    coordinator._async_get_dns_servers = AsyncMock(  # noqa: SLF001
        return_value={"results": [], "available": True}
    )

    data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["wifi_clients"] == {"results": [], "available": False}
    assert data["vdoms"]["results"] == [{"name": "root"}]
    assert data["vdoms"]["available"] is True


@pytest.mark.asyncio
async def test_diagnostics_returns_only_bounded_capture_data() -> None:
    """Test Home Assistant diagnostics exposes the in-memory capture store."""
    from custom_components.fortios_kd.const import DOMAIN  # noqa: PLC0415
    from custom_components.fortios_kd.debug import (  # noqa: PLC0415
        DEBUG_CAPTURE_MODE_CONTEXT,
        FortiOSDebugCaptureStore,
    )
    from custom_components.fortios_kd.diagnostics import (  # noqa: PLC0415
        async_get_config_entry_diagnostics,
    )

    store = FortiOSDebugCaptureStore(
        enabled=True,
        mode=DEBUG_CAPTURE_MODE_CONTEXT,
        limit=3,
    )
    hass = SimpleNamespace(data={DOMAIN: {"entry-id": {"debug_capture_store": store}}})
    entry = SimpleNamespace(entry_id="entry-id")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert diagnostics["capture_enabled"] is True
    assert diagnostics["capture_limit"] == 3
    assert diagnostics["captures"] == []
