# FortiOS KD

FortiOS KD is an unofficial Home Assistant custom integration for locally polling
Fortinet FortiGate firewalls through their REST API.

The project is in alpha. It currently focuses on read-only visibility into
FortiGate-managed access points and their connected wifi clients. FortiOS KD is
an independent community project and is not affiliated with or endorsed by
Fortinet or the Home Assistant project.

Release changes and deliberate compatibility, security, and privacy decisions
are recorded in the [changelog](CHANGELOG.md).

## Features

- Configure one or more FortiGate hubs through the Home Assistant UI.
- Communicate directly with each FortiGate over local HTTPS.
- Detect the FortiOS version and expose it in Home Assistant.
- Apply version-specific API compatibility behavior. FortiOS 6.2 has dedicated
  response enrichment for fields that moved in later releases.
- Represent the FortiGate, managed access points, and wifi clients as Home
  Assistant devices and entities.
- Represent FortiGate ARP-table entries as separate network devices, using the
  monitor API on FortiOS 6.4+ and an optional SNMPv2c fallback on FortiOS 6.2,
  with exact-MAC diagnostics linking them to wifi clients.
- Optionally represent current FortiGate DHCP leases as separate network
  devices, preserving multiple leases for the same MAC and linking exact-MAC
  wifi clients in both directions.
- Optionally synchronize FortiGate detected-device inventory as compact linked
  devices, including identity, hostname and discovery source, IPv4/IPv6,
  interface, OS, hardware classification, software version, last-seen time,
  recent/stale status, and inventory-change diagnostics.
- Optionally represent physical and VLAN interfaces from every VDOM as linked
  devices, including addressing, link details, VLAN relationships, and
  calculated traffic, packet, and error rates.
- Represent effective DNS servers as VDOM-scoped devices, including global
  configuration, per-VDOM overrides, latency, and last-tested time.
- Poll all hubs through Home Assistant `DataUpdateCoordinator` instances.
- Keep disconnected client entities available for troubleshooting, with their
  live measurements marked unavailable.
- Retain Last Known MAC and Last Known Hostname sensors after a client
  disconnects and across Home Assistant restarts.
- Create shared FortiGate, access point, and SSID dashboard filters
  automatically.
- Provide an editable FortiGate Preferred name for dashboard labels and filters
  without changing the Home Assistant device name.
- Optionally include configured but unassigned SSIDs in the SSID filter.
- Mask sensitive values for screenshots, screen sharing, training, and demos.

Development has been exercised with FortiOS 6.2.17 and 6.4.16. Fortinet changes
API endpoints and response fields between FortiOS releases, so other versions
may require additional compatibility handling.

## Available data

FortiOS KD currently provides information in the following areas.

### FortiGate

- Hostname and model when provided by the installed FortiOS version
- Serial number
- FortiOS version

### Access points

- Name, serial number, VDOM, AP profile, status, and FortiAP version
- Connection source, interface, uplink type, and uplink speed
- Board MAC, join time, uptime, CPU usage, and memory
- Connected-client count
- Radio band, channel, SSIDs, TX power, noise floor, and channel utilization
- Radio RX/TX totals, calculated rates, FortiGate bandwidth values, and MAC
  errors

### Wifi clients

- MAC address, IP address, hostname, operating system, and source FortiGate
- Access point name, ID, radio, and IP address
- VAP name, SSID, VLAN ID, radio type, MIMO, channel, signal, noise, and SNR
- Data rate, RX/TX bandwidth, radio idle time, and association time
- Last Known MAC and Last Known Hostname values for disconnected clients

### ARP table

- MAC address, IPv4 address or addresses, interface, and—when supplied by the
  source—age and VDOM
- Multiple ARP bindings for one MAC are combined under one Home Assistant device
- ARP entries remain separate devices so they can be used independently in
  ARP-focused dashboards
- A wifi client's existing IP Address entity prefers the live wifi-client value
  and falls back to current ARP addresses matched by MAC when that value is absent
- Each ARP device has a WiFi Client Match diagnostic showing the currently
  matched client hostname, or whether no wifi client is currently detected
