/**
 * Tokens design admin UWI — light mode (CdC v1.0).
 *
 * - `T` : palette de couleurs unique pour tout l'admin
 * - `radius`, `shadow`, `font` : tokens d'apparence
 * - `keyframes` : animations CSS globales (a injecter une fois par page)
 * - helpers de format : formatTime, formatDateShort, formatRelative
 *
 * Aligne sur le design du dashboard client (COLORS dans
 * src/components/layout/layout.constants.js) pour une coherence visuelle.
 */

export const T = {
  // Surfaces
  bgPage: "#F5F9FA",
  bgCard: "#FFFFFF",
  bgCardHover: "#F0F5F6",
  bgSubtle: "#F8FAFC",

  // Bordures
  border: "#E2E8F0",
  borderDark: "#CBD5E1",

  // Texte
  text: "#0A1628",
  textSecondary: "#475569",
  textMuted: "#94A3B8",

  // Accent principal
  teal: "#009CA4",
  tealDark: "#007A82",
  tealLight: "#E6F7F8",

  // Etats
  green: "#10B981",
  greenLight: "#ECFDF5",
  yellow: "#F5C842",
  yellowLight: "#FEF9E7",
  yellowText: "#92400E",
  red: "#EF4444",
  redLight: "#FEF2F2",
  orange: "#F59E0B",
  orangeLight: "#FFF7ED",

  // Neutres pour badges inactifs
  neutralLight: "#F1F5F9",
};

export const radius = {
  sm: 6,
  md: 8,
  lg: 10,
  xl: 12,
  xxl: 14,
  pill: 999,
};

export const shadow = {
  card: "0 1px 3px rgba(0,0,0,0.04)",
  cardHover: "0 4px 12px rgba(15,23,42,0.06)",
  raised: "0 8px 24px rgba(15,23,42,0.08)",
};

export const font = {
  display: "'Syne', system-ui, sans-serif",
  body: "'DM Sans', system-ui, sans-serif",
};

/** A injecter une seule fois par page (ex: <style>{keyframes}</style>). */
export const keyframes = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700;800&family=DM+Sans:wght@400;500;600;700;800&display=swap');
@keyframes uwi-fadein  { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes uwi-pulse   { 0%,100%{opacity:1} 50%{opacity:.4} }
@keyframes uwi-shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
@keyframes uwi-ping {
  0% { transform: scale(.6); opacity: .8 }
  80% { transform: scale(2); opacity: 0 }
  100% { transform: scale(2.5); opacity: 0 }
}
`;

/** Format heure courte fr-FR, ex: "14:32". */
export function formatTime(date) {
  if (!date) return "—";
  return new Date(date).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format date courte fr-FR, ex: "07/05". */
export function formatDateShort(date) {
  if (!date) return "—";
  return new Date(date).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
  });
}

/** Format relatif simple : "il y a 5 min", "il y a 2h", "hier", "07/05". */
export function formatRelative(date) {
  if (!date) return "—";
  const d = new Date(date);
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "à l'instant";
  if (diffMin < 60) return `il y a ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `il y a ${diffH}h`;
  const diffD = Math.round(diffH / 24);
  if (diffD === 1) return "hier";
  if (diffD < 7) return `il y a ${diffD} j`;
  return formatDateShort(date);
}

/** Format nombre avec separateur fr (ex: 1234 -> "1 234"). */
export function formatNumber(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("fr-FR");
}

/** Format euro entier (ex: 99 -> "99 €"). */
export function formatEuro(n) {
  if (n === null || n === undefined) return "—";
  return `${formatNumber(Math.round(n))} €`;
}

/** Format dollar avec 2 decimales. */
export function formatUsd(n) {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toFixed(2)}`;
}
