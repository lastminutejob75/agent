import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";

/** Badge couleur selon statut: ok=vert, incomplete=orange, error=rouge, not_configured=gris */
function StatusBadge({ status }) {
  const map = {
    active: { cls: "bg-emerald-100 text-emerald-800", label: "Actif" },
    connected: { cls: "bg-emerald-100 text-emerald-800", label: "Connecté" },
    online: { cls: "bg-emerald-100 text-emerald-800", label: "En ligne" },
    incomplete: { cls: "bg-amber-100 text-amber-800", label: "Incomplet" },
    offline: { cls: "bg-gray-200 text-gray-600", label: "Hors ligne" },
    not_configured: { cls: "bg-gray-200 text-gray-600", label: "Non configuré" },
  };
  const { cls, label } = map[status] || map.not_configured;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status === "online" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
      {label}
    </span>
  );
}

export default function AdminTenant() {
  const { tenantId } = useParams();
  const [tenant, setTenant] = useState(null);
  const [techStatus, setTechStatus] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    setErr("");
    Promise.all([
      api.adminGetTenant(tenantId),
      api.adminTechnicalStatus(tenantId).catch(() => null),
    ])
      .then(([t, ts]) => {
        setTenant(t);
        setTechStatus(ts);
      })
      .catch((e) => setErr(e.message || "Erreur"))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) return <p className="p-8 text-gray-600">Chargement...</p>;
  if (err) {
    const isAuth = (err || "").toLowerCase().includes("401") || (err || "").toLowerCase().includes("invalid");
    return (
      <div className="mx-auto max-w-4xl p-8">
        <p className="text-red-600">{err}</p>
        {isAuth && <Link to="/admin" className="text-blue-600 hover:underline">Saisir le token admin</Link>}
      </div>
    );
  }
  if (!tenant) return null;

  return (
    <div className="mx-auto max-w-4xl p-6 md:p-8">
      <Link to="/admin" className="text-gray-600 hover:text-gray-900">← Admin</Link>
      <h1 className="mt-4 text-2xl font-bold text-gray-900">{tenant.name} (id={tenant.tenant_id})</h1>
      <p className="mt-2">
        <Link to={`/admin/tenants/${tenantId}/dashboard`} className="text-blue-600 hover:underline">Voir le dashboard →</Link>
      </p>

      {/* Bloc Statut technique */}
      {techStatus && (
        <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Statut technique</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <tbody className="divide-y divide-gray-100">
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Numéro (DID)</td>
                  <td className="py-2 font-mono" colSpan={2}>{techStatus.did || "—"}</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Routing</td>
                  <td className="py-2" colSpan={2}>
                    <StatusBadge status={techStatus.routing_status} />
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Provider calendrier</td>
                  <td className="py-2">{techStatus.calendar_provider === "google" ? "Google" : techStatus.calendar_provider || "—"}</td>
                  <td className="py-2 pl-4">
                    <StatusBadge status={techStatus.calendar_status} />
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Calendrier ID</td>
                  <td className="py-2 font-mono text-xs" colSpan={2}>
                    {techStatus.calendar_id || "—"}
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Service agent</td>
                  <td className="py-2" colSpan={2}>
                    <StatusBadge status={techStatus.service_agent} />
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-gray-600">Dernier event reçu</td>
                  <td className="py-2" colSpan={2}>
                    {techStatus.last_event_ago}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Params</h2>
        <pre className="overflow-x-auto rounded-lg bg-gray-50 p-4 text-sm">{JSON.stringify(tenant.params || {}, null, 2)}</pre>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Flags</h2>
        <pre className="overflow-x-auto rounded-lg bg-gray-50 p-4 text-sm">{JSON.stringify(tenant.flags || {}, null, 2)}</pre>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Routing</h2>
        <pre className="overflow-x-auto rounded-lg bg-gray-50 p-4 text-sm">{JSON.stringify(tenant.routing || [], null, 2)}</pre>
      </section>
    </div>
  );
}
