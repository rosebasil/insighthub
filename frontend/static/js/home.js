const COHORT_ORDER = ["DX_KSA", "DX_JOR", "PAX_KSA", "PAX_JOR"];

function renderStatCards(stats, weekId) {
  const el = document.getElementById("stat-cards");
  el.innerHTML = `
    <a class="stat-card stat-card--accent-purple" href="/studies?week=${weekId}">
      <div class="stat-card__label">Studies</div>
      <div class="stat-card__value">${stats.studies_count}</div>
    </a>
    <a class="stat-card stat-card--accent-purple" href="/dashboards">
      <div class="stat-card__label">Dashboards</div>
      <div class="stat-card__value">${stats.dashboards_count}</div>
    </a>
    <a class="stat-card stat-card--accent-pink" href="#issues-panel">
      <div class="stat-card__label">Critical Issues</div>
      <div class="stat-card__value">${stats.critical_issues_count}</div>
    </a>
  `;
}

function renderHighlights(highlights) {
  const el = document.getElementById("highlights-grid");
  el.innerHTML = COHORT_ORDER.map((cohort) => {
    const bullets = highlights[cohort];
    const group = cohortGroup(cohort);
    if (!bullets || bullets.length === 0) {
      return `
        <div class="highlight-card empty" data-cohort-group="${group}">
          <h3><span class="cohort-tag">${group}</span>${cohortLabel(cohort)}</h3>
          <div>No highlights logged for this cohort this week.</div>
        </div>
      `;
    }
    const items = bullets
      .map((b) => {
        const isFlag = b.toLowerCase().startsWith("needs attention");
        return `<li class="${isFlag ? "needs-attention" : ""}">${b}</li>`;
      })
      .join("");
    return `
      <div class="highlight-card" data-cohort-group="${group}">
        <h3><span class="cohort-tag">${group}</span>${cohortLabel(cohort)}</h3>
        <ul>${items}</ul>
      </div>
    `;
  }).join("");
}

function renderSurveys(surveys) {
  const body = document.getElementById("surveys-body");
  if (surveys.length === 0) {
    body.innerHTML = `<tr><td colspan="4" class="empty-state">No surveys logged for this week.</td></tr>`;
    return;
  }
  body.innerHTML = surveys
    .map((s) => {
      const nameCell = s.dashboard_link
        ? `<a href="${s.dashboard_link}" target="_blank" rel="noopener">${s.name}</a>`
        : s.name;
      return `
        <tr>
          <td>${nameCell}</td>
          <td>${formatNumber(s.sent)}</td>
          <td>${formatNumber(s.responses)}</td>
          <td>
            <span class="completion-bar"><span class="completion-bar__fill" style="width:${s.completion_pct}%"></span></span>
            ${s.completion_pct}%
          </td>
        </tr>
      `;
    })
    .join("");
}

const STATUS_ORDER = ["New", "Under review", "Reported out", "Closed"];

function renderIssues(issuesData) {
  const { status_counts, items } = issuesData;
  const total = STATUS_ORDER.reduce((sum, s) => sum + (status_counts[s] || 0), 0);

  const bar = document.getElementById("issues-status-bar");
  bar.innerHTML = total
    ? STATUS_ORDER.filter((s) => status_counts[s] > 0)
        .map((s) => `<div class="status-bar__seg" data-status="${s}" style="width:${(status_counts[s] / total) * 100}%"></div>`)
        .join("")
    : "";

  const legend = document.getElementById("issues-legend");
  legend.innerHTML = STATUS_ORDER.map(
    (s) => `<span><span class="status-legend__dot" data-status="${s}"></span>${s} (${status_counts[s] || 0})</span>`
  ).join("");

  const list = document.getElementById("issues-list");
  if (items.length === 0) {
    list.innerHTML = `<div class="empty-state">No issues logged for this week.</div>`;
    return;
  }
  list.innerHTML = items
    .map((i) => {
      const ref = i.reference_id
        ? `<div class="issue-card__ref">${i.reference_type === "passenger" ? "Passenger" : "Driver"} ID: ${i.reference_id}</div>`
        : "";
      return `
        <div class="issue-card" data-status="${i.status}">
          <div class="issue-card__meta">
            <span>${i.source} &middot; ${i.category}</span>
            <span class="issue-card__status">${i.status}</span>
          </div>
          <div class="issue-card__desc">${i.description}</div>
          ${ref}
        </div>
      `;
    })
    .join("");
}

function statusPillClass(status) {
  switch (status) {
    case "GOOD":
      return "pill--good";
    case "REVIEW":
      return "pill--review";
    case "BELOW MIN":
      return "pill--below";
    default:
      return "pill--pending";
  }
}

function renderPerformance(perf) {
  const badge = document.getElementById("perf-badge");
  badge.textContent = `${perf.meta.cities_live} of ${perf.meta.cities_total} cities live on MSU survey`;

  const body = document.getElementById("perf-body");
  if (perf.rows.length === 0) {
    body.innerHTML = `<tr><td colspan="7" class="empty-state">No MSU / DIF sessions recorded for this week.</td></tr>`;
    return;
  }
  body.innerHTML = perf.rows
    .map((r) => {
      const minMet =
        r.min_met === true
          ? '<span class="pill-min-yes">YES</span>'
          : r.min_met === false
          ? '<span class="pill-min-no">NO</span>'
          : '<span class="pill-min-na">N/A</span>';
      const quality = r.quality === null ? "-" : r.quality.toFixed(1);
      const spreadWidth = Math.round((r.spread || 0) * 100);
      return `
        <tr>
          <td><strong>${r.name}</strong> &ndash; ${r.role}<br /><span style="color:var(--gray);font-size:12px;">${r.city} &middot; ${r.country}</span></td>
          <td>${r.completed}</td>
          <td>${minMet}</td>
          <td>${quality}</td>
          <td><span class="perf-spread"><span class="perf-spread__fill" style="width:${spreadWidth}%"></span></span></td>
          <td>${r.flags}</td>
          <td><span class="pill ${statusPillClass(r.status)}">${r.status}</span></td>
        </tr>
      `;
    })
    .join("");
}

async function loadWeek(weekId, weeks) {
  const week = weeks.find((w) => w.id === weekId);
  document.getElementById("week-range").textContent = week
    ? `${week.label} (${formatDateRange(week.start_date, week.end_date)})`
    : "";

  const summary = await fetchJSON(`/api/weeks/${weekId}/summary`);
  renderStatCards(summary.stats, weekId);
  renderHighlights(summary.highlights);
  renderSurveys(summary.surveys);
  renderIssues(summary.issues);
  renderPerformance(summary.performance);
}

(async function init() {
  const selectEl = document.getElementById("week-select");
  const { weeks, selectedId } = await initWeekPicker(selectEl, loadWeek);
  await loadWeek(selectedId, weeks);
})();
