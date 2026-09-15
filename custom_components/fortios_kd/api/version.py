"""FortiOS version parsing and comparison."""

from dataclasses import dataclass
import re

_VERSION_PATTERN = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$"
)


@dataclass(frozen=True, order=True, slots=True)
class FortiOSVersion:
    """Represent a FortiOS software version."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> FortiOSVersion:
        """Parse a FortiOS version such as v6.4.16."""
        match = _VERSION_PATTERN.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid FortiOS version: {value!r}")

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )

def version_family(version: FortiOSVersion, family: str) -> bool:
    """Return whether a FortiOS version belongs to a version family."""
    normalized_family = family.strip().removeprefix("v")

    if re.fullmatch(r"\d+(?:\.\d+){0,2}", normalized_family) is None:
        raise ValueError(f"Invalid FortiOS version family: {family!r}")

    family_parts = tuple(int(part) for part in normalized_family.split("."))
    version_parts = (version.major, version.minor, version.patch)

    return version_parts[: len(family_parts)] == family_parts