- The KD ARP Table hostname column first matches managed access points by board
  MAC, with their management IP as a same-FortiGate fallback. It then prefers a
  live wifi-client hostname, a current exact-MAC DHCP hostname, the
  detected-device inventory hostname, and finally the client's Last Known
  Hostname. Displayed values identify their **AP**, **WiFi**, **DHCP**, or
  **Device Info** source. A neighboring **Lease type** column reports
  **Reserved** or **Leased** for current DHCP matches. Dedicated cascading
  filters narrow the table by Firewall, Interface, and Lease type; lease choices
  include rows with no current DHCP lease. When device inventory syncing is
  enabled, a final icon opens the exact-MAC detected-device match.
- An IP Conflict diagnostic flags a different current MAC claiming the same IP
  in wifi-client or ARP data. Possible causes include overlapping DHCP scopes,
  multiple DHCP servers, static-address collisions, stale records, or spoofing.
  It is an anomaly warning and does not merge or identify devices by IP.

The `/monitor/network/arp` endpoint is not available on FortiOS 6.2. For that
release family only, enabling ARP synchronization opens a separate SNMPv2c
configuration step and reads `IF-MIB::ifName` plus
`IP-MIB::ipNetToMediaPhysAddress`. The SNMP table supplies IPv4, MAC, and
interface data but not the API's age or VDOM fields, so those diagnostics remain
unavailable on 6.2. FortiOS 6.4 and newer continue to use the REST monitor API
and never use the stored SNMP settings.

ARP synchronization is disabled by default and can be enabled independently for
each configured FortiGate. Wifi-client matching is a separate per-hub option;
disabling it keeps ARP devices and ARP-to-ARP conflict detection while removing
wifi matching and ARP fallback from wifi-client IP entities.

### FortiOS 6.2 SNMP requirements

FortiOS KD supports SNMP only as the ARP-table transport for FortiOS 6.2. It is
not a general SNMP monitoring feature and is not used on 6.4 or later.

- Enable read-only SNMPv2c queries on the FortiGate and apply the configuration.
- Restrict the community's allowed manager host to the Home Assistant address.
- Permit UDP 161 from Home Assistant to the FortiGate management interface.
- Enter that community and port in the version-gated **Configure FortiOS 6.2
  ARP access** step.

SNMPv2c does not encrypt its community or payload. Use it only on a trusted
management network, use a dedicated read-only community, and do not reuse a
sensitive password. The community is stored in the Home Assistant config entry
like the FortiGate API key.

### DHCP leases

- MAC address, IP address or addresses, hostname or hostnames, interface,
  status, address type, server ID, assignment type, and latest expiration
- Multiple DHCP leases for one MAC are combined under one Home Assistant device
  without treating an IP address as device identity
- Each DHCP device has a WiFi Client Match diagnostic based on an exact MAC
  match
- Wifi-client devices gain an **IP Assigned By** diagnostic when DHCP syncing is
  enabled. It reports **DHCP Reserved** for a matching reserved lease, **DHCP**
  for another matching lease, or **Static or Unknown** when the client's current
  IP has no matching lease.
- When a DHCP lease has no hostname, an exact-MAC detected-device hostname is
  used as a fallback and labeled **(Device Info)**.

DHCP synchronization is disabled by default and can be enabled independently
for each FortiGate. If the endpoint is unavailable or the API account lacks
permission, DHCP entities remain unavailable without blocking wifi monitoring.

### Detected-device inventory

- Exact FortiGate-scoped MAC matches enrich ARP, DHCP, and wifi-client device
  metadata with the detected hardware manufacturer, family or type, hardware
  version, and software version.
- A separate **OUI-derived vendor** diagnostic resolves globally assigned MAC
  prefixes from Home Assistant's packaged IEEE database. It does not replace
  FortiGuard's vendor classification and does not require an external lookup.
  Locally administered or randomized MAC addresses may not have an OUI vendor.
- **Vendor identification assessment** reports **FortiGuard identification may
  be wrong** when a FortiGuard-sourced vendor conflicts with the normalized OUI
  vendor. It reports agreement or why comparison was unavailable otherwise.
