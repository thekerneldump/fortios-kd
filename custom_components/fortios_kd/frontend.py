"""Frontend resources for FortiOS KD."""

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

FRONTEND_URL = "/fortios_kd/fortios-kd-dashboard.js"
FRONTEND_PATH = Path(__file__).parent / "frontend" / "fortios-kd-dashboard.js"
FRONTEND_MODULE_URL = f"{FRONTEND_URL}?v={FRONTEND_PATH.stat().st_mtime_ns}"


async def async_register_dashboard_strategy(hass: HomeAssistant) -> None:
    """Serve and load the FortiOS KD community dashboard strategy."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(FRONTEND_PATH), cache_headers=False)]
    )
    add_extra_js_url(hass, FRONTEND_MODULE_URL)
