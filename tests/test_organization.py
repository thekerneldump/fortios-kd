"""Tests for FortiOS KD hub organization."""

from types import SimpleNamespace

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    label_registry as lr,
)
from tests.common import MockConfigEntry  # noqa: TID251

DOMAIN = "fortios_kd"
FORTIGATE_SERIAL = "FGT123"
AP_SERIAL = "FAP123"
CLIENT_MAC = "aa:bb:cc:dd:ee:ff"
CLIENT_IDENTIFIER = f"{FORTIGATE_SERIAL}_wifi_client_{CLIENT_MAC}"


async def test_area_moves_preserve_manual_device_areas(
    hass: HomeAssistant,
) -> None:
    """Test hub/AP propagation while preserving manual device placement."""
    from custom_components.fortios_kd.organization import (  # noqa: PLC0415
        FortiOSKDOrganizationManager,
    )

    area_registry = ar.async_get(hass)
    home = area_registry.async_create("Home")
    office = area_registry.async_create("Office")
    manual = area_registry.async_create("Manual")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "organization_mode": "area",
            "hub_area_id": home.id,
            "inherit_hub_area": True,
            "move_devices_if_hub_moves": True,
            "clients_follow_ap_area": True,
        },
    )
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(
        data={
            "wifi_clients": {
                "results": [
                    {
                        "mac": CLIENT_MAC,
                        "wtp_id": AP_SERIAL,
                    }
                ]
            }
        }
    )
    manager = FortiOSKDOrganizationManager(
        hass,
        entry,
        coordinator,
        FORTIGATE_SERIAL,
    )
    manager.setup()
    registry = dr.async_get(hass)
    hub = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, FORTIGATE_SERIAL)},
    )
    ap = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, AP_SERIAL)},
        via_device_id=hub.id,
    )
    client = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CLIENT_IDENTIFIER)},
        via_device_id=hub.id,
    )
    await hass.async_block_till_done()

    assert registry.async_get(hub.id).area_id == home.id
    assert registry.async_get(ap.id).area_id == home.id
    assert registry.async_get(client.id).area_id == home.id

    registry.async_update_device(ap.id, area_id=office.id)
    await hass.async_block_till_done()
    assert registry.async_get(client.id).area_id == office.id

    registry.async_update_device(client.id, area_id=manual.id)
    registry.async_update_device(ap.id, area_id=home.id)
    await hass.async_block_till_done()
    assert registry.async_get(client.id).area_id == manual.id

    registry.async_update_device(hub.id, area_id=office.id)
    await hass.async_block_till_done()
    assert registry.async_get(ap.id).area_id == office.id
    assert registry.async_get(client.id).area_id == manual.id
    assert entry.data["hub_area_id"] == office.id


async def test_label_is_created_and_applied_to_every_device(
    hass: HomeAssistant,
) -> None:
    """Test label creation, color conversion, and device assignment."""
    from custom_components.fortios_kd.organization import (  # noqa: PLC0415
        FortiOSKDOrganizationManager,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "organization_mode": "label",
            "hub_label": "Other House",
            "hub_label_color": [18, 52, 86],
            "clients_follow_ap_area": True,
        },
    )
    entry.add_to_hass(hass)
    office = ar.async_get(hass).async_create("Office")
    coordinator = SimpleNamespace(
        data={"wifi_clients": {"results": [{"mac": CLIENT_MAC, "wtp_id": AP_SERIAL}]}}
    )
    manager = FortiOSKDOrganizationManager(
        hass,
        entry,
        coordinator,
        FORTIGATE_SERIAL,
    )
    manager.setup()
    registry = dr.async_get(hass)
    hub = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, FORTIGATE_SERIAL)},
    )
    ap = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, AP_SERIAL)},
        via_device_id=hub.id,
    )
    registry.async_update_device(ap.id, area_id=office.id)
    client = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CLIENT_IDENTIFIER)},
        via_device_id=hub.id,
    )
    await hass.async_block_till_done()

    label = lr.async_get(hass).async_get_label_by_name("Other House")
    assert label is not None
    assert label.color == "#123456"
    assert label.label_id in registry.async_get(hub.id).labels
    assert label.label_id in registry.async_get(ap.id).labels
    assert label.label_id in registry.async_get(client.id).labels
    assert registry.async_get(client.id).area_id == office.id
