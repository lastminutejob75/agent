import { T } from "../../theme.js";

export const CREATION_STEP_LABELS = [
  "Identité cabinet",
  "Abonnement",
  "Canaux activés",
  "Assistant Vapi",
  "Agenda",
  "Règles d’accueil",
  "Accès client",
  "Vérification finale",
];

export default function CreateTenantStepper({ step, onStep }) {
  return (
    <div
      style={{
        borderRadius: 24,
        border: `1px solid ${T.border}`,
        background: T.bgCard,
        padding: 16,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 800, color: T.text, marginBottom: 12 }}>Étapes de création</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {CREATION_STEP_LABELS.map((label, idx) => {
          const done = idx < step;
          const active = idx === step;
          return (
            <button
              key={label}
              type="button"
              onClick={() => onStep(idx)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 14,
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "inherit",
                background: active ? T.tealLight : "transparent",
                transition: "background 0.15s ease",
              }}
            >
              <span
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 10,
                  display: "grid",
                  placeItems: "center",
                  fontSize: 11,
                  fontWeight: 900,
                  background: done ? T.green : active ? T.teal : "#F2F4F7",
                  color: done || active ? "#fff" : T.textMuted,
                }}
              >
                {done ? "✓" : idx + 1}
              </span>
              <span style={{ fontSize: 13, fontWeight: 800, color: T.text }}>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