- ARP, DHCP, and wifi-client devices gain a **Detected Device Match** diagnostic
  with the inventory hostname, IPv4/IPv6 addresses, interface, OS, and hardware
  classification. Dashboard links open the matching detected-device object
  without merging the independent devices.
- Each detected device exposes **Recently seen** or **Stale** using a rolling
  one-hour threshold. **Inventory changes** and **Last inventory change** retain
  the latest changed field names and timestamp without storing the previous
  potentially sensitive values.
- Both IPv4 and IPv6 addresses are indexed for correlation. IPv6 is exposed now
  and can be reused by a future neighbor-table feature without treating an IP
  address as persistent device identity.

### Interfaces

- Physical and VLAN interfaces from every returned VDOM are represented as
  devices linked to their FortiGate. Device identity includes both VDOM and
  interface name so repeated interface names remain distinct.
- Interface diagnostics include name, alias, IPv4 address, prefix length, link
  state, negotiated speed, duplex, VLAN ID, and parent interface when FortiOS
  supplies those fields.
- Each interface has an editable **Preferred name** used by interface graph
  legends. It is initially populated from the FortiGate interface alias, or the
  interface name when no alias exists. A Home Assistant override is preserved
  across refreshes and restarts; it is replaced only after the alias changes on
  the FortiGate, at which point the new alias is applied once.
- TX/RX packet, byte, bit, and error rates are calculated from successive
  cumulative counters. Bit rates are the byte-rate delta multiplied by eight.
  The first sample after setup or a counter reset remains unavailable until a
  valid delta can be calculated.
- Byte rates use bytes per second as their native unit and request megabytes per
  second as Home Assistant's default display unit. Bit rates use bits per second
  and request megabits per second. Packet and error rates use per-second units.

Interface synchronization is disabled by default and can be enabled independently
for each FortiGate. The endpoint is explicitly queried with `include_vlan=true`
and `vdom=*`. Some FortiOS builds reject that monitor request with a duplicate
`Etag` error. FortiOS KD detects that response once and automatically falls back
to requesting each configured VDOM separately.

### VDOMs and DNS servers

- Each configured VDOM is represented as a device connected to its FortiGate
  using Home Assistant's established `via_device` relationship.
- Each effective DNS server is represented as a separate device connected
  through its VDOM. The DNS device identity includes both VDOM and IP address,
  so the same inherited server remains distinguishable in different VDOMs.
- DNS devices expose IP address, VDOM, configuration source, configured role,
  current latency in milliseconds, and the calculated last-tested timestamp.
- A DNS latency measurement becomes unavailable when FortiGate reports that it
  was last updated more than one hour ago. The Last tested timestamp remains
  available so stale timeout penalties are not presented as current latency.
- Configuration source reports **Global** or **VDOM override**, while configured
  role reports **Primary** or **Secondary**. Runtime latency entries enrich
  matching configured servers but do not independently create devices.
- Each VDOM device exposes a **DNS servers** summary entity in addition to the
  connected DNS-server devices.

Global DNS configuration is refreshed every five minutes. Runtime latency is
polled with the normal coordinator interval. DNS endpoint failures are isolated
from wifi polling; configuration and latency diagnostics become unavailable
independently rather than unloading the integration.

Some fields are absent on particular FortiOS or FortiAP versions. Those entities
may be unavailable when the firewall does not provide the underlying value.

## Installation with HACS

FortiOS KD is currently installed as a custom HACS repository.

1. Open HACS in Home Assistant.
2. Select **Integrations**.
3. Open the three-dot menu and choose **Custom repositories**.
4. Enter `https://github.com/thekerneldump/fortios-kd` as the repository.
5. Select **Integration** as the category and add the repository.
6. Find **FortiOS KD** in HACS and install it.
7. Restart Home Assistant.
8. Open **Settings > Devices & services > Add integration** and select
   **FortiOS KD**.

## Manual installation

Copy `custom_components/fortios_kd` from this repository into the
`custom_components` directory under your Home Assistant configuration directory,
then restart Home Assistant.

