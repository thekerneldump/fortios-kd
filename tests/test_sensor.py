"""Tests for FortiOS KD sensors."""

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.core import State


def test_registered_wifi_client_macs() -> None:
    """Test extracting previously registered clients for one FortiGate."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        _registered_wifi_client_macs,
    )

    entries = [
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_wifi_client_aa:bb:cc:dd:ee:ff_mac_address",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_wifi_client_aa:bb:cc:dd:ee:ff_ssid",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT999_wifi_client_11:22:33:44:55:66_mac_address",
        ),
        SimpleNamespace(
            domain="select",
            platform="fortios_kd",
            unique_id="wifi_client_ssid_filter",
        ),
    ]

    assert _registered_wifi_client_macs(entries, "FGT123") == {"aa:bb:cc:dd:ee:ff"}


def test_registered_arp_macs() -> None:
    """Test extracting previously registered ARP devices."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        _registered_arp_macs,
    )

    entries = [
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_arp_aa:bb:cc:dd:ee:ff_ip_addresses",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_arp_aa:bb:cc:dd:ee:ff_interfaces",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT999_arp_11:22:33:44:55:66_ip_addresses",
        ),
    ]

    assert _registered_arp_macs(entries, "FGT123") == {"aa:bb:cc:dd:ee:ff"}


def test_arp_entities_use_separate_device_and_aggregate_rows() -> None:
    """Test ARP rows use a separate device and aggregate duplicate MACs."""
    from custom_components.fortios_kd.sensor import create_arp_entities  # noqa: PLC0415

    mac = "aa:bb:cc:dd:ee:ff"
    match_id = sha256(f"fortios_kd\0FGT123\0{mac}".encode()).hexdigest()
    entries = [
        {
            "mac": mac,
            "ip": "192.0.2.10",
            "interface": "lan",
            "age": 4,
            "vdom": "root",
        },
        {
            "mac": mac,
            "ip": "192.0.2.11",
            "interface": "guest",
            "age": 1,
            "vdom": "root",
        },
    ]
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.match_arp_wifi_clients = True
    coordinator.get_arp_entries.return_value = entries
    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "hostname": "TestPhone",
    }
    coordinator.get_wifi_clients_by_ip.return_value = []
    coordinator.get_arp_entries_by_ip.side_effect = lambda ip: [
        entry for entry in entries if entry["ip"] == ip
    ]

    entities = create_arp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        False,
    )
    values = {entity.name: entity.native_value for entity in entities}

    assert values == {
        "ARP MAC Address": mac,
        "ARP IP Addresses": "192.0.2.10, 192.0.2.11",
        "ARP Interfaces": "guest, lan",
        "ARP Age": 1,
        "ARP VDOMs": "root",
        "WiFi Client Match": "TestPhone",
        "IP Conflict": "Clear",
    }
    assert entities[0].device_info["identifiers"] == {
        ("fortios_kd", f"FGT123_arp_{mac}")
    }
    assert entities[0].device_info["name"] == f"ARP Device {mac} (TestGate)"
    assert entities[0].extra_state_attributes == {
        "fortios_kd_entry_type": "arp_entry",
        "fortios_kd_arp_field": "mac_address",
        "fortios_kd_match_id": match_id,
    }


