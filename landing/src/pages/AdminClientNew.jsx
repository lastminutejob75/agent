import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function AdminClientNew() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    contact_email: "",
    timezone: "Europe/Paris",
    business_type: "",
    notes: "",
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
      };
      const created = await api.adminCreateTenant(payload);
      navigate(`/admin/tenants/${created.tenant_id}`);
    } catch (err) {
      const code = err?.data?.error_code;
      if (err.status === 409 && code === "EMAIL_ALREADY_ASSIGNED") {
        setErrorMsg("Cet email est déjà rattaché à un autre client (v1 : 1 email = 1 tenant).");
      } else {
        setErrorMsg(err.message || "Erreur lors de la création.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <Link to="/admin" style={{ color: "#374151", marginBottom: 16, display: "inline-block" }}>
        ← Admin
      </Link>
      <h1 style={{ marginTop: 8 }}>Créer un client</h1>

      {errorMsg && (
        <div
          style={{
            padding: 12,
            border: "1px solid #dc2626",
            backgroundColor: "#fef2f2",
            borderRadius: 8,
            marginTop: 16,
          }}
        >
          {errorMsg}
        </div>
      )}

      <form onSubmit={onSubmit} style={{ display: "grid", gap: 16, marginTop: 24 }}>
        <label style={{ display: "block" }}>
          Nom entreprise *
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            minLength={2}
            maxLength={120}
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }}
          />
        </label>

        <label style={{ display: "block" }}>
          Email contact *
          <input
            value={form.contact_email}
            onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            type="email"
            required
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }}
          />
        </label>

        <label style={{ display: "block" }}>
          Fuseau horaire
          <input
            value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }}
          />
        </label>

        <label style={{ display: "block" }}>
          Type de business
          <input
            value={form.business_type}
            onChange={(e) => setForm({ ...form, business_type: e.target.value })}
            placeholder="medical / artisan / …"
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }}
          />
        </label>

        <label style={{ display: "block" }}>
          Notes internes
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={4}
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }}
          />
        </label>

        <button type="submit" disabled={loading} style={{ padding: "10px 20px", cursor: loading ? "wait" : "pointer" }}>
          {loading ? "Création…" : "Créer le client"}
        </button>
      </form>
    </div>
  );
}
