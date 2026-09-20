import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const THROUGHPUT_GRAPHS = [
  { metric: "tx_bits_per_second", title: "Calculated TX Rate" },
  { metric: "rx_bits_per_second", title: "Calculated RX Rate" },
  { metric: "bandwidth_tx", title: "FortiGate TX Bandwidth" },
  { metric: "bandwidth_rx", title: "FortiGate RX Bandwidth" },
];

const HEALTH_GRAPHS = [
  { metric: "channel_utilization_percent", title: "Channel Utilization" },
  { metric: "noise_floor", title: "Noise Floor" },
  { metric: "mac_errors_tx", title: "TX MAC Errors" },
  { metric: "mac_errors_rx", title: "RX MAC Errors" },
  { metric: "tx_mac_errors_per_minute", title: "TX MAC Error Rate" },
  { metric: "rx_mac_errors_per_minute", title: "RX MAC Error Rate" },
];

const OVERVIEW_GRAPHS = [
  {
    title: "Clients",
    scope: "ap",
    metrics: [{ metric: "clients", title: "Clients" }],
  },
  {
    title: "CPU Usage",
    scope: "ap",
    metrics: [{ metric: "cpu_usage", title: "CPU Usage" }],
  },
  {
    title: "Memory Free",
    scope: "ap",
    metrics: [{ metric: "mem_free", title: "Memory Free" }],
  },
  {
    title: "Memory Total",
    scope: "ap",
    metrics: [{ metric: "mem_total", title: "Memory Total" }],
  },
  {
    title: "Channel",
    scope: "radio",
    metrics: [{ metric: "oper_chan", title: "Channel" }],
  },
  ...HEALTH_GRAPHS.map((graph) => ({
    title: graph.title,
    scope: "radio",
    metrics: [graph],
  })),
  ...THROUGHPUT_GRAPHS.map((graph) => ({
    title: graph.title,
    scope: "radio",
    metrics: [graph],
  })),
];

const GRAPH_GROUPS = {
  overview: OVERVIEW_GRAPHS,
};
const BANDS = ["2.4 GHz", "5 GHz"];
const STRATEGY_ELEMENT = "ll-strategy-dashboard-fortios-kd-wifi-graphs";

class FortiOSKDWifiGraphsDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD Wifi Graphs",
      icon: "mdi:chart-line",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD Wifi Graphs",
      views: [dashboardView("Wifi Overview", "wifi-overview", "overview")],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDWifiGraphsDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-wifi-graphs",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-wifi-graphs",
    strategyType: "dashboard",
    name: "FortiOS KD Wifi Graphs",
    description:
      "Explore automatically discovered FortiGate radio history with hub, AP, and SSID filters.",
    documentationURL:
      "https://github.com/thekerneldump/fortios-kd#community-dashboards",
  });
}

const LEGEND_LAYOUT_STYLE = `
  .chart-legend {
    padding-inline: 8px;
  }
  .chart-legend ul {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    justify-content: stretch;
    align-items: start;
    gap: var(--ha-space-1) var(--ha-space-4);
  }
  .chart-legend li,
  .chart-legend.multiple-items li,
  .chart-legend.multiple-items li:has(.value) {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    max-width: none;
    justify-self: stretch;
  }
  .chart-legend li:not(:has(.legend-toggle)) {
    display: flex;
  }
  .chart-legend .value {
    justify-self: end;
  }
  .chart-legend li:has(ha-assist-chip) {
    display: none;
  }
`;
const LEGEND_STYLE_SHEET =
  typeof CSSStyleSheet !== "undefined" &&
  typeof CSSStyleSheet.prototype.replaceSync === "function"
    ? new CSSStyleSheet()
    : undefined;
LEGEND_STYLE_SHEET?.replaceSync(LEGEND_LAYOUT_STYLE);
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

function registryName(entry, fallback = "") {
  return entry?.name_by_user || entry?.name || fallback;
}

function selectedFilter(hass, entityId) {
  return hass.states[entityId]?.state || "All";
}

function matchesFilter(selected, value) {
  return FILTER_DEFAULTS.has(selected) || selected === value;
}

function radioKey(deviceId, radioId) {
  return `${deviceId || ""}:${radioId ?? ""}`;
}

