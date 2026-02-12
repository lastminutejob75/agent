import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function AdminTenant() {
  const { tenantId } = useParams();
  const [tenant, setTenant] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    setErr("");
    api
      .adminGetTenant(tenantId)
      .then(setTenant)
      .catch((e) => setErr(e.message || "Erreur"))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) return <p>Chargement...</p>;
  if (err) {
    const isAuth = (err || "").toLowerCase().includes("401") || (err || "").toLowerCase().includes("invalid");
    return (
      <div style={{ margin: "40px auto", padding: 16 }}>
        <p style={{ color: "crimson" }}>{err}</p>
        {isAuth && <Link to="/admin">Saisir le token admin</Link>}
      </div>
    );
  }
  if (!tenant) return null;

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: 16 }}>
      <Link to="/admin">← Retour</Link>
      <h1>{tenant.name} (id={tenant.tenant_id})</h1>

      <section style={{ marginTop: 24 }}>
        <h2>Params</h2>
        <pre style={{ background: "#f5f5f5", padding: 12 }}>{JSON.stringify(tenant.params || {}, null, 2)}</pre>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Flags</h2>
        <pre style={{ background: "#f5f5f5", padding: 12 }}>{JSON.stringify(tenant.flags || {}, null, 2)}</pre>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Routing</h2>
        <pre style={{ background: "#f5f5f5", padding: 12 }}>{JSON.stringify(tenant.routing || [], null, 2)}</pre>
      </section>
    </div>
  );
}
