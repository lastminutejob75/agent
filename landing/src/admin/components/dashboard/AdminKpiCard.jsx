import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { T, radius, shadow, font } from "../../theme.js";

/**
 * Carte KPI dashboard (Zone 2).
 *
 * Props :
 *  - icon : composant lucide-react (taille 18px geree ici)
 *  - label : libelle court ("Clients actifs")
 *  - value : valeur formatee a afficher
 *  - delta : { delta_pct: number|null, trend: "up"|"down"|"flat", prev: number }
 *  - tone : couleur d'accent pour l'icone (defaut teal)
 *  - onClick : navigation a l'ouverture
 */
export default function AdminKpiCard({ icon: Icon, label, value, delta, tone = T.teal, onClick, hint }) {
  const isClickable = typeof onClick === "function";

  return (
    <div
      onClick={onClick}
      style={{
        background: T.bgCard,
        border: `1px solid ${T.border}`,
        borderRadius: radius.xl,
        padding: "16px 18px",
        boxShadow: shadow.card,
        cursor: isClickable ? "pointer" : "default",
        transition: "box-shadow 0.18s, border-color 0.18s, transform 0.18s",
        minWidth: 0,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
      onMouseEnter={(e) => {
        if (!isClickable) return;
        e.currentTarget.style.boxShadow = shadow.cardHover;
        e.currentTarget.style.borderColor = T.borderDark;
      }}
      onMouseLeave={(e) => {
        if (!isClickable) return;
        e.currentTarget.style.boxShadow = shadow.card;
        e.currentTarget.style.borderColor = T.border;
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
        {Icon ? (
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: radius.md,
              background: `${tone}12`,
              color: tone,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon size={18} strokeWidth={2} />
          </div>
        ) : null}
        {delta ? <DeltaPill delta={delta} /> : null}
      </div>

      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: T.text,
            letterSpacing: -0.8,
            lineHeight: 1.1,
            fontFamily: font.display,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {value}
        </div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: T.textSecondary,
            marginTop: 6,
            fontFamily: font.body,
          }}
        >
          {label}
        </div>
        {hint ? (
          <div style={{ fontSize: 12, color: T.textMuted, marginTop: 4, fontFamily: font.body }}>
            {hint}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DeltaPill({ delta }) {
  const { delta_pct, trend } = delta || {};
  if (delta_pct === null || delta_pct === undefined) {
    return (
      <span
        style={{
          fontSize: 12,
          color: T.textMuted,
          fontFamily: font.body,
          fontWeight: 600,
        }}
      >
        —
      </span>
    );
  }
  const cfg = {
    up: { color: T.green, Icon: ArrowUpRight },
    down: { color: T.red, Icon: ArrowDownRight },
    flat: { color: T.textMuted, Icon: Minus },
  }[trend || "flat"];

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        fontSize: 12,
        fontWeight: 600,
        color: cfg.color,
        fontFamily: font.body,
      }}
    >
      <cfg.Icon size={14} strokeWidth={2.4} />
      {Math.abs(delta_pct)}%
    </span>
  );
}