## FortiGate API account and permissions

Create a dedicated FortiGate REST API administrator. Do not reuse a full
administrator account or API key.

The access profile needs read access to these FortiGate permission groups:

| Permission group | Access | Used for |
| --- | --- | --- |
| System (`sysgrp`) | Read | System status, firmware details, model, hostname, DNS configuration, VDOM resources, and optional DHCP leases and interface statistics |
| Network (`netgrp`) | Read | ARP table on FortiOS 6.4 and newer, plus DNS latency |
| Wifi Controller (`wifi`) | Read | Managed APs, clients, VAPs, and WTP profiles |

The REST API access profile does not provide the FortiOS 6.2 ARP table. That
version instead requires the separate read-only SNMPv2c configuration described
above.

Use a **global** access-profile scope so the required monitor and configuration
endpoints are not blocked by VDOM-scoped permissions. Limit the REST API
administrator to the required VDOMs and configure trusted hosts wherever
possible. FortiOS KD does not require read-write permission.

The integration currently reads these API resources:

- `/api/v2/monitor/system/status`
- `/api/v2/monitor/system/firmware` on versions that require it
- `/api/v2/monitor/system/dhcp` when DHCP lease synchronization is enabled
- `/api/v2/monitor/system/interface?include_vlan=true&vdom=*` when interface synchronization is enabled
- `/api/v2/monitor/user/device` when detected-device synchronization is enabled
- `/api/v2/monitor/system/vdom-resource?vdom=*`
- `/api/v2/cmdb/system/global` on versions that require it
- `/api/v2/cmdb/system/vdom?vdom=*`
- `/api/v2/cmdb/system/dns?vdom=<management-vdom>`
- `/api/v2/cmdb/system/vdom-dns?vdom=*` when multiple VDOMs are configured
- `/api/v2/monitor/network/arp` on FortiOS 6.4 and newer
- `/api/v2/monitor/network/dns/latency?vdom=*`
- `/api/v2/monitor/wifi/managed_ap`
- `/api/v2/monitor/wifi/client`
- `/api/v2/monitor/wifi/meta`
- `/api/v2/monitor/wifi/ap-names`
- `/api/v2/monitor/wifi/ap_channels` for managed FortiAP models
- `/api/v2/cmdb/wireless-controller/vap`
- `/api/v2/cmdb/wireless-controller/wtp-profile`

FortiOS configuration commands and GUI labels vary by release. Verify the final
profile with `show full-configuration system accprofile` and confirm that
`sysgrp`, `netgrp`, and `wifi` are set to read access.

## Configuration

When adding a FortiGate, provide:

- **Hostname or IP address:** Do not include `https://`.
- **Port:** The HTTPS administrative port, normally `443` unless customized.
- **API key:** The key belonging to the dedicated REST API administrator.
- **Verify SSL certificate:** Enable this when the FortiGate presents a
  certificate trusted by Home Assistant.
- **Request timeout:** Maximum time to wait for each FortiGate API request.
  The default is 60 seconds, and the allowed range is 5–300 seconds.
- **Include unassigned SSIDs in filters:** Include every configured VAP in the
  SSID filter instead of only SSIDs assigned through active WTP profiles.
- **Sync ARP table devices:** Create and maintain diagnostic devices for current
  ARP entries. FortiOS 6.4+ uses the REST API. FortiOS 6.2 opens a separate,
  clearly labeled SNMPv2c configuration and validation step.
- **Match ARP entries with wifi clients:** Enable exact-MAC ARP/wifi links and
  ARP fallback for wifi-client IP entities.
- **Sync DHCP lease devices:** Create and maintain diagnostic devices for
  current DHCP leases and add exact-MAC assignment diagnostics to wifi clients.
- **Sync detected device inventory:** Create compact diagnostic devices from
  FortiGate device identification. Each device exposes its selected inventory
  fields on a details entity plus proper last-seen, recent/stale, and inventory
  change diagnostics. Inventory hostnames are used only when a more direct
  hostname source is unavailable.
  The larger inventory endpoint is refreshed every five minutes to avoid
  generating hundreds of rapidly changing last-seen states.
