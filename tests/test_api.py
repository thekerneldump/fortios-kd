"""Tests for the FortiOS-KD API."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration
from tests.common import MockConfigEntry  # noqa: TID251
from tests.test_util.aiohttp import AiohttpClientMocker  # noqa: TID251

DOMAIN = "fortios_kd"
BASE_URL = "https://fgt.example.local:8443/api/v2"


def test_vdom_response_shape_normalization() -> None:
    """Test direct and enveloped FortiOS VDOM list responses."""
    from custom_components.fortios_kd.coordinator import _vdom_results  # noqa: PLC0415

    expected = [{"name": "root"}, {"name": "lab"}]

    assert _vdom_results(expected) == expected
    assert (
        _vdom_results(
            [
                {"vdom": "root", "results": [{"name": "root"}]},
                {"vdom": "lab", "results": [{"name": "root"}]},
            ]
        )
        == expected
    )
    assert _vdom_results({"results": expected}) == expected


def test_vdom_resource_response_shape_normalization() -> None:
    """Test single- and multi-VDOM resource response normalization."""
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        _vdom_resource_results,
    )

    root_resources = {
        "cpu": 12,
        "memory": 51,
        "session": {"current_usage": 1454, "usage_percent": 3},
    }
    lab_resources = {
        "cpu": 7,
        "memory": 42,
        "session": {"current_usage": 208, "usage_percent": 1},
    }

    assert _vdom_resource_results(
        [
            {"vdom": "root", "results": root_resources},
            {"vdom": "lab", "results": lab_resources},
        ]
    ) == {"root": root_resources, "lab": lab_resources}
    assert _vdom_resource_results({"vdom": "root", "results": root_resources}) == {
        "root": root_resources
    }
    assert _vdom_resource_results({"results": []}) is None


def test_dns_configuration_and_latency_normalization() -> None:
    """Test effective DNS sources and last-test age conversion."""
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        _configured_dns_servers,
        _dns_latency_results,
    )

    configured = _configured_dns_servers(
        {
            "results": {
                "primary": "203.0.113.53",
                "secondary": "203.0.113.54",
            }
        },
        [
            {
                "vdom": "lab",
                "results": {
                    "vdom-dns": "enable",
                    "primary": "192.0.2.53",
                    "secondary": "192.0.2.54",
                },
            },
            {"vdom": "root", "results": {"vdom-dns": "disable"}},
        ],
        {"lab", "root"},
        "root",
    )

    assert configured == {
        ("lab", "192.0.2.53"): {
            "vdom": "lab",
            "ip": "192.0.2.53",
            "configuration_source": "VDOM override",
            "roles": ["Primary"],
        },
        ("lab", "192.0.2.54"): {
            "vdom": "lab",
            "ip": "192.0.2.54",
            "configuration_source": "VDOM override",
            "roles": ["Secondary"],
        },
        ("root", "203.0.113.53"): {
            "vdom": "root",
            "ip": "203.0.113.53",
            "configuration_source": "Global",
            "roles": ["Primary"],
        },
        ("root", "203.0.113.54"): {
            "vdom": "root",
            "ip": "203.0.113.54",
            "configuration_source": "Global",
            "roles": ["Secondary"],
        },
    }

    observed_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    latency = _dns_latency_results(
        {
            "vdom": "root",
            "results": [
                {
                    "service": "dns_server",
                    "latency": 30,
                    "last_update": 2410,
                    "ip": "203.0.113.53",
                }
            ],
        },
        observed_at,
    )

    assert latency == {
        ("root", "203.0.113.53"): {
            "vdom": "root",
            "ip": "203.0.113.53",
            "service": "dns_server",
            "latency": 30,
            "last_tested": (observed_at - timedelta(milliseconds=2410)).replace(
                microsecond=0
            ),
            "latency_stale": False,
        }
    }

    stale_latency = _dns_latency_results(
        {
            "vdom": "root",
            "results": [
                {
                    "latency": 14940,
                    "last_update": 3_600_000,
                    "ip": "203.0.113.54",
                },
                {
                    "latency": 14940,
                    "last_update": 3_600_001,
                    "ip": "203.0.113.55",
                },
            ],
        },
        observed_at,
    )

    assert stale_latency is not None
    assert stale_latency[("root", "203.0.113.54")]["latency_stale"] is False
    assert stale_latency[("root", "203.0.113.55")]["latency_stale"] is True


async def test_monitor_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the system and wifi Monitor API modules."""
    status = {
        "version": "v6.4.16",
        "build": 2098,
        "serial": "FGT80E000000001",
        "results": {"hostname": "TestGate", "model": "FGT80E"},
    }
    access_point = {
        "serial": "FP221E000000001",
        "radio": [
            {
                "radio_id": 2,
                "radio_type": "802.11ac",
                "oper_chan": 52,
            }
        ],
    }
    access_points = {"results": [access_point]}
    wifi_client = {"mac": "AA:BB:CC:DD:EE:FF", "hostname": "TestPhone"}
    wifi_clients = {"results": [wifi_client]}
    arp_table = {
        "results": [
            {
                "ip": "192.0.2.50",
                "mac": "AA-BB-CC-DD-EE-FF",
                "interface": "internal",
                "age": 2,
            }
        ],
        "vdom": "root",
    }
    dhcp_leases = {
        "results": [
            {
                "ip": "192.0.2.50",
                "reserved": True,
                "mac": "AA-BB-CC-DD-EE-FF",
                "hostname": "TestPhone",
                "expire_time": 1790037166,
                "status": "leased",
                "interface": "internal",
                "type": "ipv4",
                "server_mkey": 21,
            }
        ]
    }
    vdom_results = [
        {"name": "lab"},
        {"name": "root"},
    ]
    vdoms = [
        {
            "version": "v6.4.16",
            "vdom": "lab",
            "results": [{"name": "root"}],
        },
        {
            "version": "v6.4.16",
            "vdom": "root",
            "results": [{"name": "root"}],
        },
    ]
    vdom_global_settings = {
        "results": {
            "vdom-mode": "multi-vdom",
            "management-vdom": "root",
        }
    }
    vdom_resources = [
        {
            "vdom": "lab",
            "results": {
                "cpu": 7,
                "memory": 42,
                "session": {"current_usage": 208, "usage_percent": 1},
            },
        },
        {
            "vdom": "root",
            "results": {
                "cpu": 12,
                "memory": 51,
                "session": {"current_usage": 1454, "usage_percent": 3},
            },
        },
    ]
    global_dns = {
        "results": {
            "primary": "203.0.113.53",
            "secondary": "203.0.113.54",
        },
        "vdom": "root",
    }
    vdom_dns = [
        {
            "vdom": "lab",
            "results": {
                "vdom-dns": "enable",
                "primary": "192.0.2.53",
                "secondary": "192.0.2.54",
            },
        },
        {
            "vdom": "root",
            "results": {"vdom-dns": "disable"},
        },
    ]
    dns_latency = [
        {
            "vdom": "lab",
            "results": [
                {
                    "service": "dns_server",
                    "latency": 8,
                    "ip": "192.0.2.53",
                }
            ],
        },
        {
            "vdom": "root",
            "results": [
                {
                    "service": "dns_server",
                    "latency": 30,
                    "ip": "203.0.113.53",
                },
                {
                    "service": "dns_server",
                    "latency": 12,
                    "ip": "198.51.100.53",
                },
            ],
        },
    ]
    wifi_meta = {
        "results": {
            "band_spectrum_map": {
                "802.11n": "24ghz",
                "future-5g-radio": "5ghz",
            }
        }
    }
    ap_names = {
        "results": [
            {
                "prefix": "FP221E",
                "model": "FAP-221E",
                "platform": "221E",
            }
        ]
    }
    ap_channels = {
        "results": {
            "channel_lists": {
                "802.11ac": {
                    "20MHz": [{"channels": {"36": "", "52": "dfs"}}],
                    "40MHz": [{"channels": {"36": "", "52": "dfs"}}],
                    "channel_widths": ["20MHz", "40MHz"],
                }
            }
        }
    }
    configured_vaps = {
        "results": [
            {
                "name": "TestVAP",
                "ssid": "ExampleWifi",
                "local-bridging": "disable",
            }
        ]
    }
    configured_wtp_profiles = {
        "results": [
            {
                "name": "TestProfile",
                "radio-1": {"vap-all": "manual", "vaps": ["TestVAP"]},
            }
        ]
    }

    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json=status,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/wireless-controller/vap?format=name|ssid|local-bridging",
        json=configured_vaps,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/wireless-controller/wtp-profile",
        json=configured_wtp_profiles,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/managed_ap",
        json=access_points,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/client",
        json=wifi_clients,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/meta",
        json=wifi_meta,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/ap-names",
        json=ap_names,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/ap_channels?platform_type=221E",
        json=ap_channels,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/network/arp",
        json=arp_table,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/dhcp",
        json=dhcp_leases,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/vdom?vdom=*",
        json=vdoms,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/global?format=management-vdom",
        json=vdom_global_settings,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/vdom-resource?vdom=*",
        json=vdom_resources,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/dns?vdom=root",
        json=global_dns,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/vdom-dns?vdom=*",
        json=vdom_dns,
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/network/dns/latency?vdom=*",
        json=dns_latency,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fgt.example.local",
            CONF_PORT: 8443,
            CONF_API_KEY: "test-api-key",
            CONF_VERIFY_SSL: False,
            "sync_arp_table": True,
            "match_arp_wifi_clients": True,
            "sync_dhcp_leases": True,
        },
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert any(
        url.startswith("/fortios_kd/fortios-kd-dashboard-loader.js?v=")
        for url in hass.data[DATA_EXTRA_MODULE_URL].urls
    )
    assert hass.data[DOMAIN][entry.entry_id]["status"] == status
    api = hass.data[DOMAIN][entry.entry_id]["client"]
    assert api.version is not None
    assert api._http._timeout.total == 60  # noqa: SLF001
    assert (
        api.version.major,
        api.version.minor,
        api.version.patch,
    ) == (6, 4, 16)
    assert api.supports_network_arp
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator.sync_arp_table
    assert coordinator.match_arp_wifi_clients
    assert coordinator.sync_dhcp_leases
    assert coordinator.data == {
        "results": [
            {
                **access_point,
                "fortios_kd_ap_model": "FAP-221E",
                "fortios_kd_platform_type": "221E",
                "radio": [
                    {
                        **access_point["radio"][0],
                        "rx_bits_per_second": None,
                        "tx_bits_per_second": None,
                        "rx_mac_errors_per_minute": None,
                        "tx_mac_errors_per_minute": None,
                    }
                ],
            }
        ],
        "wifi_clients": wifi_clients,
        "arp_table": {**arp_table, "supported": True},
        "dhcp_leases": {**dhcp_leases, "available": True},
        "vdoms": {
            "results": vdom_results,
            "available": True,
            "management_vdom": "root",
        },
        "vdom_resources": {
            "results": {item["vdom"]: item["results"] for item in vdom_resources},
            "available": True,
        },
        "dns_servers": {
            "results": [
                {
                    "vdom": "lab",
                    "ip": "192.0.2.53",
                    "configuration_available": True,
                    "latency_available": True,
                    "configured": True,
                    "configuration_source": "VDOM override",
                    "roles": ["Primary"],
                    "service": "dns_server",
                    "latency": 8,
                },
                {
                    "vdom": "lab",
                    "ip": "192.0.2.54",
                    "configuration_available": True,
                    "latency_available": False,
                    "configured": True,
                    "configuration_source": "VDOM override",
                    "roles": ["Secondary"],
                },
                {
                    "vdom": "root",
                    "ip": "203.0.113.53",
                    "configuration_available": True,
                    "latency_available": True,
                    "configured": True,
                    "configuration_source": "Global",
                    "roles": ["Primary"],
                    "service": "dns_server",
                    "latency": 30,
                },
                {
                    "vdom": "root",
                    "ip": "203.0.113.54",
                    "configuration_available": True,
                    "latency_available": False,
                    "configured": True,
                    "configuration_source": "Global",
                    "roles": ["Secondary"],
                },
            ],
            "available": True,
        },
        "configured_vaps": configured_vaps,
        "configured_wtp_profiles": configured_wtp_profiles,
    }
    assert coordinator.get_wifi_client("aa:bb:cc:dd:ee:ff") == wifi_client
    assert coordinator.get_wifi_client("AA:BB:CC:DD:EE:FF") == wifi_client
    assert coordinator.get_wifi_client("00:00:00:00:00:00") is None
    assert coordinator.get_arp_entries("aa:bb:cc:dd:ee:ff") == [
        {
            **arp_table["results"][0],
            "mac": "aa:bb:cc:dd:ee:ff",
            "vdom": "root",
        }
    ]
    assert coordinator.arp_macs == {"aa:bb:cc:dd:ee:ff"}
    assert coordinator.get_dhcp_entries("aa:bb:cc:dd:ee:ff") == [
        {**dhcp_leases["results"][0], "mac": "aa:bb:cc:dd:ee:ff"}
    ]
    assert coordinator.get_dhcp_entries_by_ip("192.0.2.50") == [
        {**dhcp_leases["results"][0], "mac": "aa:bb:cc:dd:ee:ff"}
    ]
    assert coordinator.dhcp_macs == {"aa:bb:cc:dd:ee:ff"}
    assert coordinator.dhcp_data_available
    assert coordinator.vdom_names == {"lab", "root"}
    assert coordinator.management_vdom == "root"
    assert coordinator.vdom_data_available
    assert coordinator.vdom_resource_data_available
    assert coordinator.get_vdom_resources("root") == vdom_resources[1]["results"]
    assert coordinator.dns_server_keys == {
        ("lab", "192.0.2.53"),
        ("lab", "192.0.2.54"),
        ("root", "203.0.113.53"),
        ("root", "203.0.113.54"),
    }
    assert (
        coordinator.get_dns_server("lab", "192.0.2.53")
        == (coordinator.data["dns_servers"]["results"][0])
    )
    assert coordinator.dns_data_available
    assert coordinator.wifi_meta == wifi_meta["results"]
    assert coordinator.radio_type_bands["802.11n"] == "2.4 GHz"
    assert coordinator.radio_type_bands["future-5g-radio"] == "5 GHz"
    assert coordinator.get_radio_channel_metadata("221E", "802.11ac", 52) == {
        "fortios_kd_supported_channel_widths": ["20MHz", "40MHz"],
        "fortios_kd_dfs_channel": True,
    }
    assert coordinator.get_radio_channel_metadata("221E", "802.11ac", 36) == {
        "fortios_kd_supported_channel_widths": ["20MHz", "40MHz"],
        "fortios_kd_dfs_channel": False,
    }


