"""Tests for the FortiOS-KD config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from tests.common import MockConfigEntry  # noqa: TID251
from tests.test_util.aiohttp import AiohttpClientMocker  # noqa: TID251

DOMAIN = "fortios_kd"
BASE_URL = "https://fgt.example.local:8443/api/v2"
CONF_MASK_SERIAL_NUMBERS = "mask_serial_numbers"
CONF_MASK_SSIDS = "mask_ssids"
CONF_MASK_CLIENT_MACS = "mask_client_macs"
CONF_MASK_CLIENT_HOSTNAMES = "mask_client_hostnames"
CONF_MASK_VLAN_IDS = "mask_vlan_ids"
CONF_MASK_AP_NAMES = "mask_ap_names"
CONF_INCLUDE_UNASSIGNED_SSIDS = "include_unassigned_ssids"
CONF_REQUEST_TIMEOUT = "request_timeout"
CONF_ORGANIZATION_MODE = "organization_mode"
CONF_HUB_AREA_ID = "hub_area_id"
CONF_INHERIT_HUB_AREA = "inherit_hub_area"
CONF_MOVE_DEVICES_WITH_HUB = "move_devices_if_hub_moves"
CONF_CLIENTS_FOLLOW_AP_AREA = "clients_follow_ap_area"
CONF_HUB_LABEL_COLOR = "hub_label_color"


async def test_user_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test configuring a FortiGate manually."""
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json={"version": "v6.4.16", "build": 2098},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "FGT.Example.Local",
            CONF_API_KEY: "test-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_REQUEST_TIMEOUT: 60,
            CONF_INCLUDE_UNASSIGNED_SSIDS: False,
            CONF_MASK_SERIAL_NUMBERS: True,
            CONF_MASK_SSIDS: True,
            CONF_MASK_CLIENT_MACS: True,
            CONF_MASK_CLIENT_HOSTNAMES: True,
            CONF_MASK_VLAN_IDS: True,
            CONF_MASK_AP_NAMES: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "fgt.example.local:8443"
    assert result["data"] == {
        CONF_HOST: "fgt.example.local",
        CONF_API_KEY: "test-api-key",
        CONF_PORT: 8443,
        CONF_VERIFY_SSL: True,
        CONF_REQUEST_TIMEOUT: 60,
        CONF_INCLUDE_UNASSIGNED_SSIDS: False,
        CONF_ORGANIZATION_MODE: "none",
        CONF_INHERIT_HUB_AREA: False,
        CONF_MOVE_DEVICES_WITH_HUB: False,
        CONF_CLIENTS_FOLLOW_AP_AREA: False,
        CONF_HUB_LABEL_COLOR: [3, 169, 244],
        CONF_MASK_SERIAL_NUMBERS: True,
        CONF_MASK_SSIDS: True,
        CONF_MASK_CLIENT_MACS: True,
        CONF_MASK_CLIENT_HOSTNAMES: True,
        CONF_MASK_VLAN_IDS: True,
        CONF_MASK_AP_NAMES: True,
    }


async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an invalid API key shows a form error."""
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        status=401,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "FGT.Example.Local",
            CONF_API_KEY: "wrong-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that invalid reconfigure credentials stay on the form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="fgt.example.local",
        title="fgt.example.local:8443",
        data={
            CONF_HOST: "fgt.example.local",
            CONF_API_KEY: "old-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        status=401,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "FGT.Example.Local",
            CONF_API_KEY: "wrong-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_API_KEY] == "old-api-key"


async def test_area_organization_requires_area(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that area organization requires an area selection."""
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json={"version": "v6.4.16", "build": 2098},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "FGT.Example.Local",
            CONF_API_KEY: "test-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_ORGANIZATION_MODE: "area",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HUB_AREA_ID: "area_required"}
