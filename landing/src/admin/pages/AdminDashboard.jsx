import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const WINDOW_OPTIONS = [7, 30];

export default function AdminDashboard() {
  const [windowDays, setWindowDays] = useState(30);
  const [globalStats, setGlobalStats] = useState(null);
  const [timeseries, setTimeseries] = useState(null);
  const [topTenants, setTopTenants] = useState(null);
  const [topTenantsByCost, setTopTenantsByCost] = useState(null);
  const [billingSnapshot, setBillingSnapshot] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const [stats, ts, top, topCost, snapshot] = await Promise.all([
        adminApi.globalStats(windowDays),
        adminApi.statsTimeseries("calls", windowDays),
        adminApi.statsTopTenants("calls", windowDays, 10),
        adminApi.statsTopTenants("cost_usd", windowDays, 10),
        adminApi.billingSnapshot().catch(() => null),
      ]);
      setGlobalStats(stats);
      setTimeseries(ts);
      setTopTenants(top);
      setTopTenantsByCost(topCost);
      setBillingSnapshot(snapshot);
      setLastUpdated(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    } catch (e) {
      setErr(e.message || "Erreur chargement stats");
    } finally {
      setLoading(false);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !globalStats) {
    return <div className="text-gray-500">Chargement du dashboard…</div>;
  }
  if (err && !globalStats) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {err}
      </div>
    );
  }

  const s = globalStats || {};
  const cards = [
    { label: "Clients actifs", value: s.tenants_active ?? "—", sub: `/${s.tenants_total ?? 0} total` },
    { label: "Appels", value: s.calls_total ?? "—", sub: `${s.calls_abandoned ?? 0} abandons` },
    { label: "RDV confirmés", value: s.appointments_total ?? "—" },
    { label: "Transferts", value: s.transfers_total ?? "—" },
    { label: "Minutes (appels)", value: s.minutes_total ?? "—" },
    { label: "Coût 30j (USD)", value: s.cost_usd_total != null ? Number(s.cost_usd_total).toFixed(2) : "—" },
    { label: "Erreurs", value: s.errors_total ?? "—" },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">Fenêtre</span>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900"
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} j</option>
            ))}
          </select>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-lg hover:bg-indigo-50 disabled:opacity-50"
          >
            Rafraîchir
          </button>
        </div>
      </div>
      {lastUpdated && (
        <p className="text-xs text-gray-400 mt-1">Dernière mise à jour : {lastUpdated}</p>
      )}

      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{c.label}</div>
            <div className="text-xl font-bold text-gray-900 mt-1">{c.value}</div>
            {c.sub && <div className="text-xs text-gray-400 mt-0.5">{c.sub}</div>}
          </div>
        ))}
      </div>

      {s.last_activity_at && (
        <p className="mt-2 text-xs text-gray-500">Dernière activité globale : {new Date(s.last_activity_at).toLocaleString("fr-FR")}</p>
      )}

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Top 10 clients (appels)</h2>
          {topTenants?.items?.length ? (
            <ul className="mt-3 divide-y divide-gray-100">
              {topTenants.items.map((t) => (
                <li key={t.tenant_id} className="py-2 flex justify-between items-center">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                    {t.name}
                  </Link>
                  <span className="text-gray-600 font-mono">{t.value}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 mt-3">Aucune donnée sur la période.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Top 10 clients (coût USD)</h2>
          {topTenantsByCost?.items?.length ? (
            <ul className="mt-3 divide-y divide-gray-100">
              {topTenantsByCost.items.map((t) => (
                <li key={t.tenant_id} className="py-2 flex justify-between items-center">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                    {t.name}
                  </Link>
                  <span className="text-gray-600 font-mono">{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 mt-3">Aucune donnée sur la période.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Billing (ce mois UTC)</h2>
          {billingSnapshot && (
            <div className="mt-3 space-y-2 text-sm">
              <p><span className="text-gray-500">Coût Vapi ce mois :</span> <strong className="font-mono">{Number(billingSnapshot.cost_usd_this_month ?? 0).toFixed(2)} $</strong></p>
              {billingSnapshot.tenants_past_due_count > 0 && (
                <div className="text-amber-700">
                  <p className="font-medium mb-1">{billingSnapshot.tenants_past_due_count} client(s) past_due</p>
                  {billingSnapshot.tenants_past_due?.length > 0 ? (
                    <ul className="space-y-1">
                      {billingSnapshot.tenants_past_due.map((t) => (
                        <li key={t.tenant_id}>
                          <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                            {t.name}
                          </Link>
                          {t.current_period_end && (
                            <span className="text-gray-500 text-xs ml-1">(période jusqu'au {new Date(t.current_period_end).toLocaleDateString("fr-FR")})</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="ml-1">
                      {billingSnapshot.tenant_ids_past_due?.map((tid) => (
                        <Link key={tid} to={`/admin/tenants/${tid}`} className="text-indigo-600 hover:underline ml-1">#{tid}</Link>
                      ))}
                    </span>
                  )}
                </div>
              )}
              {billingSnapshot.top_tenants_by_cost_this_month?.length > 0 && (
                <ul className="mt-2 divide-y divide-gray-100">
                  {billingSnapshot.top_tenants_by_cost_this_month.slice(0, 5).map((t) => (
                    <li key={t.tenant_id} className="py-1 flex justify-between">
                      <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline truncate">{t.name}</Link>
                      <span className="font-mono text-gray-600">{Number(t.value).toFixed(2)} $</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {(!billingSnapshot || (billingSnapshot.cost_usd_this_month === 0 && !billingSnapshot.tenants_past_due_count)) && (
            <p className="text-gray-500 mt-3 text-sm">Aucun coût ce mois / aucun past_due.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm lg:col-span-3">
          <h2 className="text-lg font-semibold text-gray-800">Activité {windowDays} jours (appels/jour)</h2>
          {timeseries?.points?.length ? (
            (() => {
              const maxVal = Math.max(1, ...timeseries.points.map((x) => x.value)));
              return (
                <div className="mt-3 flex flex-wrap gap-1 items-end">
                  {timeseries.points.map((p) => (
                    <div
                      key={p.date}
                      className="flex flex-col items-center"
                      title={`${p.date}: ${p.value}`}
                    >
                      <div
                        className="w-2 bg-indigo-400 rounded-t min-h-[4px]"
                        style={{ height: Math.max(4, (p.value / maxVal) * 60) }}
                      />
                      <span className="text-[10px] text-gray-400 mt-1">
                        {p.date.slice(8)}
                      </span>
                    </div>
                  ))}
                </div>
              );
            })()
          ) : (
            <p className="text-gray-500 mt-3">Aucune série sur la période.</p>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-4">
        <Link to="/admin/tenants" className="text-indigo-600 hover:underline font-medium">
          Voir toute la liste des clients →
        </Link>
        <Link to="/admin/calls" className="text-indigo-600 hover:underline font-medium">
          Voir tous les appels →
        </Link>
      </div>
    </div>
  );
}
