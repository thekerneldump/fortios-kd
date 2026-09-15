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
    coordinator.data = {"wifi_clients": {"results": []}}
    mac = "aa:bb:cc:dd:ee:ff"

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

    coordinator.data["wifi_clients"]["results"] = [{"mac": mac}]

    assert entities[0].available


def test_last_known_client_identity_survives_disconnect() -> None:
    """Test retaining client identity after the client disconnects."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        create_wifi_client_entities,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    mac = "aa:bb:cc:dd:ee:ff"
    coordinator.data = {
        "wifi_clients": {"results": [{"mac": mac, "hostname": "TestPhone"}]}
    }

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

    coordinator.data["wifi_clients"]["results"] = []

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
    coordinator.data = {
        "wifi_clients": {
            "results": [
                {"mac": "aa:bb:cc:dd:ee:ff", "hostname": "TestPhone"},
            ]
        }
    }

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


async def test_last_known_hostname_restores_after_restart() -> None:
    """Test restoring a retained hostname after Home Assistant restarts."""
    from custom_components.fortios_kd.sensor import (  # noqa: PLC0415
        FortiGateWiFiClientLastKnownHostname,
    )

    coordinator = Mock()
    coordinator.data = {"wifi_clients": {"results": []}}
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
