import { Link } from "react-router-dom";
import { Info } from "lucide-react";
import { T, radius, font } from "../theme.js";

export default function AdminAuditLogPage() {
  return (
    <div style={{ padding: "28px 32px", fontFamily: font.body, background: T.bgPage, minHeight: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Info size={24} color={T.teal} />
        <h1 style={{ fontSize: 26, fontWeight: 800, color: T.text, margin: 0 }}>Audit log</h1>
      </div>
      <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 560, lineHeight: 1.55, marginTop: 12 }}>
        Journal d&apos;audit multi-tenant (connexions admin, modifications sensibles, webhooks Stripe, etc.).
        Endpoint dédié côté API à prévoir ; la navigation est prête dans l&apos;UI.
      </p>
      <Link
        to="/admin"
        style={{
          display: "inline-block",
          marginTop: 18,
          fontSize: 13,
          fontWeight: 700,
          color: T.teal,
        }}
      >
        ← Retour au cockpit
      </Link>

      <div
        style={{
          marginTop: 28,
          padding: 20,
          borderRadius: radius.xl ?? 12,
          border: `1px dashed ${T.borderDark}`,
          background: T.bgSubtle,
          fontSize: 12,
          color: T.textSecondary,
          lineHeight: 1.5,
        }}
      >
        Aucune entrée : branche une route type <code>GET /api/admin/audit/events</code> puis remplace cet écran par la
        table filtrée.
      </div>
    </div>
  );
}
