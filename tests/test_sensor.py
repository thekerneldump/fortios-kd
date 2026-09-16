"""Tests for FortiOS KD sensors."""

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
    coordinator.data = {
        "results": [
            {
                "serial": "FAP123",
                "radio": [
                    {
                        "radio_id": 2,
                        "radio_type": "802.11ac-only",
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
    ssids = FortiGateAPRadioSSIDs(ap, radio, False)

    assert metric.extra_state_attributes == {
        "fortios_kd_metric": "tx_bits_per_second",
        "fortios_kd_scope": "radio",
        "fortios_kd_radio_id": 2,
        "fortios_kd_band": "5 GHz",
    }
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
    from custom_components.fortios_kd.sensor import RADIO_TYPE_BANDS  # noqa: PLC0415

    assert RADIO_TYPE_BANDS["802.11ac"] == "5 GHz"
