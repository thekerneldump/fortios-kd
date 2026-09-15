"""FortiOS version-specific compatibility dispatch."""

from typing import Any

from custom_components.fortios_kd.api.configuration import FortiOSConfigurationApi
from custom_components.fortios_kd.api.context import FortiOSApiContext
from custom_components.fortios_kd.api.monitor import FortiOSMonitorApi

from .v6_2 import async_enrich_system_status as async_enrich_v6_2_system_status


async def async_enrich_system_status(
    status: dict[str, Any],
    context: FortiOSApiContext,
    configuration: FortiOSConfigurationApi,
    monitor: FortiOSMonitorApi,
) -> dict[str, Any]:
    """Apply compatibility behavior for the detected FortiOS version."""
    if context.matches_version("6.2"):
        return await async_enrich_v6_2_system_status(
            status,
            configuration,
            monitor,
        )

    return status
