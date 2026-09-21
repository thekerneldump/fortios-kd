"""Tests for FortiOS KD dashboard filter switches."""

from typing import Any

from tests.common import MockConfigEntry  # noqa: TID251


async def test_interface_graph_filter_switches(hass: Any) -> None:
    """Test independent interface exclusions default to enabled."""
    from custom_components.fortios_kd.const import (  # noqa: PLC0415
        DATA_FILTER_MANAGER,
        DOMAIN,
    )
    from custom_components.fortios_kd.filter_manager import (  # noqa: PLC0415
        FortiOSKDFilterManager,
    )
    from custom_components.fortios_kd.switch import async_setup_entry  # noqa: PLC0415

    entry = MockConfigEntry(domain=DOMAIN, entry_id="entry-a")
    manager = FortiOSKDFilterManager(hass)
    hass.data[DOMAIN] = {DATA_FILTER_MANAGER: manager}
    entities: list[Any] = []

    await async_setup_entry(hass, entry, entities.extend)

    assert len(entities) == 2
    hardware_members, wifi_ssids = entities
    assert hardware_members.is_on
    assert wifi_ssids.is_on

    await hardware_members.async_turn_off()
    await wifi_ssids.async_turn_off()
    assert not manager.hide_interface_hardware_switch_members
    assert not manager.hide_interface_wifi_ssid_interfaces

    await hardware_members.async_turn_on()
    await wifi_ssids.async_turn_on()
    assert manager.hide_interface_hardware_switch_members
    assert manager.hide_interface_wifi_ssid_interfaces

    duplicate_entities: list[Any] = []
    await async_setup_entry(
        hass,
        MockConfigEntry(domain=DOMAIN, entry_id="entry-b"),
        duplicate_entities.extend,
    )
    assert duplicate_entities == []
