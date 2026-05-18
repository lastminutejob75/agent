import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";

const C = {
  bg: "#F4F8FA",
  card: "#FFFFFF",
  border: "#DCE8EC",
  text: "#071A33",
  muted: "#667085",
  teal: "#009CA4",
  danger: "#D92D20",
};

function statusLabel(status) {
  if (status === "new") return "Nouveau";
  if (status === "contacted") return "Contacté";
  if (status === "converted") return "Converti";
  if (status === "lost") return "Perdu";
  return status || "—";
}

export default function AdminLeadDetail() {
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [lead, setLead] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const row = await adminApi.leadGet(id);
        if (!cancelled) setLead(row);
      } catch (e) {
        if (!cancelled) setError(e?.message || "Lead introuvable");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function changeStatus(nextStatus) {
    if (!lead) return;
    try {
      await adminApi.leadSetStatus(lead.id, { status: nextStatus });
      setLead((prev) => ({ ...prev, status: nextStatus }));
    } catch (e) {
      setError(e?.message || "Erreur de mise à jour");
    }
  }

  if (loading) return <div style={{ padding: 24, color: C.muted }}>Chargement…</div>;
  if (error && !lead) return <div style={{ padding: 24, color: C.danger }}>{error}</div>;
  if (!lead) return <div style={{ padding: 24, color: C.muted }}>Lead introuvable.</div>;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "20px 16px" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 14 }}>
          <Link to="/admin/leads" style={{ color: C.muted, textDecoration: "none", fontWeight: 700 }}>← Retour aux leads</Link>
          <Link
            to={`/admin/tenants/new?fromLead=${encodeURIComponent(lead.id)}`}
            style={{ borderRadius: 12, background: C.teal, color: "#fff", textDecoration: "none", padding: "8px 12px", fontWeight: 900 }}
          >
            Convertir en cabinet client →
          </Link>
        </div>

        <div style={{ border: `1px solid ${C.border}`, borderRadius: 20, background: C.card, padding: 18 }}>
          <div style={{ marginBottom: 10, fontSize: 30, lineHeight: 1.1, fontWeight: 900, letterSpacing: "-0.04em", color: C.text }}>
            {lead.cabinet_name || lead.email || `Lead ${lead.id}`}
          </div>
          <div style={{ marginBottom: 12, fontSize: 13, fontWeight: 700, color: C.muted }}>
            Statut: <strong style={{ color: C.text }}>{statusLabel(lead.status)}</strong> · Source: {lead.source || "—"}
          </div>
          <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
            <Info label="Email" value={lead.email || "—"} />
            <Info label="Téléphone" value={lead.callback_phone || "—"} />
            <Info label="Spécialité" value={lead.medical_specialty_label || lead.medical_specialty || "—"} />
            <Info label="Appels / jour" value={lead.daily_call_volume || "—"} />
            <Info label="Assistante" value={lead.assistant_name || "—"} />
            <Info label="Créé le" value={lead.created_at || "—"} />
          </div>
          <div style={{ marginTop: 10, borderRadius: 12, background: "#F8FBFC", border: `1px solid ${C.border}`, padding: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#98A2B3" }}>
              Douleur principale
            </div>
            <div style={{ marginTop: 5, fontSize: 13, lineHeight: 1.5, fontWeight: 700, color: C.text }}>
              {lead.primary_pain_point || "Non renseignée"}
            </div>
          </div>
          <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button onClick={() => changeStatus("new")} style={btn(lead.status === "new", C)}>Nouveau</button>
            <button onClick={() => changeStatus("contacted")} style={btn(lead.status === "contacted", C)}>Contacté</button>
            <button onClick={() => changeStatus("lost")} style={btn(lead.status === "lost", C)}>Perdu</button>
            <button onClick={() => changeStatus("converted")} style={btn(lead.status === "converted", C)}>Converti</button>
          </div>
          {error ? <div style={{ marginTop: 10, color: C.danger, fontWeight: 700 }}>{error}</div> : null}
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div style={{ borderRadius: 10, border: "1px solid #E4ECEF", background: "#FBFDFD", padding: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase" }}>{label}</div>
      <div style={{ marginTop: 3, fontSize: 13, fontWeight: 900, color: "#071A33" }}>{value}</div>
    </div>
  );
}

function btn(active, C) {
  return {
    borderRadius: 10,
    border: `1px solid ${active ? C.teal : C.border}`,
    background: active ? "#E7F7F7" : "#fff",
    color: active ? C.teal : C.muted,
    fontSize: 12,
    fontWeight: 900,
    padding: "8px 12px",
    cursor: "pointer",
  };
}
