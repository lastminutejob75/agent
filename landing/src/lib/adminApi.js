/**
 * API admin : credentials: "include" (cookie session).
 * Base URL = VITE_UWI_API_BASE_URL (même que api.js).
 */
const baseUrl = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");

async function adminFetch(path, options = {}) {
  const res = await fetch(baseUrl + path, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    let message = "Request failed";
    if (typeof data?.detail === "string" && data.detail) {
      message = data.detail;
    } else if (Array.isArray(data?.detail) && data.detail.length) {
      message = data.detail.map((x) => x?.msg ?? x?.loc?.join(".") ?? JSON.stringify(x)).join(" · ");
    } else if (data?.detail?.msg) {
      message = data.detail.msg;
    } else if (res.status) {
      message = `Erreur ${res.status}${data?.detail ? ` — ${JSON.stringify(data.detail)}` : ""}`.trim();
    }
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const adminApi = {
  me: () => adminFetch("/api/admin/auth/me", { method: "GET" }),
  login: (payload) =>
    adminFetch("/api/admin/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () => adminFetch("/api/admin/auth/logout", { method: "POST" }),

  listTenants: (params = "") => adminFetch(`/api/admin/tenants${params}`, { method: "GET" }),
  getTenant: (id) => adminFetch(`/api/admin/tenants/${id}`, { method: "GET" }),
  /** Token 5 min pour ouvrir /app/impersonate?token=... (voir comme le client). */
  impersonate: (tenantId) =>
    adminFetch(`/api/admin/tenants/${tenantId}/impersonate`, { method: "POST" }),
  /** Mappe sur PATCH /params (tenant_config.params_json). Ne met pas à jour name/timezone (table tenants). */
  updateTenant: (id, payload) => {
    const params = {};
    if (payload.contact_email !== undefined) params.contact_email = payload.contact_email;
    if (payload.billing_email !== undefined) params.billing_email = payload.billing_email;
    if (payload.manager_phone !== undefined) params.responsible_phone = payload.manager_phone;
    if (payload.manager_name !== undefined) params.manager_name = payload.manager_name;
    if (payload.notes !== undefined) params.notes = payload.notes;
    if (Object.keys(params).length === 0) return Promise.resolve();
    return adminFetch(`/api/admin/tenants/${id}/params`, { method: "PATCH", body: JSON.stringify({ params }) });
  },
  /** Mappe sur PATCH /params. DID = routing (addRouting), pas un champ unique. */
  updateTenantTelephony: (id, payload) => {
    const params = {};
    if (payload.transfer_number !== undefined) params.transfer_number = payload.transfer_number;
    if (Object.keys(params).length === 0) return Promise.resolve();
    return adminFetch(`/api/admin/tenants/${id}/params`, { method: "PATCH", body: JSON.stringify({ params }) });
  },
  updateTenantVapi: (id, payload) => {
    const params = {};
    if (payload.vapi_assistant_id !== undefined) params.vapi_assistant_id = payload.vapi_assistant_id;
    if (Object.keys(params).length === 0) return Promise.resolve();
    return adminFetch(`/api/admin/tenants/${id}/params`, { method: "PATCH", body: JSON.stringify({ params }) });
  },
  createTenant: (payload) =>
    adminFetch("/api/admin/tenants", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patchTenantParams: (id, params) =>
    adminFetch(`/api/admin/tenants/${id}/params`, {
      method: "PATCH",
      body: JSON.stringify({ params }),
    }),
  patchTenantFlags: (id, flags) =>
    adminFetch(`/api/admin/tenants/${id}/flags`, {
      method: "PATCH",
      body: JSON.stringify({ flags }),
    }),
  deleteTenant: (id) =>
    adminFetch(`/api/admin/tenants/${id}`, { method: "DELETE" }),

  addRouting: (payload) =>
    adminFetch("/api/admin/routing", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getTenantDashboard: (id) => adminFetch(`/api/admin/tenants/${id}/dashboard`, { method: "GET" }),
  getTenantTechnicalStatus: (id) =>
    adminFetch(`/api/admin/tenants/${id}/technical-status`, { method: "GET" }),
  getTenantBilling: (id) =>
    adminFetch(`/api/admin/tenants/${id}/billing`, { method: "GET" }),
  getBillingPlans: () =>
    adminFetch("/api/admin/billing/plans", { method: "GET" }),
  getTenantQuota: (id, month) =>
    adminFetch(`/api/admin/tenants/${id}/quota?month=${encodeURIComponent(month)}`, { method: "GET" }),
  tenantSuspend: (id, mode = "hard") =>
    adminFetch(`/api/admin/tenants/${id}/suspend`, {
      method: "POST",
      body: JSON.stringify({ mode: mode === "soft" ? "soft" : "hard" }),
    }),
  tenantUnsuspend: (id) =>
    adminFetch(`/api/admin/tenants/${id}/unsuspend`, { method: "POST" }),
  tenantForceActive: (id, days = 7) =>
    adminFetch(`/api/admin/tenants/${id}/force-active`, {
      method: "POST",
      body: JSON.stringify({ days }),
    }),
  createStripeCustomer: (id) =>
    adminFetch(`/api/admin/tenants/${id}/stripe-customer`, { method: "POST" }),
  createStripeCheckout: (id, body) =>
    adminFetch(`/api/admin/tenants/${id}/stripe-checkout`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getTenantUsage: (id, month) =>
    adminFetch(`/api/admin/tenants/${id}/usage?month=${encodeURIComponent(month)}`, { method: "GET" }),
  getKpisWeekly: (tenantId, start, end) =>
    adminFetch(`/api/admin/kpis/weekly?tenant_id=${tenantId}&start=${start}&end=${end}`, { method: "GET" }),
  getRgpd: (tenantId, start, end) =>
    adminFetch(`/api/admin/rgpd?tenant_id=${tenantId}&start=${start}&end=${end}`, { method: "GET" }),

  globalStats: (windowDays = 30) =>
    adminFetch(`/api/admin/stats/global?window_days=${windowDays}`, { method: "GET" }),
  statsTimeseries: (metric, days) =>
    adminFetch(`/api/admin/stats/timeseries?metric=${metric}&days=${days}`, { method: "GET" }),
  statsTopTenants: (metric, windowDays, limit = 10) =>
    adminFetch(`/api/admin/stats/top-tenants?metric=${metric}&window_days=${windowDays}&limit=${limit}`, { method: "GET" }),
  billingSnapshot: () =>
    adminFetch("/api/admin/stats/billing-snapshot", { method: "GET" }),

  operationsSnapshot: (windowDays = 7) =>
    adminFetch(`/api/admin/stats/operations-snapshot?window_days=${windowDays}`, { method: "GET" }),

  qualitySnapshot: (windowDays = 7) =>
    adminFetch(`/api/admin/stats/quality-snapshot?window_days=${windowDays}`, { method: "GET" }),

  tenantStats: (tenantId, windowDays = 7) =>
    adminFetch(`/api/admin/stats/tenants/${tenantId}?window_days=${windowDays}`, { method: "GET" }),
  tenantTimeseries: (tenantId, metric, days) =>
    adminFetch(`/api/admin/stats/tenants/${tenantId}/timeseries?metric=${metric}&days=${days}`, { method: "GET" }),
  tenantActivity: (tenantId, limit = 50) =>
    adminFetch(`/api/admin/tenants/${tenantId}/activity?limit=${limit}`, { method: "GET" }),

  getCalls: (opts = {}) => {
    const params = new URLSearchParams();
    if (opts.tenantId != null) params.set("tenant_id", opts.tenantId);
    params.set("days", opts.days ?? 7);
    params.set("limit", opts.limit ?? 50);
    if (opts.cursor) params.set("cursor", opts.cursor);
    if (opts.result) params.set("result", opts.result);
    return adminFetch(`/api/admin/calls?${params}`, { method: "GET" });
  },

  getCallDetail: (tenantId, callId) =>
    adminFetch(`/api/admin/tenants/${tenantId}/calls/${encodeURIComponent(callId)}`, { method: "GET" }),
};
