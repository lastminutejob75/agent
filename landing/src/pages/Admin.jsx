import { useEffect, useState } from "react";
import { api, getAdminToken, setAdminToken } from "../lib/api.js";
import { Link } from "react-router-dom";

export default function Admin() {
  const [token, setToken] = useState(getAdminToken());
  const [tenants, setTenants] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setErr("");
    setLoading(true);
    try {
      const r = await api.adminListTenants();
      setTenants(r.tenants || r || []);
    } catch (e) {
      setErr(e.message || "Erreur");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (getAdminToken()) load();
  }, []);

  return (
    <div style={{ maxWidth: 900, margin: "40px auto", padding: 16 }}>
      <h1>Admin</h1>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Admin API Token"
          style={{ flex: 1 }}
        />
        <button onClick={() => { setAdminToken(token); load(); }}>
          Charger
        </button>
      </div>

      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {loading && <p>Chargement...</p>}

      <ul>
        {tenants.map((t) => (
          <li key={t.tenant_id ?? t.id}>
            <Link to={`/admin/tenants/${t.tenant_id ?? t.id}`}>
              {t.name || "Unnamed"} (id={t.tenant_id ?? t.id})
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
