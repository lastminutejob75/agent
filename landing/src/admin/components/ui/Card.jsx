import { T, radius, shadow, font } from "../../theme.js";

/**
 * Conteneur visuel unifie de l'admin (light mode).
 * Variantes :
 *  - default : panneau plein (background bgCard, ombre subtile)
 *  - subtle  : background bgSubtle (sous-bloc dans une Card)
 *  - flat    : transparent, juste une bordure
 */
export function Card({
  variant = "default",
  padding = 20,
  hoverable = false,
  style,
  children,
  ...rest
}) {
  const variants = {
    default: {
      background: T.bgCard,
      border: `1px solid ${T.border}`,
      boxShadow: shadow.card,
    },
    subtle: {
      background: T.bgSubtle,
      border: `1px solid ${T.border}`,
    },
    flat: {
      background: "transparent",
      border: `1px solid ${T.border}`,
    },
  };
  return (
    <div
      style={{
        ...variants[variant],
        borderRadius: radius.xl,
        padding,
        minWidth: 0,
        transition: hoverable ? "box-shadow 0.18s, border-color 0.18s" : undefined,
        ...style,
      }}
      onMouseEnter={
        hoverable
          ? (e) => {
              e.currentTarget.style.boxShadow = shadow.cardHover;
              e.currentTarget.style.borderColor = T.borderDark;
            }
          : undefined
      }
      onMouseLeave={
        hoverable
          ? (e) => {
              e.currentTarget.style.boxShadow = shadow.card;
              e.currentTarget.style.borderColor = T.border;
            }
          : undefined
      }
      {...rest}
    >
      {children}
    </div>
  );
}

/**
 * Card avec entete (titre, sous-titre, eyebrow optionnel, action a droite).
 */
export function PanelCard({ title, subtitle, eyebrow, action = null, padding = 20, children }) {
  return (
    <Card padding={padding}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          {eyebrow ? (
            <div
              style={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: T.teal,
                marginBottom: 6,
                fontFamily: font.body,
              }}
            >
              {eyebrow}
            </div>
          ) : null}
          <div
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: T.text,
              fontFamily: font.body,
              lineHeight: 1.2,
            }}
          >
            {title}
          </div>
          {subtitle ? (
            <div
              style={{
                fontSize: 13,
                color: T.textSecondary,
                marginTop: 4,
                fontFamily: font.body,
              }}
            >
              {subtitle}
            </div>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}