def test_arp_ip_conflict_reports_masked_claimants() -> None:
    """Test conflicting wifi and ARP claims are diagnostic, not identity links."""
    from custom_components.fortios_kd.sensor import create_arp_entities  # noqa: PLC0415

    mac = "aa:bb:cc:dd:ee:ff"
    match_id = sha256(f"fortios_kd\0FGT123\0{mac}".encode()).hexdigest()
    other_mac = "11:22:33:44:55:66"
    ip_address = "192.0.2.10"
    own_entry = {"mac": mac, "ip": ip_address}
    other_arp_entry = {"mac": other_mac, "ip": ip_address}
    other_wifi_client = {
        "mac": other_mac,
        "ip": ip_address,
        "hostname": "OtherPhone",
    }
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.match_arp_wifi_clients = True
    coordinator.get_arp_entries.return_value = [own_entry]
    coordinator.get_arp_entries_by_ip.return_value = [own_entry, other_arp_entry]
    coordinator.get_wifi_clients_by_ip.return_value = [other_wifi_client]

    entities = create_arp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        True,
        True,
    )
    conflict_entity = next(
        entity for entity in entities if entity.name == "IP Conflict"
    )

    assert conflict_entity.native_value == "Possible conflict"
    assert conflict_entity.extra_state_attributes == {
        "fortios_kd_entry_type": "arp_entry",
        "fortios_kd_arp_field": "ip_conflict",
        "fortios_kd_match_id": match_id,
        "conflict_count": 1,
        "conflicting_claimants": [
            {
                "ip_address": ip_address,
                "mac_address": "11:22:33:**:**:**",
                "sources": ["wifi_client", "arp"],
                "hostname": "Othe******",
            }
        ],
    }


def test_arp_wifi_matching_can_be_disabled() -> None:
    """Test disabling wifi matching preserves independent ARP diagnostics."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_arp_entities,
        create_wifi_client_entities,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    other_mac = "11:22:33:44:55:66"
    ip_address = "192.0.2.10"
    own_entry = {"mac": mac, "ip": ip_address}
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.match_arp_wifi_clients = False
    coordinator.get_wifi_client.return_value = None
    coordinator.get_arp_entries.return_value = [own_entry]
    coordinator.get_arp_entries_by_ip.return_value = [own_entry]
    coordinator.get_wifi_clients_by_ip.return_value = [
        {"mac": other_mac, "ip": ip_address, "hostname": "OtherPhone"}
    ]

    arp_entities = create_arp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        False,
    )
    names = {entity.name for entity in arp_entities}
    conflict_entity = next(
        entity for entity in arp_entities if entity.name == "IP Conflict"
    )

    assert "WiFi Client Match" not in names
    assert conflict_entity.native_value == "Clear"
    coordinator.get_wifi_clients_by_ip.assert_not_called()

    wifi_entities = create_wifi_client_entities(
        coordinator,
        {"mac": mac},
        "FGT123",
        "TestGate",
        {
            "mac": False,
            "hostname": False,
            "ssid": False,
            "vlan_id": False,
            "wtp_name": False,
        },
    )
    ip_entity = next(entity for entity in wifi_entities if entity.name == "IP Address")

    assert not ip_entity.available
    assert ip_entity.native_value is None


def test_arp_wifi_client_match_respects_hostname_masking() -> None:
    """Test the reverse ARP-to-wifi diagnostic and hostname masking."""
    from custom_components.fortios_kd.sensor import create_arp_entities  # noqa: PLC0415

    mac = "aa:bb:cc:dd:ee:ff"
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_arp_entries.return_value = [{"mac": mac, "ip": "192.0.2.10"}]
    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "hostname": "TestPhone",
    }

    entities = create_arp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        False,
        True,
    )
    match_entity = next(
        entity for entity in entities if entity.name == "WiFi Client Match"
    )

    assert match_entity.native_value == "Test*****"

    coordinator.get_wifi_client.return_value = None

    assert match_entity.native_value == "Not currently detected"


def test_arp_device_masks_mac_and_becomes_unavailable() -> None:
    """Test standalone ARP devices respect masking and availability."""
    from custom_components.fortios_kd.sensor import create_arp_entities  # noqa: PLC0415

    mac = "aa:bb:cc:dd:ee:ff"
    entries = [{"mac": mac, "ip": "192.0.2.10"}]
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_arp_entries.side_effect = lambda _mac: entries

    entities = create_arp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        True,
    )

    assert entities[0].native_value == "aa:bb:cc:**:**:**"
    assert entities[0].device_info["name"] == (
        "ARP Device aa:bb:cc:**:**:** (TestGate)"
    )
    assert entities[0].available

    entries.clear()

    assert not entities[0].available


def test_wifi_client_ip_falls_back_to_arp() -> None:
    """Test a wifi-client IP remains populated from an exact ARP MAC match."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_wifi_client_entities,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    clients_by_mac: dict[str, dict[str, str]] = {}
    arp_entries = [
        {"mac": mac, "ip": "192.0.2.11"},
        {"mac": mac, "ip": "192.0.2.10"},
    ]
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_wifi_client.side_effect = clients_by_mac.get
    coordinator.get_arp_entries.return_value = arp_entries

    entities = create_wifi_client_entities(
        coordinator,
        {"mac": mac},
        "FGT123",
        "TestGate",
        {
            "mac": False,
            "hostname": False,
            "ssid": False,
            "vlan_id": False,
            "wtp_name": False,
        },
    )
    ip_entity = next(entity for entity in entities if entity.name == "IP Address")

    assert ip_entity.available
    assert ip_entity.native_value == "192.0.2.10, 192.0.2.11"

    clients_by_mac[mac] = {"mac": mac, "ip": "192.0.2.12"}

    assert ip_entity.available
    assert ip_entity.native_value == "192.0.2.12"

    clients_by_mac.clear()
    arp_entries.clear()

    assert not ip_entity.available
    assert ip_entity.native_value is None


