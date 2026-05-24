import { api } from "./api.js";

function normalizePhone(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return raw.replace(/[^\d+]/g, "");
}

function formatPhone(value) {
  const raw = String(value || "").trim();
  return raw || "";
}

function formatTime(value) {
  const dt = new Date(String(value || ""));
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function formatDateLabel(value) {
  const dt = new Date(String(value || ""));
  if (Number.isNaN(dt.getTime())) return "—";
  const now = new Date();
  const sameDay = dt.toDateString() === now.toDateString();
  if (sameDay) return "Aujourd'hui";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (dt.toDateString() === yesterday.toDateString()) return "Hier";
  return dt.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

function formatDuration(call) {
  const sec = Number(call?.duration_sec);
  if (Number.isFinite(sec) && sec >= 0) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  const fromApi = String(call?.duration || "").trim();
  if (fromApi) return fromApi;
  return "00:00";
}

function inferType(call) {
  const status = String(call?.status || "").toLowerCase();
  const reason = String(call?.reason_category || "").toLowerCase();
  const summary = String(call?.summary || "").toLowerCase();
  const followup = String(call?.followup_state || "").toLowerCase();

  if (reason === "urgency" || /urgence|douleur thorac|h[eé]morrag|sensible/.test(summary)) return "sensible";
  if (/annul/.test(summary)) return "annulation";
  if (/reprogramm|d[eé]plac|deplac/.test(summary)) return "deplacement";
  if (followup === "callback" || /rappel/.test(summary)) return "a-rappeler";
  if (status === "abandoned" || status === "missed" || status === "transferred") return "appel-manque";
  if (reason === "agenda" || status === "confirmed" || /rdv|rendez-vous/.test(summary)) return "rendez-vous";
  return "information";
}

function inferStatus(call) {
  const status = String(call?.status || "").toLowerCase();
  const followup = String(call?.followup_state || "").toLowerCase();
  if (followup === "processed") return "résolu";
  if (status === "abandoned" || status === "missed") return "manqué";
  if (followup === "callback" || status === "transferred") return "à traiter";
  return "traité";
}

/** Journal d’appels : patient « avec fiche » = identité validée sur la fiche patient du dashboard (`validated_name` ≥ 2 car., comme `patient_has_file` à l’agenda). */
export function patientDashboardFileHasValidatedIdentity(patient) {
  const p = patient || {};
  return String(p.validated_name || "").trim().length >= 2;
}

function shortCallRef(call) {
  const value = String(call?.call_id || call?.id || "").trim();
  if (!value) return "";
  return value.slice(-6).toUpperCase();
}

function unknownDisplayName(call, masked, phoneRaw) {
  const phone = normalizePhone(phoneRaw);
  if (phone) {
    const last4 = phone.slice(-4);
    return last4 ? `Patient inconnu · ${last4}` : "Patient inconnu";
  }
  const ref = shortCallRef(call);
  if (masked) {
    return ref ? `Numéro masqué · ${ref}` : "Numéro masqué";
  }
  return ref ? `Patient inconnu · ${ref}` : "Patient inconnu";
}

function normalizePatient(call) {
  const patient = call?.patient || {};
  const fullNameFromParts = [String(patient?.first_name || "").trim(), String(patient?.last_name || "").trim()]
    .filter(Boolean)
    .join(" ")
    .trim();
  const displayName = String(
    patient?.display_name ||
      patient?.validated_name ||
      patient?.raw_name ||
      patient?.name ||
      call?.patient_name ||
      fullNameFromParts ||
      "",
  ).trim();
  const phoneRaw = formatPhone(patient?.phone || call?.customer_number || "");
  const phone = normalizePhone(phoneRaw);
  const masked = /masqu|non identifi|anonymous|unknown/i.test(String(phoneRaw || ""));
  const known = patientDashboardFileHasValidatedIdentity(patient);
  const initials = known
    ? displayName
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0])
        .join("")
        .toUpperCase()
    : "";
  return {
    id: patient?.id ? String(patient.id) : undefined,
    name: known ? displayName : unknownDisplayName(call, masked, phoneRaw),
    phone: phoneRaw || null,
    initials: initials || null,
    known,
    masked,
  };
}

function normalizeCallItem(raw) {
  const createdAt = String(raw?.last_event_at || raw?.started_at || "");
  const patient = normalizePatient(raw);
  const type = inferType(raw);
  const status = inferStatus(raw);
  return {
    id: String(raw?.call_id || raw?.id || ""),
    callId: String(raw?.call_id || raw?.id || ""),
    patient,
    phone: patient.phone,
    type,
    status,
    summary: String(raw?.summary || raw?.reason_label || "Aucun résumé disponible."),
    claraResume: String(raw?.clara_summary || raw?.ai_summary || raw?.summary || ""),
    date: formatDateLabel(createdAt),
    time: formatTime(createdAt),
    duration: formatDuration(raw),
    recordingUrl: raw?.recording_url || raw?.recording_url_signed || null,
    followupState: String(raw?.followup_state || ""),
    followupNotes: String(raw?.followup_notes || raw?.notes || ""),
    createdAt,
    raw,
  };
}

function buildQuery(filters = {}) {
  const qs = new URLSearchParams();
  const requestedLimit = Number(filters.limit || 50);
  const safeLimit = Number.isFinite(requestedLimit)
    ? Math.max(1, Math.min(50, Math.trunc(requestedLimit)))
    : 50;
  qs.set("limit", String(safeLimit));
  qs.set("days", String(filters.days || 30));
  const compact = filters.compact === true ? "1" : "0";
  qs.set("compact", compact);
  const query = qs.toString();
  return query ? `?${query}` : "";
}

export async function getCalls(filters = {}) {
  const payload = await api.tenantGetCalls(buildQuery(filters));
  const source = Array.isArray(payload?.calls) ? payload.calls : Array.isArray(payload?.items) ? payload.items : [];
  return source.map(normalizeCallItem).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export async function getCallById(id) {
  const detail = await api.tenantGetCallDetail(id);
  return normalizeCallItem(detail || {});
}

export async function markCallAsHandled(id) {
  await api.tenantUpdateCallFollowup(id, { followup_state: "processed" });
}

export async function createPatientFromCall(callId, payload = {}) {
  return api.tenantUpdateCallPatient(callId, payload);
}

export async function addCallNote(callId, note) {
  const detail = await api.tenantGetCallDetail(callId);
  const text = String(note || "").trim();
  if (!text) throw new Error("La note est vide.");
  const phone = normalizePhone(detail?.patient?.phone || detail?.customer_number || "");
  const validated = String(detail?.patient?.validated_name || "").trim();
  const knownPatient = validated.length >= 2;
  if (knownPatient && phone) {
    return api.tenantCreatePatientNote(phone, { text, author: "Cabinet" });
  }
  const previousNotes = String(detail?.followup_notes || "").trim();
  const merged = previousNotes ? `${previousNotes}\n${text}` : text;
  return api.tenantUpdateCallFollowup(callId, {
    followup_state: detail?.followup_state || "new",
    notes: merged,
  });
}

export async function getRecordingUrl(callId) {
  const detail = await api.tenantGetCallDetail(callId);
  return detail?.recording_url || detail?.recording_url_signed || null;
}
