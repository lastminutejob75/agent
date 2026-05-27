import { T, font } from "../../theme.js";

/**
 * Badge admin light mode.
 * Si `tone` est fourni, fond pastel + texte de la couleur tone.
 * Sinon utiliser `variant` predefini : "neutral" (gris), "teal", "green", "yellow", "red", "orange".
 */
const VARIANT_TONES = {
  neutral: { bg: T.neutralLight, text: T.textSecondary, border: T.border },
  teal: { bg: T.tealLight, text: T.teal, border: "rgba(0,156,164,0.2)" },
  green: { bg: T.greenLight, text: T.green, border: "rgba(16,185,129,0.2)" },
  yellow: { bg: T.yellowLight, text: T.yellowText, border: "rgba(245,200,66,0.3)" },
  red: { bg: T.redLight, text: T.red, border: "rgba(239,68,68,0.2)" },
  orange: { bg: T.orangeLight, text: T.orange, border: "rgba(245,158,11,0.25)" },
};

export function Badge({ variant = "neutral", tone, size = "md", dot = false, children, style }) {
  const cfg = tone
    ? { bg: `${tone}15`, text: tone, border: `${tone}40` }
    : VARIANT_TONES[variant] || VARIANT_TONES.neutral;
  const sizes = {
    sm: { padding: "2px 7px", fontSize: 11, dotSize: 5 },
    md: { padding: "3px 9px", fontSize: 12, dotSize: 6 },
  };
  const s = sizes[size];
  return (
    <span
      style={{
        background: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.border}`,
        borderRadius: 6,
        fontWeight: 600,
        fontFamily: font.body,
        whiteSpace: "nowrap",
        display: "inline-flex",
        alignItems: "center",
        gap: dot ? 6 : 0,
        ...s,
        ...style,
      }}
    >
      {dot ? (
        <span
          style={{
            width: s.dotSize,
            height: s.dotSize,
            borderRadius: "50%",
            background: cfg.text,
            display: "inline-block",
          }}
        />
      ) : null}
      {children}
    </span>
  );
}

const STATUS_VARIANT = {
  active: { variant: "teal", label: "Actif" },
  inactive: { variant: "neutral", label: "Inactif" },
  suspended: { variant: "red", label: "Suspendu" },
  trial: { variant: "yellow", label: "Essai" },
  sandbox: { variant: "yellow", label: "Sandbox" },
  pending_payment: { variant: "orange", label: "Paiement en attente" },
};

export function TenantStatusBadge({ status }) {
  const cfg = STATUS_VARIANT[(status || "").toLowerCase()] || {
    variant: "neutral",
    label: status || "—",
  };
  return (
    <Badge variant={cfg.variant} dot>
      {cfg.label}
    </Badge>
  );
}

const PLAN_VARIANT = {
  free: { variant: "neutral", label: "Free" },
  starter: { variant: "teal", label: "Starter" },
  growth: { variant: "yellow", label: "Growth" },
  pro: { variant: "green", label: "Pro" },
  business: { variant: "green", label: "Business" },
};

export function PlanBadge({ plan }) {
  const cfg = PLAN_VARIANT[(plan || "").toLowerCase()] || PLAN_VARIANT.free;
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

const RESULT_VARIANT = {
  booking_confirmed: { variant: "green", label: "RDV" },
  rdv: { variant: "green", label: "RDV" },
  transferred_human: { variant: "yellow", label: "Transfert" },
  transferred: { variant: "yellow", label: "Transfert" },
  transfert: { variant: "yellow", label: "Transfert" },
  user_abandon: { variant: "red", label: "Abandon" },
  abandon: { variant: "red", label: "Abandon" },
  error: { variant: "red", label: "Erreur" },
  info: { variant: "neutral", label: "Info" },
};

export function CallResultBadge({ status }) {
  const cfg = RESULT_VARIANT[(status || "").toLowerCase()] || RESULT_VARIANT.info;
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

/** Pastille ronde colore + label, utilisee pour les compteurs et chips. */
export function CountChip({ label, value, tone }) {
  const color = tone || T.textSecondary;
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "5px 10px",
        borderRadius: 999,
        background: `${color}10`,
        border: `1px solid ${color}30`,
        color,
        fontSize: 12,
        fontWeight: 600,
        fontFamily: font.body,
      }}
    >
      <span>{label}</span>
      <span style={{ fontWeight: 700 }}>{value}</span>
    </div>
  );
}
