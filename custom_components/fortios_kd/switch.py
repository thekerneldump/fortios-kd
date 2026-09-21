"""Switch entities for shared FortiOS KD dashboard filters."""

from typing import override

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_FILTER_MANAGER, DOMAIN
from .filter_manager import FortiOSKDFilterManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the shared interface dashboard switches."""
    manager: FortiOSKDFilterManager = hass.data[DOMAIN][DATA_FILTER_MANAGER]
    if not manager.claim_owner(entry.entry_id):
        return

    async_add_entities(
        [
            FortiOSKDFilterSwitch(
                manager,
                "hide_interface_hardware_switch_members",
            ),
            FortiOSKDFilterSwitch(
                manager,
                "hide_interface_wifi_ssid_interfaces",
            ),
        ]
    )


class FortiOSKDFilterSwitch(SwitchEntity):
    """Represent one shared boolean dashboard filter."""

    _attr_should_poll = False

    def __init__(
        self,
        manager: FortiOSKDFilterManager,
        filter_type: str,
    ) -> None:
        """Initialize a dashboard filter switch."""
        self._manager = manager
        self._filter_type = filter_type
        self._attr_unique_id = f"interface_graphs_{filter_type}"
        self._attr_name = {
            "hide_interface_hardware_switch_members": (
                "Interface Graphs Hide Hardware Switch Members"
            ),
            "hide_interface_wifi_ssid_interfaces": (
                "Interface Graphs Hide WiFi SSID Interfaces"
            ),
        }[filter_type]
        self._attr_icon = {
            "hide_interface_hardware_switch_members": "mdi:lan-disconnect",
            "hide_interface_wifi_ssid_interfaces": "mdi:wifi-off",
        }[filter_type]

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the matching interfaces are hidden."""
        return getattr(self._manager, self._filter_type)

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        """Hide the matching interfaces."""
        getattr(self._manager, f"set_{self._filter_type}")(True)

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        """Show the matching interfaces."""
        getattr(self._manager, f"set_{self._filter_type}")(False)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to shared filter changes."""
        self.async_on_remove(self._manager.add_listener(self.async_write_ha_state))
