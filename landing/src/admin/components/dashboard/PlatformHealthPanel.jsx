import { CheckCircle2, AlertTriangle, XCircle, Circle } from "lucide-react";
import { T, font, radius, formatRelative } from "../../theme.js";
import { PanelCard } from "../ui/Card.jsx";

/**
 * Zone 4 : sante de la plateforme.
 * Affiche le statut des integrations critiques + indicateurs 24h.
 */
const SERVICE_LABELS = {
  backend: "Backend API",
  vapi: "Vapi (voix)",
  twilio: "Twilio (telephonie)",
  stripe: "Stripe (paiement)",
  postmark: "Postmark (email)",
  calendar: "Google Calendar",
};

const STATUS_CFG = {
  ok: { Icon: CheckCircle2, color: T.green, label: "OK" },
  degraded: { Icon: AlertTriangle, color: T.orange, label: "Degrade" },
  down: { Icon: XCircle, color: T.red, label: "Incident" },
  not_configured: { Icon: Circle, color: T.textMuted, label: "Non configure" },
};

export default function PlatformHealthPanel({ health, loading }) {
  const services = health?.services || {};
  const indicators = health?.indicators || {};
  const generatedAt = health?.generated_at;

  const overallCfg = STATUS_CFG[health?.overall || "ok"] || STATUS_CFG.ok;

  return (
    <PanelCard
      eyebrow="Sante plateforme"
      title="Etat des services et incidents"
      subtitle={`Mis a jour ${formatRelative(generatedAt)}`}
      action={
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 12px",
            borderRadius: 999,
            background: `${overallCfg.color}15`,
            color: overallCfg.color,
            fontSize: 12,
            fontWeight: 600,
            border: `1px solid ${overallCfg.color}30`,
            fontFamily: font.body,
          }}
        >
          <overallCfg.Icon size={14} strokeWidth={2.4} />
          {overallCfg.label}
        </span>
      }
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 10,
          marginBottom: 14,
        }}
      >
        {Object.entries(SERVICE_LABELS).map(([key, label]) => {
          const status = services[key]?.status || (loading ? "ok" : "not_configured");
          const cfg = STATUS_CFG[status] || STATUS_CFG.not_configured;
          return (
            <div
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: radius.md,
                background: T.bgSubtle,
                border: `1px solid ${T.border}`,
              }}
            >
              <cfg.Icon size={16} color={cfg.color} strokeWidth={2.2} style={{ flexShrink: 0 }} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: T.text,
                    fontFamily: font.body,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </div>
                <div style={{ fontSize: 11, color: cfg.color, fontFamily: font.body }}>
                  {cfg.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 10,
          paddingTop: 14,
          borderTop: `1px solid ${T.border}`,
        }}
      >
        <Indicator
          label="Erreurs 24h"
          value={indicators.errors_24h ?? 0}
          tone={(indicators.errors_24h ?? 0) > 10 ? T.red : T.text}
        />
        <Indicator
          label="Appels echoues 24h"
          value={indicators.failed_calls_24h ?? 0}
          tone={(indicators.failed_calls_24h ?? 0) > 20 ? T.orange : T.text}
        />
        <Indicator
          label="Dernier evenement"
          value={
            indicators.last_event_at ? formatRelative(indicators.last_event_at) : "—"
          }
          tone={T.textSecondary}
        />
      </div>
    </PanelCard>
  );
}

function Indicator({ label, value, tone }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          fontWeight: 700,
          marginBottom: 4,
          fontFamily: font.body,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: tone,
          fontFamily: font.display,
          letterSpacing: -0.3,
        }}
      >
        {value}
      </div>
    </div>
  );
}
