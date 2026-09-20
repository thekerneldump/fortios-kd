const VDOM_GRAPH_CARD_ELEMENT = "fortios-kd-vdom-resource-graph-grid";
const STRATEGY_ELEMENT =
  "ll-strategy-dashboard-fortios-kd-vdom-resources";
const FILTER_ALL = "All";
const GRAPH_LAYOUT_COMBINED = "Combined by resource";
const GRAPH_LAYOUT_SEPARATE = "Separate by VDOM";
const FILTER_DEFAULTS = new Set([
  FILTER_ALL,
  "unknown",
  "unavailable",
  "none",
  "",
]);
const RESOURCE_GRAPHS = [
  { metric: "cpu", title: "CPU usage" },
  { metric: "memory", title: "Memory usage" },
  { metric: "session_current_usage", title: "Sessions" },
  { metric: "session_usage_percent", title: "Session Usage Percent" },
];
const RESOURCE_GRAPH_BY_METRIC = new Map(
  RESOURCE_GRAPHS.map((graph) => [graph.metric, graph]),
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

class FortiOSKDVDOMResourcesDashboardStrategy extends HTMLElement {
  static getCreateSuggestions(_hass) {
    return {
      title: "KD VDOM Resources",
      icon: "mdi:server-network",
    };
  }

  static async generate(config, _hass) {
    return {
      title: config.title || "KD VDOM Resources",
      views: [dashboardView()],
    };
  }
}

if (!customElements.get(STRATEGY_ELEMENT)) {
  customElements.define(
    STRATEGY_ELEMENT,
    FortiOSKDVDOMResourcesDashboardStrategy,
  );
}

window.customStrategies = window.customStrategies || [];

if (
  !window.customStrategies.some(
    (strategy) => strategy.type === "fortios-kd-vdom-resources",
  )
) {
  window.customStrategies.push({
    type: "fortios-kd-vdom-resources",
    strategyType: "dashboard",
    name: "FortiOS KD VDOM Resources",
    description:
      "Graph FortiGate CPU, memory, and session utilization by virtual domain.",
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

function selectedFilter(hass, entityId) {
  return hass.states[entityId]?.state || FILTER_ALL;
}

function matchesFilter(selected, value) {
  return FILTER_DEFAULTS.has(selected) || selected === value;
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

function vdomResourceModel(hass) {
  const selectedFortigate = selectedFilter(
    hass,
    "select.vdom_resources_firewall_filter",
  );
  const selectedVdom = selectedFilter(
    hass,
    "select.vdom_resources_vdom_filter",
  );
  const selectedLayout = selectedFilter(
    hass,
    "select.vdom_resources_graph_layout",
  );
  const graphLayout =
    selectedLayout === GRAPH_LAYOUT_SEPARATE
      ? GRAPH_LAYOUT_SEPARATE
      : GRAPH_LAYOUT_COMBINED;
  const matchingEntities = [];
  const signatureParts = [selectedFortigate, selectedVdom, graphLayout];

  for (const state of Object.values(hass.states)) {
    if (state.attributes.fortios_kd_scope !== "vdom") {
      continue;
    }

    const metric = state.attributes.fortios_kd_metric;
    const graph = RESOURCE_GRAPH_BY_METRIC.get(metric);
    if (!graph) {
      continue;
    }

    const entity = registryEntry(hass.entities, state.entity_id);
    const vdomDevice = registryEntry(hass.devices, entity?.device_id);
    const fortigateDevice = registryEntry(
      hass.devices,
      vdomDevice?.via_device_id,
    );
    const fortigateName = registryName(fortigateDevice, "FortiGate");
    const vdomName = state.attributes.fortios_kd_vdom;
    if (!entity?.device_id || typeof vdomName !== "string" || !vdomName) {
      continue;
    }

    signatureParts.push(
      state.entity_id,
      entity.device_id,
      metric,
      fortigateName,
      vdomName,
    );

    if (
      !matchesFilter(selectedFortigate, fortigateName) ||
      !matchesFilter(selectedVdom, vdomName)
    ) {
      continue;
    }

    matchingEntities.push({
      deviceId: entity.device_id,
      entityId: state.entity_id,
      fortigateName,
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
      }),
  );

  let groups;
  if (graphLayout === GRAPH_LAYOUT_SEPARATE) {
    const groupsByDevice = new Map();
    for (const item of matchingEntities) {
      let group = groupsByDevice.get(item.deviceId);
      if (!group) {
        group = {
          key: item.deviceId,
          title: `VDOM ${item.vdomName}`,
          subtitle: item.fortigateName,
          entitiesByMetric: new Map(),
        };
        groupsByDevice.set(item.deviceId, group);
      }
      group.entitiesByMetric.set(item.metric, item.entityId);
    }

    groups = [...groupsByDevice.values()].map((group) => ({
      ...group,
      cardConfigs: RESOURCE_GRAPHS.flatMap((graph) => {
        const entityId = group.entitiesByMetric.get(graph.metric);
        return entityId
          ? [
              {
                type: "history-graph",
                title: graph.title,
                hours_to_show: 24,
                entities: [{ entity: entityId, name: group.title }],
              },
            ]
          : [];
      }),
    }));
  } else {
    const vdomCount = new Set(
      matchingEntities.map((item) => item.deviceId),
    ).size;
    groups = matchingEntities.length
      ? [
          {
            key: "combined",
            title: "Combined resource graphs",
            subtitle: `${vdomCount} matching VDOM${vdomCount === 1 ? "" : "s"}`,
            cardConfigs: RESOURCE_GRAPHS.flatMap((graph) => {
              const entities = matchingEntities
                .filter((item) => item.metric === graph.metric)
                .map((item) => ({
                  entity: item.entityId,
                  name: `${item.fortigateName} · ${item.vdomName}`,
                }));
              return entities.length
                ? [
                    {
                      type: "history-graph",
                      title: graph.title,
                      hours_to_show: 24,
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

class FortiOSKDVDOMResourceGraphGrid extends HTMLElement {
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

    const model = vdomResourceModel(hass);
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

    const nextModel = model || vdomResourceModel(this._hass);
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
          group.cardConfigs.map((config) =>
            helpers.createCardElement(config),
          ),
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
        grid-template-columns: repeat(auto-fit, minmax(min(360px, 100%), 1fr));
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
        '<div class="empty">No VDOM resource graphs match the selected filters.</div>';
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

if (!customElements.get(VDOM_GRAPH_CARD_ELEMENT)) {
  customElements.define(
    VDOM_GRAPH_CARD_ELEMENT,
    FortiOSKDVDOMResourceGraphGrid,
  );
}

function dashboardView() {
  return {
    title: "VDOM Resources",
    path: "vdom-resources",
    type: "sections",
    max_columns: 4,
    sections: [
      {
        type: "grid",
        column_span: 4,
        cards: [
          {
            type: "heading",
            heading: "VDOM Resource Filters",
            heading_style: "title",
          },
          {
            type: "entities",
            title: "VDOM Resource Filters",
            entities: [
              {
                entity: "select.vdom_resources_firewall_filter",
                name: "Firewall",
              },
              {
                entity: "select.vdom_resources_vdom_filter",
                name: "VDOM",
              },
              {
                entity: "select.vdom_resources_graph_layout",
                name: "Graph layout",
              },
            ],
            grid_options: { columns: "full" },
          },
          {
            type: "heading",
            heading: "VDOM Resources",
            heading_style: "title",
          },
          {
            type: `custom:${VDOM_GRAPH_CARD_ELEMENT}`,
            grid_options: { columns: "full" },
          },
        ],
      },
    ],
  };
}