def test_restored_wifi_client_becomes_available() -> None:
    """Test that a restored client becomes available when it reconnects."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_wifi_client_entities,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    mac = "aa:bb:cc:dd:ee:ff"
    clients_by_mac: dict[str, dict[str, str]] = {}
    coordinator.get_wifi_client.side_effect = clients_by_mac.get

    entities = create_wifi_client_entities(
        coordinator,
        {"mac": mac},
        "FGT123",
        "TestGate",
        {
            "mac": False,
            "hostname": False,
            "ssid": False,
            "vlan_id": False,
            "wtp_name": False,
        },
    )

    assert not entities[0].available

    clients_by_mac[mac] = {"mac": mac}

    assert entities[0].available


def test_last_known_client_identity_survives_disconnect() -> None:
    """Test retaining client identity after the client disconnects."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_wifi_client_entities,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    mac = "aa:bb:cc:dd:ee:ff"
    clients_by_mac = {mac: {"mac": mac, "hostname": "TestPhone"}}
    coordinator.get_wifi_client.side_effect = clients_by_mac.get

    entities = create_wifi_client_entities(
        coordinator,
        {"mac": mac, "hostname": "TestPhone"},
        "FGT123",
        "TestGate",
        {
            "mac": False,
            "hostname": False,
            "ssid": False,
            "vlan_id": False,
            "wtp_name": False,
        },
    )
    last_known_mac = next(
        entity for entity in entities if entity.name == "Last Known MAC"
    )
    last_known_hostname = next(
        entity for entity in entities if entity.name == "Last Known Hostname"
    )

    assert last_known_mac.native_value == mac
    assert last_known_hostname.native_value == "TestPhone"

    clients_by_mac.clear()

    assert last_known_mac.available
    assert last_known_mac.native_value == mac
    assert last_known_hostname.available
    assert last_known_hostname.native_value == "TestPhone"


