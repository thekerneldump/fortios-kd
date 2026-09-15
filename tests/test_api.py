"""Tests for the FortiOS-KD API."""

from unittest.mock import patch

import pytest

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
    access_points = {"results": []}
    wifi_clients = {"results": []}
    configured_vaps = {
        "results": [
            {
                "name": "FamilyFi",
                "ssid": "TellMyWifiLoveHer",
                "local-bridging": "disable",
            }
        ]
    }
    configured_wtp_profiles = {
        "results": [
            {
                "name": "TestProfile",
                "radio-1": {"vap-all": "manual", "vaps": ["FamilyFi"]},
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

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "fgt.example.local",
            CONF_PORT: 8443,
            CONF_API_KEY: "test-api-key",
            CONF_VERIFY_SSL: False,
        },
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id]["status"] == status
    api = hass.data[DOMAIN][entry.entry_id]["client"]
    assert api.version is not None
    assert (
        api.version.major,
        api.version.minor,
        api.version.patch,
    ) == (6, 4, 16)
    assert hass.data[DOMAIN][entry.entry_id]["coordinator"].data == {
        "results": [],
        "wifi_clients": wifi_clients,
        "configured_vaps": configured_vaps,
        "configured_wtp_profiles": configured_wtp_profiles,
    }


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
    )

    result = await api.async_initialize()

    assert result["results"]["hostname"] == "FortiGate-62"
    assert result["results"]["model"] == "FGT80E"


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
