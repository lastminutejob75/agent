import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const WINDOW_OPTIONS = [7, 30];

export default function AdminTenantDashboard() {
  const { id } = useParams();
  const [windowDays, setWindowDays] = useState(30);
  const [tenant, setTenant] = useState(null);
  const [stats, setStats] = useState(null);
  const [timeseries, setTimeseries] = useState(null);
  const [activity, setActivity] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    if (!id) return;
    setErr(null);
    setLoading(true);
    try {
      const [t, s, ts, act] = await Promise.all([
        adminApi.getTenant(id),
        adminApi.tenantStats(id, windowDays),
        adminApi.tenantTimeseries(id, "calls", windowDays),
        adminApi.tenantActivity(id, 20),
      ]);
      setTenant(t);
      setStats(s);
      setTimeseries(ts);
      setActivity(act);
      setLastUpdated(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    } catch (e) {
      setErr(e.message || "Erreur chargement");
    } finally {
      setLoading(false);
    }
  }, [id, windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !stats) {
    return <div className="text-gray-500">Chargement du dashboard…</div>;
  }
  if (err && !stats) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {err}
        <Link to={`/admin/tenants/${id}`} className="block mt-2 text-indigo-600 hover:underline">
          ← Retour au client
        </Link>
      </div>
    );
  }

  const s = stats || {};
  const name = tenant?.name || `#${id}`;

  const cards = [
    { label: "Appels", value: s.calls_total ?? "—", sub: `${s.calls_abandoned ?? 0} abandons` },
    { label: "Répondus", value: s.calls_answered ?? "—" },
    { label: "RDV confirmés", value: s.appointments_total ?? "—" },
    { label: "Transferts", value: s.transfers_total ?? "—" },
    { label: "Minutes", value: s.minutes_total ?? "—" },
    { label: "Erreurs", value: s.errors_total ?? "—" },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Link to="/admin/tenants" className="text-gray-600 hover:text-gray-900">
          ← Clients
        </Link>
        <span className="text-gray-400">/</span>
        <Link to={`/admin/tenants/${id}`} className="text-gray-600 hover:text-gray-900">
          {name}
        </Link>
        <span className="text-gray-400">/</span>
        <span className="font-medium text-gray-900">Dashboard</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard · {name}</h1>
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

      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{c.label}</div>
            <div className="text-xl font-bold text-gray-900 mt-1">{c.value}</div>
            {c.sub && <div className="text-xs text-gray-400 mt-0.5">{c.sub}</div>}
          </div>
        ))}
      </div>

      {s.last_activity_at && (
        <p className="mt-2 text-xs text-gray-500">
          Dernière activité : {new Date(s.last_activity_at).toLocaleString("fr-FR")}
        </p>
      )}

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Appels par jour ({windowDays} j)</h2>
          {timeseries?.points?.length ? (
            (() => {
              const maxVal = Math.max(1, ...timeseries.points.map((x) => x.value));
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
                      <span className="text-[10px] text-gray-400 mt-1">{p.date.slice(8)}</span>
                    </div>
                  ))}
                </div>
              );
            })()
          ) : (
            <p className="text-gray-500 mt-3">Aucune donnée sur la période.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Dernière activité</h2>
          {activity?.items?.length ? (
            <ul className="mt-3 divide-y divide-gray-100 max-h-64 overflow-y-auto">
              {activity.items.map((item, i) => (
                <li key={i} className="py-2 text-sm flex flex-wrap gap-x-2 gap-y-0.5">
                  <span className="text-gray-500 shrink-0">
                    {new Date(item.date).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
                  </span>
                  <span className="font-mono text-gray-600">{item.call_id || "—"}</span>
                  <span className="text-indigo-600 font-medium">{item.event}</span>
                  {item.meta && (
                    <span className="text-gray-400 text-xs">{JSON.stringify(item.meta)}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 mt-3">Aucun événement récent.</p>
          )}
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          to={`/admin/tenants/${id}`}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
        >
          Voir détails client
        </Link>
        <Link
          to={`/admin/tenants/${id}/calls`}
          className="inline-flex items-center px-4 py-2 border border-indigo-300 text-indigo-700 font-medium rounded-lg hover:bg-indigo-50"
        >
          Voir appels
        </Link>
      </div>
    </div>
  );
}
