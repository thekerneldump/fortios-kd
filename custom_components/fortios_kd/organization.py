"""Organize FortiOS KD devices by a hub area or label."""

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, label_registry as lr

from .const import (
    CONF_CLIENTS_FOLLOW_AP_AREA,
    CONF_CLIENTS_FOLLOW_AP_LABELS,
    CONF_HUB_AREA_ID,
    CONF_HUB_LABEL,
    CONF_HUB_LABEL_COLOR,
    CONF_HUB_LABEL_ID,
    CONF_INHERIT_HUB_AREA,
    CONF_MOVE_DEVICES_WITH_HUB,
    CONF_ORGANIZATION_MODE,
    DEFAULT_CLIENTS_FOLLOW_AP_AREA,
    DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
    DEFAULT_INHERIT_HUB_AREA,
    DEFAULT_MOVE_DEVICES_WITH_HUB,
    DEFAULT_ORGANIZATION_MODE,
    DOMAIN,
    ORGANIZATION_MODE_AREA,
    ORGANIZATION_MODE_LABEL,
)
from .coordinator import FortiOSKDCoordinator

CLIENT_IDENTIFIER_MARKER = "_wifi_client_"


def _rgb_to_hex(value: Any) -> str | None:
    """Convert a selector RGB list to a label-registry hex color."""
    if not isinstance(value, list) or len(value) != 3:
        return None
    if not all(isinstance(channel, int) and 0 <= channel <= 255 for channel in value):
        return None
    return "#{:02X}{:02X}{:02X}".format(*value)


