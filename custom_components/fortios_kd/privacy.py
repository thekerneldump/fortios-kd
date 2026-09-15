"""Privacy helpers for values exposed by FortiOS KD."""


def mask_serial(serial: str) -> str:
    """Mask a serial number except for its final four characters."""
    return "*" * max(0, len(serial) - 4) + serial[-4:]


def mask_name(name: str) -> str:
    """Mask the middle of a device name."""
    if len(name) <= 8:
        return name

    return name[:5] + "*" * (len(name) - 8) + name[-3:]


def mask_ssid(ssid: str) -> str:
    """Mask an SSID while preserving an optional band suffix."""
    name, separator, band = ssid.rpartition(" ")
    if separator and band.casefold() in {"2.4ghz", "5ghz", "6ghz"}:
        return f"{name[:2]}{'*' * max(0, len(name) - 2)} {band}"

    return ssid[:2] + "*" * max(0, len(ssid) - 2)


def mask_client_mac(mac: str) -> str:
    """Keep the OUI and mask the device-specific half."""
    parts = mac.split(":")
    if len(parts) == 6:
        return ":".join([*parts[:3], "**", "**", "**"])

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
