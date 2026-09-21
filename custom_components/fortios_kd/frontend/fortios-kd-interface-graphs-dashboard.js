import {
  preferredDeviceName,
  preferredNamesByDevice,
} from "./fortios-kd-preferred-names.js";

const INTERFACE_GRAPH_CARD_ELEMENT = "fortios-kd-interface-graph-grid";
const STRATEGY_ELEMENT =
  "ll-strategy-dashboard-fortios-kd-interface-graphs";
const FILTER_ALL = "All";
const INTERFACE_KIND_HARDWARE_SWITCH_MEMBER = "Hardware switch member";
const INTERFACE_KIND_WIFI_SSID = "WiFi SSID interface";
const GRAPH_LAYOUT_COMBINED = "Combined by rate";
const GRAPH_LAYOUT_SEPARATE = "Separated by firewall";
const TIME_SPAN_HOURS = new Map([
  ["1 week", 168],
  ["1 day", 24],
  ["12 hours", 12],
  ["6 hours", 6],
  ["3 hours", 3],
  ["1 hour", 1],
  ["30 min", 0.5],
]);
const FILTER_DEFAULTS = new Set([
  FILTER_ALL,
  "unknown",
  "unavailable",
  "none",
  "",
]);
const RATE_GRAPHS = [
  { metric: "tx_bits_per_second", title: "TX Data Rate (Mbps)" },
  { metric: "rx_bits_per_second", title: "RX Data Rate (Mbps)" },
  { metric: "tx_bytes_per_second", title: "TX Data Rate (MB/s)" },
  { metric: "rx_bytes_per_second", title: "RX Data Rate (MB/s)" },
  { metric: "tx_packets_per_second", title: "TX Packet Rate" },
  { metric: "rx_packets_per_second", title: "RX Packet Rate" },
  { metric: "tx_errors_per_second", title: "TX Error Rate" },
  { metric: "rx_errors_per_second", title: "RX Error Rate" },
];
const RATE_GRAPH_BY_METRIC = new Map(
  RATE_GRAPHS.map((graph) => [graph.metric, graph]),
);
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

class FortiOSKDInterfaceGraphsDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD Interface Graphs",
      icon: "mdi:chart-line",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD Interface Graphs",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDInterfaceGraphsDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-interface-graphs",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-interface-graphs",
    strategyType: "dashboard",
    name: "FortiOS KD Interface Graphs",
    description:
      "Graph calculated traffic, packet, and error rates for FortiGate interfaces.",
    documentationURL:
      "https://github.com/thekerneldump/fortios-kd#community-dashboards",
  });
}

function registryEntry(registry, id) {
  return registry?.get?.(id) ?? registry?.[id];
}

function selectedFilter(hass, entityId) {
  return hass.states[entityId]?.state || FILTER_ALL;
}

function enabledToggle(hass, entityId, defaultValue = true) {
  const state = hass.states[entityId]?.state;
  return state === "on" ? true : state === "off" ? false : defaultValue;
}

function matchesFilter(selected, value) {
  return FILTER_DEFAULTS.has(selected) || selected === value;
}

function currentInterfaceField(state) {
  const value = state?.state;
  return typeof value === "string" &&
    !FILTER_DEFAULTS.has(value.toLocaleLowerCase())
    ? value
    : undefined;
}

function speedDuplexLabel(fields) {
  const parts = [];
  const speed = currentInterfaceField(fields?.get("speed"));
  if (speed !== undefined) {
    const numericSpeed = Number(speed);
    parts.push(`${Number.isFinite(numericSpeed) ? numericSpeed : speed} Mbps`);
  }

  const duplex = currentInterfaceField(fields?.get("duplex"));
  if (duplex !== undefined) {
    parts.push(duplex);
  }

  return parts.join(" / ") || undefined;
}

