"""Editable FortiOS KD naming preferences."""

from typing import Any, override

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INTERFACE_PREFERRED_NAMES,
    CONF_PREFERRED_NAME,
    DATA_FILTER_MANAGER,
    DOMAIN,
)
from .coordinator import FortiOSKDCoordinator, interface_identifier
from .filter_manager import FortiOSKDFilterManager

PREFERRED_NAME_SCOPE_ATTRIBUTE = "fortios_kd_preferred_name_scope"
PREFERRED_NAME_SCOPE_FORTIGATE = "fortigate"
PREFERRED_NAME_SCOPE_INTERFACE = "interface"

_INTERFACE_PREFERRED_NAME = "preferred_name"
_INTERFACE_SOURCE_ALIAS = "source_alias"


def _interface_preference_key(vdom_name: str, interface_name: str) -> str:
    """Return the config-entry key for one VDOM-scoped interface."""
    return f"{vdom_name}::{interface_name}"


def _interface_alias(
    coordinator: FortiOSKDCoordinator,
    vdom_name: str,
    interface_name: str,
) -> str | None:
    """Return the normalized FortiGate alias for an interface."""
    interface = coordinator.get_interface(vdom_name, interface_name)
    if not isinstance(interface, dict):
        return None
    alias = interface.get("alias")
    return alias.strip() if isinstance(alias, str) and alias.strip() else ""


