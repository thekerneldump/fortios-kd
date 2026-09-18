"""Tests for the FortiOS 6.2 SNMP ARP reader."""

from collections.abc import AsyncIterator
from typing import Any

from homeassistant.core import HomeAssistant


class _ObjectName:
    """Provide the pysnmp ObjectName behavior used by the parser."""

    def __init__(self, value: tuple[int, ...]) -> None:
        self._value = value

    def asTuple(self) -> tuple[int, ...]:
        """Return the numeric OID."""
        return self._value


class _Value:
    """Provide text and octet SNMP value representations."""

    def __init__(self, *, text: str = "", octets: bytes = b"") -> None:
        self._text = text
        self._octets = octets

    def prettyPrint(self) -> str:
        """Return display text."""
        return self._text

    def asOctets(self) -> bytes:
        """Return raw octets."""
        return self._octets


async def test_snmp_arp_rows_are_converted_to_monitor_format(
    hass: HomeAssistant,
) -> None:
    """Test IF-MIB and IP-MIB walks produce API-compatible ARP rows."""
    from custom_components.fortios_kd.snmp_arp import (  # noqa: PLC0415
        IF_NAME_OID,
        IP_NET_TO_MEDIA_PHYS_ADDRESS_OID,
        FortiOSKDSnmpArpClient,
    )

    client = FortiOSKDSnmpArpClient(hass, "192.0.2.1", "readonly")

    async def walk(base_oid: tuple[int, ...]) -> AsyncIterator[tuple[Any, Any]]:
        if base_oid == IF_NAME_OID:
            yield _ObjectName((*IF_NAME_OID, 13)), _Value(text="iot_vlan")
            return
        yield _ObjectName(
            (*IP_NET_TO_MEDIA_PHYS_ADDRESS_OID, 13, 192, 0, 2, 45)
        ), _Value(octets=bytes.fromhex("02000000002d"))

    client._async_walk = walk  # type: ignore[method-assign]  # noqa: SLF001

    assert await client.async_get_arp_table() == {
        "results": [
            {
                "ip": "192.0.2.45",
                "mac": "02:00:00:00:00:2d",
                "interface": "iot_vlan",
                "source": "snmp",
            }
        ],
        "supported": True,
        "source": "snmp",
    }


async def test_snmp_arp_uses_interface_index_fallback(
    hass: HomeAssistant,
) -> None:
    """Test an unknown interface index remains identifiable."""
    from custom_components.fortios_kd.snmp_arp import (  # noqa: PLC0415
        IF_NAME_OID,
        IP_NET_TO_MEDIA_PHYS_ADDRESS_OID,
        FortiOSKDSnmpArpClient,
    )

    client = FortiOSKDSnmpArpClient(hass, "192.0.2.1", "readonly")

    async def walk(base_oid: tuple[int, ...]) -> AsyncIterator[tuple[Any, Any]]:
        if base_oid == IF_NAME_OID:
            return
        yield _ObjectName(
            (*IP_NET_TO_MEDIA_PHYS_ADDRESS_OID, 99, 192, 0, 2, 46)
        ), _Value(octets=bytes.fromhex("02000000002e"))

    client._async_walk = walk  # type: ignore[method-assign]  # noqa: SLF001

    result = await client.async_get_arp_table()

    assert result["results"][0]["interface"] == "ifIndex 99"
