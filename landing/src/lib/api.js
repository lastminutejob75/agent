/**
 * Client API pour uwi-landing → backend FastAPI (Railway).
 * VITE_UWI_API_BASE_URL = https://xxx.railway.app (racine backend)
 * Routes: /api/public/onboarding, /api/admin/*
 */

const BASE_URL = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");

export function getApiBaseUrl() {
  return BASE_URL;
}

export function getAdminToken() {
  return localStorage.getItem("uwi_admin_token") || "";
}

export function setAdminToken(token) {
  localStorage.setItem("uwi_admin_token", (token || "").trim());
}

export function getTenantToken() {
  return localStorage.getItem("uwi_tenant_token") || "";
}

export function setTenantToken(token) {
  localStorage.setItem("uwi_tenant_token", (token || "").trim());
}

export function clearTenantToken() {
  localStorage.removeItem("uwi_tenant_token");
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

const MSG_BACKEND_UNREACHABLE =
  "Impossible de joindre le serveur. Vérifiez VITE_UWI_API_BASE_URL, CORS et que le backend est démarré.";

async function request(path, { method = "GET", body, admin = false, tenant = false, leadToken = "" } = {}) {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = { "Content-Type": "application/json" };
  if (admin) {
    const tok = getAdminToken();
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
  }
  if (tenant) {
    const tok = getTenantToken();
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
  }
  if (leadToken) {
    headers["X-Lead-Token"] = String(leadToken);
  }

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: "include", // cookie uwi_session (login email+mdp ou Google)
    });
  } catch (e) {
    if (e?.message === "Failed to fetch" || (e?.name === "TypeError" && /fetch|network/i.test(e?.message || ""))) {
      throw new Error(MSG_BACKEND_UNREACHABLE);
    }
    throw e;
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const msg = (data && (data.detail || data.error || data.message)) || `HTTP ${res.status}`;
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
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
  authLogin: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password } }),
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
  tenantKpis: (days = 7) => request(`/api/tenant/kpis?days=${days}`, { tenant: true }),
  tenantTechnicalStatus: () => request("/api/tenant/technical-status", { tenant: true }),
  tenantRgpd: () => request("/api/tenant/rgpd", { tenant: true }),
  tenantPatchParams: (params) =>
    request("/api/tenant/params", { method: "PATCH", body: params, tenant: true }),
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
  tenantGetPatients: (params = "") =>
    request(`/api/tenant/patients${params}`, { tenant: true }),
  tenantRegisterPatient: (body) =>
    request("/api/tenant/patients", { method: "POST", body, tenant: true }),
  tenantGetPatient: (phone) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}`, { tenant: true }),
  tenantUpdatePatient: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}`, { method: "PATCH", body, tenant: true }),
  tenantGetPatientNotes: (phone, params = "") =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes${params}`, { tenant: true }),
  tenantCreatePatientNote: (phone, body) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes`, { method: "POST", body, tenant: true }),
  tenantDeletePatientNote: (phone, noteId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/notes/${encodeURIComponent(noteId)}`, { method: "DELETE", tenant: true }),
  tenantUploadPatientDocument: async (phone, file) => {
    const formData = new FormData();
    formData.append("file", file);
    const base = (typeof import.meta !== "undefined" && import.meta.env?.VITE_UWI_API_BASE_URL) || "";
    const url = `${base}/api/tenant/patients/${encodeURIComponent(phone)}/documents`;
    const res = await fetch(url, { method: "POST", body: formData, credentials: "include" });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
    return res.json();
  },
  tenantDownloadPatientDocument: (phone, docId) =>
    `${(typeof import.meta !== "undefined" && import.meta.env?.VITE_UWI_API_BASE_URL) || ""}/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}/download`,
  tenantDeletePatientDocument: (phone, docId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}`, { method: "DELETE", tenant: true }),
  tenantSendPatientDocument: (phone, docId) =>
    request(`/api/tenant/patients/${encodeURIComponent(phone)}/documents/${docId}/send`, { method: "POST", tenant: true }),
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
  tenantGetAgenda: (params = "") => request(`/api/tenant/agenda${params}`, { tenant: true }),
  tenantGetAgendaBulk: (dates) =>
    request(`/api/tenant/agenda/bulk?dates=${encodeURIComponent((dates || []).join(","))}`, { tenant: true }),
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
  tenantCreateAgendaBooking: (body) =>
    request("/api/tenant/agenda/bookings", { method: "POST", body, tenant: true }),
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
