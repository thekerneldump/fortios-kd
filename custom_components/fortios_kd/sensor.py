"""Sensor platform for FortiOS KD."""

from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MASK_AP_NAMES,
    CONF_MASK_CLIENT_HOSTNAMES,
    CONF_MASK_CLIENT_MACS,
    CONF_MASK_SERIAL_NUMBERS,
    CONF_MASK_SSIDS,
    CONF_MASK_VLAN_IDS,
    DEFAULT_MASK_AP_NAMES,
    DEFAULT_MASK_CLIENT_HOSTNAMES,
    DEFAULT_MASK_CLIENT_MACS,
    DEFAULT_MASK_SERIAL_NUMBERS,
    DEFAULT_MASK_SSIDS,
    DEFAULT_MASK_VLAN_IDS,
    DOMAIN,
)
from .coordinator import FortiOSKDCoordinator, normalize_mac_address


def mask_serial(serial: str) -> str:
    return "*" * max(0, len(serial) - 4) + serial[-4:]


def mask_name(name: str) -> str:
    if len(name) <= 8:
        return name

    return name[:5] + "*" * (len(name) - 8) + name[-3:]


def mask_ssid(ssid: str) -> str:
    name, separator, band = ssid.rpartition(" ")
    if separator and band.casefold() in {"2.4ghz", "5ghz", "6ghz"}:
        return f"{name[:2]}{'*' * max(0, len(name) - 2)} {band}"

    return ssid[:2] + "*" * max(0, len(ssid) - 2)


def mask_client_mac(mac: str) -> str:
    """Keep the OUI and mask the device-specific half."""
    parts = mac.split(":")
    if len(parts) == 6:
        return ":".join(parts[:3] + ["**", "**", "**"])

    return mac[:8] + "*" * max(0, len(mac) - 8)


def mask_client_hostname(hostname: str) -> str:
    """Mask a client hostname while retaining a useful prefix."""
    if "-" in hostname:
        prefix, separator, suffix = hostname.partition("-")
        return prefix + separator + "*" * len(suffix)

    return hostname[:4] + "*" * max(0, len(hostname) - 4)


def mask_vlan_id(vlan_id: str | int) -> str:
    """Mask every digit of a VLAN ID."""
    return "*" * len(str(vlan_id))


def _freeze_state_value(value: Any) -> Any:
    """Return an immutable snapshot suitable for coordinator state comparisons."""
    if isinstance(value, dict):
        return tuple(
            (key, _freeze_state_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_state_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze_state_value(item) for item in value), key=repr))
    return value


def _dashboard_match_id(fortigate_serial: str, mac: str) -> str:
    """Return an opaque exact-match identifier for related dashboard entities."""
    normalized_mac = normalize_mac_address(mac) or mac.casefold()
    identity = f"{DOMAIN}\0{fortigate_serial}\0{normalized_mac}"
    return sha256(identity.encode()).hexdigest()


def _registered_wifi_client_macs(
    entries: Iterable[er.RegistryEntry],
    fortigate_serial: str,
) -> set[str]:
    """Return client MACs represented by registered MAC-address sensors."""
    unique_id_prefix = f"{fortigate_serial}_wifi_client_"
    unique_id_suffix = "_mac_address"
    macs: set[str] = set()

    for registry_entry in entries:
        unique_id = registry_entry.unique_id
        if (
            registry_entry.domain != "sensor"
            or registry_entry.platform != DOMAIN
            or not unique_id.startswith(unique_id_prefix)
            or not unique_id.endswith(unique_id_suffix)
        ):
            continue

        mac = unique_id[len(unique_id_prefix) : -len(unique_id_suffix)]
        if normalized_mac := normalize_mac_address(mac):
            macs.add(normalized_mac)

    return macs


