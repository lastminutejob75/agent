import React from "react";
import { Helmet } from "react-helmet-async";
import { useLocation } from "react-router-dom";
import { SEO_VERTICAL_PAGES, SEO_VERTICAL_PATHS } from "../config/seoVerticalPages.config.js";

/**
 * NOINDEX_PATTERNS + getMetaForPath : mapping route → meta, noindex pour
 * /admin, /app, /login, /checkout, /billing, /auth/, 404, etc.
 * /checkout couvre /checkout/return ; /reset-password, /auth/ déjà couverts.
 * Pas de /magic ou /invite (ajouter aux patterns si créés).
 */

const SITE_URL = (import.meta.env.VITE_SITE_URL || "https://www.uwiapp.com").replace(/\/$/, "");

function toAbsoluteUrl(pathname) {
  const p = pathname || "/";
  const clean = p.startsWith("/") ? p : `/${p}`;
  return `${SITE_URL}${clean}`;
}

const ROUTE_META = {
  "/": {
    title: "UWi — Agent d'accueil IA multicanal (téléphone, web, WhatsApp)",
    description: null, // évite doublon : meta description home = celle de index.html (fallback crawler)
  },
  "/creer-assistante": {
    title: "Créer mon assistant — UWi",
    description:
      "Configurez votre assistant vocal IA en quelques minutes. Essai gratuit 1 mois, sans carte bancaire.",
  },
  "/pricing": {
    title: "Tarifs UWi — Forfaits sans engagement pour cabinets médicaux",
    description:
      "Tarifs UWi pour cabinets médicaux libéraux : forfait ajusté à votre volume d'appels, facturation juste, sans engagement. À partir de 99 € / mois.",
  },
  "/securite": {
    title: "Sécurité & RGPD — UWi pour cabinets médicaux",
    description:
      "Sécurité, hébergement et conformité RGPD pour les cabinets médicaux : chiffrement, hébergement européen, contrat de traitement des données disponible.",
  },
  "/contact": {
    title: "Contact — UWi",
    description: "Contactez l'équipe UWi pour une démo ou un accompagnement.",
  },
  "/demo": {
    title: "UWi — Parlez à Clara, votre assistante IA",
    description:
      "Testez Clara, l'assistante vocale IA pour cabinets médicaux. Elle répond, filtre et prend les rendez-vous automatiquement.",
  },
  "/cgv": { title: "Conditions générales de vente — UWi", description: "CGV UWi Medical." },
  "/cgu": { title: "Conditions générales d'utilisation — UWi", description: "CGU UWi." },
  "/mentions-legales": {
    title: "Mentions légales — UWi",
    description: "Mentions légales et informations légales UWi.",
  },
  "/app": {
    title: "Tableau de bord — Espace Client UWi",
    description: "Pilotez votre standard UWi, vos appels, votre agenda et la configuration de votre cabinet.",
  },
  "/app/appels": {
    title: "Appels — Espace Client UWi",
    description: "Suivez les appels traités par votre assistante UWi et les actions à mener.",
  },
  "/app/agenda": {
    title: "Agenda — Espace Client UWi",
    description: "Gérez les rendez-vous pris par UWi et la connexion de votre agenda.",
  },
  "/app/patients": {
    title: "Patients — Espace Client UWi",
    description: "Consultez et confirmez les fiches patients de votre cabinet UWi.",
  },
  "/app/demandes": {
    title: "Demandes — Espace Client UWi",
    description: "Suivez les demandes patients : renouvellements, rappels et urgences.",
  },
  "/app/settings": {
    title: "Statistiques & réglages — Espace Client UWi",
    description: "Performance de votre assistant, sécurité et configuration du cabinet.",
  },
  "/app/clara": {
    title: "Clara — Centre de pilotage — UWi",
    description:
      "Pilotez Clara : urgences, horaires, absences et consignes depuis votre espace cabinet.",
  },
  "/app/patient-dashboard": {
    title: "Patients — Espace Client UWi",
    description: "Consultez et organisez les fiches patients de votre cabinet.",
  },
  "/app/profile": {
    title: "Mon cabinet — Espace Client UWi",
    description: "Centre de configuration : identité du cabinet et préférences.",
  },
  "/app/onboarding": {
    title: "Configuration — Espace Client UWi",
    description: "Complétez la mise en route de votre standard UWi pour votre cabinet.",
  },
  "/app/impersonate": {
    title: "Accès support — Espace Client UWi",
    description: "Session ouverte par l’équipe UWi pour vous accompagner.",
  },
  "/admin": {
    title: "Dashboard Admin — UWi",
    description: "Pilotez les clients, leads, appels et activations depuis le cockpit admin UWi.",
  },
  "/admin/login": {
    title: "Connexion Admin — UWi",
    description: "Accédez au cockpit d'administration UWi.",
  },
  "/admin/leads": {
    title: "Leads — Admin UWi",
    description: "Suivez les prospects, conversions et actions CRM dans l'admin UWi.",
  },
  "/admin/calls": {
    title: "Appels — Admin UWi",
    description: "Supervisez les appels et les actions métier depuis l'admin UWi.",
  },
  "/admin/quality": {
    title: "Qualité — Admin UWi",
    description: "Analysez la qualité opérationnelle des appels et parcours dans l'admin UWi.",
  },
  ...Object.fromEntries(
    SEO_VERTICAL_PATHS.map((path) => [
      path,
      { title: SEO_VERTICAL_PAGES[path].title, description: SEO_VERTICAL_PAGES[path].description },
    ])
  ),
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
  const normalized = (pathname || "").replace(/\?.*$/, "").replace(/\/+$/, "") || "/";
  const exact = ROUTE_META[normalized];
  if (exact) return { ...exact, noIndex: false };
  /** Sous-routes SPA /app absentes du dictionnaire : éviter titre 404 tant que la section existe sous AppShell */
  const appMeta = ROUTE_META["/app"];
  if (appMeta && normalized.startsWith("/app/")) {
    return {
      title: "Espace Client — UWi",
      description: appMeta.description,
      noIndex: false,
    };
  }
  const noIndex =
    NOINDEX_PATTERNS.some((re) => re.test(normalized)) ||
    (normalized !== "/" && !ROUTE_META[normalized]);
  return {
    title: "404 — Page introuvable — UWi",
    description: "Cette page n'existe pas.",
    noIndex: true,
  };
}