async def test_wifi_meta_failure_uses_fallback(hass: HomeAssistant) -> None:
    """Test an unavailable wifi metadata endpoint does not block updates."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.const import RADIO_TYPE_BANDS  # noqa: PLC0415
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.supports_network_arp = True
    client.monitor.wifi.get_meta = AsyncMock(side_effect=ClientConnectionError())
    client.monitor.wifi.get_ap_names = AsyncMock(side_effect=ClientConnectionError())
    client.monitor.wifi.get_managed_access_points = AsyncMock(
        return_value={"results": []}
    )
    client.monitor.wifi.get_clients = AsyncMock(return_value={"results": []})
    client.monitor.network.get_arp_table = AsyncMock()
    client.monitor.system.get_dhcp_leases = AsyncMock()
    client.monitor.system.get_vdom_resources = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.monitor.network.get_dns_latency = AsyncMock(
        return_value={"vdom": "root", "results": []}
    )
    client.configuration.system.get_vdoms = AsyncMock(
        return_value={"results": [{"name": "root"}]}
    )
    client.configuration.system.get_vdom_global_settings = AsyncMock(
        return_value={"results": {"management-vdom": "root"}}
    )
    client.configuration.system.get_global_dns = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.configuration.system.get_vdom_dns = AsyncMock()
    client.configuration.wifi.get_vaps = AsyncMock(return_value={"results": []})

    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        include_unassigned_ssids=True,
    )

    await coordinator._async_update_data()  # noqa: SLF001
    await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator.radio_type_bands == RADIO_TYPE_BANDS
    assert client.monitor.wifi.get_meta.await_count == 1
    assert client.monitor.wifi.get_ap_names.await_count == 1
    assert client.configuration.system.get_vdoms.await_count == 1
    assert client.configuration.system.get_vdom_global_settings.await_count == 1
    client.monitor.network.get_arp_table.assert_not_awaited()
    client.monitor.system.get_dhcp_leases.assert_not_awaited()


async def test_dhcp_failure_does_not_block_wifi_updates(hass: HomeAssistant) -> None:
    """Test an unavailable DHCP endpoint leaves its diagnostics unavailable."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.supports_network_arp = True
    client.monitor.wifi.get_meta = AsyncMock(return_value={"results": {}})
    client.monitor.wifi.get_ap_names = AsyncMock(return_value={"results": []})
    client.monitor.wifi.get_managed_access_points = AsyncMock(
        return_value={"results": []}
    )
    client.monitor.wifi.get_clients = AsyncMock(return_value={"results": []})
    client.monitor.system.get_dhcp_leases = AsyncMock(
        side_effect=ClientConnectionError()
    )
    client.monitor.system.get_vdom_resources = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.monitor.network.get_dns_latency = AsyncMock(
        return_value={"vdom": "root", "results": []}
    )
    client.monitor.network.get_arp_table = AsyncMock()
    client.configuration.system.get_vdoms = AsyncMock(
        return_value={"results": [{"name": "root"}]}
    )
    client.configuration.system.get_vdom_global_settings = AsyncMock(
        return_value={"results": {"management-vdom": "root"}}
    )
    client.configuration.system.get_global_dns = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.configuration.system.get_vdom_dns = AsyncMock()
    client.configuration.wifi.get_vaps = AsyncMock(return_value={"results": []})

    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        include_unassigned_ssids=True,
        sync_dhcp_leases=True,
    )

    data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["dhcp_leases"] == {"results": [], "available": False}
    assert not coordinator.dhcp_data_available
    assert coordinator.dhcp_macs == set()
    client.monitor.network.get_arp_table.assert_not_awaited()


