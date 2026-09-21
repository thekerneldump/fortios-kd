import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const DEVICE_TABLE_CARD_ELEMENT = "fortios-kd-device-table";
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-device-table";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);
const FILTER_ALL = "All";
const LAST_SEEN_WINDOWS = new Map([
  ["Less than 1 hour ago", ["less", 60 * 60 * 1000]],
  ["Less than 1 day ago", ["less", 24 * 60 * 60 * 1000]],
  ["Less than 1 week ago", ["less", 7 * 24 * 60 * 60 * 1000]],
  ["Less than 1 month ago", ["less", 30 * 24 * 60 * 60 * 1000]],
  ["Less than 1 year ago", ["less", 365 * 24 * 60 * 60 * 1000]],
  ["More than 1 hour ago", ["more", 60 * 60 * 1000]],
  ["More than 1 day ago", ["more", 24 * 60 * 60 * 1000]],
  ["More than 1 week ago", ["more", 7 * 24 * 60 * 60 * 1000]],
  ["More than 1 month ago", ["more", 30 * 24 * 60 * 60 * 1000]],
  ["More than 1 year ago", ["more", 365 * 24 * 60 * 60 * 1000]],
]);

class FortiOSKDDeviceTableDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD Device Table",
      icon: "mdi:devices",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD Device Table",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDDeviceTableDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-device-table",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-device-table",
    strategyType: "dashboard",
    name: "FortiOS KD Device Table",
    description:
      "View FortiGate-detected devices and their classifications in a compact table.",
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

function currentStateValue(hass, entityId) {
  const state = hass.states[entityId];
  return isCurrent(state) ? state.state : undefined;
}

function fieldValue(fields, detailsState, field, attribute = field) {
  const state = fields.get(field);
  if (isCurrent(state)) {
    return state.state;
  }

  const value = detailsState?.attributes?.[attribute];
  return typeof value === "string" && value ? value : "—";
}

function matchesLastSeen(lastSeen, selectedLastSeen) {
  if (selectedLastSeen === FILTER_ALL) {
    return true;
  }

  const window = LAST_SEEN_WINDOWS.get(selectedLastSeen);
  const timestamp = Date.parse(lastSeen);
  if (!window || !Number.isFinite(timestamp)) {
    return false;
  }

  const [comparison, threshold] = window;
  const age = Date.now() - timestamp;
  return comparison === "less" ? age < threshold : age > threshold;
}

