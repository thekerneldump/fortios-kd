"""Diagnostics support for FortiOS KD."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .debug import FortiOSDebugCaptureStore


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return bounded malformed-response captures for a config entry."""
    integration_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    capture_store = integration_data.get("debug_capture_store")
    if not isinstance(capture_store, FortiOSDebugCaptureStore):
        return {
            "capture_enabled": False,
            "capture_count": 0,
            "captures": [],
        }
    return capture_store.diagnostics()
