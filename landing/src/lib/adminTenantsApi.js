/**
 * Couche dédiée Clients / Cabinets (admin).
 * Utilise le même transport que adminApi (cookie session / Bearer).
 */
import { adminApi } from "./adminApi.js";

/**
 * @param {{
 *   includeInactive?: boolean;
 *   search?: string;
 *   status?: string;
 *   statusIn?: string;
 *   page?: number;
 *   limit?: number;
 * }} opts
 */
export function buildTenantsListQuery(opts = {}) {
  const p = new URLSearchParams();
  if (opts.includeInactive !== false) p.set("include_inactive", "true");
  if (opts.search && String(opts.search).trim()) p.set("search", String(opts.search).trim());
  if (opts.status && String(opts.status).trim()) p.set("status", String(opts.status).trim());
  if (opts.statusIn && String(opts.statusIn).trim()) p.set("status_in", String(opts.statusIn).trim());
  if (opts.page != null && opts.limit != null) {
    p.set("page", String(Math.max(1, Number(opts.page))));
    p.set("limit", String(Math.min(500, Math.max(1, Number(opts.limit)))));
  }
  return `?${p.toString()}`;
}

export async function listTenants(opts = {}) {
  const qs = buildTenantsListQuery(opts);
  return adminApi.listTenants(qs);
}

export async function tenantsSummary(periodDays = 30) {
  return adminApi.tenantsSummary(periodDays);
}

export async function createTenantDraft(payload) {
  return adminApi.createTenant(payload);
}

export async function patchTenantParams(tenantId, params) {
  return adminApi.patchTenantParams(tenantId, params);
}

export async function getTenant(id) {
  return adminApi.getTenant(id);
}

/** Demandes patient / handoffs pour un tenant (GET /api/admin/tenants/:id/patient-requests). */
export async function patientRequestsForTenant(tenantId, opts = {}) {
  return adminApi.tenantPatientRequests(Number(tenantId), opts);
}
