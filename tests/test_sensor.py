"""Tests for FortiOS KD sensors."""

from datetime import UTC, datetime
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


def test_registered_dhcp_macs() -> None:
    """Test extracting previously registered DHCP devices."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        _registered_dhcp_macs,
    )

    entries = [
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_dhcp_aa:bb:cc:dd:ee:ff_ip_addresses",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT123_dhcp_aa:bb:cc:dd:ee:ff_hostnames",
        ),
        SimpleNamespace(
            domain="sensor",
            platform="fortios_kd",
            unique_id="FGT999_dhcp_11:22:33:44:55:66_ip_addresses",
        ),
    ]

    assert _registered_dhcp_macs(entries, "FGT123") == {"aa:bb:cc:dd:ee:ff"}


def test_firmware_version_uses_latest_coordinator_response() -> None:
    """Test the firmware sensor follows versions observed during polling."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateVersionSensor,
    )

    coordinator = Mock()
    coordinator.data = {"version": "v6.2.17"}
    coordinator.client.version_text = "v6.2.17"
    entry = Mock()
    entry.title = "Example FortiGate"
    status = {
        "serial": "FGT123",
        "version": "v6.2.17",
        "results": {"hostname": "Example FortiGate", "model": "FGT80E"},
    }
    entity = FortiGateVersionSensor(coordinator, entry, status, False)

    assert entity.native_value == "v6.2.17"

    coordinator.client.version_text = "v6.4.16"
    coordinator.data = {"version": "v6.4.16"}

    assert entity.native_value == "v6.4.16"


def test_vdom_name_sensor_is_attached_to_fortigate() -> None:
    """Test VDOM names are visible directly on their FortiGate device."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateVDOMNameSensor,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.vdom_data_available = True
    coordinator.vdom_names = {"root", "Tunnels"}
    coordinator.management_vdom = "root"

    entity = FortiGateVDOMNameSensor(coordinator, "FGT123", "root")

    assert entity.available
    assert entity.name == "VDOM root"
    assert entity.native_value == "root"
    assert entity.unique_id == "FGT123_vdom_root_name"
    assert entity.device_info["identifiers"] == {("fortios_kd", "FGT123")}
    assert entity.extra_state_attributes == {"management_vdom": True}

    coordinator.vdom_names = {"Tunnels"}

    assert not entity.available


def test_vdom_resource_sensors_live_on_vdom_device() -> None:
    """Test VDOM resource sensors expose numerical usage on the VDOM device."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_vdom_resource_entities,
    )

    resources = {
        "cpu": 12,
        "memory": 51,
        "session": {"current_usage": 1454, "usage_percent": 3},
    }
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.vdom_resource_data_available = True
    coordinator.get_vdom_resources.return_value = resources

    entities = create_vdom_resource_entities(
        coordinator,
        "FGT123",
        "TestGate",
        "root",
    )

    assert {entity.name: entity.native_value for entity in entities} == {
        "CPU usage": 12,
        "Memory usage": 51,
        "Sessions": 1454,
        "Session usage": 3,
    }
    assert {entity.name: entity.native_unit_of_measurement for entity in entities} == {
        "CPU usage": "%",
        "Memory usage": "%",
        "Sessions": "sessions",
        "Session usage": "%",
    }
    assert all(entity.available for entity in entities)
    assert entities[0].unique_id == "FGT123_vdom_root_cpu"
    assert entities[0].device_info["identifiers"] == {
        ("fortios_kd", "FGT123_vdom_root")
    }
    assert entities[0].device_info["via_device"] == ("fortios_kd", "FGT123")
    assert entities[0].extra_state_attributes == {
        "fortios_kd_metric": "cpu",
        "fortios_kd_scope": "vdom",
        "fortios_kd_vdom": "root",
    }

    coordinator.vdom_resource_data_available = False

    assert not entities[0].available


def test_dns_server_entities_are_linked_through_vdom_device() -> None:
    """Test DNS diagnostics and the HA 2025.12-compatible device relationship."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateVDOMDNSServersSensor,
        create_dns_server_entities,
    )

    last_tested = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    record = {
        "vdom": "root",
        "ip": "203.0.113.53",
        "configuration_source": "Global",
        "roles": ["Primary"],
        "configured": True,
        "configuration_available": True,
        "latency_available": True,
        "latency": 30,
        "last_tested": last_tested,
    }
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.dns_data_available = True
    coordinator.get_dns_server.return_value = record
    coordinator.get_vdom_dns_servers.return_value = [record]

    entities = create_dns_server_entities(
        coordinator,
        "FGT123",
        "TestGate",
        "root",
        "203.0.113.53",
    )
    values = {entity.name: entity.native_value for entity in entities}

    assert values == {
        "IP address": "203.0.113.53",
        "VDOM": "root",
        "Configuration source": "Global",
        "Configured role": "Primary",
        "Latency": 30,
        "Last tested": last_tested,
    }
    assert all(entity.available for entity in entities)
    assert entities[0].device_info["via_device"] == (
        "fortios_kd",
        "FGT123_vdom_root",
    )
    assert entities[0].device_info["model"] == "DNS Server"
    assert entities[0].extra_state_attributes == {
        "fortios_kd_entry_type": "dns_server",
        "fortios_kd_dns_field": "ip",
        "fortios_kd_vdom": "root",
        "fortios_kd_dns_ip": "203.0.113.53",
    }

    summary = FortiGateVDOMDNSServersSensor(
        coordinator,
        "FGT123",
        "TestGate",
        "root",
    )
    assert summary.native_value == "203.0.113.53"
    assert summary.device_info["identifiers"] == {("fortios_kd", "FGT123_vdom_root")}
    assert summary.extra_state_attributes["dns_server_count"] == 1

    record["latency_available"] = False
    latency_entity = next(entity for entity in entities if entity.name == "Latency")
    ip_entity = next(entity for entity in entities if entity.name == "IP address")

    assert latency_entity.extra_state_attributes == {
        "fortios_kd_entry_type": "dns_server",
        "fortios_kd_dns_field": "latency",
        "fortios_kd_vdom": "root",
        "fortios_kd_dns_ip": "203.0.113.53",
        "fortios_kd_metric": "dns_latency",
        "fortios_kd_scope": "dns_server",
    }

    assert not latency_entity.available
    assert ip_entity.available


def test_ap_network_entities_expose_dashboard_matching_metadata() -> None:
    """Test AP management IP and board MAC entities can enrich ARP rows."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateAPBoardMAC,
        FortiGateAPConnectingFrom,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    match_id = sha256(f"fortios_kd\0FGT123\0{mac}".encode()).hexdigest()
    ap = {
        "serial": "FAP123",
        "board_mac": mac,
        "connecting_from": "192.0.2.10",
    }

    board_mac = FortiGateAPBoardMAC(ap, "FGT123")
    connecting_from = FortiGateAPConnectingFrom(ap, "FGT123")

    assert board_mac.extra_state_attributes == {
        "fortios_kd_entry_type": "access_point",
        "fortios_kd_ap_field": "mac_address",
        "fortios_kd_match_id": match_id,
    }
    assert connecting_from.extra_state_attributes == {
        "fortios_kd_entry_type": "access_point",
        "fortios_kd_ap_field": "ip_address",
        "fortios_kd_match_id": match_id,
    }


