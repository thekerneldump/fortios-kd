# Changelog

Notable changes and deliberate compatibility, security, and privacy decisions
are recorded here for each release.

## 0.7.3-beta.1 - 2026-09-22

Debugging release for [issue #11](https://github.com/thekerneldump/fortios-kd/issues/11).

- Adds opt-in capture of malformed API responses. Users can collect either 100
  bytes before and after the invalid data or the complete response, with a
  configurable capture limit that defaults to three.
- Captures are kept in memory, redact serial numbers, and can be extracted with
  Home Assistant's **Download diagnostics** action. Full responses may still
  contain private network information and should be reviewed before sharing.
- Repairs isolated invalid UTF-8 bytes when the resulting response remains valid
  JSON. Wi-Fi response failures no longer make VDOMs and unrelated data
  unavailable.

## 0.7.2 - 2026-09-21

### Added

- Add optional FortiGate detected-device inventory synchronization. Detected
  devices expose hostname, MAC and master MAC, IPv4 and IPv6 addresses,
  interface, operating system, hardware vendor/type/family/version, software
  version, identification sources, and relative last-seen time.
- Add OUI-derived vendor diagnostics using Home Assistant's packaged IEEE
  database. A separate assessment identifies conservative conflicts between
  the OUI-derived vendor and a FortiGuard-sourced vendor without replacing the
  FortiGate classification.
- Add **Recently seen**, **Stale**, **Inventory changes**, and **Last inventory
  change** diagnostics. Inventory changes retain field names and a timestamp
  without storing the previous potentially sensitive values.
- Add exact-MAC detected-device matches to ARP, DHCP, and wifi-client devices.
  Inventory hostnames can serve as a lower-priority fallback labeled **(Device
  Info)** when no better hostname source is available.
- Add a **KD Device Table** dashboard strategy with FortiGate, hardware vendor,
  hardware type, hardware family, operating system, software version,
  interface, and relative last-seen filters. Last-seen filtering supports both
  less-than and more-than choices from one hour through one year.
- Add optional interface synchronization for physical and VLAN interfaces in
  every available VDOM. Interface devices expose name, alias, IPv4 address,
  prefix length, link state, speed, duplex, VLAN ID, parent interface, and
  calculated TX/RX bit, byte, packet, and error rates.
- Add an editable **Preferred name** to every interface. It initially follows
  the FortiGate interface alias, or the interface name when no alias exists. A
  Home Assistant override remains in place until the alias changes on the
  FortiGate, at which point the new alias is applied once.
- Add a **KD Interface Graphs** dashboard strategy. Graphs are ordered as TX/RX
  Mbps, TX/RX MB/s, TX/RX packet rate, and TX/RX error rate. Filters cover
  FortiGate, link state, observed speed/duplex, and parent interface; layouts
  can combine matching interfaces by rate or separate them by firewall. Time
  ranges extend from 30 minutes through one week and default to one hour.
- Add independent dashboard switches for hiding hardware-switch members and
  logical Wi-Fi SSID interfaces while retaining interface-kind diagnostics.

### Changed

- Use each interface's Preferred name in interface graph legends. All-firewall
  views include the FortiGate and VDOM; single-firewall and separated layouts
  omit the redundant FortiGate name for shorter legends.
- Display interface data rates in both networking-oriented Mbps and storage-
  oriented MB/s views, with Mbps graphs shown first.
- Refresh interface counters and aliases on the normal coordinator interval,
  cache the larger detected-device inventory for five minutes, and suppress
  unchanged interface state writes to reduce Recorder and WebSocket activity.

### Compatibility

- Keep detected-device and interface synchronization disabled by default so an
  upgrade does not unexpectedly create large device and entity inventories.
- Continue using Home Assistant 2025.12-compatible device relationships rather
  than requiring the newer subdevice API.
- Automatically fall back to requesting interfaces one VDOM at a time when a
  FortiOS build cannot return all VDOM interfaces in one monitor request.

## 0.7.1 - 2026-09-20

### Added

- Add independent time-span pickers to the **KD VDOM Resources** and **KD Wifi
  Graphs** dashboards. Available views are 1 week, 1 day, 12 hours, 6 hours,
  3 hours, 1 hour, and 30 minutes. Each dashboard defaults to 1 hour, and its
  selection applies to every graph on that dashboard.

### Changed

- Stop reporting an individual DNS server's latency when FortiGate has not
  updated the measurement for more than one hour. The **Last tested** diagnostic
  remains available, preventing stale timeout penalties from appearing as
  current latency.

### Fixed

- Restore the **Unavailable Clients** filter on the **KD Wifi Clients**
  dashboard. Disconnected clients are now discovered through their durable
  **Last Known MAC** entities, while their current MAC entities determine
  connection availability.

## 0.7.0 - 2026-09-19

### Added

- Add an editable **Preferred name** configuration entity to each FortiGate.
  Bundled dashboards use it for FortiGate labels, graph legends, and firewall
  filters without renaming the underlying Home Assistant device.
- Add VDOM-scoped DNS server devices from global DNS configuration and optional
  per-VDOM overrides. Runtime DNS observations enrich configured devices with
  latency and last-tested diagnostics but do not create unconfigured devices.
  Each DNS device is linked through its VDOM using the Home Assistant
  2025.12-compatible device relationship and provides IP address, VDOM,
  configuration source, and configured role. VDOM devices also expose a DNS
  server summary entity. Add configured DNS-server latency to the **KD VDOM
  Resources** dashboard, with preferred FortiGate names in combined legends
  and compact IP-only legends when filtered to one firewall or grouped into
  separate VDOM cards.

## 0.6.0 - 2026-09-19

### Added

- Discover all configured FortiGate VDOMs and represent each as a separate
  connected device associated with its FortiGate, with a Management VDOM
  diagnostic indicating the VDOM selected by the global FortiOS configuration.
  This uses Home Assistant's established device relationship so installations
  still running Home Assistant 2025.12 remain supported; it does not use the
  newer child-device API. Also expose one diagnostic VDOM-name sensor per
  configured VDOM directly on the FortiGate device so the inventory remains
  visible when its connected-device list contains many ARP, DHCP, wifi-client,
  or FortiAP devices.
- Add per-VDOM CPU usage, memory usage, active session count, and session usage
  percentage sensors from `/monitor/system/vdom-resource?vdom=*`. Resource
  collection is isolated so an unavailable endpoint does not interrupt the
  integration's primary wifi polling.
- Add a **KD VDOM Resources** community dashboard strategy with 24-hour graphs,
  cascading Firewall and VDOM filters, and a layout selector that can combine
  all matching VDOMs into one graph per resource or show separate cards grouped
  by VDOM.

### Changed

- Refresh the detected FortiOS version from every normal API response. Firmware
  upgrades are reflected by the firmware entity immediately, and ARP collection
  switches between the FortiOS 6.4+ REST API and the configured FortiOS 6.2
  SNMPv2c fallback without waiting for an integration reload.
- Retain previously configured SNMPv2c ARP settings while ARP synchronization
  remains enabled, allowing a runtime downgrade from FortiOS 6.4+ to 6.2 to
  switch back to SNMP immediately. If the settings are missing or fail, create
  a fixable Home Assistant Repair that validates replacement settings without
  exposing the community value in the issue or logs.

## 0.5.0 - 2026-09-18

### Added

- Add a **KD DHCP Entries** community dashboard strategy with independent,
  cascading FortiGate and Interface filters, current lease diagnostics, and
  direct links to DHCP, FortiGate, and matched wifi-client devices.
- Add a Hostname column to the KD ARP Table. It identifies managed access points
  by board MAC or same-FortiGate management IP before preferring a live
  wifi-client hostname, a current exact-MAC DHCP hostname, then the wifi
  client's Last Known Hostname. Displayed values identify their **AP**, **WiFi**,
  or **DHCP** source, and a neighboring Lease type column identifies current
  DHCP matches as **Reserved** or **Leased**.
- Add independent, cascading Firewall, Interface, and Lease type filters to the
  KD ARP Table, including a **No DHCP lease** choice.
- Add an explicitly version-gated FortiOS 6.2 SNMPv2c ARP fallback. It resolves
  interface indices through `IF-MIB::ifName`, reads IPv4/MAC bindings from
  `IP-MIB::ipNetToMediaPhysAddress`, validates the community during setup, and
  feeds the existing ARP devices and dashboards. FortiOS 6.4+ continues to use
  the REST monitor API.
- Add optional per-FortiGate DHCP lease synchronization through
  `/monitor/system/dhcp`. Leases are represented as separate devices grouped by
  MAC, with IP, hostname, interface, status, assignment type, expiration,
  address type, server ID, and exact wifi-client match diagnostics.
- Add an **IP Assigned By** wifi-client diagnostic reporting **DHCP Reserved**,
  **DHCP**, or **Static or Unknown** from the current exact-MAC/IP lease match.

### Hostname and network identity improvements

This release correlates AP, wifi-client, ARP, and DHCP observations instead of
treating each source as an isolated value. Hostnames use a defined precedence
and fallback order so missing data from one source does not leave an otherwise
identifiable device unnamed. The dashboards show whether a displayed hostname
came from an AP, a wifi client, or DHCP so that the result remains predictable
and its source is visible.

ARP entries also gain assignment context from exact-MAC DHCP and wifi-client
matches. This distinguishes dynamic leases from reservations, shows when an ARP
observation matches a known wireless client, and makes discrepancies between
the independently collected data easier to investigate without treating an IP
address as device identity.

When Home Assistant Recorder is configured to retain these entities, its state
history can preserve earlier ARP addresses and DHCP lease details. That history
can help identify a device's previous IP after an outage or large reconnect and
expose gaps in DHCP reservation coverage. Historical availability depends on
the user's Recorder inclusion and retention settings; FortiOS KD does not
maintain a separate historical archive or reverse-search index.

## 0.4.0 - 2026-09-17

### Added

- Add FortiGate ARP-table collection and diagnostic MAC, IP-address, interface,
  age, and VDOM entities for each discovered network device.
- Keep ARP entries as separate per-FortiGate Home Assistant devices so they can
  be independently selected for ARP-focused dashboards.
- Populate a wifi client's IP Address entity from exact-MAC ARP bindings when
  the wifi-client endpoint does not currently provide an address.
- Add a reverse WiFi Client Match diagnostic to ARP devices so an exact-MAC
  client association can be inspected from either side.
- Add an IP Conflict diagnostic for different MACs simultaneously claiming an
  ARP device's IP in current wifi-client or ARP data. This can expose overlapping
  DHCP scopes, multiple DHCP servers, static collisions, stale data, or spoofing
  without treating an IP address as device identity.
- Add per-FortiGate settings for opting into ARP synchronization and separately
  controlling ARP-to-wifi client matching. ARP synchronization defaults off to
  avoid unexpectedly creating large numbers of devices.
- Add an auto-populating KD ARP Entries community dashboard for current ARP
  devices, including direct links to the ARP device and its FortiGate.
- Add a compact KD ARP Table community dashboard with IP, interface, and MAC
  columns plus direct links to ARP devices and exact wifi-client matches.

### Changed

- Load all four community dashboard strategies through one cache-busted frontend
  module and register the Wifi graph strategy before graph-card setup.
- Suppress unchanged AP, radio, ARP, and wifi-client coordinator state writes,
  reducing websocket traffic during the 30-second polling cycle.
- Use the FortiGate-provided `monitor/wifi/meta` band-spectrum map when
  classifying FortiAP radios instead of relying only on a partial hardcoded
  list. The metadata is loaded once per integration setup and reused for all
  radio entities.
- Use `monitor/wifi/ap-names` to match managed FortiAP serial prefixes to their
  model and platform type. Channel capabilities are then requested once for
  each installed platform and cached for the life of the coordinator.
- Expose the FortiAP model on AP devices and supported channel widths plus DFS
  status on radio channel entities when the FortiGate supplies that metadata.

### Fixed

- Restore KD ARP Table wifi-client links by joining ARP and wifi-client
  entities with an opaque exact-match identifier; Home Assistant's frontend
  display registry intentionally omits entity unique IDs.
- Prevent intermittent community-dashboard strategy timeouts caused by partial
  frontend registration or unsupported constructable stylesheet APIs.
- Prevent ARP MAC-address entities from appearing as Wifi clients by using
  explicit dashboard entry-type metadata instead of generated entity IDs.
- Create radio entities for every radio type reported by the FortiGate metadata,
  including additional 2.4 GHz and 5 GHz variants that were previously omitted.

### Compatibility

- Retain the complete shared radio-type map returned by FortiOS 6.2.17 and
  6.4.16 as a built-in fallback. Both EOL releases returned the same map during
  testing, so integrations continue to classify radios if the metadata endpoint
  is unavailable or inaccessible.
- Treat `ap-names` as the FortiGate firmware's supported-model catalog rather
  than a list of installed APs, and query `ap_channels` only for models matched
  to currently managed AP serial numbers. Allowed channels and DFS markers are
  intentionally not hardcoded because they may vary by regulatory context.
- Do not request `/monitor/network/arp` on FortiOS 6.2 because Fortinet did not
  add that monitor endpoint until FortiOS 6.4. When explicitly configured, 6.2
  obtains IPv4 ARP bindings through SNMPv2c instead. An unavailable API or SNMP
  ARP source does not block the integration's primary wifi update.

## 0.3.0 - 2026-09-16

### Added

- Add an automatically populated Wifi graph community dashboard with shared
  FortiGate, AP, and SSID filters.
- Add automatically discovered AP client, CPU, free-memory, and total-memory
  history graphs.
- Add 2.4 GHz and 5 GHz graphs for channels, channel utilization, noise floor,
  RX/TX MAC errors, RX/TX MAC error rates, calculated throughput, and
  FortiGate-reported bandwidth.
- Add an automatically registered community dashboard strategy for Home
  Assistant 2026.5 and newer, while retaining the editable YAML dashboard.
- Add optional per-FortiGate device organization using a selected or automatically
  created Home Assistant area, or a reusable/automatically created label.
- Add an existing-label picker while retaining the option to create a new label.
- Add registry-backed area and label filters to the Wifi client dashboard.
- Add opt-in propagation when a hub or AP changes area while preserving devices
  that users manually moved elsewhere.
- Add opt-in synchronization of AP label additions and removals to currently
  associated wifi clients while preserving unrelated client labels.
- Add opt-in propagation of FortiGate label additions and removals to all APs
  and wifi clients managed by that hub, with an explicit broad-change warning.

### Changed

- Render Wifi client and graph dashboard contents in the browser instead of
  using large server-side templates, reducing Home Assistant event-loop work
  and making filter changes react immediately.
- Use indexed wifi-client lookups and avoid rewriting unchanged client entity
  states during coordinator refreshes.
- Show only AP names in graph legends and arrange them as two aligned columns,
  including cards that Home Assistant renders lazily while scrolling.

### Fixed

- Register both community-dashboard frontend modules directly so either
  dashboard strategy loads independently.
- Recognize the FortiOS 6.2 `802.11ac` radio type as 5 GHz so its radio metrics
  and graphs are created.

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
