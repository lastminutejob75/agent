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

async function request(path, { method = "GET", body, admin = false } = {}) {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = { "Content-Type": "application/json" };
  if (admin) {
    const tok = getAdminToken();
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
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
    throw err;
  }
  return data;
}

export const api = {
  // public
  onboardingCreate: (payload) => request("/api/public/onboarding", { method: "POST", body: payload }),

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
};
