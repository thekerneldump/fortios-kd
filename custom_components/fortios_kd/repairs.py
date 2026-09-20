"""Repair flows for FortiOS-KD."""

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir, selector

from .const import (
    CONF_SNMP_COMMUNITY,
    CONF_SNMP_PORT,
    DEFAULT_SNMP_PORT,
    DEFAULT_SNMP_TIMEOUT,
    DOMAIN,
)
from .snmp_arp import FortiOSKDSnmpArpClient, SnmpArpError

ISSUE_SNMP_ARP_REQUIRED = "snmp_arp_required"


def snmp_arp_issue_id(entry_id: str) -> str:
    """Return the per-entry SNMP ARP repair issue ID."""
    return f"{ISSUE_SNMP_ARP_REQUIRED}_{entry_id}"


@callback
def async_create_snmp_arp_issue(
    hass: HomeAssistant,
    entry_id: str,
    version: str | None,
) -> None:
    """Create a repair when FortiOS 6.2 ARP cannot use SNMP."""
    entry = hass.config_entries.async_get_entry(entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        snmp_arp_issue_id(entry_id),
        data={"entry_id": entry_id},
        is_fixable=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_SNMP_ARP_REQUIRED,
        translation_placeholders={
            "name": entry.title if entry is not None else "FortiGate",
            "version": version or "FortiOS 6.2",
        },
    )


@callback
def async_delete_snmp_arp_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the per-entry SNMP ARP repair issue if it exists."""
    ir.async_delete_issue(hass, DOMAIN, snmp_arp_issue_id(entry_id))


class SnmpArpRepairFlow(RepairsFlow):
    """Collect and validate SNMPv2c settings for FortiOS 6.2 ARP."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Validate and save replacement SNMPv2c settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            community = str(user_input.get(CONF_SNMP_COMMUNITY, "")).strip()
            port = int(user_input.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT))
            if not community:
                errors[CONF_SNMP_COMMUNITY] = "snmp_community_required"
            else:
                client = FortiOSKDSnmpArpClient(
                    self.hass,
                    self._entry.data[CONF_HOST],
                    community,
                    port,
                    DEFAULT_SNMP_TIMEOUT,
                )
                try:
                    await client.async_get_arp_table()
                except SnmpArpError, TimeoutError, ValueError:
                    errors["base"] = "snmp_cannot_connect"
                else:
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={
                            **self._entry.data,
                            CONF_SNMP_COMMUNITY: community,
                            CONF_SNMP_PORT: port,
                        },
                    )
                    async_delete_snmp_arp_issue(self.hass, self._entry.entry_id)
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                    return self.async_create_entry(data={})

        suggested_port = user_input.get(CONF_SNMP_PORT) if user_input else None
        if suggested_port is None:
            suggested_port = self._entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)
        schema = vol.Schema(
            {
                vol.Required(CONF_SNMP_COMMUNITY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    CONF_SNMP_PORT,
                    default=int(suggested_port),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": self._entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the requested repair flow."""
    if (
        issue_id.startswith(f"{ISSUE_SNMP_ARP_REQUIRED}_")
        and data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
    ):
        return SnmpArpRepairFlow(entry)
    return ConfirmRepairFlow()
