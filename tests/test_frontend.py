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
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredNamesByDevice(hass)" in source
    assert "preferredDeviceName(" in source
    assert 'action_name: "Open FortiGate"' in source
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
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredNamesByDevice(hass)" in source
    assert "preferredDeviceName(preferredNames, fortigate)" in source
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
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredDeviceName(" in source
    assert '["wifi_client_match", "WiFi client match"]' in source
    assert '["ip_conflict", "IP conflict"]' in source
    assert "class FortiOSKDARPEntryGrid extends HTMLElement" in source
    assert "type: `custom:${ARP_CARD_ELEMENT}`" in source


async def test_arp_table_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the ARP table links matches and shows their hostnames."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    table_path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-arp-table-dashboard.js"]
    source = table_path.read_text()

    assert 'type: "fortios-kd-arp-table"' in source
    assert 'title: "KD ARP Table"' in source
    assert 'entity: "select.arp_table_fortigate_filter"' in source
    assert 'entity: "select.arp_table_interface_filter"' in source
    assert 'entity: "select.arp_table_lease_type_filter"' in source
    assert 'name: "Firewall"' in source
    assert "selectedFortigate !== fortigateName" in source
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredNamesByDevice(hass)" in source
    assert "preferredDeviceName(" in source
    assert "!interfaces.includes(selectedInterface)" in source
    assert "selectedLeaseType !== leaseFilterValue" in source
    assert 'const FILTER_NO_DHCP_LEASE = "No DHCP lease"' in source
    assert "wifiClientsByMatchId" in source
    assert "dhcpHostnamesByMatchId" in source
    assert "dhcpLeaseTypesByMatchId" in source
    assert "accessPointsByMatchId" in source
    assert "accessPointsByScopedIp" in source
    assert "state.attributes.fortios_kd_match_id" in source
    assert "wifiClientsByMatchId.get(entry.matchId)" in source
    assert 'field === "hostnames"' in source
    assert "dhcpHostnamesByMatchId.get(entry.matchId)" in source
    assert 'field === "assignment_type"' in source
    assert 'state.state === "DHCP Reserved"' in source
    assert 'state.state === "DHCP"' in source
    assert "dhcpLeaseTypesByMatchId.get(entry.matchId)" in source
    assert 'fortios_kd_entry_type === "access_point"' in source
    assert 'field === "mac_address"' in source
    assert 'field === "ip_address"' in source
    assert "accessPointsByMatchId.get(entry.matchId)" in source
    assert "scopedIpKey(arpDevice.via_device_id, ipAddress)" in source
    assert "accessPointByMac || accessPointByIp" in source
    assert "`${accessPoint.name} (AP)`" in source
    assert "available: isCurrent(state)" in source
    assert "`${base}_hostname`" in source
    assert "`${base}_last_known_hostname`" in source
    assert "`${wifiClient.hostname} (WiFi)`" in source
    assert "`${dhcpHostname} (DHCP)`" in source
    assert "`(${wifiClient.lastKnownHostname}) (WiFi)`" in source
    assert 'iconLink(row.deviceId, "mdi:open-in-new", "Open ARP device")' in source
    assert 'iconLink(row.wifiDeviceId, "mdi:wifi", "Open WiFi client")' in source
    assert '"Device"' in source
    assert '"IP address"' in source
    assert '"Interface"' in source
    assert '"MAC address"' in source
    assert '"Hostname"' in source
    assert '"Lease type"' in source
    assert "textCell(row.hostname)" in source
    assert "textCell(row.dhcpLeaseType)" in source
    assert "class FortiOSKDARPTable extends HTMLElement" in source
    assert "type: `custom:${ARP_TABLE_CARD_ELEMENT}`" in source


