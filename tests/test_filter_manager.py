"""Tests for the Wifi client filter manager."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    label_registry as lr,
)
from tests.common import MockConfigEntry  # noqa: TID251


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
    coordinator.sync_arp_table = True
    coordinator.sync_dhcp_leases = True
    coordinator.sync_device_inventory = True
    coordinator.arp_macs = {"aa:bb:cc:dd:ee:ff"}
    coordinator.get_arp_entries.return_value = [
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ip": "192.0.2.10",
            "interface": "lan",
        }
    ]
    coordinator.get_dhcp_entries.return_value = [
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ip": "192.0.2.10",
            "interface": "lan",
            "reserved": False,
        }
    ]
    coordinator.dhcp_macs = {"aa:bb:cc:dd:ee:ff"}
    coordinator.detected_device_macs = {"aa:bb:cc:dd:ee:ff"}
    coordinator.get_detected_device.return_value = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "os": {"name": "ExampleOS"},
        "hardware_vendor": "Example Vendor",
        "hardware_type": "Example Type",
        "hardware_family": "Example Family",
        "software_version": "1.2.3",
        "interface": "lan",
    }
    coordinator.vdom_names = {"root"}
    coordinator.interface_keys = {("root", "lan"), ("root", vap_name)}

    def get_interface(_vdom_name: str, interface_name: str) -> dict[str, Any]:
        if interface_name == vap_name:
            return {
                "name": vap_name,
                "vdom": "root",
                "link": True,
                "speed": 0,
                "duplex": 0,
            }
        return {
            "name": "lan",
            "vdom": "root",
            "link": True,
            "speed": 1000,
            "duplex": 1,
            "interface": "port1",
        }

    coordinator.get_interface.side_effect = get_interface
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


async def test_fortigate_options(hass: Any) -> None:
    """Test that FortiGate options are unique and sorted."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    manager = FortiOSKDFilterManager(hass)

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


async def test_preferred_name_updates_filters_and_active_selections(hass: Any) -> None:
    """Test a preferred name immediately replaces the registered hub name."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FortiOSKDFilterManager,
    )

    manager = FortiOSKDFilterManager(hass)
    coordinator = _mock_coordinator("OfficeAP", "OfficeWifi")
    _register_hub(manager, "entry-a", "FortiGate80E", coordinator)

    manager.select_fortigate("FortiGate80E")
    manager.select_arp_fortigate("FortiGate80E")
    manager.select_dhcp_fortigate("FortiGate80E")
    manager.select_device_fortigate("FortiGate80E")
    manager.select_vdom_fortigate("FortiGate80E")
    manager.select_interface_fortigate("FortiGate80E")

    manager.update_hub_name("entry-a", "OfficeGate80E")

    assert manager.fortigate_options == ["All", "OfficeGate80E"]
    assert manager.arp_fortigate_options == ["All", "OfficeGate80E"]
    assert manager.dhcp_fortigate_options == ["All", "OfficeGate80E"]
    assert manager.device_fortigate_options == ["All", "OfficeGate80E"]
    assert manager.vdom_fortigate_options == ["All", "OfficeGate80E"]
    assert manager.interface_fortigate_options == ["All", "OfficeGate80E"]
    assert manager.selected_fortigate == "OfficeGate80E"
    assert manager.selected_arp_fortigate == "OfficeGate80E"
    assert manager.selected_dhcp_fortigate == "OfficeGate80E"
    assert manager.selected_device_fortigate == "OfficeGate80E"
    assert manager.selected_vdom_fortigate == "OfficeGate80E"
    assert manager.selected_interface_fortigate == "OfficeGate80E"


async def test_live_updates_masking_and_ownership(hass: Any) -> None:
    """Test coordinator notifications, masking, and select ownership."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        FortiOSKDFilterManager,
    )

    manager = FortiOSKDFilterManager(hass)
    coordinator = _mock_coordinator("LivingRoom421E", "FamilyWifi 5GHz")
    listener = Mock()
    manager.add_listener(listener)

    _register_hub(
        manager,
        "entry-a",
        "TestAP01",
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


async def test_unassigned_ssid_option_and_profile_modes(hass: Any) -> None:
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
    coordinator.vdom_names = set()

    manager = FortiOSKDFilterManager(hass)
    _register_hub(manager, "entry-a", "AlphaGate", coordinator)

    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Bridge Wifi",
        "Client-only Wifi",
        "Manual Wifi",
    ]

    manager_with_all = FortiOSKDFilterManager(hass)
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


