import { Link } from "react-router-dom";

import { T } from "../theme.js";
const C = { bg: T.bgPage, text: T.text, muted: T.textMuted, accent: T.teal };

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
