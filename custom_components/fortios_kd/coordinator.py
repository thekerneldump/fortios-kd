"""Coordinate FortiGate API updates."""

from datetime import timedelta
import logging
from time import monotonic
from typing import Any

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FortiOSApi

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
            data = await self.client.monitor.wifi.get_managed_access_points()
            wifi_clients = await self.client.monitor.wifi.get_clients()
            configured_vaps = await self.client.configuration.wifi.get_vaps()

            data["wifi_clients"] = wifi_clients
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
