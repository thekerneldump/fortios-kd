"""Manage the shared FortiOS KD dashboard filters."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from custom_components.fortios_kd.const import DOMAIN
from custom_components.fortios_kd.coordinator import FortiOSKDCoordinator
from custom_components.fortios_kd.privacy import mask_name, mask_ssid

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    label_registry as lr,
)

FILTER_ALL = "All"
FILTER_UNAVAILABLE_CLIENTS = "Unavailable Clients"
FILTER_NO_AREA = "No Area"
FILTER_NO_LABELS = "No Labels"
FILTER_NO_DHCP_LEASE = "No DHCP lease"
FILTER_RESERVED = "Reserved"
FILTER_LEASED = "Leased"
VDOM_GRAPH_LAYOUT_COMBINED = "Combined by resource"
VDOM_GRAPH_LAYOUT_SEPARATE = "Separate by VDOM"
CLIENT_IDENTIFIER_MARKER = "_wifi_client_"


@dataclass(slots=True)
class FortiOSKDFilterHub:
    """Describe one FortiGate supplying filter data."""

    name: str
    coordinator: FortiOSKDCoordinator
    mask_ap_names: bool
    mask_ssids: bool
    include_unassigned_ssids: bool
    remove_update_listener: Callable[[], None]


class FortiOSKDFilterManager:
    """Combine filter data from every configured FortiGate."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the filter manager."""
        self._hass = hass
        self._device_registry = dr.async_get(hass)
        self._area_registry = ar.async_get(hass)
        self._label_registry = lr.async_get(hass)
        self._hubs: dict[str, FortiOSKDFilterHub] = {}
        self._selected_fortigate = FILTER_ALL
        self._selected_access_point = FILTER_ALL
        self._selected_ssid = FILTER_ALL
        self._selected_area = FILTER_ALL
        self._selected_label = FILTER_ALL
        self._selected_arp_fortigate = FILTER_ALL
        self._selected_arp_interface = FILTER_ALL
        self._selected_arp_lease_type = FILTER_ALL
        self._selected_dhcp_fortigate = FILTER_ALL
        self._selected_dhcp_interface = FILTER_ALL
        self._selected_vdom_fortigate = FILTER_ALL
        self._selected_vdom = FILTER_ALL
        self._selected_vdom_graph_layout = VDOM_GRAPH_LAYOUT_COMBINED
        self._listeners: set[Callable[[], None]] = set()
        self._owner_entry_id: str | None = None
        self._remove_registry_listeners = [
            hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                self._handle_registry_update,
            ),
            hass.bus.async_listen(
                ar.EVENT_AREA_REGISTRY_UPDATED,
                self._handle_registry_update,
            ),
            hass.bus.async_listen(
                lr.EVENT_LABEL_REGISTRY_UPDATED,
                self._handle_registry_update,
            ),
        ]

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a filter-state listener."""
        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def _notify_listeners(self) -> None:
        """Notify entities that filter state changed."""
        for listener in self._listeners.copy():
            listener()

    def _handle_coordinator_update(self) -> None:
        """Update selections and entities after a coordinator refresh."""
        if self._selected_access_point not in self.access_point_options:
            self._selected_access_point = FILTER_ALL
        if self._selected_ssid not in self.ssid_options:
            self._selected_ssid = FILTER_ALL
        if self._selected_area not in self.area_options:
            self._selected_area = FILTER_ALL
        if self._selected_label not in self.label_options:
            self._selected_label = FILTER_ALL
        if self._selected_arp_fortigate not in self.arp_fortigate_options:
            self._selected_arp_fortigate = FILTER_ALL
        if self._selected_arp_interface not in self.arp_interface_options:
            self._selected_arp_interface = FILTER_ALL
        if self._selected_arp_lease_type not in self.arp_lease_type_options:
            self._selected_arp_lease_type = FILTER_ALL
        if self._selected_dhcp_fortigate not in self.dhcp_fortigate_options:
            self._selected_dhcp_fortigate = FILTER_ALL
        if self._selected_dhcp_interface not in self.dhcp_interface_options:
            self._selected_dhcp_interface = FILTER_ALL
        if self._selected_vdom_fortigate not in self.vdom_fortigate_options:
            self._selected_vdom_fortigate = FILTER_ALL
        if self._selected_vdom not in self.vdom_options:
            self._selected_vdom = FILTER_ALL
        self._notify_listeners()

    @callback
    def _handle_registry_update(self, _event: Event[Any]) -> None:
        """Refresh area and label choices after registry changes."""
        self._handle_coordinator_update()

    def shutdown(self) -> None:
        """Remove registry listeners owned by this manager."""
        for remove_listener in self._remove_registry_listeners:
            remove_listener()
        self._remove_registry_listeners.clear()

    def register_hub(
        self,
        entry_id: str,
        name: str,
        coordinator: FortiOSKDCoordinator,
        *,
        mask_ap_names: bool,
        mask_ssids: bool,
        include_unassigned_ssids: bool,
    ) -> None:
        """Register or replace a FortiGate."""
        if existing_hub := self._hubs.pop(entry_id, None):
            existing_hub.remove_update_listener()

        remove_update_listener = coordinator.async_add_listener(
            self._handle_coordinator_update
        )
        self._hubs[entry_id] = FortiOSKDFilterHub(
            name,
            coordinator,
            mask_ap_names,
            mask_ssids,
            include_unassigned_ssids,
            remove_update_listener,
        )
        self._handle_coordinator_update()

    def unregister_hub(self, entry_id: str) -> None:
        """Remove a FortiGate."""
        if hub := self._hubs.pop(entry_id, None):
            hub.remove_update_listener()
        if self._selected_fortigate not in self.fortigate_options:
            self._selected_fortigate = FILTER_ALL
            self._selected_access_point = FILTER_ALL
            self._selected_ssid = FILTER_ALL
            self._selected_area = FILTER_ALL
            self._selected_label = FILTER_ALL
        if self._selected_arp_fortigate not in self.arp_fortigate_options:
            self._selected_arp_fortigate = FILTER_ALL
            self._selected_arp_interface = FILTER_ALL
            self._selected_arp_lease_type = FILTER_ALL
        if self._selected_dhcp_fortigate not in self.dhcp_fortigate_options:
            self._selected_dhcp_fortigate = FILTER_ALL
            self._selected_dhcp_interface = FILTER_ALL
        if self._selected_vdom_fortigate not in self.vdom_fortigate_options:
            self._selected_vdom_fortigate = FILTER_ALL
            self._selected_vdom = FILTER_ALL
        self._handle_coordinator_update()

    def update_hub_name(self, entry_id: str, name: str) -> None:
        """Update a FortiGate display name and preserve active selections."""
        hub = self._hubs.get(entry_id)
        if hub is None or hub.name == name:
            return

        old_name = hub.name
        hub.name = name
        for attribute in (
            "_selected_fortigate",
            "_selected_arp_fortigate",
            "_selected_dhcp_fortigate",
            "_selected_vdom_fortigate",
        ):
            if getattr(self, attribute) == old_name:
                setattr(self, attribute, name)
        self._handle_coordinator_update()

    @property
    def has_hubs(self) -> bool:
        """Return whether any FortiGate hubs are registered."""
        return bool(self._hubs)

    def claim_owner(self, entry_id: str) -> bool:
        """Claim ownership of the shared select entities."""
        if self._owner_entry_id is None:
            self._owner_entry_id = entry_id
        return self._owner_entry_id == entry_id

    def release_owner(self, entry_id: str) -> str | None:
        """Release select ownership and return a possible successor."""
        if self._owner_entry_id != entry_id:
            return None

        self._owner_entry_id = None
        return next(iter(self._hubs), None)

    @property
    def fortigate_options(self) -> list[str]:
        """Return all available FortiGate names."""
        names = {hub.name for hub in self._hubs.values()}
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_fortigate(self) -> str:
        """Return the selected FortiGate."""
        return self._selected_fortigate

    def select_fortigate(self, option: str) -> None:
        """Select a FortiGate."""
        if option not in self.fortigate_options:
            raise ValueError(f"Unknown FortiGate option: {option}")

        self._selected_fortigate = option
        self._selected_access_point = FILTER_ALL
        self._selected_ssid = FILTER_ALL
        self._selected_area = FILTER_ALL
        self._selected_label = FILTER_ALL
        self._notify_listeners()

    @property
    def access_point_options(self) -> list[str]:
        """Return AP names for the selected FortiGate."""
        names: set[str] = set()

        for hub in self._hubs.values():
            if self._selected_fortigate not in (FILTER_ALL, hub.name):
                continue

            data = hub.coordinator.data or {}
            for access_point in data.get("results", []):
                name = access_point.get("name")
                if isinstance(name, str) and name:
                    names.add(mask_name(name) if hub.mask_ap_names else name)

        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_access_point(self) -> str:
        """Return the selected access point."""
        return self._selected_access_point

    def select_access_point(self, option: str) -> None:
        """Select an access point."""
        if option not in self.access_point_options:
            raise ValueError(f"Unknown access point option: {option}")

        self._selected_access_point = option
        if self._selected_ssid == FILTER_UNAVAILABLE_CLIENTS:
            self._selected_ssid = FILTER_ALL
        self._notify_listeners()

    @property
    def ssid_options(self) -> list[str]:
        """Return configured SSIDs for the selected FortiGate."""
        names: set[str] = set()

        for hub in self._hubs.values():
            if self._selected_fortigate not in (FILTER_ALL, hub.name):
                continue

            data = hub.coordinator.data or {}
            configured_vaps = data.get("configured_vaps") or {}
            assigned_vap_names = self._assigned_vap_names(data)

            for vap in configured_vaps.get("results", []):
                if not isinstance(vap, dict):
                    continue
                vap_name = vap.get("name")
                if (
                    not hub.include_unassigned_ssids
                    and vap_name not in assigned_vap_names
                ):
                    continue
                ssid = vap.get("ssid")
                if isinstance(ssid, str) and ssid:
                    names.add(mask_ssid(ssid) if hub.mask_ssids else ssid)

            wifi_clients = data.get("wifi_clients") or {}
            for client in wifi_clients.get("results", []):
                if not isinstance(client, dict):
                    continue
                ssid = client.get("ssid")
                if isinstance(ssid, str) and ssid:
                    names.add(mask_ssid(ssid) if hub.mask_ssids else ssid)

        names.discard(FILTER_UNAVAILABLE_CLIENTS)
        return [
            FILTER_ALL,
            FILTER_UNAVAILABLE_CLIENTS,
            *sorted(names, key=str.casefold),
        ]

    @staticmethod
    def _assigned_vap_names(data: dict[str, Any]) -> set[str]:
        """Return VAP names assigned manually or automatically by a profile."""
        profiles = data.get("configured_wtp_profiles") or {}
        if not isinstance(profiles, dict):
            return set()

        assigned_names: set[str] = set()
        automatic_modes: set[str] = set()

        for profile in profiles.get("results", []):
            if not isinstance(profile, dict):
                continue

            for key, radio in profile.items():
                if not key.startswith("radio-") or not isinstance(radio, dict):
                    continue

                vap_all = radio.get("vap-all")
                if vap_all in ("enable", "tunnel"):
                    automatic_modes.add("tunnel")
                elif vap_all == "bridge":
                    automatic_modes.add("bridge")

                vaps = radio.get("vaps", [])
                if isinstance(vaps, str):
                    assigned_names.add(vaps)
                elif isinstance(vaps, list):
                    for vap in vaps:
                        if isinstance(vap, str):
                            assigned_names.add(vap)
                        elif isinstance(vap, dict):
                            name = vap.get("name")
                            if isinstance(name, str):
                                assigned_names.add(name)

        configured_vaps = data.get("configured_vaps") or {}
        if not isinstance(configured_vaps, dict):
            return assigned_names

        for vap in configured_vaps.get("results", []):
            if not isinstance(vap, dict):
                continue
            name = vap.get("name")
            if not isinstance(name, str):
                continue

            local_bridging = vap.get("local-bridging")
            mode = (
                "bridge"
                if local_bridging in (True, 1, "enable", "enabled", "true")
                else "tunnel"
            )
            if mode in automatic_modes:
                assigned_names.add(name)

        return assigned_names

    @property
    def selected_ssid(self) -> str:
        """Return the selected SSID."""
        return self._selected_ssid

    def select_ssid(self, option: str) -> None:
        """Select an SSID."""
        if option not in self.ssid_options:
            raise ValueError(f"Unknown SSID option: {option}")

        if option == FILTER_UNAVAILABLE_CLIENTS:
            self._selected_fortigate = FILTER_ALL
            self._selected_access_point = FILTER_ALL
        self._selected_ssid = option
        self._notify_listeners()

    def _client_devices(self) -> list[dr.AnyDeviceEntry]:
        """Return client devices belonging to the selected FortiGate hubs."""
        devices: list[dr.AnyDeviceEntry] = []
        for entry_id, hub in self._hubs.items():
            if self._selected_fortigate not in (FILTER_ALL, hub.name):
                continue
            devices.extend(
                device
                for device in dr.async_entries_for_config_entry(
                    self._device_registry,
                    entry_id,
                )
                if any(
                    domain == DOMAIN and CLIENT_IDENTIFIER_MARKER in identifier
                    for domain, identifier in device.identifiers
                )
            )
        return devices

    @property
    def area_options(self) -> list[str]:
        """Return effective client areas for the selected FortiGate."""
        names: set[str] = set()
        has_unassigned = False
        for device in self._client_devices():
            area_id = dr.async_get_effective_area_id(self._hass, device)
            if area_id is None:
                has_unassigned = True
                continue
            if area := self._area_registry.async_get_area(area_id):
                names.add(area.name)

        options = [FILTER_ALL]
        if has_unassigned:
            options.append(FILTER_NO_AREA)
        return [*options, *sorted(names, key=str.casefold)]

    @property
    def selected_area(self) -> str:
        """Return the selected client area."""
        return self._selected_area

    def select_area(self, option: str) -> None:
        """Select a client area."""
        if option not in self.area_options:
            raise ValueError(f"Unknown area option: {option}")
        self._selected_area = option
        self._notify_listeners()

    @property
    def label_options(self) -> list[str]:
        """Return client labels for the selected FortiGate."""
        names: set[str] = set()
        has_unassigned = False
        for device in self._client_devices():
            if not device.labels:
                has_unassigned = True
            for label_id in device.labels:
                if label := self._label_registry.async_get_label(label_id):
                    names.add(label.name)

        options = [FILTER_ALL]
        if has_unassigned:
            options.append(FILTER_NO_LABELS)
        return [*options, *sorted(names, key=str.casefold)]

    @property
    def selected_label(self) -> str:
        """Return the selected client label."""
        return self._selected_label

    def select_label(self, option: str) -> None:
        """Select a client label."""
        if option not in self.label_options:
            raise ValueError(f"Unknown label option: {option}")
        self._selected_label = option
        self._notify_listeners()

    def _arp_hubs(self) -> list[FortiOSKDFilterHub]:
        """Return ARP-enabled hubs matching the ARP FortiGate selection."""
        return [
            hub
            for hub in self._hubs.values()
            if hub.coordinator.sync_arp_table is True
            and self._selected_arp_fortigate in (FILTER_ALL, hub.name)
        ]

    @property
    def arp_fortigate_options(self) -> list[str]:
        """Return FortiGates with ARP synchronization enabled."""
        names = {
            hub.name
            for hub in self._hubs.values()
            if hub.coordinator.sync_arp_table is True
        }
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_arp_fortigate(self) -> str:
        """Return the selected ARP-table FortiGate."""
        return self._selected_arp_fortigate

    def select_arp_fortigate(self, option: str) -> None:
        """Select an ARP-table FortiGate and reset dependent filters."""
        if option not in self.arp_fortigate_options:
            raise ValueError(f"Unknown ARP FortiGate option: {option}")

        self._selected_arp_fortigate = option
        self._selected_arp_interface = FILTER_ALL
        self._selected_arp_lease_type = FILTER_ALL
        self._notify_listeners()

    @property
    def arp_interface_options(self) -> list[str]:
        """Return ARP interfaces for the selected FortiGate."""
        names: set[str] = set()
        for hub in self._arp_hubs():
            for mac in hub.coordinator.arp_macs:
                for entry in hub.coordinator.get_arp_entries(mac):
                    interface = entry.get("interface")
                    if isinstance(interface, str) and interface:
                        names.add(interface)
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_arp_interface(self) -> str:
        """Return the selected ARP-table interface."""
        return self._selected_arp_interface

    def select_arp_interface(self, option: str) -> None:
        """Select an ARP-table interface and reset the lease-type filter."""
        if option not in self.arp_interface_options:
            raise ValueError(f"Unknown ARP interface option: {option}")

        self._selected_arp_interface = option
        self._selected_arp_lease_type = FILTER_ALL
        self._notify_listeners()

    @property
    def arp_lease_type_options(self) -> list[str]:
        """Return DHCP lease types represented by matching ARP rows."""
        lease_types: set[str] = set()
        for hub in self._arp_hubs():
            for mac in hub.coordinator.arp_macs:
                arp_entries = hub.coordinator.get_arp_entries(mac)
                if self._selected_arp_interface != FILTER_ALL and not any(
                    entry.get("interface") == self._selected_arp_interface
                    for entry in arp_entries
                ):
                    continue

                dhcp_entries = hub.coordinator.get_dhcp_entries(mac)
                if not dhcp_entries:
                    lease_types.add(FILTER_NO_DHCP_LEASE)
                elif any(entry.get("reserved") is True for entry in dhcp_entries):
                    lease_types.add(FILTER_RESERVED)
                else:
                    lease_types.add(FILTER_LEASED)

        ordered_types = [
            lease_type
            for lease_type in (
                FILTER_RESERVED,
                FILTER_LEASED,
                FILTER_NO_DHCP_LEASE,
            )
            if lease_type in lease_types
        ]
        return [FILTER_ALL, *ordered_types]

    @property
    def selected_arp_lease_type(self) -> str:
        """Return the selected ARP-table lease type."""
        return self._selected_arp_lease_type

    def select_arp_lease_type(self, option: str) -> None:
        """Select an ARP-table lease type."""
        if option not in self.arp_lease_type_options:
            raise ValueError(f"Unknown ARP lease-type option: {option}")

        self._selected_arp_lease_type = option
        self._notify_listeners()

    def _dhcp_hubs(self) -> list[FortiOSKDFilterHub]:
        """Return DHCP-enabled hubs matching the DHCP FortiGate selection."""
        return [
            hub
            for hub in self._hubs.values()
            if hub.coordinator.sync_dhcp_leases is True
            and self._selected_dhcp_fortigate in (FILTER_ALL, hub.name)
        ]

    @property
    def dhcp_fortigate_options(self) -> list[str]:
        """Return FortiGates with DHCP synchronization enabled."""
        names = {
            hub.name
            for hub in self._hubs.values()
            if hub.coordinator.sync_dhcp_leases is True
        }
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_dhcp_fortigate(self) -> str:
        """Return the selected DHCP-entry FortiGate."""
        return self._selected_dhcp_fortigate

    def select_dhcp_fortigate(self, option: str) -> None:
        """Select a DHCP-entry FortiGate and reset the interface filter."""
        if option not in self.dhcp_fortigate_options:
            raise ValueError(f"Unknown DHCP FortiGate option: {option}")

        self._selected_dhcp_fortigate = option
        self._selected_dhcp_interface = FILTER_ALL
        self._notify_listeners()

    @property
    def dhcp_interface_options(self) -> list[str]:
        """Return DHCP interfaces for the selected FortiGate."""
        names: set[str] = set()
        for hub in self._dhcp_hubs():
            for mac in hub.coordinator.dhcp_macs:
                for entry in hub.coordinator.get_dhcp_entries(mac):
                    interface = entry.get("interface")
                    if isinstance(interface, str) and interface:
                        names.add(interface)
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_dhcp_interface(self) -> str:
        """Return the selected DHCP-entry interface."""
        return self._selected_dhcp_interface

    def select_dhcp_interface(self, option: str) -> None:
        """Select a DHCP-entry interface."""
        if option not in self.dhcp_interface_options:
            raise ValueError(f"Unknown DHCP interface option: {option}")

        self._selected_dhcp_interface = option
        self._notify_listeners()

    def _vdom_hubs(self) -> list[FortiOSKDFilterHub]:
        """Return hubs matching the VDOM-resource FortiGate selection."""
        return [
            hub
            for hub in self._hubs.values()
            if hub.coordinator.vdom_names
            and self._selected_vdom_fortigate in (FILTER_ALL, hub.name)
        ]

    @property
    def vdom_fortigate_options(self) -> list[str]:
        """Return FortiGates that currently expose VDOM inventory."""
        names = {hub.name for hub in self._hubs.values() if hub.coordinator.vdom_names}
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_vdom_fortigate(self) -> str:
        """Return the selected VDOM-resource FortiGate."""
        return self._selected_vdom_fortigate

    def select_vdom_fortigate(self, option: str) -> None:
        """Select a VDOM-resource FortiGate and reset the VDOM filter."""
        if option not in self.vdom_fortigate_options:
            raise ValueError(f"Unknown VDOM FortiGate option: {option}")

        self._selected_vdom_fortigate = option
        self._selected_vdom = FILTER_ALL
        self._notify_listeners()

    @property
    def vdom_options(self) -> list[str]:
        """Return VDOM names for the selected FortiGate."""
        names = {
            vdom_name
            for hub in self._vdom_hubs()
            for vdom_name in hub.coordinator.vdom_names
            if isinstance(vdom_name, str) and vdom_name
        }
        return [FILTER_ALL, *sorted(names, key=str.casefold)]

    @property
    def selected_vdom(self) -> str:
        """Return the selected VDOM name."""
        return self._selected_vdom

    def select_vdom(self, option: str) -> None:
        """Select a VDOM resource group."""
        if option not in self.vdom_options:
            raise ValueError(f"Unknown VDOM option: {option}")

        self._selected_vdom = option
        self._notify_listeners()

    @property
    def vdom_graph_layout_options(self) -> list[str]:
        """Return the available VDOM resource graph layouts."""
        return [VDOM_GRAPH_LAYOUT_COMBINED, VDOM_GRAPH_LAYOUT_SEPARATE]

    @property
    def selected_vdom_graph_layout(self) -> str:
        """Return the selected VDOM resource graph layout."""
        return self._selected_vdom_graph_layout

    def select_vdom_graph_layout(self, option: str) -> None:
        """Select how VDOM resource history graphs are grouped."""
        if option not in self.vdom_graph_layout_options:
            raise ValueError(f"Unknown VDOM graph layout option: {option}")

        self._selected_vdom_graph_layout = option
        self._notify_listeners()
