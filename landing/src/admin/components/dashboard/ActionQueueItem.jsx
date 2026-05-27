import {
  AlertCircle,
  AlertTriangle,
  Info,
  UserPlus,
  Phone,
  CreditCard,
  Activity,
  TrendingUp,
  Clock,
  ChevronRight,
} from "lucide-react";
import { T, radius, font, formatRelative } from "../../theme.js";

/**
 * Item de la file d'actions Zone 3.
 *
 * @param {object} item
 *  - priority : "critical" | "warning" | "info"
 *  - type : "lead" | "activation" | "billing" | "error" | "quota" | "follow_up"
 *  - title : libelle principal (nom cabinet ou lead)
 *  - reason : raison courte ("Quota a 92%", "Past due 5j")
 *  - timestamp : ISO date
 *  - actions : [{ label, onClick, primary?: boolean }]
 *  - onOpen : clic global (ouvre la fiche)
 */

const PRIORITY_CFG = {
  critical: { color: T.red, Icon: AlertCircle, label: "Critique" },
  warning: { color: T.orange, Icon: AlertTriangle, label: "Attention" },
  info: { color: T.teal, Icon: Info, label: "Info" },
};

const TYPE_CFG = {
  lead: { Icon: UserPlus, label: "Lead" },
  activation: { Icon: Activity, label: "Activation" },
  billing: { Icon: CreditCard, label: "Billing" },
  error: { Icon: AlertCircle, label: "Erreur" },
  quota: { Icon: TrendingUp, label: "Quota" },
  follow_up: { Icon: Clock, label: "Relance" },
  call: { Icon: Phone, label: "Appel" },
};

export default function ActionQueueItem({ item, onOpen }) {
  const priority = PRIORITY_CFG[item.priority] || PRIORITY_CFG.info;
  const type = TYPE_CFG[item.type] || TYPE_CFG.lead;
  const PriorityIcon = priority.Icon;
  const TypeIcon = type.Icon;

  const handleRowClick = () => onOpen?.(item);

  return (
    <div
      onClick={handleRowClick}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        gap: 14,
        alignItems: "center",
        padding: "12px 14px",
        borderRadius: radius.lg,
        background: T.bgCard,
        border: `1px solid ${T.border}`,
        cursor: "pointer",
        transition: "background 0.15s, border-color 0.15s",
        fontFamily: font.body,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = T.bgCardHover;
        e.currentTarget.style.borderColor = T.borderDark;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = T.bgCard;
        e.currentTarget.style.borderColor = T.border;
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: radius.md,
          background: `${priority.color}12`,
          color: priority.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <PriorityIcon size={18} strokeWidth={2.2} />
      </div>

      <div style={{ minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 4,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "2px 8px",
              borderRadius: 6,
              background: T.neutralLight,
              color: T.textSecondary,
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            <TypeIcon size={11} strokeWidth={2.4} />
            {type.label}
          </span>
          <span
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: T.text,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              minWidth: 0,
            }}
          >
            {item.title}
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 13,
              color: priority.color,
              fontWeight: 500,
            }}
          >
            {item.reason}
          </span>
          {item.timestamp ? (
            <span
              style={{
                fontSize: 12,
                color: T.textMuted,
              }}
            >
              · {formatRelative(item.timestamp)}
            </span>
          ) : null}
        </div>
        {item.actions?.length ? (
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {item.actions.map((a) => (
              <button
                key={a.label}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  a.onClick?.(item);
                }}
                style={{
                  padding: "4px 10px",
                  fontSize: 12,
                  fontWeight: 600,
                  borderRadius: 6,
                  background: a.primary ? T.tealLight : "transparent",
                  border: `1px solid ${a.primary ? T.teal : T.border}`,
                  color: a.primary ? T.teal : T.textSecondary,
                  cursor: "pointer",
                  fontFamily: font.body,
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <ChevronRight size={18} color={T.textMuted} style={{ flexShrink: 0 }} />
    </div>
  );
}

/** Helper export : config priorite/type pour utilisation externe (file d'actions agregee). */
export { PRIORITY_CFG, TYPE_CFG };
