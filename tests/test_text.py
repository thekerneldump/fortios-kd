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
