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
    assert 'state.attributes.fortios_kd_entry_type === "wifi_client"' in source
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


async def test_arp_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the ARP dashboard discovers only current ARP entries."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    arp_path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-arp-dashboard.js"]
    source = arp_path.read_text()

    assert 'type: "fortios-kd-arp-entries"' in source
    assert 'title: "KD ARP Entries"' in source
    assert 'state.attributes.fortios_kd_entry_type !== "arp_entry"' in source
    assert "fortios_kd_arp_field" in source
    assert 'entry.fields.get("mac_address")' in source
    assert 'entry.fields.get("interfaces")' in source
    assert "`${ipAddress} - ${interfaceName}`" in source
    assert "if (!isCurrent(macState))" in source
    assert 'action_name: "Open ARP device"' in source
    assert 'action_name: "Open FortiGate"' in source
    assert '["wifi_client_match", "WiFi client match"]' in source
    assert '["ip_conflict", "IP conflict"]' in source
    assert "class FortiOSKDARPEntryGrid extends HTMLElement" in source
    assert "type: `custom:${ARP_CARD_ELEMENT}`" in source


async def test_arp_table_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the compact ARP table links exact matched devices."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    table_path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-arp-table-dashboard.js"]
    source = table_path.read_text()

    assert 'type: "fortios-kd-arp-table"' in source
    assert 'title: "KD ARP Table"' in source
    assert "wifiDevicesByMatchId" in source
    assert "state.attributes.fortios_kd_match_id" in source
    assert "wifiDevicesByMatchId.get(entry.matchId)" in source
    assert 'matchState.state !== "Not currently detected"' in source
    assert 'iconLink(row.deviceId, "mdi:open-in-new", "Open ARP device")' in source
    assert 'iconLink(row.wifiDeviceId, "mdi:wifi", "Open WiFi client")' in source
    assert '"Device"' in source
    assert '"IP address"' in source
    assert '"Interface"' in source
    assert '"MAC address"' in source
    assert "class FortiOSKDARPTable extends HTMLElement" in source
    assert "type: `custom:${ARP_TABLE_CARD_ELEMENT}`" in source


async def test_all_frontend_assets_are_loaded(hass: HomeAssistant) -> None:
    """Test that one loader imports every dashboard strategy module."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import (  # noqa: PLC0415
        FRONTEND_ASSETS,
        FRONTEND_LOADER_PATH,
        FRONTEND_LOADER_URL,
        FRONTEND_MODULE_URLS,
    )

    assert len(FRONTEND_ASSETS) == 5
    assert len(FRONTEND_MODULE_URLS) == 1
    assert FRONTEND_MODULE_URLS[0].startswith(f"{FRONTEND_LOADER_URL}?v=")

    loader_source = FRONTEND_LOADER_PATH.read_text()
    assert 'import "./fortios-kd-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-wifi-graphs-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-arp-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-arp-table-dashboard.js";' in loader_source