def _interface_preference(
    stored_preferences: dict[str, Any],
    key: str,
    interface_name: str,
    alias: str,
) -> tuple[str, str, bool]:
    """Return the preferred name, applied alias, and whether storage changed."""
    record = stored_preferences.get(key)
    if isinstance(record, dict):
        preferred_name = record.get(_INTERFACE_PREFERRED_NAME)
        source_alias = record.get(_INTERFACE_SOURCE_ALIAS)
        if (
            isinstance(preferred_name, str)
            and preferred_name.strip()
            and isinstance(source_alias, str)
            and source_alias == alias
        ):
            return preferred_name.strip(), source_alias, False

    preferred_name = alias or interface_name
    stored_preferences[key] = {
        _INTERFACE_PREFERRED_NAME: preferred_name,
        _INTERFACE_SOURCE_ALIAS: alias,
    }
    return preferred_name, alias, True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FortiGate and interface preferred-name entities."""
    integration_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: FortiOSKDCoordinator = integration_data["coordinator"]
    fortigate_serial = str(integration_data["status"]["serial"])
    stored_value = entry.data.get(CONF_INTERFACE_PREFERRED_NAMES)
    stored_preferences = dict(stored_value) if isinstance(stored_value, dict) else {}

    entities: list[TextEntity] = [
        FortiGatePreferredNameText(
            entry,
            fortigate_serial,
            str(integration_data["fortigate_default_preferred_name"]),
            str(integration_data["fortigate_preferred_name"]),
            integration_data,
            hass.data[DOMAIN][DATA_FILTER_MANAGER],
        )
    ]
    known_interface_keys: set[tuple[str, str]] = set()
    preferences_changed = False

    def add_interface_entities(
        interface_keys: set[tuple[str, str]],
    ) -> list[InterfacePreferredNameText]:
        """Build preferred-name entities for newly discovered interfaces."""
        nonlocal preferences_changed
        new_entities: list[InterfacePreferredNameText] = []
        for vdom_name, interface_name in sorted(interface_keys):
            key = (vdom_name, interface_name)
            if key in known_interface_keys:
                continue

            known_interface_keys.add(key)
            alias = _interface_alias(coordinator, vdom_name, interface_name) or ""
            preference_key = _interface_preference_key(vdom_name, interface_name)
            preferred_name, source_alias, changed = _interface_preference(
                stored_preferences,
                preference_key,
                interface_name,
                alias,
            )
            preferences_changed |= changed
            new_entities.append(
                InterfacePreferredNameText(
                    entry,
                    coordinator,
                    fortigate_serial,
                    vdom_name,
                    interface_name,
                    preferred_name,
                    source_alias,
                )
            )
        return new_entities

    entities.extend(add_interface_entities(coordinator.interface_keys))
    if preferences_changed:
        updated_data = dict(entry.data)
        updated_data[CONF_INTERFACE_PREFERRED_NAMES] = stored_preferences
        hass.config_entries.async_update_entry(entry, data=updated_data)

    async_add_entities(entities)

    if not coordinator.sync_interfaces:
        return

    @callback
    def add_new_interfaces() -> None:
        nonlocal preferences_changed
        preferences_changed = False
        latest_value = entry.data.get(CONF_INTERFACE_PREFERRED_NAMES)
        if isinstance(latest_value, dict):
            stored_preferences.clear()
            stored_preferences.update(latest_value)
        new_entities = add_interface_entities(coordinator.interface_keys)
        if preferences_changed:
            updated_data = dict(entry.data)
            updated_data[CONF_INTERFACE_PREFERRED_NAMES] = stored_preferences
            hass.config_entries.async_update_entry(entry, data=updated_data)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(add_new_interfaces))


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


class InterfacePreferredNameText(
    CoordinatorEntity[FortiOSKDCoordinator],
    TextEntity,
):
    """Store the dashboard name for one FortiGate interface."""

    _attr_has_entity_name = True
    _attr_name = "Preferred name"
    _attr_icon = "mdi:rename-box"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_native_min = 0
    _attr_native_max = 64

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: FortiOSKDCoordinator,
        fortigate_serial: str,
        vdom_name: str,
        interface_name: str,
        preferred_name: str,
        source_alias: str,
    ) -> None:
        """Initialize an interface preferred-name entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._vdom_name = vdom_name
        self._interface_name = interface_name
        self._value = preferred_name
        self._source_alias = source_alias
        self._preference_key = _interface_preference_key(vdom_name, interface_name)
        self._last_available: bool | None = None
        device_identifier = interface_identifier(
            fortigate_serial,
            vdom_name,
            interface_name,
        )
        self._attr_unique_id = f"{device_identifier}_preferred_name"
        self._attr_extra_state_attributes = {
            PREFERRED_NAME_SCOPE_ATTRIBUTE: PREFERRED_NAME_SCOPE_INTERFACE,
            "fortios_kd_interface": interface_name,
            "fortios_kd_vdom": vdom_name,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
        )

    @property
    @override
    def native_value(self) -> str:
        """Return the current dashboard name."""
        return self._value

    @property
    @override
    def available(self) -> bool:
        """Return whether the interface is in the current monitor response."""
        return (
            super().available
            and self.coordinator.get_interface(
                self._vdom_name,
                self._interface_name,
            )
            is not None
        )

    def _persist(self) -> None:
        """Persist this preference without replacing other interfaces."""
        stored_value = self._entry.data.get(CONF_INTERFACE_PREFERRED_NAMES)
        stored_preferences = (
            dict(stored_value) if isinstance(stored_value, dict) else {}
        )
        stored_preferences[self._preference_key] = {
            _INTERFACE_PREFERRED_NAME: self._value,
            _INTERFACE_SOURCE_ALIAS: self._source_alias,
        }
        updated_data = dict(self._entry.data)
        updated_data[CONF_INTERFACE_PREFERRED_NAMES] = stored_preferences
        self.hass.config_entries.async_update_entry(
            self._entry,
            data=updated_data,
        )

    @override
    async def async_set_value(self, value: str) -> None:
        """Persist a user-selected interface dashboard name."""
        stripped_value = value.strip()
        self._value = stripped_value or self._source_alias or self._interface_name
        self._persist()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to interface updates and remember availability."""
        await super().async_added_to_hass()
        self._last_available = self.available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply a changed FortiGate alias once without clobbering overrides."""
        alias = _interface_alias(
            self.coordinator,
            self._vdom_name,
            self._interface_name,
        )
        alias_changed = alias is not None and alias != self._source_alias
        if alias_changed:
            self._source_alias = alias
            self._value = alias or self._interface_name
            self._persist()

        available = self.available
        if alias_changed or available != self._last_available:
            self._last_available = available
            self.async_write_ha_state()
