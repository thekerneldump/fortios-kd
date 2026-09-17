"""Coordinate FortiGate API updates."""

from datetime import timedelta
import logging
from time import monotonic
from typing import Any

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FortiOSApi
from .const import RADIO_SPECTRUM_BANDS, RADIO_TYPE_BANDS

_LOGGER = logging.getLogger(__name__)


def normalize_mac_address(value: Any) -> str | None:
    """Return a lowercase colon-delimited MAC address when valid."""
    if not isinstance(value, str):
        return None

    compact = value.strip().casefold().replace(":", "").replace("-", "")
    compact = compact.replace(".", "")
    if len(compact) != 12 or compact in {"0" * 12, "f" * 12}:
        return None

    try:
        int(compact, 16)
    except ValueError:
        return None

    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


class FortiOSKDCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll FortiGate and distribute the latest AP data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FortiOSApi,
        *,
        include_unassigned_ssids: bool = False,
        sync_arp_table: bool = False,
        match_arp_wifi_clients: bool = True,
    ) -> None:
        """Initialize the FortiGate coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="FortiOS-KD access points",
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self.client = client
        self.include_unassigned_ssids = include_unassigned_ssids
        self.sync_arp_table = sync_arp_table
        self.match_arp_wifi_clients = match_arp_wifi_clients
        self._radio_counters: dict[tuple[str, int, str], tuple[int, float]] = {}
        self._wifi_clients_by_mac: dict[str, dict[str, Any]] = {}
        self._wifi_clients_by_ip: dict[str, list[dict[str, Any]]] = {}
        self._arp_entries_by_mac: dict[str, list[dict[str, Any]]] = {}
        self._arp_entries_by_ip: dict[str, list[dict[str, Any]]] = {}
        self._arp_supported = bool(sync_arp_table and client.supports_network_arp)
        self._arp_table: dict[str, Any] = {
            "results": [],
            "supported": self._arp_supported,
        }
        self._arp_error_logged = False
        self._wifi_meta_loaded = False
        self.wifi_meta: dict[str, Any] = {}
        self.radio_type_bands = RADIO_TYPE_BANDS.copy()
        self._ap_names_loaded = False
        self._ap_models_by_prefix: dict[str, dict[str, str]] = {}
        self._ap_channel_capabilities: dict[str, dict[str, Any]] = {}
        self._ap_channel_capabilities_attempted: set[str] = set()

    def get_wifi_client(self, mac: str) -> dict[str, Any] | None:
        """Return a wifi client by MAC address without scanning every client."""
        normalized_mac = normalize_mac_address(mac)
        return (
            self._wifi_clients_by_mac.get(normalized_mac)
            if normalized_mac is not None
            else None
        )

    def get_arp_entries(self, mac: str) -> list[dict[str, Any]]:
        """Return every current ARP binding for a MAC address."""
        normalized_mac = normalize_mac_address(mac)
        if normalized_mac is None:
            return []
        return self._arp_entries_by_mac.get(normalized_mac, [])

    def get_wifi_clients_by_ip(self, ip_address: str) -> list[dict[str, Any]]:
        """Return current wifi clients claiming an IP address."""
        return self._wifi_clients_by_ip.get(ip_address, [])

    def get_arp_entries_by_ip(self, ip_address: str) -> list[dict[str, Any]]:
        """Return current ARP bindings claiming an IP address."""
        return self._arp_entries_by_ip.get(ip_address, [])

    @property
    def arp_macs(self) -> set[str]:
        """Return MAC addresses currently present in the ARP table."""
        return set(self._arp_entries_by_mac)

    async def _async_get_arp_table(self) -> dict[str, Any]:
        """Return the ARP table, retaining the last table after request errors."""
        if not self._arp_supported:
            return self._arp_table

        try:
            response = await self.client.monitor.network.get_arp_table()
        except (ClientError, TimeoutError) as err:
            if not self._arp_error_logged:
                _LOGGER.warning("Unable to load the FortiGate ARP table: %s", err)
                self._arp_error_logged = True
            return self._arp_table

        results = response.get("results")
        if not isinstance(results, list):
            if not self._arp_error_logged:
                _LOGGER.warning("FortiGate ARP table response has no results list")
                self._arp_error_logged = True
            return self._arp_table

        self._arp_error_logged = False
        self._arp_table = {**response, "results": results, "supported": True}
        return self._arp_table

    def _index_arp_entries(self, arp_table: dict[str, Any]) -> None:
        """Index valid ARP entries by canonical MAC address."""
        entries_by_mac: dict[str, list[dict[str, Any]]] = {}
        entries_by_ip: dict[str, list[dict[str, Any]]] = {}
        response_vdom = arp_table.get("vdom")

        for entry in arp_table.get("results", []):
            if not isinstance(entry, dict):
                continue

            normalized_mac = normalize_mac_address(entry.get("mac"))
            ip_address = entry.get("ip")
            if normalized_mac is None or not isinstance(ip_address, str):
                continue

            normalized_entry = {**entry, "mac": normalized_mac}
            if "vdom" not in normalized_entry and isinstance(response_vdom, str):
                normalized_entry["vdom"] = response_vdom
            entries_by_mac.setdefault(normalized_mac, []).append(normalized_entry)
            entries_by_ip.setdefault(ip_address, []).append(normalized_entry)

        self._arp_entries_by_mac = entries_by_mac
        self._arp_entries_by_ip = entries_by_ip

    async def _async_load_wifi_meta(self) -> None:
        """Load FortiGate wifi lookup tables once, retaining safe fallbacks."""
        if self._wifi_meta_loaded:
            return

        self._wifi_meta_loaded = True

        try:
            response = await self.client.monitor.wifi.get_meta()
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning(
                "Unable to load FortiGate wifi metadata; using fallback radio "
                "band mapping: %s",
                err,
            )
            return

        results = response.get("results")
        if not isinstance(results, dict):
            _LOGGER.warning(
                "FortiGate wifi metadata response has no results object; using "
                "fallback radio band mapping"
            )
            return

        self.wifi_meta = results
        spectrum_map = results.get("band_spectrum_map")
        if not isinstance(spectrum_map, dict):
            _LOGGER.warning(
                "FortiGate wifi metadata has no band spectrum map; using fallback "
                "radio band mapping"
            )
            return

        fortigate_bands: dict[str, str] = {}
        for radio_type, spectrum in spectrum_map.items():
            if not isinstance(radio_type, str) or not isinstance(spectrum, str):
                continue

            if band := RADIO_SPECTRUM_BANDS.get(spectrum.casefold()):
                fortigate_bands[radio_type] = band

        if fortigate_bands:
            self.radio_type_bands = {**RADIO_TYPE_BANDS, **fortigate_bands}

    async def _async_load_ap_names(self) -> None:
        """Load the FortiGate-supported FortiAP model catalog once."""
        if self._ap_names_loaded:
            return

        self._ap_names_loaded = True

        try:
            response = await self.client.monitor.wifi.get_ap_names()
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning("Unable to load FortiAP model metadata: %s", err)
            return

        results = response.get("results")
        if not isinstance(results, list):
            _LOGGER.warning("FortiAP model metadata response has no results list")
            return

        for item in results:
            if not isinstance(item, dict):
                continue

            prefix = item.get("prefix")
            model = item.get("model")
            platform = item.get("platform")
            if not all(
                isinstance(value, str) and value for value in (prefix, model, platform)
            ):
                continue

            self._ap_models_by_prefix[prefix.casefold()] = {
                "model": model,
                "platform": platform,
            }

    def _ap_model_info(self, serial: str) -> dict[str, str] | None:
        """Return model metadata matching a FortiAP serial prefix."""
        folded_serial = serial.casefold()
        for prefix in sorted(self._ap_models_by_prefix, key=len, reverse=True):
            if folded_serial.startswith(prefix):
                return self._ap_models_by_prefix[prefix]
        return None

    def _annotate_access_points(self, data: dict[str, Any]) -> set[str]:
        """Attach model metadata and return installed platform types."""
        platforms: set[str] = set()

        for ap in data.get("results", []):
            if not isinstance(ap, dict):
                continue

            serial = ap.get("serial")
            if not isinstance(serial, str):
                continue

            if model_info := self._ap_model_info(serial):
                ap["fortios_kd_ap_model"] = model_info["model"]
                ap["fortios_kd_platform_type"] = model_info["platform"]
                platforms.add(model_info["platform"])

        return platforms

    async def _async_load_ap_channel_capabilities(
        self,
        platforms: set[str],
    ) -> None:
        """Load channel capabilities once for each installed AP platform."""
        for platform in sorted(platforms):
            if platform in self._ap_channel_capabilities_attempted:
                continue

            self._ap_channel_capabilities_attempted.add(platform)
            try:
                response = await self.client.monitor.wifi.get_ap_channels(platform)
            except (ClientError, TimeoutError) as err:
                _LOGGER.warning(
                    "Unable to load FortiAP %s channel capabilities: %s",
                    platform,
                    err,
                )
                continue

            results = response.get("results")
            if isinstance(results, dict):
                self._ap_channel_capabilities[platform] = results
            else:
                _LOGGER.warning(
                    "FortiAP %s channel capability response has no results object",
                    platform,
                )

    def get_radio_channel_metadata(
        self,
        platform_type: str,
        radio_type: str,
        channel: str | int | None,
    ) -> dict[str, Any]:
        """Return widths and DFS status for one AP radio and channel."""
        platform = self._ap_channel_capabilities.get(platform_type)
        if not isinstance(platform, dict):
            return {}

        channel_lists = platform.get("channel_lists")
        if not isinstance(channel_lists, dict):
            return {}

        radio = channel_lists.get(radio_type)
        if not isinstance(radio, dict):
            return {}

        widths = radio.get("channel_widths")
        supported_widths = (
            [width for width in widths if isinstance(width, str)]
            if isinstance(widths, list)
            else []
        )
        metadata: dict[str, Any] = {}
        if supported_widths:
            metadata["fortios_kd_supported_channel_widths"] = supported_widths

        if channel is None:
            return metadata

        channel_key = str(channel)
        channel_found = False
        channel_is_dfs = False
        for width in supported_widths:
            variants = radio.get(width)
            if not isinstance(variants, list):
                continue

            for variant in variants:
                if not isinstance(variant, dict):
                    continue

                channels = variant.get("channels")
                if not isinstance(channels, dict) or channel_key not in channels:
                    continue

                channel_found = True
                if str(channels[channel_key]).casefold() == "dfs":
                    channel_is_dfs = True

        if channel_found:
            metadata["fortios_kd_dfs_channel"] = channel_is_dfs

        return metadata

    def _add_radio_rates(self, data: dict[str, Any]) -> None:
        """Calculate radio rates from cumulative byte counters."""
        sample_time = monotonic()

        for ap in data.get("results", []):
            serial = ap.get("serial")
            if not isinstance(serial, str):
                continue

            for radio in ap.get("radio", []):
                radio_id = radio.get("radio_id")
                if not isinstance(radio_id, int):
                    continue

                for counter_field, rate_field, multiplier in (
                    ("bytes_rx", "rx_bits_per_second", 8),
                    ("bytes_tx", "tx_bits_per_second", 8),
                    ("mac_errors_rx", "rx_mac_errors_per_minute", 60),
                    ("mac_errors_tx", "tx_mac_errors_per_minute", 60),
                ):
                    current_value = radio.get(counter_field)
                    radio[rate_field] = None

                    if not isinstance(current_value, int):
                        continue

                    key = (serial, radio_id, counter_field)
                    previous = self._radio_counters.get(key)

                    if previous is not None:
                        previous_value, previous_time = previous
                        elapsed = sample_time - previous_time

                        if current_value >= previous_value and elapsed > 0:
                            radio[rate_field] = (
                                (current_value - previous_value) * multiplier
                            ) / elapsed

                    self._radio_counters[key] = (
                        current_value,
                        sample_time,
                    )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self._async_load_wifi_meta()
            await self._async_load_ap_names()
            data = await self.client.monitor.wifi.get_managed_access_points()
            platforms = self._annotate_access_points(data)
            await self._async_load_ap_channel_capabilities(platforms)
            wifi_clients = await self.client.monitor.wifi.get_clients()
            arp_table = await self._async_get_arp_table()
            configured_vaps = await self.client.configuration.wifi.get_vaps()

            data["wifi_clients"] = wifi_clients
            self._wifi_clients_by_mac = {}
            self._wifi_clients_by_ip = {}
            for wifi_client in wifi_clients.get("results", []):
                normalized_mac = normalize_mac_address(wifi_client.get("mac"))
                if normalized_mac is not None:
                    self._wifi_clients_by_mac[normalized_mac] = wifi_client

                ip_address = wifi_client.get("ip")
                if isinstance(ip_address, str) and ip_address:
                    self._wifi_clients_by_ip.setdefault(ip_address, []).append(
                        wifi_client
                    )
            data["arp_table"] = arp_table
            self._index_arp_entries(arp_table)
            data["configured_vaps"] = configured_vaps
            if not self.include_unassigned_ssids:
                data[
                    "configured_wtp_profiles"
                ] = await self.client.configuration.wifi.get_wtp_profiles()
            self._add_radio_rates(data)
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Unable to update FortiGate access points: {err}"
            ) from err
        else:
            return data
