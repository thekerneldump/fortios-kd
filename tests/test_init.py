"""Tests for FortiOS KD config-entry migrations."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from tests.common import MockConfigEntry  # noqa: TID251

DOMAIN = "fortios_kd"


async def test_migrate_compacts_detected_device_field_entities(
    hass: HomeAssistant,
) -> None:
    """Test verbose inventory fields are disabled once without overriding users."""
    from custom_components.fortios_kd import async_migrate_entry  # noqa: PLC0415

    entry = MockConfigEntry(domain=DOMAIN, minor_version=1)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    verbose_entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "FGT123_detected_device_aa:bb:cc:dd:ee:ff_hardware_vendor",
        config_entry=entry,
    )
    user_disabled_entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "FGT123_detected_device_aa:bb:cc:dd:ee:ff_software_version",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    details_entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "FGT123_detected_device_aa:bb:cc:dd:ee:ff_details",
        config_entry=entry,
    )

    assert await async_migrate_entry(hass, entry)

    assert entry.minor_version == 2
    assert registry.async_get(verbose_entry.entity_id).disabled_by is (
        er.RegistryEntryDisabler.INTEGRATION
    )
    assert registry.async_get(user_disabled_entry.entity_id).disabled_by is (
        er.RegistryEntryDisabler.USER
    )
    assert registry.async_get(details_entry.entity_id).disabled_by is None
