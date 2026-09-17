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


class FortiOSKDCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll FortiGate and distribute the latest AP data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FortiOSApi,
        *,
        include_unassigned_ssids: bool = False,
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
        self._radio_counters: dict[tuple[str, int, str], tuple[int, float]] = {}
        self._wifi_clients_by_mac: dict[str, dict[str, Any]] = {}
        self._wifi_meta_loaded = False
        self.wifi_meta: dict[str, Any] = {}
        self.radio_type_bands = RADIO_TYPE_BANDS.copy()

    def get_wifi_client(self, mac: str) -> dict[str, Any] | None:
        """Return a wifi client by MAC address without scanning every client."""
        return self._wifi_clients_by_mac.get(mac.casefold())

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
            data = await self.client.monitor.wifi.get_managed_access_points()
            wifi_clients = await self.client.monitor.wifi.get_clients()
            configured_vaps = await self.client.configuration.wifi.get_vaps()

            data["wifi_clients"] = wifi_clients
            self._wifi_clients_by_mac = {
                mac.casefold(): wifi_client
                for wifi_client in wifi_clients.get("results", [])
                if isinstance((mac := wifi_client.get("mac")), str) and mac
            }
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
