"""FortiOS Configuration API modules."""

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext

from .system import FortiOSSystemConfigurationApi
from .wifi import FortiOSWifiConfigurationApi


class FortiOSConfigurationApi:
    """Group FortiOS Configuration APIs by function."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the Configuration API groups."""
        self.system = FortiOSSystemConfigurationApi(http, context)
        self.wifi = FortiOSWifiConfigurationApi(http, context)
