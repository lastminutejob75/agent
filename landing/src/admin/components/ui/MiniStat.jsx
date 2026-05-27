import { ChevronRight, Check } from "lucide-react";
import { T, radius, shadow, font } from "../../theme.js";

/**
 * Carte stat minimale (utilisée pour resumés secondaires).
 *
 * Props :
 *  - onClick   : rend la card cliquable (filtre rapide / drill-down)
 *  - active    : surligne la card pour indiquer le filtre actif
 *  - title     : tooltip natif (ex. "Cliquer pour filtrer")
 */
export function MiniStat({
  label,
  value,
  hint,
  tone = T.text,
  onClick,
  active = false,
  title,
}) {
  const isClickable = typeof onClick === "function";

  const baseBorder = active ? T.teal : T.border;
  const baseBackground = active ? T.tealLight : T.bgCard;

  const handleKeyDown = (e) => {
    if (!isClickable) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(e);
    }
  };

  return (
    <div
      role={isClickable ? "button" : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={isClickable ? onClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      title={title}
      style={{
        background: baseBackground,
        border: `1px solid ${baseBorder}`,
        borderRadius: radius.xl,
        padding: "14px 16px",
        boxShadow: shadow.card,
        minWidth: 0,
        cursor: isClickable ? "pointer" : "default",
        transition: isClickable
          ? "transform 0.15s, box-shadow 0.15s, border-color 0.15s, background 0.15s"
          : undefined,
        outline: "none",
        userSelect: "none",
        position: "relative",
      }}
      onMouseEnter={
        isClickable
          ? (e) => {
              e.currentTarget.style.boxShadow = shadow.cardHover;
              e.currentTarget.style.borderColor = active ? T.tealDark : T.borderDark;
              e.currentTarget.style.transform = "translateY(-1px)";
            }
          : undefined
      }
      onMouseLeave={
        isClickable
          ? (e) => {
              e.currentTarget.style.boxShadow = shadow.card;
              e.currentTarget.style.borderColor = baseBorder;
              e.currentTarget.style.transform = "translateY(0)";
            }
          : undefined
      }
      onFocus={
        isClickable
          ? (e) => {
              e.currentTarget.style.boxShadow = `0 0 0 3px ${T.teal}33`;
              e.currentTarget.style.borderColor = T.teal;
            }
          : undefined
      }
      onBlur={
        isClickable
          ? (e) => {
              e.currentTarget.style.boxShadow = shadow.card;
              e.currentTarget.style.borderColor = baseBorder;
            }
          : undefined
      }
    >
      {isClickable ? (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 18,
            height: 18,
            borderRadius: radius.pill,
            background: active ? T.teal : T.bgSubtle,
            color: active ? "#FFFFFF" : T.textMuted,
            transition: "background 0.15s, color 0.15s",
            pointerEvents: "none",
          }}
          aria-hidden="true"
        >
          {active ? (
            <Check size={11} strokeWidth={3} />
          ) : (
            <ChevronRight size={12} strokeWidth={2.5} />
          )}
        </div>
      ) : null}
      <div
        style={{
          fontSize: 11,
          color: T.textMuted,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          marginBottom: 8,
          fontFamily: font.body,
          paddingRight: isClickable ? 24 : 0,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: tone,
          letterSpacing: -0.5,
          lineHeight: 1.1,
          fontFamily: font.display,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
      {hint ? (
        <div
          style={{
            fontSize: 12,
            color: T.textSecondary,
            marginTop: 6,
            fontFamily: font.body,
          }}
        >
          {hint}
        </div>
      ) : null}
    </div>
  );
}

/** Skeleton shimmer pour une card pendant le chargement. */
export function MiniStatSkeleton() {
  return (
    <div
      style={{
        background: T.bgCard,
        border: `1px solid ${T.border}`,
        borderRadius: radius.xl,
        padding: "16px 18px",
        height: 110,
        boxShadow: shadow.card,
      }}
    >
      <div
        style={{
          width: 60,
          height: 11,
          borderRadius: 4,
          background: `linear-gradient(90deg, ${T.border} 0%, ${T.bgCardHover} 50%, ${T.border} 100%)`,
          backgroundSize: "200% 100%",
          marginBottom: 14,
          animation: "uwi-shimmer 1.4s linear infinite",
        }}
      />
      <div
        style={{
          width: 100,
          height: 28,
          borderRadius: 6,
          background: `linear-gradient(90deg, ${T.border} 0%, ${T.bgCardHover} 50%, ${T.border} 100%)`,
          backgroundSize: "200% 100%",
          animation: "uwi-shimmer 1.4s linear .15s infinite",
        }}
      />
    </div>
  );
}

/** Loader inline (utilise pour zones lazy-loaded type graphique). */
export function InlineLoader({ height = 160 }) {
  return (
    <div
      style={{
        height,
        borderRadius: radius.lg,
        background: `linear-gradient(90deg, ${T.bgSubtle} 0%, ${T.bgCardHover} 50%, ${T.bgSubtle} 100%)`,
        backgroundSize: "200% 100%",
        animation: "uwi-shimmer 1.4s linear infinite",
        border: `1px solid ${T.border}`,
      }}
    />
  );
}
