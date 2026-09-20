import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const DHCP_CARD_ELEMENT = "fortios-kd-dhcp-entry-grid";
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-dhcp-entries";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);
const FILTER_ALL = "All";

class FortiOSKDDHCPEntriesDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD DHCP Entries",
      icon: "mdi:ip-network-outline",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD DHCP Entries",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDDHCPEntriesDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-dhcp-entries",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-dhcp-entries",
    strategyType: "dashboard",
    name: "FortiOS KD DHCP Entries",
    description:
      "Inspect current FortiGate DHCP leases and their wifi-client matches.",
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

function currentStateValues(state) {
  if (!isCurrent(state)) {
    return [];
  }

  return String(state.state)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function dhcpModel(hass) {
  const preferredNames = preferredNamesByDevice(hass);
  const selectedFortigate =
    currentStateValue(hass, "select.dhcp_entries_fortigate_filter") ||
    FILTER_ALL;
  const selectedInterface =
    currentStateValue(hass, "select.dhcp_entries_interface_filter") ||
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

    if (state.attributes.fortios_kd_entry_type !== "dhcp_entry") {
      continue;
    }

    const field = state.attributes.fortios_kd_dhcp_field;
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

  const entries = [];
  for (const entry of entriesByDevice.values()) {
    const macState = entry.fields.get("mac_address");
    if (!isCurrent(macState)) {
      continue;
    }

    const ipState = entry.fields.get("ip_addresses");
    const interfaceState = entry.fields.get("interfaces");
    const matchState = entry.fields.get("wifi_client_match");
    const dhcpDevice = registryEntry(hass.devices, entry.deviceId);
    const fortigateDevice = registryEntry(
      hass.devices,
      dhcpDevice?.via_device_id,
    );
    const fortigateName = preferredDeviceName(
      preferredNames,
      fortigateDevice,
      "FortiGate",
    );
    const interfaces = currentStateValues(interfaceState);

    if (
      (selectedFortigate !== FILTER_ALL &&
        selectedFortigate !== fortigateName) ||
      (selectedInterface !== FILTER_ALL &&
        !interfaces.includes(selectedInterface))
    ) {
      continue;
    }

    const ipAddress = isCurrent(ipState) ? ipState.state : "";
    const interfaceName = isCurrent(interfaceState) ? interfaceState.state : "";
    const macAddress = macState.state;
    const title =
      ipAddress && interfaceName
        ? `${ipAddress} - ${interfaceName}`
        : ipAddress || interfaceName || macAddress;
    const wifiDeviceId =
      isCurrent(matchState) && matchState.state !== "Not currently detected"
        ? wifiClientsByMatchId.get(entry.matchId)
        : undefined;

    entries.push({
      ...entry,
      fortigateDevice,
      fortigateName,
      ipAddress,
      macAddress,
      title,
      wifiDeviceId,
    });
  }

  entries.sort((left, right) =>
    (left.ipAddress || left.macAddress).localeCompare(
      right.ipAddress || right.macAddress,
      undefined,
      { numeric: true },
    ),
  );

  const cards = [];
  const signatureParts = [selectedFortigate, selectedInterface];
  for (const entry of entries) {
    const rows = [
      {
        type: "button",
        name: entry.title,
        icon: "mdi:ip-network-outline",
        action_name: "Open DHCP device",
        tap_action: {
          action: "navigate",
          navigation_path: `/config/devices/device/${entry.deviceId}`,
        },
      },
    ];

    if (entry.fortigateDevice?.id) {
      rows.push({
        type: "button",
        name: entry.fortigateName,
        icon: "mdi:shield-home",
        action_name: "Open FortiGate",
        tap_action: {
          action: "navigate",
          navigation_path: `/config/devices/device/${entry.fortigateDevice.id}`,
        },
      });
    }

    if (entry.wifiDeviceId) {
      rows.push({
        type: "button",
        name: "Matched WiFi client",
        icon: "mdi:wifi",
        action_name: "Open WiFi client",
        tap_action: {
          action: "navigate",
          navigation_path: `/config/devices/device/${entry.wifiDeviceId}`,
        },
      });
    }

    for (const [field, label] of [
      ["mac_address", "MAC address"],
      ["ip_addresses", "IP addresses"],
      ["hostnames", "Hostnames"],
      ["interfaces", "Interfaces"],
      ["statuses", "Statuses"],
      ["assignment_type", "IP assignment type"],
      ["lease_expiration", "Latest lease expiration"],
      ["address_types", "Address types"],
      ["server_mkeys", "Server IDs"],
      ["wifi_client_match", "WiFi client match"],
    ]) {
      const state = entry.fields.get(field);
      if (state) {
        rows.push({ entity: state.entity_id, name: label });
        signatureParts.push(state.entity_id, state.state);
      }
    }

    signatureParts.push(
      entry.deviceId,
      entry.title,
      entry.fortigateDevice?.id || "",
      entry.fortigateName,
      entry.wifiDeviceId || "",
    );
    cards.push({ type: "entities", title: entry.title, entities: rows });
  }

  return {
    cards,
    signature: signatureParts.join("\u001e"),
  };
}

class FortiOSKDDHCPEntryGrid extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cards = [];
    this._buildVersion = 0;
  }

  setConfig(config) {
    this._config = config;
    this._signature = undefined;
    this._scheduleBuild();
  }

  set hass(hass) {
    this._hass = hass;

    for (const card of this._cards) {
      card.hass = hass;
    }

    if (!this._config) {
      return;
    }

    const model = dhcpModel(hass);
    if (model.signature !== this._signature) {
      this._signature = model.signature;
      this._scheduleBuild(model);
    }
  }

  getCardSize() {
    return Math.max(1, this._cards.length * 3);
  }

  _scheduleBuild(model) {
    if (!this._hass || !this._config) {
      return;
    }

    const nextModel = model || dhcpModel(this._hass);
    const buildVersion = ++this._buildVersion;
    void this._build(nextModel, buildVersion);
  }

  async _build(model, buildVersion) {
    const helpers = await window.loadCardHelpers();
    const cards = await Promise.all(
      model.cards.map((config) => helpers.createCardElement(config)),
    );

    if (buildVersion !== this._buildVersion) {
      return;
    }

    this._cards = cards;
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      .entries {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(340px, 100%), 1fr));
        gap: 8px;
      }
      .empty {
        color: var(--secondary-text-color);
        padding: 16px;
      }
    `;
    const container = document.createElement("div");
    container.className = "entries";

    if (!cards.length) {
      const empty = document.createElement("ha-card");
      empty.innerHTML =
        '<div class="empty">No current DHCP entries. Enable DHCP lease synchronization on a FortiGate hub.</div>';
      container.append(empty);
    } else {
      for (const card of cards) {
        card.hass = this._hass;
        container.append(card);
      }
    }

    this.shadowRoot.replaceChildren(style, container);
  }
}

if (!customElements.get(DHCP_CARD_ELEMENT)) {
  customElements.define(DHCP_CARD_ELEMENT, FortiOSKDDHCPEntryGrid);
}

function dashboardView() {
  return {
    title: "DHCP Entries",
    path: "dhcp-entries",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "DHCP Entry Filters",
            heading_style: "title",
          },
          {
            type: "entities",
            title: "DHCP Entry Filters",
            entities: [
              {
                entity: "select.dhcp_entries_fortigate_filter",
                name: "Firewall",
              },
              {
                entity: "select.dhcp_entries_interface_filter",
                name: "Interface",
              },
            ],
            grid_options: { columns: "full" },
          },
          {
            type: "heading",
            heading: "DHCP Entries",
            heading_style: "title",
          },
          {
            type: `custom:${DHCP_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
