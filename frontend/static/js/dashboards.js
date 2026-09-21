function categoryTagClass(category) {
  if (category === "PAX") return "tag--pax";
  if (category === "DX") return "tag--dx";
  return "tag";
}

function renderDashboards(dashboards) {
  const grid = document.getElementById("dashboards-grid");
  document.getElementById("filter-count").textContent =
    `${dashboards.length} dashboard${dashboards.length === 1 ? "" : "s"}`;

  if (dashboards.length === 0) {
    grid.innerHTML = `<div class="empty-state">No dashboards match these filters.</div>`;
    return;
  }

  grid.innerHTML = dashboards
    .map(
      (d) => `
        <article class="item-card">
          <div class="item-card__tags">
            <span class="tag ${categoryTagClass(d.category)}">${d.category}</span>
          </div>
          <div class="item-card__title">${d.name}</div>
          <div class="item-card__summary">${d.description}</div>
          <div class="item-card__footer">
            <span>${d.owner}</span>
            <span>Updated ${d.updated_at}</span>
          </div>
          <a href="${d.link}" target="_blank" rel="noopener" style="font-size:12.5px;">Open dashboard &rarr;</a>
        </article>
      `
    )
    .join("");
}

async function applyFilters() {
  const category = document.getElementById("filter-category").value;
  const q = document.getElementById("filter-search").value.trim();

  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (q) params.set("q", q);

  const dashboards = await fetchJSON(`/api/dashboards?${params.toString()}`);
  renderDashboards(dashboards);
}

(async function init() {
  const dashboards = await fetchJSON("/api/dashboards");
  const categories = Array.from(new Set(dashboards.map((d) => d.category))).sort();

  const categorySelect = document.getElementById("filter-category");
  categorySelect.innerHTML =
    `<option value="">All categories</option>` +
    categories.map((c) => `<option value="${c}">${c}</option>`).join("");

  categorySelect.addEventListener("change", applyFilters);
  document.getElementById("filter-search").addEventListener("input", () => {
    clearTimeout(window.__searchDebounce);
    window.__searchDebounce = setTimeout(applyFilters, 200);
  });

  renderDashboards(dashboards);
})();
