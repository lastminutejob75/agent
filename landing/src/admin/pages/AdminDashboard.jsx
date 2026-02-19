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
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <div className="h-10 w-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span>Chargement du dashboard…</span>
      </div>
    );
  }
  if (err && !globalStats) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
        <p className="font-medium">Erreur</p>
        <p className="mt-1 text-sm">{err}</p>
        <button
          type="button"
          onClick={load}
          className="mt-4 px-4 py-2 text-sm font-medium text-red-700 bg-white border border-red-200 rounded-lg hover:bg-red-50"
        >
          Réessayer
        </button>
      </div>
    );
  }

  const s = globalStats || {};
  const primaryCards = [
    { label: "Appels", value: s.calls_total ?? "—", sub: `${s.calls_abandoned ?? 0} abandons`, href: "/admin/calls" },
    { label: "RDV confirmés", value: s.appointments_total ?? "—", sub: null, href: null },
    { label: "Coût 30j (USD)", value: s.cost_usd_total != null ? Number(s.cost_usd_total).toFixed(2) : "—", sub: "Vapi", href: null },
    { label: "Clients", value: s.tenants_active ?? "—", sub: `/${s.tenants_total ?? 0} total`, href: "/admin/tenants" },
  ];
  const secondaryCards = [
    { label: "Transferts", value: s.transfers_total ?? "—" },
    { label: "Minutes", value: s.minutes_total ?? "—" },
    { label: "Erreurs", value: s.errors_total ?? "—" },
  ];

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="mt-1 text-slate-500 text-sm">
            Vue d’ensemble sur les {windowDays} derniers jours
            {lastUpdated && <> · Mis à jour à {lastUpdated}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} jours</option>
            ))}
          </select>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 disabled:opacity-50"
          >
            Rafraîchir
          </button>
        </div>
      </div>

      {/* KPIs principaux */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {primaryCards.map((c) => (
          <div
            key={c.label}
            className={`bg-white rounded-xl border border-slate-200 p-5 shadow-sm ${c.href ? "hover:border-indigo-200 transition-colors" : ""}`}
          >
            {c.href ? (
              <Link to={c.href} className="block group">
                <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{c.label}</div>
                <div className="text-2xl font-bold text-slate-900 mt-1 group-hover:text-indigo-600">{c.value}</div>
                {c.sub && <div className="text-xs text-slate-400 mt-0.5">{c.sub}</div>}
                <span className="inline-block mt-2 text-xs font-medium text-indigo-600 opacity-0 group-hover:opacity-100">Voir →</span>
              </Link>
            ) : (
              <>
                <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{c.label}</div>
                <div className="text-2xl font-bold text-slate-900 mt-1">{c.value}</div>
                {c.sub && <div className="text-xs text-slate-400 mt-0.5">{c.sub}</div>}
              </>
            )}
          </div>
        ))}
      </div>

      {/* KPIs secondaires */}
      <div className="flex flex-wrap gap-3">
        {secondaryCards.map((c) => (
          <div key={c.label} className="bg-slate-50 rounded-lg border border-slate-100 px-4 py-2.5">
            <span className="text-xs text-slate-500">{c.label}</span>
            <span className="ml-2 font-semibold text-slate-800">{c.value}</span>
          </div>
        ))}
        {s.last_activity_at && (
          <span className="text-xs text-slate-400 self-center">
            Dernière activité : {new Date(s.last_activity_at).toLocaleString("fr-FR")}
          </span>
        )}
      </div>

      {/* Grille contenu */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">Top clients (appels)</h2>
          {topTenants?.items?.length ? (
            <ul className="mt-3 divide-y divide-slate-100">
              {topTenants.items.map((t) => (
                <li key={t.tenant_id} className="py-2.5 flex justify-between items-center">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium truncate pr-2">
                    {t.name}
                  </Link>
                  <span className="text-slate-600 font-mono text-sm">{t.value}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500 mt-3 text-sm">Aucune donnée sur la période.</p>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">Top clients (coût USD)</h2>
          {topTenantsByCost?.items?.length ? (
            <ul className="mt-3 divide-y divide-slate-100">
              {topTenantsByCost.items.map((t) => (
                <li key={t.tenant_id} className="py-2.5 flex justify-between items-center">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium truncate pr-2">
                    {t.name}
                  </Link>
                  <span className="text-slate-600 font-mono text-sm">{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500 mt-3 text-sm">Aucune donnée sur la période.</p>
          )}
        </section>

        <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">Billing (mois UTC)</h2>
          {billingSnapshot && (
            <div className="mt-3 space-y-3 text-sm">
              <p>
                <span className="text-slate-500">Coût Vapi ce mois :</span>{" "}
                <strong className="font-mono text-slate-900">{Number(billingSnapshot.cost_usd_this_month ?? 0).toFixed(2)} $</strong>
              </p>
              {billingSnapshot.tenants_past_due_count > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800">
                  <p className="font-medium">{billingSnapshot.tenants_past_due_count} client(s) past_due</p>
                  {billingSnapshot.tenants_past_due?.length > 0 ? (
                    <ul className="mt-1 space-y-1">
                      {billingSnapshot.tenants_past_due.map((t) => (
                        <li key={t.tenant_id}>
                          <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                            {t.name}
                          </Link>
                          {t.current_period_end && (
                            <span className="text-amber-700/80 text-xs ml-1">(période jusqu’au {new Date(t.current_period_end).toLocaleDateString("fr-FR")})</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="flex flex-wrap gap-1 mt-1">
                      {billingSnapshot.tenant_ids_past_due?.map((tid) => (
                        <Link key={tid} to={`/admin/tenants/${tid}`} className="text-indigo-600 hover:underline">#{tid}</Link>
                      ))}
                    </span>
                  )}
                </div>
              )}
              {billingSnapshot.top_tenants_by_cost_this_month?.length > 0 && (
                <ul className="divide-y divide-slate-100 pt-2">
                  {billingSnapshot.top_tenants_by_cost_this_month.slice(0, 5).map((t) => (
                    <li key={t.tenant_id} className="py-1.5 flex justify-between text-sm">
                      <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline truncate pr-2">{t.name}</Link>
                      <span className="font-mono text-slate-600">{Number(t.value).toFixed(2)} $</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {(!billingSnapshot || (billingSnapshot.cost_usd_this_month === 0 && !billingSnapshot.tenants_past_due_count)) && (
            <p className="text-slate-500 mt-3 text-sm">Aucun coût ce mois / aucun past_due.</p>
          )}
        </section>
      </div>

      {/* Activité + actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">Activité ({windowDays} j) — appels/jour</h2>
          {timeseries?.points?.length ? (
            (() => {
              const maxVal = Math.max(1, ...timeseries.points.map((x) => x.value));
              return (
                <div className="mt-4 flex flex-wrap gap-1 items-end">
                  {timeseries.points.map((p) => (
                    <div
                      key={p.date}
                      className="flex flex-col items-center flex-1 min-w-[8px]"
                      title={`${p.date}: ${p.value}`}
                    >
                      <div
                        className="w-full max-w-[12px] bg-indigo-400 rounded-t min-h-[4px]"
                        style={{ height: Math.max(6, (p.value / maxVal) * 80) }}
                      />
                      <span className="text-[10px] text-slate-400 mt-1 truncate w-full text-center">
                        {p.date?.slice(8) ?? ""}
                      </span>
                    </div>
                  ))}
                </div>
              );
            })()
          ) : (
            <p className="text-slate-500 mt-4 text-sm">Aucune série sur la période.</p>
          )}
        </section>
        <section className="flex flex-col justify-center gap-3">
          <Link
            to="/admin/tenants"
            className="inline-flex items-center justify-center px-4 py-3 bg-slate-900 text-white font-medium rounded-xl hover:bg-slate-800 transition-colors"
          >
            Voir tous les clients →
          </Link>
          <Link
            to="/admin/calls"
            className="inline-flex items-center justify-center px-4 py-3 border border-slate-300 text-slate-700 font-medium rounded-xl hover:bg-slate-50 transition-colors"
          >
            Voir tous les appels →
          </Link>
        </section>
      </div>
    </div>
  );
}