async def test_fortios_62_automatic_tunnel_assignment(hass: Any) -> None:
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
    coordinator.vdom_names = set()

    manager = FortiOSKDFilterManager(hass)
    _register_hub(manager, "entry-a", "AlphaGate", coordinator)

    assert manager.ssid_options == [
        FILTER_ALL,
        FILTER_UNAVAILABLE_CLIENTS,
        "Tunnel Wifi",
    ]


async def test_device_filters_are_scoped_by_fortigate(hass: Any) -> None:
    """Test selecting a FortiGate scopes and resets device-table filters."""
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FILTER_ALL,
        FortiOSKDFilterManager,
    )

    alpha = _mock_coordinator("OfficeAP", "OfficeWifi")
    alpha.get_detected_device.return_value = {
        "hardware_vendor": "Alpha Vendor",
        "hardware_type": "Alpha Type",
        "hardware_family": "Alpha Family",
        "os": {"name": "AlphaOS"},
        "software_version": "1.0",
        "interface": "alpha_lan",
    }
    beta = _mock_coordinator("YardAP", "YardWifi")
    beta.get_detected_device.return_value = {
        "hardware_vendor": "Beta Vendor",
        "hardware_type": "Beta Type",
        "hardware_family": "Beta Family",
        "os": {"name": "BetaOS"},
        "software_version": "2.0",
        "interface": "beta_lan",
    }

    manager = FortiOSKDFilterManager(hass)
    _register_hub(manager, "entry-a", "AlphaGate", alpha)
    _register_hub(manager, "entry-b", "BetaGate", beta)

    assert manager.device_hardware_vendor_options == [
        FILTER_ALL,
        "Alpha Vendor",
        "Beta Vendor",
    ]
    manager.select_device_fortigate("AlphaGate")
    assert manager.device_hardware_vendor_options == [FILTER_ALL, "Alpha Vendor"]
    assert manager.device_hardware_type_options == [FILTER_ALL, "Alpha Type"]
    assert manager.device_hardware_family_options == [FILTER_ALL, "Alpha Family"]
    assert manager.device_operating_system_options == [FILTER_ALL, "AlphaOS"]
    assert manager.device_software_version_options == [FILTER_ALL, "1.0"]
    assert manager.device_interface_options == [FILTER_ALL, "alpha_lan"]

    manager.select_device_hardware_vendor("Alpha Vendor")
    manager.select_device_hardware_type("Alpha Type")
    manager.select_device_hardware_family("Alpha Family")
    manager.select_device_last_seen("More than 1 day ago")
    manager.select_device_fortigate("BetaGate")
    assert manager.selected_device_hardware_vendor == FILTER_ALL
    assert manager.selected_device_hardware_type == FILTER_ALL
    assert manager.selected_device_hardware_family == FILTER_ALL
    assert manager.selected_device_last_seen == FILTER_ALL
    assert manager.device_hardware_vendor_options == [FILTER_ALL, "Beta Vendor"]


