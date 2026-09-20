"""Binary sensor platform for FortiOS KD virtual domains."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FortiOSKDCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VDOM management-status entities."""
    integration_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: FortiOSKDCoordinator = integration_data["coordinator"]
    status = integration_data["status"]
    fortigate_serial = str(status["serial"])
    fortigate_name = str(integration_data["fortigate_display_name"])

    known_vdoms = set(coordinator.vdom_names)
    async_add_entities(
        FortiGateVDOMManagementBinarySensor(
            coordinator,
            fortigate_serial,
            fortigate_name,
            vdom_name,
        )
        for vdom_name in sorted(known_vdoms)
    )

    def _add_new_vdoms() -> None:
        new_vdoms = coordinator.vdom_names - known_vdoms
        if not new_vdoms:
            return

        known_vdoms.update(new_vdoms)
        async_add_entities(
            FortiGateVDOMManagementBinarySensor(
                coordinator,
                fortigate_serial,
                fortigate_name,
                vdom_name,
            )
            for vdom_name in sorted(new_vdoms)
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_vdoms))


class FortiGateVDOMManagementBinarySensor(
    CoordinatorEntity[FortiOSKDCoordinator],
    BinarySensorEntity,
):
    """Indicate whether a VDOM is the FortiGate management VDOM."""

    _attr_has_entity_name = True
    _attr_name = "Management VDOM"
    _attr_icon = "mdi:server-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        fortigate_serial: str,
        fortigate_name: str,
        vdom_name: str,
    ) -> None:
        """Initialize a VDOM management-status entity."""
        super().__init__(coordinator)
        self._vdom_name = vdom_name
        vdom_identifier = f"{fortigate_serial}_vdom_{vdom_name}"

        self._attr_unique_id = f"{vdom_identifier}_management_vdom"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vdom_identifier)},
            name=f"VDOM {vdom_name} ({fortigate_name})",
            manufacturer="Fortinet",
            model="FortiOS Virtual Domain",
            via_device=(DOMAIN, fortigate_serial),
        )

    @property
    def available(self) -> bool:
        """Return whether this VDOM remains in the current inventory."""
        return (
            super().available
            and self.coordinator.vdom_data_available
            and self.coordinator.management_vdom is not None
            and self._vdom_name in self.coordinator.vdom_names
        )

    @property
    def is_on(self) -> bool | None:
        """Return true when this is the selected management VDOM."""
        if self.coordinator.management_vdom is None:
            return None
        return self._vdom_name == self.coordinator.management_vdom
