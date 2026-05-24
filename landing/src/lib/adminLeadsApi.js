import { adminApi } from "./adminApi.js";

export const LEAD_STATUS_LABELS = {
  all: "Tous",
  new: "Nouveau",
  to_contact: "À contacter",
  contacted: "Contacté",
  interested: "Intéressé",
  demo_scheduled: "Démo prévue",
  trial_offered: "Essai proposé",
  trial_started: "Essai gratuit",
  converted: "Converti",
  lost: "Perdu",
  later: "À relancer plus tard",
};

export function mapLeadStatusToBackend(status) {
  if (!status || status === "all") return undefined;
  if (status === "to_contact") return "new";
  if (status === "demo") return "demo_scheduled";
  if (status === "trial") return "trial_started";
  return status;
}

export async function getLeadsSummary(period = "30d") {
  return adminApi.leadsSummary(period);
}

export async function getLeadsStats(period = "30d") {
  return adminApi.leadsStats(period);
}

export async function listAdminLeads({
  status = "all",
  search = "",
  source,
  priority,
  segment,
  sort = "created_desc",
  page = 1,
  limit = 25,
  followUpToday = false,
} = {}) {
  const backendStatus = mapLeadStatusToBackend(status);
  const res = await adminApi.leadsList({
    status: backendStatus,
    search: search || undefined,
    source: source || undefined,
    priority: priority || undefined,
    segment: segment || undefined,
    sort,
    follow_up: followUpToday ? "today" : undefined,
    page,
    limit,
  });
  return {
    items: res?.items || res?.leads || [],
    total: Number(res?.total || (res?.items || res?.leads || []).length || 0),
    page: Number(res?.page || page || 1),
    limit: Number(res?.limit || limit || 25),
    pipeline: res?.pipeline || {},
  };
}
