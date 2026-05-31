/** Statuts UI des demandes (aligné AppRequests / dashboard). */

export function toUiStatus(rawStatus) {
  const raw = String(rawStatus || "").toLowerCase();
  if (raw === "processed" || raw === "cancelled") return "Traitées";
  if (raw.includes("live") || raw === "callback_scheduled") return "En cours";
  return "À traiter";
}

export function formatRequestDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === now.toDateString()) {
    return `Aujourd'hui ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
  }
  if (date.toDateString() === yesterday.toDateString()) {
    return `Hier ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return `${date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function classifyRequestType(callOrHandoff) {
  const source = callOrHandoff._source;
  const reason = String(callOrHandoff.reason || callOrHandoff.reason_category || "").toLowerCase();
  const summary = String(callOrHandoff.summary || "").toLowerCase();
  if (source === "callback_request") {
    return { type: "Rappel page publique", typeKey: "callback" };
  }
  if (reason.includes("renew") || summary.includes("renouvel") || summary.includes("ordonnance")) {
    return { type: "Renouvellement", typeKey: "renewal" };
  }
  if (reason.includes("document") || summary.includes("certificat") || summary.includes("arrêt") || summary.includes("arret")) {
    return { type: "Document", typeKey: "document" };
  }
  if (reason.includes("question")) return { type: "Question", typeKey: "question" };
  if (source === "handoff") return { type: "Transfert humain", typeKey: "transfer" };
  return { type: "Rappel", typeKey: "callback" };
}

function requestPriority(callOrHandoff) {
  const p = String(callOrHandoff.priority || "").toLowerCase();
  const summary = String(callOrHandoff.summary || "").toLowerCase();
  if (p.includes("urgent") || summary.includes("urgence")) return "Urgence";
  if (p.includes("low") || p.includes("faible")) return "Faible";
  return "Standard";
}

/** Construit les lignes demandes (appels + handoffs + rappels page publique). */
export function buildTenantRequestRows(calls = [], handoffs = [], callbacks = [], overrides = {}) {
  const fromCalls = calls
    .filter((c) => c.followup_state === "callback" || c.status === "TRANSFERRED" || c.reason_category === "urgency")
    .map((c) => {
      const t = classifyRequestType({ ...c, _source: "call" });
      const statusRaw = c.followup_state === "processed" ? "processed" : "callback_created";
      return {
        id: `call-${c.call_id || c.id}`,
        patientName: c.patient_name || "Patient",
        type: t.type,
        typeKey: t.typeKey,
        priority: requestPriority(c),
        status_raw: statusRaw,
        summary: c.summary || c.reason_label || "Demande transférée nécessitant une action humaine.",
        phone: c.customer_number || "",
        createdAtLabel: formatRequestDate(c.started_at || c.last_event_at),
        createdAt: c.started_at || c.last_event_at,
        source: "Via appel",
      };
    });

  const fromHandoffs = handoffs.map((h) => {
    const t = classifyRequestType({ ...h, _source: "handoff" });
    const rawStatus = String(h.status || "").toLowerCase();
    return {
      id: `req-${String(h.id || "").padStart(3, "0")}`,
      patientName: h.display_name || "Patient",
      type: t.type,
      typeKey: t.typeKey,
      priority: requestPriority(h),
      status_raw: rawStatus,
      summary: h.summary || h.reason || "Demande transférée nécessitant une action humaine.",
      phone: h.patient_phone || "",
      createdAtLabel: formatRequestDate(h.created_at),
      createdAt: h.created_at,
      source: "Via transfert",
    };
  });

  const fromCallbacks = callbacks.map((c) => {
    const reasonLabel = {
      question_rdv: "Question sur un rendez-vous",
      modifier: "Modifier un rendez-vous",
      annuler: "Annuler un rendez-vous",
      admin: "Question administrative",
      ordonnance: "Ordonnance / document",
      other: "Autre demande",
    }[String(c.reason || "").toLowerCase()] || String(c.reason || "Autre demande");
    const rawStatus = String(c.status || "new").toLowerCase();
    const statusRaw = rawStatus === "new" ? "callback_created" : rawStatus;
    const t = classifyRequestType({ ...c, _source: "callback_request" });
    return {
      id: `callback-${c.id}`,
      patientName: c.name || "Patient",
      type: t.type,
      typeKey: t.typeKey,
      priority: "Standard",
      status_raw: statusRaw,
      summary: (c.message || "").trim() || reasonLabel,
      phone: c.phone || "",
      createdAtLabel: formatRequestDate(c.created_at),
      createdAt: c.created_at,
      source: "Page publique",
    };
  });

  return [...fromHandoffs, ...fromCalls, ...fromCallbacks]
    .map((item) => {
      const override = overrides[item.id];
      const statusRaw = override?.status_raw ? String(override.status_raw).toLowerCase() : item.status_raw;
      return {
        ...item,
        status_raw: statusRaw,
        status: toUiStatus(statusRaw),
      };
    })
    .sort((a, b) => new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime());
}

/** Demandes ouvertes pour un numéro patient normalisé. */
export function filterOpenPatientRequests(rows, phoneNorm, normalizePhoneFn) {
  if (!phoneNorm) return [];
  return rows.filter((row) => {
    const rowPhone = normalizePhoneFn(String(row.phone || ""));
    if (!rowPhone || rowPhone !== phoneNorm) return false;
    return row.status === "À traiter" || row.status === "En cours";
  });
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

/** Construit les demandes visibles (appels + handoffs + callbacks) pour compter les KPI dashboard. */
export function buildRequestItemsFromCallsAndHandoffs(calls = [], handoffs = [], callbacks = []) {
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

  const fromCallbacks = callbacks.map((c) => ({
    status_raw: String(c.status || "new").toLowerCase() === "new" ? "callback_created" : String(c.status || "").toLowerCase(),
    priority: "Standard",
    createdAt: c.created_at,
  }));

  return [...fromHandoffs, ...fromCalls, ...fromCallbacks].map((item) => ({
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
