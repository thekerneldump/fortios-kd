"""The FortiOS-KD integration."""

import logging

from aiohttp import ClientError
import aiooui

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FortiOSApi
from .const import (
    CONF_DEBUG_RESPONSE_CAPTURE,
    CONF_DEBUG_RESPONSE_CAPTURE_LIMIT,
    CONF_DEBUG_RESPONSE_CAPTURE_MODE,
    CONF_INCLUDE_UNASSIGNED_SSIDS,
    CONF_MASK_AP_NAMES,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    CONF_MATCH_ARP_WIFI_CLIENTS,
    CONF_PREFERRED_NAME,
    CONF_REQUEST_TIMEOUT,
    CONF_SNMP_COMMUNITY,
    CONF_SNMP_PORT,
    CONF_SYNC_ARP_TABLE,
    CONF_SYNC_DEVICE_INVENTORY,
    CONF_SYNC_DHCP_LEASES,
    CONF_SYNC_INTERFACES,
    DATA_FILTER_MANAGER,
    DEFAULT_DEBUG_RESPONSE_CAPTURE,
    DEFAULT_DEBUG_RESPONSE_CAPTURE_LIMIT,
    DEFAULT_DEBUG_RESPONSE_CAPTURE_MODE,
    DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DEFAULT_MATCH_ARP_WIFI_CLIENTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SNMP_PORT,
    DEFAULT_SNMP_TIMEOUT,
    DEFAULT_SYNC_ARP_TABLE,
    DEFAULT_SYNC_DEVICE_INVENTORY,
    DEFAULT_SYNC_DHCP_LEASES,
    DEFAULT_SYNC_INTERFACES,
    DOMAIN,
)
from .coordinator import FortiOSKDCoordinator
from .debug import FortiOSDebugCaptureStore
from .filter_manager import FortiOSKDFilterManager
from .frontend import async_register_dashboard_strategy
from .organization import FortiOSKDOrganizationManager
from .privacy import mask_name, mask_serial
from .repairs import async_delete_snmp_arp_issue
from .snmp_arp import FortiOSKDSnmpArpClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
]

