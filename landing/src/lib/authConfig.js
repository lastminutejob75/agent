/**
 * Config auth client (login email+mdp, Google SSO).
 * VITE_UWI_API_BASE_URL = racine backend (ex. https://xxx.railway.app)
 * VITE_GOOGLE_REDIRECT_URI doit matcher backend + Google Console.
 */
const API_URL = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");
const _rawRedirect =
  import.meta.env.VITE_GOOGLE_REDIRECT_URI || (typeof window !== "undefined" ? `${window.location.origin}/auth/google/callback` : "");
const GOOGLE_REDIRECT_URI = _rawRedirect.replace(/\/$/, "");

export const getApiUrl = () => API_URL;
export const getGoogleRedirectUri = () => GOOGLE_REDIRECT_URI;

export { API_URL, GOOGLE_REDIRECT_URI };

export const OAUTH_CODE_VERIFIER_KEY = "oauth_code_verifier";
