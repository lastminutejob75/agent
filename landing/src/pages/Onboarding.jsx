import { useState } from "react";
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
        <div style={{ marginTop: 16, padding: 12, border: "1px solid #ddd" }}>
          <div><b>Tenant créé</b></div>
          <div>tenant_id: {result.tenant_id}</div>
          <div>{result.message}</div>
        </div>
      )}
    </div>
  );
}
