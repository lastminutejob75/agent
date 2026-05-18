const PLAN_META = {
  starter: { monthly: 99, included: 400, overage: 0.19, label: "Starter" },
  growth: { monthly: 149, included: 800, overage: 0.17, label: "Growth" },
  pro: { monthly: 199, included: 1200, overage: 0.15, label: "Pro" },
  trial: { monthly: 0, included: 200, overage: 0.0, label: "Trial" },
  free: { monthly: 0, included: 0, overage: 0.0, label: "Free" },
};

export function mapFilterToApi(filterLabel) {
  const map = {
    Tous: "all",
    Actifs: "active",
    Essais: "trialing",
    "Quota élevé": "quota_high",
    Dépassement: "overage",
    "Marge faible": "margin_low",
    "Stripe incomplet": "stripe_incomplete",
    Alertes: "alerts",
  };
  return map[filterLabel] || "all";
}

export function mapSortToApi(sortLabel) {
  const map = {
    margin_low: "margin_low",
    mrr: "mrr_desc",
    vapi: "vapi_cost_desc",
    usage: "usage_desc",
    name: "name_asc",
    invoice: "next_invoice_asc",
  };
  return map[sortLabel] || "margin_low";
}

export function enrichTenant(row) {
  const planKey = String(row.plan_key || "free").toLowerCase();
  const plan = PLAN_META[planKey] || PLAN_META.free;
  const used = Number(row?.voice_minutes_used ?? row?.usage?.minutes ?? row?.quota?.used ?? 0);
  const cost = Number(row?.vapi_cost_estimate ?? row?.usage?.cost_usd ?? 0);
  const included = Number(row?.included_minutes ?? row?.quota?.included ?? plan.included ?? 0);
  const overMinutes = Math.max(0, used - included);
  const overageAmount = overMinutes * Number(plan.overage || 0);
  const expectedRevenue = Number(row?.mrr_eur || row.monthly_price || plan.monthly || 0) + overageAmount;
  const margin = expectedRevenue - cost;
  const marginRate = expectedRevenue > 0 ? Math.round((margin / expectedRevenue) * 100) : 0;
  const usagePercent = included > 0 ? Math.round((used / included) * 100) : 0;
  const alerts = [];
  if (!row?.stripe_customer_id) alerts.push("Stripe customer manquant");
  if (!row?.stripe_subscription_id) alerts.push("Subscription manquante");
  if (usagePercent >= 85) alerts.push(`Quota à ${usagePercent}%`);
  if (overMinutes > 0) alerts.push("Dépassement minutes");
  if (margin < 0) alerts.push("Marge négative estimée");
  return {
    tenantId: row.tenant_id,
    name: row.name || `Tenant #${row.tenant_id}`,
    planKey,
    planLabel: plan.label,
    stripeStatus: row.stripe_status || "none",
    stripeCustomerId: row.stripe_customer_id || "",
    stripeSubscriptionId: row.stripe_subscription_id || "",
    periodEndTs: row.current_period_end || null,
    mrr: Number(row.mrr_eur || row.monthly_price || 0),
    usedMinutes: used,
    includedMinutes: included,
    overMinutes,
    overageAmount,
    vapiCost: cost,
    expectedRevenue,
    margin,
    marginRate,
    usagePercent,
    alerts: Array.isArray(row?.alerts) && row.alerts.length ? row.alerts : alerts,
    row,
  };
}
