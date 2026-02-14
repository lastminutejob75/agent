import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";

/**
 * Contrat attendu :
 * - service_status.status ∈ online|offline|unknown
 * - last_call peut être null
 * - last_booking peut être null
 * - counters_7d toujours présent (valeurs 0)
 */
const COUNTERS_DEFAULT = { calls_total: 0, bookings_confirmed: 0, transfers: 0, abandons: 0 };

function formatDate(ts) {
  if (ts == null) return "—";
  try {
    return new Date(ts).toLocaleString("fr-FR");
  } catch {
    return "—";
  }
}

function outcomeLabel(outcome) {
  const map = {
    booking_confirmed: "RDV confirmé",
    transferred_human: "Transféré",
    user_abandon: "Abandon",
  };
  return map[outcome] ?? "—";
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

function getErrorMessage(err) {
  const status = err?.status;
  if (status === 401) return { msg: "Token invalide ou expiré.", link: true };
  if (status === 404) return { msg: "Tenant introuvable.", link: false };
  if (status >= 500) return { msg: "Erreur serveur.", link: false };
  return { msg: err?.message || "Erreur", link: false };
}

export default function AdminTenantDashboard() {
  const { tenantId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  function loadDashboard(silent = false) {
    if (!tenantId) return;
    if (!silent) setLoading(true);
    setErr(null);
    api
      .adminDashboard(tenantId)
      .then(setData)
      .catch((e) => setErr(e))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadDashboard();
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) return;
    const id = setInterval(() => loadDashboard(true), 30000);
    return () => clearInterval(id);
  }, [tenantId]);

  if (loading) return <p className="p-8 text-gray-600">Chargement...</p>;
  if (err) {
    const { msg, link } = getErrorMessage(err);
    return (
      <div className="mx-auto max-w-4xl p-8">
        <p className="text-red-600">{msg}</p>
        {link && (
          <Link to="/admin" className="mt-2 inline-block text-blue-600 hover:underline">
            Retour /admin pour saisir le token
          </Link>
        )}
      </div>
    );
  }
  if (!data) return null;

  const { tenant_name, service_status, last_call, last_booking, counters_7d, transfer_reasons } = data;
  const counters = { ...COUNTERS_DEFAULT, ...(counters_7d || {}) };
  const status = ["online", "offline", "unknown"].includes(service_status?.status) ? service_status.status : "unknown";
  const topTransferred = transfer_reasons?.top_transferred ?? [];
  const transferTotal = topTransferred.reduce((s, x) => s + x.count, 0);
  const needsPriority = transferTotal > 0;

  return (
    <div className="mx-auto max-w-4xl p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <Link to="/admin" className="text-gray-600 hover:text-gray-900">← Admin</Link>
        <Link to={`/admin/tenants/${tenantId}`} className="text-gray-600 hover:text-gray-900">Détail tenant</Link>
      </div>

      {/* Header */}
      <div className="mb-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{tenant_name || `Tenant ${tenantId}`}</h1>
            <p className="mt-1 text-sm text-gray-500">Dashboard — 7 derniers jours</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={loadDashboard}
              disabled={loading}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Rafraîchir
            </button>
            <StatusBadge status={status} />
          </div>
        </div>
      </div>

      {/* 3 blocs */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Bleu — Dernier appel */}
        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-blue-800">Dernier appel</h2>
          {last_call ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-gray-600">Le</span> {formatDate(last_call.created_at)}</p>
              <p><span className="text-gray-600">Issue</span> <span className="font-medium">{outcomeLabel(last_call.outcome)}</span></p>
              {last_call.name && <p><span className="text-gray-600">Nom</span> {last_call.name}</p>}
              {last_call.motif && <p><span className="text-gray-600">Motif</span> {last_call.motif}</p>}
              {last_call.slot_label && <p><span className="text-gray-600">Créneau</span> {last_call.slot_label}</p>}
            </div>
          ) : (
            <p className="text-blue-700/70">Aucun appel récent</p>
          )}
        </div>

        {/* Vert — Dernier RDV */}
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-emerald-800">Dernier RDV</h2>
          {last_booking ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-gray-600">Le</span> {formatDate(last_booking.created_at)}</p>
              <p><span className="text-gray-600">Client</span> <span className="font-medium">{last_booking.name || "—"}</span></p>
              {last_booking.slot_label && <p><span className="text-gray-600">Créneau</span> {last_booking.slot_label}</p>}
              {last_booking.source && <p className="text-xs text-gray-500">Source: {last_booking.source}</p>}
            </div>
          ) : (
            <p className="text-emerald-700/70">Aucun rendez-vous confirmé</p>
          )}
        </div>

        {/* Violet — Stats 7j */}
        <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-violet-800">Stats 7 jours</h2>
          <div className="space-y-2 text-sm">
            <p><span className="text-gray-600">Appels</span> <span className="font-semibold">{counters.calls_total}</span></p>
            <p><span className="text-gray-600">RDV confirmés</span> <span className="font-semibold">{counters.bookings_confirmed}</span></p>
            <p><span className="text-gray-600">Transferts</span> <span className="font-semibold">{counters.transfers}</span></p>
            <p><span className="text-gray-600">Abandons</span> <span className="font-semibold">{counters.abandons}</span></p>
          </div>
        </div>
      </div>

      {/* Top 5 raisons de transfert */}
      <div className="mt-6 rounded-xl border border-amber-100 bg-amber-50/50 p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-800">Top 5 raisons de transfert (7 jours)</h2>
          {needsPriority && (
            <span className="rounded-full bg-amber-200 px-3 py-1 text-xs font-medium text-amber-900">À traiter en priorité</span>
          )}
        </div>
        {topTransferred.length > 0 ? (
          <div className="space-y-2 text-sm">
            {topTransferred.map((item, i) => (
              <div key={item.reason} className="flex items-center justify-between">
                <span className="font-mono text-gray-700">{item.reason}</span>
                <span className="font-semibold text-amber-800">{item.count}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-amber-700/70">Aucun transfert sur la période</p>
        )}
      </div>
    </div>
  );
}
