/** Statuts UI des demandes (aligné AppRequests / dashboard). */

export const CALLBACK_REASON_LABELS = {
  question_rdv: "Question sur un rendez-vous",
  modifier: "Modifier un rendez-vous",
  annuler: "Annuler un rendez-vous",
  admin: "Question administrative",
  ordonnance: "Ordonnance / document",
  other: "Autre demande",
};

const LIVE_HANDOFF_STATUSES = new Set([
  "live_attempted",
  "live_forwarding_confirmed",
  "live_connected",
  "live_failed",
  "live_unconfirmed_timeout",
]);

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

export function isLiveTransferHandoff(handoff) {
  const mode = String(handoff?.mode || handoff?.handoff_mode || "").toLowerCase();
  const status = String(handoff?.status || handoff?.handoff_status || "").toLowerCase();
  return mode === "live_then_callback" && LIVE_HANDOFF_STATUSES.has(status);
}

export function linkedHandoffIds(callbacks = []) {
  return new Set(
    callbacks
      .map((c) => c.handoff_id)
      .filter(Boolean)
      .map((id) => String(id)),
  );
}

export function linkedCallIds(callbacks = []) {
  return new Set(
    callbacks
      .map((c) => String(c.call_id || "").trim())
      .filter(Boolean),
  );
}

export function shouldShowHandoffInRequestInbox(handoff, callbacks = []) {
  const handoffId = String(handoff?.id || "");
  if (!handoffId) return true;
  if (!linkedHandoffIds(callbacks).has(handoffId)) return true;
  return isLiveTransferHandoff(handoff);
}

/** Masque un appel TRANSFERRED si un rappel unifié callback_requests existe déjà pour le même call_id. */
export function shouldShowCallInRequestInbox(call, callbacks = []) {
  const callId = String(call?.call_id || call?.id || "").trim();
  if (!callId) return true;
  return !linkedCallIds(callbacks).has(callId);
}

export function callbackRequestSourceLabel(callback) {
  return String(callback?.source || "").toLowerCase() === "vocal_agent" ? "Appel vocal" : "Page publique";
}

export function callbackRequestStatusRaw(callback) {
  const handoffStatus = String(callback?.handoff_status || "").toLowerCase();
  if (handoffStatus) return handoffStatus;
  const raw = String(callback?.status || "new").toLowerCase();
  return raw === "new" ? "callback_created" : raw;
}

export function callbackRequestPriority(callback) {
  const priority = String(callback?.handoff_priority || "").toLowerCase();
  if (priority.includes("urgent")) return "Urgence";
  if (priority.includes("low") || priority.includes("faible")) return "Faible";
  return "Standard";
}

export function callbackRequestSummary(callback) {
  const reasonLabel =
    CALLBACK_REASON_LABELS[String(callback?.reason || "").toLowerCase()] ||
    String(callback?.reason || "Autre demande");
  return (String(callback?.message || "").trim() || reasonLabel);
}

export function classifyRequestType(callOrHandoff) {
  const source = callOrHandoff._source;
  const reason = String(callOrHandoff.reason || callOrHandoff.reason_category || "").toLowerCase();
  const summary = String(callOrHandoff.summary || "").toLowerCase();
  if (source === "callback_request") {
    return { type: "Rappel", typeKey: "callback" };
  }
  if (reason.includes("renew") || summary.includes("renouvel") || summary.includes("ordonnance")) {
    return { type: "Renouvellement", typeKey: "renewal" };
  }
  if (reason.includes("document") || summary.includes("certificat") || summary.includes("arrêt") || summary.includes("arret")) {
    return { type: "Document", typeKey: "document" };
  }
  if (reason.includes("question")) return { type: "Question", typeKey: "question" };
  if (source === "handoff" && isLiveTransferHandoff(callOrHandoff)) {
    return { type: "Transfert humain", typeKey: "transfer" };
  }
  if (source === "handoff") return { type: "Rappel", typeKey: "callback" };
  return { type: "Rappel", typeKey: "callback" };
}

function requestPriority(callOrHandoff) {
  const p = String(callOrHandoff.priority || callOrHandoff.handoff_priority || "").toLowerCase();
  const summary = String(callOrHandoff.summary || "").toLowerCase();
  if (p.includes("urgent") || summary.includes("urgence")) return "Urgence";
  if (p.includes("low") || p.includes("faible")) return "Faible";
  return "Standard";
}

function mapCallbackRequestRow(callback) {
  const statusRaw = callbackRequestStatusRaw(callback);
  return {
    id: `callback-${callback.id}`,
    patientName: callback.name || "Patient",
    type: "Rappel",
    typeKey: "callback",
    priority: callbackRequestPriority(callback),
    status_raw: statusRaw,
    summary: callbackRequestSummary(callback),
    phone: callback.phone || "",
    createdAtLabel: formatRequestDate(callback.created_at),
    createdAt: callback.created_at,
    source: callbackRequestSourceLabel(callback),
    callbackId: callback.id,
    handoffId: callback.handoff_id || null,
    callId: callback.call_id || null,
  };
}

/** Construit les lignes demandes (appels + handoffs + rappels unifiés). */
export function buildTenantRequestRows(calls = [], handoffs = [], callbacks = [], overrides = {}) {
  const fromCalls = calls
    .filter((c) => c.followup_state === "callback" || c.status === "TRANSFERRED" || c.reason_category === "urgency")
    .filter((c) => shouldShowCallInRequestInbox(c, callbacks))
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

  const fromHandoffs = handoffs
    .filter((h) => shouldShowHandoffInRequestInbox(h, callbacks))
    .map((h) => {
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
        source: isLiveTransferHandoff(h) ? "Transfert live" : "Appel vocal",
        handoffId: h.id || null,
      };
    });

  const fromCallbacks = callbacks.map((c) => mapCallbackRequestRow(c));

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
    .filter((c) => shouldShowCallInRequestInbox(c, callbacks))
    .map((c) => ({
      status_raw: c.followup_state === "processed" ? "processed" : "callback_created",
      priority: requestPriority(c),
      createdAt: c.started_at || c.last_event_at,
    }));

  const fromHandoffs = handoffs
    .filter((h) => shouldShowHandoffInRequestInbox(h, callbacks))
    .map((h) => ({
      status_raw: String(h.status || "").toLowerCase(),
      priority: requestPriority(h),
      createdAt: h.created_at,
    }));

  const fromCallbacks = callbacks.map((c) => ({
    status_raw: callbackRequestStatusRaw(c),
    priority: callbackRequestPriority(c),
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
