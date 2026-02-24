import React from "react";
import { API_URL, GOOGLE_REDIRECT_URI, OAUTH_CODE_VERIFIER_KEY } from "../lib/authConfig.js";

export function GoogleLoginButton() {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const startGoogle = () => {
    setLoading(true);
    setError(null);
    // Laisser le navigateur peindre "Redirection..." avant de lancer le fetch (évite "Event handlers blocked UI")
    const run = async () => {
      try {
        if (!API_URL) {
          setError("Backend non configuré : définir VITE_UWI_API_BASE_URL (ex. URL de l'API).");
          setLoading(false);
          return;
        }
        if (!GOOGLE_REDIRECT_URI) {
          setError("Redirect URI non configurée : définir VITE_GOOGLE_REDIRECT_URI ou ouvrir depuis le bon domaine.");
          setLoading(false);
          return;
        }
        const url = new URL(`${API_URL}/api/auth/google/start`);
        url.searchParams.set("redirect_uri", GOOGLE_REDIRECT_URI);

        const res = await fetch(url.toString(), {
          method: "GET",
          credentials: "include",
        });

        if (!res.ok) {
          const txt = await res.text().catch(() => "") || res.statusText;
          if (res.status === 503) {
            throw new Error("Google SSO désactivé côté serveur (vérifier GOOGLE_CLIENT_ID, JWT_SECRET).");
          }
          if (res.status === 0 || res.type === "opaque") {
            throw new Error("Impossible de joindre l'API (CORS ou URL backend incorrecte).");
          }
          throw new Error(`Échec démarrage Google (${res.status}). ${txt}`);
        }

        const data = await res.json();

        if (!data?.auth_url || !data?.code_verifier || !data?.state) {
          throw new Error("google/start: réponse invalide");
        }

        sessionStorage.setItem(OAUTH_CODE_VERIFIER_KEY, data.code_verifier);
        window.location.href = data.auth_url;
      } catch (e) {
        setError(e?.message || "Impossible de démarrer Google SSO");
        setLoading(false);
      }
    };
    requestAnimationFrame(() => {
      run();
    });
  };

  return (
    <div>
      <button
        type="button"
        onClick={startGoogle}
        disabled={loading}
        className="w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-2.5 font-bold text-slate-200 hover:bg-slate-700/80 hover:border-slate-500 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
      >
        {loading ? "Redirection..." : "Continuer avec Google"}
      </button>
      {error && (
        <p className="mt-2 text-sm text-red-400" role="alert">{error}</p>
      )}
    </div>
  );
}
