import React from "react";
import { API_URL, GOOGLE_REDIRECT_URI, OAUTH_CODE_VERIFIER_KEY } from "../lib/authConfig.js";

export function GoogleLoginButton() {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const startGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_URL}/api/auth/google/start`);
      url.searchParams.set("redirect_uri", GOOGLE_REDIRECT_URI);

      const res = await fetch(url.toString(), {
        method: "GET",
        credentials: "include",
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`google/start failed (${res.status}) ${txt}`);
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

  return (
    <div>
      <button
        type="button"
        onClick={startGoogle}
        disabled={loading}
        className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading ? "Redirection..." : "Continuer avec Google"}
      </button>
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
