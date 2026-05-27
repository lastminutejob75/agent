/** Statuts UI des demandes (aligné AppRequests / dashboard). */

export function toUiStatus(rawStatus) {
  const raw = String(rawStatus || "").toLowerCase();
  if (raw === "processed" || raw === "cancelled") return "Traitées";
  if (raw.includes("live") || raw === "callback_scheduled") return "En cours";
  return "À traiter";
}

function minutesSince(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
}

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
  );
}

function requestPriority(callOrHandoff) {
  const p = String(callOrHandoff.priority || "").toLowerCase();
  if (p.includes("urgent") || p === "high") return "Urgence";
  if (p.includes("low") || p === "faible") return "Faible";
  return "Standard";
}

/** Construit les demandes visibles (appels + handoffs) pour compter les KPI dashboard. */
export function buildRequestItemsFromCallsAndHandoffs(calls = [], handoffs = []) {
  const fromCalls = calls
    .filter((c) => c.followup_state === "callback" || c.status === "TRANSFERRED" || c.reason_category === "urgency")
    .map((c) => ({
      status_raw: c.followup_state === "processed" ? "processed" : "callback_created",
      priority: requestPriority(c),
      createdAt: c.started_at || c.last_event_at,
    }));

  const fromHandoffs = handoffs.map((h) => ({
    status_raw: String(h.status || "").toLowerCase(),
    priority: requestPriority(h),
    createdAt: h.created_at,
  }));

  return [...fromHandoffs, ...fromCalls].map((item) => ({
    ...item,
    status: toUiStatus(item.status_raw),
  }));
}

export function summarizeRequestItems(items = []) {
  let handled = 0;
  let inProgress = 0;
  let toProcess = 0;
  let urgentOpen = 0;
  let handledToday = 0;
  const today = new Date();
  const activeDelays = [];

  for (const item of items) {
    if (item.status === "Traitées") {
      handled += 1;
      const created = new Date(String(item.createdAt || ""));
      if (!Number.isNaN(created.getTime()) && isSameDay(created, today)) {
        handledToday += 1;
      }
    } else if (item.status === "En cours") {
      inProgress += 1;
      const delay = minutesSince(item.createdAt);
      if (Number.isFinite(delay)) activeDelays.push(delay);
      if (item.priority === "Urgence") urgentOpen += 1;
    } else if (item.status === "À traiter") {
      toProcess += 1;
      const delay = minutesSince(item.createdAt);
      if (Number.isFinite(delay)) activeDelays.push(delay);
      if (item.priority === "Urgence") urgentOpen += 1;
    }
  }

  const avgResponseMinutes = activeDelays.length
    ? Math.round(activeDelays.reduce((sum, x) => sum + x, 0) / activeDelays.length)
    : null;

  return {
    handled,
    inProgress,
    toProcess,
    urgentOpen,
    handledToday,
    avgResponseMinutes,
  };
}
