const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8" };

export default function AdminAuditLog() {
  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 8 }}>Audit log</h1>
      <p style={{ fontSize: 14, color: C.muted, marginBottom: 24 }}>Historique des actions admin.</p>
      <div style={{ padding: 24, background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, color: "#FFB347", fontSize: 14 }}>
        Bientôt disponible.
      </div>
    </div>
  );
}
