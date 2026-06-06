/**
 * Config auth client (login email+mdp, Google SSO).
 * VITE_UWI_API_BASE_URL = racine backend (ex. https://xxx.railway.app)
 * VITE_GOOGLE_REDIRECT_URI doit matcher backend + Google Console.
 *
 * Dev local : laisser VITE_UWI_API_BASE_URL vide → URLs relatives + proxy Vite (:5173 → :8000).
 */
export function getApiUrl() {
  const configured = (import.meta.env.VITE_UWI_API_BASE_URL || "").trim().replace(/\/$/, "");
  if (configured) return configured;
  if (import.meta.env.DEV) return "";
  if (typeof window !== "undefined") {
    const host = String(window.location.hostname || "").toLowerCase();
    if (host.endsWith("uwiapp.com") && host !== "api.uwiapp.com") {
      // Filet de sécurité prod: si VITE_UWI_API_BASE_URL est absente sur uwiapp.com,
      // on pointe vers l'API publique pour éviter les erreurs réseau côté dashboard.
      return "https://api.uwiapp.com";
    }
  }
  return "";
}

const API_URL = getApiUrl();
const _rawRedirect =
  import.meta.env.VITE_GOOGLE_REDIRECT_URI || (typeof window !== "undefined" ? `${window.location.origin}/auth/google/callback` : "");
const GOOGLE_REDIRECT_URI = _rawRedirect.replace(/\/$/, "");

export const getGoogleRedirectUri = () => GOOGLE_REDIRECT_URI;

export { API_URL, GOOGLE_REDIRECT_URI };

export const OAUTH_CODE_VERIFIER_KEY = "oauth_code_verifier";