async def test_vdom_inventory_retains_last_valid_response(
    hass: HomeAssistant,
) -> None:
    """Test transient VDOM failures retain the last valid inventory."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.supports_network_arp = True
    client.configuration.system.get_vdoms = AsyncMock(
        return_value={"results": [{"name": "root"}, {"name": "lab"}]}
    )
    client.configuration.system.get_vdom_global_settings = AsyncMock(
        return_value={"results": {"management-vdom": "root"}}
    )
    coordinator = FortiOSKDCoordinator(hass, client)

    first = await coordinator._async_get_vdom_inventory()  # noqa: SLF001

    assert first == {
        "results": [{"name": "root"}, {"name": "lab"}],
        "available": True,
        "management_vdom": "root",
    }

    coordinator._vdom_inventory_updated_at = None  # noqa: SLF001
    client.configuration.system.get_vdoms.side_effect = ClientConnectionError()
    client.configuration.system.get_vdom_global_settings.side_effect = (
        ClientConnectionError()
    )

    second = await coordinator._async_get_vdom_inventory()  # noqa: SLF001

    assert second == first
    assert coordinator.vdom_names == {"lab", "root"}
    assert coordinator.management_vdom == "root"
    assert coordinator.vdom_data_available


async def test_vdom_resource_failure_isolated_and_marks_data_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test VDOM resource failures retain values but mark sensors unavailable."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    resources = {
        "cpu": 12,
        "memory": 51,
        "session": {"current_usage": 1454, "usage_percent": 3},
    }
    client = Mock()
    client.monitor.system.get_vdom_resources = AsyncMock(
        return_value={"vdom": "root", "results": resources}
    )
    coordinator = FortiOSKDCoordinator(hass, client)

    first = await coordinator._async_get_vdom_resources()  # noqa: SLF001

    assert first == {"results": {"root": resources}, "available": True}
    assert coordinator.get_vdom_resources("root") == resources
    assert coordinator.vdom_resource_data_available

    client.monitor.system.get_vdom_resources.side_effect = ClientConnectionError()

    second = await coordinator._async_get_vdom_resources()  # noqa: SLF001

    assert second == {"results": {"root": resources}, "available": False}
    assert coordinator.get_vdom_resources("root") == resources
    assert not coordinator.vdom_resource_data_available


async def test_dns_failures_are_isolated_and_mark_data_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test unsupported DNS endpoints do not raise from coordinator polling."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.configuration.system.get_global_dns = AsyncMock(
        side_effect=ClientConnectionError()
    )
    client.configuration.system.get_vdom_dns = AsyncMock()
    client.monitor.network.get_dns_latency = AsyncMock(
        side_effect=ClientConnectionError()
    )
    coordinator = FortiOSKDCoordinator(hass, client)
    coordinator._vdoms = {  # noqa: SLF001
        "results": [{"name": "root"}],
        "available": True,
    }
    coordinator._management_vdom = "root"  # noqa: SLF001

    dns_servers = await coordinator._async_get_dns_servers()  # noqa: SLF001

    assert dns_servers == {"results": [], "available": False}
    assert not coordinator.dns_data_available
    assert coordinator.dns_server_keys == set()
    client.configuration.system.get_vdom_dns.assert_not_awaited()


async def test_fortios_62_uses_snmp_arp_fallback(hass: HomeAssistant) -> None:
    """Test FortiOS 6.2 ARP data is supplied by the configured SNMP client."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    arp_entry = {
        "ip": "192.0.2.45",
        "mac": "02:00:00:00:00:2d",
        "interface": "iot_vlan",
        "source": "snmp",
    }
    client = Mock()
    client.supports_network_arp = False
    client.monitor.wifi.get_meta = AsyncMock(return_value={"results": {}})
    client.monitor.wifi.get_ap_names = AsyncMock(return_value={"results": []})
    client.monitor.wifi.get_managed_access_points = AsyncMock(
        return_value={"results": []}
    )
    client.monitor.wifi.get_clients = AsyncMock(return_value={"results": []})
    client.monitor.system.get_dhcp_leases = AsyncMock()
    client.monitor.system.get_vdom_resources = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.monitor.network.get_dns_latency = AsyncMock(
        return_value={"vdom": "root", "results": []}
    )
    client.monitor.network.get_arp_table = AsyncMock()
    client.configuration.system.get_vdoms = AsyncMock(
        return_value={"results": [{"name": "root"}]}
    )
    client.configuration.system.get_vdom_global_settings = AsyncMock(
        return_value={"results": {"management-vdom": "root"}}
    )
    client.configuration.system.get_global_dns = AsyncMock(
        return_value={"vdom": "root", "results": {}}
    )
    client.configuration.system.get_vdom_dns = AsyncMock()
    client.configuration.wifi.get_vaps = AsyncMock(return_value={"results": []})
    snmp_client = Mock()
    snmp_client.async_get_arp_table = AsyncMock(
        return_value={
            "results": [arp_entry],
            "supported": True,
            "source": "snmp",
        }
    )
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        include_unassigned_ssids=True,
        sync_arp_table=True,
        snmp_arp_client=snmp_client,
    )

    data = await coordinator._async_update_data()  # noqa: SLF001

    assert data["arp_table"]["source"] == "snmp"
    assert coordinator.get_arp_entries("02:00:00:00:00:2d") == [arp_entry]
    snmp_client.async_get_arp_table.assert_awaited_once_with()
    client.monitor.network.get_arp_table.assert_not_awaited()


