"""Frontend resources for FortiOS KD."""

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

FRONTEND_URL = "/fortios_kd/fortios-kd-dashboard.js"
FRONTEND_PATH = Path(__file__).parent / "frontend" / "fortios-kd-dashboard.js"
FRONTEND_GRAPH_URL = "/fortios_kd/fortios-kd-wifi-graphs-dashboard.js"
FRONTEND_GRAPH_PATH = (
    Path(__file__).parent / "frontend" / "fortios-kd-wifi-graphs-dashboard.js"
)
FRONTEND_ARP_URL = "/fortios_kd/fortios-kd-arp-dashboard.js"
FRONTEND_ARP_PATH = Path(__file__).parent / "frontend" / "fortios-kd-arp-dashboard.js"
FRONTEND_ARP_TABLE_URL = "/fortios_kd/fortios-kd-arp-table-dashboard.js"
FRONTEND_ARP_TABLE_PATH = (
    Path(__file__).parent / "frontend" / "fortios-kd-arp-table-dashboard.js"
)
FRONTEND_DHCP_URL = "/fortios_kd/fortios-kd-dhcp-dashboard.js"
FRONTEND_DHCP_PATH = Path(__file__).parent / "frontend" / "fortios-kd-dhcp-dashboard.js"
FRONTEND_VDOM_RESOURCES_URL = "/fortios_kd/fortios-kd-vdom-resources-dashboard.js"
FRONTEND_VDOM_RESOURCES_PATH = (
    Path(__file__).parent / "frontend" / "fortios-kd-vdom-resources-dashboard.js"
)
FRONTEND_PREFERRED_NAMES_URL = "/fortios_kd/fortios-kd-preferred-names.js"
FRONTEND_PREFERRED_NAMES_PATH = (
    Path(__file__).parent / "frontend" / "fortios-kd-preferred-names.js"
)
FRONTEND_LOADER_URL = "/fortios_kd/fortios-kd-dashboard-loader.js"
FRONTEND_LOADER_PATH = (
    Path(__file__).parent / "frontend" / "fortios-kd-dashboard-loader.js"
)
FRONTEND_ASSETS = {
    FRONTEND_URL: FRONTEND_PATH,
    FRONTEND_GRAPH_URL: FRONTEND_GRAPH_PATH,
    FRONTEND_ARP_URL: FRONTEND_ARP_PATH,
    FRONTEND_ARP_TABLE_URL: FRONTEND_ARP_TABLE_PATH,
    FRONTEND_DHCP_URL: FRONTEND_DHCP_PATH,
    FRONTEND_VDOM_RESOURCES_URL: FRONTEND_VDOM_RESOURCES_PATH,
    FRONTEND_PREFERRED_NAMES_URL: FRONTEND_PREFERRED_NAMES_PATH,
    FRONTEND_LOADER_URL: FRONTEND_LOADER_PATH,
}
FRONTEND_VERSION = max(path.stat().st_mtime_ns for path in FRONTEND_ASSETS.values())
FRONTEND_MODULE_URL = f"{FRONTEND_LOADER_URL}?v={FRONTEND_VERSION}"
FRONTEND_MODULE_URLS = (FRONTEND_MODULE_URL,)


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