def test_last_known_client_identity_respects_masking() -> None:
    """Test masking retained client identity values."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_wifi_client_entities,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_wifi_client.side_effect = {
        "aa:bb:cc:dd:ee:ff": {
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "TestPhone",
        }
    }.get

    entities = create_wifi_client_entities(
        coordinator,
        {"mac": "aa:bb:cc:dd:ee:ff", "hostname": "TestPhone"},
        "FGT123",
        "TestGate",
        {
            "mac": True,
            "hostname": True,
            "ssid": False,
            "vlan_id": False,
            "wtp_name": False,
        },
    )
    last_known_mac = next(
        entity for entity in entities if entity.name == "Last Known MAC"
    )
    last_known_hostname = next(
        entity for entity in entities if entity.name == "Last Known Hostname"
    )

    assert last_known_mac.native_value == "aa:bb:cc:**:**:**"
    assert last_known_hostname.native_value == "Test*****"


def test_wifi_client_skips_unchanged_coordinator_writes() -> None:
    """Test that unchanged client values do not rewrite entity state."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateWiFiClientMetric,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    client = {"mac": mac, "signal": -55}
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_wifi_client.return_value = client
    entity = FortiGateWiFiClientMetric(
        coordinator,
        client,
        "FGT123",
        "signal",
        "Signal",
        "mdi:signal",
    )
    entity.async_write_ha_state = Mock()
    entity._last_coordinator_state = entity._coordinator_state()  # noqa: SLF001

    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()

    client["signal"] = -48
    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once_with()


def test_wifi_client_mac_exposes_dashboard_entry_type() -> None:
    """Test that the client dashboard can exclude non-client MAC entities."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateWiFiClientMAC,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    match_id = sha256(f"fortios_kd\0FGT123\0{mac}".encode()).hexdigest()
    coordinator = Mock()
    coordinator.last_update_success = True
    entity = FortiGateWiFiClientMAC(
        coordinator,
        {"mac": mac},
        "FGT123",
        "TestGate",
        False,
    )

    assert entity.extra_state_attributes == {
        "fortios_kd_entry_type": "wifi_client",
        "fortios_kd_match_id": match_id,
    }


def test_ap_metric_skips_unchanged_coordinator_writes() -> None:
    """Test that unchanged AP metrics do not rewrite entity state."""
    from custom_components.fortios_kd.sensor import FortiGateAPMetric  # noqa: PLC0415

    ap = {"serial": "FAP123", "cpu_usage": 12}
    coordinator = Mock()
    coordinator.data = {"results": [ap]}
    coordinator.last_update_success = True
    entity = FortiGateAPMetric(
        coordinator,
        ap,
        "cpu_usage",
        "CPU Usage",
        "mdi:cpu-64-bit",
    )
    entity.async_write_ha_state = Mock()
    entity._last_coordinator_state = entity._coordinator_state()  # noqa: SLF001

    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()

    ap["cpu_usage"] = 18
    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once_with()


def test_arp_metric_skips_unchanged_coordinator_writes() -> None:
    """Test that unchanged ARP fields do not rewrite entity state."""
    from custom_components.fortios_kd.sensor import FortiGateARPMetric  # noqa: PLC0415

    entry = {"mac": "aa:bb:cc:dd:ee:ff", "interface": "lan"}
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_arp_entries.return_value = [entry]
    entity = FortiGateARPMetric(
        coordinator,
        entry["mac"],
        "FGT123",
        "TestGate",
        "interfaces",
        "ARP Interfaces",
        "mdi:lan",
        mask_mac=False,
        mask_hostname=False,
    )
    entity.async_write_ha_state = Mock()
    entity._last_coordinator_state = entity._coordinator_state()  # noqa: SLF001

    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()

    entry["interface"] = "guest"
    entity._handle_coordinator_update()  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once_with()


async def test_last_known_hostname_restores_after_restart() -> None:
    """Test restoring a retained hostname after Home Assistant restarts."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateWiFiClientLastKnownHostname,
    )

    coordinator = Mock()
    coordinator.get_wifi_client.return_value = None
    coordinator.async_add_listener.return_value = Mock()
    entity = FortiGateWiFiClientLastKnownHostname(
        coordinator,
        {"mac": "aa:bb:cc:dd:ee:ff"},
        "FGT123",
        False,
    )
    entity.async_get_last_state = AsyncMock(
        return_value=State("sensor.test_last_known_hostname", "TestPhone")
    )

    await entity.async_added_to_hass()

    assert entity.available
    assert entity.native_value == "TestPhone"


