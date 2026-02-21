import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const COUNTERS_DEFAULT = { calls_total: 0, bookings_confirmed: 0, transfers: 0, abandons: 0 };

function formatTimeAgo(ts) {
  if (ts == null) return "—";
  try {
    const date = typeof ts === "string" ? new Date(ts.replace("Z", "+00:00")) : new Date(ts);
    const s = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (s < 10) return "à l'instant";
    if (s < 60) return `il y a ${s}s`;
    if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
    if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
    return `il y a ${Math.floor(s / 86400)} j`;
  } catch {
    return "—";
  }
}

function formatDate(ts) {
  if (ts == null) return "—";
  try {
    return new Date(ts).toLocaleString("fr-FR");
  } catch {
    return "—";
  }
}

function TrendBadge({ value }) {
  if (value == null || value === 0) return null;
  const isUp = value > 0;
  return (
    <span className={`text-sm font-medium ${isUp ? "text-emerald-600" : "text-red-600"}`}>
      {isUp ? "↑" : "↓"} {Math.abs(value)}%
    </span>
  );
}

function MiniChart({ days }) {
  if (!days || days.length === 0) return null;
  const maxVal = Math.max(1, ...days.map((d) => d.calls + d.bookings + d.transfers));
  const barMaxHeight = 56;
  return (
    <div className="mt-4 flex items-end gap-1.5" style={{ height: barMaxHeight + 28 }}>
      {days.map((d) => {
        const total = d.calls + d.bookings + d.transfers;
        const barHeight = maxVal ? Math.max((total / maxVal) * barMaxHeight, 4) : 4;
        const dayShort = d.date ? new Date(d.date + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "short" }) : "";
        return (
          <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1.5">
            <div
              className="w-full rounded-t-md bg-teal-200 transition-all"
              style={{ height: `${barHeight}px` }}
              title={`${d.date}: ${d.calls} appels, ${d.bookings} RDV, ${d.transfers} transférés`}
            />
            <span className="text-xs text-slate-500 shrink-0">{dayShort}</span>
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
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium shadow-sm ${
        isOnline ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-600 border border-slate-200"
      }`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${isOnline ? "bg-emerald-500" : "bg-slate-400"}`} />
      {isOnline ? "100% disponible" : "Hors ligne"}
    </span>
  );
}

function buildActivityItems(last_call, last_booking) {
  const items = [];
  if (last_call?.created_at) {
    const outcomeLabel =
      last_call.outcome === "booking_confirmed"
        ? "RDV programmé"
        : last_call.outcome === "transferred_human"
          ? "Appel transféré"
          : last_call.outcome === "user_abandon"
            ? "Appel abandonné"
            : "Appel traité";
    const detail =
      last_call.outcome === "booking_confirmed" && last_call.slot_label
        ? `RDV le ${last_call.slot_label}`
        : "Appel entrant traité";
    items.push({
      id: "call-" + (last_call.call_id || "0"),
      at: last_call.created_at,
      type: "call",
      title: "Appel entrant traité",
      detail: last_call.outcome === "booking_confirmed" ? detail : outcomeLabel,
      color: "emerald",
    });
  }
  if (last_booking?.created_at) {
    const detail = last_booking.slot_label
      ? `RDV le ${last_booking.slot_label}`
      : last_booking.name
        ? `Client: ${last_booking.name}`
        : "RDV confirmé";
    items.push({
      id: "booking-" + (last_booking.created_at || ""),
      at: last_booking.created_at,
      type: "booking",
      title: "RDV confirmé",
      detail,
      color: "sky",
    });
  }
  items.sort((a, b) => new Date(b.at) - new Date(a.at));
  return items.slice(0, 5);
}

const activityColors = {
  emerald: "bg-emerald-500",
  sky: "bg-sky-400",
  violet: "bg-violet-400",
  amber: "bg-amber-400",
};

const activityCardBg = {
  emerald: "bg-emerald-50 border-emerald-100",
  sky: "bg-sky-50 border-sky-100",
  violet: "bg-violet-50 border-violet-100",
  amber: "bg-amber-50 border-amber-100",
};

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

  if (loading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <p className="text-slate-500">Chargement...</p>
      </div>
    );
  }
  if (err) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-700">
        {err.message || "Erreur"}
      </div>
    );
  }
  if (!data) return null;

  const { tenant_name, service_status, last_call, last_booking, counters_7d } = data;
  const counters = { ...COUNTERS_DEFAULT, ...(counters_7d || {}) };
  const status = ["online", "offline", "unknown"].includes(service_status?.status) ? service_status.status : "unknown";
  const trend = kpis?.trend || {};
  const activities = buildActivityItems(last_call, last_booking);

  return (
    <div className="space-y-8 pb-8">
      {/* En-tête : titre + disponibilité */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{tenant_name || "Tableau de bord"}</h1>
          <p className="text-sm text-slate-500 mt-0.5">Vue d'ensemble des 7 derniers jours</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Rafraîchir
          </button>
        </div>
      </div>

      {/* 3 KPI principaux — style pastel, pédagogique */}
      <div className="grid gap-5 sm:grid-cols-3">
        <div className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-6 shadow-sm">
          <p className="text-sm font-medium text-emerald-800/80">Appels (7 jours)</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-emerald-700">{counters.calls_total}</span>
            <TrendBadge value={trend.calls_pct} />
          </div>
        </div>
        <div className="rounded-2xl border border-sky-100 bg-gradient-to-br from-sky-50 to-white p-6 shadow-sm">
          <p className="text-sm font-medium text-sky-800/80">RDV confirmés</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-sky-700">{counters.bookings_confirmed}</span>
            <TrendBadge value={trend.bookings_pct} />
          </div>
        </div>
        <div className="rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50 to-white p-6 shadow-sm">
          <p className="text-sm font-medium text-violet-800/80">Disponibilité</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-violet-700">
              {status === "online" ? "100%" : "—"}
            </span>
          </div>
          <p className="text-xs text-violet-600/80 mt-1">
            {status === "online" ? "Service actif" : "Pas d'activité récente"}
          </p>
        </div>
      </div>

      {/* Activité récente — cartes avec point coloré, titre, détail, temps relatif */}
      <div>
        <h2 className="text-base font-semibold text-slate-800 mb-4">Activité récente</h2>
        {activities.length === 0 ? (
          <div className="rounded-2xl border border-slate-100 bg-slate-50/50 p-6 text-center text-slate-500 text-sm">
            Aucune activité récente sur les 7 derniers jours.
          </div>
        ) : (
          <ul className="space-y-3">
            {activities.map((a) => (
              <li
                key={a.id}
                className={`rounded-xl border p-4 ${activityCardBg[a.color] || activityCardBg.emerald}`}
              >
                <div className="flex gap-3">
                  <span className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ${activityColors[a.color] || activityColors.emerald}`} />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-900">{a.title}</p>
                    <p className="text-sm text-slate-600 mt-0.5">{a.detail}</p>
                    <p className="text-xs text-slate-500 mt-2">{formatTimeAgo(a.at)}</p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Graphique 7 jours */}
      {kpis?.days?.length > 0 && (
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700">Activité sur 7 jours</h3>
          <MiniChart days={kpis.days} />
        </div>
      )}

      {/* Badge pédagogique Réponse rapide */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="inline-flex items-center gap-2 rounded-xl border border-amber-100 bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-800">
          <span className="text-amber-500">⚡</span>
          Réponse &lt; 2 s
        </div>
      </div>
    </div>
  );
}
