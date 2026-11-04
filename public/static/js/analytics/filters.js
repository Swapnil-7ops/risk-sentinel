(function () {
  const allowed = ["level", "status", "asset_type", "owner", "control_theme", "source", "date_from", "date_to", "view"];
  let state = {};
  const listeners = [];
  function readUrl() {
    const params = new URLSearchParams(window.location.search);
    state = {};
    allowed.forEach((key) => { if (params.get(key)) state[key] = params.get(key); });
  }
  function notify() { listeners.forEach((listener) => listener({ ...state })); }
  function update(changes) {
    Object.keys(changes).forEach((key) => { if (allowed.includes(key)) { if (changes[key]) state[key] = changes[key]; else delete state[key]; } });
    const params = new URLSearchParams(state);
    history.pushState({}, "", `${window.location.pathname}${params.toString() ? "?" + params : ""}`);
    notify();
  }
  function toggle(changes) {
    const selected = Object.entries(changes).every(([key, value]) => String(state[key] || "") === String(value));
    update(Object.fromEntries(Object.keys(changes).map((key) => [key, selected ? "" : changes[key]])));
  }
  readUrl();
  window.AnalyticsFilters = { get: () => ({ ...state }), update, toggle, clear: () => { state = {}; history.pushState({}, "", window.location.pathname); notify(); }, subscribe: (listener) => { listeners.push(listener); listener({ ...state }); } };
  window.addEventListener("popstate", () => { readUrl(); notify(); });
})();