- **Sync interface devices and rates for all VDOMs:** Create linked interface
  devices from the FortiOS monitor endpoint, include VLAN interfaces, and
  calculate packet, byte, and error rates from counter deltas.

### Areas and labels

Each FortiGate can optionally organize its devices using a Home Assistant area,
label, both, or neither:

- **Area:** Select an existing area or enter a new area name for the integration
  to create. You can also assign the FortiGate's APs and wifi clients to that area,
  move still-managed devices when the FortiGate moves, and move clients with an AP
  when its area changes. Devices manually moved away from the previously managed
  area are left alone.
- **Label:** Select an existing label or enter a new label name to apply to the
  FortiGate, APs, and wifi clients. The picker avoids accidentally creating a
  misspelled duplicate. A typed name reuses an exact existing match or creates a
  label using the selected color; existing labels keep their current color. An
  additional opt-in setting synchronizes labels added to or removed from an AP
  with its currently associated wifi clients while preserving unrelated
  client-only labels. A separate opt-in setting propagates labels added to or
  removed from the FortiGate device to all of its managed APs and wifi clients.

AP-to-client synchronization only removes the specific labels removed from the
AP. For example, if an AP has the label `Upstairs` and a phone connected to it
has both `Upstairs` and `Family member`, removing `Upstairs` from the AP removes
only `Upstairs` from the phone. The client-only `Family member` label remains.
This allows labels identifying a person, device purpose, or ownership to coexist
with location labels inherited from an AP.

> **Warning:** When FortiGate label propagation is enabled, changing a label on
> the FortiGate device intentionally updates every AP and wifi client managed by
> that hub. Removing a FortiGate label also removes that label from those managed
> devices, even if the same label was manually assigned to one of them. Leave the
> propagation option disabled if FortiGate, AP, or client labels should be managed
> independently.

Area assignment is optional. Entities inherit their device's area unless an entity
has been assigned its own area in Home Assistant. Switching to label organization
does not erase existing area assignments.

Additional FortiGates can be added by repeating the integration setup. The
detected FortiOS version is displayed when an existing hub is reconfigured.
Invalid or insufficient API credentials are reported in the configuration form
without replacing the previously working key.

The included Wifi client dashboard provides FortiGate, AP, SSID, area, and label
filters. Area and label choices come from the Home Assistant device registry, so
they also cover retained client devices that are currently unavailable.

## Preferred dashboard names

Each FortiGate device exposes a **Preferred name** configuration entity. Change
it from the FortiGate device page to choose the name shown by FortiOS KD's
bundled dashboards, firewall filters, and VDOM graph legends. The preference is
local to the integration: it does not rename the Home Assistant device or alter
the FortiGate hostname. Clearing the value restores the device-name fallback.

## Privacy masking

Privacy controls are configured independently for each FortiGate hub:

- **Mask serial numbers:** Preserve only the final four characters.
- **Mask SSIDs:** Preserve the first two characters and a recognized band suffix.
- **Mask client MAC addresses:** Preserve the OUI and mask the device-specific
  half.
- **Mask client hostnames:** Preserve the first four characters. For names with a
  dash, preserve the portion before the dash and mask the remainder.
- **Mask client VLAN IDs:** Mask every digit.
- **Mask AP names:** Preserve a recognizable prefix and suffix on longer names.

Reconfiguring privacy controls reloads that FortiGate hub so its entities are
recreated with the new display values. Newly observed values in last-known
identity sensors follow the same MAC and hostname masking settings.

Masking is a point-in-time display feature intended to reduce accidental
disclosure while navigating dashboards, sharing screenshots, or recording
demonstrations. It is not anonymization and does not rewrite Home Assistant's
entity registry, device identifiers, recorder history, backups, or stored restore
state. Home Assistant history and Last Known Hostname restore state may still
contain values recorded before masking was enabled, so avoid opening entity
details or history while sharing a screen that may contain older private data.

