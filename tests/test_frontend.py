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
    assert "class FortiOSKDWifiClientGrid extends HTMLElement" in source
    assert "registryEntry(hass.entities, macState.entity_id)" in source
    assert "registryEntry(hass.devices, entity?.device_id)" in source
    assert "clientDevice?.via_device_id" in source
    assert 'selectedSsid === "Unavailable Clients"' in source
    assert "type: `custom:${CLIENT_CARD_ELEMENT}`" in source
    assert "custom:auto-entities" not in source
    assert "custom:layout-card" not in source
    assert 'title: "KD Wifi Clients"' in source


async def test_wifi_graph_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the graph dashboard discovers and filters radio metrics."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    graph_path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-wifi-graphs-dashboard.js"]
    source = graph_path.read_text()

    assert 'type: "fortios-kd-wifi-graphs"' in source
    assert 'title: "KD Wifi Graphs"' in source
    assert 'entity: "select.wifi_client_fortigate_filter"' in source
    assert 'entity: "select.wifi_client_ap_filter"' in source
    assert 'entity: "select.wifi_client_ssid_filter"' in source
    assert "fortios_kd_metric" in source
    assert "fortios_kd_radio_id" in source
    assert "fortios_kd_band" in source
    assert "tx_bits_per_second" in source
    assert "bandwidth_rx" in source
    assert "OVERVIEW_GRAPHS" in source
    assert 'metric: "oper_chan"' in source
    assert 'metric: "clients"' in source
    assert 'metric: "cpu_usage"' in source
    assert 'metric: "mem_free"' in source
    assert 'scope: "ap"' in source
    assert 'scope: "radio"' in source
    assert "channel_utilization_percent" in source
    assert "mac_errors_tx" in source
    assert "mac_errors_rx" in source
    assert "tx_mac_errors_per_minute" in source
    assert "rx_mac_errors_per_minute" in source
    assert "noise_floor" in source
    assert 'metric: "mem_total"' in source
    assert 'dashboardView("Wifi Overview", "wifi-overview", "overview")' in source
    assert 'dashboardView("Radio Health"' not in source
    assert "class FortiOSKDWifiGraphGrid extends HTMLElement" in source
    assert "registryEntry(hass.entities, state.entity_id)" in source
    assert "registryEntry(hass.devices, deviceId)" in source
    assert "device?.via_device_id" in source
    assert "Array.isArray(ssids)" in source
    assert "not per-SSID measurements" in source
    assert "name: accessPointName" in source
    assert "`${accessPointName} · radio" not in source
    assert "applyHistoryGraphLegendLayout" in source
    assert "display: grid !important" in source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important" in source
    assert "justify-self: end" in source
    assert "expand_legend: true" in source
    assert "chartRoot.adoptedStyleSheets" in source
    assert ".chart-legend li:has(ha-assist-chip)" in source
    assert "new IntersectionObserver" in source
    assert 'rootMargin: "200px 0px"' in source
    assert "type: `custom:${GRAPH_CARD_ELEMENT}`" in source
    assert "custom:auto-entities" not in source


async def test_all_frontend_assets_are_loaded(hass: HomeAssistant) -> None:
    """Test that Home Assistant loads both dashboard strategy modules."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import (  # noqa: PLC0415
        FRONTEND_ASSETS,
        FRONTEND_MODULE_URLS,
    )

    assert len(FRONTEND_MODULE_URLS) == len(FRONTEND_ASSETS) == 2
    for url in FRONTEND_ASSETS:
        assert any(
            module_url.startswith(f"{url}?v=") for module_url in FRONTEND_MODULE_URLS
        )
