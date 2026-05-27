import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

function StatusRow({ label, value, ok }) {
  const color = ok === true ? "text-emerald-600" : ok === false ? "text-red-600" : "text-gray-700";
  return (
    <tr className="border-b border-gray-100 last:border-0">
      <td className="py-2 pr-4 text-sm text-gray-500">{label}</td>
      <td className={`py-2 text-sm font-medium ${color}`}>{value}</td>
    </tr>
  );
}

export default function AppStatus() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .tenantTechnicalStatus()
      .then(setData)
      .catch(setErr)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-600">Chargement...</p>;
  if (err) return <p className="text-red-600">{err.message || "Erreur"}</p>;
  if (!data) return null;

  const { vocal, whatsapp, calendar, service_agent } = data;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Statut technique</h2>
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <table className="w-full">
          <tbody>
            <StatusRow label="Vocal (DID)" value={vocal?.did || "—"} ok={vocal?.ok} />
            <StatusRow label="WhatsApp" value={whatsapp?.key ? "Configuré" : "Non configuré"} ok={whatsapp?.ok} />
            <StatusRow label="Calendrier" value={calendar?.provider || "—"} ok={calendar?.ok} />
            <StatusRow label="Service agent" value={service_agent?.status || "—"} ok={service_agent?.ok} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
