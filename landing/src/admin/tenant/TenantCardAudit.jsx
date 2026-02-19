import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

export default function TenantCardAudit({ tenantId }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    adminApi
      .tenantActivity(tenantId, 10)
      .then((d) => setEvents(d?.items ?? []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [tenantId]);

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Logs & Audit</h2>
      {loading ? (
        <p className="text-sm text-gray-500">Chargement…</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-gray-500">Aucun événement récent.</p>
      ) : (
        <ul className="space-y-1 text-sm text-gray-700">
          {events.slice(0, 10).map((ev, i) => (
            <li key={i} className="flex flex-wrap gap-2">
              <span className="text-gray-500">{ev.date ? new Date(ev.date).toLocaleString("fr-FR") : "—"}</span>
              <span className="font-medium">{ev.event ?? "—"}</span>
              {ev.call_id && <span className="font-mono text-xs">{ev.call_id}</span>}
              {ev.meta?.reason && <span className="text-gray-500">{ev.meta.reason}</span>}
            </li>
          ))}
        </ul>
      )}
      <Link to="/admin/audit" className="mt-3 inline-block text-sm text-indigo-600 hover:underline">
        Voir tout l'audit →
      </Link>
    </section>
  );
}
