"""Tests for the Wifi client filter manager."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock


def _mock_coordinator(access_point: str, ssid: str) -> Mock:
    """Create a coordinator containing one AP and one configured SSID."""
    coordinator = Mock()
    vap_name = f"vap-{ssid}"
    coordinator.data = {
        "results": [{"name": access_point}],
        "configured_vaps": {"results": [{"name": vap_name, "ssid": ssid}]},
        "configured_wtp_profiles": {
            "results": [
                {
                    "radio-1": {
                        "vap-all": "manual",
                        "vaps": [vap_name],
                    }
                }
            ]
        },
        "wifi_clients": {"results": []},
    }
    coordinator.async_add_listener.return_value = Mock()
    return coordinator


def _register_hub(
    manager: Any,
    entry_id: str,
    name: str,
    coordinator: Mock,
    *,
    mask_ap_names: bool = False,
    mask_ssids: bool = False,
    include_unassigned_ssids: bool = False,
) -> None:
    """Register a test hub with explicit masking settings."""
    register: Callable[..., None] = manager.register_hub
    register(
        entry_id,
        name,
        coordinator,
        mask_ap_names=mask_ap_names,
        mask_ssids=mask_ssids,
        include_unassigned_ssids=include_unassigned_ssids,
    )


def test_fortigate_options() -> None:
    """Test that FortiGate options are unique and sorted."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    manager = FortiOSKDFilterManager()

    _register_hub(
        manager,
        "entry-b",
        "ZuluGate",
        _mock_coordinator("YardAP", "GuestWifi"),
    )
    _register_hub(
        manager,
        "entry-a",
        "AlphaGate",
        _mock_coordinator("OfficeAP", "FamilyWifi"),
    )
    _register_hub(
        manager,
        "entry-c",
        "AlphaGate",
        _mock_coordinator("GarageAP", "IoTWifi"),
    )

    assert manager.access_point_options == [
        FILTER_ALL,
        "GarageAP",
        "OfficeAP",
        "YardAP",
    ]
    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "FamilyWifi",
        "GuestWifi",
        "IoTWifi",
    ]
    assert manager.fortigate_options == [
        FILTER_ALL,
        "AlphaGate",
        "ZuluGate",
    ]
    assert manager.selected_fortigate == FILTER_ALL

    manager.select_access_point("YardAP")
    manager.select_ssid("GuestWifi")

    assert manager.selected_access_point == "YardAP"
    assert manager.selected_ssid == "GuestWifi"

    manager.select_fortigate("AlphaGate")
    assert manager.selected_access_point == FILTER_ALL
    assert manager.selected_ssid == FILTER_ALL
    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "FamilyWifi",
        "IoTWifi",
    ]
    assert manager.selected_fortigate == "AlphaGate"
    assert manager.access_point_options == [
        FILTER_ALL,
        "GarageAP",
        "OfficeAP",
    ]

    manager.select_access_point("OfficeAP")
    manager.select_ssid(FILTER_UNAVAILABLE_CLIENTS)
    assert manager.selected_fortigate == FILTER_ALL
    assert manager.selected_access_point == FILTER_ALL
    assert manager.selected_ssid == FILTER_UNAVAILABLE_CLIENTS

    manager.select_access_point("YardAP")
    assert manager.selected_ssid == FILTER_ALL

    manager.select_fortigate("AlphaGate")
    manager.unregister_hub("entry-a")
    manager.unregister_hub("entry-c")

    assert manager.fortigate_options == [
        FILTER_ALL,
        "ZuluGate",
    ]
    assert manager.selected_fortigate == FILTER_ALL
    assert manager.selected_access_point == FILTER_ALL
    assert manager.selected_ssid == FILTER_ALL


