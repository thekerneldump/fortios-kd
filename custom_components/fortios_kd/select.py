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
            FortiOSKDFilterSelect(manager, "device_fortigate"),
            FortiOSKDFilterSelect(manager, "device_hardware_vendor"),
            FortiOSKDFilterSelect(manager, "device_hardware_type"),
            FortiOSKDFilterSelect(manager, "device_hardware_family"),
            FortiOSKDFilterSelect(manager, "device_operating_system"),
            FortiOSKDFilterSelect(manager, "device_software_version"),
            FortiOSKDFilterSelect(manager, "device_interface"),
            FortiOSKDFilterSelect(manager, "device_last_seen"),
            FortiOSKDFilterSelect(manager, "vdom_fortigate"),
            FortiOSKDFilterSelect(manager, "vdom"),
            FortiOSKDFilterSelect(manager, "vdom_graph_layout"),
            FortiOSKDFilterSelect(manager, "vdom_time_span"),
            FortiOSKDFilterSelect(manager, "interface_fortigate"),
            FortiOSKDFilterSelect(manager, "interface_link"),
            FortiOSKDFilterSelect(manager, "interface_speed_duplex"),
            FortiOSKDFilterSelect(manager, "interface_parent"),
            FortiOSKDFilterSelect(manager, "interface_graph_layout"),
            FortiOSKDFilterSelect(manager, "interface_time_span"),
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
            "device_fortigate": "Device Table FortiGate Filter",
            "device_hardware_vendor": "Device Table Hardware Vendor Filter",
            "device_hardware_type": "Device Table Hardware Type Filter",
            "device_hardware_family": "Device Table Hardware Family Filter",
            "device_operating_system": "Device Table Operating System Filter",
            "device_software_version": "Device Table Software Version Filter",
            "device_interface": "Device Table Interface Filter",
            "device_last_seen": "Device Table Last Seen Filter",
            "vdom_fortigate": "VDOM Resources Firewall Filter",
            "vdom": "VDOM Resources VDOM Filter",
            "vdom_graph_layout": "VDOM Resources Graph Layout",
            "vdom_time_span": "VDOM Resources Time Span",
            "interface_fortigate": "Interface Graphs Firewall Filter",
            "interface_link": "Interface Graphs Link Filter",
            "interface_speed_duplex": "Interface Graphs Speed and Duplex Filter",
            "interface_parent": "Interface Graphs Parent Interface Filter",
            "interface_graph_layout": "Interface Graphs Graph Layout",
            "interface_time_span": "Interface Graphs Time Span",
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
            "device_fortigate": "mdi:shield-router",
            "device_hardware_vendor": "mdi:factory",
            "device_hardware_type": "mdi:devices",
            "device_hardware_family": "mdi:devices",
            "device_operating_system": "mdi:laptop",
            "device_software_version": "mdi:update",
            "device_interface": "mdi:lan-connect",
            "device_last_seen": "mdi:clock-outline",
            "vdom_fortigate": "mdi:shield-router",
            "vdom": "mdi:server-network",
            "vdom_graph_layout": "mdi:view-dashboard-variant",
            "vdom_time_span": "mdi:clock-outline",
            "interface_fortigate": "mdi:shield-router",
            "interface_link": "mdi:lan-connect",
            "interface_speed_duplex": "mdi:speedometer",
            "interface_parent": "mdi:lan-pending",
            "interface_graph_layout": "mdi:view-dashboard-variant",
            "interface_time_span": "mdi:clock-outline",
        }[filter_type]

    @property
    @override
    def options(self) -> list[str]:
        """Return the available filter options."""
        return getattr(self._manager, f"{self._filter_type}_options")

    @property
    @override
    def current_option(self) -> str:
        """Return the selected filter option."""
        return getattr(self._manager, f"selected_{self._filter_type}")

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a filter option."""
        getattr(self._manager, f"select_{self._filter_type}")(option)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to shared filter changes."""
        self.async_on_remove(self._manager.add_listener(self.async_write_ha_state))
