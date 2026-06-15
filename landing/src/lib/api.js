/**
 * Client API pour uwi-landing → backend FastAPI (Railway).
 * VITE_UWI_API_BASE_URL = https://xxx.railway.app (racine backend)
 * Routes: /api/public/onboarding, /api/admin/*
 */

import { getApiUrl } from "./authConfig.js";

const BASE_URL = getApiUrl();
const TENANT_TOKEN_KEY = "uwi_tenant_token";
const PROD_API_FALLBACK_BASES = [
  "https://agent-production-c246.up.railway.app",
  "https://api.uwiapp.com",
];

export function getApiBaseUrl() {
  return BASE_URL;
}

/*
 * Sécurité : la session est portée UNIQUEMENT par un cookie HttpOnly
 * (`uwi_session` / `uwi_admin_session`), inaccessible à JavaScript.
 * Les anciens tokens stockés en localStorage sont une surface XSS et
 * ont été supprimés. On garde les helpers (no-op) pour rétrocompat.
 */
function _purgeLegacyAuthLocalStorage() {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.removeItem("uwi_admin_token");
    window.localStorage.removeItem("uwi_tenant_token");
  } catch {
    /* localStorage indisponible (mode privé, quota) → ignore */
  }
}
_purgeLegacyAuthLocalStorage();

function _readTenantTokenFromSessionStorage() {
  if (typeof window === "undefined" || !window.sessionStorage) return "";
  try {
    return String(window.sessionStorage.getItem(TENANT_TOKEN_KEY) || "");
  } catch {
    return "";
  }
}

function _writeTenantTokenToSessionStorage(token) {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    const value = String(token || "").trim();
    if (!value) {
      window.sessionStorage.removeItem(TENANT_TOKEN_KEY);
      return;
    }
    window.sessionStorage.setItem(TENANT_TOKEN_KEY, value);
  } catch {
    /* sessionStorage indisponible (mode privé, quota) → ignore */
  }
}

export function getAdminToken() {
  return "";
}

export function setAdminToken(_token) {
  _purgeLegacyAuthLocalStorage();
}

export function getTenantToken() {
  return _readTenantTokenFromSessionStorage();
}

export function setTenantToken(token) {
  _purgeLegacyAuthLocalStorage();
  _writeTenantTokenToSessionStorage(token);
}

export function clearTenantToken() {
  _purgeLegacyAuthLocalStorage();
  _writeTenantTokenToSessionStorage("");
}

export function isTenantUnauthorized(err) {
  if (!err) return false;
  const msg = String(err.message || "").toLowerCase();
  return (
    err.status === 401 ||
    err.status === 403 ||
    msg.includes("401") ||
    msg.includes("403") ||
    msg.includes("unauthorized") ||
    msg.includes("not authenticated") ||
    msg.includes("token")
  );
}

const MSG_BACKEND_UNREACHABLE = import.meta.env.DEV
  ? "Impossible de joindre le serveur. Vérifiez VITE_UWI_API_BASE_URL, CORS et que le backend est démarré."
  : "Impossible de joindre le serveur pour le moment. Vérifiez votre connexion puis réessayez.";
const DEFAULT_REQUEST_TIMEOUT_MS = 15000;

function tenantAuthHeaders(extra = {}) {
  const headers = { ...extra };
  const tenantToken = getTenantToken();
  if (tenantToken && !headers.Authorization) {
    headers.Authorization = `Bearer ${tenantToken}`;
  }
  return headers;
}

function parseApiError(data, statusText) {
  let msg = (data && (data.detail || data.error || data.message)) || statusText;
  if (typeof msg === "object" && msg !== null) {
    msg = msg.message || JSON.stringify(msg);
  }
  if (Array.isArray(msg)) {
    msg = msg
      .map((item) => (typeof item === "object" && item !== null ? item.msg || JSON.stringify(item) : String(item)))
      .join("; ");
  }
  return typeof msg === "string" ? msg : JSON.stringify(msg);
}

function isLikelyNetworkError(e) {
  // Browser fetch() rejects network/CORS/DNS failures as TypeError, with message variants
  // that differ by engine/language ("Failed to fetch", "Load failed", etc.).
  if (e?.name === "TypeError") return true;
  return (
    e?.message === "Failed to fetch" ||
    (e?.name === "TypeError" && /fetch|network|load failed/i.test(e?.message || ""))
  );
}

