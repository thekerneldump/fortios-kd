"""Coordinate FortiGate API updates."""

from datetime import UTC, datetime, timedelta
import logging
from time import monotonic
from typing import Any

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FortiOSApi
from .api.version import version_family
from .const import RADIO_SPECTRUM_BANDS, RADIO_TYPE_BANDS
from .repairs import async_create_snmp_arp_issue, async_delete_snmp_arp_issue
from .snmp_arp import FortiOSKDSnmpArpClient, SnmpArpError

_LOGGER = logging.getLogger(__name__)
_VDOM_REFRESH_INTERVAL_SECONDS = 300
_DNS_CONFIGURATION_REFRESH_INTERVAL_SECONDS = 300

DNSServerKey = tuple[str, str]


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


def _vdom_results(response: dict[str, Any] | list[Any]) -> list[dict[str, Any]] | None:
    """Normalize FortiOS object and multi-VDOM list response shapes."""
    if isinstance(response, dict):
        results = response.get("results")
        if not isinstance(results, list):
            return None
        return [item for item in results if isinstance(item, dict)]

    results: list[dict[str, Any]] = []
    for item in response:
        if not isinstance(item, dict):
            continue

        response_vdom = item.get("vdom")
        if isinstance(response_vdom, str) and response_vdom:
            results.append({"name": response_vdom})
            continue

        nested_results = item.get("results")
        if isinstance(nested_results, list):
            results.extend(
                result for result in nested_results if isinstance(result, dict)
            )
        elif isinstance(item.get("name"), str):
            results.append(item)

    return results


def _vdom_resource_results(
    response: dict[str, Any] | list[Any],
) -> dict[str, dict[str, Any]] | None:
    """Normalize FortiOS single- and multi-VDOM resource responses."""
    envelopes = [response] if isinstance(response, dict) else response
    results: dict[str, dict[str, Any]] = {}

    for envelope in envelopes:
        if not isinstance(envelope, dict):
            continue

        vdom_name = envelope.get("vdom")
        resource_data = envelope.get("results")
        if isinstance(vdom_name, str) and vdom_name and isinstance(resource_data, dict):
            results[vdom_name] = resource_data

    return results or None


def _vdom_dns_results(
    response: dict[str, Any] | list[Any],
) -> dict[str, dict[str, Any]] | None:
    """Normalize FortiOS single- and multi-VDOM DNS configuration responses."""
    envelopes = [response] if isinstance(response, dict) else response
    results: dict[str, dict[str, Any]] = {}
    response_shape_valid = False

    for envelope in envelopes:
        if not isinstance(envelope, dict):
            continue

        vdom_name = envelope.get("vdom")
        settings = envelope.get("results")
        if not isinstance(settings, dict):
            continue

        response_shape_valid = True
        if isinstance(vdom_name, str) and vdom_name:
            results[vdom_name] = settings

    return results if response_shape_valid else None


def _configured_dns_servers(
    global_response: dict[str, Any],
    vdom_response: dict[str, Any] | list[Any] | None,
    vdom_names: set[str],
    management_vdom: str,
) -> dict[DNSServerKey, dict[str, Any]] | None:
    """Return each VDOM's effective configured DNS servers."""
    global_settings = global_response.get("results")
    if not isinstance(global_settings, dict):
        return None

    vdom_settings: dict[str, dict[str, Any]] = {}
    if vdom_response is not None:
        normalized_vdom_settings = _vdom_dns_results(vdom_response)
        if normalized_vdom_settings is None:
            return None
        vdom_settings = normalized_vdom_settings

    results: dict[DNSServerKey, dict[str, Any]] = {}
    for vdom_name in sorted(vdom_names or {management_vdom}):
        effective_settings = global_settings
        source = "Global"
        override = vdom_settings.get(vdom_name)
        if (
            vdom_name != management_vdom
            and isinstance(override, dict)
            and override.get("vdom-dns") == "enable"
        ):
            effective_settings = override
            source = "VDOM override"

        for field, role in (("primary", "Primary"), ("secondary", "Secondary")):
            ip_address = effective_settings.get(field)
            if not isinstance(ip_address, str) or ip_address in {
                "",
                "0.0.0.0",
                "::",
            }:
                continue

            key = (vdom_name, ip_address)
            record = results.setdefault(
                key,
                {
                    "vdom": vdom_name,
                    "ip": ip_address,
                    "configuration_source": source,
                    "roles": [],
                },
            )
            record["roles"].append(role)

    return results


