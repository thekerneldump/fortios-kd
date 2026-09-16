"""Select entities for Wifi client dashboard filters."""

from typing import override

from homeassistant.components.select import SelectEntity
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
    """Set up the shared Wifi client filter selects."""
    manager: FortiOSKDFilterManager = hass.data[DOMAIN][DATA_FILTER_MANAGER]
    if not manager.claim_owner(entry.entry_id):
        return

    async_add_entities(
        [
            FortiOSKDFilterSelect(manager, "fortigate"),
            FortiOSKDFilterSelect(manager, "access_point"),
            FortiOSKDFilterSelect(manager, "ssid"),
            FortiOSKDFilterSelect(manager, "area"),
            FortiOSKDFilterSelect(manager, "label"),
        ]
    )


class FortiOSKDFilterSelect(SelectEntity):
    """Represent one shared Wifi client dashboard filter."""

    _attr_should_poll = False

    def __init__(
        self,
        manager: FortiOSKDFilterManager,
        filter_type: str,
    ) -> None:
        """Initialize a Wifi client filter select."""
        self._manager = manager
        self._filter_type = filter_type
        self._attr_unique_id = f"wifi_client_{filter_type}_filter"
        self._attr_name = {
            "fortigate": "Wifi Client FortiGate Filter",
            "access_point": "Wifi Client AP Filter",
            "ssid": "Wifi Client SSID Filter",
            "area": "Wifi Client Area Filter",
            "label": "Wifi Client Label Filter",
        }[filter_type]
        self._attr_icon = {
            "fortigate": "mdi:shield-router",
            "access_point": "mdi:access-point-network",
            "ssid": "mdi:wifi",
            "area": "mdi:floor-plan",
            "label": "mdi:label",
        }[filter_type]

    @property
    @override
    def options(self) -> list[str]:
        """Return the available filter options."""
        if self._filter_type == "fortigate":
            return self._manager.fortigate_options
        if self._filter_type == "access_point":
            return self._manager.access_point_options
        if self._filter_type == "ssid":
            return self._manager.ssid_options
        if self._filter_type == "area":
            return self._manager.area_options
        return self._manager.label_options

    @property
    @override
    def current_option(self) -> str:
        """Return the selected filter option."""
        if self._filter_type == "fortigate":
            return self._manager.selected_fortigate
        if self._filter_type == "access_point":
            return self._manager.selected_access_point
        if self._filter_type == "ssid":
            return self._manager.selected_ssid
        if self._filter_type == "area":
            return self._manager.selected_area
        return self._manager.selected_label

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a filter option."""
        if self._filter_type == "fortigate":
            self._manager.select_fortigate(option)
        elif self._filter_type == "access_point":
            self._manager.select_access_point(option)
        elif self._filter_type == "ssid":
            self._manager.select_ssid(option)
        elif self._filter_type == "area":
            self._manager.select_area(option)
        else:
            self._manager.select_label(option)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to shared filter changes."""
        self.async_on_remove(self._manager.add_listener(self.async_write_ha_state))
