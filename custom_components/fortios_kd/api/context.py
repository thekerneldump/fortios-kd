"""Shared FortiOS API context."""

from dataclasses import dataclass

from .version import FortiOSVersion, version_family


@dataclass(slots=True)
class FortiOSApiContext:
    """Store information shared by all API modules."""

    version: FortiOSVersion | None = None
    version_text: str | None = None

    def matches_version(self, family: str) -> bool:
        """Return whether the detected version belongs to a version family."""
        if self.version is None:
            raise RuntimeError("FortiOS version has not been detected")

        return version_family(self.version, family)
