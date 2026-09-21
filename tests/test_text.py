"""Tests for FortiOS KD editable naming preferences."""

from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from tests.common import MockConfigEntry  # noqa: TID251

DOMAIN = "fortios_kd"


async def test_preferred_name_is_stored_without_renaming_device(
    hass: HomeAssistant,
) -> None:
    """Test edits persist as integration metadata and notify dashboard filters."""
    from custom_components.fortios_kd.const import CONF_PREFERRED_NAME  # noqa: PLC0415
    from custom_components.fortios_kd.text import (  # noqa: PLC0415
        FortiGatePreferredNameText,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "fortigate.example"},
    )
    entry.add_to_hass(hass)
    integration_data = {"fortigate_preferred_name": "FortiGate80E"}
    filter_manager = Mock()
    entity = FortiGatePreferredNameText(
        entry,
        "FGT123",
        "FortiGate80E",
        "FortiGate80E",
        integration_data,
        filter_manager,
    )
    entity.hass = hass

    assert entity.native_value == "FortiGate80E"
    assert entity.unique_id == "FGT123_preferred_name"
    assert entity.entity_category is EntityCategory.CONFIG
    assert entity.device_info["identifiers"] == {(DOMAIN, "FGT123")}
    assert entity.extra_state_attributes == {
        "fortios_kd_preferred_name_scope": "fortigate"
    }

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_set_value("  OfficeGate80E  ")

    assert entry.data[CONF_PREFERRED_NAME] == "OfficeGate80E"
    assert entity.native_value == "OfficeGate80E"
    assert integration_data["fortigate_preferred_name"] == "OfficeGate80E"
    filter_manager.update_hub_name.assert_called_once_with(
        entry.entry_id,
        "OfficeGate80E",
    )
    write_state.assert_called_once_with()


async def test_clearing_preferred_name_restores_default(
    hass: HomeAssistant,
) -> None:
    """Test blank input removes the override and restores the device-name fallback."""
    from custom_components.fortios_kd.const import CONF_PREFERRED_NAME  # noqa: PLC0415
    from custom_components.fortios_kd.text import (  # noqa: PLC0415
        FortiGatePreferredNameText,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "fortigate.example",
            CONF_PREFERRED_NAME: "OfficeGate80E",
        },
    )
    entry.add_to_hass(hass)
    integration_data = {"fortigate_preferred_name": "OfficeGate80E"}
    filter_manager = Mock()
    entity = FortiGatePreferredNameText(
        entry,
        "FGT123",
        "FortiGate80E",
        "OfficeGate80E",
        integration_data,
        filter_manager,
    )
    entity.hass = hass

    with patch.object(entity, "async_write_ha_state"):
        await entity.async_set_value("   ")

    assert CONF_PREFERRED_NAME not in entry.data
    assert entity.native_value == "FortiGate80E"
    filter_manager.update_hub_name.assert_called_once_with(
        entry.entry_id,
        "FortiGate80E",
    )


async def test_interface_preferred_name_tracks_alias_without_overwriting_user(
    hass: HomeAssistant,
) -> None:
    """Test an alias change is applied once while a stable alias preserves edits."""
    from custom_components.fortios_kd.const import (  # noqa: PLC0415
        CONF_INTERFACE_PREFERRED_NAMES,
    )
    from custom_components.fortios_kd.text import (  # noqa: PLC0415
        InterfacePreferredNameText,
    )

    entry = MockConfigEntry(domain=DOMAIN, data={"host": "fortigate.example"})
    entry.add_to_hass(hass)
    interface = {"name": "wan1", "alias": "Primary uplink"}
    coordinator = Mock()
    coordinator.last_update_success = True
    coordinator.get_interface.side_effect = lambda _vdom, _name: interface
    entity = InterfacePreferredNameText(
        entry,
        coordinator,
        "FGT123",
        "root",
        "wan1",
        "Primary uplink",
        "Primary uplink",
    )
    entity.hass = hass
    entity._last_available = True  # noqa: SLF001

    assert entity.native_value == "Primary uplink"
    assert entity.unique_id == "FGT123_interface_wan1_preferred_name"
    assert entity.device_info["identifiers"] == {(DOMAIN, "FGT123_interface_wan1")}
    assert entity.extra_state_attributes == {
        "fortios_kd_preferred_name_scope": "interface",
        "fortios_kd_interface": "wan1",
        "fortios_kd_vdom": "root",
    }

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_set_value("  Internet  ")
        write_state.reset_mock()
        entity._handle_coordinator_update()  # noqa: SLF001
        write_state.assert_not_called()

        interface["alias"] = "Fiber uplink"
        entity._handle_coordinator_update()  # noqa: SLF001
        write_state.assert_called_once_with()

    assert entity.native_value == "Fiber uplink"
    assert entry.data[CONF_INTERFACE_PREFERRED_NAMES]["root::wan1"] == {
        "preferred_name": "Fiber uplink",
        "source_alias": "Fiber uplink",
    }


async def test_text_setup_seeds_interface_preferred_name_from_alias(
    hass: HomeAssistant,
) -> None:
    """Test interface preferred names are initially seeded from FortiOS aliases."""
    from custom_components.fortios_kd.const import (  # noqa: PLC0415
        CONF_INTERFACE_PREFERRED_NAMES,
        DATA_FILTER_MANAGER,
    )
    from custom_components.fortios_kd.text import async_setup_entry  # noqa: PLC0415

    entry = MockConfigEntry(domain=DOMAIN, data={"host": "fortigate.example"})
    entry.add_to_hass(hass)
    coordinator = Mock()
    coordinator.interface_keys = {("root", "wan1")}
    coordinator.sync_interfaces = True
    coordinator.get_interface.return_value = {
        "name": "wan1",
        "alias": "Primary uplink",
    }
    coordinator.async_add_listener.return_value = Mock()
    hass.data[DOMAIN] = {
        DATA_FILTER_MANAGER: Mock(),
        entry.entry_id: {
            "status": {"serial": "FGT123"},
            "coordinator": coordinator,
            "fortigate_default_preferred_name": "FortiGate80E",
            "fortigate_preferred_name": "FortiGate80E",
        },
    }
    entities: list[object] = []

    await async_setup_entry(hass, entry, entities.extend)

    assert len(entities) == 2
    assert entities[1].native_value == "Primary uplink"
    assert entry.data[CONF_INTERFACE_PREFERRED_NAMES]["root::wan1"] == {
        "preferred_name": "Primary uplink",
        "source_alias": "Primary uplink",
    }
