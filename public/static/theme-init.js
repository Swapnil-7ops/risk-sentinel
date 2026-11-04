(function () {
  try {
    document.documentElement.dataset.theme = localStorage.getItem("grc-theme") || "dark";
  } catch (_error) {
    document.documentElement.dataset.theme = "dark";
  }
  document.documentElement.dataset.themeReady = "true";
})();