function deviceTableModel(hass) {
  const preferredNames = preferredNamesByDevice(hass);
  const selectedFortigate =
    currentStateValue(hass, "select.device_table_fortigate_filter") ||
    FILTER_ALL;
  const selectedHardwareVendor =
    currentStateValue(hass, "select.device_table_hardware_vendor_filter") ||
    FILTER_ALL;
  const selectedHardwareType =
    currentStateValue(hass, "select.device_table_hardware_type_filter") ||
    FILTER_ALL;
  const selectedHardwareFamily =
    currentStateValue(hass, "select.device_table_hardware_family_filter") ||
    FILTER_ALL;
  const selectedOperatingSystem =
    currentStateValue(hass, "select.device_table_operating_system_filter") ||
    FILTER_ALL;
  const selectedSoftwareVersion =
    currentStateValue(hass, "select.device_table_software_version_filter") ||
    FILTER_ALL;
  const selectedInterface =
    currentStateValue(hass, "select.device_table_interface_filter") ||
    FILTER_ALL;
  const selectedLastSeen =
    currentStateValue(hass, "select.device_table_last_seen_filter") ||
    FILTER_ALL;
  const wifiClientsByMatchId = new Map();
  const entriesByDevice = new Map();

  for (const state of Object.values(hass.states)) {
    const entity = registryEntry(hass.entities, state.entity_id);
    if (!entity?.device_id) {
      continue;
    }

    if (state.attributes.fortios_kd_entry_type === "wifi_client") {
      const matchId = state.attributes.fortios_kd_match_id;
      if (matchId && state.entity_id.endsWith("_mac_address")) {
        wifiClientsByMatchId.set(matchId, entity.device_id);
      }
      continue;
    }

    if (state.attributes.fortios_kd_entry_type !== "detected_device") {
      continue;
    }

    const field = state.attributes.fortios_kd_device_field;
    if (!field) {
      continue;
    }

    const entry = entriesByDevice.get(entity.device_id) || {
      deviceId: entity.device_id,
      fields: new Map(),
      matchId: undefined,
    };
    entry.fields.set(field, state);
    if (state.attributes.fortios_kd_match_id) {
      entry.matchId = state.attributes.fortios_kd_match_id;
    }
    entriesByDevice.set(entity.device_id, entry);
  }

  const rows = [];
  for (const entry of entriesByDevice.values()) {
    const detailsState = entry.fields.get("details");
    const macState = entry.fields.get("mac_address");
    if (!isCurrent(detailsState) && !isCurrent(macState)) {
      continue;
    }

    const detectedDevice = registryEntry(hass.devices, entry.deviceId);
    const fortigateDevice = registryEntry(
      hass.devices,
      detectedDevice?.via_device_id,
    );
    const fortigateName = preferredDeviceName(
      preferredNames,
      fortigateDevice,
      "FortiGate",
    );

    const hardwareVendor = fieldValue(
      entry.fields,
      detailsState,
      "hardware_vendor",
    );
    const operatingSystem = fieldValue(
      entry.fields,
      detailsState,
      "operating_system",
    );
    const softwareVersion = fieldValue(
      entry.fields,
      detailsState,
      "software_version",
    );
    const interfaceName = fieldValue(
      entry.fields,
      detailsState,
      "interface",
    );
    const lastSeen = fieldValue(entry.fields, detailsState, "last_seen");
    const hardwareType = fieldValue(
      entry.fields,
      detailsState,
      "hardware_type",
    );
    const hardwareFamily = fieldValue(
      entry.fields,
      detailsState,
      "hardware_family",
    );

    if (
      (selectedFortigate !== FILTER_ALL &&
        selectedFortigate !== fortigateName) ||
      (selectedHardwareVendor !== FILTER_ALL &&
        selectedHardwareVendor !== hardwareVendor) ||
      (selectedHardwareType !== FILTER_ALL &&
        selectedHardwareType !== hardwareType) ||
      (selectedHardwareFamily !== FILTER_ALL &&
        selectedHardwareFamily !== hardwareFamily) ||
      (selectedOperatingSystem !== FILTER_ALL &&
        selectedOperatingSystem !== operatingSystem) ||
      (selectedSoftwareVersion !== FILTER_ALL &&
        selectedSoftwareVersion !== softwareVersion) ||
      (selectedInterface !== FILTER_ALL &&
        selectedInterface !== interfaceName) ||
      !matchesLastSeen(lastSeen, selectedLastSeen)
    ) {
      continue;
    }

    rows.push({
      deviceId: entry.deviceId,
      fortigateName,
      hostname: fieldValue(entry.fields, detailsState, "hostname"),
      ipAddress: fieldValue(entry.fields, detailsState, "ipv4_address"),
      macAddress: fieldValue(
        entry.fields,
        detailsState,
        "mac_address",
      ),
      operatingSystem,
      hardwareVendor,
      hardwareType,
      hardwareFamily,
      hardwareVersion: fieldValue(
        entry.fields,
        detailsState,
        "hardware_version",
      ),
      softwareVersion,
      interfaceName,
      lastSeen,
      wifiDeviceId: entry.matchId
        ? wifiClientsByMatchId.get(entry.matchId)
        : undefined,
    });
  }

  rows.sort((left, right) => {
    const hostnameOrder = left.hostname.localeCompare(right.hostname, undefined, {
      numeric: true,
      sensitivity: "base",
    });
    return hostnameOrder || left.macAddress.localeCompare(right.macAddress);
  });

  return {
    rows,
    signature: rows
      .flatMap((row) => [
        row.deviceId,
        row.fortigateName,
        row.hostname,
        row.ipAddress,
        row.macAddress,
        row.operatingSystem,
        row.hardwareVendor,
        row.hardwareType,
        row.hardwareFamily,
        row.hardwareVersion,
        row.softwareVersion,
        row.lastSeen,
        row.wifiDeviceId || "",
      ])
      .concat([
        selectedFortigate,
        selectedHardwareVendor,
        selectedHardwareType,
        selectedHardwareFamily,
        selectedOperatingSystem,
        selectedSoftwareVersion,
        selectedInterface,
        selectedLastSeen,
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

function lastSeenCell(value) {
  const cell = document.createElement("td");
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    cell.textContent = "—";
    return cell;
  }

  const elapsedSeconds = Math.max(
    0,
    Math.floor((Date.now() - timestamp) / 1000),
  );
  let quantity;
  let unit;
  if (elapsedSeconds < 60) {
    quantity = elapsedSeconds;
    unit = "sec";
  } else if (elapsedSeconds < 60 * 60) {
    quantity = Math.floor(elapsedSeconds / 60);
    unit = "min";
  } else if (elapsedSeconds < 24 * 60 * 60) {
    quantity = Math.floor(elapsedSeconds / (60 * 60));
    unit = "hr";
  } else if (elapsedSeconds < 30 * 24 * 60 * 60) {
    quantity = Math.floor(elapsedSeconds / (24 * 60 * 60));
    unit = quantity === 1 ? "day" : "days";
  } else if (elapsedSeconds < 365 * 24 * 60 * 60) {
    quantity = Math.floor(elapsedSeconds / (30 * 24 * 60 * 60));
    unit = quantity === 1 ? "month" : "months";
  } else {
    quantity = Math.floor(elapsedSeconds / (365 * 24 * 60 * 60));
    unit = quantity === 1 ? "year" : "years";
  }

  cell.textContent = `${quantity} ${unit} ago`;
  cell.title = new Date(timestamp).toLocaleString();
  return cell;
}

class FortiOSKDDeviceTable extends HTMLElement {
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

    const model = deviceTableModel(this._hass);
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
        "No current detected devices match the selected filters.";
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
      "Hostname",
      "IP address",
      "MAC address",
      "Operating system",
      "Hardware vendor",
      "Hardware type",
      "Hardware family",
      "Hardware version",
      "Software version",
      "Last seen",
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
        iconLink(row.deviceId, "mdi:open-in-new", "Open detected device"),
      );
      tableRow.append(
        deviceCell,
        textCell(row.hostname),
        textCell(row.ipAddress),
        textCell(row.macAddress),
        textCell(row.operatingSystem),
        textCell(row.hardwareVendor),
        textCell(row.hardwareType),
        textCell(row.hardwareFamily),
        textCell(row.hardwareVersion),
        textCell(row.softwareVersion),
        lastSeenCell(row.lastSeen),
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

if (!customElements.get(DEVICE_TABLE_CARD_ELEMENT)) {
  customElements.define(DEVICE_TABLE_CARD_ELEMENT, FortiOSKDDeviceTable);
}

function filterCard() {
  return {
    type: "entities",
    title: "Device Table Filters",
    entities: [
      {
        entity: "select.device_table_fortigate_filter",
        name: "Firewall",
      },
      {
        entity: "select.device_table_hardware_vendor_filter",
        name: "Hardware vendor",
      },
      {
        entity: "select.device_table_hardware_type_filter",
        name: "Hardware type",
      },
      {
        entity: "select.device_table_hardware_family_filter",
        name: "Hardware family",
      },
      {
        entity: "select.device_table_operating_system_filter",
        name: "Operating system",
      },
      {
        entity: "select.device_table_software_version_filter",
        name: "Software version",
      },
      {
        entity: "select.device_table_interface_filter",
        name: "Interface",
      },
      {
        entity: "select.device_table_last_seen_filter",
        name: "Last seen",
      },
    ],
    grid_options: { columns: "full" },
  };
}

function dashboardView() {
  return {
    title: "Device Table",
    path: "device-table",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "Device Table",
            heading_style: "title",
          },
          filterCard(),
          {
            type: `custom:${DEVICE_TABLE_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
