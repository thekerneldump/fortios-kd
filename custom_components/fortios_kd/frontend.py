"""Frontend resources for FortiOS KD."""

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

FRONTEND_ASSETS = {
    "/fortios_kd/fortios-kd-dashboard.js": (
        Path(__file__).parent / "frontend" / "fortios-kd-dashboard.js"
    ),
    "/fortios_kd/fortios-kd-wifi-graphs-dashboard.js": (
        Path(__file__).parent / "frontend" / "fortios-kd-wifi-graphs-dashboard.js"
    ),
}
FRONTEND_URL, FRONTEND_PATH = next(iter(FRONTEND_ASSETS.items()))
FRONTEND_MODULE_URL = f"{FRONTEND_URL}?v={FRONTEND_PATH.stat().st_mtime_ns}"
FRONTEND_MODULE_URLS = tuple(
    f"{url}?v={path.stat().st_mtime_ns}" for url, path in FRONTEND_ASSETS.items()
)


async def async_register_dashboard_strategy(hass: HomeAssistant) -> None:
    """Serve and load the FortiOS KD community dashboard strategy."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(url, str(path), cache_headers=False)
            for url, path in FRONTEND_ASSETS.items()
        ]
    )
    for module_url in FRONTEND_MODULE_URLS:
        add_extra_js_url(hass, module_url)
