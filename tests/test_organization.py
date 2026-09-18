"""Tests for FortiOS KD hub organization."""

from types import SimpleNamespace
from unittest.mock import Mock

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
            "clients_follow_ap_labels": True,
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
        },
        async_add_listener=Mock(return_value=Mock()),
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

    label_registry = lr.async_get(hass)
    ap_label = label_registry.async_create("Upstairs")
    replacement_label = label_registry.async_create("Downstairs")
    client_only_label = label_registry.async_create("Client only")
    registry.async_update_device(
        client.id,
        labels={client_only_label.label_id},
    )
    registry.async_update_device(ap.id, labels={ap_label.label_id})
    await hass.async_block_till_done()
    assert registry.async_get(client.id).labels == {
        ap_label.label_id,
        client_only_label.label_id,
    }

    registry.async_update_device(ap.id, labels={replacement_label.label_id})
    await hass.async_block_till_done()
    assert registry.async_get(client.id).labels == {
        replacement_label.label_id,
        client_only_label.label_id,
    }

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


async def test_existing_label_is_applied_to_every_device(
    hass: HomeAssistant,
) -> None:
    """Test selected-label reuse and device assignment."""
    from custom_components.fortios_kd.organization import (  # noqa: PLC0415
        FortiOSKDOrganizationManager,
    )

    label_registry = lr.async_get(hass)
    label = label_registry.async_create("Example Place", color="#ABCDEF")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "organization_mode": "label",
            "hub_label_id": label.label_id,
            "hub_label_color": [18, 52, 86],
            "clients_follow_ap_area": True,
        },
    )
    entry.add_to_hass(hass)
    office = ar.async_get(hass).async_create("Office")
    coordinator = SimpleNamespace(
        data={"wifi_clients": {"results": [{"mac": CLIENT_MAC, "wtp_id": AP_SERIAL}]}},
        async_add_listener=Mock(return_value=Mock()),
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

    assert label_registry.async_get_label(label.label_id).color == "#ABCDEF"
    assert label.label_id in registry.async_get(hub.id).labels
    assert label.label_id in registry.async_get(ap.id).labels
    assert label.label_id in registry.async_get(client.id).labels
    assert registry.async_get(client.id).area_id == office.id

    hub_only_label = label_registry.async_create("Hub only")
    registry.async_update_device(
        hub.id,
        labels=registry.async_get(hub.id).labels | {hub_only_label.label_id},
    )
    await hass.async_block_till_done()
    assert hub_only_label.label_id not in registry.async_get(ap.id).labels
    assert hub_only_label.label_id not in registry.async_get(client.id).labels


async def test_hub_label_changes_propagate_when_enabled(
    hass: HomeAssistant,
) -> None:
    """Test opt-in FortiGate label propagation to APs and clients."""
    from custom_components.fortios_kd.organization import (  # noqa: PLC0415
        FortiOSKDOrganizationManager,
    )

    label_registry = lr.async_get(hass)
    base_label = label_registry.async_create("Example Place")
    inherited_label = label_registry.async_create("Inherited")
    ap_only_label = label_registry.async_create("AP only")
    client_only_label = label_registry.async_create("Client only")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "organization_mode": "label",
            "hub_label_id": base_label.label_id,
            "devices_follow_hub_labels": True,
        },
    )
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(
        data={"wifi_clients": {"results": [{"mac": CLIENT_MAC, "wtp_id": AP_SERIAL}]}},
        async_add_listener=Mock(return_value=Mock()),
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

    registry.async_update_device(
        ap.id,
        labels=registry.async_get(ap.id).labels | {ap_only_label.label_id},
    )
    registry.async_update_device(
        client.id,
        labels=registry.async_get(client.id).labels | {client_only_label.label_id},
    )
    registry.async_update_device(
        hub.id,
        labels=registry.async_get(hub.id).labels | {inherited_label.label_id},
    )
    await hass.async_block_till_done()

    assert registry.async_get(ap.id).labels == {
        base_label.label_id,
        inherited_label.label_id,
        ap_only_label.label_id,
    }
    assert registry.async_get(client.id).labels == {
        base_label.label_id,
        inherited_label.label_id,
        client_only_label.label_id,
    }

    registry.async_update_device(
        hub.id,
        labels={base_label.label_id},
    )
    await hass.async_block_till_done()

    assert registry.async_get(ap.id).labels == {
        base_label.label_id,
        ap_only_label.label_id,
    }
    assert registry.async_get(client.id).labels == {
        base_label.label_id,
        client_only_label.label_id,
    }
