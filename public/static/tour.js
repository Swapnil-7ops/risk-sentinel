(function () {
  if (localStorage.getItem("risk-sentinel-tour-complete")) return;
  const steps = [
    ["Welcome", "Use the filters to focus the risk picture."],
    ["KPIs", "Review open risks, critical exposure, appetite breaches, and overdue treatments."],
    ["Charts", "Charts include text labels so severity is not conveyed by color alone."],
    ["Report", "Download a PDF report for review and sharing."]
  ];
  let index = 0;
  const dialog = document.createElement("dialog");
  dialog.setAttribute("aria-label", "Dashboard tour");
  dialog.innerHTML = '<div class="card-body"><h2 data-tour-title></h2><p data-tour-text></p><div class="toolbar"><button type="button" class="button secondary" data-tour-skip>Skip</button><button type="button" class="button" data-tour-next>Next</button></div></div>';
  document.body.appendChild(dialog);
  const render = () => {
    dialog.querySelector("[data-tour-title]").textContent = steps[index][0];
    dialog.querySelector("[data-tour-text]").textContent = steps[index][1];
    dialog.querySelector("[data-tour-next]").textContent = index === steps.length - 1 ? "Done" : "Next";
  };
  const close = () => { localStorage.setItem("risk-sentinel-tour-complete", "1"); dialog.close(); };
  dialog.querySelector("[data-tour-skip]").addEventListener("click", close);
  dialog.querySelector("[data-tour-next]").addEventListener("click", () => { if (index === steps.length - 1) close(); else { index += 1; render(); } });
  dialog.addEventListener("cancel", close);
  render();
  dialog.showModal();
}());