def test_live_updates_masking_and_ownership() -> None:
    """Test coordinator notifications, masking, and select ownership."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    manager = FortiOSKDFilterManager()
    coordinator = _mock_coordinator("LivingRoom421E", "FamilyWifi 5GHz")
    listener = Mock()
    manager.add_listener(listener)

    _register_hub(
        manager,
        "entry-a",
        "FortiYard01",
        coordinator,
        mask_ap_names=True,
        mask_ssids=True,
    )

    assert manager.access_point_options == [FILTER_ALL, "Livin******21E"]
    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Fa******** 5GHz",
    ]
    assert listener.called

    manager.select_access_point("Livin******21E")
    manager.select_ssid("Fa******** 5GHz")
    coordinator.data = {
        "results": [{"name": "OfficeTop421E"}],
        "configured_vaps": {
            "results": [{"name": "vap-GuestWifi", "ssid": "GuestWifi"}]
        },
        "configured_wtp_profiles": {
            "results": [
                {
                    "radio-1": {
                        "vap-all": "manual",
                        "vaps": ["vap-GuestWifi"],
                    }
                }
            ]
        },
        "wifi_clients": {"results": []},
    }
    update_callback = coordinator.async_add_listener.call_args.args[0]
    update_callback()

    assert manager.selected_access_point == FILTER_ALL
    assert manager.selected_ssid == FILTER_ALL
    assert manager.claim_owner("entry-a")
    assert not manager.claim_owner("entry-b")

    _register_hub(
        manager,
        "entry-b",
        "SecondGate",
        _mock_coordinator("YardAP", "IoTWifi"),
    )
    manager.unregister_hub("entry-a")
    assert manager.release_owner("entry-a") == "entry-b"


def test_unassigned_ssid_option_and_profile_modes() -> None:
    """Test filtering unassigned SSIDs across FortiOS profile modes."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    coordinator = Mock()
    coordinator.data = {
        "results": [],
        "configured_vaps": {
            "results": [
                {
                    "name": "ManualFi",
                    "ssid": "Manual Wifi",
                    "local-bridging": "disable",
                },
                {
                    "name": "TunnelFi",
                    "ssid": "Tunnel Wifi",
                    "local-bridging": "disable",
                },
                {
                    "name": "BridgeFi",
                    "ssid": "Bridge Wifi",
                    "local-bridging": "enable",
                },
                {
                    "name": "UnusedFi",
                    "ssid": "Unused Wifi",
                    "local-bridging": "disable",
                },
            ]
        },
        "configured_wtp_profiles": {
            "results": [
                {
                    "radio-1": {
                        "vap-all": "manual",
                        "vaps": ["ManualFi"],
                    },
                    "radio-2": {"vap-all": "bridge", "vaps": []},
                }
            ]
        },
        "wifi_clients": {"results": [{"ssid": "Client-only Wifi"}]},
    }
    coordinator.async_add_listener.return_value = Mock()

    manager = FortiOSKDFilterManager()
    _register_hub(manager, "entry-a", "AlphaGate", coordinator)

    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Bridge Wifi",
        "Client-only Wifi",
        "Manual Wifi",
    ]

    manager_with_all = FortiOSKDFilterManager()
    _register_hub(
        manager_with_all,
        "entry-a",
        "AlphaGate",
        coordinator,
        include_unassigned_ssids=True,
    )

    assert manager_with_all.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Bridge Wifi",
        "Client-only Wifi",
        "Manual Wifi",
        "Tunnel Wifi",
        "Unused Wifi",
    ]


def test_fortios_62_automatic_tunnel_assignment() -> None:
    """Test the FortiOS 6.2 vap-all enable representation."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    coordinator = Mock()
    coordinator.data = {
        "results": [],
        "configured_vaps": {
            "results": [
                {
                    "name": "TunnelFi",
                    "ssid": "Tunnel Wifi",
                    "local-bridging": "disable",
                },
                {
                    "name": "BridgeFi",
                    "ssid": "Bridge Wifi",
                    "local-bridging": "enable",
                },
            ]
        },
        "configured_wtp_profiles": {
            "results": [{"radio-1": {"vap-all": "enable", "vaps": []}}]
        },
        "wifi_clients": {"results": []},
    }
    coordinator.async_add_listener.return_value = Mock()

    manager = FortiOSKDFilterManager()
    _register_hub(manager, "entry-a", "AlphaGate", coordinator)

    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Tunnel Wifi",
    ]


async def test_select_entities(hass: Any) -> None:
    """Test the three shared select entities and dependent options."""
    from custom_components.fortios_kd.const import (  # noqa: PLC0415
        DATA_FILTER_MANAGER,
        DOMAIN,
    )
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FortiOSKDFilterManager,
    )
    from custom_components.fortios_kd.select import async_setup_entry  # noqa: PLC0415

    manager = FortiOSKDFilterManager()
    _register_hub(
        manager,
        "entry-a",
        "AlphaGate",
        _mock_coordinator("OfficeAP", "FamilyWifi"),
    )
    _register_hub(
        manager,
        "entry-b",
        "BetaGate",
        _mock_coordinator("YardAP", "GuestWifi"),
    )
    hass.data[DOMAIN] = {DATA_FILTER_MANAGER: manager}
    entities: list[Any] = []
    entry = Mock(entry_id="entry-a")

    await async_setup_entry(hass, entry, entities.extend)

    assert len(entities) == 3
    fortigate, access_point, ssid = entities
    assert fortigate.options == ["All", "AlphaGate", "BetaGate"]

    await fortigate.async_select_option("AlphaGate")
    assert access_point.options == ["All", "OfficeAP"]
    assert ssid.options == ["All", "Unavailable Clients", "FamilyWifi"]

    duplicate_entities: list[Any] = []
    await async_setup_entry(
        hass,
        Mock(entry_id="entry-b"),
        duplicate_entities.extend,
    )
    assert duplicate_entities == []