function interfaceFieldsByDevice(hass) {
  const fieldsByDevice = new Map();
  for (const state of Object.values(hass.states)) {
    if (state.attributes.fortios_kd_entry_type !== "interface") {
      continue;
    }

    const field = state.attributes.fortios_kd_interface_field;
    const entity = registryEntry(hass.entities, state.entity_id);
    if (!entity?.device_id || typeof field !== "string" || !field) {
      continue;
    }

    let fields = fieldsByDevice.get(entity.device_id);
    if (!fields) {
      fields = new Map();
      fieldsByDevice.set(entity.device_id, fields);
    }
    fields.set(field, state);
  }
  return fieldsByDevice;
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

function interfaceGraphModel(hass) {
  const preferredNames = preferredNamesByDevice(hass);
  const interfacePreferredNames = preferredNamesByDevice(hass, "interface");
  const selectedFortigate = selectedFilter(
    hass,
    "select.interface_graphs_firewall_filter",
  );
  const hideHardwareSwitchMembers = enabledToggle(
    hass,
    "switch.interface_graphs_hide_hardware_switch_members",
  );
  const hideWifiSsidInterfaces = enabledToggle(
    hass,
    "switch.interface_graphs_hide_wifi_ssid_interfaces",
  );
  const selectedLink = selectedFilter(
    hass,
    "select.interface_graphs_link_filter",
  );
  const selectedSpeedDuplex = selectedFilter(
    hass,
    "select.interface_graphs_speed_and_duplex_filter",
  );
  const selectedParent = selectedFilter(
    hass,
    "select.interface_graphs_parent_interface_filter",
  );
  const selectedLayout = selectedFilter(
    hass,
    "select.interface_graphs_graph_layout",
  );
  const selectedTimeSpan = selectedFilter(
    hass,
    "select.interface_graphs_time_span",
  );
  const hoursToShow = TIME_SPAN_HOURS.get(selectedTimeSpan) ?? 1;
  const graphLayout =
    selectedLayout === GRAPH_LAYOUT_SEPARATE
      ? GRAPH_LAYOUT_SEPARATE
      : GRAPH_LAYOUT_COMBINED;
  const matchingEntities = [];
  const fieldsByDevice = interfaceFieldsByDevice(hass);
  const signatureParts = [
    selectedFortigate,
    hideHardwareSwitchMembers,
    hideWifiSsidInterfaces,
    selectedLink,
    selectedSpeedDuplex,
    selectedParent,
    graphLayout,
    selectedTimeSpan,
  ];

  for (const state of Object.values(hass.states)) {
    if (state.attributes.fortios_kd_scope !== "interface") {
      continue;
    }

    const metric = state.attributes.fortios_kd_metric;
    if (!RATE_GRAPH_BY_METRIC.has(metric)) {
      continue;
    }

    const entity = registryEntry(hass.entities, state.entity_id);
    const interfaceDevice = registryEntry(hass.devices, entity?.device_id);
    const fortigateDevice = registryEntry(
      hass.devices,
      interfaceDevice?.via_device_id,
    );
    const fortigateName = preferredDeviceName(
      preferredNames,
      fortigateDevice,
      "FortiGate",
    );
    const vdomName = state.attributes.fortios_kd_vdom;
    const interfaceName = state.attributes.fortios_kd_interface;
    if (
      !fortigateDevice?.id ||
      typeof vdomName !== "string" ||
      !vdomName ||
      typeof interfaceName !== "string" ||
      !interfaceName
    ) {
      continue;
    }
    const interfaceDisplayName =
      interfacePreferredNames.get(interfaceDevice.id) || interfaceName;

    const fields = fieldsByDevice.get(entity.device_id);
    const kind = currentInterfaceField(fields?.get("kind"));
    const link = currentInterfaceField(fields?.get("link"));
    const speedDuplex = speedDuplexLabel(fields);
    const parent = currentInterfaceField(fields?.get("interface"));

    signatureParts.push(
      state.entity_id,
      entity.device_id,
      metric,
      fortigateName,
      vdomName,
      interfaceName,
      interfaceDisplayName,
      kind || "",
      link || "",
      speedDuplex || "",
      parent || "",
    );
    if (
      !matchesFilter(selectedFortigate, fortigateName) ||
      (hideHardwareSwitchMembers &&
        kind === INTERFACE_KIND_HARDWARE_SWITCH_MEMBER) ||
      (hideWifiSsidInterfaces && kind === INTERFACE_KIND_WIFI_SSID) ||
      !matchesFilter(selectedLink, link) ||
      !matchesFilter(selectedSpeedDuplex, speedDuplex) ||
      !matchesFilter(selectedParent, parent)
    ) {
      continue;
    }

    matchingEntities.push({
      entityId: state.entity_id,
      fortigateDeviceId: fortigateDevice.id,
      fortigateName,
      interfaceDisplayName,
      interfaceName,
      metric,
      vdomName,
    });
  }

  matchingEntities.sort(
    (left, right) =>
      left.fortigateName.localeCompare(right.fortigateName, undefined, {
        sensitivity: "base",
      }) ||
      left.vdomName.localeCompare(right.vdomName, undefined, {
        sensitivity: "base",
      }) ||
      left.interfaceName.localeCompare(right.interfaceName, undefined, {
        sensitivity: "base",
      }),
  );

  let groups;
  if (graphLayout === GRAPH_LAYOUT_SEPARATE) {
    const groupsByFortigate = new Map();
    for (const item of matchingEntities) {
      let group = groupsByFortigate.get(item.fortigateDeviceId);
      if (!group) {
        group = {
          key: item.fortigateDeviceId,
          title: item.fortigateName,
          items: [],
        };
        groupsByFortigate.set(item.fortigateDeviceId, group);
      }
      group.items.push(item);
    }

    groups = [...groupsByFortigate.values()].map((group) => {
      const interfaceCount = new Set(
        group.items.map((item) => `${item.vdomName}\u0000${item.interfaceName}`),
      ).size;
      return {
        ...group,
        subtitle: `${interfaceCount} interface${interfaceCount === 1 ? "" : "s"}`,
        cardConfigs: RATE_GRAPHS.flatMap((graph) => {
          const entities = group.items
            .filter((item) => item.metric === graph.metric)
            .map((item) => ({
              entity: item.entityId,
              name: `${item.vdomName} - ${item.interfaceDisplayName}`,
            }));
          return entities.length
            ? [
                {
                  type: "history-graph",
                  title: graph.title,
                  hours_to_show: hoursToShow,
                  expand_legend: true,
                  entities,
                },
              ]
            : [];
        }),
      };
    });
  } else {
    const interfaceCount = new Set(
      matchingEntities.map(
        (item) =>
          `${item.fortigateDeviceId}\u0000${item.vdomName}\u0000${item.interfaceName}`,
      ),
    ).size;
    groups = matchingEntities.length
      ? [
          {
            key: "combined",
            title: "Combined interface rates",
            subtitle: `${interfaceCount} interface${interfaceCount === 1 ? "" : "s"}`,
            cardConfigs: RATE_GRAPHS.flatMap((graph) => {
              const entities = matchingEntities
                .filter((item) => item.metric === graph.metric)
                .map((item) => ({
                  entity: item.entityId,
                  name:
                    selectedFortigate === FILTER_ALL
                      ? `${item.fortigateName} - ${item.vdomName} - ${item.interfaceDisplayName}`
                      : `${item.vdomName} - ${item.interfaceDisplayName}`,
                }));
              return entities.length
                ? [
                    {
                      type: "history-graph",
                      title: graph.title,
                      hours_to_show: hoursToShow,
                      expand_legend: true,
                      entities,
                    },
                  ]
                : [];
            }),
          },
        ]
      : [];
  }

  return {
    groups,
    signature: signatureParts.join("\u001e"),
  };
}

class FortiOSKDInterfaceGraphGrid extends HTMLElement {
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

    const model = interfaceGraphModel(hass);
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

    const nextModel = model || interfaceGraphModel(this._hass);
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
    const builtGroups = await Promise.all(
      model.groups.map(async (group) => ({
        ...group,
        cards: await Promise.all(
          group.cardConfigs.map((config) => helpers.createCardElement(config)),
        ),
      })),
    );

    if (buildVersion !== this._buildVersion) {
      return;
    }

    this._cards = builtGroups.flatMap((group) => group.cards);
    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
      }
      .groups {
        display: grid;
        gap: 16px;
      }
      .group-title {
        color: var(--primary-text-color);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-medium);
        padding: 4px 4px 0;
      }
      .group-subtitle {
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
        font-weight: normal;
        margin-left: 8px;
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
    container.className = "groups";

    if (!builtGroups.length) {
      const empty = document.createElement("ha-card");
      empty.innerHTML =
        '<div class="empty">No interface rate graphs match the selected filters.</div>';
      container.append(empty);
    } else {
      for (const group of builtGroups) {
        const section = document.createElement("section");
        const title = document.createElement("div");
        title.className = "group-title";
        title.textContent = group.title;
        const subtitle = document.createElement("span");
        subtitle.className = "group-subtitle";
        subtitle.textContent = group.subtitle;
        title.append(subtitle);

        const graphs = document.createElement("div");
        graphs.className = "graphs";
        for (const card of group.cards) {
          card.hass = this._hass;
          graphs.append(card);
        }

        section.append(title, graphs);
        container.append(section);
      }
    }

    this.shadowRoot.replaceChildren(style, container);
    if (this._cards.length) {
      this._watchLegends(this._cards, buildVersion);
    }
  }
}

