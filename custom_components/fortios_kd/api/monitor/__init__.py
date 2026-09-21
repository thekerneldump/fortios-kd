"""FortiOS Monitor API modules."""

from custom_components.fortios_kd.api.client import FortiOSHttpClient
from custom_components.fortios_kd.api.context import FortiOSApiContext

from .network import FortiOSNetworkApi
from .system import FortiOSSystemApi
from .user import FortiOSUserApi
from .wifi import FortiOSWifiApi


class FortiOSMonitorApi:
    """Group FortiOS Monitor APIs by function."""

    def __init__(
        self,
        http: FortiOSHttpClient,
        context: FortiOSApiContext,
    ) -> None:
        """Initialize the Monitor API groups."""
        self.network = FortiOSNetworkApi(http, context)
        self.system = FortiOSSystemApi(http, context)
        self.user = FortiOSUserApi(http, context)
        self.wifi = FortiOSWifiApi(http, context)
