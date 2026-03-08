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
  return err && (err.status === 401 || err.message?.includes("401") || err.message?.includes("Token"));
}

const MSG_BACKEND_UNREACHABLE =
  "Impossible de joindre le serveur. Vérifiez VITE_UWI_API_BASE_URL, CORS et que le backend est démarré.";

async function request(path, { method = "GET", body, admin = false, tenant = false } = {}) {
  if (!BASE_URL) {
    throw new Error("Backend non configuré : définir VITE_UWI_API_BASE_URL (ex. URL de l'API).");
  }
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
  preOnboardingCallbackBooking: (leadId, payload) =>
    request(`/api/pre-onboarding/leads/${encodeURIComponent(leadId)}/callback-booking`, {
      method: "POST",
      body: payload,
    }),

  // admin — leads
  adminLeadsCountNew: () => request("/api/admin/leads/count-new", { admin: true }),
  adminLeadsList: (status) =>
    request(`/api/admin/leads${status ? `?status=${encodeURIComponent(status)}` : ""}`, { admin: true }),
  adminLeadGet: (leadId) => request(`/api/admin/leads/${leadId}`, { admin: true }),
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
    request(`/api/auth/impersonate?token=${encodeURIComponent(token)}`),

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
  tenantGetAgenda: (params = "") => request(`/api/tenant/agenda${params}`, { tenant: true }),
  tenantGetAgendaAvailableSlots: (params = "") =>
    request(`/api/tenant/agenda/available-slots${params}`, { tenant: true }),
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
  tenantGetFaq: () => request("/api/tenant/faq", { tenant: true }),
  tenantUpdateFaq: (faq) =>
    request("/api/tenant/faq", { method: "PUT", body: faq, tenant: true }),
  tenantResetFaq: () =>
    request("/api/tenant/faq/reset", { method: "POST", tenant: true }),
  tenantChangePassword: (newPassword) =>
    request("/api/tenant/auth/change-password", {
      method: "PATCH",
      body: { new_password: newPassword },
      tenant: true,
    }),

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
export const tenantGetAgenda = (params = "") => api.tenantGetAgenda(params);
export const tenantGetAgendaAvailableSlots = (params = "") => api.tenantGetAgendaAvailableSlots(params);
export const tenantCancelAgendaAppointment = (appointmentId, body) => api.tenantCancelAgendaAppointment(appointmentId, body);
export const tenantRescheduleAgendaAppointment = (appointmentId, body) => api.tenantRescheduleAgendaAppointment(appointmentId, body);
export const tenantGetFaq = () => api.tenantGetFaq();
export const tenantUpdateFaq = (faq) => api.tenantUpdateFaq(faq);
export const tenantResetFaq = () => api.tenantResetFaq();
export const adminUpdateHoraires = (tenantId, rules) => api.adminUpdateHoraires(tenantId, rules);
