/**
 * Entry pré-render (Node-only, pas de Chrome).
 * Utilisé par vite-prerender-plugin : rend le HTML + head (Helmet) pour chaque route.
 */
import React from "react";
import { renderToString } from "react-dom/server";
import { StaticRouter } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";
import { getHeadForPrerender } from "./components/SeoHead.jsx";
import { SEO_VERTICAL_PATHS } from "./config/seoVerticalPages.config.js";
import App from "./App.jsx";

const ROUTES = [
  "/",
  "/creer-assistante",
  "/contact",
  "/cgv",
  "/cgu",
  "/mentions-legales",
  ...SEO_VERTICAL_PATHS,
];

export async function prerender(data) {
  const path = data?.url ?? "/";
  const html = renderToString(
    <HelmetProvider>
      <StaticRouter location={path}>
        <App />
      </StaticRouter>
    </HelmetProvider>
  );
  const head = getHeadForPrerender(path);
  return {
    html,
    head,
    links: new Set(ROUTES),
  };
}