function buildCandidateApiBases() {
  const first = String(BASE_URL || "").trim().replace(/\/$/, "");
  const out = [];

  // En prod UWi, on garde un plan B automatique entre domaine custom et Railway.
  let isUwiProdHost = false;
  if (typeof window !== "undefined") {
    const host = String(window.location.hostname || "").toLowerCase();
    if (host.endsWith("uwiapp.com")) {
      isUwiProdHost = true;
      // Priorité au même domaine via rewrite Vercel (/api/* -> Railway).
      if (!out.includes("")) out.push("");
      for (const base of PROD_API_FALLBACK_BASES) {
        const clean = String(base || "").trim().replace(/\/$/, "");
        if (!out.includes(clean)) out.push(clean);
      }
    }
  }

  // Garder l'URL configurée en priorité lorsqu'elle existe.
  if (first) {
    // Toujours prioriser l'URL configurée, même si elle est déjà dans la liste.
    const idx = out.indexOf(first);
    if (idx >= 0) out.splice(idx, 1);
    out.unshift(first);
  } else if (!isUwiProdHost) {
    // En local/dev sans config, on garde les URLs relatives pour le proxy Vite.
    out.unshift("");
  }
  return out;
}

function normalizeTimeoutMs(timeoutMs) {
  // Timeout global par défaut pour éviter les requêtes bloquées sans fin.
  if (timeoutMs == null) return DEFAULT_REQUEST_TIMEOUT_MS;
  const parsed = Number(timeoutMs);
  if (!Number.isFinite(parsed)) return DEFAULT_REQUEST_TIMEOUT_MS;
  return Math.max(0, Math.trunc(parsed));
}

async function request(path, { method = "GET", body, admin: _admin = false, tenant: _tenant = false, leadToken = "", signal, timeoutMs } = {}) {
  const pathPart = path.startsWith("/") ? path : `/${path}`;
  const baseCandidates = buildCandidateApiBases();

  /* Session : cookie HttpOnly via `credentials: include`. Plus de Bearer JWT en JS. */
  const headers = { "Content-Type": "application/json" };
  if (leadToken) {
    headers["X-Lead-Token"] = String(leadToken);
  }
  const tenantToken = getTenantToken();
  if (_tenant && tenantToken && !headers.Authorization) {
    headers.Authorization = `Bearer ${tenantToken}`;
  }

  let timeoutId;
  let timeoutController;
  let fetchSignal = signal;
  const effectiveTimeoutMs = normalizeTimeoutMs(timeoutMs);
  if (effectiveTimeoutMs > 0 && !signal) {
    timeoutController = new AbortController();
    fetchSignal = timeoutController.signal;
    if (typeof window !== "undefined") {
      timeoutId = window.setTimeout(() => timeoutController.abort(), effectiveTimeoutMs);
    }
  }

  try {
    let res;
    let lastNetworkError = null;
    for (const base of baseCandidates) {
      const url = `${base}${pathPart}`;
      try {
        res = await fetch(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
          credentials: "include", // cookie uwi_session (login email+mdp ou Google)
          signal: fetchSignal,
        });
        break;
      } catch (e) {
        if (e?.name === "AbortError") {
          throw new Error("Délai dépassé. Le serveur met trop de temps à répondre.");
        }
        if (isLikelyNetworkError(e)) {
          lastNetworkError = e;
          continue;
        }
        throw e;
      }
    }
    if (!res) {
      if (lastNetworkError) throw new Error(MSG_BACKEND_UNREACHABLE);
      throw new Error(MSG_BACKEND_UNREACHABLE);
    }

    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const err = new Error(parseApiError(data, `HTTP ${res.status}`));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  } finally {
    if (timeoutId && typeof window !== "undefined") window.clearTimeout(timeoutId);
  }
}