def _dns_latency_results(
    response: dict[str, Any] | list[Any],
    observed_at: datetime,
) -> dict[DNSServerKey, dict[str, Any]] | None:
    """Normalize per-VDOM DNS latency and calculate the last-test timestamp."""
    envelopes = [response] if isinstance(response, dict) else response
    results: dict[DNSServerKey, dict[str, Any]] = {}
    response_shape_valid = False

    for envelope in envelopes:
        if not isinstance(envelope, dict):
            continue

        vdom_name = envelope.get("vdom")
        latency_entries = envelope.get("results")
        if not isinstance(vdom_name, str) or not vdom_name:
            continue
        if not isinstance(latency_entries, list):
            continue

        response_shape_valid = True
        for entry in latency_entries:
            if not isinstance(entry, dict):
                continue

            ip_address = entry.get("ip")
            if not isinstance(ip_address, str) or not ip_address:
                continue

            record: dict[str, Any] = {
                "vdom": vdom_name,
                "ip": ip_address,
            }
            service = entry.get("service")
            if isinstance(service, str) and service:
                record["service"] = service

            latency = entry.get("latency")
            if isinstance(latency, (int, float)) and not isinstance(latency, bool):
                record["latency"] = latency

            last_update = entry.get("last_update")
            if (
                isinstance(last_update, (int, float))
                and not isinstance(last_update, bool)
                and last_update >= 0
            ):
                record["last_tested"] = (
                    observed_at - timedelta(milliseconds=last_update)
                ).replace(microsecond=0)

            results[(vdom_name, ip_address)] = record

    return results if response_shape_valid else None


class FortiOSKDCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll FortiGate and distribute the latest AP data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FortiOSApi,
        *,
        config_entry_id: str | None = None,
        include_unassigned_ssids: bool = False,
        sync_arp_table: bool = False,
        match_arp_wifi_clients: bool = True,
        sync_dhcp_leases: bool = False,
        snmp_arp_client: FortiOSKDSnmpArpClient | None = None,
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
        self._config_entry_id = config_entry_id
        self.include_unassigned_ssids = include_unassigned_ssids
        self.sync_arp_table = sync_arp_table
        self.match_arp_wifi_clients = match_arp_wifi_clients
        self.sync_dhcp_leases = sync_dhcp_leases
        self._snmp_arp_client = snmp_arp_client
        self._radio_counters: dict[tuple[str, int, str], tuple[int, float]] = {}
        self._wifi_clients_by_mac: dict[str, dict[str, Any]] = {}
        self._wifi_clients_by_ip: dict[str, list[dict[str, Any]]] = {}
        self._arp_entries_by_mac: dict[str, list[dict[str, Any]]] = {}
        self._arp_entries_by_ip: dict[str, list[dict[str, Any]]] = {}
        self._dhcp_entries_by_mac: dict[str, list[dict[str, Any]]] = {}
        self._dhcp_entries_by_ip: dict[str, list[dict[str, Any]]] = {}
        self._arp_supported = bool(
            sync_arp_table
            and (client.supports_network_arp or snmp_arp_client is not None)
        )
        self._arp_table: dict[str, Any] = {
            "results": [],
            "supported": self._arp_supported,
        }
        self._arp_error_logged = False
        self._dhcp_leases: dict[str, Any] = {"results": [], "available": False}
        self._dhcp_error_logged = False
        self._vdoms: dict[str, Any] = {"results": [], "available": False}
        self._vdom_resources: dict[str, Any] = {
            "results": {},
            "available": False,
        }
        self._dns_configuration: dict[str, Any] = {
            "results": {},
            "available": False,
        }
        self._dns_latency: dict[str, Any] = {
            "results": {},
            "available": False,
        }
        self._dns_servers: dict[str, Any] = {
            "results": [],
            "available": False,
        }
        self._dns_servers_by_key: dict[DNSServerKey, dict[str, Any]] = {}
        self._management_vdom: str | None = None
        self._vdom_list_error_logged = False
        self._vdom_global_error_logged = False
        self._vdom_resource_error_logged = False
        self._dns_configuration_error_logged = False
        self._dns_latency_error_logged = False
        self._vdom_inventory_updated_at: float | None = None
        self._dns_configuration_updated_at: float | None = None
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

    def get_dhcp_entries(self, mac: str) -> list[dict[str, Any]]:
        """Return every current DHCP lease for a MAC address."""
        normalized_mac = normalize_mac_address(mac)
        if normalized_mac is None:
            return []
        return self._dhcp_entries_by_mac.get(normalized_mac, [])

    def get_dhcp_entries_by_ip(self, ip_address: str) -> list[dict[str, Any]]:
        """Return current DHCP leases claiming an IP address."""
        return self._dhcp_entries_by_ip.get(ip_address, [])

    @property
    def arp_macs(self) -> set[str]:
        """Return MAC addresses currently present in the ARP table."""
        return set(self._arp_entries_by_mac)

    @property
    def dhcp_macs(self) -> set[str]:
        """Return MAC addresses currently present in the DHCP lease table."""
        return set(self._dhcp_entries_by_mac)

    @property
    def dhcp_data_available(self) -> bool:
        """Return whether a valid DHCP response has been received."""
        return bool(self._dhcp_leases.get("available"))

    @property
    def vdom_names(self) -> set[str]:
        """Return the configured VDOM names from the latest valid response."""
        return {
            name
            for item in self._vdoms.get("results", [])
            if isinstance(item, dict)
            and isinstance(name := item.get("name"), str)
            and name
        }

    @property
    def management_vdom(self) -> str | None:
        """Return the VDOM selected for FortiGate management."""
        return self._management_vdom

    @property
    def vdom_data_available(self) -> bool:
        """Return whether valid VDOM inventory has been received."""
        return bool(self._vdoms.get("available"))

    @property
    def vdom_resource_data_available(self) -> bool:
        """Return whether a valid VDOM resource response was received."""
        return bool(self._vdom_resources.get("available"))

    def get_vdom_resources(self, vdom_name: str) -> dict[str, Any] | None:
        """Return current resource utilization for one VDOM."""
        results = self._vdom_resources.get("results")
        if not isinstance(results, dict):
            return None

        resource_data = results.get(vdom_name)
        return resource_data if isinstance(resource_data, dict) else None

    @property
    def dns_server_keys(self) -> set[DNSServerKey]:
        """Return the current VDOM and IP identity of every DNS server."""
        return set(self._dns_servers_by_key)

    @property
    def dns_data_available(self) -> bool:
        """Return whether DNS configuration or latency data is current."""
        return bool(self._dns_servers.get("available"))

    def get_dns_server(
        self,
        vdom_name: str,
        ip_address: str,
    ) -> dict[str, Any] | None:
        """Return one DNS server record scoped to a VDOM."""
        return self._dns_servers_by_key.get((vdom_name, ip_address))

    def get_vdom_dns_servers(self, vdom_name: str) -> list[dict[str, Any]]:
        """Return current DNS server records for one VDOM."""
        return sorted(
            (
                record
                for (record_vdom, _), record in self._dns_servers_by_key.items()
                if record_vdom == vdom_name
                and (
                    record.get("configuration_available")
                    or record.get("latency_available")
                )
            ),
            key=lambda record: str(record.get("ip", "")),
        )

    async def _async_get_vdom_inventory(self) -> dict[str, Any]:
        """Return VDOM inventory while retaining the last valid configuration."""
        if (
            self._vdom_inventory_updated_at is not None
            and monotonic() - self._vdom_inventory_updated_at
            < _VDOM_REFRESH_INTERVAL_SECONDS
        ):
            return {
                **self._vdoms,
                "management_vdom": self._management_vdom,
            }

        vdom_list_valid = False
        try:
            vdom_response = await self.client.configuration.system.get_vdoms()
        except (ClientError, TimeoutError, TypeError) as err:
            if not self._vdom_list_error_logged:
                _LOGGER.warning("Unable to load FortiGate VDOM list: %s", err)
                self._vdom_list_error_logged = True
        else:
            vdom_results = _vdom_results(vdom_response)
            if vdom_results is not None:
                response_metadata = (
                    vdom_response if isinstance(vdom_response, dict) else {}
                )
                self._vdoms = {
                    **response_metadata,
                    "results": [
                        item
                        for item in vdom_results
                        if isinstance(item, dict)
                        and isinstance(item.get("name"), str)
                        and item["name"]
                    ],
                    "available": True,
                }
                self._vdom_list_error_logged = False
                vdom_list_valid = True
            elif not self._vdom_list_error_logged:
                _LOGGER.warning("FortiGate VDOM response has no results list")
                self._vdom_list_error_logged = True

        management_vdom_valid = False
        try:
            global_response = (
                await self.client.configuration.system.get_vdom_global_settings()
            )
        except (ClientError, TimeoutError, TypeError) as err:
            if not self._vdom_global_error_logged:
                _LOGGER.warning(
                    "Unable to load FortiGate management VDOM setting: %s",
                    err,
                )
                self._vdom_global_error_logged = True
        else:
            global_results = global_response.get("results")
            management_vdom = (
                global_results.get("management-vdom")
                if isinstance(global_results, dict)
                else None
            )
            if isinstance(management_vdom, str) and management_vdom:
                self._management_vdom = management_vdom
                self._vdom_global_error_logged = False
                management_vdom_valid = True
            elif not self._vdom_global_error_logged:
                _LOGGER.warning(
                    "FortiGate global configuration response has no management VDOM"
                )
                self._vdom_global_error_logged = True

        if vdom_list_valid and management_vdom_valid:
            self._vdom_inventory_updated_at = monotonic()

        return {
            **self._vdoms,
            "management_vdom": self._management_vdom,
        }

    async def _async_get_vdom_resources(self) -> dict[str, Any]:
        """Return VDOM resource usage without blocking primary wifi updates."""
        try:
            response = await self.client.monitor.system.get_vdom_resources()
        except (ClientError, TimeoutError, TypeError) as err:
            self._vdom_resources = {
                **self._vdom_resources,
                "available": False,
            }
            if not self._vdom_resource_error_logged:
                _LOGGER.warning("Unable to load FortiGate VDOM resources: %s", err)
                self._vdom_resource_error_logged = True
            return self._vdom_resources

        resource_results = _vdom_resource_results(response)
        if resource_results is None:
            self._vdom_resources = {
                **self._vdom_resources,
                "available": False,
            }
            if not self._vdom_resource_error_logged:
                _LOGGER.warning(
                    "FortiGate VDOM resource response has no per-VDOM results"
                )
                self._vdom_resource_error_logged = True
            return self._vdom_resources

        self._vdom_resource_error_logged = False
        self._vdom_resources = {
            "results": resource_results,
            "available": True,
        }
        return self._vdom_resources

    async def _async_get_dns_configuration(self) -> dict[str, Any]:
        """Return effective DNS configuration without blocking wifi updates."""
        if (
            self._dns_configuration_updated_at is not None
            and monotonic() - self._dns_configuration_updated_at
            < _DNS_CONFIGURATION_REFRESH_INTERVAL_SECONDS
        ):
            return self._dns_configuration

        vdom_names = self.vdom_names
        management_vdom = self._management_vdom or (
            min(vdom_names) if vdom_names else "root"
        )

        try:
            global_response = await self.client.configuration.system.get_global_dns(
                management_vdom
            )
            vdom_response = (
                await self.client.configuration.system.get_vdom_dns()
                if len(vdom_names) > 1
                else None
            )
        except (ClientError, TimeoutError, TypeError) as err:
            self._dns_configuration = {
                **self._dns_configuration,
                "available": False,
            }
            if not self._dns_configuration_error_logged:
                _LOGGER.warning("Unable to load FortiGate DNS configuration: %s", err)
                self._dns_configuration_error_logged = True
            return self._dns_configuration

        configured_servers = _configured_dns_servers(
            global_response,
            vdom_response,
            vdom_names,
            management_vdom,
        )
        if configured_servers is None:
            self._dns_configuration = {
                **self._dns_configuration,
                "available": False,
            }
            if not self._dns_configuration_error_logged:
                _LOGGER.warning(
                    "FortiGate DNS configuration response has an unexpected shape"
                )
                self._dns_configuration_error_logged = True
            return self._dns_configuration

        self._dns_configuration_error_logged = False
        self._dns_configuration_updated_at = monotonic()
        self._dns_configuration = {
            "results": configured_servers,
            "available": True,
        }
        return self._dns_configuration

    async def _async_get_dns_latency(self) -> dict[str, Any]:
        """Return current DNS latency without blocking primary wifi updates."""
        try:
            response = await self.client.monitor.network.get_dns_latency()
        except (ClientError, TimeoutError, TypeError) as err:
            self._dns_latency = {
                **self._dns_latency,
                "available": False,
            }
            if not self._dns_latency_error_logged:
                _LOGGER.warning("Unable to load FortiGate DNS latency: %s", err)
                self._dns_latency_error_logged = True
            return self._dns_latency

        latency_results = _dns_latency_results(response, datetime.now(UTC))
        if latency_results is None:
            self._dns_latency = {
                **self._dns_latency,
                "available": False,
            }
            if not self._dns_latency_error_logged:
                _LOGGER.warning(
                    "FortiGate DNS latency response has no per-VDOM results"
                )
                self._dns_latency_error_logged = True
            return self._dns_latency

        self._dns_latency_error_logged = False
        self._dns_latency = {
            "results": latency_results,
            "available": True,
        }
        return self._dns_latency

    def _rebuild_dns_servers(self) -> dict[str, Any]:
        """Combine configured and runtime-observed DNS servers by VDOM and IP."""
        configuration_results = self._dns_configuration.get("results")
        latency_results = self._dns_latency.get("results")
        configuration = (
            configuration_results if isinstance(configuration_results, dict) else {}
        )
        latency = latency_results if isinstance(latency_results, dict) else {}
        configuration_available = bool(self._dns_configuration.get("available"))
        latency_available = bool(self._dns_latency.get("available"))
        records: dict[DNSServerKey, dict[str, Any]] = {}

        for key in configuration.keys() | latency.keys():
            configured_record = configuration.get(key)
            latency_record = latency.get(key)
            vdom_name, ip_address = key
            record: dict[str, Any] = {
                "vdom": vdom_name,
                "ip": ip_address,
                "configuration_available": configuration_available
                and isinstance(configured_record, dict),
                "latency_available": latency_available
                and isinstance(latency_record, dict),
                "configured": isinstance(configured_record, dict),
            }
            if isinstance(configured_record, dict):
                record.update(configured_record)
            else:
                record["configuration_source"] = "Runtime discovered"
                record["roles"] = []
            if isinstance(latency_record, dict):
                record.update(latency_record)
            records[key] = record

        self._dns_servers_by_key = records
        self._dns_servers = {
            "results": [records[key] for key in sorted(records)],
            "available": configuration_available or latency_available,
        }
        return self._dns_servers

    async def _async_get_dns_servers(self) -> dict[str, Any]:
        """Return effective DNS servers and their runtime latency."""
        await self._async_get_dns_configuration()
        await self._async_get_dns_latency()
        return self._rebuild_dns_servers()

    async def _async_get_arp_table(self) -> dict[str, Any]:
        """Return the ARP table, retaining the last table after request errors."""
        requires_snmp = bool(
            self.sync_arp_table
            and self.client.version is not None
            and version_family(self.client.version, "6.2")
        )
        if not requires_snmp and self._config_entry_id is not None:
            async_delete_snmp_arp_issue(self.hass, self._config_entry_id)
        self._arp_supported = bool(
            self.sync_arp_table
            and (self.client.supports_network_arp or self._snmp_arp_client is not None)
        )
        if not self._arp_supported:
            self._arp_table = {"results": [], "supported": False}
            if requires_snmp and self._config_entry_id is not None:
                async_create_snmp_arp_issue(
                    self.hass,
                    self._config_entry_id,
                    self.client.version_text,
                )
            return self._arp_table

        try:
            if self.client.supports_network_arp:
                response = await self.client.monitor.network.get_arp_table()
            elif self._snmp_arp_client is not None:
                response = await self._snmp_arp_client.async_get_arp_table()
            else:
                return self._arp_table
        except (ClientError, SnmpArpError, TimeoutError) as err:
            if requires_snmp and self._config_entry_id is not None:
                async_create_snmp_arp_issue(
                    self.hass,
                    self._config_entry_id,
                    self.client.version_text,
                )
            if not self._arp_error_logged:
                _LOGGER.warning(
                    "Unable to load the FortiGate ARP table using %s: %s",
                    "the API" if self.client.supports_network_arp else "SNMPv2c",
                    err,
                )
                self._arp_error_logged = True
            return self._arp_table

        results = response.get("results")
        if not isinstance(results, list):
            if not self._arp_error_logged:
                _LOGGER.warning("FortiGate ARP table response has no results list")
                self._arp_error_logged = True
            return self._arp_table

        self._arp_error_logged = False
        if self._config_entry_id is not None:
            async_delete_snmp_arp_issue(self.hass, self._config_entry_id)
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

    async def _async_get_dhcp_leases(self) -> dict[str, Any]:
        """Return DHCP leases, retaining the last valid response on errors."""
        if not self.sync_dhcp_leases:
            return self._dhcp_leases

        try:
            response = await self.client.monitor.system.get_dhcp_leases()
        except (ClientError, TimeoutError) as err:
            if not self._dhcp_error_logged:
                _LOGGER.warning("Unable to load FortiGate DHCP leases: %s", err)
                self._dhcp_error_logged = True
            return self._dhcp_leases

        results = response.get("results")
        if not isinstance(results, list):
            if not self._dhcp_error_logged:
                _LOGGER.warning("FortiGate DHCP response has no results list")
                self._dhcp_error_logged = True
            return self._dhcp_leases

        self._dhcp_error_logged = False
        self._dhcp_leases = {**response, "results": results, "available": True}
        return self._dhcp_leases

    def _index_dhcp_entries(self, dhcp_leases: dict[str, Any]) -> None:
        """Index valid DHCP leases by canonical MAC and IP address."""
        entries_by_mac: dict[str, list[dict[str, Any]]] = {}
        entries_by_ip: dict[str, list[dict[str, Any]]] = {}

        for entry in dhcp_leases.get("results", []):
            if not isinstance(entry, dict):
                continue

            normalized_mac = normalize_mac_address(entry.get("mac"))
            ip_address = entry.get("ip")
            if normalized_mac is None or not isinstance(ip_address, str):
                continue

            normalized_entry = {**entry, "mac": normalized_mac}
            entries_by_mac.setdefault(normalized_mac, []).append(normalized_entry)
            entries_by_ip.setdefault(ip_address, []).append(normalized_entry)

        self._dhcp_entries_by_mac = entries_by_mac
        self._dhcp_entries_by_ip = entries_by_ip

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
            dhcp_leases = await self._async_get_dhcp_leases()
            vdoms = await self._async_get_vdom_inventory()
            vdom_resources = await self._async_get_vdom_resources()
            dns_servers = await self._async_get_dns_servers()
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
            data["dhcp_leases"] = dhcp_leases
            self._index_dhcp_entries(dhcp_leases)
            data["vdoms"] = vdoms
            data["vdom_resources"] = vdom_resources
            data["dns_servers"] = dns_servers
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
