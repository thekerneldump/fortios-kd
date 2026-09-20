"""Tests for FortiOS-KD Repairs."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration
from tests.common import MockConfigEntry  # noqa: TID251

DOMAIN = "fortios_kd"
CONF_SNMP_COMMUNITY = "snmp_community"
CONF_SNMP_PORT = "snmp_port"


async def test_snmp_arp_repair_validates_and_saves_settings(
    hass: HomeAssistant,
) -> None:
    """Test the Repair safely validates, stores, and applies SNMP settings."""
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()

    from custom_components.fortios_kd.repairs import (  # noqa: PLC0415
        async_create_fix_flow,
        async_create_snmp_arp_issue,
        snmp_arp_issue_id,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example FortiGate",
        data={CONF_HOST: "fgt.example.local"},
    )
    entry.add_to_hass(hass)
    async_create_snmp_arp_issue(hass, entry.entry_id, "v6.2.17")
    issue_id = snmp_arp_issue_id(entry.entry_id)

    flow = await async_create_fix_flow(
        hass,
        issue_id,
        {"entry_id": entry.entry_id},
    )
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with (
        patch(
            "custom_components.fortios_kd.repairs."
            "FortiOSKDSnmpArpClient.async_get_arp_table",
            return_value={"results": [], "source": "snmp"},
        ) as get_arp_table,
        patch.object(
            hass.config_entries,
            "async_reload",
            new=AsyncMock(return_value=True),
        ) as reload_entry,
    ):
        result = await flow.async_step_init(
            {
                CONF_SNMP_COMMUNITY: "replacement-readonly-community",
                CONF_SNMP_PORT: 1161,
            }
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_SNMP_COMMUNITY] == "replacement-readonly-community"
    assert entry.data[CONF_SNMP_PORT] == 1161
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    get_arp_table.assert_awaited_once_with()
    reload_entry.assert_awaited_once_with(entry.entry_id)