def test_dhcp_entities_use_separate_device_and_aggregate_rows() -> None:
    """Test DHCP rows use a separate device and retain duplicate-MAC leases."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_dhcp_entities,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    match_id = sha256(f"fortios_kd\0FGT123\0{mac}".encode()).hexdigest()
    entries = [
        {
            "mac": mac,
            "ip": "192.0.2.10",
            "hostname": "TestPhone",
            "interface": "lan",
            "status": "leased",
            "reserved": False,
            "expire_time": 1790037166,
            "type": "ipv4",
            "server_mkey": 21,
        },
        {
            "mac": mac,
            "ip": "192.0.2.11",
            "hostname": "TestPhone-Backup",
            "interface": "guest",
            "status": "leased",
            "reserved": True,
            "expire_time": 1790083210,
            "type": "ipv4",
            "server_mkey": 22,
        },
    ]
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.dhcp_data_available = True
    coordinator.get_dhcp_entries.return_value = entries
    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "hostname": "TestPhone",
    }

    entities = create_dhcp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        False,
        False,
    )

    assert {entity.name: entity.native_value for entity in entities} == {
        "DHCP MAC Address": mac,
        "DHCP IP Addresses": "192.0.2.10, 192.0.2.11",
        "DHCP Hostnames": "TestPhone, TestPhone-Backup",
        "DHCP Interfaces": "guest, lan",
        "DHCP Statuses": "leased",
        "IP Assignment Type": "DHCP Reserved",
        "Latest Lease Expiration": datetime.fromtimestamp(1790083210, tz=UTC),
        "DHCP Address Types": "ipv4",
        "DHCP Server IDs": "21, 22",
        "WiFi Client Match": "TestPhone",
    }
    assert entities[0].device_info["identifiers"] == {
        ("fortios_kd", f"FGT123_dhcp_{mac}")
    }
    assert entities[0].device_info["name"] == f"DHCP Device {mac} (TestGate)"
    assert entities[0].extra_state_attributes == {
        "fortios_kd_entry_type": "dhcp_entry",
        "fortios_kd_dhcp_field": "mac_address",
        "fortios_kd_match_id": match_id,
    }


def test_wifi_client_ip_assignment_uses_exact_current_lease() -> None:
    """Test wifi assignment source matches both MAC and current IP address."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateWiFiClientIPAssignedBy,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.dhcp_data_available = True
    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "ip": "192.0.2.10",
    }
    coordinator.get_dhcp_entries.return_value = [
        {"mac": mac, "ip": "192.0.2.10", "reserved": True},
        {"mac": mac, "ip": "192.0.2.20", "reserved": False},
    ]
    entity = FortiGateWiFiClientIPAssignedBy(coordinator, {"mac": mac}, "FGT123")

    assert entity.available
    assert entity.native_value == "DHCP Reserved"

    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "ip": "192.0.2.20",
    }

    assert entity.native_value == "DHCP"

    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "ip": "192.0.2.30",
    }

    assert entity.native_value == "Static or Unknown"

    coordinator.dhcp_data_available = False

    assert not entity.available


def test_dhcp_entities_mask_mac_and_hostnames() -> None:
    """Test DHCP devices apply the existing screen-sharing privacy controls."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_dhcp_entities,
    )

    mac = "aa:bb:cc:dd:ee:ff"
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.dhcp_data_available = True
    coordinator.get_dhcp_entries.return_value = [
        {
            "mac": mac,
            "ip": "192.0.2.10",
            "hostname": "TestPhone",
            "reserved": False,
        }
    ]
    coordinator.get_wifi_client.return_value = {
        "mac": mac,
        "hostname": "OtherPhone",
    }

    entities = create_dhcp_entities(
        coordinator,
        mac,
        "FGT123",
        "TestGate",
        True,
        True,
    )
    values = {entity.name: entity.native_value for entity in entities}

    assert values["DHCP MAC Address"] == "aa:bb:cc:**:**:**"
    assert values["DHCP Hostnames"] == "Test*****"
    assert values["WiFi Client Match"] == "Othe******"


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
