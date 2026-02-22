/**
 * Client API pour uwi-landing → backend FastAPI (Railway).
 * VITE_UWI_API_BASE_URL = https://xxx.railway.app (racine backend)
 * Routes: /api/public/onboarding, /api/admin/*
 */

const BASE_URL = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");

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

async function request(path, { method = "GET", body, admin = false, tenant = false } = {}) {
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

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include", // cookie uwi_session (login email+mdp ou Google)
  });

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
};
