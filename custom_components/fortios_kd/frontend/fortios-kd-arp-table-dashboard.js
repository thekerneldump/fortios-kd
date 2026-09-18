const ARP_TABLE_CARD_ELEMENT = "fortios-kd-arp-table";
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-arp-table";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);
const FILTER_ALL = "All";
const FILTER_NO_DHCP_LEASE = "No DHCP lease";

class FortiOSKDARPTableDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD ARP Table",
      icon: "mdi:table-network",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD ARP Table",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDARPTableDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-arp-table",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-arp-table",
    strategyType: "dashboard",
    name: "FortiOS KD ARP Table",
    description:
      "View current FortiGate ARP entries in a compact network table.",
    documentationURL:
      "https://github.com/thekerneldump/fortios-kd#community-dashboards",
  });
}

function registryEntry(registry, id) {
  return registry?.get?.(id) ?? registry?.[id];
}

function registryName(entry, fallback = "") {
  return entry?.name_by_user || entry?.name || fallback;
}

function isCurrent(state) {
  return state && !UNAVAILABLE_STATES.has(state.state);
}

function currentStateValue(hass, entityId) {
  const state = hass.states[entityId];
  return isCurrent(state) ? state.state : undefined;
}

function currentStateValues(state) {
  if (!isCurrent(state)) {
    return [];
  }

  return String(state.state)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function scopedIpKey(fortigateDeviceId, ipAddress) {
  return `${fortigateDeviceId}\u0000${ipAddress}`;
}

function arpTableModel(hass) {
  const selectedFortigate =
    currentStateValue(hass, "select.arp_table_fortigate_filter") || FILTER_ALL;
  const selectedInterface =
    currentStateValue(hass, "select.arp_table_interface_filter") || FILTER_ALL;
  const selectedLeaseType =
    currentStateValue(hass, "select.arp_table_lease_type_filter") || FILTER_ALL;
  const wifiClientsByMatchId = new Map();
  const dhcpHostnamesByMatchId = new Map();
  const dhcpLeaseTypesByMatchId = new Map();
  const accessPointsByMatchId = new Map();
  const accessPointsByScopedIp = new Map();
  const entriesByDevice = new Map();

  for (const state of Object.values(hass.states)) {
    const entity = registryEntry(hass.entities, state.entity_id);
    if (!entity?.device_id) {
      continue;
    }

    if (state.attributes.fortios_kd_entry_type === "wifi_client") {
      const matchId = state.attributes.fortios_kd_match_id;
      const macSuffix = "_mac_address";
      if (matchId && state.entity_id.endsWith(macSuffix)) {
        const base = state.entity_id.slice(0, -macSuffix.length);
        wifiClientsByMatchId.set(matchId, {
          deviceId: entity.device_id,
          available: isCurrent(state),
          hostname: currentStateValue(hass, `${base}_hostname`),
          lastKnownHostname: currentStateValue(
            hass,
            `${base}_last_known_hostname`,
          ),
        });
      }
      continue;
    }

    if (state.attributes.fortios_kd_entry_type === "dhcp_entry") {
      const matchId = state.attributes.fortios_kd_match_id;
      const field = state.attributes.fortios_kd_dhcp_field;
      if (matchId && isCurrent(state)) {
        if (field === "hostnames") {
          dhcpHostnamesByMatchId.set(matchId, state.state);
        } else if (field === "assignment_type") {
          const leaseType =
            state.state === "DHCP Reserved"
              ? "Reserved"
              : state.state === "DHCP"
                ? "Leased"
                : undefined;
          if (leaseType) {
            dhcpLeaseTypesByMatchId.set(matchId, leaseType);
          }
        }
      }
      continue;
    }

    if (state.attributes.fortios_kd_entry_type === "access_point") {
      const device = registryEntry(hass.devices, entity.device_id);
      const field = state.attributes.fortios_kd_ap_field;
      const matchId = state.attributes.fortios_kd_match_id;
      const accessPoint = {
        deviceId: entity.device_id,
        name: registryName(device, "Access Point"),
      };

      if (field === "mac_address" && matchId && isCurrent(state)) {
        accessPointsByMatchId.set(matchId, accessPoint);
      } else if (field === "ip_address" && device?.via_device_id) {
        for (const ipAddress of currentStateValues(state)) {
          accessPointsByScopedIp.set(
            scopedIpKey(device.via_device_id, ipAddress),
            accessPoint,
          );
        }
      }
      continue;
    }

    if (state.attributes.fortios_kd_entry_type !== "arp_entry") {
      continue;
    }

    const field = state.attributes.fortios_kd_arp_field;
    if (!field) {
      continue;
    }

    const entry = entriesByDevice.get(entity.device_id) || {
      deviceId: entity.device_id,
      fields: new Map(),
      matchId: undefined,
    };
    entry.fields.set(field, state);
    if (field === "mac_address") {
      entry.matchId = state.attributes.fortios_kd_match_id;
    }
    entriesByDevice.set(entity.device_id, entry);
  }

  const rows = [];
  for (const entry of entriesByDevice.values()) {
    const macState = entry.fields.get("mac_address");
    if (!isCurrent(macState)) {
      continue;
    }

    const ipState = entry.fields.get("ip_addresses");
    const interfaceState = entry.fields.get("interfaces");
    const matchState = entry.fields.get("wifi_client_match");
    const arpDevice = registryEntry(hass.devices, entry.deviceId);
    const fortigateDevice = registryEntry(
      hass.devices,
      arpDevice?.via_device_id,
    );
    const fortigateName =
      fortigateDevice?.name || registryName(fortigateDevice, "FortiGate");
    const accessPointByMac = entry.matchId
      ? accessPointsByMatchId.get(entry.matchId)
      : undefined;
    const accessPointByIp = arpDevice?.via_device_id
      ? currentStateValues(ipState)
          .map((ipAddress) =>
            accessPointsByScopedIp.get(
              scopedIpKey(arpDevice.via_device_id, ipAddress),
            ),
          )
          .find(Boolean)
      : undefined;
    const accessPoint = accessPointByMac || accessPointByIp;
    const wifiClient =
      isCurrent(matchState) && entry.matchId
        ? wifiClientsByMatchId.get(entry.matchId)
        : undefined;
    const dhcpHostname = entry.matchId
      ? dhcpHostnamesByMatchId.get(entry.matchId)
      : undefined;
    const dhcpLeaseType = entry.matchId
      ? dhcpLeaseTypesByMatchId.get(entry.matchId)
      : undefined;
    const hostname =
      accessPoint?.name
        ? `${accessPoint.name} (AP)`
        : wifiClient?.available && wifiClient.hostname
        ? `${wifiClient.hostname} (WiFi)`
        : dhcpHostname
          ? `${dhcpHostname} (DHCP)`
          : wifiClient?.lastKnownHostname
            ? `(${wifiClient.lastKnownHostname}) (WiFi)`
            : undefined;

    const interfaces = currentStateValues(interfaceState);
    const leaseFilterValue = dhcpLeaseType || FILTER_NO_DHCP_LEASE;
    if (
      (selectedFortigate !== FILTER_ALL &&
        selectedFortigate !== fortigateName) ||
      (selectedInterface !== FILTER_ALL &&
        !interfaces.includes(selectedInterface)) ||
      (selectedLeaseType !== FILTER_ALL &&
        selectedLeaseType !== leaseFilterValue)
    ) {
      continue;
    }

    rows.push({
      deviceId: entry.deviceId,
      fortigateName,
      ipAddress: isCurrent(ipState) ? ipState.state : "—",
      interfaceName: isCurrent(interfaceState) ? interfaceState.state : "—",
      macAddress: macState.state,
      hostname: hostname || "—",
      dhcpLeaseType: dhcpLeaseType || "—",
      wifiDeviceId: wifiClient?.deviceId,
    });
  }

  rows.sort((left, right) =>
    left.ipAddress.localeCompare(right.ipAddress, undefined, { numeric: true }),
  );

  return {
    rows,
    signature: rows
      .flatMap((row) => [
        row.deviceId,
        row.ipAddress,
        row.interfaceName,
        row.macAddress,
        row.hostname,
        row.dhcpLeaseType,
        row.wifiDeviceId || "",
      ])
      .concat([selectedFortigate, selectedInterface, selectedLeaseType])
      .join("\u001e"),
  };
}

function iconLink(deviceId, icon, label) {
  const link = document.createElement("a");
  link.className = "device-link";
  link.href = `/config/devices/device/${deviceId}`;
  link.title = label;
  link.setAttribute("aria-label", label);

  const haIcon = document.createElement("ha-icon");
  haIcon.icon = icon;
  link.append(haIcon);
  return link;
}

function textCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

class FortiOSKDARPTable extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = config;
    this._signature = undefined;
    this._renderIfReady();
  }

  set hass(hass) {
    this._hass = hass;
    this._renderIfReady();
  }

  getCardSize() {
    return Math.max(1, Math.ceil((this._rowCount || 0) / 4));
  }

  _renderIfReady() {
    if (!this._hass || !this._config) {
      return;
    }

    const model = arpTableModel(this._hass);
    if (model.signature === this._signature) {
      return;
    }

    this._signature = model.signature;
    this._rowCount = model.rows.length;
    this._render(model.rows);
  }

  _render(rows) {
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      ha-card {
        overflow: hidden;
      }
      .table-wrapper {
        overflow-x: auto;
      }
      table {
        border-collapse: collapse;
        width: 100%;
      }
      th,
      td {
        border-bottom: 1px solid var(--divider-color);
        padding: 10px 12px;
        text-align: left;
        white-space: nowrap;
      }
      th {
        color: var(--secondary-text-color);
        font-size: 0.875rem;
        font-weight: 500;
      }
      tbody tr:last-child td {
        border-bottom: 0;
      }
      .icon-cell {
        padding-inline: 8px;
        text-align: center;
        width: 40px;
      }
      .device-link {
        align-items: center;
        color: var(--primary-color);
        display: inline-flex;
        justify-content: center;
        min-height: 32px;
        min-width: 32px;
        text-decoration: none;
      }
      .empty {
        color: var(--secondary-text-color);
        padding: 16px;
      }
    `;

    const card = document.createElement("ha-card");
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent =
        "No current ARP entries match the selected filters.";
      card.append(empty);
      this.shadowRoot.replaceChildren(style, card);
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "table-wrapper";
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    for (const label of [
      "Device",
      "IP address",
      "Interface",
      "MAC address",
      "Hostname",
      "Lease type",
      "WiFi",
    ]) {
      const heading = document.createElement("th");
      heading.textContent = label;
      if (label === "Device" || label === "WiFi") {
        heading.className = "icon-cell";
      }
      headerRow.append(heading);
    }
    head.append(headerRow);
    table.append(head);

    const body = document.createElement("tbody");
    for (const row of rows) {
      const tableRow = document.createElement("tr");
      const deviceCell = document.createElement("td");
      deviceCell.className = "icon-cell";
      deviceCell.append(
        iconLink(row.deviceId, "mdi:open-in-new", "Open ARP device"),
      );
      tableRow.append(
        deviceCell,
        textCell(row.ipAddress),
        textCell(row.interfaceName),
        textCell(row.macAddress),
        textCell(row.hostname),
        textCell(row.dhcpLeaseType),
      );

      const wifiCell = document.createElement("td");
      wifiCell.className = "icon-cell";
      if (row.wifiDeviceId) {
        wifiCell.append(
          iconLink(row.wifiDeviceId, "mdi:wifi", "Open WiFi client"),
        );
      }
      tableRow.append(wifiCell);
      body.append(tableRow);
    }
    table.append(body);
    wrapper.append(table);
    card.append(wrapper);
    this.shadowRoot.replaceChildren(style, card);
  }
}

if (!customElements.get(ARP_TABLE_CARD_ELEMENT)) {
  customElements.define(ARP_TABLE_CARD_ELEMENT, FortiOSKDARPTable);
}

function filterCard() {
  return {
    type: "entities",
    title: "ARP Table Filters",
    entities: [
      {
        entity: "select.arp_table_fortigate_filter",
        name: "Firewall",
      },
      {
        entity: "select.arp_table_interface_filter",
        name: "Interface",
      },
      {
        entity: "select.arp_table_lease_type_filter",
        name: "Lease type",
      },
    ],
    grid_options: { columns: "full" },
  };
}

function dashboardView() {
  return {
    title: "ARP Table",
    path: "arp-table",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "ARP Table",
            heading_style: "title",
          },
          filterCard(),
          {
            type: `custom:${ARP_TABLE_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
