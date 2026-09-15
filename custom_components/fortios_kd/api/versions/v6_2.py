"""FortiOS 6.2 response compatibility."""

from typing import Any

from custom_components.fortios_kd.api.configuration import FortiOSConfigurationApi
from custom_components.fortios_kd.api.monitor import FortiOSMonitorApi


async def async_enrich_system_status(
    status: dict[str, Any],
    configuration: FortiOSConfigurationApi,
    monitor: FortiOSMonitorApi,
) -> dict[str, Any]:
    """Add system fields missing from the FortiOS 6.2 status response."""
    global_config = await configuration.system.get_global()
    firmware = await monitor.system.get_firmware()

    hostname = global_config.get("results", {}).get("hostname")
    model = firmware.get("results", {}).get("current", {}).get("platform-id")
    status_results = status.setdefault("results", {})

    if isinstance(hostname, str):
        status_results["hostname"] = hostname

    if isinstance(model, str):
        status_results["model"] = model

    return status
