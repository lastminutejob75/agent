import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { getClientLoginUrl } from "../../lib/clientAppUrl";

const C = {
  bg: "#0A1828",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  text: "#FFFFFF",
  muted: "#6B90A8",
  danger: "#FF6B6B",
};

export default function AdminTenantsList() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [errStatus, setErrStatus] = useState(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    adminApi
      .listTenants("?include_inactive=true")
      .then((r) => {
        const raw = r?.tenants ?? r;
        setTenants(Array.isArray(raw) ? raw : []);
      })
      .catch((e) => {
        setErr(e?.message ?? (e?.data?.detail ?? String(e)) ?? "Erreur de chargement");
        setErrStatus(e?.status);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = tenants.filter((t) => {
    const name = (t.name || "").toLowerCase();
    const email = (t.contact_email || "").toLowerCase();
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return name.includes(q) || email.includes(q) || String(t.tenant_id ?? t.id).includes(q);
  });

  if (loading) {
    return (
      <div style={{ padding: "32px", color: C.muted }}>Chargement des clients…</div>
    );
  }
  if (err) {
    return (
      <div
        style={{
          padding: "32px",
          background: "rgba(255,107,107,0.1)",
          border: `1px solid rgba(255,107,107,0.3)`,
          borderRadius: 12,
          color: C.danger,
        }}
      >
        <p>{err}</p>
        {errStatus === 401 && (
          <Link
            to="/admin/login"
            style={{ marginTop: 8, display: "inline-block", color: C.accent, fontWeight: 600 }}
          >
            Revenir à la connexion
          </Link>
        )}
      </div>
    );
  }

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <style>{`input.admin-search-input::placeholder { color: #6B90A8; }`}</style>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, margin: 0 }}>
          Clients
        </h1>
        <Link
          to="/admin/tenants/new"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "10px 20px",
            background: `linear-gradient(135deg,${C.accent},#00b87c)`,
            color: C.bg,
            fontWeight: 600,
            borderRadius: 10,
            textDecoration: "none",
          }}
        >
          Créer un client
        </Link>
      </div>

      <div style={{ marginTop: 16 }}>
        <input
          type="search"
          placeholder="Rechercher (nom, email, id…)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: "100%",
            maxWidth: 400,
            padding: "10px 14px",
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            background: C.card,
            color: C.text,
            fontSize: 14,
          }}
          className="admin-search-input"
        />
      </div>

      <div
        style={{
          marginTop: 16,
          background: C.card,
          borderRadius: 16,
          border: `1px solid ${C.border}`,
          overflow: "hidden",
        }}
      >
        {filtered.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: C.muted }}>
            {tenants.length === 0
              ? "Aucun client. Cliquez sur « Créer un client » pour commencer."
              : "Aucun résultat pour cette recherche."}
          </div>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", borderTop: `1px solid ${C.border}` }}>
            {filtered.map((t, index) => {
              const id = t.tenant_id ?? t.id;
              const name = t.name || "Sans nom";
              const status = t.status || "active";
              return (
                <li
                  key={id != null ? id : `row-${index}`}
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "16px 24px",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, color: C.text }}>{name}</span>
                    <span style={{ color: C.muted, fontSize: 13, marginLeft: 8 }}>#{id}</span>
                    {status !== "active" && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: "rgba(107,144,168,0.2)",
                          color: C.muted,
                        }}
                      >
                        {status}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    {id != null && (
                      <>
                        <Link
                          to={`/admin/tenants/${id}`}
                          style={{
                            padding: "6px 12px",
                            fontSize: 13,
                            fontWeight: 600,
                            color: C.muted,
                            background: "#0F2236",
                            border: `1px solid ${C.border}`,
                            borderRadius: 8,
                            textDecoration: "none",
                          }}
                        >
                          Détail
                        </Link>
                        {status === "active" && (
                          <Link
                            to={`/admin/tenants/${id}/dashboard`}
                            style={{
                              padding: "6px 12px",
                              fontSize: 13,
                              fontWeight: 600,
                              color: C.bg,
                              background: "linear-gradient(135deg, #00E5A0, #00b87c)",
                              border: "none",
                              borderRadius: 8,
                              textDecoration: "none",
                            }}
                          >
                            Dashboard
                          </Link>
                        )}
                        <a
                          href={getClientLoginUrl(t.contact_email || t.params?.contact_email, id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            padding: "6px 10px",
                            fontSize: 13,
                            color: C.muted,
                            textDecoration: "none",
                          }}
                          title="Ouvrir la page de connexion du client (dashboard client)"
                        >
                          <span aria-hidden>↗</span>
                        </a>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