async def test_dhcp_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test that the DHCP dashboard discovers entries and exposes filters."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    dhcp_path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-dhcp-dashboard.js"]
    source = dhcp_path.read_text()

    assert 'type: "fortios-kd-dhcp-entries"' in source
    assert 'title: "KD DHCP Entries"' in source
    assert 'entity: "select.dhcp_entries_fortigate_filter"' in source
    assert 'entity: "select.dhcp_entries_interface_filter"' in source
    assert 'name: "Firewall"' in source
    assert 'name: "Interface"' in source
    assert 'fortios_kd_entry_type !== "dhcp_entry"' in source
    assert "fortios_kd_dhcp_field" in source
    assert 'entry.fields.get("mac_address")' in source
    assert 'entry.fields.get("interfaces")' in source
    assert "selectedFortigate !== fortigateName" in source
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredNamesByDevice(hass)" in source
    assert "preferredDeviceName(" in source
    assert "!interfaces.includes(selectedInterface)" in source
    assert "`${ipAddress} - ${interfaceName}`" in source
    assert 'action_name: "Open DHCP device"' in source
    assert 'action_name: "Open FortiGate"' in source
    assert 'action_name: "Open WiFi client"' in source
    assert '["assignment_type", "IP assignment type"]' in source
    assert '["lease_expiration", "Latest lease expiration"]' in source
    assert "class FortiOSKDDHCPEntryGrid extends HTMLElement" in source
    assert "type: `custom:${DHCP_CARD_ELEMENT}`" in source


async def test_vdom_resource_dashboard_strategy_asset(hass: HomeAssistant) -> None:
    """Test the VDOM resource dashboard discovers and groups resource graphs."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-vdom-resources-dashboard.js"]
    source = path.read_text()

    assert 'type: "fortios-kd-vdom-resources"' in source
    assert 'title: "KD VDOM Resources"' in source
    assert 'entity: "select.vdom_resources_firewall_filter"' in source
    assert 'entity: "select.vdom_resources_vdom_filter"' in source
    assert 'entity: "select.vdom_resources_graph_layout"' in source
    assert 'name: "Firewall"' in source
    assert 'name: "VDOM"' in source
    assert 'name: "Graph layout"' in source
    assert 'state.attributes.fortios_kd_scope !== "vdom"' in source
    assert "fortios_kd_vdom" in source
    assert 'metric: "cpu"' in source
    assert 'metric: "memory"' in source
    assert 'metric: "session_current_usage"' in source
    assert 'metric: "session_usage_percent"' in source
    assert 'title: "Session Usage Percent"' in source
    assert "vdomDevice?.via_device_id" in source
    assert 'from "./fortios-kd-preferred-names.js"' in source
    assert "preferredNamesByDevice(hass)" in source
    assert "preferredDeviceName(" in source
    assert "class FortiOSKDVDOMResourceGraphGrid extends HTMLElement" in source
    assert "type: `custom:${VDOM_GRAPH_CARD_ELEMENT}`" in source
    assert 'const GRAPH_LAYOUT_COMBINED = "Combined by resource"' in source
    assert 'const GRAPH_LAYOUT_SEPARATE = "Separate by VDOM"' in source
    assert 'key: "combined"' in source
    assert "name: `${item.fortigateName} · ${item.vdomName}`" in source
    assert "group.entitiesByMetric.get(graph.metric)" in source
    assert "title.textContent = group.title" in source
    assert "applyHistoryGraphLegendLayout" in source
    assert "display: grid !important" in source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr)) !important" in source
    assert "justify-self: end" in source
    assert "chartRoot.adoptedStyleSheets" in source
    assert "new IntersectionObserver" in source
    assert 'rootMargin: "200px 0px"' in source


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

    assert len(FRONTEND_ASSETS) == 8
    assert len(FRONTEND_MODULE_URLS) == 1
    assert FRONTEND_MODULE_URLS[0].startswith(f"{FRONTEND_LOADER_URL}?v=")

    loader_source = FRONTEND_LOADER_PATH.read_text()
    assert 'import "./fortios-kd-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-wifi-graphs-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-arp-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-arp-table-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-dhcp-dashboard.js";' in loader_source
    assert 'import "./fortios-kd-vdom-resources-dashboard.js";' in loader_source


async def test_preferred_name_frontend_helper(hass: HomeAssistant) -> None:
    """Test dashboard aliases are discovered from device-linked text entities."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.frontend import FRONTEND_ASSETS  # noqa: PLC0415

    path = FRONTEND_ASSETS["/fortios_kd/fortios-kd-preferred-names.js"]
    source = path.read_text()

    assert '"fortios_kd_preferred_name_scope"' in source
    assert 'scope = "fortigate"' in source
    assert "registryEntry(hass.entities, state.entity_id)" in source
    assert "names.set(entity.device_id, preferredName)" in source
    assert "preferredNames.get(device.id)" in source
