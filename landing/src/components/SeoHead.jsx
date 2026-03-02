/**
 * SEO par route : title, description, canonical, noindex, OG, Twitter.
 * Base URL via VITE_SITE_URL (ex. .env.production / Vercel).
 */
import { useLocation } from "react-router-dom";
import { Helmet } from "react-helmet-async";

const SITE_URL = (import.meta.env.VITE_SITE_URL || "https://www.uwiapp.com").replace(/\/$/, "");

function toAbsoluteUrl(pathname) {
  const path = pathname && pathname !== "/" ? pathname : "";
  return path ? `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}` : SITE_URL + "/";
}

const ROUTE_META = {
  "/": {
    title: "UWi — Agent d'accueil IA multicanal (téléphone, web, WhatsApp)",
    description:
      "Répondez aux appels, qualifiez les demandes et prenez des RDV automatiquement. Agent vocal IA pour cabinets et PME. Handoff humain inclus. Essai gratuit.",
  },
  "/creer-assistante": {
    title: "Créer mon assistant — UWi",
    description: "Configurez votre assistant vocal IA en quelques minutes. Essai gratuit 1 mois, sans carte bancaire.",
  },
  "/contact": {
    title: "Contact — UWi",
    description: "Contactez l'équipe UWi pour une démo ou un accompagnement.",
  },
  "/cgv": {
    title: "Conditions générales de vente — UWi",
    description: "CGV UWi Medical.",
  },
  "/cgu": {
    title: "Conditions générales d'utilisation — UWi",
    description: "CGU UWi.",
  },
  "/mentions-legales": {
    title: "Mentions légales — UWi",
    description: "Mentions légales et informations légales UWi.",
  },
};

const NOINDEX_PATTERNS = [
  /^\/login/,
  /^\/forgot-password/,
  /^\/reset-password/,
  /^\/auth\//,
  /^\/app/,
  /^\/admin/,
  /^\/checkout/,
  /^\/billing/,
  /^\/onboarding/,
  /^\/essai-gratuit/,
  /^\/decouverte/,
];

function getMetaForPath(pathname) {
  const normalized = pathname.replace(/\?.*$/, "") || "/";
  const exact = ROUTE_META[normalized];
  if (exact) return { ...exact, noIndex: false };
  const noIndex =
    NOINDEX_PATTERNS.some((re) => re.test(normalized)) ||
    (normalized !== "/" && !ROUTE_META[normalized]);
  return {
    title: "404 — Page introuvable — UWi",
    description: "Cette page n'existe pas.",
    noIndex: true,
  };
}

export default function SeoHead() {
  const { pathname } = useLocation();
  const meta = getMetaForPath(pathname);
  const url = toAbsoluteUrl(pathname.replace(/\?.*$/, "") || "/");

  return (
    <Helmet>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={url} />
      <meta name="robots" content={meta.noIndex ? "noindex,nofollow" : "index,follow"} />

      <meta property="og:site_name" content="UWi" />
      <meta property="og:locale" content="fr_FR" />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={url} />
      <meta property="og:title" content={meta.title} />
      <meta property="og:description" content={meta.description} />

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={meta.title} />
      <meta name="twitter:description" content={meta.description} />
    </Helmet>
  );
}