def _registered_arp_macs(
    entries: Iterable[er.RegistryEntry],
    fortigate_serial: str,
) -> set[str]:
    """Return MACs represented by registered ARP address sensors."""
    unique_id_prefix = f"{fortigate_serial}_arp_"
    unique_id_suffix = "_ip_addresses"
    macs: set[str] = set()

    for registry_entry in entries:
        unique_id = registry_entry.unique_id
        if (
            registry_entry.domain != "sensor"
            or registry_entry.platform != DOMAIN
            or not unique_id.startswith(unique_id_prefix)
            or not unique_id.endswith(unique_id_suffix)
        ):
            continue

        mac = unique_id[len(unique_id_prefix) : -len(unique_id_suffix)]
        if normalized_mac := normalize_mac_address(mac):
            macs.add(normalized_mac)

    return macs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    status = hass.data[DOMAIN][entry.entry_id]["status"]
    fortigate_hostname = status["results"].get("hostname") or entry.title
    fortigate_serial = status["serial"]
    mask_serial_numbers = entry.data.get(
        CONF_MASK_SERIAL_NUMBERS,
        DEFAULT_MASK_SERIAL_NUMBERS,
    )
    displayed_fortigate_hostname = (
        mask_name(fortigate_hostname) if mask_serial_numbers else fortigate_hostname
    )
    mask_ssids = entry.data.get(
        CONF_MASK_SSIDS,
        DEFAULT_MASK_SSIDS,
    )
    mask_client_macs = entry.data.get(
        CONF_MASK_CLIENT_MACS,
        DEFAULT_MASK_CLIENT_MACS,
    )
    mask_client_hostnames = entry.data.get(
        CONF_MASK_CLIENT_HOSTNAMES,
        DEFAULT_MASK_CLIENT_HOSTNAMES,
    )
    mask_vlan_ids = entry.data.get(
        CONF_MASK_VLAN_IDS,
        DEFAULT_MASK_VLAN_IDS,
    )
    mask_ap_names = entry.data.get(
        CONF_MASK_AP_NAMES,
        DEFAULT_MASK_AP_NAMES,
    )
    client_masking = {
        "mac": mask_client_macs,
        "hostname": mask_client_hostnames,
        "ssid": mask_ssids,
        "vlan_id": mask_vlan_ids,
        "wtp_name": mask_ap_names,
    }

    coordinator: FortiOSKDCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    radio_type_bands = coordinator.radio_type_bands
    aps = coordinator.data["results"]
    wifi_clients = coordinator.data["wifi_clients"]["results"]
    current_client_macs = {
        normalized_mac
        for client in wifi_clients
        if (normalized_mac := normalize_mac_address(client.get("mac")))
    }
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry,
        entry.entry_id,
    )
    registered_client_macs = _registered_wifi_client_macs(
        registry_entries,
        fortigate_serial,
    )
    known_client_macs = current_client_macs | registered_client_macs
    client_records = [
        *wifi_clients,
        *({"mac": mac} for mac in sorted(registered_client_macs - current_client_macs)),
    ]
    current_arp_macs = coordinator.arp_macs if coordinator.sync_arp_table else set()
    registered_arp_macs = (
        _registered_arp_macs(
            registry_entries,
            fortigate_serial,
        )
        if coordinator.sync_arp_table
        else set()
    )
    known_arp_macs = current_arp_macs | registered_arp_macs
    arp_records = sorted(known_arp_macs)

    async_add_entities(
        [
            FortiGateVersionSensor(entry, status, mask_serial_numbers),
            *(
                entity
                for client in client_records
                if isinstance(client.get("mac"), str) and client["mac"]
                for entity in create_wifi_client_entities(
                    coordinator,
                    client,
                    fortigate_serial,
                    displayed_fortigate_hostname,
                    client_masking,
                )
            ),
            *(
                entity
                for mac in arp_records
                for entity in create_arp_entities(
                    coordinator,
                    mac,
                    fortigate_serial,
                    displayed_fortigate_hostname,
                    mask_client_macs,
                    mask_client_hostnames,
                )
            ),
            *(
                FortiGateAPSerialSensor(
                    ap,
                    mask_serial_numbers,
                    mask_ap_names,
                )
                for ap in aps
            ),
            *(FortiGateAPVDOMEntity(ap) for ap in aps),
            *(FortiGateAPAPProfileEntity(ap) for ap in aps),
            *(FortiGateAPState(ap) for ap in aps),
            *(FortiGateAPConnectingFrom(ap) for ap in aps),
            *(FortiGateAPConnectingInterface(ap) for ap in aps),
            *(FortiGateAPStatus(ap) for ap in aps),
            *(FortiGateAPUplink(ap) for ap in aps),
            *(
                FortiGateAPUplinkSpeed(ap)
                for ap in aps
                if "mesh_uplink_intf_speed" in ap
            ),
            *(FortiGateAPOSVersion(ap) for ap in aps if "os_version" in ap),
            *(FortiGateAPClients(coordinator, ap) for ap in aps),
            *(
                FortiGateAPMetric(
                    coordinator,
                    ap,
                    "lldp_enable",
                    "LLDP",
                    "mdi:protocol",
                )
                for ap in aps
            ),
            *(
                FortiGateAPMetric(
                    coordinator,
                    ap,
                    "cli_enabled",
                    "CLI Access",
                    "mdi:console",
                )
                for ap in aps
            ),
            *(
                FortiGateAPMetric(
                    coordinator,
                    ap,
                    "cpu_usage",
                    "CPU Usage",
                    "mdi:cpu-64-bit",
                    unit=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                )
                for ap in aps
            ),
            *(
                FortiGateAPMetric(
                    coordinator,
                    ap,
                    "mem_free",
                    "Memory Free",
                    "mdi:memory",
                    unit=UnitOfInformation.KILOBYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_unit=UnitOfInformation.MEGABYTES,
                )
                for ap in aps
            ),
            *(
                FortiGateAPMetric(
                    coordinator,
                    ap,
                    "mem_total",
                    "Memory Total",
                    "mdi:memory",
                    unit=UnitOfInformation.KILOBYTES,
                    device_class=SensorDeviceClass.DATA_SIZE,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_unit=UnitOfInformation.MEGABYTES,
                )
                for ap in aps
            ),
            *(FortiGateAPBoardMAC(ap) for ap in aps),
            *(FortiGateAPJoinTime(ap) for ap in aps),
            *(FortiGateAPUpTime(ap) for ap in aps),
            *(
                FortiGateAPRadioSSIDs(
                    ap,
                    radio,
                    mask_ssids,
                    radio_type_bands,
                )
                for ap in aps
                for radio in ap.get("radio", [])
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "oper_chan",
                    "Channel",
                    "mdi:radio-tower",
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "oper_txpower",
                    "TX Power",
                    "mdi:signal",
                    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "bytes_rx",
                    "RX Total",
                    "mdi:download-network-outline",
                    UnitOfInformation.BYTES,
                    SensorDeviceClass.DATA_SIZE,
                    SensorStateClass.TOTAL_INCREASING,
                    UnitOfInformation.GIGABYTES,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "bytes_tx",
                    "TX Total",
                    "mdi:upload-network-outline",
                    UnitOfInformation.BYTES,
                    SensorDeviceClass.DATA_SIZE,
                    SensorStateClass.TOTAL_INCREASING,
                    UnitOfInformation.GIGABYTES,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "rx_bits_per_second",
                    "RX Rate",
                    "mdi:download-network",
                    UnitOfDataRate.BITS_PER_SECOND,
                    SensorDeviceClass.DATA_RATE,
                    SensorStateClass.MEASUREMENT,
                    UnitOfDataRate.MEGABITS_PER_SECOND,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "tx_bits_per_second",
                    "TX Rate",
                    "mdi:upload-network",
                    UnitOfDataRate.BITS_PER_SECOND,
                    SensorDeviceClass.DATA_RATE,
                    SensorStateClass.MEASUREMENT,
                    UnitOfDataRate.MEGABITS_PER_SECOND,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "channel_utilization_percent",
                    "Channel Utilization",
                    "mdi:chart-donut",
                    unit=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "mac_errors_rx",
                    "RX MAC Errors",
                    "mdi:alert-circle-outline",
                    unit="errors",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "mac_errors_tx",
                    "TX MAC Errors",
                    "mdi:alert-circle-outline",
                    unit="errors",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "rx_mac_errors_per_minute",
                    "RX MAC Error Rate",
                    "mdi:alert-circle",
                    unit="errors/min",
                    state_class=SensorStateClass.MEASUREMENT,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "tx_mac_errors_per_minute",
                    "TX MAC Error Rate",
                    "mdi:alert-circle",
                    unit="errors/min",
                    state_class=SensorStateClass.MEASUREMENT,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "noise_floor",
                    "Noise Floor",
                    "mdi:signal-distance-variant",
                    unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                    state_class=SensorStateClass.MEASUREMENT,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "radio_type",
                    "Radio Type",
                    "mdi:wifi-cog",
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "mode",
                    "Mode",
                    "mdi:access-point",
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "bandwidth_rx",
                    "RX Bandwidth",
                    "mdi:download-network",
                    unit=UnitOfDataRate.BITS_PER_SECOND,
                    device_class=SensorDeviceClass.DATA_RATE,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_unit=UnitOfDataRate.MEGABITS_PER_SECOND,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
            *(
                FortiGateAPRadioMetric(
                    coordinator,
                    ap,
                    radio,
                    "bandwidth_tx",
                    "TX Bandwidth",
                    "mdi:upload-network",
                    unit=UnitOfDataRate.BITS_PER_SECOND,
                    device_class=SensorDeviceClass.DATA_RATE,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_unit=UnitOfDataRate.MEGABITS_PER_SECOND,
                )
                for ap in aps
                for radio in ap.get("radio", [])
                if radio.get("radio_type") in radio_type_bands
            ),
        ]
    )

    def _add_new_wifi_clients() -> None:
        new_entities: list[SensorEntity] = []
        current_clients = coordinator.data.get("wifi_clients", {}).get("results", [])

        for client in current_clients:
            mac = client.get("mac")
            if not isinstance(mac, str) or not mac:
                continue

            normalized_mac = normalize_mac_address(mac)
            if normalized_mac is None:
                continue
            if normalized_mac in known_client_macs:
                continue

            known_client_macs.add(normalized_mac)
            new_entities.extend(
                create_wifi_client_entities(
                    coordinator,
                    client,
                    fortigate_serial,
                    displayed_fortigate_hostname,
                    client_masking,
                )
            )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_wifi_clients))

    def _add_new_arp_entries() -> None:
        new_entities: list[SensorEntity] = []

        for normalized_mac in coordinator.arp_macs:
            if normalized_mac in known_arp_macs:
                continue

            known_arp_macs.add(normalized_mac)
            new_entities.extend(
                create_arp_entities(
                    coordinator,
                    normalized_mac,
                    fortigate_serial,
                    displayed_fortigate_hostname,
                    mask_client_macs,
                    mask_client_hostnames,
                )
            )

        if new_entities:
            async_add_entities(new_entities)

    if coordinator.sync_arp_table:
        entry.async_on_unload(coordinator.async_add_listener(_add_new_arp_entries))

    device_registry = dr.async_get(hass)

    fortigate_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, status["serial"])},
        name=(
            mask_name(fortigate_hostname) if mask_serial_numbers else fortigate_hostname
        ),
        manufacturer="Fortinet",
        model=status["results"].get("model"),
        serial_number=mask_serial(status["serial"])
        if mask_serial_numbers
        else status["serial"],
        sw_version=status["version"],
    )
    for ap in aps:
        serial = ap["serial"]
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial)},
            name=mask_name(ap["name"]) if mask_ap_names else ap["name"],
            manufacturer="Fortinet",
            serial_number=mask_serial(serial) if mask_serial_numbers else serial,
            via_device_id=fortigate_device.id,
        )


class FortiGateVersionSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Firmware version"

    def __init__(
        self,
        entry: ConfigEntry,
        status: dict[str, Any],
        mask_serial_numbers: bool,
    ) -> None:
        serial = status["serial"]
        details = status["results"]
        hostname = details.get("hostname") or entry.title

        self._attr_unique_id = f"{serial}_firmware_version"
        self._attr_native_value = status["version"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=mask_name(hostname) if mask_serial_numbers else hostname,
            manufacturer="Fortinet",
            model=details.get("model"),
            serial_number=mask_serial(serial) if mask_serial_numbers else serial,
            sw_version=status["version"],
        )


class FortiGateAPSerialSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Serial number"
    _attr_icon = "mdi:identifier"

    def __init__(
        self,
        ap: dict[str, Any],
        mask_serial_numbers: bool,
        mask_ap_names: bool,
    ) -> None:
        serial = ap["serial"]
        displayed_serial = mask_serial(serial) if mask_serial_numbers else serial

        self._attr_unique_id = f"{serial}_serial_number"
        self._attr_native_value = displayed_serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=mask_name(ap["name"]) if mask_ap_names else ap["name"],
            manufacturer="Fortinet",
            model=ap.get("fortios_kd_ap_model"),
            serial_number=displayed_serial,
        )


