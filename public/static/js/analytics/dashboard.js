(function () {
  const filters = window.AnalyticsFilters;
  const query = (state) => new URLSearchParams(Object.entries(state).filter(([, value]) => value));
  const renderKpis = (data) => {
    const labels = [["total_open", "Open risks"], ["critical", "Critical risks"], ["appetite_breaches", "Appetite breaches"], ["overdue_treatments", "Overdue treatments"]];
    document.querySelector("[data-kpis]").innerHTML = labels.map(([key, label]) => `<div class="card kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${data.kpis[key]}</div></div>`).join("");
  };
  const renderTop = (data) => { document.querySelector("[data-top-risks]").innerHTML = data.top_risks.length ? data.top_risks.map((risk) => `<tr><td><a href="/risks/${AnalyticsCharts.escape(risk.id)}">${AnalyticsCharts.escape(risk.title)}</a></td><td>${AnalyticsCharts.escape(risk.owner)}</td><td>${risk.score}</td><td><span class="badge ${risk.level.toLowerCase()}">${AnalyticsCharts.escape(risk.level)}</span></td></tr>`).join("") : `<tr><td colspan="4"><div class="empty">No risks match these filters.</div></td></tr>`; };
  const renderChips = (state) => { const target = document.querySelector("[data-filter-chips]"); target.innerHTML = Object.entries(state).filter(([, value]) => value).map(([key, value]) => `<button class="badge medium" type="button" data-remove-filter="${key}">${AnalyticsCharts.escape(key)}: ${AnalyticsCharts.escape(value)} ×</button>`).join(""); target.querySelectorAll("[data-remove-filter]").forEach((button) => button.addEventListener("click", () => filters.update({ [button.dataset.removeFilter]: "" }))); };
  async function load(state) {
    document.querySelector("[data-kpis]").classList.add("loading");
    try {
      const response = await fetch(`/api/analytics/summary?${query(state)}`);
      if (!response.ok) throw new Error("Unable to load analytics.");
      const data = await response.json();
      renderKpis(data); renderTop(data); AnalyticsCharts.update(data, state);
      renderChips(state);
      const exportLink = document.querySelector("[data-export-link]");
      exportLink.href = `${exportLink.dataset.exportBase}?${query(state)}`;
      document.querySelector("[data-drillthrough-link]").href = `/risks?${query(state)}`;
      document.querySelectorAll("[data-filter]").forEach((input) => { input.value = state[input.dataset.filter] || ""; });
    } catch (error) { document.querySelector("[data-kpis]").innerHTML = `<div class="card empty">Unable to load analytics. <button class="button secondary" type="button" data-retry>Retry</button></div>`; document.querySelector("[data-retry]")?.addEventListener("click", () => load(state)); }
    document.querySelector("[data-kpis]").classList.remove("loading");
  }
  document.querySelectorAll("[data-filter]").forEach((input) => input.addEventListener("change", () => filters.update({ [input.dataset.filter]: input.value })));
  document.querySelector("[data-clear-filters]").addEventListener("click", () => filters.clear());
  document.querySelectorAll("[data-export-chart]").forEach((button) => button.addEventListener("click", () => { const link = document.createElement("a"); link.href = AnalyticsCharts.exportPng(button.dataset.exportChart); link.download = `${button.dataset.exportChart}.png`; link.click(); }));
  document.querySelector("[data-bookmark-form]")?.addEventListener("submit", () => { document.querySelector("[data-bookmark-filters]").value = JSON.stringify(filters.get()); });
  fetch("/analytics/bookmarks").then((response) => response.ok ? response.json() : []).then((bookmarks) => {
    const select = document.querySelector("[data-bookmarks]");
    bookmarks.forEach((bookmark) => { const option = document.createElement("option"); option.value = JSON.stringify(bookmark.filters); option.textContent = bookmark.name; select.appendChild(option); });
  });
  document.querySelector("[data-bookmarks]")?.addEventListener("change", (event) => { if (event.target.value) filters.update(JSON.parse(event.target.value)); });
  filters.subscribe(load);
  new MutationObserver(() => { if (window.AnalyticsCharts) { const state = filters.get(); fetch(`/api/analytics/summary?${query(state)}`).then((response) => response.json()).then((data) => AnalyticsCharts.update(data, state)); } }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.addEventListener("resize", () => AnalyticsCharts.resize());
})();
