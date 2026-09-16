"""The FortiOS-KD integration."""

import logging

from aiohttp import ClientError

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FortiOSApi
from .const import (
    CONF_INCLUDE_UNASSIGNED_SSIDS,
    CONF_MASK_AP_NAMES,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    CONF_REQUEST_TIMEOUT,
    DATA_FILTER_MANAGER,
    DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DEFAULT_REQUEST_TIMEOUT,
    DOMAIN,
)
from .coordinator import FortiOSKDCoordinator
from .filter_manager import FortiOSKDFilterManager
from .frontend import async_register_dashboard_strategy
from .organization import FortiOSKDOrganizationManager
from .privacy import mask_name

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.SELECT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide frontend resources."""
    await async_register_dashboard_strategy(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to the FortiGate."""
    client = FortiOSApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        entry.data[CONF_VERIFY_SSL],
        entry.data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
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
    coordinator = FortiOSKDCoordinator(
        hass,
        client,
        include_unassigned_ssids=include_unassigned_ssids,
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
    domain_data[entry.entry_id] = {
        "client": client,
        "status": status,
        "coordinator": coordinator,
        "organization_manager": organization_manager,
    }
    organization_manager.setup()

    fortigate_hostname = status.get("results", {}).get("hostname") or entry.title
    displayed_fortigate_hostname = (
        mask_name(fortigate_hostname)
        if entry.data.get(CONF_MASK_SERIAL_NUMBERS, DEFAULT_MASK_SERIAL_NUMBERS)
        else fortigate_hostname
    )
    manager.register_hub(
        entry.entry_id,
        displayed_fortigate_hostname,
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