class FortiGateAPVDOMEntity(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:server-network"
    _attr_name = "VDOM"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_vdom"
        self._attr_native_value = ap["vdom"]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, serial)})


class FortiGateAPAPProfileEntity(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:tune-variant"
    _attr_name = "AP Profile"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_ap_profile"
        self._attr_native_value = ap["ap_profile"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPState(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "State"

    @property
    def icon(self) -> str:
        if str(self.native_value).casefold() == "authorized":
            return "mdi:shield-check"

        return "mdi:shield-alert"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_state"
        self._attr_native_value = ap["state"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPConnectingFrom(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:ip-network"
    _attr_name = "Connecting From"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_connecting_from"
        self._attr_native_value = ap["connecting_from"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPConnectingInterface(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:ethernet"
    _attr_name = "Connecting Interface"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_connecting_interface"
        self._attr_native_value = ap["connecting_interface"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPStatus(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:access-point-network"
    _attr_name = "Status"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_status"
        self._attr_native_value = ap["status"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPUplink(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:lan-connect"
    _attr_name = "Uplink Type"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_uplink"
        self._attr_native_value = ap["mesh_uplink"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPUplinkSpeed(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:speedometer"
    _attr_name = "Uplink Speed"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_uplink_speed"
        self._attr_native_value = ap["mesh_uplink_intf_speed"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPOSVersion(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:update"
    _attr_name = "OS Version"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_os_version"
        os_version = ap.get("os_version")
        self._attr_native_value = os_version
        self._attr_available = os_version is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateChangedCoordinatorSensor(
    CoordinatorEntity[FortiOSKDCoordinator], SensorEntity
):
    """Write state only when this entity's state or attributes changed."""

    _last_coordinator_state: tuple[bool, Any, Any] | None = None

    def _coordinator_state(self) -> tuple[bool, Any, Any]:
        """Return an immutable snapshot of externally visible entity state."""
        return (
            self.available,
            _freeze_state_value(self.native_value),
            _freeze_state_value(self.extra_state_attributes),
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates and remember the initial entity state."""
        await super().async_added_to_hass()
        self._last_coordinator_state = self._coordinator_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write state only when the coordinator changed this entity."""
        current_state = self._coordinator_state()
        if current_state == self._last_coordinator_state:
            return

        self._last_coordinator_state = current_state
        self.async_write_ha_state()


class FortiGateAPClients(FortiGateChangedCoordinatorSensor):
    _attr_has_entity_name = True
    _attr_icon = "mdi:account-multiple"
    _attr_name = "Clients"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, ap: dict[str, Any]) -> None:
        super().__init__(coordinator)

        self._serial = ap["serial"]
        self._attr_unique_id = f"{self._serial}_clients"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "clients"
        self._attr_extra_state_attributes = {
            "fortios_kd_metric": "clients",
            "fortios_kd_scope": "ap",
        }

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
        )

    def _get_ap(self) -> dict[str, Any] | None:
        for ap in self.coordinator.data.get("results", []):
            if ap.get("serial") == self._serial:
                return ap
        return None

    @property
    def native_value(self) -> int | None:
        ap = self._get_ap()
        if ap is None:
            return None

        try:
            return int(ap.get("clients"))
        except TypeError, ValueError:
            return None


class FortiGateAPBoardMAC(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:network-outline"
    _attr_name = "Board MAC Address"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        self._attr_unique_id = f"{serial}_board_mac"
        self._attr_native_value = ap["board_mac"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPJoinTime(SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Join time"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        raw_time = ap.get("join_time_raw")

        self._attr_unique_id = f"{serial}_join_time"

        try:
            self._attr_native_value = dt_util.utc_from_timestamp(int(raw_time))
        except TypeError, ValueError:
            self._attr_native_value = None
            self._attr_available = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPUpTime(SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Up time"

    def __init__(self, ap: dict[str, Any]) -> None:
        serial = ap["serial"]
        raw_time = ap.get("last_reboot_time_raw")

        self._attr_unique_id = f"{serial}_uptime"

        try:
            self._attr_native_value = dt_util.utc_from_timestamp(int(raw_time))
        except TypeError, ValueError:
            self._attr_native_value = None
            self._attr_available = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )


class FortiGateAPRadioSSIDs(SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        ap: dict[str, Any],
        radio: dict[str, Any],
        mask_ssids: bool,
        radio_type_bands: dict[str, str],
    ) -> None:
        serial = ap["serial"]
        radio_id = radio["radio_id"]
        self._radio_object_id = f"Radio {radio_id} SSIDs"
        band = radio_type_bands.get(
            radio.get("radio_type"),
            f"Radio {radio_id}",
        )

        ssids = list(radio.get("ssid", {}).values())
        if mask_ssids:
            ssids = [mask_ssid(ssid) for ssid in ssids]

        self._attr_unique_id = f"{serial}_radio_{radio_id}_ssids"
        self._attr_name = f"{band} SSIDs"
        self._attr_native_value = len(ssids)
        self._attr_native_value = ", ".join(ssids) if ssids else "None"
        self._attr_extra_state_attributes = {
            "count": len(ssids),
            "ssids": ssids,
            "fortios_kd_radio_id": radio_id,
            "fortios_kd_band": band,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )

    @property
    def suggested_object_id(self) -> str:
        return self._radio_object_id


class FortiGateAPRadioMetric(FortiGateChangedCoordinatorSensor):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        ap: dict[str, Any],
        radio: dict[str, Any],
        field: str,
        label: str,
        icon: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        suggested_unit: str | None = None,
    ) -> None:
        super().__init__(coordinator)

        self._serial = ap["serial"]
        self._radio_id = radio["radio_id"]
        self._field = field
        self._ap_model = ap.get("fortios_kd_ap_model")
        self._platform_type = ap.get("fortios_kd_platform_type")
        self._radio_object_id = f"Radio {self._radio_id} {label}"
        self._band = coordinator.radio_type_bands.get(
            radio.get("radio_type"),
            f"Radio {self._radio_id}",
        )

        self._attr_unique_id = f"{self._serial}_radio_{self._radio_id}_{field}"
        self._attr_name = f"{self._band} {label}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_suggested_unit_of_measurement = suggested_unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
        )
        self._attr_extra_state_attributes = {
            "fortios_kd_metric": field,
            "fortios_kd_scope": "radio",
            "fortios_kd_radio_id": self._radio_id,
            "fortios_kd_band": self._band,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return graph metadata and live channel capability details."""
        attributes = dict(self._attr_extra_state_attributes)
        if self._field != "oper_chan" or not isinstance(self._platform_type, str):
            return attributes

        attributes["fortios_kd_platform_type"] = self._platform_type
        if isinstance(self._ap_model, str):
            attributes["fortios_kd_ap_model"] = self._ap_model

        radio = self._get_radio()
        if radio is None:
            return attributes

        radio_type = radio.get("radio_type")
        if not isinstance(radio_type, str):
            return attributes

        attributes.update(
            self.coordinator.get_radio_channel_metadata(
                self._platform_type,
                radio_type,
                radio.get("oper_chan"),
            )
        )
        return attributes

    @property
    def suggested_object_id(self) -> str:
        return self._radio_object_id

    def _get_radio(self) -> dict[str, Any] | None:
        for ap in self.coordinator.data.get("results", []):
            if ap.get("serial") != self._serial:
                continue

            for radio in ap.get("radio", []):
                if radio.get("radio_id") == self._radio_id:
                    return radio

        return None

    @property
    def native_value(self) -> str | int | float | None:
        radio = self._get_radio()
        if radio is None:
            return None

        value = radio.get(self._field)

        if self._field == "noise_floor" and value == 0:
            return None

        if isinstance(value, (str, int, float)):
            return value

        return None


class FortiGateAPMetric(FortiGateChangedCoordinatorSensor):
    """Represent a numeric AP-level metric."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        ap: dict[str, Any],
        field: str,
        label: str,
        icon: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        suggested_unit: str | None = None,
    ) -> None:
        super().__init__(coordinator)

        self._serial = ap["serial"]
        self._field = field

        self._attr_unique_id = f"{self._serial}_{field}"
        self._attr_name = label
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_suggested_unit_of_measurement = suggested_unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
        )
        self._attr_extra_state_attributes = {
            "fortios_kd_metric": field,
            "fortios_kd_scope": "ap",
        }

    def _get_ap(self) -> dict[str, Any] | None:
        for ap in self.coordinator.data.get("results", []):
            if ap.get("serial") == self._serial:
                return ap

        return None

    @property
    def native_value(self) -> str | int | float | None:
        ap = self._get_ap()
        if ap is None:
            return None

        value = ap.get(self._field)

        if isinstance(value, bool):
            return "Enabled" if value else "Disabled"

        if isinstance(value, (str, int, float)):
            return value

        return None


class FortiGateARPMetric(FortiGateChangedCoordinatorSensor):
    """Represent one field from an ARP-table device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        mac: str,
        fortigate_serial: str,
        fortigate_hostname: str,
        field: str,
        label: str,
        icon: str,
        *,
        mask_mac: bool,
        mask_hostname: bool,
        unit: str | None = None,
    ) -> None:
        """Initialize an ARP-table entity."""
        super().__init__(coordinator)

        self._mac = mac
        self._field = field
        self._mask_mac = mask_mac
        self._mask_hostname = mask_hostname
        arp_identifier = f"{fortigate_serial}_arp_{mac}"
        displayed_mac = mask_client_mac(mac) if mask_mac else mac

        self._attr_unique_id = f"{fortigate_serial}_arp_{mac}_{field}"
        self._attr_name = label
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_extra_state_attributes = {
            "fortios_kd_entry_type": "arp_entry",
            "fortios_kd_arp_field": field,
            "fortios_kd_match_id": _dashboard_match_id(fortigate_serial, mac),
        }
        device_info = DeviceInfo(
            identifiers={(DOMAIN, arp_identifier)},
            name=f"ARP Device {displayed_mac} ({fortigate_hostname})",
            via_device=(DOMAIN, fortigate_serial),
        )
        self._attr_device_info = device_info

    def _entries(self) -> list[dict[str, Any]]:
        """Return the current ARP bindings for this device."""
        return self.coordinator.get_arp_entries(self._mac)

    def _ip_conflicts(self) -> list[dict[str, Any]]:
        """Return different MACs currently claiming this device's IPs."""
        conflicts: dict[tuple[str, str], dict[str, Any]] = {}

        for entry in self._entries():
            ip_address = entry.get("ip")
            if not isinstance(ip_address, str) or not ip_address:
                continue

            claimants: list[tuple[str, dict[str, Any]]] = []
            if self.coordinator.match_arp_wifi_clients:
                claimants.extend(
                    ("wifi_client", claimant)
                    for claimant in self.coordinator.get_wifi_clients_by_ip(ip_address)
                )
            claimants.extend(
                ("arp", claimant)
                for claimant in self.coordinator.get_arp_entries_by_ip(ip_address)
            )

            for source, claimant in claimants:
                claimant_mac = normalize_mac_address(claimant.get("mac"))
                if claimant_mac is None or claimant_mac == self._mac:
                    continue

                key = (ip_address, claimant_mac)
                conflict = conflicts.setdefault(
                    key,
                    {
                        "ip_address": ip_address,
                        "mac_address": (
                            mask_client_mac(claimant_mac)
                            if self._mask_mac
                            else claimant_mac
                        ),
                        "sources": [],
                    },
                )
                if source not in conflict["sources"]:
                    conflict["sources"].append(source)

                hostname = claimant.get("hostname")
                if isinstance(hostname, str) and hostname:
                    conflict["hostname"] = (
                        mask_client_hostname(hostname)
                        if self._mask_hostname
                        else hostname
                    )

        return list(conflicts.values())

    @property
    def available(self) -> bool:
        """Return whether this MAC is currently in the ARP table."""
        return super().available and bool(self._entries())

    @property
    def native_value(self) -> str | int | float | None:
        """Return the selected ARP field, aggregating duplicate MAC rows."""
        entries = self._entries()
        if not entries:
            return None

        if self._field == "mac_address":
            return mask_client_mac(self._mac) if self._mask_mac else self._mac

        if self._field == "wifi_client_match":
            client = self.coordinator.get_wifi_client(self._mac)
            if client is None:
                return "Not currently detected"

            hostname = client.get("hostname")
            if isinstance(hostname, str) and hostname:
                return (
                    mask_client_hostname(hostname) if self._mask_hostname else hostname
                )
            return "Connected"

        if self._field == "ip_conflict":
            return "Possible conflict" if self._ip_conflicts() else "Clear"

        if self._field == "ip_addresses":
            values = {
                value
                for entry in entries
                if isinstance((value := entry.get("ip")), str) and value
            }
            return ", ".join(sorted(values)) or None

        if self._field == "interfaces":
            values = {
                value
                for entry in entries
                if isinstance((value := entry.get("interface")), str) and value
            }
            return ", ".join(sorted(values)) or None

        if self._field == "vdoms":
            values = {
                value
                for entry in entries
                if isinstance((value := entry.get("vdom")), str) and value
            }
            return ", ".join(sorted(values)) or None

        if self._field == "age":
            ages: list[float] = []
            for entry in entries:
                try:
                    ages.append(float(entry["age"]))
                except KeyError, TypeError, ValueError:
                    continue
            if not ages:
                return None
            age = min(ages)
            return int(age) if age.is_integer() else age

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return claimant details for possible IP conflicts."""
        attributes = dict(self._attr_extra_state_attributes)
        if self._field != "ip_conflict":
            return attributes

        conflicts = self._ip_conflicts()
        attributes.update(
            {
                "conflict_count": len(conflicts),
                "conflicting_claimants": conflicts,
            }
        )
        return attributes


class FortiGateWiFiClientCoordinatorEntity(FortiGateChangedCoordinatorSensor):
    """Represent a Wi-Fi client that suppresses unchanged state writes."""


class FortiGateWiFiClientMAC(FortiGateWiFiClientCoordinatorEntity):
    """Represent a connected Wi-Fi client."""

    _attr_has_entity_name = True
    _attr_name = "MAC address"
    _attr_icon = "mdi:network-outline"

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        client: dict[str, Any],
        fortigate_serial: str,
        fortigate_hostname: str,
        should_mask: bool,
    ) -> None:
        super().__init__(coordinator)

        self._mac = client["mac"].lower()
        client_identifier = f"{fortigate_serial}_wifi_client_{self._mac}"
        displayed_mac = mask_client_mac(self._mac) if should_mask else self._mac

        self._attr_unique_id = f"{client_identifier}_mac_address"
        self._attr_native_value = displayed_mac
        self._attr_extra_state_attributes = {
            "fortios_kd_entry_type": "wifi_client",
            "fortios_kd_match_id": _dashboard_match_id(
                fortigate_serial,
                self._mac,
            ),
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client_identifier)},
            name=f"Wifi Client {displayed_mac} ({fortigate_hostname})",
            via_device=(DOMAIN, fortigate_serial),
        )

    def _get_client(self) -> dict[str, Any] | None:
        return self.coordinator.get_wifi_client(self._mac)

    @property
    def available(self) -> bool:
        return super().available and self._get_client() is not None


class FortiGateWiFiClientLastKnownMAC(SensorEntity):
    """Represent the last known MAC address of a wifi client."""

    _attr_has_entity_name = True
    _attr_name = "Last Known MAC"
    _attr_icon = "mdi:network-outline"

    def __init__(
        self,
        client: dict[str, Any],
        fortigate_serial: str,
        should_mask: bool,
    ) -> None:
        """Initialize the last known MAC sensor."""
        mac = client["mac"].lower()
        client_identifier = f"{fortigate_serial}_wifi_client_{mac}"

        self._attr_unique_id = f"{client_identifier}_last_known_mac"
        self._attr_native_value = mask_client_mac(mac) if should_mask else mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client_identifier)},
        )


class FortiGateWiFiClientMetric(FortiGateWiFiClientCoordinatorEntity):
    """Represent a Wi-Fi client field."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        client: dict[str, Any],
        fortigate_serial: str,
        field: str,
        label: str,
        icon: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        suggested_unit: str | None = None,
        should_mask: bool = False,
    ) -> None:
        super().__init__(coordinator)

        self._mac = client["mac"].lower()
        self._field = field
        self._should_mask = should_mask
        client_identifier = f"{fortigate_serial}_wifi_client_{self._mac}"

        self._attr_unique_id = f"{client_identifier}_{field}"
        self._attr_name = label
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_suggested_unit_of_measurement = suggested_unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client_identifier)},
            via_device=(DOMAIN, fortigate_serial),
        )

    def _get_client(self) -> dict[str, Any] | None:
        return self.coordinator.get_wifi_client(self._mac)

    @property
    def native_value(self) -> Any:
        client = self._get_client()
        if client is None:
            return None

        value = client.get(self._field)

        if self._field == "association_time":
            try:
                return dt_util.utc_from_timestamp(int(value))
            except TypeError, ValueError:
                return None

        if self._should_mask:
            if self._field == "wtp_name" and isinstance(value, str):
                return mask_name(value)
            if self._field == "hostname" and isinstance(value, str):
                return mask_client_hostname(value)
            if self._field == "ssid" and isinstance(value, str):
                return mask_ssid(value)
            if self._field == "vlan_id" and isinstance(value, (str, int)):
                return mask_vlan_id(value)

        if isinstance(value, (str, int, float)):
            return value

        return None

    @property
    def available(self) -> bool:
        return super().available and self._get_client() is not None


class FortiGateWiFiClientIPAddress(FortiGateWiFiClientMetric):
    """Represent a wifi client's current or ARP-derived IP address."""

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        client: dict[str, Any],
        fortigate_serial: str,
    ) -> None:
        """Initialize the wifi-client IP address entity."""
        super().__init__(
            coordinator,
            client,
            fortigate_serial,
            "ip",
            "IP Address",
            "mdi:ip",
        )

    def _arp_ip_addresses(self) -> list[str]:
        """Return current ARP addresses for this client's MAC."""
        if not self.coordinator.match_arp_wifi_clients:
            return []
        return sorted(
            {
                ip_address
                for entry in self.coordinator.get_arp_entries(self._mac)
                if isinstance((ip_address := entry.get("ip")), str) and ip_address
            }
        )

    @property
    def native_value(self) -> str | None:
        """Prefer the wifi-client IP and fall back to current ARP bindings."""
        client = self._get_client()
        if client is not None:
            ip_address = client.get("ip")
            if isinstance(ip_address, str) and ip_address:
                return ip_address

        arp_ip_addresses = self._arp_ip_addresses()
        return ", ".join(arp_ip_addresses) or None

    @property
    def available(self) -> bool:
        """Remain available while either endpoint knows about this client."""
        return self.coordinator.last_update_success and (
            self._get_client() is not None or bool(self._arp_ip_addresses())
        )


class FortiGateWiFiClientLastKnownHostname(
    FortiGateWiFiClientCoordinatorEntity, RestoreEntity
):
    """Retain the most recently reported hostname for a wifi client."""

    _attr_has_entity_name = True
    _attr_name = "Last Known Hostname"
    _attr_icon = "mdi:form-textbox"

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        client: dict[str, Any],
        fortigate_serial: str,
        should_mask: bool,
    ) -> None:
        """Initialize the last known hostname sensor."""
        super().__init__(coordinator)

        self._mac = client["mac"].lower()
        self._should_mask = should_mask
        self._last_known_hostname: str | None = None
        client_identifier = f"{fortigate_serial}_wifi_client_{self._mac}"

        self._attr_unique_id = f"{client_identifier}_last_known_hostname"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client_identifier)},
        )

    def _current_hostname(self) -> str | None:
        """Return the client's current valid hostname."""
        client = self.coordinator.get_wifi_client(self._mac)
        if client is None:
            return None

        hostname = client.get("hostname")
        if (
            isinstance(hostname, str)
            and hostname
            and hostname.casefold() not in {"none", "unknown", "unavailable"}
        ):
            return mask_client_hostname(hostname) if self._should_mask else hostname

        return None

    async def async_added_to_hass(self) -> None:
        """Restore the last hostname after a Home Assistant restart."""
        await super().async_added_to_hass()

        if self._current_hostname() is not None:
            return

        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.state
            and last_state.state.casefold() not in {"none", "unknown", "unavailable"}
        ):
            self._last_known_hostname = last_state.state

    @property
    def native_value(self) -> str | None:
        """Return the current hostname or the most recently reported one."""
        if (hostname := self._current_hostname()) is not None:
            self._last_known_hostname = hostname

        return self._last_known_hostname

    @property
    def available(self) -> bool:
        """Remain available whenever a hostname has been learned."""
        return (
            self._current_hostname() is not None
            or self._last_known_hostname is not None
        )


class FortiGateWiFiClientSource(FortiGateWiFiClientMetric):
    """Represent the FortiGate that reported a wifi client."""

    def __init__(
        self,
        coordinator: FortiOSKDCoordinator,
        client: dict[str, Any],
        fortigate_serial: str,
        fortigate_hostname: str,
    ) -> None:
        """Initialize the FortiGate source entity."""
        super().__init__(
            coordinator,
            client,
            fortigate_serial,
            "fortigate",
            "FortiGate",
            "mdi:shield-home",
        )
        self._fortigate_hostname = fortigate_hostname

    @property
    def native_value(self) -> str:
        """Return the source FortiGate hostname."""
        return self._fortigate_hostname


def create_arp_entities(
    coordinator: FortiOSKDCoordinator,
    mac: str,
    fortigate_serial: str,
    fortigate_hostname: str,
    mask_mac: bool,
    mask_hostname: bool = False,
) -> list[SensorEntity]:
    """Create the diagnostic entities belonging to one ARP-table device."""
    common = (
        coordinator,
        mac,
        fortigate_serial,
        fortigate_hostname,
    )
    options = {
        "mask_mac": mask_mac,
        "mask_hostname": mask_hostname,
    }
    return [
        FortiGateARPMetric(
            *common,
            "mac_address",
            "ARP MAC Address",
            "mdi:network-outline",
            **options,
        ),
        FortiGateARPMetric(
            *common,
            "ip_addresses",
            "ARP IP Addresses",
            "mdi:ip-network",
            **options,
        ),
        FortiGateARPMetric(
            *common,
            "interfaces",
            "ARP Interfaces",
            "mdi:lan-connect",
            **options,
        ),
        FortiGateARPMetric(
            *common,
            "age",
            "ARP Age",
            "mdi:timer-outline",
            unit=UnitOfTime.MINUTES,
            **options,
        ),
        FortiGateARPMetric(
            *common,
            "vdoms",
            "ARP VDOMs",
            "mdi:server-network",
            **options,
        ),
        *(
            [
                FortiGateARPMetric(
                    *common,
                    "wifi_client_match",
                    "WiFi Client Match",
                    "mdi:wifi-check",
                    **options,
                )
            ]
            if coordinator.match_arp_wifi_clients
            else []
        ),
        FortiGateARPMetric(
            *common,
            "ip_conflict",
            "IP Conflict",
            "mdi:shield-alert-outline",
            **options,
        ),
    ]


def create_wifi_client_entities(
    coordinator: FortiOSKDCoordinator,
    client: dict[str, Any],
    fortigate_serial: str,
    fortigate_hostname: str,
    masking: dict[str, bool],
) -> list[SensorEntity]:
    """Create every entity belonging to one Wi-Fi client."""
    normalized_mac = normalize_mac_address(client.get("mac"))
    if normalized_mac is None:
        return []
    if client.get("mac") != normalized_mac:
        client = {**client, "mac": normalized_mac}

    return [
        FortiGateWiFiClientMAC(
            coordinator,
            client,
            fortigate_serial,
            fortigate_hostname,
            masking["mac"],
        ),
        FortiGateWiFiClientLastKnownMAC(
            client,
            fortigate_serial,
            masking["mac"],
        ),
        FortiGateWiFiClientLastKnownHostname(
            coordinator,
            client,
            fortigate_serial,
            masking["hostname"],
        ),
        FortiGateWiFiClientSource(
            coordinator,
            client,
            fortigate_serial,
            fortigate_hostname,
        ),
        FortiGateWiFiClientIPAddress(coordinator, client, fortigate_serial),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "wtp_name",
            "AP Name",
            "mdi:access-point",
            should_mask=masking["wtp_name"],
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "wtp_id",
            "AP ID",
            "mdi:identifier",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "wtp_radio",
            "AP Radio",
            "mdi:radio-tower",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "wtp_ip",
            "AP IP",
            "mdi:ip-network",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "vap_name",
            "VAP Name",
            "mdi:wifi-cog",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "ssid",
            "SSID",
            "mdi:wifi",
            should_mask=masking["ssid"],
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "os",
            "Operating System",
            "mdi:devices",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "hostname",
            "Hostname",
            "mdi:form-textbox",
            should_mask=masking["hostname"],
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "data_rate_bps",
            "Data Rate",
            "mdi:speedometer",
            unit=UnitOfDataRate.BITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit=UnitOfDataRate.MEGABITS_PER_SECOND,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "bandwidth_rx",
            "RX Bandwidth",
            "mdi:download-network",
            unit=UnitOfDataRate.BITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit=UnitOfDataRate.MEGABITS_PER_SECOND,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "bandwidth_tx",
            "TX Bandwidth",
            "mdi:upload-network",
            unit=UnitOfDataRate.BITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit=UnitOfDataRate.MEGABITS_PER_SECOND,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "snr",
            "SNR",
            "mdi:signal",
            unit=SIGNAL_STRENGTH_DECIBELS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "idle_time",
            "Radio Idle Time",
            "mdi:timer-outline",
            unit=UnitOfTime.SECONDS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "association_time",
            "Association Time",
            "mdi:clock-outline",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "channel",
            "Channel",
            "mdi:radio-tower",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "signal",
            "Signal",
            "mdi:signal",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "noise",
            "Noise",
            "mdi:signal-distance-variant",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "radio_type",
            "Radio Type",
            "mdi:wifi-cog",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "mimo",
            "MIMO",
            "mdi:antenna",
        ),
        FortiGateWiFiClientMetric(
            coordinator,
            client,
            fortigate_serial,
            "vlan_id",
            "VLAN ID",
            "mdi:lan",
            should_mask=masking["vlan_id"],
        ),
    ]
