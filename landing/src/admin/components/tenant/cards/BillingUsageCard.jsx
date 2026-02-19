import { useState, useEffect } from "react";
import { adminApi } from "../../../../lib/adminApi";
import InlineAlert from "../InlineAlert";

function copy(text) {
  navigator.clipboard?.writeText(String(text)).catch(() => {});
}

export default function BillingUsageCard({ tenantId, tenant, billing, usageMonth, setUsageMonth, onCreateStripeCustomer, onSaved }) {
  const [usageData, setUsageData] = useState(null);
  const [quota, setQuota] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loadingUsage, setLoadingUsage] = useState(false);
  const [loadingQuota, setLoadingQuota] = useState(false);
  const [stripeLoading, setStripeLoading] = useState(false);
  const [planSelect, setPlanSelect] = useState("");
  const [planSaving, setPlanSaving] = useState(false);
  const [planErr, setPlanErr] = useState(null);
  const [customQuotaInput, setCustomQuotaInput] = useState("");
  const [customQuotaSaving, setCustomQuotaSaving] = useState(false);
  const [customQuotaErr, setCustomQuotaErr] = useState(null);

  const month = usageMonth || (() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  })();

  useEffect(() => {
    if (!tenantId || !month) return;
    setLoadingUsage(true);
    adminApi
      .getTenantUsage(tenantId, month)
      .then(setUsageData)
      .catch(() => setUsageData(null))
      .finally(() => setLoadingUsage(false));
  }, [tenantId, month]);

  useEffect(() => {
    adminApi.getBillingPlans().then((r) => setPlans(r?.items ?? [])).catch(() => setPlans([]));
  }, []);

  useEffect(() => {
    if (!tenantId || !month) return;
    setLoadingQuota(true);
    adminApi
      .getTenantQuota(tenantId, month)
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setLoadingQuota(false));
  }, [tenantId, month]);

  useEffect(() => {
    const pk = tenant?.params?.plan_key ?? quota?.plan_key ?? "";
    setPlanSelect(pk);
  }, [tenant?.params?.plan_key, quota?.plan_key]);

  useEffect(() => {
    const v = tenant?.params?.custom_included_minutes_month;
    setCustomQuotaInput(v !== undefined && v !== null ? String(v) : "");
  }, [tenant?.params?.custom_included_minutes_month]);

  async function savePlan() {
    if (!tenantId) return;
    setPlanErr(null);
    setPlanSaving(true);
    try {
      await adminApi.patchTenantParams(tenantId, { plan_key: planSelect });
      await onSaved?.();
      const q = await adminApi.getTenantQuota(tenantId, month);
      setQuota(q);
    } catch (e) {
      setPlanErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setPlanSaving(false);
    }
  }

  async function saveCustomQuota() {
    if (!tenantId) return;
    setCustomQuotaErr(null);
    const raw = customQuotaInput.trim();
    const parsed = raw === "" ? 0 : parseInt(customQuotaInput.trim(), 10);
    if (Number.isNaN(parsed) || parsed < 0) {
      setCustomQuotaErr("Entier ≥ 0 requis.");
      return;
    }
    setCustomQuotaSaving(true);
    try {
      await adminApi.patchTenantParams(tenantId, { custom_included_minutes_month: String(parsed) });
      await onSaved?.();
      const q = await adminApi.getTenantQuota(tenantId, month);
      setQuota(q);
    } catch (e) {
      setCustomQuotaErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setCustomQuotaSaving(false);
    }
  }

  const usagePct = quota?.usage_pct ?? 0;
  const quotaBadge =
    quota?.included_minutes_month === 0
      ? null
      : usagePct > 100
        ? { label: "Dépassement", className: "bg-red-100 text-red-800" }
        : usagePct >= 80
          ? { label: "Alerte", className: "bg-amber-100 text-amber-800" }
          : { label: "OK", className: "bg-green-100 text-green-800" };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="font-semibold text-gray-900 mb-4">Usage & Billing</div>

      {/* Quota (mois UTC) */}
      <div className="mb-4 pb-4 border-b border-gray-100">
        <div className="text-sm font-medium text-gray-700 mb-2">Quota (mois UTC)</div>
        {loadingQuota ? (
          <p className="text-sm text-gray-500">Chargement…</p>
        ) : quota ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-gray-900 font-mono">
                {quota.used_minutes_month ?? 0} / {quota.included_minutes_month ?? 0} min
              </span>
              {quotaBadge && (
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${quotaBadge.className}`}>
                  {quotaBadge.label}
                </span>
              )}
            </div>
            {quota.included_minutes_month > 0 && (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${usagePct > 100 ? "bg-red-500" : usagePct >= 80 ? "bg-amber-500" : "bg-green-500"}`}
                  style={{ width: `${Math.min(usagePct, 100)}%` }}
                />
              </div>
            )}
            {quota.remaining_minutes_month != null && quota.included_minutes_month > 0 && (
              <p className="text-xs text-gray-500">Reste : {quota.remaining_minutes_month} min</p>
            )}
            {quota.quota_source && (
              <p className="text-xs text-gray-500">Source quota : {quota.quota_source}</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-500">—</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="text-sm text-gray-600">Plan</label>
          <select
            value={planSelect}
            onChange={(e) => setPlanSelect(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="">—</option>
            {plans.map((p) => (
              <option key={p.plan_key} value={p.plan_key}>
                {p.plan_key} ({p.included_minutes_month ?? 0} min)
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={planSaving}
            onClick={savePlan}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {planSaving ? "Enregistrement…" : "Enregistrer plan"}
          </button>
        </div>
        {planErr && <InlineAlert kind="error" message={planErr} />}
        {planSelect === "custom" && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className="text-sm text-gray-600">Quota minutes (mois)</label>
            <input
              type="number"
              min={0}
              step={1}
              value={customQuotaInput}
              onChange={(e) => setCustomQuotaInput(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-sm w-24"
              placeholder="0"
            />
            <button
              type="button"
              disabled={customQuotaSaving}
              onClick={saveCustomQuota}
              className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {customQuotaSaving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        )}
        {customQuotaErr && <InlineAlert kind="error" message={customQuotaErr} />}
      </div>

      <div className="grid gap-4">
        <div>
          <div className="text-sm font-medium text-gray-700 mb-2">Usage Vapi (mois)</div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="month"
              value={month}
              onChange={(e) => setUsageMonth?.(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <span className="text-sm text-gray-500">
              {loadingUsage ? "…" : usageData != null ? `${usageData.minutes_total ?? 0} min · ${Number(usageData.cost_usd ?? 0).toFixed(2)} $ · ${usageData.calls_count ?? 0} appels` : "—"}
            </span>
          </div>
        </div>

        <div>
          <div className="text-sm font-medium text-gray-700 mb-2">Stripe</div>
          {billing?.stripe_customer_id ? (
            <div className="text-sm space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Customer:</span>
                <code className="bg-gray-100 px-1 rounded text-xs">{billing.stripe_customer_id}</code>
                <button type="button" onClick={() => copy(billing.stripe_customer_id)} className="text-xs text-indigo-600 hover:underline">Copier</button>
              </div>
              {billing.billing_status && <p><span className="text-gray-500">Statut:</span> {billing.billing_status}</p>}
              {billing.current_period_end && <p><span className="text-gray-500">Fin période:</span> {new Date(billing.current_period_end).toLocaleDateString("fr-FR")}</p>}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm text-gray-500">Aucun customer Stripe.</p>
              {onCreateStripeCustomer && (
                <button
                  type="button"
                  disabled={stripeLoading}
                  onClick={async () => {
                    setStripeLoading(true);
                    try {
                      await onCreateStripeCustomer();
                    } finally {
                      setStripeLoading(false);
                    }
                  }}
                  className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {stripeLoading ? "Création…" : "Créer customer Stripe"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
