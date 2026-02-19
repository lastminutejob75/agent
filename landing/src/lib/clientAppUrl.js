/**
 * URL de base du dashboard client (uwiapp.com).
 * En prod : VITE_UWI_APP_URL=https://uwiapp.com si client et admin sont sur des domaines différents.
 * Sinon (même origine) : laisser vide ou non défini → on utilise l’origine courante.
 */
const base = (import.meta.env.VITE_UWI_APP_URL || "").replace(/\/$/, "") || (typeof window !== "undefined" ? window.location.origin : "");

/**
 * Encode un entier en base64url (sans exposer l’id en clair dans l’URL).
 * Usage interne support / analytics uniquement.
 */
function toBase64Url(id) {
  const s = String(id);
  const b64 = typeof btoa !== "undefined" ? btoa(s) : s; // fallback pour env sans btoa (tests)
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Retourne l’URL de la page de connexion client, avec email pré-rempli si fourni.
 * Usage : "Ouvrir la page de connexion client" (Option B) — l’admin envoie vers la page login client.
 * - Email encodé avec encodeURIComponent (sécurité UX).
 * - from=admin pour analytics / traçabilité support.
 * - tenant=base64url(id) quand tenantId fourni (support : savoir quel tenant était visé, interne uniquement).
 * @param {string} [email] - Email du contact tenant (optionnel)
 * @param {number} [tenantId] - ID tenant (optionnel), ajouté en base64url pour support
 * @returns {string} URL absolue vers /login?email=...&from=admin&tenant=...
 */
export function getClientLoginUrl(email, tenantId) {
  const path = "/login";
  const url = new URL(path, base || "https://uwiapp.com");
  const params = [];
  if (email && String(email).trim()) {
    params.push(`email=${encodeURIComponent(String(email).trim())}`);
  }
  params.push("from=admin");
  if (tenantId != null && Number.isInteger(tenantId) && tenantId > 0) {
    params.push(`tenant=${toBase64Url(tenantId)}`);
  }
  url.search = params.join("&");
  return url.toString();
}

/**
 * URL du dashboard client (/app) — pour affichage ou futur impersonation.
 */
export function getClientAppUrl() {
  const b = base || (typeof window !== "undefined" ? window.location.origin : "") || "https://uwiapp.com";
  return `${b.replace(/\/$/, "")}/app`;
}

/**
 * URL d’entrée impersonation : /app/impersonate?token=...
 * Utilisée par l’admin après POST .../impersonate pour ouvrir le dashboard client.
 */
export function getClientImpersonateUrl(token) {
  const app = getClientAppUrl();
  return `${app.replace(/\/$/, "")}/impersonate?token=${encodeURIComponent(token)}`;
}
