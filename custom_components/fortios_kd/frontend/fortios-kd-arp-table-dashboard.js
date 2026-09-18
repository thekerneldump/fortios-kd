const ARP_TABLE_CARD_ELEMENT = "fortios-kd-arp-table";
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-arp-table";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);

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

function isCurrent(state) {
  return state && !UNAVAILABLE_STATES.has(state.state);
}

function arpTableModel(hass) {
  const wifiDevicesByMatchId = new Map();
  const entriesByDevice = new Map();

  for (const state of Object.values(hass.states)) {
    const entity = registryEntry(hass.entities, state.entity_id);
    if (!entity?.device_id) {
      continue;
    }

    if (state.attributes.fortios_kd_entry_type === "wifi_client") {
      const matchId = state.attributes.fortios_kd_match_id;
      if (matchId) {
        wifiDevicesByMatchId.set(matchId, entity.device_id);
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
    const hasWifiMatch =
      isCurrent(matchState) && matchState.state !== "Not currently detected";
    const wifiDeviceId =
      hasWifiMatch && entry.matchId
        ? wifiDevicesByMatchId.get(entry.matchId)
        : undefined;

    rows.push({
      deviceId: entry.deviceId,
      ipAddress: isCurrent(ipState) ? ipState.state : "—",
      interfaceName: isCurrent(interfaceState) ? interfaceState.state : "—",
      macAddress: macState.state,
      wifiDeviceId,
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
        row.wifiDeviceId || "",
      ])
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
        "No current ARP entries. Enable ARP synchronization on a supported FortiGate hub.";
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
          {
            type: `custom:${ARP_TABLE_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
