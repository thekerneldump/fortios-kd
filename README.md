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
- Represent FortiGate ARP-table entries as separate network devices on FortiOS
  6.4 and newer, with exact-MAC diagnostics linking them to wifi clients.
- Poll all hubs through Home Assistant `DataUpdateCoordinator` instances.
- Keep disconnected client entities available for troubleshooting, with their
  live measurements marked unavailable.
- Retain Last Known MAC and Last Known Hostname sensors after a client
  disconnects and across Home Assistant restarts.
- Create shared FortiGate, access point, and SSID dashboard filters
  automatically.
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

- MAC address, IPv4 address or addresses, interface, age, and VDOM
- Multiple ARP bindings for one MAC are combined under one Home Assistant device
- ARP entries remain separate devices so they can be used independently in
  ARP-focused dashboards
- A wifi client's existing IP Address entity prefers the live wifi-client value
  and falls back to current ARP addresses matched by MAC when that value is absent
- Each ARP device has a WiFi Client Match diagnostic showing the currently
  matched client hostname, or whether no wifi client is currently detected
- An IP Conflict diagnostic flags a different current MAC claiming the same IP
  in wifi-client or ARP data. Possible causes include overlapping DHCP scopes,
  multiple DHCP servers, static-address collisions, stale records, or spoofing.
  It is an anomaly warning and does not merge or identify devices by IP.

The `/monitor/network/arp` endpoint is not available before FortiOS 6.4. On
FortiOS 6.2, ARP collection is skipped without generating request errors.
ARP synchronization is disabled by default and can be enabled independently for
each configured FortiGate. Wifi-client matching is a separate per-hub option;
disabling it keeps ARP devices and ARP-to-ARP conflict detection while removing
wifi matching and ARP fallback from wifi-client IP entities.

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
| System (`sysgrp`) | Read | System status, firmware details, model, and hostname |
| Network (`netgrp`) | Read | ARP table on FortiOS 6.4 and newer |
| Wifi Controller (`wifi`) | Read | Managed APs, clients, VAPs, and WTP profiles |

Use a **global** access-profile scope so the required monitor and configuration
endpoints are not blocked by VDOM-scoped permissions. Limit the REST API
administrator to the required VDOMs and configure trusted hosts wherever
possible. FortiOS KD does not require read-write permission.

The integration currently reads these API resources:

- `/api/v2/monitor/system/status`
- `/api/v2/monitor/system/firmware` on versions that require it
- `/api/v2/cmdb/system/global` on versions that require it
- `/api/v2/monitor/network/arp` on FortiOS 6.4 and newer
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

On Home Assistant 2026.5 or newer, FortiOS KD registers four community
dashboard strategies automatically. After restarting Home Assistant, open
**Settings > Dashboards**, select **Add dashboard**, and choose:

- **FortiOS KD Wifi Clients** for searchable client cards. Its suggested title
  is **KD Wifi Clients** and its suggested URL is `kd-wifi-clients`.
- **FortiOS KD Wifi Graphs** for automatically discovered radio throughput and
  health graphs. Its suggested title is **KD Wifi Graphs** and its suggested URL
  is `kd-wifi-graphs`.
- **FortiOS KD ARP Entries** for current ARP-table devices and their optional
  wifi-client match and IP-conflict diagnostics. Its suggested title is
  **KD ARP Entries** and its suggested URL is `kd-arp-entries`.
- **FortiOS KD ARP Table** for a compact table of current IP addresses,
  interfaces, and MAC addresses, with direct links to ARP devices and exactly
  matched wifi clients. Its suggested title is **KD ARP Table** and its
  suggested URL is `kd-arp-table`.

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
