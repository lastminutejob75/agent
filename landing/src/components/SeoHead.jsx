/**
 * SEO par route : title, description, canonical, noindex.
 * Utilise react-helmet-async. Les métadonnées par path sont définies ici.
 */
import { useLocation } from "react-router-dom";
import { Helmet } from "react-helmet-async";

const BASE = "https://www.uwiapp.com";

const ROUTE_META = {
  "/": {
    title: "UWi — Agent d'accueil IA multicanal (téléphone, web, WhatsApp)",
    description:
      "Répondez aux appels, qualifiez les demandes et prenez des RDV automatiquement. Agent vocal IA pour cabinets et PME. Handoff humain inclus. Essai gratuit.",
    canonical: "/",
  },
  "/creer-assistante": {
    title: "Créer mon assistant — UWi",
    description: "Configurez votre assistant vocal IA en quelques minutes. Essai gratuit 1 mois, sans carte bancaire.",
    canonical: "/creer-assistante",
  },
  "/contact": {
    title: "Contact — UWi",
    description: "Contactez l'équipe UWi pour une démo ou un accompagnement.",
    canonical: "/contact",
  },
  "/cgv": {
    title: "Conditions générales de vente — UWi",
    description: "CGV UWi Medical.",
    canonical: "/cgv",
  },
  "/cgu": {
    title: "Conditions générales d'utilisation — UWi",
    description: "CGU UWi.",
    canonical: "/cgu",
  },
  "/mentions-legales": {
    title: "Mentions légales — UWi",
    description: "Mentions légales et informations légales UWi.",
    canonical: "/mentions-legales",
  },
};

/** Routes à ne pas indexer (noindex, nofollow) */
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
    (normalized !== "/" && !ROUTE_META[normalized]); // chemins inconnus = noindex (type 404)
  return {
    title: "404 — Page introuvable — UWi",
    description: "Cette page n'existe pas.",
    canonical: "/",
    noIndex: true,
  };
}

export default function SeoHead() {
  const { pathname } = useLocation();
  const meta = getMetaForPath(pathname);
  const canonicalUrl = `${BASE}${meta.canonical === "/" ? "" : meta.canonical}`;

  return (
    <Helmet>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={canonicalUrl} />
      {meta.noIndex && <meta name="robots" content="noindex, nofollow" />}
      <meta property="og:title" content={meta.title} />
      <meta property="og:description" content={meta.description} />
      <meta property="og:url" content={canonicalUrl} />
    </Helmet>
  );
}
