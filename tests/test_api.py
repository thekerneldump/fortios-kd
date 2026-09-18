"""Tests for the FortiOS-KD API."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration
from tests.common import MockConfigEntry  # noqa: TID251
from tests.test_util.aiohttp import AiohttpClientMocker  # noqa: TID251

DOMAIN = "fortios_kd"
BASE_URL = "https://fgt.example.local:8443/api/v2"


async def test_monitor_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the system and wifi Monitor API modules."""
    status = {"version": "v6.4.16", "build": 2098}
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

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fgt.example.local",
            CONF_PORT: 8443,
            CONF_API_KEY: "test-api-key",
            CONF_VERIFY_SSL: False,
            "sync_arp_table": True,
            "match_arp_wifi_clients": True,
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
