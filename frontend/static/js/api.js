// Shared helpers used by every InsightHub page.

const COHORT_LABELS = {
  DX_KSA: "DX · KSA",
  DX_JOR: "DX · Jordan",
  PAX_KSA: "PAX · KSA",
  PAX_JOR: "PAX · Jordan",
};

function cohortLabel(cohort) {
  return COHORT_LABELS[cohort] || cohort;
}

function cohortGroup(cohort) {
  return cohort && cohort.startsWith("PAX") ? "PAX" : "DX";
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request to ${url} failed with ${res.status}`);
  }
  return res.json();
}

function formatNumber(n) {
  return Number(n).toLocaleString("en-US");
}

function formatDateRange(startISO, endISO) {
  const opts = { month: "short", day: "numeric" };
  const start = new Date(startISO + "T00:00:00");
  const end = new Date(endISO + "T00:00:00");
  return `${start.toLocaleDateString("en-US", opts)} - ${end.toLocaleDateString("en-US", opts)}`;
}

function markActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll(".sidebar nav a").forEach((link) => {
    const href = link.getAttribute("href");
    const isActive = href === path || (href !== "/" && path.startsWith(href));
    link.classList.toggle("active", isActive);
  });
}

const WEEK_STORAGE_KEY = "insighthub:selected-week";

function getStoredWeek() {
  try {
    return localStorage.getItem(WEEK_STORAGE_KEY);
  } catch (e) {
    return null;
  }
}

function storeWeek(weekId) {
  try {
    localStorage.setItem(WEEK_STORAGE_KEY, weekId);
  } catch (e) {
    /* ignore - private browsing etc. */
  }
}

/**
 * Populate a <select> with weeks fetched from /api/weeks, restoring the
 * last-picked week from localStorage when present, and wiring onChange.
 * Returns the list of weeks and the id that ended up selected.
 */
async function initWeekPicker(selectEl, onChange) {
  const weeks = await fetchJSON("/api/weeks");
  const stored = getStoredWeek();
  const current = weeks.find((w) => w.is_current) || weeks[weeks.length - 1];
  const initial = weeks.find((w) => w.id === stored) ? stored : current.id;

  selectEl.innerHTML = weeks
    .slice()
    .reverse()
    .map((w) => {
      const suffix = w.is_current ? " (current)" : "";
      return `<option value="${w.id}" ${w.id === initial ? "selected" : ""}>${w.label}${suffix}</option>`;
    })
    .join("");

  selectEl.addEventListener("change", () => {
    storeWeek(selectEl.value);
    onChange(selectEl.value, weeks);
  });

  return { weeks, selectedId: initial };
}

document.addEventListener("DOMContentLoaded", markActiveNav);
