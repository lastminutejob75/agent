import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "60vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        fontFamily: "system-ui, sans-serif",
        background: "#0D1120",
        color: "#fff",
      }}
    >
      <h1 style={{ fontSize: 72, fontWeight: 800, margin: 0, color: "rgba(0,240,181,0.9)" }}>404</h1>
      <p style={{ fontSize: 18, color: "rgba(255,255,255,0.8)", marginTop: 8 }}>
        Page introuvable
      </p>
      <Link
        to="/"
        style={{
          marginTop: 24,
          padding: "12px 24px",
          borderRadius: 12,
          background: "linear-gradient(135deg, #00F0B5, #00A3A3)",
          color: "#0D1120",
          fontWeight: 700,
          textDecoration: "none",
        }}
      >
        Retour à l'accueil
      </Link>
    </div>
  );
}