export const api = {
  // public
  onboardingCreate: (payload) => request("/api/public/onboarding", { method: "POST", body: payload }),
  preOnboardingCommit: (payload) =>
    request("/api/pre-onboarding/commit", { method: "POST", body: payload }),
  preOnboardingLeadCheck: (leadId) =>
    request(`/api/pre-onboarding/leads/${encodeURIComponent(leadId)}/check`, { method: "GET" }),
  preOnboardingLeadEmail: (leadId) =>
    request(`/api/pre-onboarding/leads/${encodeURIComponent(leadId)}/email`, { method: "GET" }),
  preOnboardingCallbackBooking: (leadId, payload, leadToken = "") => {
    const token = (leadToken || "").trim();
    const qs = token ? `?token=${encodeURIComponent(token)}` : "";
    return request(`/api/pre-onboarding/leads/${encodeURIComponent(leadId)}/callback-booking${qs}`, {
      method: "POST",
      body: payload,
      // Header + query : query évite un échec preflight si CORS pas encore à jour en prod.
      leadToken: token,
    });
  },
  preOnboardingCreateAccount: (leadId, payload) =>
    request(`/api/pre-onboarding/leads/${encodeURIComponent(leadId)}/create-account`, {
      method: "POST",
      body: payload,
    }),

  // admin — leads
  adminLeadsCountNew: () => request("/api/admin/leads/count-new", { admin: true }),
  adminLeadsList: (status) =>
    request(`/api/admin/leads${status ? `?status=${encodeURIComponent(status)}` : ""}`, { admin: true }),
  adminLeadGet: (leadId) => request(`/api/admin/leads/${leadId}`, { admin: true }),
  adminLeadDelete: (leadId) =>
    request(`/api/admin/leads/${encodeURIComponent(leadId)}`, { method: "DELETE", admin: true }),
  adminLeadPatch: (leadId, body) =>
    request(`/api/admin/leads/${leadId}`, { method: "PATCH", body, admin: true }),

  // admin
  adminListTenants: () => request("/api/admin/tenants", { admin: true }),
  adminGetTenant: (tenantId) => request(`/api/admin/tenants/${tenantId}`, { admin: true }),
  adminPatchFlags: (tenantId, flags) =>
    request(`/api/admin/tenants/${tenantId}/flags`, { method: "PATCH", body: { flags }, admin: true }),
  adminPatchParams: (tenantId, params) =>
    request(`/api/admin/tenants/${tenantId}/params`, { method: "PATCH", body: { params }, admin: true }),
  adminUpdateHoraires: (tenantId, rules) =>
    request(`/api/admin/tenants/${tenantId}/horaires`, { method: "PATCH", body: rules, admin: true }),
  adminAddRouting: (payload) => request("/api/admin/routing", { method: "POST", body: payload, admin: true }),
  adminKpisWeekly: (tenantId, start, end) =>
    request(`/api/admin/kpis/weekly?tenant_id=${tenantId}&start=${start}&end=${end}`, { admin: true }),
  adminRgpd: (tenantId, start, end) =>
    request(`/api/admin/rgpd?tenant_id=${tenantId}&start=${start}&end=${end}`, { admin: true }),
  adminDashboard: (tenantId) =>
    request(`/api/admin/tenants/${tenantId}/dashboard`, { admin: true }),
  adminTechnicalStatus: (tenantId) =>
    request(`/api/admin/tenants/${tenantId}/technical-status`, { admin: true }),
  adminAddTenantUser: (tenantId, payload) =>
    request(`/api/admin/tenants/${tenantId}/users`, { method: "POST", body: payload, admin: true }),
  adminCreateTenant: (payload) =>
    request("/api/admin/create-tenant", { method: "POST", body: payload, admin: true }),

  // auth
  authLogin: async (email, password) => {
    const data = await request("/api/auth/login", { method: "POST", body: { email, password } });
    if (data?.token) setTenantToken(data.token);
    return data;
  },
  authForgotPassword: (email) =>
    request("/api/auth/forgot-password", { method: "POST", body: { email } }),
  authResetPassword: (email, token, newPassword) =>
    request("/api/auth/reset-password", {
      method: "POST",
      body: { email, token, new_password: newPassword },
    }),
  tenantImpersonateValidate: (token) =>
    request("/api/auth/impersonate", { method: "POST", body: { token } }),

  // tenant ( protégé JWT )
  tenantMe: () => request("/api/tenant/me", { tenant: true }),
  tenantDashboard: () => request("/api/tenant/dashboard", { tenant: true }),
  tenantDashboardStatsFast: () => request("/api/tenant/dashboard/stats-fast", { tenant: true }),
  tenantKpis: (days = 7) => request(`/api/tenant/kpis?days=${days}`, { tenant: true }),
  tenantBookingsToday: () => request("/api/tenant/bookings/today", { tenant: true }),
  tenantTechnicalStatus: () => request("/api/tenant/technical-status", { tenant: true }),
  tenantRgpd: () => request("/api/tenant/rgpd", { tenant: true }),
  tenantPatchParams: (params) =>
    request("/api/tenant/params", { method: "PATCH", body: params, tenant: true }),
  tenantPatchDashboardTeamNote: (note) =>
    request("/api/tenant/dashboard/team-note", {
      method: "PATCH",
      body: { note: String(note || "") },
      tenant: true,
    }),
  tenantUpdateDashboardTeamNote: (noteId, note) =>
    request(`/api/tenant/dashboard/team-note/${encodeURIComponent(String(noteId || ""))}`, {
      method: "PATCH",
      body: { note: String(note || "") },
      tenant: true,
    }),
  tenantDeleteDashboardTeamNote: (noteId) =>
    request(`/api/tenant/dashboard/team-note/${encodeURIComponent(String(noteId || ""))}`, {
      method: "DELETE",
      tenant: true,
    }),
  tenantGetHoraires: () => request("/api/tenant/horaires", { tenant: true }),
  tenantUpdateHoraires: (rules) =>
    request("/api/tenant/horaires", { method: "PATCH", body: rules, tenant: true }),
  tenantGetCalls: (params = "") =>
    request(`/api/tenant/calls${params}`, { tenant: true }),
  tenantGetCallDetail: (callId) =>
    request(`/api/tenant/calls/${encodeURIComponent(callId)}`, { tenant: true }),
  tenantUpdateCallFollowup: (callId, body) =>
    request(`/api/tenant/calls/${encodeURIComponent(callId)}/followup`, {
      method: "PATCH",
      body,
      tenant: true,
    }),
  tenantUpdateCallPatient: (callId, body) =>
    request(`/api/tenant/calls/${encodeURIComponent(callId)}/patient`, {
      method: "PATCH",
      body,
      tenant: true,
    }),
  tenantGetPatients: (params = "", opts = {}) =>
    request(`/api/tenant/patients${params}`, { tenant: true, ...opts }),
  tenantCheckPatientDuplicate: (params = "", opts = {}) =>
    request(`/api/tenant/patients/duplicate-check${params}`, { tenant: true, ...opts }),
  tenantRegisterPatient: (body) =>
    request("/api/tenant/patients", { method: "POST", body, tenant: true }),
  tenantGetPatient: (phone, opts = {}) => {
    const params = new URLSearchParams();
    if (opts?.lightweight) params.set("lightweight", "1");
    if (opts?.includeDocuments) params.set("include_documents", "1");
    const qs = params.toString();
    return request(
      `/api/tenant/patients/${encodeURIComponent(phone)}${qs ? `?${qs}` : ""}`,
      { tenant: true },
    );
  },
  tenantGetPatientDocuments: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/documents`, { tenant: true }),
  tenantUpdatePatient: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}`, { method: "PATCH", body, tenant: true }),
  tenantGetPatientNotes: (phone, params = "") =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes${params}`, { tenant: true }),
  tenantGetPatientHistory: (phone, params = "") =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/history${params}`, { tenant: true }),
  tenantGetPatientAppointments: (phone, params = "") =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/appointments${params}`, { tenant: true }),
  tenantListPatientConsultations: (phone, params = "") =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/consultations${params}`, { tenant: true }),
  tenantCreatePatientConsultation: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/consultations`, {
      method: "POST",
      body,
      tenant: true,
      timeoutMs: 20000,
    }),
  tenantUpdatePatientConsultation: (phone, consultationId, body) =>
    request(
      `/api/tenant/patients/${encodeURIComponent(phone)}/consultations/${encodeURIComponent(String(consultationId || ""))}`,
      {
        method: "PATCH",
        body,
        tenant: true,
        timeoutMs: 20000,
      },
    ),
  tenantDeletePatientConsultation: (phone, consultationId) =>
    request(
      `/api/tenant/patients/${encodeURIComponent(phone)}/consultations/${encodeURIComponent(String(consultationId || ""))}`,
      {
        method: "DELETE",
        tenant: true,
        timeoutMs: 15000,
      },
    ),
  tenantDownloadPatientConsultationPdf: (phone, consultationId) =>
    `${BASE_URL}/api/tenant/patients/${encodeURIComponent(phone)}/consultations/${encodeURIComponent(String(consultationId || ""))}/pdf`,
  tenantFetchPatientConsultationPdf: async (phone, consultationId) => {
    const url = `${BASE_URL}/api/tenant/patients/${encodeURIComponent(phone)}/consultations/${encodeURIComponent(String(consultationId || ""))}/pdf`;
    let res;
    try {
      res = await fetch(url, { credentials: "include", headers: tenantAuthHeaders() });
    } catch (e) {
      if (e?.message === "Failed to fetch" || (e?.name === "TypeError" && /fetch|network/i.test(e?.message || ""))) {
        throw new Error(MSG_BACKEND_UNREACHABLE);
      }
      throw e;
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(parseApiError(e, res.statusText));
    }
    return res.blob();
  },
  tenantGetPatientContextPack: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/context-pack`, { tenant: true }),
  tenantGetPatientConsultationPrefill: (phone) =>
    request("/api/tenant/consultations/prefill", {
      method: "POST",
      body: { phone: String(phone || "") },
      tenant: true,
    }),
  tenantGenerateConsultationSummary: (body) =>
    request("/api/tenant/consultations/summary", {
      method: "POST",
      body,
      tenant: true,
    }),
  tenantTranscribeConsultation: async (audioBlob, phone = "") => {
    const formData = new FormData();
    formData.append("audio", audioBlob, "consultation.webm");
    if (phone) formData.append("phone", String(phone));
    const base = getApiUrl();
    const url = `${base}/api/tenant/consultations/transcribe`;
    const headers = {};
    const tenantToken = getTenantToken();
    if (tenantToken) headers.Authorization = `Bearer ${tenantToken}`;
    const res = await fetch(url, {
      method: "POST",
      body: formData,
      headers,
      credentials: "include",
    });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(e.detail || res.statusText);
    }
    return res.json();
  },
  tenantGetPatientQuestionnaire: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/questionnaire`, { tenant: true }),
  tenantSavePatientQuestionnaire: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/questionnaire`, { method: "PUT", body, tenant: true }),
  tenantSendPatientQuestionnaire: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/questionnaire/send`, { method: "POST", tenant: true }),
  tenantGetPatientSummary: (phone, opts = {}) => {
    const params = new URLSearchParams();
    if (opts?.refresh) params.set("refresh", "true");
    const qs = params.toString();
    return request(
      `/api/tenant/patients/${encodeURIComponent(phone)}/summary${qs ? `?${qs}` : ""}`,
      { tenant: true },
    );
  },
  tenantCreatePatientQuestionnaireV2: (phone, body = {}) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/questionnaires`, {
      method: "POST",
      body,
      tenant: true,
    }),
  tenantListPatientQuestionnairesV2: (phone, opts = {}) => {
    const params = new URLSearchParams();
    if (opts?.templateType) params.set("template_type", opts.templateType);
    const qs = params.toString();
    return request(
      `/api/tenant/patients/${encodeURIComponent(phone)}/questionnaires-v2${qs ? `?${qs}` : ""}`,
      { tenant: true },
    );
  },
  tenantGetQuestionnaireV2Response: (responseId) =>
    request(`/api/tenant/questionnaires-v2/${encodeURIComponent(responseId)}`, { tenant: true }),
  tenantIntegrateQuestionnaireV2: (responseId) =>
    request(`/api/tenant/questionnaires-v2/${encodeURIComponent(responseId)}/integrate`, {
      method: "POST",
      tenant: true,
    }),
  tenantGetCapabilities: () => request("/api/tenant/capabilities", { tenant: true }),
  tenantDownloadQuestionnaireV2Document: (docId) =>
    `${getApiUrl()}/api/tenant/questionnaires-v2/documents/${encodeURIComponent(docId)}/download`,
  tenantDeleteQuestionnaireV2Document: (docId) =>
    request(`/api/tenant/questionnaires-v2/documents/${encodeURIComponent(docId)}`, {
      method: "DELETE",
      tenant: true,
    }),
  publicGetPatientQuestionnaire: (token) =>
    request(`/api/public/patient-questionnaire/${encodeURIComponent(token)}`),
  publicSubmitPatientQuestionnaire: (token, body) =>
    request(`/api/public/patient-questionnaire/${encodeURIComponent(token)}`, { method: "POST", body }),
  publicGetQuestionnaireV2: (token) => request(`/api/q/${encodeURIComponent(token)}`),
  publicSubmitQuestionnaireV2: (token, body) =>
    request(`/api/q/${encodeURIComponent(token)}/submit`, { method: "POST", body }),
  publicUploadQuestionnaireV2File: async (token, file) => {
    const formData = new FormData();
    formData.append("file", file);
    const base = getApiUrl();
    const url = `${base}/api/q/${encodeURIComponent(token)}/upload`;
    const res = await fetch(url, { method: "POST", body: formData, credentials: "include" });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(e.detail || res.statusText);
    }
    return res.json();
  },
  tenantCreatePatientNote: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes`, { method: "POST", body, tenant: true }),
  tenantUpdatePatientNote: (phone, noteId, body) =>
    request(
      `/api/tenant/patients/${encodeURIComponent(phone)}/notes/${encodeURIComponent(noteId)}`,
      { method: "PATCH", body, tenant: true },
    ),
  tenantDeletePatientNote: (phone, noteId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes/${encodeURIComponent(noteId)}`, { method: "DELETE", tenant: true }),
  tenantUploadPatientDocument: async (phone, file) => {
    const formData = new FormData();
    formData.append("file", file);
    const url = `${BASE_URL}/api/tenant/patients/${encodeURIComponent(phone)}/documents`;
    let res;
    try {
      res = await fetch(url, {
        method: "POST",
        body: formData,
        credentials: "include",
        headers: tenantAuthHeaders(),
      });
    } catch (e) {
      if (e?.message === "Failed to fetch" || (e?.name === "TypeError" && /fetch|network/i.test(e?.message || ""))) {
        throw new Error(MSG_BACKEND_UNREACHABLE);
      }
      throw e;
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(parseApiError(e, res.statusText));
    }
    return res.json();
  },
  tenantDownloadPatientDocument: (phone, docId) =>
    `${BASE_URL}/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}/download`,
  tenantFetchPatientDocument: async (phone, docId) => {
    const url = `${BASE_URL}/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}/download`;
    let res;
    try {
      res = await fetch(url, { credentials: "include", headers: tenantAuthHeaders() });
    } catch (e) {
      if (e?.message === "Failed to fetch" || (e?.name === "TypeError" && /fetch|network/i.test(e?.message || ""))) {
        throw new Error(MSG_BACKEND_UNREACHABLE);
      }
      throw e;
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(parseApiError(e, res.statusText));
    }
    return res.blob();
  },
  tenantDeletePatientDocument: (phone, docId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}`, { method: "DELETE", tenant: true }),
  tenantPreparePatientDelete: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/delete-request`, { method: "POST", tenant: true }),
  tenantConfirmPatientDelete: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/delete-confirm`, {
      method: "POST",
      body,
      tenant: true,
    }),
  tenantSendPatientDocument: (phone, docId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}/send`, { method: "POST", tenant: true }),
  tenantSendPatientMessage: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/messages`, { method: "POST", body, tenant: true }),
  tenantSendBulkPatientMessage: (body) =>
    request("/api/tenant/patients/messages/bulk", { method: "POST", body, tenant: true }),
  tenantGetHandoffs: (params = "") =>
    request(`/api/tenant/handoffs${params}`, { tenant: true }),
  tenantGetHandoff: (handoffId) =>
    request(`/api/tenant/handoffs/${encodeURIComponent(handoffId)}`, { tenant: true }),
  tenantUpdateHandoff: (handoffId, body) =>
    request(`/api/tenant/handoffs/${encodeURIComponent(handoffId)}`, {
      method: "PATCH",
      body,
      tenant: true,
    }),
  tenantGetCallbackRequests: (params = "") =>
    request(`/api/tenant/callback-requests${params}`, { tenant: true }),
  tenantUpdateCallbackRequest: (requestId, body) =>
    request(`/api/tenant/callback-requests/${encodeURIComponent(requestId)}`, {
      method: "PATCH",
      body,
      tenant: true,
    }),
  tenantGetAgenda: (params = "", opts = {}) => {
    const raw = String(params || "").trim();
    const qs = raw.startsWith("?") ? raw.slice(1) : raw;
    const search = new URLSearchParams(qs);
    if (opts?.lightweight) search.set("lightweight", "1");
    if (opts?.skipGoogle) search.set("skip_google", "1");
    const query = search.toString();
    const path = query ? `/api/tenant/agenda?${query}` : "/api/tenant/agenda";
    const { lightweight: _lw, skipGoogle: _sg, timeoutMs, ...rest } = opts || {};
    return request(path, { tenant: true, timeoutMs: timeoutMs ?? 10000, ...rest });
  },
  tenantGetAgendaBulk: async (dates, opts = {}) => {
    const all = Array.from(new Set((dates || []).filter(Boolean))).sort();
    if (all.length === 0) return { dates: {} };
    const params = new URLSearchParams();
    params.set("dates", all.join(","));
    if (opts?.lightweight) params.set("lightweight", "1");
    if (opts?.skipGoogle) params.set("skip_google", "1");
    return request(`/api/tenant/agenda/bulk?${params.toString()}`, {
      tenant: true,
      timeoutMs: opts?.timeoutMs ?? 12000,
    });
  },
  tenantGetAgendaAvailableSlots: (params = "") =>
    request(`/api/tenant/agenda/available-slots${params}`, { tenant: true }),
  tenantGetAgendaAvailableDates: (month) =>
    request(`/api/tenant/agenda/available-dates?month=${encodeURIComponent(month)}`, { tenant: true }),
  tenantCancelAgendaAppointment: (appointmentId, body) =>
    request(`/api/tenant/agenda/appointments/${encodeURIComponent(appointmentId)}/cancel`, {
      method: "POST",
      body,
      tenant: true,
    }),
  tenantRescheduleAgendaAppointment: (appointmentId, body) =>
    request(`/api/tenant/agenda/appointments/${encodeURIComponent(appointmentId)}/reschedule`, {
      method: "POST",
      body,
      tenant: true,
    }),
  tenantCreateAgendaBooking: (body) =>
    request("/api/tenant/agenda/bookings", { method: "POST", body, tenant: true, timeoutMs: 15000 }),
  tenantGetFaq: () => request("/api/tenant/faq", { tenant: true }),
  tenantUpdateFaq: (faq) =>
    request("/api/tenant/faq", { method: "PUT", body: faq, tenant: true }),
  tenantResetFaq: () =>
    request("/api/tenant/faq/reset", { method: "POST", tenant: true }),
  tenantVapiStatus: () => request("/api/tenant/vapi/status", { tenant: true }),
  tenantChangePassword: (newPassword) =>
    request("/api/tenant/auth/change-password", {
      method: "PATCH",
      body: { new_password: newPassword },
      tenant: true,
    }),
  tenantGetProfileSummary: () => request("/api/tenant/profile-summary", { tenant: true }),
  tenantGetProfile: () => request("/api/tenant/profile", { tenant: true }),
  tenantPatchProfile: (body) => request("/api/tenant/profile", { method: "PATCH", body, tenant: true }),
  tenantGetOpeningHours: () => request("/api/tenant/opening-hours", { tenant: true }),
  tenantPatchOpeningHours: (body) => request("/api/tenant/opening-hours", { method: "PATCH", body, tenant: true }),
  tenantGetAvailabilitySettings: () => request("/api/tenant/availability-settings", { tenant: true }),
  tenantPatchAvailabilitySettings: (body) =>
    request("/api/tenant/availability-settings", { method: "PATCH", body, tenant: true }),
  tenantGetBookingRules: () => request("/api/tenant/booking-rules", { tenant: true }),
  tenantPatchBookingRules: (body) => request("/api/tenant/booking-rules", { method: "PATCH", body, tenant: true }),
  tenantGetAppointmentReasons: () => request("/api/tenant/appointment-reasons", { tenant: true }),
  tenantCreateAppointmentReason: (body) =>
    request("/api/tenant/appointment-reasons", { method: "POST", body, tenant: true }),
  tenantPatchAppointmentReason: (reasonId, body) =>
    request(`/api/tenant/appointment-reasons/${encodeURIComponent(reasonId)}`, { method: "PATCH", body, tenant: true }),
  tenantDeleteAppointmentReason: (reasonId) =>
    request(`/api/tenant/appointment-reasons/${encodeURIComponent(reasonId)}`, { method: "DELETE", tenant: true }),
  tenantGetAssistantSettings: () => request("/api/tenant/assistant-settings", { tenant: true }),
  tenantPatchAssistantSettings: (body) =>
    request("/api/tenant/assistant-settings", { method: "PATCH", body, tenant: true }),
  tenantAssistantPreview: (message) =>
    request("/api/tenant/assistant-preview", { method: "POST", body: { message }, tenant: true }),
  tenantTestBookingRule: (message) =>
    request("/api/tenant/test-booking-rule", { method: "POST", body: { message }, tenant: true }),
  tenantGetCalendarStatus: () => request("/api/tenant/calendar/status", { tenant: true }),
  tenantGetBillingSummary: () => request("/api/tenant/billing/summary", { tenant: true }),
  tenantGetBillingInvoices: () => request("/api/tenant/billing/invoices", { tenant: true }),
  tenantBillingPortalSession: () =>
    request("/api/tenant/billing/portal-session", { method: "POST", tenant: true }),
  tenantBillingChangePlan: (planKey) =>
    request("/api/tenant/billing/change-plan", { method: "POST", body: { plan_key: planKey }, tenant: true }),

  // Agenda setup
  agendaConfig: () => request("/api/tenant/agenda/config", { tenant: true }),
  agendaVerifyGoogle: (calendarId) =>
    request("/api/tenant/agenda/verify-google", { method: "POST", body: { calendar_id: calendarId }, tenant: true }),
  agendaContactRequest: (software, softwareOther) =>
    request("/api/tenant/agenda/contact-request", {
      method: "POST",
      body: { software, software_other: softwareOther || "" },
      tenant: true,
    }),
  agendaActivateNone: () =>
    request("/api/tenant/agenda/activate-none", { method: "POST", tenant: true }),
};

export const tenantGetHoraires = () => api.tenantGetHoraires();
export const tenantUpdateHoraires = (rules) => api.tenantUpdateHoraires(rules);
export const tenantGetCalls = (params = "") => api.tenantGetCalls(params);
export const tenantGetCallDetail = (callId) => api.tenantGetCallDetail(callId);
export const tenantUpdateCallFollowup = (callId, body) => api.tenantUpdateCallFollowup(callId, body);
export const tenantUpdateCallPatient = (callId, body) => api.tenantUpdateCallPatient(callId, body);
export const tenantGetHandoffs = (params = "") => api.tenantGetHandoffs(params);
export const tenantGetHandoff = (handoffId) => api.tenantGetHandoff(handoffId);
export const tenantUpdateHandoff = (handoffId, body) => api.tenantUpdateHandoff(handoffId, body);
export const tenantGetAgenda = (params = "") => api.tenantGetAgenda(params);
export const tenantGetAgendaAvailableSlots = (params = "") => api.tenantGetAgendaAvailableSlots(params);
export const tenantGetAgendaAvailableDates = (month) => api.tenantGetAgendaAvailableDates(month);
export const tenantCancelAgendaAppointment = (appointmentId, body) => api.tenantCancelAgendaAppointment(appointmentId, body);
export const tenantRescheduleAgendaAppointment = (appointmentId, body) => api.tenantRescheduleAgendaAppointment(appointmentId, body);
export const tenantGetFaq = () => api.tenantGetFaq();
export const tenantUpdateFaq = (faq) => api.tenantUpdateFaq(faq);
export const tenantResetFaq = () => api.tenantResetFaq();
export const adminUpdateHoraires = (tenantId, rules) => api.adminUpdateHoraires(tenantId, rules);