async def test_select_entities(hass: Any) -> None:
    """Test the shared select entities and their dependent options."""
    from custom_components.fortios_kd.const import (  # noqa: PLC0415
        DATA_FILTER_MANAGER,
        DOMAIN,
    )
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FortiOSKDFilterManager,
    )
    from custom_components.fortios_kd.select import async_setup_entry  # noqa: PLC0415

    entry_a = MockConfigEntry(domain=DOMAIN, entry_id="entry-a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain=DOMAIN, entry_id="entry-b")
    entry_b.add_to_hass(hass)
    manager = FortiOSKDFilterManager(hass)
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

    await async_setup_entry(hass, entry_a, entities.extend)

    area = ar.async_get(hass).async_create("Office")
    label = lr.async_get(hass).async_create("Trusted")
    registry = dr.async_get(hass)
    client = registry.async_get_or_create(
        config_entry_id="entry-a",
        identifiers={(DOMAIN, "FGT123_wifi_client_aa:bb:cc:dd:ee:ff")},
    )
    registry.async_update_device(
        client.id,
        area_id=area.id,
        labels={label.label_id},
    )

    assert len(entities) == 29
    (
        fortigate,
        access_point,
        ssid,
        area_filter,
        label_filter,
        wifi_graph_time_span,
        arp_fortigate,
        arp_interface,
        arp_lease_type,
        dhcp_fortigate,
        dhcp_interface,
        device_fortigate,
        device_hardware_vendor,
        device_hardware_type,
        device_hardware_family,
        device_operating_system,
        device_software_version,
        device_interface,
        device_last_seen,
        vdom_fortigate,
        vdom_filter,
        vdom_graph_layout,
        vdom_time_span,
        interface_fortigate,
        interface_link,
        interface_speed_duplex,
        interface_parent,
        interface_graph_layout,
        interface_time_span,
    ) = entities
    assert fortigate.options == ["All", "AlphaGate", "BetaGate"]

    await fortigate.async_select_option("AlphaGate")
    assert access_point.options == ["All", "OfficeAP"]
    assert ssid.options == ["All", "Unavailable Clients", "FamilyWifi"]
    assert area_filter.options == ["All", "Office"]
    assert label_filter.options == ["All", "Trusted"]

    await area_filter.async_select_option("Office")
    await label_filter.async_select_option("Trusted")
    assert manager.selected_area == "Office"
    assert manager.selected_label == "Trusted"

    assert wifi_graph_time_span.options == [
        "1 week",
        "1 day",
        "12 hours",
        "6 hours",
        "3 hours",
        "1 hour",
        "30 min",
    ]
    assert wifi_graph_time_span.current_option == "1 hour"
    await wifi_graph_time_span.async_select_option("6 hours")
    assert manager.selected_wifi_graph_time_span == "6 hours"

    assert arp_fortigate.options == ["All", "AlphaGate", "BetaGate"]
    await arp_fortigate.async_select_option("AlphaGate")
    assert arp_interface.options == ["All", "lan"]
    await arp_interface.async_select_option("lan")
    assert arp_lease_type.options == ["All", "Leased"]
    await arp_lease_type.async_select_option("Leased")
    assert manager.selected_arp_fortigate == "AlphaGate"
    assert manager.selected_arp_interface == "lan"
    assert manager.selected_arp_lease_type == "Leased"

    assert dhcp_fortigate.options == ["All", "AlphaGate", "BetaGate"]
    await dhcp_fortigate.async_select_option("AlphaGate")
    assert dhcp_interface.options == ["All", "lan"]
    await dhcp_interface.async_select_option("lan")
    assert manager.selected_dhcp_fortigate == "AlphaGate"
    assert manager.selected_dhcp_interface == "lan"

    assert device_fortigate.options == ["All", "AlphaGate", "BetaGate"]
    await device_fortigate.async_select_option("AlphaGate")
    assert manager.selected_device_fortigate == "AlphaGate"
    assert device_hardware_vendor.options == ["All", "Example Vendor"]
    assert device_hardware_type.options == ["All", "Example Type"]
    assert device_hardware_family.options == ["All", "Example Family"]
    assert device_operating_system.options == ["All", "ExampleOS"]
    assert device_software_version.options == ["All", "1.2.3"]
    assert device_interface.options == ["All", "lan"]
    assert device_last_seen.options == [
        "All",
        "Less than 1 hour ago",
        "Less than 1 day ago",
        "Less than 1 week ago",
        "Less than 1 month ago",
        "Less than 1 year ago",
        "More than 1 hour ago",
        "More than 1 day ago",
        "More than 1 week ago",
        "More than 1 month ago",
        "More than 1 year ago",
    ]
    await device_hardware_vendor.async_select_option("Example Vendor")
    await device_hardware_type.async_select_option("Example Type")
    await device_hardware_family.async_select_option("Example Family")
    await device_operating_system.async_select_option("ExampleOS")
    await device_software_version.async_select_option("1.2.3")
    await device_interface.async_select_option("lan")
    await device_last_seen.async_select_option("Less than 1 week ago")
    assert manager.selected_device_hardware_vendor == "Example Vendor"
    assert manager.selected_device_hardware_type == "Example Type"
    assert manager.selected_device_hardware_family == "Example Family"
    assert manager.selected_device_operating_system == "ExampleOS"
    assert manager.selected_device_software_version == "1.2.3"
    assert manager.selected_device_interface == "lan"
    assert manager.selected_device_last_seen == "Less than 1 week ago"
    await device_last_seen.async_select_option("More than 1 month ago")
    assert manager.selected_device_last_seen == "More than 1 month ago"

    assert vdom_fortigate.options == ["All", "AlphaGate", "BetaGate"]
    await vdom_fortigate.async_select_option("AlphaGate")
    assert vdom_filter.options == ["All", "root"]
    await vdom_filter.async_select_option("root")
    assert manager.selected_vdom_fortigate == "AlphaGate"
    assert manager.selected_vdom == "root"
    assert vdom_graph_layout.options == [
        "Combined by resource",
        "Separate by VDOM",
    ]
    assert vdom_graph_layout.current_option == "Combined by resource"
    await vdom_graph_layout.async_select_option("Separate by VDOM")
    assert manager.selected_vdom_graph_layout == "Separate by VDOM"
    assert vdom_time_span.options == [
        "1 week",
        "1 day",
        "12 hours",
        "6 hours",
        "3 hours",
        "1 hour",
        "30 min",
    ]
    assert vdom_time_span.current_option == "1 hour"
    await vdom_time_span.async_select_option("30 min")
    assert manager.selected_vdom_time_span == "30 min"

    assert interface_fortigate.options == ["All", "AlphaGate", "BetaGate"]
    await interface_fortigate.async_select_option("AlphaGate")
    assert manager.selected_interface_fortigate == "AlphaGate"
    assert interface_link.options == ["All", "Up"]
    assert interface_speed_duplex.options == [
        "All",
        "0 Mbps / Half",
        "1000 Mbps / Full",
    ]
    assert interface_parent.options == ["All", "port1"]
    await interface_link.async_select_option("Up")
    await interface_speed_duplex.async_select_option("1000 Mbps / Full")
    await interface_parent.async_select_option("port1")
    assert manager.selected_interface_link == "Up"
    assert manager.selected_interface_speed_duplex == "1000 Mbps / Full"
    assert manager.selected_interface_parent == "port1"
    assert interface_graph_layout.options == [
        "Combined by rate",
        "Separated by firewall",
    ]
    assert interface_graph_layout.current_option == "Combined by rate"
    await interface_graph_layout.async_select_option("Separated by firewall")
    assert manager.selected_interface_graph_layout == "Separated by firewall"
    assert interface_time_span.options == [
        "1 week",
        "1 day",
        "12 hours",
        "6 hours",
        "3 hours",
        "1 hour",
        "30 min",
    ]
    assert interface_time_span.current_option == "1 hour"
    await interface_time_span.async_select_option("3 hours")
    assert manager.selected_interface_time_span == "3 hours"

    duplicate_entities: list[Any] = []
    await async_setup_entry(
        hass,
        entry_b,
        duplicate_entities.extend,
    )
    assert duplicate_entities == []
