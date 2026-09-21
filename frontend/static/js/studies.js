function statusChipLabel(status) {
  return status;
}

function renderStudies(studies) {
  const grid = document.getElementById("studies-grid");
  document.getElementById("filter-count").textContent =
    `${studies.length} stud${studies.length === 1 ? "y" : "ies"}`;

  if (studies.length === 0) {
    grid.innerHTML = `<div class="empty-state">No studies match these filters.</div>`;
    return;
  }

  grid.innerHTML = studies
    .map((s) => {
      const group = cohortGroup(s.cohort);
      const tagClass = group === "PAX" ? "tag--pax" : "tag--dx";
      return `
        <article class="item-card">
          <div class="item-card__tags">
            <span class="tag ${tagClass}">${cohortLabel(s.cohort)}</span>
            <span class="tag">${s.type}</span>
          </div>
          <div class="item-card__title">${s.title}</div>
          <div class="item-card__summary">${s.summary}</div>
          <div class="item-card__footer">
            <span>${s.owner} &middot; ${s.published_date}</span>
            <span class="status-chip">${statusChipLabel(s.status)}</span>
          </div>
          ${s.link ? `<a href="${s.link}" target="_blank" rel="noopener" style="font-size:12.5px;">Open dashboard &rarr;</a>` : ""}
        </article>
      `;
    })
    .join("");
}

async function applyFilters() {
  const week = document.getElementById("filter-week").value;
  const cohort = document.getElementById("filter-cohort").value;
  const type = document.getElementById("filter-type").value;
  const q = document.getElementById("filter-search").value.trim();

  const params = new URLSearchParams();
  if (week) params.set("week_id", week);
  if (cohort) params.set("cohort", cohort);
  if (type) params.set("type", type);
  if (q) params.set("q", q);

  const studies = await fetchJSON(`/api/studies?${params.toString()}`);
  renderStudies(studies);
}

function populateSelect(selectEl, values, labelFn) {
  const current = selectEl.value;
  const extra = values
    .map((v) => `<option value="${v}">${labelFn ? labelFn(v) : v}</option>`)
    .join("");
  selectEl.innerHTML = selectEl.querySelector("option[value='']").outerHTML + extra;
  if (values.includes(current)) selectEl.value = current;
}

(async function init() {
  const filters = await fetchJSON("/api/studies/filters");

  const weekSelect = document.getElementById("filter-week");
  populateSelect(
    weekSelect,
    filters.weeks.slice().reverse().map((w) => w.id),
    (id) => filters.weeks.find((w) => w.id === id).label
  );

  const cohortSelect = document.getElementById("filter-cohort");
  populateSelect(cohortSelect, filters.cohorts, cohortLabel);

  const typeSelect = document.getElementById("filter-type");
  populateSelect(typeSelect, filters.types);

  const urlParams = new URLSearchParams(window.location.search);
  const weekFromUrl = urlParams.get("week");
  if (weekFromUrl && filters.weeks.some((w) => w.id === weekFromUrl)) {
    weekSelect.value = weekFromUrl;
  }

  ["filter-week", "filter-cohort", "filter-type"].forEach((id) =>
    document.getElementById(id).addEventListener("change", applyFilters)
  );
  document.getElementById("filter-search").addEventListener("input", () => {
    clearTimeout(window.__searchDebounce);
    window.__searchDebounce = setTimeout(applyFilters, 200);
  });

  await applyFilters();
})();
