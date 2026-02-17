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
  const [routingDid, setRoutingDid] = useState("");
  const [routingLoading, setRoutingLoading] = useState(false);
  const [routingErr, setRoutingErr] = useState("");
  const [routingSuccess, setRoutingSuccess] = useState(false);

  function loadTenant() {
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
  }

  useEffect(() => {
    loadTenant();
  }, [tenantId]);

  async function onActivateNumber(e) {
    e.preventDefault();
    const did = (routingDid || "").trim().replace(/\s/g, "");
    if (!did) {
      setRoutingErr("Saisissez un numéro (E.164 ou FR).");
      return;
    }
    setRoutingErr("");
    setRoutingSuccess(false);
    setRoutingLoading(true);
    try {
      await api.adminAddRouting({
        channel: "vocal",
        key: did.startsWith("+") ? did : did.startsWith("0") ? "+33" + did.slice(1) : "+33" + did,
        tenant_id: parseInt(tenantId, 10),
      });
      setRoutingSuccess(true);
      setRoutingDid("");
      loadTenant();
    } catch (e) {
      const code = e?.data?.error_code;
      if (e?.status === 409 && code === "TEST_NUMBER_IMMUTABLE") {
        setRoutingErr("Numéro test immuable : ce numéro est réservé à la démo.");
      } else {
        setRoutingErr(e?.message || "Erreur lors de l’activation.");
      }
    } finally {
      setRoutingLoading(false);
    }
  }

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

      {/* Bloc Raccorder un numéro */}
      <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Raccorder un numéro</h2>
        <form onSubmit={onActivateNumber} className="flex flex-wrap items-end gap-4">
          <label className="flex-1 min-w-[200px]">
            <span className="block text-sm font-medium text-gray-700 mb-1">Numéro (DID)</span>
            <input
              type="text"
              value={routingDid}
              onChange={(e) => setRoutingDid(e.target.value)}
              placeholder="+33987654321 ou 09 87 65 43 21"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="shrink-0">
            <span className="block text-sm font-medium text-gray-700 mb-1">Canal</span>
            <input type="text" value="vocal" readOnly className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm w-24" />
          </label>
          <button
            type="submit"
            disabled={routingLoading}
            className="rounded-lg bg-teal-600 text-white px-4 py-2 text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
          >
            {routingLoading ? "Activation…" : "Activer"}
          </button>
        </form>
        {routingSuccess && <p className="mt-3 text-sm text-emerald-600">Numéro activé.</p>}
        {routingErr && <p className="mt-3 text-sm text-red-600">{routingErr}</p>}
      </section>

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
