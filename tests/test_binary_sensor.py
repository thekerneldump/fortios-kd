"""Tests for FortiOS KD binary sensors."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry  # noqa: TID251


async def test_vdom_setup_adds_new_inventory_devices(hass: HomeAssistant) -> None:
    """Test newly discovered VDOMs are added without reloading the integration."""
    from custom_components.fortios_kd.binary_sensor import (  # noqa: PLC0415
        async_setup_entry,
    )

    entry = MockConfigEntry(domain="fortios_kd")
    entry.add_to_hass(hass)
    coordinator = Mock()
    coordinator.vdom_names = {"root"}
    coordinator.async_add_listener.return_value = Mock()
    hass.data["fortios_kd"] = {
        entry.entry_id: {
            "coordinator": coordinator,
            "status": {"serial": "FGT123"},
            "fortigate_display_name": "TestGate",
        }
    }
    added_entities = []

    await async_setup_entry(hass, entry, added_entities.extend)

    assert [entity.unique_id for entity in added_entities] == [
        "FGT123_vdom_root_management_vdom"
    ]

    coordinator.vdom_names = {"lab", "root"}
    listener = coordinator.async_add_listener.call_args.args[0]
    listener()

    assert [entity.unique_id for entity in added_entities] == [
        "FGT123_vdom_root_management_vdom",
        "FGT123_vdom_lab_management_vdom",
    ]


def test_vdom_management_entity_is_linked_to_fortigate() -> None:
    """Test VDOM devices are linked through their FortiGate."""
    from custom_components.fortios_kd.binary_sensor import (  # noqa: PLC0415
        FortiGateVDOMManagementBinarySensor,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.vdom_data_available = True
    coordinator.vdom_names = {"lab", "root"}
    coordinator.management_vdom = "root"

    root = FortiGateVDOMManagementBinarySensor(
        coordinator,
        "FGT123",
        "TestGate",
        "root",
    )
    lab = FortiGateVDOMManagementBinarySensor(
        coordinator,
        "FGT123",
        "TestGate",
        "lab",
    )

    assert root.is_on is True
    assert lab.is_on is False
    assert root.available
    assert root.name == "Management VDOM"
    assert root.unique_id == "FGT123_vdom_root_management_vdom"
    assert root.device_info["identifiers"] == {
        ("fortios_kd", "FGT123_vdom_root")
    }
    assert root.device_info["name"] == "VDOM root (TestGate)"
    assert root.device_info["via_device"] == ("fortios_kd", "FGT123")


def test_vdom_management_entity_handles_missing_inventory() -> None:
    """Test removed VDOMs and unknown management selection are unavailable."""
    from custom_components.fortios_kd.binary_sensor import (  # noqa: PLC0415
        FortiGateVDOMManagementBinarySensor,
    )

    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.vdom_data_available = False
    coordinator.vdom_names = set()
    coordinator.management_vdom = None

    entity = FortiGateVDOMManagementBinarySensor(
        coordinator,
        "FGT123",
        "TestGate",
        "root",
    )

    assert not entity.available
    assert entity.is_on is None