async def test_fortios_62_hostname_lookup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the FortiOS 6.2 hostname lookup."""
    status = {"version": "v6.2.17", "results": {}}

    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json=status,
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/global?format=hostname",
        json={"results": {"hostname": "FortiGate-62"}},
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/firmware",
        json={"results": {"current": {"platform-id": "FGT80E"}}},
    )

    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.api import FortiOSApi  # noqa: PLC0415

    api = FortiOSApi(
        async_get_clientsession(hass),
        "fgt.example.local",
        8443,
        "test-api-key",
        False,
        17,
    )

    assert api._http._timeout.total == 17  # noqa: SLF001

    result = await api.async_initialize()

    assert result["results"]["hostname"] == "FortiGate-62"
    assert result["results"]["model"] == "FGT80E"
    assert not api.supports_network_arp


async def test_api_refreshes_version_from_normal_responses(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test any API response can refresh the cached FortiOS version."""
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json={"version": "v6.2.17", "results": {}},
    )
    aioclient_mock.get(
        f"{BASE_URL}/cmdb/system/global?format=hostname",
        json={"results": {"hostname": "FortiGate-62"}},
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/firmware",
        json={"results": {"current": {"platform-id": "FGT80E"}}},
    )
    aioclient_mock.get(
        f"{BASE_URL}/monitor/wifi/managed_ap",
        json={"version": "v6.4.16", "results": []},
    )

    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.api import FortiOSApi  # noqa: PLC0415

    api = FortiOSApi(
        async_get_clientsession(hass),
        "fgt.example.local",
        8443,
        "test-api-key",
        False,
    )

    status = await api.async_initialize()

    assert not api.supports_network_arp
    assert api.version_text == "v6.2.17"

    await api.monitor.wifi.get_managed_access_points()

    assert api.supports_network_arp
    assert api.version_text == "v6.4.16"
    assert status["version"] == "v6.4.16"


