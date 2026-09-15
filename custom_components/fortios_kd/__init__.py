"""The FortiOS-KD integration."""

import json
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

from .api import FortiOSApi
from .const import (
    CONF_INCLUDE_UNASSIGNED_SSIDS,
    CONF_MASK_AP_NAMES,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    DATA_FILTER_MANAGER,
    DEFAULT_INCLUDE_UNASSIGNED_SSIDS,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DOMAIN,
)
from .coordinator import FortiOSKDCoordinator
from .filter_manager import FortiOSKDFilterManager
from .privacy import mask_name

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to the FortiGate."""
    client = FortiOSApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
        entry.data[CONF_VERIFY_SSL],
    )

    try:
        status = await client.async_initialize()

        _LOGGER.info(
            "FortiGate response:\n%s",
            json.dumps(status, indent=2),
        )

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
    manager = domain_data.setdefault(DATA_FILTER_MANAGER, FortiOSKDFilterManager())
    domain_data[entry.entry_id] = {
        "client": client,
        "status": status,
        "coordinator": coordinator,
    }

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
            domain_data.pop(DATA_FILTER_MANAGER)

    return unloaded
