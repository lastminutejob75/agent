import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

function formatDate(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString("fr-FR");
  } catch {
    return ts;
  }
}

export default function AppRgpd() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .tenantRgpd()
      .then(setData)
      .catch(setErr)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-600">Chargement...</p>;
  if (err) return <p className="text-red-600">{err.message || "Erreur"}</p>;
  if (!data) return null;

  const {
    consent_obtained,
    calls_total,
    consent_rate,
    last_consents = [],
    start,
    end,
  } = data;

  function downloadCsv() {
    const rows = [
      ["Période", start || "", end || ""],
      ["Appels", calls_total ?? 0],
      ["Consentements obtenus", consent_obtained ?? 0],
      ["Taux consentement (%)", typeof consent_rate === "number" ? (consent_rate * 100).toFixed(1) : ""],
      [],
      ["Call ID", "Date", "Version"],
      ...last_consents.map((c) => [c.call_id || "", c.at || "", c.version || ""]),
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rgpd-consent-${start?.slice(0, 10) || "export"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">RGPD — Consentement</h2>
        <button
          type="button"
          onClick={downloadCsv}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Télécharger CSV
        </button>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-medium text-gray-700">7 derniers jours</h3>
        <p className="mt-1 text-xs text-gray-500">
          {start?.slice(0, 10)} → {end?.slice(0, 10)}
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-sm text-gray-500">Appels</p>
            <p className="text-2xl font-bold text-gray-900">{calls_total ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Consentements obtenus</p>
            <p className="text-2xl font-bold text-emerald-600">{consent_obtained ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Taux consentement</p>
            <p className="text-2xl font-bold text-gray-900">
              {typeof consent_rate === "number" ? `${(consent_rate * 100).toFixed(0)} %` : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-medium text-gray-700">Derniers consentements obtenus</h3>
        <p className="mt-1 text-xs text-gray-500">
          call_id, date, version (context)
        </p>
        {last_consents.length === 0 ? (
          <p className="mt-4 text-gray-500">Aucun consentement enregistré.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-2 pr-4 text-left text-gray-500">Call ID</th>
                  <th className="py-2 pr-4 text-left text-gray-500">Date</th>
                  <th className="py-2 text-left text-gray-500">Version</th>
                </tr>
              </thead>
              <tbody>
                {last_consents.map((c, i) => (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 pr-4 font-mono text-xs text-gray-700">
                      {(c.call_id || "").length > 20 ? (c.call_id || "").slice(0, 20) + "…" : (c.call_id || "—")}
                    </td>
                    <td className="py-2 pr-4 text-gray-600">{formatDate(c.at)}</td>
                    <td className="py-2 text-gray-600">{c.version || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
