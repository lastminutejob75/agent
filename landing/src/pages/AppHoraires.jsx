import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api.js";
import { deriveHorairesText, normalizeBookingRules } from "../lib/bookingUtils.js";

const C = {
  bg: "var(--bg, #0a0f1a)",
  card: "var(--card, #111827)",
  border: "var(--border, #1e293b)",
  text: "var(--text, #f1f5f9)",
  muted: "var(--muted, #64748b)",
  accent: "var(--accent, #00e5a0)",
  accentDim: "var(--accent-dim, #00b87c)",
  danger: "var(--danger, #ff6b6b)",
};

const DAY_CHOICES = [
  ["L", 0],
  ["M", 1],
  ["Me", 2],
  ["J", 3],
  ["V", 4],
  ["S", 5],
  ["D", 6],
];

export default function AppHoraires() {
  const [rules, setRules] = useState(normalizeBookingRules());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api
      .tenantGetHoraires()
      .then((res) => setRules(normalizeBookingRules(res || {})))
      .catch((e) => setError(e?.message || "Impossible de charger les horaires."))
      .finally(() => setLoading(false));
  }, []);

  const preview = useMemo(() => deriveHorairesText(rules), [rules]);

  const toggleDay = (day) => {
    setRules((current) => {
      const days = current.booking_days.includes(day)
        ? current.booking_days.filter((value) => value !== day)
        : [...current.booking_days, day].sort((a, b) => a - b);
      return { ...current, booking_days: days };
    });
  };

  const updateNumber = (key, fallback) => (event) => {
    const value = parseInt(event.target.value, 10);
    setRules((current) => ({ ...current, [key]: Number.isFinite(value) ? value : fallback }));
  };

  const save = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = normalizeBookingRules(rules);
      const res = await api.tenantUpdateHoraires(payload);
      setRules(normalizeBookingRules(res || payload));
      setSuccess(res?.horaires || deriveHorairesText(payload));
    } catch (e) {
      setError(e?.message || "Impossible d'enregistrer les horaires.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="dcard">
          <p style={{ color: C.muted }}>Chargement…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="dcard" style={{ maxWidth: 760 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>Horaires de réservation</div>
          <p style={{ color: C.muted, fontSize: 14 }}>
            Définissez quand votre assistant peut proposer des créneaux aux patients.
          </p>
        </div>

        <div style={{ display: "grid", gap: 18 }}>
          <div>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 8 }}>Jours d'ouverture</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {DAY_CHOICES.map(([label, day]) => {
                const active = rules.booking_days.includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleDay(day)}
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 10,
                      border: `1px solid ${active ? C.accent : C.border}`,
                      background: active ? C.accent : C.bg,
                      color: active ? "#04131f" : C.text,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, color: C.muted }}>Heure de début</span>
              <input
                type="number"
                min={6}
                max={22}
                value={rules.booking_start_hour}
                onChange={updateNumber("booking_start_hour", 9)}
                style={{ padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, color: C.muted }}>Heure de fin</span>
              <input
                type="number"
                min={6}
                max={22}
                value={rules.booking_end_hour}
                onChange={updateNumber("booking_end_hour", 18)}
                style={{ padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, color: C.muted }}>Durée d'un RDV</span>
              <input
                type="number"
                min={5}
                max={120}
                step={5}
                value={rules.booking_duration_minutes}
                onChange={updateNumber("booking_duration_minutes", 15)}
                style={{ padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
              />
            </label>
            <label style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, color: C.muted }}>Buffer entre RDV</span>
              <input
                type="number"
                min={0}
                max={120}
                step={5}
                value={rules.booking_buffer_minutes}
                onChange={updateNumber("booking_buffer_minutes", 0)}
                style={{ padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
              />
            </label>
          </div>

          <div
            style={{
              borderRadius: 14,
              border: `1px solid rgba(0,229,160,0.18)`,
              background: "rgba(0,229,160,0.08)",
              padding: 16,
            }}
          >
            <div style={{ fontSize: 12, color: C.accent, fontWeight: 700, marginBottom: 6 }}>Aperçu live</div>
            <div style={{ color: C.text, fontSize: 14 }}>
              Votre assistant propose des créneaux : {preview}, RDV de {rules.booking_duration_minutes} min
            </div>
          </div>

          {error && <div style={{ color: C.danger, fontSize: 14 }}>{error}</div>}
          {success && <div style={{ color: C.accent, fontSize: 14 }}>Horaires enregistrés : {success}</div>}

          <button
            type="button"
            onClick={save}
            disabled={saving}
            style={{
              padding: "12px 18px",
              borderRadius: 12,
              border: "none",
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              color: "#04131f",
              fontWeight: 800,
              cursor: "pointer",
              width: "fit-content",
            }}
          >
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
