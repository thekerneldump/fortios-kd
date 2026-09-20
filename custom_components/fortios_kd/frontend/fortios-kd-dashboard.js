import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const FILTER_DEFAULTS = new Set([
  "All",
  "unknown",
  "unavailable",
  "none",
  "",
]);

function registryEntry(registry, id) {
  return registry?.get?.(id) ?? registry?.[id];
}

function registryValues(registry) {
  if (!registry) {
    return [];
  }

  return registry.values ? [...registry.values()] : Object.values(registry);
}

function registryName(entry, fallback = "") {
  return entry?.name_by_user || entry?.name || fallback;
}

function selectedFilter(hass, entityId) {
  return hass.states[entityId]?.state || "All";
}

function matchesFilter(selected, value) {
  return FILTER_DEFAULTS.has(selected) || selected === value;
}

function stateValue(hass, entityId) {
  return hass.states[entityId]?.state || "unavailable";
}

function labelNames(hass, device) {
  return [...(device?.labels || [])]
    .map((labelId) => registryName(registryEntry(hass.labels, labelId)))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
}

function clientModel(hass) {
  const preferredNames = preferredNamesByDevice(hass);
  const selectedFortigate = selectedFilter(
    hass,
    "select.wifi_client_fortigate_filter",
  );
  const selectedAccessPoint = selectedFilter(
    hass,
    "select.wifi_client_ap_filter",
  );
  const selectedSsid = selectedFilter(hass, "select.wifi_client_ssid_filter");
  const selectedArea = selectedFilter(hass, "select.wifi_client_area_filter");
  const selectedLabel = selectedFilter(
    hass,
    "select.wifi_client_label_filter",
  );
  const unavailableMode = selectedSsid === "Unavailable Clients";
  const devices = registryValues(hass.devices);
  const macStates = Object.values(hass.states)
    .filter(
      (state) =>
        state.attributes.fortios_kd_entry_type === "wifi_client" &&
        state.entity_id.startsWith("sensor.wifi_client_") &&
        state.entity_id.endsWith("_mac_address"),
    )
    .sort((left, right) => left.entity_id.localeCompare(right.entity_id));
  const cards = [];
  const signatureParts = [
    selectedFortigate,
    selectedAccessPoint,
    selectedSsid,
    selectedArea,
    selectedLabel,
  ];

  for (const macState of macStates) {
    const base = macState.entity_id.slice(0, -"_mac_address".length);
    const hostname = stateValue(hass, `${base}_hostname`);
    const lastKnownHostname = stateValue(
      hass,
      `${base}_last_known_hostname`,
    );
    const reportedFortigateName = stateValue(hass, `${base}_fortigate`);
    const accessPoint = stateValue(hass, `${base}_ap_name`);
    const ssid = stateValue(hass, `${base}_ssid`);
    const entity = registryEntry(hass.entities, macState.entity_id);
    const clientDevice = registryEntry(hass.devices, entity?.device_id);
    const areaId = entity?.area_id || clientDevice?.area_id;
    const areaName = registryName(registryEntry(hass.areas, areaId));
    const labels = labelNames(hass, clientDevice);
    const fortigateDeviceId = clientDevice?.via_device_id;
    const fortigateDevice = registryEntry(hass.devices, fortigateDeviceId);
    const fortigateName = preferredDeviceName(
      preferredNames,
      fortigateDevice,
      reportedFortigateName,
    );
    const accessPointDevice = devices.find(
      (device) =>
        device.via_device_id === fortigateDeviceId &&
        registryName(device) === accessPoint,
    );
    const areaText = areaName || "No Area";
    const labelText = labels.length ? labels.join(", ") : "No Labels";
    const areaMatches =
      matchesFilter(selectedArea, areaName) ||
      (selectedArea === "No Area" && !areaName);
    const labelMatches =
      matchesFilter(selectedLabel, "") ||
      (selectedLabel === "No Labels" && !labels.length) ||
      labels.includes(selectedLabel);
    const ssidMatches = unavailableMode
      ? macState.state === "unavailable"
      : matchesFilter(selectedSsid, ssid);
    const title = !FILTER_DEFAULTS.has(hostname)
      ? hostname
      : !FILTER_DEFAULTS.has(lastKnownHostname)
        ? lastKnownHostname
        : "Wifi Client";

    signatureParts.push(
      macState.entity_id,
      macState.state,
      hostname,
      lastKnownHostname,
      fortigateName,
      accessPoint,
      ssid,
      entity?.device_id || "",
      accessPointDevice?.id || "",
      areaText,
      labelText,
    );

    if (
      !matchesFilter(selectedFortigate, fortigateName) ||
      !matchesFilter(selectedAccessPoint, accessPoint) ||
      !ssidMatches ||
      !areaMatches ||
      !labelMatches
    ) {
      continue;
    }

    const rows = [];

    if (entity?.device_id) {
      rows.push({
        type: "button",
        name: title,
        icon: "mdi:devices",
        action_name: "Open client",
        tap_action: {
          action: "navigate",
          navigation_path: `/config/devices/device/${entity.device_id}`,
        },
      });
    }

    if (accessPointDevice?.id) {
      rows.push({
        type: "button",
        name: accessPoint,
        icon: "mdi:access-point-network",
        action_name: "Open AP",
        tap_action: {
          action: "navigate",
          navigation_path: `/config/devices/device/${accessPointDevice.id}`,
        },
      });
    }

    rows.push(
      { type: "section", label: `Area: ${areaText}` },
      { type: "section", label: `Labels: ${labelText}` },
      { entity: macState.entity_id, name: "MAC address" },
      { entity: `${base}_last_known_mac`, name: "Last Known MAC" },
      { entity: `${base}_ip_address`, name: "IP address" },
    );

    rows.push(
      fortigateDevice?.id
        ? {
            type: "button",
            name: fortigateName,
            icon: "mdi:shield-home",
            action_name: "Open FortiGate",
            tap_action: {
              action: "navigate",
              navigation_path: `/config/devices/device/${fortigateDevice.id}`,
            },
          }
        : { entity: `${base}_fortigate`, name: "FortiGate" },
    );

    rows.push(
      { entity: `${base}_ap_name`, name: "Access point" },
      { entity: `${base}_ssid`, name: "SSID" },
      { entity: `${base}_hostname`, name: "Hostname" },
      {
        entity: `${base}_last_known_hostname`,
        name: "Last Known Hostname",
      },
      { entity: `${base}_signal`, name: "Signal strength" },
    );

    cards.push({ type: "entities", title, entities: rows });
  }

  return {
    cards,
    signature: signatureParts.join("\u001e"),
  };
}

