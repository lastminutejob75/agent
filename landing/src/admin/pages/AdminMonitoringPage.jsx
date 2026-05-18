import { Link } from "react-router-dom";
import { Activity, ClipboardList } from "lucide-react";
import { T, radius, font } from "../theme.js";

export default function AdminMonitoringPage() {
  return (
    <div style={{ padding: "28px 32px", fontFamily: font.body, background: T.bgPage, minHeight: "100%" }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, color: T.text, marginTop: 0 }}>Monitoring</h1>
      <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 560, lineHeight: 1.55 }}>
        Vue santé infra et alertes temps réel (à agréger côté backend). En attendant, passe par Operations et Quality
        pour le détail incidents et indicateurs récents.
      </p>
      <div
        style={{
          marginTop: 24,
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <PillCard
          icon={<Activity size={18} color={T.teal} />}
          title="Operations"
          to="/admin/operations"
          desc="Incident, retry, charge support"
        />
        <PillCard
          icon={<ClipboardList size={18} color={T.teal} />}
          title="Quality"
          to="/admin/quality"
          desc="Qualité conversationnelle"
        />
      </div>
    </div>
  );
}

function PillCard({ icon, title, desc, to }) {
  return (
    <Link
      to={to}
      style={{
        display: "block",
        textDecoration: "none",
        color: "inherit",
        border: `1px solid ${T.border}`,
        borderRadius: radius.xl ?? 12,
        padding: 18,
        background: T.bgCard,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        minWidth: 220,
        transition: "box-shadow 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span>{icon}</span>
        <span style={{ fontWeight: 700, color: T.text }}>{title}</span>
      </div>
      <div style={{ fontSize: 12, color: T.textMuted }}>{desc}</div>
    </Link>
  );
}
