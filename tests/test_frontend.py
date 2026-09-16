"""Tests for the FortiOS KD frontend resources."""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

DOMAIN = "fortios_kd"


async def test_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the bundled dashboard strategy exposes the expected filters."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_PATH  # noqa: PLC0415

    source = FRONTEND_PATH.read_text()

    assert "customElements.define(STRATEGY_ELEMENT" in source
    assert 'type: "fortios-kd"' in source
    assert 'strategyType: "dashboard"' in source
    assert 'entity: "select.wifi_client_fortigate_filter"' in source
    assert 'entity: "select.wifi_client_ap_filter"' in source
    assert 'entity: "select.wifi_client_ssid_filter"' in source
    assert 'entity: "select.wifi_client_area_filter"' in source
    assert 'entity: "select.wifi_client_label_filter"' in source
    assert 'type: "custom:auto-entities"' in source
    assert 'type: "custom:layout-card"' in source
    assert 'title: "KD Wifi Clients"' in source