class FortiOSKDWifiClientGrid extends HTMLElement {
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

    const model = clientModel(hass);
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

    const nextModel = model || clientModel(this._hass);
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
      .clients {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
        gap: 8px;
      }
      .empty {
        color: var(--secondary-text-color);
        padding: 16px;
      }
    `;
    const container = document.createElement("div");
    container.className = "clients";

    if (!cards.length) {
      const empty = document.createElement("ha-card");
      empty.innerHTML =
        '<div class="empty">No Wifi clients match the selected filters.</div>';
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

const CLIENT_CARD_ELEMENT = "fortios-kd-wifi-client-grid";

if (!customElements.get(CLIENT_CARD_ELEMENT)) {
  customElements.define(CLIENT_CARD_ELEMENT, FortiOSKDWifiClientGrid);
}

function filterCard() {
  return {
    type: "entities",
    title: "Client Filters",
    entities: [
      {
        entity: "select.wifi_client_fortigate_filter",
        name: "FortiGate",
      },
      {
        entity: "select.wifi_client_ap_filter",
        name: "Access point",
      },
      {
        entity: "select.wifi_client_ssid_filter",
        name: "SSID",
      },
      {
        entity: "select.wifi_client_area_filter",
        name: "Area",
      },
      {
        entity: "select.wifi_client_label_filter",
        name: "Label",
      },
    ],
    grid_options: { columns: "full" },
  };
}

class FortiOSKDDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD Wifi Clients",
      icon: "mdi:access-point-network",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD Wifi Clients",
      views: [
        {
          title: "Wifi Clients",
          path: "wifi-clients",
          type: "sections",
          max_columns: 4,
          sections: [
            {
              type: "grid",
              column_span: 4,
              cards: [
                {
                  type: "heading",
                  heading: "Wifi Clients",
                  heading_style: "title",
                },
                filterCard(),
                {
                  type: `custom:${CLIENT_CARD_ELEMENT}`,
                  grid_options: { columns: "full" },
                },
              ],
            },
          ],
        },
      ],
    };
  }
}

const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd";

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(STRATEGY_ELEMENT, FortiOSKDDashboardStrategy);
}

window.customStrategies = window.customStrategies || [];

if (!window.customStrategies.some((strategy) => strategy.type === "fortios-kd")) {
  window.customStrategies.push({
    type: "fortios-kd",
    strategyType: "dashboard",
    name: "FortiOS KD Wifi Clients",
    description:
      "Explore FortiGate wifi clients with hub, AP, SSID, area, and label filters.",
    documentationURL:
      "https://github.com/thekerneldump/fortios-kd#community-dashboard",
  });
}