function graphModel(hass, group) {
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
  const ssidsByRadio = new Map();
  const ssidsByDevice = new Map();
  const metricStates = [];

  for (const state of Object.values(hass.states)) {
    const radioId = state.attributes.fortios_kd_radio_id;
    const entity = registryEntry(hass.entities, state.entity_id);
    const deviceId = entity?.device_id;
    const ssids = state.attributes.ssids;

    if (deviceId && Array.isArray(ssids)) {
      ssidsByRadio.set(radioKey(deviceId, radioId), ssids);
      const deviceSsids = ssidsByDevice.get(deviceId) || new Set();
      for (const ssid of ssids) {
        deviceSsids.add(ssid);
      }
      ssidsByDevice.set(deviceId, deviceSsids);
    }

    if (state.attributes.fortios_kd_metric) {
      metricStates.push({
        state,
        deviceId,
        scope:
          state.attributes.fortios_kd_scope ||
          (radioId === undefined ? "ap" : "radio"),
      });
    }
  }

  const cardConfigs = [];
  const signatureParts = [
    group,
    selectedFortigate,
    selectedAccessPoint,
    selectedSsid,
  ];

  for (const graph of GRAPH_GROUPS[group] || []) {
    const graphBands = graph.scope === "radio" ? BANDS : [undefined];

    for (const band of graphBands) {
      const entities = [];

      for (const { state, deviceId, scope } of metricStates) {
        const metric = graph.metrics.find(
          (item) => item.metric === state.attributes.fortios_kd_metric,
        );
        if (
          !metric ||
          scope !== graph.scope ||
          (scope === "radio" && state.attributes.fortios_kd_band !== band)
        ) {
          continue;
        }

        const device = registryEntry(hass.devices, deviceId);
        const accessPointName = registryName(device, "Access point");
        const fortigate = registryEntry(hass.devices, device?.via_device_id);
        const fortigateName = preferredDeviceName(preferredNames, fortigate);
        const radioId = state.attributes.fortios_kd_radio_id;
        const ssids =
          scope === "radio"
            ? ssidsByRadio.get(radioKey(deviceId, radioId)) || []
            : [...(ssidsByDevice.get(deviceId) || [])];
        const ssidMatches =
          FILTER_DEFAULTS.has(selectedSsid) || ssids.includes(selectedSsid);

        signatureParts.push(
          state.entity_id,
          accessPointName,
          fortigateName,
          scope,
          String(radioId),
          ssids.join("\u001f"),
        );

        if (
          matchesFilter(selectedFortigate, fortigateName) &&
          matchesFilter(selectedAccessPoint, accessPointName) &&
          ssidMatches
        ) {
          entities.push({
            entity: state.entity_id,
            name: accessPointName,
          });
        }
      }

      if (entities.length) {
        cardConfigs.push({
          type: "history-graph",
          title: band ? `${band} ${graph.title}` : graph.title,
          hours_to_show: 24,
          expand_legend: true,
          entities,
        });
      }
    }
  }

  return {
    cardConfigs,
    signature: signatureParts.join("\u001e"),
  };
}

function applyHistoryGraphLegendLayout(card) {
  const historyCharts = card.shadowRoot?.querySelector(
    "state-history-charts",
  );
  const lineCharts = historyCharts?.shadowRoot?.querySelectorAll(
    "state-history-chart-line",
  );

  if (!lineCharts?.length) {
    return false;
  }

  let complete = true;
  for (const lineChart of lineCharts) {
    const chartBase = lineChart.shadowRoot?.querySelector("ha-chart-base");
    const chartRoot = chartBase?.shadowRoot;

    if (!chartRoot) {
      complete = false;
      continue;
    }

    if (
      LEGEND_STYLE_SHEET &&
      "adoptedStyleSheets" in chartRoot &&
      !chartRoot.adoptedStyleSheets.includes(LEGEND_STYLE_SHEET)
    ) {
      chartRoot.adoptedStyleSheets = [
        ...chartRoot.adoptedStyleSheets,
        LEGEND_STYLE_SHEET,
      ];
    } else if (
      !LEGEND_STYLE_SHEET &&
      !chartRoot.querySelector("style[data-fortios-kd-legend]")
    ) {
      const style = document.createElement("style");
      style.dataset.fortiosKdLegend = "";
      style.textContent = LEGEND_LAYOUT_STYLE;
      chartRoot.append(style);
    }
  }

  return complete;
}

