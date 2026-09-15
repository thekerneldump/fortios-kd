"""FortiOS Monitor API modules."""

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext

from .system import FortiOSSystemApi
from .wifi import FortiOSWifiApi


class FortiOSMonitorApi:
    """Group FortiOS Monitor APIs by function."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the Monitor API groups."""
        self.system = FortiOSSystemApi(http, context)
        self.wifi = FortiOSWifiApi(http, context)
