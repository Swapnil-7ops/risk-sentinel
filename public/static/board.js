(function () {
  const cards = document.querySelectorAll("[draggable=true]");
  let dragged;
  cards.forEach((card) => {
    card.addEventListener("dragstart", () => { dragged = card; });
  });
  document.querySelectorAll(".board-column").forEach((column) => {
    column.addEventListener("dragover", (event) => event.preventDefault());
    column.addEventListener("drop", () => {
      if (!dragged) return;
      const form = document.createElement("form");
      form.method = "post";
      form.action = `/treatment-board/${dragged.dataset.mappingId}/status`;
      const csrf = document.querySelector("input[name=csrf_token]");
      form.innerHTML = `<input name="csrf_token" value="${csrf ? csrf.value : ""}"><input name="status" value="${column.dataset.status}">`;
      document.body.appendChild(form);
      form.submit();
    });
  });
})();
