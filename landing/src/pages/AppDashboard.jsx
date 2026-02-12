import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const COUNTERS_DEFAULT = { calls_total: 0, bookings_confirmed: 0, transfers: 0, abandons: 0 };

function formatDate(ts) {
  if (ts == null) return "—";
  try {
    return new Date(ts).toLocaleString("fr-FR");
  } catch {
    return "—";
  }
}

function TrendBadge({ value }) {
  if (value == null || value === 0) return <span className="text-gray-500 text-sm">—</span>;
  const isUp = value > 0;
  const color = isUp ? "text-emerald-600" : "text-red-600";
  return (
    <span className={`text-sm font-medium ${color}`}>
      {isUp ? "▲" : "▼"} {Math.abs(value)}%
    </span>
  );
}

function MiniChart({ days }) {
  if (!days || days.length === 0) return null;
  const maxVal = Math.max(1, ...days.map((d) => d.calls + d.bookings + d.transfers));
  const barMaxHeight = 64;
  return (
    <div className="mt-4 flex items-end gap-1" style={{ height: barMaxHeight + 24 }}>
      {days.map((d) => {
        const total = d.calls + d.bookings + d.transfers;
        const barHeight = maxVal ? Math.max((total / maxVal) * barMaxHeight, 2) : 2;
        const dayShort = d.date ? new Date(d.date + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "short" }) : "";
        return (
          <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1">
            <div
              className="w-full bg-emerald-200 rounded-t min-h-[2px] transition-all"
              style={{ height: `${barHeight}px` }}
              title={`${d.date}: ${d.calls} appels, ${d.bookings} RDV, ${d.transfers} transférés`}
            />
            <span className="text-xs text-gray-500 shrink-0">{dayShort}</span>
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }) {
  const isOnline = status === "online";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${
        isOnline ? "bg-emerald-100 text-emerald-800" : "bg-gray-200 text-gray-700"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${isOnline ? "bg-emerald-500" : "bg-gray-500"}`} />
      {isOnline ? "En ligne" : "Hors ligne"}
    </span>
  );
}

export default function AppDashboard() {
  const [data, setData] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setErr(null);
    api
      .tenantDashboard()
      .then((d) => {
        setData(d);
        return api.tenantKpis(7).then(setKpis).catch(() => setKpis(null));
      })
      .catch(setErr)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const id = setInterval(() => load(), 30000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <p className="text-gray-600">Chargement...</p>;
  if (err) return <p className="text-red-600">{err.message || "Erreur"}</p>;
  if (!data) return null;

  const { tenant_name, service_status, last_call, last_booking, counters_7d } = data;
  const counters = { ...COUNTERS_DEFAULT, ...(counters_7d || {}) };
  const status = ["online", "offline", "unknown"].includes(service_status?.status) ? service_status.status : "unknown";
  const trend = kpis?.trend || {};

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{tenant_name || "Dashboard"}</h2>
            <p className="text-sm text-gray-500">7 derniers jours</p>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Rafraîchir
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">Appels</p>
          <div className="flex items-baseline gap-2">
            <p className="text-2xl font-bold text-gray-900">{counters.calls_total}</p>
            <TrendBadge value={trend.calls_pct} />
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">RDV confirmés</p>
          <div className="flex items-baseline gap-2">
            <p className="text-2xl font-bold text-emerald-600">{counters.bookings_confirmed}</p>
            <TrendBadge value={trend.bookings_pct} />
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">Transférés</p>
          <div className="flex items-baseline gap-2">
            <p className="text-2xl font-bold text-gray-900">{counters.transfers}</p>
            <TrendBadge value={trend.transfers_pct} />
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">Abandons</p>
          <p className="text-2xl font-bold text-gray-900">{counters.abandons}</p>
        </div>
      </div>

      {kpis?.days?.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700">Activité 7 jours</h3>
          <MiniChart days={kpis.days} />
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">Dernier appel</p>
          <p className="font-medium text-gray-900">{formatDate(last_call?.at)}</p>
          {last_call?.outcome && <p className="text-xs text-gray-500">{last_call.outcome}</p>}
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-gray-500">Dernier RDV</p>
          <p className="font-medium text-gray-900">{formatDate(last_booking?.at)}</p>
        </div>
      </div>
    </div>
  );
}