class FortiOSKDWifiGraphGrid extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cards = [];
    this._buildVersion = 0;
    this._legendObserver = undefined;
    this._legendRetryTimers = new Set();
    this._legendsPending = new WeakSet();
  }

  setConfig(config) {
    if (!GRAPH_GROUPS[config.group]) {
      throw new Error(`Unknown FortiOS KD graph group: ${config.group}`);
    }

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

    const model = graphModel(hass, this._config.group);
    if (model.signature !== this._signature) {
      this._signature = model.signature;
      this._scheduleBuild(model);
    }
  }

  getCardSize() {
    return Math.max(1, this._cards.length * 3);
  }

  disconnectedCallback() {
    this._clearLegendWatchers();
  }

  _clearLegendWatchers() {
    this._legendObserver?.disconnect();
    this._legendObserver = undefined;
    for (const timer of this._legendRetryTimers) {
      window.clearTimeout(timer);
    }
    this._legendRetryTimers.clear();
    this._legendsPending = new WeakSet();
  }

  _scheduleBuild(model) {
    if (!this._hass || !this._config) {
      return;
    }

    const nextModel = model || graphModel(this._hass, this._config.group);
    const buildVersion = ++this._buildVersion;
    this._clearLegendWatchers();
    void this._build(nextModel, buildVersion);
  }

  _formatLegend(card, buildVersion, attempt = 0) {
    if (buildVersion !== this._buildVersion || !card.isConnected) {
      this._legendsPending.delete(card);
      return;
    }

    if (applyHistoryGraphLegendLayout(card)) {
      this._legendsPending.delete(card);
      return;
    }

    if (attempt >= 100) {
      this._legendsPending.delete(card);
      return;
    }

    const timer = window.setTimeout(() => {
      this._legendRetryTimers.delete(timer);
      this._formatLegend(card, buildVersion, attempt + 1);
    }, 100);
    this._legendRetryTimers.add(timer);
  }

  _watchLegends(cards, buildVersion) {
    this._legendObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting || this._legendsPending.has(entry.target)) {
            continue;
          }

          this._legendsPending.add(entry.target);
          this._formatLegend(entry.target, buildVersion);
        }
      },
      { rootMargin: "200px 0px" },
    );

    for (const card of cards) {
      this._legendObserver.observe(card);
    }
  }

  async _build(model, buildVersion) {
    const helpers = await window.loadCardHelpers();
    const cards = await Promise.all(
      model.cardConfigs.map((config) => helpers.createCardElement(config)),
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
      .graphs {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr));
        gap: 8px;
      }
      .empty {
        color: var(--secondary-text-color);
        padding: 16px;
      }
    `;
    const container = document.createElement("div");
    container.className = "graphs";

    if (!cards.length) {
      const empty = document.createElement("ha-card");
      empty.innerHTML =
        '<div class="empty">No radio graphs match the selected filters.</div>';
      container.append(empty);
    } else {
      for (const card of cards) {
        card.hass = this._hass;
        container.append(card);
      }
    }

    this.shadowRoot.replaceChildren(style, container);
    if (cards.length) {
      this._watchLegends(cards, buildVersion);
    }
  }
}

const GRAPH_CARD_ELEMENT = "fortios-kd-wifi-graph-grid";

if (!customElements.get(GRAPH_CARD_ELEMENT)) {
  customElements.define(GRAPH_CARD_ELEMENT, FortiOSKDWifiGraphGrid);
}

function filterCard() {
  return {
    type: "entities",
    title: "Graph Filters",
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
    ],
    grid_options: { columns: "full" },
  };
}

function graphGrid(group) {
  return {
    type: `custom:${GRAPH_CARD_ELEMENT}`,
    group,
    grid_options: { columns: "full" },
  };
}

function dashboardView(title, path, group) {
  return {
    title,
    path,
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: title,
            heading_style: "title",
          },
          filterCard(),
          {
            type: "markdown",
            content:
              "The SSID filter selects radios broadcasting that SSID. " +
              "Values are totals for the entire radio, not per-SSID measurements.",
            grid_options: { columns: "full" },
          },
          graphGrid(group),
        ],
      },
    ],
  };
}