class FortiOSKDOrganizationManager:
    """Apply optional per-hub area and label organization."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: FortiOSKDCoordinator,
        fortigate_serial: str,
    ) -> None:
        """Initialize organization management for one FortiGate."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._fortigate_serial = fortigate_serial
        self._settings: dict[str, Any] = dict(entry.data)
        self._device_registry = dr.async_get(hass)
        self._label_registry = lr.async_get(hass)
        self._updating_device_ids: set[str] = set()
        self._client_ap_labels: dict[str, set[str]] = {}

    @callback
    def setup(self) -> None:
        """Apply settings to existing devices and watch registry changes."""
        self._apply_existing_devices()
        self._entry.async_on_unload(
            self._hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                self._handle_device_registry_update,
            )
        )
        self._entry.async_on_unload(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def reconfigure(self, new_settings: Mapping[str, Any]) -> None:
        """Apply changed organization settings without overriding manual moves."""
        old_settings = self._settings
        old_area_id = self._configured_area_id(old_settings)
        new_area_id = self._configured_area_id(new_settings)
        old_label_id = self._configured_label_id(old_settings, create=False)
        new_label_id = self._configured_label_id(new_settings, create=True)
        devices = self._devices()

        self._settings = dict(new_settings)

        if old_label_id and old_label_id != new_label_id:
            for device in devices:
                if old_label_id in device.labels:
                    self._update_device(
                        device,
                        labels=device.labels - {old_label_id},
                    )

        if new_label_id:
            for device in devices:
                self._add_label(device, new_label_id)

        if new_settings.get(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ):
            self._sync_clients_to_ap_labels()

        clients_follow_ap = new_settings.get(
            CONF_CLIENTS_FOLLOW_AP_AREA,
            DEFAULT_CLIENTS_FOLLOW_AP_AREA,
        )
        if new_area_id is None:
            if clients_follow_ap:
                self._sync_clients_to_ap_areas(fallback_area_id=old_area_id)
            return

        hub = self._hub_device(devices)
        if hub is not None and (hub.area_id is None or hub.area_id == old_area_id):
            self._update_device(hub, area_id=new_area_id)

        if new_settings.get(CONF_INHERIT_HUB_AREA, DEFAULT_INHERIT_HUB_AREA):
            area_changed = old_area_id != new_area_id
            move_devices = new_settings.get(
                CONF_MOVE_DEVICES_WITH_HUB,
                DEFAULT_MOVE_DEVICES_WITH_HUB,
            )
            for device in devices:
                if hub is not None and device.id == hub.id:
                    continue
                if device.area_id is None or (
                    area_changed and move_devices and device.area_id == old_area_id
                ):
                    self._update_device(device, area_id=new_area_id)

        if clients_follow_ap:
            self._sync_clients_to_ap_areas(fallback_area_id=old_area_id)

    @callback
    def _apply_existing_devices(self) -> None:
        """Apply configured organization to unassigned existing devices."""
        label_id = self._configured_label_id(self._settings, create=True)
        area_id = self._configured_area_id(self._settings)
        inherit_area = self._settings.get(
            CONF_INHERIT_HUB_AREA,
            DEFAULT_INHERIT_HUB_AREA,
        )

        for device in self._devices():
            if label_id:
                self._add_label(device, label_id)
            if area_id is None or device.area_id is not None:
                continue
            if self._is_hub(device) or inherit_area:
                self._update_device(device, area_id=area_id)

        if self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_AREA,
            DEFAULT_CLIENTS_FOLLOW_AP_AREA,
        ):
            self._sync_clients_to_ap_areas()
        if self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ):
            self._sync_clients_to_ap_labels()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Keep associated clients aligned after polling or roaming."""
        if self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ):
            self._sync_clients_to_ap_labels()

    @callback
    def _handle_device_registry_update(
        self,
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        """Handle new devices and manual hub or AP area moves."""
        device_id = event.data["device_id"]
        if device_id in self._updating_device_ids:
            return

        device = self._device_registry.async_get(device_id)
        if device is None or device.config_entry_id != self._entry.entry_id:
            return

        if event.data["action"] == "create":
            self._apply_to_new_device(device)
            return

        if event.data["action"] != "update":
            return

        changes = event.data["changes"]
        if "area_id" in changes:
            old_area_id = changes["area_id"]
            if self._is_hub(device):
                self._handle_hub_area_move(device.area_id, old_area_id)
            elif self._is_ap(device):
                self._handle_ap_area_move(device, old_area_id)
        if "labels" in changes and self._is_ap(device):
            self._handle_ap_label_change(device, set(changes["labels"]))

    @callback
    def _apply_to_new_device(self, device: dr.DeviceEntry) -> None:
        """Apply current settings to one newly registered device."""
        label_id = self._configured_label_id(self._settings, create=True)
        if label_id:
            self._add_label(device, label_id)

        if self._is_client(device) and self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ):
            self._sync_client_to_ap_labels(device)

        if device.area_id is not None:
            return

        if self._is_client(device) and self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_AREA,
            DEFAULT_CLIENTS_FOLLOW_AP_AREA,
        ):
            ap_area_id = self._client_ap_area(device)
            if ap_area_id is not None:
                self._update_device(device, area_id=ap_area_id)
                return

        area_id = self._configured_area_id(self._settings)
        if area_id is None:
            return

        if self._is_hub(device):
            self._update_device(device, area_id=area_id)
            return

        if self._settings.get(CONF_INHERIT_HUB_AREA, DEFAULT_INHERIT_HUB_AREA):
            self._update_device(device, area_id=area_id)

    @callback
    def _handle_hub_area_move(
        self,
        new_area_id: str | None,
        old_area_id: str | None,
    ) -> None:
        """Store a manual hub move and optionally move managed children."""
        if self._settings.get(CONF_ORGANIZATION_MODE) != ORGANIZATION_MODE_AREA:
            return

        updated_data = dict(self._entry.data)
        if new_area_id is None:
            updated_data.pop(CONF_HUB_AREA_ID, None)
        else:
            updated_data[CONF_HUB_AREA_ID] = new_area_id
        self._settings = updated_data
        self._hass.config_entries.async_update_entry(self._entry, data=updated_data)

        if not (
            self._settings.get(CONF_INHERIT_HUB_AREA, DEFAULT_INHERIT_HUB_AREA)
            and self._settings.get(
                CONF_MOVE_DEVICES_WITH_HUB,
                DEFAULT_MOVE_DEVICES_WITH_HUB,
            )
        ):
            return

        for device in self._devices():
            if self._is_hub(device):
                continue
            if device.area_id is None or device.area_id == old_area_id:
                self._update_device(device, area_id=new_area_id)

    @callback
    def _handle_ap_area_move(
        self,
        ap_device: dr.DeviceEntry,
        old_area_id: str | None,
    ) -> None:
        """Move clients with an AP while preserving manual client areas."""
        if not self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_AREA,
            DEFAULT_CLIENTS_FOLLOW_AP_AREA,
        ):
            return

        ap_serial = self._device_identifier(ap_device)
        if ap_serial is None:
            return

        hub_area_id = self._configured_area_id(self._settings)
        for client_device in self._client_devices_for_ap(ap_serial):
            if client_device.area_id in {None, old_area_id, hub_area_id}:
                self._update_device(client_device, area_id=ap_device.area_id)

    @callback
    def _handle_ap_label_change(
        self,
        ap_device: dr.DeviceEntry,
        old_labels: set[str],
    ) -> None:
        """Apply AP label additions and removals to its current clients."""
        if not self._settings.get(
            CONF_CLIENTS_FOLLOW_AP_LABELS,
            DEFAULT_CLIENTS_FOLLOW_AP_LABELS,
        ):
            return

        ap_serial = self._device_identifier(ap_device)
        if ap_serial is None:
            return

        added_labels = ap_device.labels - old_labels
        removed_labels = old_labels - ap_device.labels
        for client_device in self._client_devices_for_ap(ap_serial):
            labels = (client_device.labels | added_labels) - removed_labels
            self._client_ap_labels[client_device.id] = set(ap_device.labels)
            if labels != client_device.labels:
                self._update_device(client_device, labels=labels)

    @callback
    def _sync_clients_to_ap_labels(self) -> None:
        """Synchronize current clients with their AP labels."""
        for client_device in self._client_devices():
            self._sync_client_to_ap_labels(client_device)

    @callback
    def _sync_client_to_ap_labels(self, client_device: dr.DeviceEntry) -> None:
        """Copy an AP's labels while retaining unrelated client labels."""
        ap_device = self._client_ap_device(client_device)
        if ap_device is None:
            return

        previous_ap_labels = self._client_ap_labels.get(client_device.id, set())
        labels = (client_device.labels | ap_device.labels) - (
            previous_ap_labels - ap_device.labels
        )
        self._client_ap_labels[client_device.id] = set(ap_device.labels)
        if labels != client_device.labels:
            self._update_device(client_device, labels=labels)

    @callback
    def _sync_clients_to_ap_areas(self, fallback_area_id: str | None = None) -> None:
        """Assign unassigned or previously hub-managed clients to their AP area."""
        for client in self._coordinator.data.get("wifi_clients", {}).get("results", []):
            mac = client.get("mac")
            ap_serial = client.get("wtp_id")
            if not isinstance(mac, str) or not isinstance(ap_serial, str):
                continue
            client_device = self._device_registry.async_get_device_by_identifier(
                (
                    DOMAIN,
                    f"{self._fortigate_serial}{CLIENT_IDENTIFIER_MARKER}{mac.lower()}",
                ),
                self._entry.entry_id,
            )
            ap_device = self._device_registry.async_get_device_by_identifier(
                (DOMAIN, ap_serial),
                self._entry.entry_id,
            )
            if client_device is None or ap_device is None or ap_device.area_id is None:
                continue
            if (
                client_device.area_id is None
                or client_device.area_id == fallback_area_id
            ):
                self._update_device(client_device, area_id=ap_device.area_id)

    def _client_ap_area(self, client_device: dr.DeviceEntry) -> str | None:
        """Return the current AP area for a client device."""
        ap_device = self._client_ap_device(client_device)
        return ap_device.area_id if ap_device else None

    def _client_ap_device(self, client_device: dr.DeviceEntry) -> dr.DeviceEntry | None:
        """Return the current AP device for a client device."""
        identifier = self._device_identifier(client_device)
        if identifier is None or CLIENT_IDENTIFIER_MARKER not in identifier:
            return None
        mac = identifier.rsplit(CLIENT_IDENTIFIER_MARKER, 1)[1]
        for client in self._coordinator.data.get("wifi_clients", {}).get("results", []):
            client_mac = client.get("mac")
            ap_serial = client.get("wtp_id")
            if (
                isinstance(client_mac, str)
                and client_mac.lower() == mac
                and isinstance(ap_serial, str)
            ):
                return self._device_registry.async_get_device_by_identifier(
                    (DOMAIN, ap_serial),
                    self._entry.entry_id,
                )
        return None

    def _client_devices(self) -> list[dr.DeviceEntry]:
        """Return currently associated client devices."""
        devices: list[dr.DeviceEntry] = []
        for client in self._coordinator.data.get("wifi_clients", {}).get("results", []):
            mac = client.get("mac")
            if not isinstance(mac, str):
                continue
            device = self._device_registry.async_get_device_by_identifier(
                (
                    DOMAIN,
                    f"{self._fortigate_serial}{CLIENT_IDENTIFIER_MARKER}{mac.lower()}",
                ),
                self._entry.entry_id,
            )
            if device is not None:
                devices.append(device)
        return devices

    def _client_devices_for_ap(self, ap_serial: str) -> list[dr.DeviceEntry]:
        """Return currently connected client devices for an AP serial."""
        devices: list[dr.DeviceEntry] = []
        for client in self._coordinator.data.get("wifi_clients", {}).get("results", []):
            mac = client.get("mac")
            if client.get("wtp_id") != ap_serial or not isinstance(mac, str):
                continue
            device = self._device_registry.async_get_device_by_identifier(
                (
                    DOMAIN,
                    f"{self._fortigate_serial}{CLIENT_IDENTIFIER_MARKER}{mac.lower()}",
                ),
                self._entry.entry_id,
            )
            if device is not None:
                devices.append(device)
        return devices

    def _configured_area_id(self, settings: Mapping[str, Any]) -> str | None:
        """Return a valid configured area when area mode is active."""
        if (
            settings.get(CONF_ORGANIZATION_MODE, DEFAULT_ORGANIZATION_MODE)
            != ORGANIZATION_MODE_AREA
        ):
            return None
        area_id = settings.get(CONF_HUB_AREA_ID)
        return area_id if isinstance(area_id, str) and area_id else None

    def _configured_label_id(
        self,
        settings: Mapping[str, Any],
        *,
        create: bool,
    ) -> str | None:
        """Return the configured label ID, optionally creating the label."""
        if (
            settings.get(CONF_ORGANIZATION_MODE, DEFAULT_ORGANIZATION_MODE)
            != ORGANIZATION_MODE_LABEL
        ):
            return None
        label_id = settings.get(CONF_HUB_LABEL_ID)
        if (
            isinstance(label_id, str)
            and label_id
            and self._label_registry.async_get_label(label_id) is not None
        ):
            return label_id

        # Retain compatibility with entries created before label selectors stored IDs.
        name = settings.get(CONF_HUB_LABEL)
        if not isinstance(name, str) or not (name := name.strip()):
            return None
        if label := self._label_registry.async_get_label_by_name(name):
            return label.label_id
        if not create:
            return None
        label = self._label_registry.async_create(
            name,
            color=_rgb_to_hex(settings.get(CONF_HUB_LABEL_COLOR)),
        )
        return label.label_id

    def _devices(self) -> list[dr.DeviceEntry]:
        """Return devices owned by this config entry."""
        return dr.async_entries_for_config_entry(
            self._device_registry,
            self._entry.entry_id,
        )

    def _hub_device(self, devices: list[dr.DeviceEntry]) -> dr.DeviceEntry | None:
        """Return the FortiGate device."""
        return next((device for device in devices if self._is_hub(device)), None)

    def _device_identifier(self, device: dr.DeviceEntry) -> str | None:
        """Return this integration's identifier for a device."""
        return next(
            (
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            ),
            None,
        )

    def _is_hub(self, device: dr.DeviceEntry) -> bool:
        """Return whether a device is this FortiGate."""
        return self._device_identifier(device) == self._fortigate_serial

    def _is_client(self, device: dr.DeviceEntry) -> bool:
        """Return whether a device is a wifi client."""
        identifier = self._device_identifier(device)
        return identifier is not None and CLIENT_IDENTIFIER_MARKER in identifier

    def _is_ap(self, device: dr.DeviceEntry) -> bool:
        """Return whether a device is a FortiAP."""
        identifier = self._device_identifier(device)
        return (
            identifier is not None
            and identifier != self._fortigate_serial
            and CLIENT_IDENTIFIER_MARKER not in identifier
        )

    @callback
    def _add_label(self, device: dr.DeviceEntry, label_id: str) -> None:
        """Add one label without disturbing user labels."""
        if label_id not in device.labels:
            self._update_device(device, labels=device.labels | {label_id})

    @callback
    def _update_device(self, device: dr.DeviceEntry, **changes: Any) -> None:
        """Update a device while suppressing reactions to our own event."""
        self._updating_device_ids.add(device.id)
        try:
            self._device_registry.async_update_device(device.id, **changes)
        finally:
            self._updating_device_ids.discard(device.id)
