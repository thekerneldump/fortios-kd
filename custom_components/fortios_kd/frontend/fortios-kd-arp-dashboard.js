import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const ARP_CARD_ELEMENT = "fortios-kd-arp-entry-grid";
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-arp-entries";
const UNAVAILABLE_STATES = new Set(["unknown", "unavailable", ""]);

class FortiOSKDARPEntriesDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD ARP Entries",
      icon: "mdi:table-network",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD ARP Entries",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDARPEntriesDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-arp-entries",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-arp-entries",
    strategyType: "dashboard",
    name: "FortiOS KD ARP Entries",
    description:
      "Inspect current FortiGate ARP entries and their wifi-client diagnostics.",
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

function arpModel(hass) {
  const preferredNames = preferredNamesByDevice(hass);
  const entriesByDevice = new Map();

  for (const state of Object.values(hass.states)) {
    if (state.attributes.fortios_kd_entry_type !== "arp_entry") {
      continue;
    }

    const field = state.attributes.fortios_kd_arp_field;
    const entity = registryEntry(hass.entities, state.entity_id);
    if (!field || !entity?.device_id) {
      continue;
    }

    const entry = entriesByDevice.get(entity.device_id) || {
      deviceId: entity.device_id,
      fields: new Map(),
    };
    entry.fields.set(field, state);
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
    const arpDevice = registryEntry(hass.devices, entry.deviceId);
    const fortigateDevice = registryEntry(
      hass.devices,
      arpDevice?.via_device_id,
    );
    const ipAddress = isCurrent(ipState) ? ipState.state : "";
    const interfaceName = isCurrent(interfaceState)
      ? interfaceState.state
      : "";
    const macAddress = macState.state;
    const title =
      ipAddress && interfaceName
        ? `${ipAddress} - ${interfaceName}`
        : ipAddress || interfaceName || macAddress;

    entries.push({
      ...entry,
      ipAddress,
      interfaceName,
      macAddress,
      fortigateDevice,
      fortigateName: preferredDeviceName(
        preferredNames,
        fortigateDevice,
        "FortiGate",
      ),
      title,
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
  const signatureParts = [];
  for (const entry of entries) {
    const rows = [
      {
        type: "button",
        name: entry.title,
        icon: "mdi:table-network",
        action_name: "Open ARP device",
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

    for (const [field, label] of [
      ["mac_address", "MAC address"],
      ["ip_addresses", "IP addresses"],
      ["interfaces", "Interfaces"],
      ["age", "Age"],
      ["vdoms", "VDOMs"],
      ["wifi_client_match", "WiFi client match"],
      ["ip_conflict", "IP conflict"],
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
    );
    cards.push({ type: "entities", title: entry.title, entities: rows });
  }

  return {
    cards,
    signature: signatureParts.join("\u001e"),
  };
}

class FortiOSKDARPEntryGrid extends HTMLElement {
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

    const model = arpModel(hass);
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

    const nextModel = model || arpModel(this._hass);
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
        '<div class="empty">No current ARP entries. Enable ARP synchronization on a supported FortiGate hub.</div>';
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

if (!customElements.get(ARP_CARD_ELEMENT)) {
  customElements.define(ARP_CARD_ELEMENT, FortiOSKDARPEntryGrid);
}

function dashboardView() {
  return {
    title: "ARP Entries",
    path: "arp-entries",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "ARP Entries",
            heading_style: "title",
          },
          {
            type: `custom:${ARP_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
