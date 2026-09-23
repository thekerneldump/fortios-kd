"""Bounded, opt-in capture of malformed FortiOS API responses."""

from copy import deepcopy
from datetime import UTC, datetime
import re
from typing import Any

DEBUG_CAPTURE_MODE_CONTEXT = "invalid_context"
DEBUG_CAPTURE_MODE_FULL = "full_response"
DEBUG_CONTEXT_BYTES = 100
REDACTED = "**REDACTED**"

_SERIAL_JSON_PATTERN = re.compile(
    r'(?i)("(?:serial|serial_number|serial-number)"\s*:\s*")[^"]*'
)


class FortiOSDebugCaptureStore:
    """Keep a bounded number of malformed responses in memory."""

    def __init__(self, *, enabled: bool, mode: str, limit: int) -> None:
        """Initialize the capture store."""
        self.enabled = enabled
        self.mode = (
            mode
            if mode in {DEBUG_CAPTURE_MODE_CONTEXT, DEBUG_CAPTURE_MODE_FULL}
            else DEBUG_CAPTURE_MODE_CONTEXT
        )
        self.limit = max(1, limit)
        self._fortigate_serial: str | None = None
        self._captures: list[dict[str, Any]] = []

    @property
    def count(self) -> int:
        """Return the number of stored captures."""
        return len(self._captures)

    @property
    def limit_reached(self) -> bool:
        """Return whether the configured capture limit has been reached."""
        return self.count >= self.limit

    def set_fortigate_serial(self, serial: str) -> None:
        """Set the FortiGate serial that must be redacted from diagnostics."""
        self._fortigate_serial = serial

    def capture(
        self,
        *,
        endpoint: str,
        http_status: int,
        body: bytes,
        encoding: str,
        error: UnicodeDecodeError | ValueError,
        byte_start: int,
        byte_end: int,
        repaired_data: Any | None,
    ) -> int | None:
        """Store one malformed response and return its one-based number."""
        if not self.enabled or self.limit_reached:
            return None

        capture_number = self.count + 1
        record: dict[str, Any] = {
            "captured_at": datetime.now(UTC).isoformat(),
            "endpoint": endpoint,
            "http_status": http_status,
            "capture_number": capture_number,
            "capture_limit": self.limit,
            "mode": self.mode,
            "error": {
                "type": type(error).__name__,
                "encoding": encoding,
                "start": byte_start,
                "end": byte_end,
                "reason": str(getattr(error, "reason", error)),
            },
        }

        if self.mode == DEBUG_CAPTURE_MODE_FULL:
            if repaired_data is not None:
                record["response"] = self._redact_value(repaired_data)
            else:
                record["response_text_with_replacement"] = self._redact_text(
                    body.decode(encoding, errors="replace")
                )
        else:
            context_start = max(0, byte_start - DEBUG_CONTEXT_BYTES)
            context_end = min(len(body), byte_end + DEBUG_CONTEXT_BYTES)
            context = self._redact_bytes(body[context_start:context_end], encoding)
            record["response_context"] = {
                "start": context_start,
                "end": context_end,
                "text_with_replacement": self._redact_text(
                    context.decode(encoding, errors="replace")
                ),
                "hex": context.hex(" "),
            }

        self._captures.append(record)
        return capture_number

    def diagnostics(self) -> dict[str, Any]:
        """Return a detached diagnostics snapshot."""
        return {
            "capture_enabled": self.enabled,
            "capture_mode": self.mode,
            "capture_limit": self.limit,
            "capture_count": self.count,
            "capture_limit_reached": self.limit_reached,
            "privacy_warning": (
                "Debug responses may contain IP addresses, MAC addresses, "
                "hostnames, usernames, and SSIDs. FortiGate serial-number "
                "fields are redacted."
            ),
            "captures": deepcopy(self._captures),
        }

    def _redact_text(self, value: str) -> str:
        """Redact serial fields and the known FortiGate serial from text."""
        redacted = _SERIAL_JSON_PATTERN.sub(rf"\1{REDACTED}", value)
        if self._fortigate_serial:
            redacted = redacted.replace(self._fortigate_serial, REDACTED)
        return redacted

    def _redact_bytes(self, value: bytes, encoding: str) -> bytes:
        """Redact the known FortiGate serial without losing byte diagnostics."""
        if not self._fortigate_serial:
            return value
        serial = self._fortigate_serial.encode(encoding, errors="ignore")
        if not serial:
            return value
        return value.replace(serial, b"*" * len(serial))

    def _redact_value(self, value: Any) -> Any:
        """Recursively redact serial-number fields from parsed JSON."""
        if isinstance(value, dict):
            return {
                key: (
                    REDACTED
                    if str(key).casefold()
                    in {"serial", "serial_number", "serial-number"}
                    else self._redact_value(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_value(item) for item in value]
        if isinstance(value, str):
            return self._redact_text(value)
        return value
