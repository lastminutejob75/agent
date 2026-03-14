const TEXT = "#111827";
const MUTED = "#6b7280";
const BORDER = "#e5e7eb";

function getViewStatusKey(appointment) {
  if (appointment?.current) return "pending";
  if (appointment?.source === "UWI") return "ai_booked";
  if (appointment?.done) return "arrived";
  return "confirmed";
}

function getStatusConfigByKey(key) {
  if (key === "pending") return { label: "En attente", color: "#f97316", light: "#fff7ed", border: "#fdba74", dot: "#f97316", grad: null };
  if (key === "ai_booked") return { label: "Via IA", color: "#8b5cf6", light: "#f5f3ff", border: "#ddd6fe", dot: "#8b5cf6", grad: null };
  if (key === "arrived") return { label: "Arrivé", color: "#10b981", light: "#f0fdf4", border: "#6ee7b7", dot: "#10b981", grad: null };
  return { label: "Confirmé", color: "#0aaf7a", light: "#e8faf4", border: "#a7f3d0", dot: "#0dc991", grad: "linear-gradient(135deg, #0dc991, #0aaf7a)" };
}

function getTypeIcon(type) {
  const value = String(type || "").toLowerCase();
  if (value.includes("ordonnance")) return "💊";
  if (value.includes("bilan")) return "📋";
  if (value.includes("vaccin")) return "💉";
  if (value.includes("suivi")) return "🔄";
  if (value.includes("prem")) return "👋";
  if (value.includes("post")) return "🏥";
  return "🩺";
}

export default function AppAgendaTooltip({ appointment, rect }) {
  if (!appointment || !rect) return null;
  const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
  const safeTop = Math.min(Math.max(rect.top + rect.height / 2, 90), window.innerHeight - 150);
  const left = Math.min(rect.right + 14, window.innerWidth - 270);
  return (
    <div
      style={{
        position: "fixed",
        top: safeTop,
        left,
        transform: "translateY(-50%)",
        zIndex: 9999,
        background: "#fff",
        border: `1px solid ${BORDER}`,
        borderRadius: 14,
        width: 250,
        boxShadow: "0 12px 40px rgba(0,0,0,0.13)",
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      <div style={{ height: 4, background: visualStatus.grad || visualStatus.dot }} />
      <div style={{ padding: "13px 15px" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: TEXT, marginBottom: 2 }}>{appointment.patient || "Patient"}</div>
        <div style={{ fontSize: 12, color: MUTED, marginBottom: 10 }}>
          {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <span style={{ fontSize: 12, color: MUTED }}>
            {appointment.displayTime} · {appointment.duration} min
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: visualStatus.color,
              background: visualStatus.light,
              padding: "2px 9px",
              borderRadius: 999,
              border: `1px solid ${visualStatus.border}`,
            }}
          >
            {visualStatus.label}
          </span>
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: MUTED, lineHeight: 1.45 }}>
          {appointment.source === "UWI" ? "Réservé via l'assistant vocal UWI." : "Synchronisé depuis l'agenda connecté."}
        </div>
      </div>
    </div>
  );
}
