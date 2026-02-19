import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { getClientLoginUrl } from "../../lib/clientAppUrl";

const WINDOW_OPTIONS = [7, 14, 30];

export default function AdminOperations() {
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [actionLoading, setActionLoading] = useState(null); // tenant_id ou "refresh"

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    setActionLoading("refresh");
    try {
      const snapshot = await adminApi.operationsSnapshot(windowDays);
      setData(snapshot);
      setLastUpdated(snapshot?.generated_at ? new Date(snapshot.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : null);
    } catch (e) {
      setErr(e?.message || "Erreur chargement");
    } finally {
      setLoading(false);
      setActionLoading(null);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUnsuspend(tenantId) {
    setActionLoading(tenantId);
    try {
      await adminApi.tenantUnsuspend(tenantId);
      await load();
    } catch (e) {
      setErr(e?.message || "Erreur unsuspend");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleForceActive(tenantId) {
    setActionLoading(tenantId);
    try {
      await adminApi.tenantForceActive(tenantId, 7);
      await load();
    } catch (e) {
      setErr(e?.message || "Erreur force-active");
    } finally {
      setActionLoading(null);
    }
  }

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <div className="h-10 w-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span>Chargement Operations…</span>
      </div>
    );
  }

  if (err && !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
        <p className="font-medium">Erreur</p>
        <p className="mt-1 text-sm">{err}</p>
        <button type="button" onClick={load} className="mt-4 px-4 py-2 text-sm font-medium text-red-700 bg-white border border-red-200 rounded-lg hover:bg-red-50">
          Réessayer
        </button>
      </div>
    );
  }

  const billing = data?.billing ?? {};
  const suspensions = data?.suspensions ?? { items: [] };
  const cost = data?.cost ?? { today_utc: { total_usd: 0, top: [] }, last_7d: { total_usd: 0, top: [] } };
  const errors = data?.errors ?? { top_tenants: [], errors_total: 0 };
  const quota = data?.quota ?? { month_utc: null, over_80: [], over_100: [] };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Operations</h1>
          <p className="mt-1 text-slate-500 text-sm">
            Risque paiement, suspendus, coûts, erreurs
            {lastUpdated && <> · Mis à jour à {lastUpdated}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Fenêtre erreurs</span>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} j</option>
            ))}
          </select>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 disabled:opacity-50"
          >
            {actionLoading === "refresh" ? "Chargement…" : "Rafraîchir"}
          </button>
        </div>
      </div>

      {err && data && (
        <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
          {err}
        </div>
      )}

      {/* À risque paiement */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">À risque paiement</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Coût Vapi ce mois (UTC) : <strong className="font-mono text-slate-900">{Number(billing.cost_usd_this_month ?? 0).toFixed(2)} $</strong>
          {billing.month_utc && <span className="ml-1">({billing.month_utc})</span>}
        </p>
        {billing.tenants_past_due?.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {billing.tenants_past_due.map((t) => (
              <li key={t.tenant_id} className="flex items-center justify-between gap-2 py-2 border-b border-slate-100 last:border-0 flex-wrap">
                <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                  {t.name}
                </Link>
                <span className="text-slate-500 text-sm">
                  {t.billing_status}
                  {t.current_period_end && ` · Période jusqu'au ${new Date(t.current_period_end).toLocaleDateString("fr-FR")}`}
                </span>
                <a
                  href={getClientLoginUrl(undefined, t.tenant_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-indigo-600 hover:underline whitespace-nowrap"
                  title="Page de connexion client"
                >
                  Connexion client ↗
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500 mt-3 text-sm">Aucun client past_due.</p>
        )}
      </section>

      {/* Quota risk */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">Quota risk</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Utilisation minutes ce mois UTC
          {quota.month_utc && <span className="ml-1">({quota.month_utc})</span>}
        </p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">80%+</span>
              {quota.over_80?.length ?? 0} tenant(s)
            </h3>
            {quota.over_80?.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {quota.over_80.map((t) => (
                  <li key={t.tenant_id} className="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-slate-100 last:border-0">
                    <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium truncate pr-2">
                      {t.name}
                    </Link>
                    <span className="text-slate-600 font-mono text-sm whitespace-nowrap">
                      {Number(t.used_minutes).toFixed(0)} / {t.included_minutes} min · {t.usage_pct}%
                    </span>
                    <a href={getClientLoginUrl(undefined, t.tenant_id)} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline" title="Connexion client">↗</a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500 mt-2 text-sm">Aucun.</p>
            )}
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-600 flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">100%+</span>
              {quota.over_100?.length ?? 0} tenant(s)
            </h3>
            {quota.over_100?.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {quota.over_100.map((t) => (
                  <li key={t.tenant_id} className="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-slate-100 last:border-0">
                    <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium truncate pr-2">
                      {t.name}
                    </Link>
                    <span className="text-slate-600 font-mono text-sm whitespace-nowrap">
                      {Number(t.used_minutes).toFixed(0)} / {t.included_minutes} min · {t.usage_pct}%
                    </span>
                    <a href={getClientLoginUrl(undefined, t.tenant_id)} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-600 hover:underline" title="Connexion client">↗</a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500 mt-2 text-sm">Aucun.</p>
            )}
          </div>
        </div>
      </section>

      {/* Suspendus */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">Suspendus</h2>
        <p className="text-sm text-slate-500 mt-0.5">{suspensions.suspended_total ?? 0} client(s) suspendu(s)</p>
        {suspensions.items?.length > 0 ? (
          <ul className="mt-3 space-y-3">
            {suspensions.items.map((s) => (
              <li key={s.tenant_id} className="flex flex-wrap items-center justify-between gap-2 py-3 border-b border-slate-100 last:border-0">
                <div>
                  <Link to={`/admin/tenants/${s.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                    {s.name}
                  </Link>
                  <span className="ml-2 text-slate-500 text-sm">
                    {s.reason}{s.mode && s.mode !== "hard" ? ` · ${s.mode}` : ""}
                    {s.suspended_at && ` · depuis ${new Date(s.suspended_at).toLocaleDateString("fr-FR")}`}
                  </span>
                </div>
                <div className="flex gap-2 items-center">
                  <a
                    href={getClientLoginUrl(undefined, s.tenant_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-600 hover:underline whitespace-nowrap"
                    title="Page de connexion client"
                  >
                    Connexion client ↗
                  </a>
                  <button
                    type="button"
                    onClick={() => handleUnsuspend(s.tenant_id)}
                    disabled={actionLoading === s.tenant_id}
                    className="px-3 py-1.5 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-50"
                  >
                    {actionLoading === s.tenant_id ? "…" : "Lever"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleForceActive(s.tenant_id)}
                    disabled={actionLoading === s.tenant_id}
                    className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 border border-slate-200 rounded-lg hover:bg-slate-200 disabled:opacity-50"
                  >
                    Forcer actif 7j
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500 mt-3 text-sm">Aucun client suspendu.</p>
        )}
      </section>

      {/* Top coût */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">Top coût</h2>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <h3 className="text-sm font-medium text-slate-500">
              Aujourd’hui (UTC){cost.today_utc?.date_utc ? ` · ${cost.today_utc.date_utc}` : ""}
            </h3>
            <p className="text-xl font-bold text-slate-900 mt-1">{Number(cost.today_utc?.total_usd ?? 0).toFixed(2)} $</p>
            <ul className="mt-2 space-y-1">
              {(cost.today_utc?.top ?? []).slice(0, 5).map((t) => (
                <li key={t.tenant_id} className="flex justify-between text-sm">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline truncate pr-2">{t.name}</Link>
                  <span className="font-mono text-slate-600">{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-500">
              {cost.last_7d?.window_days ?? 7} derniers jours
            </h3>
            <p className="text-xl font-bold text-slate-900 mt-1">{Number(cost.last_7d?.total_usd ?? 0).toFixed(2)} $</p>
            <ul className="mt-2 space-y-1">
              {(cost.last_7d?.top ?? []).slice(0, 5).map((t) => (
                <li key={t.tenant_id} className="flex justify-between text-sm">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline truncate pr-2">{t.name}</Link>
                  <span className="font-mono text-slate-600">{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-500">Ce mois (UTC)</h3>
            <p className="text-xl font-bold text-slate-900 mt-1">{Number(billing.cost_usd_this_month ?? 0).toFixed(2)} $</p>
            <ul className="mt-2 space-y-1">
              {(billing.top_tenants_by_cost_this_month ?? []).slice(0, 5).map((t) => (
                <li key={t.tenant_id} className="flex justify-between text-sm">
                  <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline truncate pr-2">{t.name}</Link>
                  <span className="font-mono text-slate-600">{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Erreurs */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">Erreurs</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Top 10 tenants par erreurs sur {errors.window_days ?? 7} j · Total : <strong>{errors.errors_total ?? 0}</strong>
        </p>
        {errors.top_tenants?.length > 0 ? (
          <ul className="mt-3 divide-y divide-slate-100">
            {errors.top_tenants.map((t) => (
              <li key={t.tenant_id} className="py-2.5 flex justify-between items-center">
                <Link to={`/admin/tenants/${t.tenant_id}`} className="text-indigo-600 hover:underline font-medium truncate pr-2">
                  {t.name}
                </Link>
                <span className="text-slate-600 font-mono text-sm">{t.errors_total}</span>
                {t.last_error_at && (
                  <span className="text-slate-400 text-xs ml-2">{new Date(t.last_error_at).toLocaleString("fr-FR")}</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500 mt-3 text-sm">Aucune erreur sur la période.</p>
        )}
      </section>
    </div>
  );
}
