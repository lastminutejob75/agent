import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8", danger: "#FF6B6B" };

const inputStyle = {
  display: "block",
  width: "100%",
  marginTop: 4,
  padding: "10px 12px",
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  background: C.card,
  color: C.text,
  fontSize: 14,
};
const labelStyle = { display: "block", fontSize: 14, fontWeight: 600, color: C.muted, marginBottom: 4 };

export default function AdminTenantNew() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    contact_email: "",
    timezone: "Europe/Paris",
    business_type: "",
    notes: "",
    plan_key: "",
    billing_email: "",
    initial_status: "active",
  });
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setErrorMsg("");
    setLoading(true);
    try {
      const payload = {
        name: form.name.trim(),
        contact_email: form.contact_email.trim(),
        timezone: form.timezone || "Europe/Paris",
        business_type: form.business_type.trim() || undefined,
        notes: form.notes.trim() || undefined,
        plan_key: form.plan_key.trim() || "",
        billing_email: form.billing_email.trim() || undefined,
        initial_status: form.initial_status || "active",
      };
      const created = await adminApi.createTenant(payload);
      navigate(`/admin/tenants/${created.tenant_id}`);
    } catch (err) {
      const code = err?.data?.error_code;
      const detail = err?.data?.detail;
      if (err.status === 409 && code === "EMAIL_ALREADY_ASSIGNED") {
        setErrorMsg("Cet email est déjà rattaché à un autre client.");
      } else if (typeof detail === "string" && detail) {
        setErrorMsg(detail);
      } else if (Array.isArray(detail) && detail.length) {
        setErrorMsg(detail.map((x) => x?.msg ?? x?.loc?.join(".") ?? JSON.stringify(x)).join(" · "));
      } else {
        setErrorMsg(err.message || "Erreur lors de la création.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", maxWidth: 640 }}>
      <Link to="/admin/tenants" style={{ color: C.muted, marginBottom: 16, display: "inline-block" }}>
        ← Clients
      </Link>
      <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 8 }}>Créer un client</h1>
      <p style={{ fontSize: 14, color: C.muted, marginBottom: 24 }}>
        Après création, configurer dans la fiche client : numéro DID, calendrier, facturation Stripe. Vous pourrez ajouter un compte utilisateur (propriétaire) depuis la fiche client.
      </p>

      {errorMsg && (
        <div style={{ marginBottom: 16, padding: "12px 16px", border: `1px solid rgba(255,107,107,0.3)`, background: "rgba(255,107,107,0.1)", borderRadius: 12, color: C.danger, fontSize: 14 }}>
          {errorMsg}
        </div>
      )}

      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <label style={labelStyle}>
          Nom entreprise *
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            minLength={2}
            maxLength={120}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Email contact *
          <input
            type="email"
            value={form.contact_email}
            onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            required
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Email facturation (optionnel)
          <input
            type="email"
            value={form.billing_email}
            onChange={(e) => setForm({ ...form, billing_email: e.target.value })}
            placeholder="Si différent du contact"
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Fuseau horaire
          <input
            type="text"
            value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Type de business
          <input
            type="text"
            value={form.business_type}
            onChange={(e) => setForm({ ...form, business_type: e.target.value })}
            placeholder="medical / artisan / …"
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Plan
          <select
            value={form.plan_key}
            onChange={(e) => setForm({ ...form, plan_key: e.target.value })}
            style={inputStyle}
          >
            <option value="">Aucun</option>
            <option value="starter">Starter</option>
            <option value="pro">Pro</option>
            <option value="business">Business</option>
            <option value="custom">Custom</option>
          </select>
        </label>
        <label style={labelStyle}>
          Statut initial
          <select
            value={form.initial_status}
            onChange={(e) => setForm({ ...form, initial_status: e.target.value })}
            style={inputStyle}
          >
            <option value="active">Actif</option>
            <option value="suspended">Suspendu</option>
            <option value="sandbox">Test / Sandbox</option>
            <option value="pending_payment">En attente paiement</option>
          </select>
        </label>
        <label style={labelStyle}>
          Notes internes
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={4}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          style={{
            marginTop: 8,
            padding: "12px 20px",
            background: C.accent,
            color: C.bg,
            fontWeight: 600,
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Création…" : "Créer le client"}
        </button>
      </form>
    </div>
  );
}
