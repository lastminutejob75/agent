/**
 * État synthétique pour la fiche cabinet lorsque la liste est en données d'exemple (?demo=1).
 */
import { getDemoCabinetRowByTenantId } from "./pages/AdminTenantsList.jsx";

export function tenantDetailUrlDemoFlag(searchParams) {
  const raw = String(searchParams.get("demo") ?? "").trim().toLowerCase();
  return ["1", "true", "oui", "yes", "exemple", "exemples", "examples", "demo"].includes(raw);
}

/**
 * Retourne l’état chargé depuis une ligne SAMPLE, ou null si ce n’est pas une prévisualisation démo valide.
 * @returns {{ tenant: object; billing: object; dashboard: object; technicalStatus: object } | null}
 */
export function resolveDemoCabinetPreviewState(rawTenantId, searchParams) {
  if (!tenantDetailUrlDemoFlag(searchParams)) return null;
  const row = getDemoCabinetRowByTenantId(rawTenantId);
  if (!row) return null;

  const n = Number(rawTenantId);
  const b = row.__sampleBilling || {};
  const act = row.__sample_activity || {};
  const email = row.contact_email || "";
  const planKey = String(b.plan_key || row.plan_key_params || "starter").trim();
  let billingStatus = "active";
  if (String(b.stripe_status || "").toLowerCase() === "trialing") billingStatus = "trialing";
  else if (["past_due", "unpaid"].includes(String(b.stripe_status || "").toLowerCase())) billingStatus = "past_due";

  const tenant = {
    tenant_id: n,
    name: row.name,
    status: row.status || "active",
    timezone: "Europe/Paris",
    created_at: "2026-01-02T09:15:00.000Z",
    contact_email: email,
    params: {
      contact_email: email,
      plan_key: planKey,
      assistant_name: "Assistante vocale · exemple",
      vapi_assistant_id: "asst_demo_preview",
      primary_practitioner_name: row.primary_practitioner_name,
      profession: row.profession,
      city: row.city,
    },
    flags: {},
    routing: [{ channel: "vocal", key: "+33912345678", is_active: true }],
  };

  const billing = {
    plan_key: planKey,
    stripe_status: b.stripe_status || "active",
    billing_status: billingStatus,
    quota: { used: Number(b.used) || 0, included: Number(b.included) || 0 },
    usage: { minutes: Number(b.used) || 0 },
  };

  const callsN = Number(act.calls) || 0;
  const dashboard = {
    service_status: { status: "online" },
    counters_7d: {
      calls_total: callsN,
      bookings_confirmed: Number(act.rdv) || 0,
      transfers: Math.max(0, Math.round(callsN * 0.07)),
      abandons: Math.max(0, Math.round(callsN * 0.04)),
    },
    last_call: null,
    last_booking: null,
    transfer_reasons: { top_transferred: [] },
  };

  const technicalStatus = {
    did: "+33 9 12 34 56 78",
    calendar_status: row.__demo_cockpit_alert ? "disconnected" : "connected",
    routing_status: "active",
    service_agent: "online",
    last_event_ago: "Quelques minutes",
    call_lock_timeout_rate_pct: null,
    call_lock_timeout_alert: false,
  };

  return { tenant, billing, dashboard, technicalStatus };
}