async def test_arp_support_is_rechecked_after_version_change(
    hass: HomeAssistant,
) -> None:
    """Test ARP can switch to the REST API after a runtime version change."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.supports_network_arp = False
    client.monitor.network.get_arp_table = AsyncMock(
        return_value={"version": "v6.4.16", "results": []}
    )
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        sync_arp_table=True,
    )

    assert not coordinator._arp_supported  # noqa: SLF001

    client.supports_network_arp = True
    result = await coordinator._async_get_arp_table()  # noqa: SLF001

    assert result == {
        "version": "v6.4.16",
        "results": [],
        "supported": True,
    }
    client.monitor.network.get_arp_table.assert_awaited_once_with()


async def test_arp_transport_switches_after_runtime_downgrade(
    hass: HomeAssistant,
) -> None:
    """Test retained SNMP settings take over after a 6.4 to 6.2 downgrade."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.api.version import FortiOSVersion  # noqa: PLC0415
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )

    client = Mock()
    client.version = FortiOSVersion.parse("v6.4.16")
    client.version_text = "v6.4.16"
    client.supports_network_arp = True
    client.monitor.network.get_arp_table = AsyncMock(
        return_value={"results": [], "source": "api"}
    )
    snmp_client = Mock()
    snmp_client.async_get_arp_table = AsyncMock(
        return_value={"results": [], "source": "snmp"}
    )
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        sync_arp_table=True,
        snmp_arp_client=snmp_client,
    )

    result = await coordinator._async_get_arp_table()  # noqa: SLF001
    assert result["source"] == "api"
    snmp_client.async_get_arp_table.assert_not_awaited()

    client.version = FortiOSVersion.parse("v6.2.17")
    client.version_text = "v6.2.17"
    client.supports_network_arp = False

    result = await coordinator._async_get_arp_table()  # noqa: SLF001
    assert result["source"] == "snmp"
    snmp_client.async_get_arp_table.assert_awaited_once_with()


