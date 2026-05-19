/**
 * API admin : credentials: "include" (cookie session) ou Authorization: Bearer (token API).
 * Base URL = VITE_UWI_API_BASE_URL (même que api.js).
 */
import { getAdminToken } from "./api.js";

async function adminFetch(path, options = {}) {
  const base = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");
  if (!base) {
    const err = new Error("VITE_UWI_API_BASE_URL non configuré. Définissez l’URL du backend (ex. Railway).");
    err.status = 0;
    throw err;
  }
  const token = (getAdminToken() || "").trim();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(base + path, {
    ...options,
    credentials: "include",
    headers,
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

/** Chemins relatifs `/api/admin/…` sans base (`VITE_UWI_API_BASE_URL`) ni réseau. Utiles aux tests smoke. */
export function buildTenantPatientRequestsPath(tenantId, opts = {}) {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.limit != null) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return `/api/admin/tenants/${encodeURIComponent(tenantId)}/patient-requests${qs ? `?${qs}` : ""}`;
}

export function buildTenantsActivityGridPath(windowDays = 30) {
  return `/api/admin/tenants/activity-grid?window_days=${encodeURIComponent(windowDays)}`;
}

export const adminApi = {
  /** Diagnostic sans auth : config backend (email_set, password_hash_set, admin_token_set). */
  authStatus: () => adminFetch("/api/admin/auth/status", { method: "GET" }),
  me: () => adminFetch("/api/admin/auth/me", { method: "GET" }),
  login: (payload) =>
    adminFetch("/api/admin/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () => adminFetch("/api/admin/auth/logout", { method: "POST" }),

  listTenants: (params = "") => adminFetch(`/api/admin/tenants${params}`, { method: "GET" }),
  /** Grille liste cabinets : calls, RDV, web_handoffs, demandes ouvertes, hints configuration. */
  tenantsActivityGrid: (windowDays = 30) =>
    adminFetch(buildTenantsActivityGridPath(windowDays), { method: "GET" }),
  tenantsSummary: (periodDays = 30) =>
    adminFetch(`/api/admin/tenants/summary?period=${encodeURIComponent(periodDays)}`, { method: "GET" }),
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
    adminFetch("/api/admin/create-tenant", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  /** Création complète : DB + Vapi + Stripe + Twilio + email */
  createTenantFull: (payload) =>
    adminFetch("/api/admin/tenants/create", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getTwilioNumbers: () => adminFetch("/api/admin/twilio/numbers", { method: "GET" }),
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
  deleteTenant: (id, body) =>
    adminFetch(`/api/admin/tenants/${id}`, {
      method: "DELETE",
      body: JSON.stringify(body || {}),
    }),

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
  getBillingSummary: (period = "month") =>
    adminFetch(`/api/admin/billing/summary?period=${encodeURIComponent(period)}`, { method: "GET" }),
  getBillingActionItems: (period = "month") =>
    adminFetch(`/api/admin/billing/action-items?period=${encodeURIComponent(period)}`, { method: "GET" }),
  listBillingTenants: ({ period = "month", filter = "all", sort = "margin_low", search = "", page = 1, limit = 25 } = {}) => {
    const params = new URLSearchParams();
    params.set("period", period);
    if (filter && filter !== "all") params.set("filter", filter);
    if (sort) params.set("sort", sort);
    if (search) params.set("search", search);
    params.set("page", String(page));
    params.set("limit", String(limit));
    return adminFetch(`/api/admin/billing/tenants?${params.toString()}`, { method: "GET" });
  },
  getBillingTenantOverview: (id, period = "month") =>
    adminFetch(`/api/admin/billing/tenants/${id}/overview?period=${encodeURIComponent(period)}`, { method: "GET" }),
  getBillingTenantUsage: (id, period = "month") =>
    adminFetch(`/api/admin/billing/tenants/${id}/usage?period=${encodeURIComponent(period)}`, { method: "GET" }),
  getBillingTenantStripe: (id) =>
    adminFetch(`/api/admin/billing/tenants/${id}/stripe`, { method: "GET" }),
  getBillingTenantInvoices: (id, limit = 10) =>
    adminFetch(`/api/admin/billing/tenants/${id}/invoices?limit=${encodeURIComponent(limit)}`, { method: "GET" }),
  syncStripeBilling: (period = "month") =>
    adminFetch(`/api/admin/billing/sync-stripe?period=${encodeURIComponent(period)}`, { method: "POST" }),
  syncStripeBillingTenant: (id) =>
    adminFetch(`/api/admin/billing/tenants/${id}/sync-stripe`, { method: "POST" }),
  pushUsageBilling: (targetDate) =>
    adminFetch(`/api/admin/billing/push-usage${targetDate ? `?target_date=${encodeURIComponent(targetDate)}` : ""}`, { method: "POST" }),
  pushUsageBillingTenant: (id, targetDate) =>
    adminFetch(`/api/admin/billing/tenants/${id}/push-usage${targetDate ? `?target_date=${encodeURIComponent(targetDate)}` : ""}`, { method: "POST" }),
  patchBillingTenantPlan: (id, planKey) =>
    adminFetch(`/api/admin/billing/tenants/${id}/plan`, {
      method: "PATCH",
      body: JSON.stringify({ plan_key: planKey }),
    }),
  suspendBillingTenant: (id, mode = "hard") =>
    adminFetch(`/api/admin/billing/tenants/${id}/suspend`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
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
  sendPaymentLink: (id) =>
    adminFetch(`/api/admin/tenants/${id}/send-payment-link`, {
      method: "POST",
    }),
  sendTenantOnboardingLink: (id, body) =>
    adminFetch(`/api/admin/tenants/${id}/send-onboarding-link`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  getTenantFaq: (id) => adminFetch(`/api/admin/tenants/${id}/faq`, { method: "GET" }),
  updateTenantFaq: (id, faq) =>
    adminFetch(`/api/admin/tenants/${id}/faq`, {
      method: "PUT",
      body: JSON.stringify(faq || []),
    }),
  resetTenantFaq: (id) =>
    adminFetch(`/api/admin/tenants/${id}/faq/reset`, {
      method: "POST",
    }),
  changeTenantPlan: (id, planKey) =>
    adminFetch(`/api/admin/tenants/${id}/billing/change-plan`, {
      method: "POST",
      body: JSON.stringify({ plan_key: planKey }),
    }),
  cancelTenantSubscription: (id) =>
    adminFetch(`/api/admin/tenants/${id}/billing/cancel`, { method: "POST" }),
  resumeTenantSubscription: (id) =>
    adminFetch(`/api/admin/tenants/${id}/billing/resume`, { method: "POST" }),
  getStripePortalLink: (id) =>
    adminFetch(`/api/admin/tenants/${id}/billing/portal-link`, { method: "POST" }),
  getTenantInvoices: (id) =>
    adminFetch(`/api/admin/tenants/${id}/billing/invoices`, { method: "GET" }),
  getTenantUsage: (id, month) =>
    adminFetch(`/api/admin/tenants/${id}/usage?month=${encodeURIComponent(month)}`, { method: "GET" }),
  getKpisWeekly: (tenantId, start, end) =>
    adminFetch(`/api/admin/kpis/weekly?tenant_id=${tenantId}&start=${start}&end=${end}`, { method: "GET" }),
  getRgpd: (tenantId, start, end) =>
    adminFetch(`/api/admin/rgpd?tenant_id=${tenantId}&start=${start}&end=${end}`, { method: "GET" }),

  globalStats: (windowDays = 30) =>
    adminFetch(`/api/admin/stats/global?window_days=${windowDays}`, { method: "GET" }),
  /** Payload unique pour la page Dashboard admin (1 round-trip au lieu de 5). */
  dashboardPayload: (windowDays = 30) =>
    adminFetch(`/api/admin/stats/dashboard-payload?window_days=${windowDays}`, { method: "GET" }),
  statsTimeseries: (metric, days) =>
    adminFetch(`/api/admin/stats/timeseries?metric=${metric}&days=${days}`, { method: "GET" }),
  statsTopTenants: (metric, windowDays, limit = 10) =>
    adminFetch(`/api/admin/stats/top-tenants?metric=${metric}&window_days=${windowDays}&limit=${limit}`, { method: "GET" }),
  billingSnapshot: () =>
    adminFetch("/api/admin/stats/billing-snapshot", { method: "GET" }),

  operationsSnapshot: (windowDays = 7) =>
    adminFetch(`/api/admin/stats/operations-snapshot?window_days=${windowDays}`, { method: "GET" }),

  getDashboardSummary: (period = "30d") =>
    adminFetch(`/api/admin/dashboard/summary?period=${encodeURIComponent(period)}`, { method: "GET" }),
  getDashboardActionItems: ({ period = "30d", severity = "all" } = {}) => {
    const params = new URLSearchParams();
    params.set("period", period);
    if (severity && severity !== "all") params.set("severity", severity);
    return adminFetch(`/api/admin/dashboard/action-items?${params.toString()}`, { method: "GET" });
  },
  getDashboardTenantWatchlist: (period = "30d") =>
    adminFetch(`/api/admin/dashboard/tenant-watchlist?period=${encodeURIComponent(period)}`, { method: "GET" }),
  getDashboardNewLeads: (period = "7d") =>
    adminFetch(`/api/admin/dashboard/new-leads?period=${encodeURIComponent(period)}`, { method: "GET" }),

  cabinetProfileAudit: ({ includeInactive = false, onlyMismatch = true, limit = 10, offset = 0 } = {}) => {
    const params = new URLSearchParams();
    params.set("include_inactive", includeInactive ? "true" : "false");
    params.set("only_mismatch", onlyMismatch ? "true" : "false");
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return adminFetch(`/api/admin/cabinet-profile-audit?${params.toString()}`, { method: "GET" });
  },

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

  // Leads pré-onboarding
  leadsCountNew: () => adminFetch("/api/admin/leads/count-new", { method: "GET" }),
  leadsList: (opts = {}) => {
    const params = new URLSearchParams();
    if (opts.status) params.set("status", opts.status);
    if (opts.enterprise === true || opts.enterprise === 1) params.set("enterprise", "1");
    if (opts.search) params.set("search", opts.search);
    if (opts.source) params.set("source", opts.source);
    if (opts.priority) params.set("priority", opts.priority);
    if (opts.segment) params.set("segment", opts.segment);
    if (opts.sort) params.set("sort", opts.sort);
    if (opts.follow_up) params.set("follow_up", opts.follow_up);
    if (opts.page != null) params.set("page", String(opts.page));
    if (opts.limit != null) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return adminFetch(`/api/admin/leads${qs ? `?${qs}` : ""}`, { method: "GET" });
  },
  leadsSummary: (period = "30d") =>
    adminFetch(`/api/admin/leads/summary?period=${encodeURIComponent(String(period).replace(/d$/i, ""))}`, { method: "GET" }),
  leadsStats: (period = "30d") =>
    adminFetch(`/api/admin/leads/stats?period=${encodeURIComponent(String(period).replace(/d$/i, ""))}`, { method: "GET" }),
  leadGet: (leadId) => adminFetch(`/api/admin/leads/${leadId}`, { method: "GET" }),
  leadDelete: (leadId) =>
    adminFetch(`/api/admin/leads/${encodeURIComponent(leadId)}`, { method: "DELETE" }),
  leadCreate: (body) =>
    adminFetch("/api/admin/leads", { method: "POST", body: JSON.stringify(body || {}) }),
  leadPatch: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}`, { method: "PATCH", body: JSON.stringify(body) }),
  leadSetStatus: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}/status`, { method: "PATCH", body: JSON.stringify(body || {}) }),
  leadFollowUp: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}/follow-up`, { method: "POST", body: JSON.stringify(body || {}) }),
  leadMarkLost: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}/mark-lost`, { method: "POST", body: JSON.stringify(body || {}) }),
  leadConvert: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}/convert`, { method: "POST", body: JSON.stringify(body || {}) }),
  sendLeadOnboardingLink: (leadId, body) =>
    adminFetch(`/api/admin/leads/${leadId}/send-onboarding-link`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  sendOnboardingLink: (body) =>
    adminFetch("/api/admin/send-onboarding-link", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  patientRequests: (opts = {}) => {
    const params = new URLSearchParams();
    if (opts.tenantId != null) params.set("tenant_id", String(opts.tenantId));
    if (opts.status) params.set("status", opts.status);
    if (opts.limit != null) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return adminFetch(`/api/admin/patient-requests${qs ? `?${qs}` : ""}`, { method: "GET" });
  },
  /** Même réponse que patientRequests mais tenant dans le chemin REST. */
  tenantPatientRequests: (tenantId, opts = {}) =>
    adminFetch(buildTenantPatientRequestsPath(tenantId, opts), { method: "GET" }),
  patientRequestDetail: (requestId, opts = {}) => {
    const params = new URLSearchParams();
    if (opts.tenantId != null) params.set("tenant_id", String(opts.tenantId));
    const qs = params.toString();
    return adminFetch(`/api/admin/patient-requests/${encodeURIComponent(requestId)}${qs ? `?${qs}` : ""}`, { method: "GET" });
  },
  patchPatientRequest: (requestId, body, opts = {}) => {
    const params = new URLSearchParams();
    if (opts.tenantId != null) params.set("tenant_id", String(opts.tenantId));
    const qs = params.toString();
    return adminFetch(`/api/admin/patient-requests/${encodeURIComponent(requestId)}${qs ? `?${qs}` : ""}`, {
      method: "PATCH",
      body: JSON.stringify(body || {}),
    });
  },
};

// ── Exports nommes (consommes par AdminDashboard) ────────────────────────────
export const getDashboardPayload = (windowDays = 30) =>
  adminFetch(`/api/admin/stats/dashboard-payload?window_days=${windowDays}`);
export const getRecentCalls = (days = 1, limit = 5) =>
  adminFetch(`/api/admin/calls?days=${days}&limit=${limit}`);
export const getBillingSnapshot = () => adminFetch("/api/admin/stats/billing-snapshot");
export const getTenants = () => adminFetch("/api/admin/tenants");
export const getCallDetail = (tenantId, callId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/calls/${encodeURIComponent(callId)}`);
export const loginAdmin = (email, password) =>
  adminFetch("/api/admin/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
export const getMe = () => adminFetch("/api/admin/auth/me");

// ── Billing overview (agrégé, 1 endpoint) ──────────────────────────────────────
export const getBillingOverview = (month) => {
  const m = month || new Date().toISOString().slice(0, 7);
  return adminFetch(`/api/admin/billing/overview?month=${encodeURIComponent(m)}`);
};

// ── Plans ─────────────────────────────────────────────────────────────────────
export const getBillingPlans = () => adminFetch("/api/admin/billing/plans");

// ── Actions Stripe ───────────────────────────────────────────────────────────
export const changeTenantPlan = (tenantId, planKey) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing/change-plan`, {
    method: "POST",
    body: JSON.stringify({ plan_key: planKey }),
  });
export const cancelTenantSubscription = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing/cancel`, { method: "POST" });
export const resumeTenantSubscription = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing/resume`, { method: "POST" });
export const getStripePortalLink = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing/portal-link`, { method: "POST" });
export const getTenantInvoices = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing/invoices`);

export const getAdminDashboardBundle = ({ period = "30d", severity = "all" } = {}) => {
  const params = new URLSearchParams();
  params.set("period", period);
  if (severity && severity !== "all") params.set("severity", severity);
  return adminFetch(`/api/admin/dashboard/bundle?${params.toString()}`);
};
export const getAdminDashboardSummary = (period = "30d") =>
  adminFetch(`/api/admin/dashboard/summary?period=${encodeURIComponent(period)}`);
export const getAdminDashboardActionItems = ({ period = "30d", severity = "all" } = {}) => {
  const params = new URLSearchParams();
  params.set("period", period);
  if (severity && severity !== "all") params.set("severity", severity);
  return adminFetch(`/api/admin/dashboard/action-items?${params.toString()}`);
};
export const getAdminDashboardTenantWatchlist = (period = "30d") =>
  adminFetch(`/api/admin/dashboard/tenant-watchlist?period=${encodeURIComponent(period)}`);
export const getAdminDashboardLeads = (period = "7d") =>
  adminFetch(`/api/admin/dashboard/new-leads?period=${encodeURIComponent(period)}`);

// ── Tenant detail page ────────────────────────────────────────────────────────
export const getTenant = (tenantId) => adminFetch(`/api/admin/tenants/${tenantId}`);
export const getTenantDashboard = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/dashboard`);
export const getTenantActivity = (tenantId, limit = 20) =>
  adminFetch(`/api/admin/tenants/${tenantId}/activity?limit=${limit}`);
