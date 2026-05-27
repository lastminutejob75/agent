import {
  Phone,
  UserPlus,
  Building2,
  CreditCard,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { T, radius, font, formatRelative } from "../../theme.js";

const ICON_MAP = {
  call: { Icon: Phone, color: T.teal },
  lead: { Icon: UserPlus, color: T.green },
  tenant_created: { Icon: Building2, color: T.teal },
  billing: { Icon: CreditCard, color: T.orange },
  error: { Icon: AlertCircle, color: T.red },
};

/**
 * Item du flux d'activite recent (Zone 5).
 *
 * @param {object} item
 *  - type : "call" | "lead" | "tenant_created" | "billing" | "error"
 *  - text : description courte ("RDV pris pour Cabinet Dr Martin")
 *  - timestamp : ISO date
 *  - onClick : navigation
 */
export default function ActivityFeedItem({ item, onClick }) {
  const cfg = ICON_MAP[item.type] || ICON_MAP.call;
  const Icon = cfg.Icon;

  return (
    <div
      onClick={() => onClick?.(item)}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto",
        gap: 12,
        alignItems: "center",
        padding: "10px 12px",
        borderRadius: radius.md,
        cursor: onClick ? "pointer" : "default",
        transition: "background 0.15s",
        fontFamily: font.body,
      }}
      onMouseEnter={(e) => {
        if (onClick) e.currentTarget.style.background = T.bgSubtle;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: radius.md,
          background: `${cfg.color}12`,
          color: cfg.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Icon size={14} strokeWidth={2.4} />
      </div>
      <div
        style={{
          fontSize: 13,
          color: T.text,
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {item.text}
      </div>
      <div style={{ fontSize: 12, color: T.textMuted, whiteSpace: "nowrap" }}>
        {formatRelative(item.timestamp)}
      </div>
      {onClick ? <ChevronRight size={14} color={T.textMuted} /> : <span />}
    </div>
  );
}
