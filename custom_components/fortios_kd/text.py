"""Editable FortiOS KD naming preferences."""

from typing import override

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_PREFERRED_NAME, DATA_FILTER_MANAGER, DOMAIN
from .filter_manager import FortiOSKDFilterManager

PREFERRED_NAME_SCOPE_ATTRIBUTE = "fortios_kd_preferred_name_scope"
PREFERRED_NAME_SCOPE_FORTIGATE = "fortigate"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FortiGate preferred-name entity."""
    integration_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FortiGatePreferredNameText(
                entry,
                str(integration_data["status"]["serial"]),
                str(integration_data["fortigate_default_preferred_name"]),
                str(integration_data["fortigate_preferred_name"]),
                integration_data,
                hass.data[DOMAIN][DATA_FILTER_MANAGER],
            )
        ]
    )


class FortiGatePreferredNameText(TextEntity):
    """Store the name used for a FortiGate in FortiOS KD dashboards."""

    _attr_has_entity_name = True
    _attr_name = "Preferred name"
    _attr_icon = "mdi:rename-box"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_native_min = 0
    _attr_native_max = 64
    _attr_extra_state_attributes = {
        PREFERRED_NAME_SCOPE_ATTRIBUTE: PREFERRED_NAME_SCOPE_FORTIGATE,
    }

    def __init__(
        self,
        entry: ConfigEntry,
        fortigate_serial: str,
        default_name: str,
        preferred_name: str,
        integration_data: dict,
        filter_manager: FortiOSKDFilterManager,
    ) -> None:
        """Initialize the preferred-name entity."""
        self._entry = entry
        self._default_name = default_name
        self._value = preferred_name
        self._integration_data = integration_data
        self._filter_manager = filter_manager
        self._attr_unique_id = f"{fortigate_serial}_preferred_name"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, fortigate_serial)},
        )

    @property
    @override
    def native_value(self) -> str:
        """Return the current dashboard name."""
        return self._value

    @override
    async def async_set_value(self, value: str) -> None:
        """Persist a preferred dashboard name without renaming the device."""
        stripped_value = value.strip()
        preferred_name = stripped_value or self._default_name
        updated_data = dict(self._entry.data)
        if preferred_name == self._default_name:
            updated_data.pop(CONF_PREFERRED_NAME, None)
        else:
            updated_data[CONF_PREFERRED_NAME] = preferred_name

        self.hass.config_entries.async_update_entry(
            self._entry,
            data=updated_data,
        )
        self._value = preferred_name
        self._integration_data["fortigate_preferred_name"] = preferred_name
        self._filter_manager.update_hub_name(
            self._entry.entry_id,
            preferred_name,
        )
        self.async_write_ha_state()
