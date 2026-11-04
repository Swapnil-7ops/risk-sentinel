(function () {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  const originalFetch = window.fetch;
  window.fetch = (input, init = {}) => {
    const method = (init.method || "GET").toUpperCase();
    if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes(method)) {
      init.headers = { ...(init.headers || {}), "X-CSRFToken": csrfToken };
    }
    return originalFetch(input, init);
  };
  const root = document.documentElement;
  const savedTheme = localStorage.getItem("grc-theme") || root.dataset.theme || "dark";
  root.dataset.theme = savedTheme;
  const updateThemeToggle = (theme) => {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const nextTheme = theme === "dark" ? "light" : "dark";
      button.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
      button.title = `Switch to ${nextTheme} theme`;
      const label = button.querySelector(".theme-toggle-label");
      if (label) label.textContent = nextTheme[0].toUpperCase() + nextTheme.slice(1);
      const icon = button.querySelector(".theme-toggle-icon");
      if (icon) icon.textContent = nextTheme === "light" ? "☼" : "☾";
    });
  };
  updateThemeToggle(savedTheme);
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const theme = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = theme;
      localStorage.setItem("grc-theme", theme);
      updateThemeToggle(theme);
    });
  });
  const sidebar = document.querySelector(".sidebar");
  const backdrop = document.querySelector("[data-sidebar-backdrop]");
  const setSidebarOpen = (open) => {
    sidebar?.classList.toggle("mobile-open", open);
    backdrop?.classList.toggle("is-visible", open);
    document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    });
  };
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 700px)").matches) {
        setSidebarOpen(!sidebar?.classList.contains("mobile-open"));
      } else {
        sidebar?.classList.toggle("collapsed");
      }
    });
  });
  backdrop?.addEventListener("click", () => setSidebarOpen(false));
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setSidebarOpen(false)));
  document.querySelectorAll("[data-risk-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.riskTab;
      document.querySelectorAll("[data-risk-tab]").forEach((tab) => {
        const active = tab === button;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
      });
      document.querySelectorAll(".risk-panel").forEach((panel) => {
        panel.hidden = panel.id !== target;
        panel.classList.toggle("is-active", panel.id === target);
      });
    });
  });
  const score = () => {
    const likelihood = Number(document.querySelector("[name=likelihood]")?.value || 0);
    const impact = Number(document.querySelector("[name=impact]")?.value || 0);
    const value = likelihood * impact;
    const level = value >= 17 ? "Critical" : value >= 10 ? "High" : value >= 5 ? "Medium" : "Low";
    const target = document.querySelector("[data-score-value]");
    const levelTarget = document.querySelector("[data-score-level]");
    if (target) target.textContent = value;
    if (levelTarget) { levelTarget.textContent = level; levelTarget.className = "badge " + level.toLowerCase(); }
    document.querySelectorAll("[data-range-output]").forEach((output) => {
      const input = document.querySelector(`[name=${output.dataset.rangeOutput}]`);
      if (input) output.textContent = input.value;
    });
  };
  document.querySelectorAll("[name=likelihood], [name=impact]").forEach((input) => input.addEventListener("input", score));
  score();
})();
