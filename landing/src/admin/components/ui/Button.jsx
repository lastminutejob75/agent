import { T, radius, font } from "../../theme.js";

/**
 * Bouton admin light mode.
 * Variantes :
 *  - primary   : CTA accent teal (texte blanc)
 *  - secondary : bordure neutre, fond blanc, hover gris clair
 *  - ghost     : sans bordure, hover bg subtle
 *  - danger    : rouge plein
 *  - tonal     : couleur custom (passee via `tone`) avec fond pastel
 */
export function Button({
  variant = "secondary",
  tone,
  size = "md",
  iconLeft,
  iconRight,
  children,
  style,
  type = "button",
  disabled,
  ...rest
}) {
  const sizes = {
    sm: { padding: "6px 12px", fontSize: 12, gap: 6 },
    md: { padding: "8px 14px", fontSize: 13, gap: 7 },
    lg: { padding: "10px 18px", fontSize: 14, gap: 8 },
  };

  const variants = {
    primary: {
      background: T.teal,
      border: `1px solid ${T.teal}`,
      color: "#FFFFFF",
      fontWeight: 600,
    },
    secondary: {
      background: T.bgCard,
      border: `1px solid ${T.borderDark}`,
      color: T.text,
      fontWeight: 600,
    },
    ghost: {
      background: "transparent",
      border: "1px solid transparent",
      color: T.textSecondary,
      fontWeight: 600,
    },
    danger: {
      background: T.red,
      border: `1px solid ${T.red}`,
      color: "#FFFFFF",
      fontWeight: 600,
    },
    tonal: {
      background: tone ? `${tone}15` : T.tealLight,
      border: `1px solid ${tone ? `${tone}40` : T.teal}40`,
      color: tone || T.teal,
      fontWeight: 600,
    },
  };

  const hoverBg = {
    primary: T.tealDark,
    secondary: T.bgCardHover,
    ghost: T.bgSubtle,
    danger: "#DC2626",
    tonal: tone ? `${tone}25` : "rgba(0,156,164,0.15)",
  };

  return (
    <button
      type={type}
      disabled={disabled}
      style={{
        ...sizes[size],
        ...variants[variant],
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: radius.md,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        fontFamily: font.body,
        whiteSpace: "nowrap",
        transition: "background 0.15s, border-color 0.15s, color 0.15s",
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.background = hoverBg[variant];
      }}
      onMouseLeave={(e) => {
        if (!disabled) e.currentTarget.style.background = variants[variant].background;
      }}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}

/** Bouton icone-only (carre, equilibre). */
export function IconButton({ children, size = "md", ariaLabel, ...rest }) {
  const dim = { sm: 28, md: 34, lg: 40 }[size];
  return (
    <Button
      variant="secondary"
      size={size}
      aria-label={ariaLabel}
      style={{
        width: dim,
        height: dim,
        padding: 0,
      }}
      {...rest}
    >
      {children}
    </Button>
  );
}
