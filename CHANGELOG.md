# Changelog

Notable changes and deliberate compatibility, security, and privacy decisions
are recorded here for each release.

## Unreleased

### Added

- Add optional per-FortiGate device organization using either an existing Home
  Assistant area or a reusable/automatically created label.
- Add opt-in propagation when a hub or AP changes area while preserving devices
  that users manually moved elsewhere.

## 0.2.2 - 2026-09-15

### Security

- Stop writing the complete FortiGate system-status response to Home Assistant's
  INFO log.
- Add a configurable 5–300 second API request timeout, defaulting to 60 seconds.

### Privacy decisions

- Privacy masking remains a point-in-time display aid for screenshots, screen
  sharing, demonstrations, and vendor support. It is not intended to anonymize
  Home Assistant's entity registry, device identifiers, recorder history,
  backups, or internal coordinator data.
- Last Known Hostname may restore a value recorded before hostname masking was
  enabled. This is an accepted limitation of the current display-masking model;
  users should avoid opening entity details or history while sharing a screen.
- Names of eight characters or fewer remain unchanged. Dashed client hostnames
  preserve the portion before the first dash. A stronger optional masking model
  is tracked in [issue #3](https://github.com/thekerneldump/fortios-kd/issues/3).

## 0.2.1 - 2026-09-15

### Added

- Initial AGPL-3.0-only release of FortiOS KD.
