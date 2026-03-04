import { Link } from "react-router-dom";

const C = { bg: "#0A1828", text: "#FFFFFF", muted: "#6B90A8", accent: "#00E5A0" };

export default function AdminNotFound() {
  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", textAlign: "center", paddingTop: 48 }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, marginBottom: 8 }}>Page introuvable</h1>
      <p style={{ fontSize: 14, color: C.muted, marginBottom: 16 }}>Cette page admin n'existe pas.</p>
      <Link to="/admin" style={{ color: C.accent, fontWeight: 600 }}>
        Retour au dashboard
      </Link>
    </div>
  );
}
