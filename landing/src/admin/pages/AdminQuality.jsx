import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const WINDOW_OPTIONS = [7, 14, 30];

function TopTable({ title, items, resultFilter, windowDays }) {
  if (!items?.length) {
    return (
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
        <p className="text-slate-500 mt-3 text-sm">Aucune donnée sur la période.</p>
      </section>
    );
  }
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500 font-medium">
              <th className="pb-2 pr-4">Client</th>
              <th className="pb-2 pr-4 text-right">Count</th>
              <th className="pb-2 pr-4">Dernier incident</th>
              <th className="pb-2 w-32" />
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.tenant_id} className="border-b border-slate-100 last:border-0">
                <td className="py-2.5 pr-4">
                  <Link to={`/admin/tenants/${row.tenant_id}`} className="text-indigo-600 hover:underline font-medium">
                    {row.name}
                  </Link>
                </td>
                <td className="py-2.5 pr-4 text-right font-mono">{row.count}</td>
                <td className="py-2.5 pr-4 text-slate-500">
                  {row.last_at ? new Date(row.last_at).toLocaleString("fr-FR") : "—"}
                </td>
                <td className="py-2.5">
                  <Link
                    to={`/admin/calls?tenant_id=${row.tenant_id}&result=${resultFilter}&days=${windowDays}`}
                    className="inline-block px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100"
                  >
                    Voir appels
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AdminQuality() {
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const snapshot = await adminApi.qualitySnapshot(windowDays);
      setData(snapshot);
    } catch (e) {
      setErr(e?.message || "Erreur chargement");
    } finally {
      setLoading(false);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <div className="h-10 w-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span>Chargement Quality…</span>
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

  const kpis = data?.kpis ?? {};
  const top = data?.top ?? { anti_loop: [], abandons: [], transfers: [] };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Quality</h1>
          <p className="mt-1 text-slate-500 text-sm">
            Améliorer l’agent · {data?.window_days ?? 7} derniers jours
            {data?.generated_at && <> · Mis à jour {new Date(data.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Fenêtre</span>
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
            Rafraîchir
          </button>
        </div>
      </div>

      {err && data && (
        <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">{err}</div>
      )}

      {/* KPIs globaux */}
      <section className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">KPIs globaux</h2>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Appels</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{kpis.calls_total ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Abandons</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{kpis.abandons ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Transferts</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{kpis.transfers ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Anti-loop</div>
            <div className="text-xl font-bold text-amber-700 mt-1">{kpis.anti_loop ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">RDV confirmés</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{kpis.appointments ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Taux abandon</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{kpis.abandon_rate_pct != null ? `${kpis.abandon_rate_pct} %` : "—"}</div>
          </div>
        </div>
      </section>

      {/* Top tenants par problème */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <TopTable
          title="Top 10 · Anti-loop"
          items={top.anti_loop}
          resultFilter="error"
          windowDays={windowDays}
        />
        <TopTable
          title="Top 10 · Abandons"
          items={top.abandons}
          resultFilter="abandoned"
          windowDays={windowDays}
        />
        <TopTable
          title="Top 10 · Transferts"
          items={top.transfers}
          resultFilter="transfer"
          windowDays={windowDays}
        />
      </div>
    </div>
  );
}
