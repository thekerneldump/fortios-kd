"""Read the FortiOS 6.2 ARP table over SNMPv2c."""

from collections.abc import AsyncIterator
from typing import Any

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    UdpTransportTarget,
    bulk_walk_cmd,
    is_end_of_mib,
)

from homeassistant.components.snmp import async_get_snmp_engine
from homeassistant.core import HomeAssistant

IF_NAME_OID = (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 1)
IP_NET_TO_MEDIA_PHYS_ADDRESS_OID = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)


class SnmpArpError(Exception):
    """Indicate that the FortiOS 6.2 SNMP ARP walk failed."""


def _oid_tuple(oid: Any) -> tuple[int, ...]:
    """Return an SNMP object name as an integer tuple."""
    if hasattr(oid, "asTuple"):
        return tuple(int(part) for part in oid.asTuple())
    return tuple(int(part) for part in str(oid).strip(".").split("."))


def _oid_suffix(oid: Any, base_oid: tuple[int, ...]) -> tuple[int, ...] | None:
    """Return the portion of an OID following the expected table prefix."""
    oid_parts = _oid_tuple(oid)
    if oid_parts[: len(base_oid)] != base_oid:
        return None
    return oid_parts[len(base_oid) :]


def _value_text(value: Any) -> str:
    """Return an SNMP value's display text."""
    if hasattr(value, "prettyPrint"):
        return str(value.prettyPrint())
    return str(value)


def _normalize_mac_address(value: str) -> str | None:
    """Return a lowercase colon-delimited MAC address when valid."""
    compact = value.strip().casefold().replace(":", "").replace("-", "")
    compact = compact.replace(".", "")
    if len(compact) != 12 or compact in {"0" * 12, "f" * 12}:
        return None
    try:
        int(compact, 16)
    except ValueError:
        return None
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


class FortiOSKDSnmpArpClient:
    """Walk the legacy IPv4 ARP MIB exposed by FortiOS 6.2."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        community: str,
        port: int = 161,
        timeout: int = 5,
    ) -> None:
        """Initialize an SNMPv2c ARP client."""
        self._hass = hass
        self._host = host
        self._port = port
        self._timeout = timeout
        self._auth_data = CommunityData(community, mpModel=1)

    async def _async_walk(self, base_oid: tuple[int, ...]) -> AsyncIterator[Any]:
        """Yield every variable binding below one numeric OID."""
        try:
            target = await UdpTransportTarget.create(
                (self._host, self._port),
                timeout=self._timeout,
                retries=1,
            )
            engine = await async_get_snmp_engine(self._hass)
            walker = bulk_walk_cmd(
                engine,
                self._auth_data,
                target,
                ContextData(),
                0,
                50,
                ObjectType(ObjectIdentity(".".join(map(str, base_oid)))),
                lexicographicMode=False,
            )
            async for error_indication, error_status, error_index, var_binds in walker:
                if error_indication:
                    raise SnmpArpError(str(error_indication))
                if error_status:
                    location = (
                        var_binds[int(error_index) - 1][0]
                        if error_index and var_binds
                        else "?"
                    )
                    raise SnmpArpError(
                        f"{error_status.prettyPrint()} at {location}"
                    )
                if is_end_of_mib(var_binds):
                    return
                for oid, value in var_binds:
                    yield oid, value
        except PySnmpError as err:
            raise SnmpArpError(str(err)) from err

    async def async_get_arp_table(self) -> dict[str, Any]:
        """Return SNMP ARP rows in the monitor/network/arp representation."""
        interfaces: dict[int, str] = {}
        async for oid, value in self._async_walk(IF_NAME_OID):
            suffix = _oid_suffix(oid, IF_NAME_OID)
            if suffix is None or len(suffix) != 1:
                continue
            interface_name = _value_text(value).strip()
            if interface_name:
                interfaces[suffix[0]] = interface_name

        entries: list[dict[str, Any]] = []
        async for oid, value in self._async_walk(IP_NET_TO_MEDIA_PHYS_ADDRESS_OID):
            suffix = _oid_suffix(oid, IP_NET_TO_MEDIA_PHYS_ADDRESS_OID)
            if suffix is None or len(suffix) != 5:
                continue

            try:
                mac_octets = value.asOctets()
            except AttributeError:
                continue
            mac = _normalize_mac_address(mac_octets.hex())
            if mac is None:
                continue

            interface_index, *ip_octets = suffix
            if any(octet < 0 or octet > 255 for octet in ip_octets):
                continue
            entries.append(
                {
                    "ip": ".".join(str(octet) for octet in ip_octets),
                    "mac": mac,
                    "interface": interfaces.get(
                        interface_index,
                        f"ifIndex {interface_index}",
                    ),
                    "source": "snmp",
                }
            )

        return {
            "results": entries,
            "supported": True,
            "source": "snmp",
        }
