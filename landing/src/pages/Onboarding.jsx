import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function Onboarding() {
  const [companyName, setCompanyName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [calendarProvider, setCalendarProvider] = useState("none");
  const [calendarId, setCalendarId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setResult(null);
    setLoading(true);
    try {
      const payload = {
        company_name: companyName.trim(),
        email: contactEmail.trim(),
        calendar_provider: calendarProvider,
        calendar_id: calendarId.trim() || "",
      };
      const r = await api.onboardingCreate(payload);
      setResult(r);
    } catch (e) {
      setErr(e.message || "Erreur");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: "40px auto", padding: 16 }}>
      <h1>Onboarding</h1>

      <form onSubmit={submit}>
        <label>Nom entreprise</label>
        <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />

        <label>Email de contact</label>
        <input value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} type="email" required />

        <label>Agenda</label>
        <select value={calendarProvider} onChange={(e) => setCalendarProvider(e.target.value)}>
          <option value="google">Google Calendar</option>
          <option value="none">Aucun agenda (prise de message)</option>
        </select>

        {calendarProvider === "google" && (
          <>
            <label>Calendar ID (optionnel)</label>
            <input
              value={calendarId}
              onChange={(e) => setCalendarId(e.target.value)}
              placeholder="xxx@group.calendar.google.com"
            />
          </>
        )}

        <button disabled={loading} type="submit">
          {loading ? "Création..." : "Créer"}
        </button>
      </form>

      {err && <p style={{ color: "crimson" }}>{err}</p>}

      {result && (
        <div style={{ marginTop: 24, padding: 20, border: "1px solid #0d9488", borderRadius: 12, background: "#f0fdfa" }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Compte créé</div>
          <p style={{ margin: "8px 0", color: "#334155" }}>{result.message}</p>
          <p style={{ marginTop: 12, fontSize: 14, color: "#64748b" }}>
            Numéro de démo : <strong>09 39 24 05 75</strong> — démo partagée pour tester l'IA en voix.
          </p>
          <Link
            to="/login"
            style={{
              display: "inline-block",
              marginTop: 16,
              padding: "10px 20px",
              background: "#0d9488",
              color: "white",
              borderRadius: 8,
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Se connecter au dashboard →
          </Link>
        </div>
      )}
    </div>
  );
}