if (!customElements.get(INTERFACE_GRAPH_CARD_ELEMENT)) {
  customElements.define(
    INTERFACE_GRAPH_CARD_ELEMENT,
    FortiOSKDInterfaceGraphGrid,
  );
}

function dashboardView() {
  return {
    title: "Interface Graphs",
    path: "interface-graphs",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "Interface Graph Filters",
            heading_style: "title",
          },
          {
            type: "entities",
            title: "Interface Graph Filters",
            entities: [
              {
                entity: "select.interface_graphs_firewall_filter",
                name: "Firewall",
              },
              {
                entity: "switch.interface_graphs_hide_hardware_switch_members",
                name: "Hide hardware switch members",
              },
              {
                entity: "switch.interface_graphs_hide_wifi_ssid_interfaces",
                name: "Hide WiFi SSID interfaces",
              },
              {
                entity: "select.interface_graphs_link_filter",
                name: "Link state",
              },
              {
                entity: "select.interface_graphs_speed_and_duplex_filter",
                name: "Speed / duplex",
              },
              {
                entity: "select.interface_graphs_parent_interface_filter",
                name: "Parent interface",
              },
              {
                entity: "select.interface_graphs_graph_layout",
                name: "Graph layout",
              },
              {
                entity: "select.interface_graphs_time_span",
                name: "Time span",
              },
            ],
            grid_options: { columns: "full" },
          },
          {
            type: "heading",
            heading: "Interface Rates",
            heading_style: "title",
          },
          {
            type: `custom:${INTERFACE_GRAPH_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
