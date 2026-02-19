import { CopyButton } from "./copyButton";

export default function TenantCardUsageBilling({
  stats7d,
  stats30d,
  billing,
  usageMonth,
  usageData,
  onMonthChange,
  onRefreshUsage,
  onCreateStripeCustomer,
  stripeLoading,
}) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage & Billing</h2>

      <div className="space-y-4">
        <div>
          <span className="block text-sm font-medium text-gray-500 mb-2">Usage Vapi</span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <div className="text-gray-500 text-xs">Minutes (7j)</div>
              <div className="font-semibold text-gray-900">{stats7d?.minutes_total ?? "—"}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Coût USD (7j)</div>
              <div className="font-semibold text-gray-900">{stats7d?.cost_usd != null ? Number(stats7d.cost_usd).toFixed(2) : "—"}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Minutes (30j)</div>
              <div className="font-semibold text-gray-900">{stats30d?.minutes_total ?? "—"}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">Coût USD (30j)</div>
              <div className="font-semibold text-gray-900">{stats30d?.cost_usd != null ? Number(stats30d.cost_usd).toFixed(2) : "—"}</div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className="text-sm text-gray-600">Mois UTC</label>
            <input
              type="month"
              value={usageMonth}
              onChange={(e) => onMonthChange?.(e.target.value)}
              onBlur={() => onRefreshUsage?.()}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={() => onRefreshUsage?.()} className="text-sm text-indigo-600 hover:underline">
              Actualiser
            </button>
          </div>
          {usageData && (
            <p className="text-sm text-gray-600 mt-1">
              {usageData.minutes_total ?? 0} min · {Number(usageData.cost_usd ?? 0).toFixed(2)} $ · {usageData.calls_count ?? 0} appels
            </p>
          )}
        </div>

        <div className="pt-3 border-t border-gray-100">
          <span className="block text-sm font-medium text-gray-500 mb-2">Stripe</span>
          {billing?.stripe_customer_id ? (
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-1">
                <span className="text-gray-500">Customer:</span>
                <code className="bg-gray-100 px-1 rounded text-xs">{billing.stripe_customer_id}</code>
                <CopyButton value={billing.stripe_customer_id} label="Copier" />
              </div>
              {billing.stripe_subscription_id && (
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Subscription:</span>
                  <code className="bg-gray-100 px-1 rounded text-xs">{billing.stripe_subscription_id}</code>
                  <CopyButton value={billing.stripe_subscription_id} label="Copier" />
                </div>
              )}
              {billing.billing_status && <p><span className="text-gray-500">Statut:</span> <span className="font-medium">{billing.billing_status}</span></p>}
              {billing.current_period_end && <p><span className="text-gray-500">Fin période:</span> {new Date(billing.current_period_end).toLocaleDateString("fr-FR")}</p>}
              {billing.trial_ends_at && <p><span className="text-gray-500">Essai jusqu'au:</span> {new Date(billing.trial_ends_at).toLocaleDateString("fr-FR")}</p>}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-gray-500 text-sm">Aucun customer Stripe.</p>
              <button
                type="button"
                disabled={stripeLoading}
                onClick={onCreateStripeCustomer}
                className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              >
                {stripeLoading ? "Création…" : "Créer customer"}
              </button>
            </div>
          )}
          <p className="text-xs text-gray-400 mt-1">Lier abonnement : bientôt</p>
        </div>
      </div>
    </section>
  );
}