export const getTenantCalls = (tenantId, days = 7, limit = 20) =>
  adminFetch(`/api/admin/calls?tenant_id=${tenantId}&days=${days}&limit=${limit}`);
export const getTenantBilling = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/billing`);
export const getTenantUsage = (tenantId, month) => {
  const m = month || new Date().toISOString().slice(0, 7);
  return adminFetch(`/api/admin/tenants/${tenantId}/usage?month=${encodeURIComponent(m)}`);
};
export const getTenantQuota = (tenantId, month) => {
  const m = month || new Date().toISOString().slice(0, 7);
  return adminFetch(`/api/admin/tenants/${tenantId}/quota?month=${encodeURIComponent(m)}`);
};
export const updateTenantFlags = (tenantId, flags) =>
  adminFetch(`/api/admin/tenants/${tenantId}/flags`, {
    method: "PATCH",
    body: JSON.stringify({ flags }),
  });
export const updateTenantParams = (tenantId, params) =>
  adminFetch(`/api/admin/tenants/${tenantId}/params`, {
    method: "PATCH",
    body: JSON.stringify({ params }),
  });
export const updateTenantHoraires = (tenantId, rules) =>
  adminFetch(`/api/admin/tenants/${tenantId}/horaires`, {
    method: "PATCH",
    body: JSON.stringify(rules),
  });
export const getTenantFaq = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/faq`);
export const updateTenantFaq = (tenantId, faq) =>
  adminFetch(`/api/admin/tenants/${tenantId}/faq`, {
    method: "PUT",
    body: JSON.stringify(faq || []),
  });
export const resetTenantFaq = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/faq/reset`, {
    method: "POST",
  });
export const sendPaymentLink = (tenantId) =>
  adminFetch(`/api/admin/tenants/${tenantId}/send-payment-link`, {
    method: "POST",
  });
export const sendTenantOnboardingLink = (tenantId, body = {}) =>
  adminFetch(`/api/admin/tenants/${tenantId}/send-onboarding-link`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const sendLeadOnboardingLink = (leadId, body = {}) =>
  adminFetch(`/api/admin/leads/${leadId}/send-onboarding-link`, {
    method: "POST",
    body: JSON.stringify(body),
  });