def test_radio_entities_expose_graph_dashboard_metadata() -> None:
    """Test stable metadata used to discover and filter radio graphs."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateAPRadioMetric,
        FortiGateAPRadioSSIDs,
    )

    coordinator = Mock()
    coordinator.radio_type_bands = {
        "future-5g-radio": "5 GHz",
    }
    coordinator.get_radio_channel_metadata.return_value = {
        "fortios_kd_supported_channel_widths": ["20MHz", "40MHz"],
        "fortios_kd_dfs_channel": True,
    }
    coordinator.data = {
        "results": [
            {
                "serial": "FAP123",
                "fortios_kd_ap_model": "FAP-221E",
                "fortios_kd_platform_type": "221E",
                "radio": [
                    {
                        "radio_id": 2,
                        "radio_type": "future-5g-radio",
                        "oper_chan": 52,
                        "ssid": {"vap-main": "Test Wifi"},
                        "tx_bits_per_second": 1234,
                    }
                ],
            }
        ]
    }
    ap = coordinator.data["results"][0]
    radio = ap["radio"][0]

    metric = FortiGateAPRadioMetric(
        coordinator,
        ap,
        radio,
        "tx_bits_per_second",
        "TX Rate",
        "mdi:upload-network",
    )
    channel = FortiGateAPRadioMetric(
        coordinator,
        ap,
        radio,
        "oper_chan",
        "Channel",
        "mdi:radio-tower",
    )
    ssids = FortiGateAPRadioSSIDs(
        ap,
        radio,
        False,
        coordinator.radio_type_bands,
    )

    assert metric.extra_state_attributes == {
        "fortios_kd_metric": "tx_bits_per_second",
        "fortios_kd_scope": "radio",
        "fortios_kd_radio_id": 2,
        "fortios_kd_band": "5 GHz",
    }
    assert channel.extra_state_attributes == {
        "fortios_kd_metric": "oper_chan",
        "fortios_kd_scope": "radio",
        "fortios_kd_radio_id": 2,
        "fortios_kd_band": "5 GHz",
        "fortios_kd_platform_type": "221E",
        "fortios_kd_ap_model": "FAP-221E",
        "fortios_kd_supported_channel_widths": ["20MHz", "40MHz"],
        "fortios_kd_dfs_channel": True,
    }
    coordinator.get_radio_channel_metadata.assert_called_once_with(
        "221E",
        "future-5g-radio",
        52,
    )
    assert ssids.extra_state_attributes == {
        "count": 1,
        "ssids": ["Test Wifi"],
        "fortios_kd_radio_id": 2,
        "fortios_kd_band": "5 GHz",
    }


def test_ap_entities_expose_graph_dashboard_metadata() -> None:
    """Test stable metadata used to discover AP-level graphs."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateAPClients,
        FortiGateAPMetric,
    )

    coordinator = Mock()
    ap = {"serial": "FAP123", "clients": 3, "cpu_usage": 12}
    coordinator.data = {"results": [ap]}

    clients = FortiGateAPClients(coordinator, ap)
    cpu = FortiGateAPMetric(
        coordinator,
        ap,
        "cpu_usage",
        "CPU Usage",
        "mdi:cpu-64-bit",
    )

    assert clients.extra_state_attributes == {
        "fortios_kd_metric": "clients",
        "fortios_kd_scope": "ap",
    }
    assert cpu.extra_state_attributes == {
        "fortios_kd_metric": "cpu_usage",
        "fortios_kd_scope": "ap",
    }


def test_fortios_6_2_5ghz_radio_type() -> None:
    """Test FortiOS 6.2 802.11ac radios are classified as 5 GHz."""
    from custom_components.fortios_kd.const import RADIO_TYPE_BANDS  # noqa: PLC0415

    assert RADIO_TYPE_BANDS["802.11ac"] == "5 GHz"