async def test_runtime_downgrade_creates_and_clears_snmp_repair(
    hass: HomeAssistant,
) -> None:
    """Test a missing 6.2 SNMP fallback raises a self-clearing Repair."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.api.version import FortiOSVersion  # noqa: PLC0415
    from custom_components.fortios_kd.coordinator import (  # noqa: PLC0415
        FortiOSKDCoordinator,
    )
    from custom_components.fortios_kd.repairs import snmp_arp_issue_id  # noqa: PLC0415

    entry = MockConfigEntry(domain=DOMAIN, title="Example FortiGate")
    entry.add_to_hass(hass)
    client = Mock()
    client.version = FortiOSVersion.parse("v6.2.17")
    client.version_text = "v6.2.17"
    client.supports_network_arp = False
    client.monitor.network.get_arp_table = AsyncMock(
        return_value={"results": [], "source": "api"}
    )
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        config_entry_id=entry.entry_id,
        sync_arp_table=True,
    )

    result = await coordinator._async_get_arp_table()  # noqa: SLF001

    assert result == {"results": [], "supported": False}
    issue_id = snmp_arp_issue_id(entry.entry_id)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.data == {"entry_id": entry.entry_id}
    assert "community" not in str(issue.data).casefold()

    client.version = FortiOSVersion.parse("v6.4.16")
    client.version_text = "v6.4.16"
    client.supports_network_arp = True
    await coordinator._async_get_arp_table()  # noqa: SLF001

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_version_parsing_and_ordering(hass: HomeAssistant) -> None:
    """Test FortiOS version parsing and numeric ordering."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.api.version import (  # noqa: PLC0415
        FortiOSVersion,
        version_family,
    )

    version = FortiOSVersion.parse("v6.4.16")

    assert version == FortiOSVersion(6, 4, 16)
    assert FortiOSVersion.parse("6.4.16") == version
    assert version < FortiOSVersion.parse("v7.0.2")
    assert version_family(version, "6")
    assert version_family(version, "6.4")
    assert version_family(version, "6.4.16")
    assert not version_family(version, "6.2")
    assert not version_family(version, "6.4.15")

    with pytest.raises(ValueError, match="Invalid FortiOS version"):
        FortiOSVersion.parse("not-a-version")
