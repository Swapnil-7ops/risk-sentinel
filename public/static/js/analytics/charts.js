(function () {
  const charts = {};
  const colors = () => {
    const root = getComputedStyle(document.documentElement);
    return { surface: root.getPropertyValue("--surface-1").trim(), text: root.getPropertyValue("--text-1").trim(), muted: root.getPropertyValue("--text-2").trim(), accent: root.getPropertyValue("--accent").trim(), low: root.getPropertyValue("--low").trim(), medium: root.getPropertyValue("--medium").trim(), high: root.getPropertyValue("--high").trim(), critical: root.getPropertyValue("--critical").trim(), border: root.getPropertyValue("--border").trim() };
  };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const tooltip = (formatter, trigger = "item") => ({ trigger, renderMode: "html", className: "chart-tooltip", confine: true, formatter });
  const itemTooltip = (item) => `<span class="chart-tooltip-label">${esc(item.name || item.seriesName || "")}</span><br><span class="chart-tooltip-value">${esc(item.value)}</span>`;
  const axisTooltip = (items) => items.map((item) => `<span class="chart-tooltip-label">${esc(item.seriesName || item.name || "")}</span>: <span class="chart-tooltip-value">${esc(item.value)}</span>`).join("<br>");
  function init(name, element, option, onClick) {
    charts[name]?.dispose();
    charts[name] = echarts.init(element, null, { renderer: "canvas" });
    charts[name].setOption(option);
    if (onClick) charts[name].on("click", onClick);
  }
  function update(data, filters) {
    const c = colors();
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    init("heatmap", document.querySelector('[data-chart="heatmap"]'), { animation: !reducedMotion, tooltip: tooltip((item) => `<span class="chart-tooltip-label">Likelihood ${esc(item.value[0])}, Impact ${esc(item.value[1])}</span><br><span class="chart-tooltip-value">${esc(item.value[2])}</span>`), xAxis: { type: "category", data: [1,2,3,4,5], name: "Likelihood" }, yAxis: { type: "category", data: [1,2,3,4,5], name: "Impact" }, visualMap: { min: 0, max: Math.max(...data.heatmap.map((item) => item.count), 1), calculable: false, inRange: { color: [c.low, c.medium, c.high, c.critical] } }, series: [{ type: "heatmap", data: data.heatmap.map((item) => [item.likelihood - 1, item.impact - 1, item.count]) }] }, (item) => window.AnalyticsFilters.toggle({ likelihood: item.value[0] + 1, impact: item.value[1] + 1 }));
    init("levels", document.querySelector('[data-chart="levels"]'), { animation: !reducedMotion, tooltip: tooltip(itemTooltip), series: [{ type: "pie", radius: ["45%", "72%"], data: data.levels.map((item) => ({ name: item.level, value: item.count })), label: { color: c.text } }] }, (item) => window.AnalyticsFilters.toggle({ level: item.name }));
    init("assets", document.querySelector('[data-chart="assets"]'), { animation: !reducedMotion, tooltip: tooltip(axisTooltip, "axis"), xAxis: { type: "category", data: data.asset_types.map((item) => item.type), axisLabel: { color: c.muted } }, yAxis: { type: "value", axisLabel: { color: c.muted } }, series: [{ type: "bar", data: data.asset_types.map((item) => item.count), itemStyle: { color: c.accent } }] }, (item) => window.AnalyticsFilters.toggle({ asset_type: data.asset_types[item.dataIndex].type }));
    init("trend", document.querySelector('[data-chart="trend"]'), { animation: !reducedMotion, tooltip: tooltip(axisTooltip, "axis"), xAxis: { type: "category", data: data.trend.points?.map((item) => item.period) || [] }, yAxis: { type: "value" }, series: [{ name: "Opened", type: "line", data: data.trend.points?.map((item) => item.opened) || [], smooth: true }, { name: "Closed", type: "line", data: data.trend.points?.map((item) => item.closed) || [], smooth: true }] });
    init("treatments", document.querySelector('[data-chart="treatments"]'), { animation: !reducedMotion, tooltip: tooltip(axisTooltip, "axis"), xAxis: { type: "category", data: data.treatments.map((item) => item.status) }, yAxis: { type: "value" }, series: [{ type: "bar", data: data.treatments.map((item) => item.count), itemStyle: { color: c.accent } }] });
    init("coverage", document.querySelector('[data-chart="coverage"]'), { animation: !reducedMotion, tooltip: tooltip(axisTooltip, "axis"), xAxis: { type: "category", data: data.coverage.map((item) => item.theme), axisLabel: { color: c.muted } }, yAxis: { type: "value" }, series: [{ type: "bar", data: data.coverage.map((item) => item.implemented), itemStyle: { color: c.accent } }] });
  }
  window.AnalyticsCharts = { update, resize: () => Object.values(charts).forEach((chart) => chart.resize()), escape: esc, exportPng: (name) => charts[name]?.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: colors().surface }) };
})();
