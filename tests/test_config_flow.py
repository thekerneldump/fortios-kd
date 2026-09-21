"""Tests for the FortiOS-KD config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar, label_registry as lr
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
CONF_SYNC_ARP_TABLE = "sync_arp_table"
CONF_MATCH_ARP_WIFI_CLIENTS = "match_arp_wifi_clients"
CONF_SYNC_DHCP_LEASES = "sync_dhcp_leases"
CONF_SYNC_DEVICE_INVENTORY = "sync_device_inventory"
CONF_SYNC_INTERFACES = "sync_interfaces"
CONF_SNMP_COMMUNITY = "snmp_community"
CONF_SNMP_PORT = "snmp_port"
CONF_REQUEST_TIMEOUT = "request_timeout"
CONF_ORGANIZATION_MODE = "organization_mode"
CONF_HUB_AREA_ID = "hub_area_id"
CONF_NEW_HUB_AREA_NAME = "new_hub_area_name"
CONF_INHERIT_HUB_AREA = "inherit_hub_area"
CONF_MOVE_DEVICES_WITH_HUB = "move_devices_if_hub_moves"
CONF_CLIENTS_FOLLOW_AP_AREA = "clients_follow_ap_area"
CONF_CLIENTS_FOLLOW_AP_LABELS = "clients_follow_ap_labels"
CONF_DEVICES_FOLLOW_HUB_LABELS = "devices_follow_hub_labels"
CONF_HUB_LABEL_ID = "hub_label_id"
CONF_NEW_HUB_LABEL_NAME = "new_hub_label_name"
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
            CONF_SYNC_ARP_TABLE: False,
            CONF_MATCH_ARP_WIFI_CLIENTS: True,
            CONF_SYNC_DHCP_LEASES: False,
            CONF_SYNC_DEVICE_INVENTORY: False,
            CONF_SYNC_INTERFACES: False,
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
        CONF_SYNC_ARP_TABLE: False,
        CONF_MATCH_ARP_WIFI_CLIENTS: True,
        CONF_SYNC_DHCP_LEASES: False,
        CONF_SYNC_DEVICE_INVENTORY: False,
        CONF_SYNC_INTERFACES: False,
        CONF_ORGANIZATION_MODE: "none",
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


async def test_fortios_62_arp_sync_requests_snmp_settings(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test ARP synchronization on 6.2 requires validated SNMPv2c settings."""
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "FGT.Example.Local",
            CONF_API_KEY: "test-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_SYNC_ARP_TABLE: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "snmp_arp"

    with patch(
        "custom_components.fortios_kd.config_flow."
        "FortiOSKDSnmpArpClient.async_get_arp_table",
        return_value={"results": [], "supported": True, "source": "snmp"},
    ) as get_arp_table:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SNMP_COMMUNITY: "readonly-community",
                CONF_SNMP_PORT: 161,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SNMP_COMMUNITY] == "readonly-community"
    assert result["data"][CONF_SNMP_PORT] == 161
    get_arp_table.assert_awaited_once_with()


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


@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.homeassistant.config.abort.reconfigure_successful"],
)
async def test_reconfigure_on_newer_firmware_retains_snmp_fallback(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    ignore_missing_translations: str,
) -> None:
    """Test 6.2 SNMP settings remain dormant after an upgrade to 6.4."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="fgt.example.local",
        title="fgt.example.local:8443",
        data={
            CONF_HOST: "fgt.example.local",
            CONF_API_KEY: "test-api-key",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_REQUEST_TIMEOUT: 60,
            CONF_SYNC_ARP_TABLE: True,
            CONF_SNMP_COMMUNITY: "stored-readonly-community",
            CONF_SNMP_PORT: 161,
            CONF_ORGANIZATION_MODE: "none",
        },
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(
        f"{BASE_URL}/monitor/system/status",
        json={"version": "v6.4.16", "build": 2098},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    with patch.object(
        hass.config_entries,
        "async_reload",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "fgt.example.local",
                CONF_API_KEY: "test-api-key",
                CONF_PORT: 8443,
                CONF_VERIFY_SSL: True,
                CONF_REQUEST_TIMEOUT: 60,
                CONF_SYNC_ARP_TABLE: True,
                CONF_ORGANIZATION_MODE: "none",
            },
        )

    assert ignore_missing_translations
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_SNMP_COMMUNITY] == "stored-readonly-community"
    assert entry.data[CONF_SNMP_PORT] == 161


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
    assert result["step_id"] == "area_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "area_organization"
    assert result["errors"] == {CONF_HUB_AREA_ID: "area_required"}


async def test_area_organization_creates_typed_area(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a typed area is created and stored by ID."""
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
    assert result["step_id"] == "area_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NEW_HUB_AREA_NAME: "Example Place"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    area = ar.async_get(hass).async_get_area_by_name("Example Place")
    assert area is not None
    assert result["data"][CONF_HUB_AREA_ID] == area.id
    assert CONF_NEW_HUB_AREA_NAME not in result["data"]


async def test_label_organization_uses_existing_label(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that selecting a label stores its ID without changing its color."""
    label_registry = lr.async_get(hass)
    label = label_registry.async_create("Example Place", color="#ABCDEF")
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
            CONF_ORGANIZATION_MODE: "label",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "label_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HUB_LABEL_ID: label.label_id,
            CONF_HUB_LABEL_COLOR: [18, 52, 86],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HUB_LABEL_ID] == label.label_id
    assert label_registry.async_get_label(label.label_id).color == "#ABCDEF"


async def test_label_organization_creates_typed_label(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a typed label is created and stored by ID."""
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
            CONF_ORGANIZATION_MODE: "label",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "label_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NEW_HUB_LABEL_NAME: "Example Place",
            CONF_HUB_LABEL_COLOR: [18, 52, 86],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    label = lr.async_get(hass).async_get_label_by_name("Example Place")
    assert label is not None
    assert label.color == "#123456"
    assert result["data"][CONF_HUB_LABEL_ID] == label.label_id
    assert CONF_NEW_HUB_LABEL_NAME not in result["data"]


async def test_both_organization_uses_area_and_label(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test configuring both area and label organization."""
    area = ar.async_get(hass).async_create("Example Place")
    label = lr.async_get(hass).async_create("Example Label", color="#00CC88")
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
            CONF_ORGANIZATION_MODE: "both",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "area_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HUB_AREA_ID: area.id,
            CONF_INHERIT_HUB_AREA: True,
            CONF_MOVE_DEVICES_WITH_HUB: True,
            CONF_CLIENTS_FOLLOW_AP_AREA: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "label_organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HUB_LABEL_ID: label.label_id,
            CONF_CLIENTS_FOLLOW_AP_LABELS: True,
            CONF_DEVICES_FOLLOW_HUB_LABELS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ORGANIZATION_MODE] == "both"
    assert result["data"][CONF_HUB_AREA_ID] == area.id
    assert result["data"][CONF_HUB_LABEL_ID] == label.label_id
    assert result["data"][CONF_CLIENTS_FOLLOW_AP_AREA] is True
    assert result["data"][CONF_CLIENTS_FOLLOW_AP_LABELS] is True
    assert result["data"][CONF_DEVICES_FOLLOW_HUB_LABELS] is True