_DETECTED_DEVICE_VERBOSE_FIELD_SUFFIXES = (
    "_mac_address",
    "_master_mac_address",
    "_hostname",
    "_hostname_source",
    "_ipv4_address",
    "_ipv6_address",
    "_interface",
    "_operating_system",
    "_operating_system_source",
    "_hardware_vendor",
    "_hardware_vendor_source",
    "_oui_vendor",
    "_vendor_identification_assessment",
    "_hardware_type",
    "_hardware_type_source",
    "_hardware_family",
    "_hardware_family_source",
    "_hardware_version",
    "_hardware_version_source",
    "_software_version",
    "_software_version_source",
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide frontend resources."""
    if not aiooui.is_loaded():
        await aiooui.async_load()
    await async_register_dashboard_strategy(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate compact detected-device entities without overriding user choices."""
    if entry.version == 1 and entry.minor_version < 2:
        entity_registry = er.async_get(hass)
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry,
            entry.entry_id,
        ):
            if (
                registry_entry.domain == Platform.SENSOR
                and registry_entry.platform == DOMAIN
                and "_detected_device_" in registry_entry.unique_id
                and registry_entry.unique_id.endswith(
                    _DETECTED_DEVICE_VERBOSE_FIELD_SUFFIXES
                )
                and registry_entry.disabled_by is None
            ):
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to the FortiGate."""
    debug_capture_store = FortiOSDebugCaptureStore(
        enabled=bool(
            entry.data.get(
                CONF_DEBUG_RESPONSE_CAPTURE,
                DEFAULT_DEBUG_RESPONSE_CAPTURE,
            )
        ),
        mode=str(
            entry.data.get(
                CONF_DEBUG_RESPONSE_CAPTURE_MODE,
                DEFAULT_DEBUG_RESPONSE_CAPTURE_MODE,
            )
        ),
        limit=int(
            entry.data.get(
                CONF_DEBUG_RESPONSE_CAPTURE_LIMIT,
                DEFAULT_DEBUG_RESPONSE_CAPTURE_LIMIT,
            )
        ),
    )
    client = FortiOSApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        entry.data[CONF_VERIFY_SSL],
        entry.data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
        debug_capture_store,
    )

    try:
        status = await client.async_initialize()

    except (ClientError, TimeoutError) as err:
        _LOGGER.exception("FortiGate request failed")
        raise ConfigEntryNotReady(f"Cannot connect to FortiGate: {err}") from err

    include_unassigned_ssids = entry.data.get(
        CONF_INCLUDE_UNASSIGNED_SSIDS,
        DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    )
    sync_arp_table = entry.data.get(CONF_SYNC_ARP_TABLE, DEFAULT_SYNC_ARP_TABLE)
    match_arp_wifi_clients = entry.data.get(
        CONF_MATCH_ARP_WIFI_CLIENTS,
        DEFAULT_MATCH_ARP_WIFI_CLIENTS,
    )
    sync_dhcp_leases = entry.data.get(
        CONF_SYNC_DHCP_LEASES,
        DEFAULT_SYNC_DHCP_LEASES,
    )
    sync_device_inventory = entry.data.get(
        CONF_SYNC_DEVICE_INVENTORY,
        DEFAULT_SYNC_DEVICE_INVENTORY,
    )
    sync_interfaces = entry.data.get(
        CONF_SYNC_INTERFACES,
        DEFAULT_SYNC_INTERFACES,
    )
    snmp_arp_client = None
    if sync_arp_table:
        community = entry.data.get(CONF_SNMP_COMMUNITY)
        if isinstance(community, str) and community:
            snmp_arp_client = FortiOSKDSnmpArpClient(
                hass,
                entry.data[CONF_HOST],
                community,
                int(entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)),
                DEFAULT_SNMP_TIMEOUT,
            )
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        config_entry_id=entry.entry_id,
        include_unassigned_ssids=include_unassigned_ssids,
        sync_arp_table=sync_arp_table,
        match_arp_wifi_clients=match_arp_wifi_clients,
        sync_dhcp_leases=sync_dhcp_leases,
        sync_device_inventory=sync_device_inventory,
        sync_interfaces=sync_interfaces,
        snmp_arp_client=snmp_arp_client,
    )
    await coordinator.async_config_entry_first_refresh()

    domain_data = hass.data.setdefault(DOMAIN, {})
    if not isinstance(
        manager := domain_data.get(DATA_FILTER_MANAGER),
        FortiOSKDFilterManager,
    ):
        manager = FortiOSKDFilterManager(hass)
        domain_data[DATA_FILTER_MANAGER] = manager
    organization_manager = FortiOSKDOrganizationManager(
        hass,
        entry,
        coordinator,
        str(status.get("serial") or entry.unique_id or entry.entry_id),
    )
    fortigate_hostname = status.get("results", {}).get("hostname") or entry.title
    mask_serial_numbers = entry.data.get(
        CONF_MASK_SERIAL_NUMBERS,
        DEFAULT_MASK_SERIAL_NUMBERS,
    )
    fortigate_serial = str(status["serial"])
    debug_capture_store.set_fortigate_serial(fortigate_serial)
    displayed_fortigate_hostname = (
        mask_name(fortigate_hostname) if mask_serial_numbers else fortigate_hostname
    )
    fortigate_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, fortigate_serial)},
        name=displayed_fortigate_hostname,
        manufacturer="Fortinet",
        model=status["results"].get("model"),
        serial_number=mask_serial(fortigate_serial)
        if mask_serial_numbers
        else fortigate_serial,
        sw_version=status["version"],
    )
    default_preferred_name = (
        fortigate_device.name_by_user
        or fortigate_device.name
        or displayed_fortigate_hostname
    )
    stored_preferred_name = entry.data.get(CONF_PREFERRED_NAME)
    preferred_name = (
        stored_preferred_name.strip()
        if isinstance(stored_preferred_name, str) and stored_preferred_name.strip()
        else default_preferred_name
    )
    domain_data[entry.entry_id] = {
        "client": client,
        "status": status,
        "coordinator": coordinator,
        "fortigate_device_id": fortigate_device.id,
        "fortigate_display_name": displayed_fortigate_hostname,
        "fortigate_default_preferred_name": default_preferred_name,
        "fortigate_preferred_name": preferred_name,
        "organization_manager": organization_manager,
        "debug_capture_store": debug_capture_store,
    }
    organization_manager.setup()

    manager.register_hub(
        entry.entry_id,
        preferred_name,
        coordinator,
        mask_ap_names=entry.data.get(CONF_MASK_AP_NAMES, DEFAULT_MASK_AP_NAMES),
        mask_ssids=entry.data.get(CONF_MASK_SSIDS, DEFAULT_MASK_SSIDS),
        include_unassigned_ssids=include_unassigned_ssids,
    )

    _LOGGER.info("FortiGate version: %s", status["version"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a FortiGate and transfer shared filter ownership if needed."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        async_delete_snmp_arp_issue(hass, entry.entry_id)
        domain_data = hass.data[DOMAIN]
        manager: FortiOSKDFilterManager = domain_data[DATA_FILTER_MANAGER]
        manager.unregister_hub(entry.entry_id)
        next_owner = manager.release_owner(entry.entry_id)
        domain_data.pop(entry.entry_id)

        if next_owner is not None:
            hass.config_entries.async_schedule_reload(next_owner)
        elif not manager.has_hubs:
            manager.shutdown()
            domain_data.pop(DATA_FILTER_MANAGER)

    return unloaded
