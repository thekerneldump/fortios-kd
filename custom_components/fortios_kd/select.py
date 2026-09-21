"""Select entities for FortiOS KD dashboard filters."""

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
            FortiOSKDFilterSelect(manager, "wifi_graph_time_span"),
            FortiOSKDFilterSelect(manager, "arp_fortigate"),
            FortiOSKDFilterSelect(manager, "arp_interface"),
            FortiOSKDFilterSelect(manager, "arp_lease_type"),
            FortiOSKDFilterSelect(manager, "dhcp_fortigate"),
            FortiOSKDFilterSelect(manager, "dhcp_interface"),
            FortiOSKDFilterSelect(manager, "vdom_fortigate"),
            FortiOSKDFilterSelect(manager, "vdom"),
            FortiOSKDFilterSelect(manager, "vdom_graph_layout"),
            FortiOSKDFilterSelect(manager, "vdom_time_span"),
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
            "wifi_graph_time_span": "Wifi Graphs Time Span",
            "arp_fortigate": "ARP Table FortiGate Filter",
            "arp_interface": "ARP Table Interface Filter",
            "arp_lease_type": "ARP Table Lease Type Filter",
            "dhcp_fortigate": "DHCP Entries FortiGate Filter",
            "dhcp_interface": "DHCP Entries Interface Filter",
            "vdom_fortigate": "VDOM Resources Firewall Filter",
            "vdom": "VDOM Resources VDOM Filter",
            "vdom_graph_layout": "VDOM Resources Graph Layout",
            "vdom_time_span": "VDOM Resources Time Span",
        }[filter_type]
        self._attr_icon = {
            "fortigate": "mdi:shield-router",
            "access_point": "mdi:access-point-network",
            "ssid": "mdi:wifi",
            "area": "mdi:floor-plan",
            "label": "mdi:label",
            "wifi_graph_time_span": "mdi:clock-outline",
            "arp_fortigate": "mdi:shield-router",
            "arp_interface": "mdi:lan-connect",
            "arp_lease_type": "mdi:ip-check",
            "dhcp_fortigate": "mdi:shield-router",
            "dhcp_interface": "mdi:lan-connect",
            "vdom_fortigate": "mdi:shield-router",
            "vdom": "mdi:server-network",
            "vdom_graph_layout": "mdi:view-dashboard-variant",
            "vdom_time_span": "mdi:clock-outline",
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
        if self._filter_type == "label":
            return self._manager.label_options
        if self._filter_type == "wifi_graph_time_span":
            return self._manager.wifi_graph_time_span_options
        if self._filter_type == "arp_fortigate":
            return self._manager.arp_fortigate_options
        if self._filter_type == "arp_interface":
            return self._manager.arp_interface_options
        if self._filter_type == "arp_lease_type":
            return self._manager.arp_lease_type_options
        if self._filter_type == "dhcp_fortigate":
            return self._manager.dhcp_fortigate_options
        if self._filter_type == "dhcp_interface":
            return self._manager.dhcp_interface_options
        if self._filter_type == "vdom_fortigate":
            return self._manager.vdom_fortigate_options
        if self._filter_type == "vdom":
            return self._manager.vdom_options
        if self._filter_type == "vdom_graph_layout":
            return self._manager.vdom_graph_layout_options
        return self._manager.vdom_time_span_options

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
        if self._filter_type == "label":
            return self._manager.selected_label
        if self._filter_type == "wifi_graph_time_span":
            return self._manager.selected_wifi_graph_time_span
        if self._filter_type == "arp_fortigate":
            return self._manager.selected_arp_fortigate
        if self._filter_type == "arp_interface":
            return self._manager.selected_arp_interface
        if self._filter_type == "arp_lease_type":
            return self._manager.selected_arp_lease_type
        if self._filter_type == "dhcp_fortigate":
            return self._manager.selected_dhcp_fortigate
        if self._filter_type == "dhcp_interface":
            return self._manager.selected_dhcp_interface
        if self._filter_type == "vdom_fortigate":
            return self._manager.selected_vdom_fortigate
        if self._filter_type == "vdom":
            return self._manager.selected_vdom
        if self._filter_type == "vdom_graph_layout":
            return self._manager.selected_vdom_graph_layout
        return self._manager.selected_vdom_time_span

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
        elif self._filter_type == "label":
            self._manager.select_label(option)
        elif self._filter_type == "wifi_graph_time_span":
            self._manager.select_wifi_graph_time_span(option)
        elif self._filter_type == "arp_fortigate":
            self._manager.select_arp_fortigate(option)
        elif self._filter_type == "arp_interface":
            self._manager.select_arp_interface(option)
        elif self._filter_type == "arp_lease_type":
            self._manager.select_arp_lease_type(option)
        elif self._filter_type == "dhcp_fortigate":
            self._manager.select_dhcp_fortigate(option)
        elif self._filter_type == "dhcp_interface":
            self._manager.select_dhcp_interface(option)
        elif self._filter_type == "vdom_fortigate":
            self._manager.select_vdom_fortigate(option)
        elif self._filter_type == "vdom":
            self._manager.select_vdom(option)
        elif self._filter_type == "vdom_graph_layout":
            self._manager.select_vdom_graph_layout(option)
        else:
            self._manager.select_vdom_time_span(option)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to shared filter changes."""
        self.async_on_remove(self._manager.add_listener(self.async_write_ha_state))