Short device names of eight characters or fewer are currently left unchanged.
For client hostnames containing a dash, the complete portion before the first
dash remains visible. A stronger masking strategy is being designed in
[issue #3](https://github.com/thekerneldump/fortios-kd/issues/3).

## Wifi client dashboard filters

FortiOS KD creates these shared select entities:

- `select.wifi_client_fortigate_filter`
- `select.wifi_client_ap_filter`
- `select.wifi_client_ssid_filter`
- `select.wifi_client_area_filter`
- `select.wifi_client_label_filter`

Selecting a FortiGate limits the AP and SSID choices to that hub. The SSID filter
also includes **Unavailable Clients**, which displays clients that are no longer
reported as associated. Their Last Known MAC remains available immediately. Last
Known Hostname begins retaining a value after FortiOS KD observes that client
with a valid hostname.

The Wifi client dashboard requires the
[auto-entities](https://github.com/thomasloven/lovelace-auto-entities) and
[layout-card](https://github.com/thomasloven/lovelace-layout-card) frontend
cards, both of which can be installed through HACS.

### Community dashboards

On Home Assistant 2026.5 or newer, FortiOS KD registers eight community
dashboard strategies automatically. After restarting Home Assistant, open
**Settings > Dashboards**, select **Add dashboard**, and choose:

- **FortiOS KD Wifi Clients** for searchable client cards. Its suggested title
  is **KD Wifi Clients** and its suggested URL is `kd-wifi-clients`.
- **FortiOS KD Wifi Graphs** for automatically discovered radio throughput and
  health graphs. An independent Time span picker offers 1 week, 1 day, 12 hours,
  6 hours, 3 hours, 1 hour, and 30 min views, defaulting to 1 hour. Its suggested
  title is **KD Wifi Graphs** and its suggested URL is `kd-wifi-graphs`.
- **FortiOS KD ARP Entries** for current ARP-table devices and their optional
  wifi-client match and IP-conflict diagnostics. Its suggested title is
  **KD ARP Entries** and its suggested URL is `kd-arp-entries`.
- **FortiOS KD ARP Table** for a compact, filterable table of current IP
  addresses, interfaces, MAC addresses, sourced hostnames, and lease types,
  with direct links to ARP devices, exactly matched wifi clients, and detected
  device inventory. Its
  Firewall, Interface, and Lease type filters are independent of the Wifi
  dashboard filters. Its suggested title is **KD ARP Table** and its suggested
  URL is `kd-arp-table`.
- **FortiOS KD Device Table** for a compact table of FortiGate-detected device
  hostnames, IP and MAC addresses, operating systems, hardware vendors, hardware
  types, hardware families, hardware versions, software versions, and relative
  Last seen times (with the exact local timestamp available on hover). The first
  icon opens the
  detected-device object, while an exact FortiGate-scoped MAC match adds an
  icon linking to the corresponding wifi client. Independent filters cover
  FortiGate, hardware vendor, hardware type, hardware family, operating system,
  software version, interface, and rolling Last seen windows of less than or
  more than 1 hour, 1 day, 1 week, 1 month (30 days), or 1 year (365 days). Its
  suggested title is **KD Device Table** and its suggested URL is
  `kd-device-table`.
- **FortiOS KD DHCP Entries** for current DHCP-lease device cards, including
  lease status, reservation type, expiration, server ID, and optional
  wifi-client matches. Its independent FortiGate and Interface filters narrow
  the displayed leases. Its suggested title is **KD DHCP Entries** and its
  suggested URL is `kd-dhcp-entries`.
- **FortiOS KD VDOM Resources** for per-VDOM CPU, memory, active-session,
  session-usage, and configured DNS-server latency history. Its Firewall and
  VDOM filters can display matching VDOMs together for comparison or as
  separate graph groups. Combined DNS legends include the preferred FortiGate
  name when multiple firewalls are visible; filtered and separate-card views
  use the DNS-server IP alone. A Time span picker applies to every graph and
  offers 1 week, 1 day, 12 hours, 6 hours, 3 hours, 1 hour, and 30 min; the
  default is 1 hour. Its suggested title is **KD VDOM Resources** and its
  suggested URL is `kd-vdom-resources`.

  DNS latency stops reporting when FortiGate's measurement is more than one
  hour old, preventing an old timeout penalty from appearing as current
  latency. The DNS-server device retains its Last tested diagnostic.

  **DNS latency legend note:** In the combined all-firewall view, a label such
  as `Firewall name - DNS IP` may be visually truncated when the available
  legend space is narrow. The full label remains available in the graph's hover
  details, and **Separate by VDOM** provides compact IP-only labels. The longer
  combined label is retained because it identifies the firewall unambiguously.
  A future enhancement may assign each configured DNS server a short number so
  combined labels can use a form such as `Firewall name - 1`.
- **FortiOS KD Interface Graphs** for TX/RX packet, data, and error rates across
  physical and VLAN interfaces in every VDOM. Its Firewall filter uses each
  FortiGate's preferred name, while additional live filters narrow the graphs
  by link state, observed speed/duplex combination, or parent interface. Two
  independent switches hide hardware-switch member ports and logical WiFi SSID
  interfaces by default. FortiGate's available-interface metadata identifies
  hardware-switch membership and WiFi interfaces; configured FortiAP VAP names
  provide a fallback for WiFi classification. Disable either switch to include
  that interface class in the graphs.
  Network-style **Mbps** data-rate graphs appear first, followed by **MB/s**
  data-rate graphs, packet rates, and error rates.
  **Combined by rate** puts all matching interfaces on one card per rate with
  `Firewall - VDOM - Interface` legends, shortened to `VDOM - Interface` when
  one firewall is selected. **Separated by firewall** creates one section per
  FortiGate and also uses `VDOM - Interface`. The Time
  span picker offers the same 1 week through 30 minute choices as the VDOM
  resource dashboard and defaults to 1 hour. Its suggested title is **KD
  Interface Graphs** and its suggested URL is `kd-interface-graphs`.

The Wifi client dashboard explicitly excludes ARP devices. The Wifi client and
graph dashboards share the FortiGate, AP, and SSID filter selects. The graph
dashboard includes calculated RX/TX rates, FortiGate-reported bandwidth,
channel utilization, noise floor, and MAC error rates for every discovered 2.4
GHz and 5 GHz radio. Selecting an SSID includes radios that broadcast that SSID;
the plotted values remain totals for the entire radio rather than per-SSID
measurements.

The generated dashboards automatically adapt their columns to the available
screen width. Their configurations remain managed by their strategies; use the
manual dashboard when you want to customize individual cards.

### Manual dashboard

For older Home Assistant releases or a fully editable dashboard, copy the
complete [Wifi client dashboard example](docs/wifi-clients-dashboard.yaml) into
a new dashboard's raw configuration editor.

## Troubleshooting

### Invalid API key or insufficient permissions

Confirm that the API key belongs to the intended REST API administrator, its
trusted-host rules permit the Home Assistant address, and its access profile has
global-scope read access for `sysgrp` and `wifi`.

### Cannot connect

Confirm the host, HTTPS administrative port, certificate-verification setting,
and network path from Home Assistant to the FortiGate.

### Client fields are unavailable

A disconnected client's live entities intentionally become unavailable. Use
Last Known MAC and Last Known Hostname for retained identity. Some connected
clients do not advertise a hostname, so FortiOS may only return a generic device
classification or no hostname at all.

## Goals

- Extend compatibility to FortiOS 6.0 and newer through version-specific API
  handling.
- Cover the FortiOS monitor, configuration, and log APIs that are useful for
  day-to-day Home Assistant visibility and automation.
- Remain screen-share friendly and mobile friendly.

Older FortiGate models are common in home labs, and useful API endpoints are
frequently moved or deprecated between FortiOS trains. Compatibility therefore
needs to be implemented and tested incrementally rather than inferred from the
latest FortiOS documentation.

## License

Copyright © 2026 [thekerneldump](https://github.com/thekerneldump).

FortiOS KD is licensed under the GNU Affero General Public License version 3
only (`AGPL-3.0-only`). See [LICENSE](LICENSE) for the complete terms.

Modified versions that are distributed or made available for users to interact
with over a network must provide the corresponding source under the same
license.