function matchesNoindex(pathname) {
  return NOINDEX_PATTERNS.some((re) => re.test(pathname || ""));
}

/** Description fallback home (alignée index.html). */
const DEFAULT_DESCRIPTION =
  "Répondez aux appels, qualifiez les demandes et prenez des RDV automatiquement. Handoff humain inclus.";

/**
 * Construit l’objet head pour vite-prerender-plugin (title + elements).
 * Une seule source de vérité avec getMetaForPath.
 */
export function getHeadForPrerender(pathname) {
  const path = (pathname || "").replace(/\?.*$/, "").replace(/\/+$/, "") || "/";
  const meta = getMetaForPath(path);
  const noindex = Boolean(meta?.noIndex ?? meta?.noindex ?? matchesNoindex(path));
  const title = meta?.title || "UWi";
  const url = toAbsoluteUrl(path);
  const description = meta?.description ?? (path === "/" ? DEFAULT_DESCRIPTION : null);

  const elements = new Set([
    { type: "link", props: { rel: "canonical", href: url } },
    { type: "meta", props: { name: "robots", content: noindex ? "noindex,nofollow" : "index,follow" } },
    { type: "meta", props: { property: "og:site_name", content: "UWi" } },
    { type: "meta", props: { property: "og:locale", content: "fr_FR" } },
    { type: "meta", props: { property: "og:type", content: "website" } },
    { type: "meta", props: { property: "og:url", content: url } },
    { type: "meta", props: { property: "og:title", content: title } },
    { type: "meta", props: { name: "twitter:card", content: "summary_large_image" } },
    { type: "meta", props: { name: "twitter:title", content: title } },
  ]);
  if (description) {
    elements.add({ type: "meta", props: { name: "description", content: description } });
    elements.add({ type: "meta", props: { property: "og:description", content: description } });
    elements.add({ type: "meta", props: { name: "twitter:description", content: description } });
  }

  // FAQ JSON-LD : uniquement via UwiLanding (/) et SeoVerticalPage (Helmet).
  // Ne pas ajouter ici pour éviter "FAQPage en double" (Search Console).

  return { title, lang: "fr", elements };
}

export function SeoHeadInner({ title, description, path, noindex }) {
  const url = toAbsoluteUrl(path);

  return (
    <Helmet>
      <title>{title}</title>

      {description ? <meta name="description" content={description} /> : null}

      <link rel="canonical" href={url} />

      <meta name="robots" content={noindex ? "noindex,nofollow" : "index,follow"} />

      {/* Open Graph (ordre demandé) */}
      <meta property="og:site_name" content="UWi" />
      <meta property="og:locale" content="fr_FR" />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={url} />
      <meta property="og:title" content={title} />
      {description ? <meta property="og:description" content={description} /> : null}

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      {description ? <meta name="twitter:description" content={description} /> : null}
    </Helmet>
  );
}

export default function SeoHead() {
  const { pathname } = useLocation();
  const path = pathname || "/";
  const meta = getMetaForPath(path);
  const noindex = Boolean(meta?.noindex || meta?.noIndex) || matchesNoindex(path);

  return (
    <SeoHeadInner
      title={meta?.title || "UWi"}
      description={meta?.description}
      path={path}
      noindex={noindex}
    />
  );
}
