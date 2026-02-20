import React from "react";
import { useNavigate } from "react-router-dom";
import { API_URL, GOOGLE_REDIRECT_URI, OAUTH_CODE_VERIFIER_KEY } from "../lib/authConfig.js";

export default function AuthGoogleCallback() {
  const nav = useNavigate();
  const [status, setStatus] = React.useState("loading");
  const [message, setMessage] = React.useState("Connexion en cours…");

  React.useEffect(() => {
    const run = async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code") || "";
        const state = params.get("state") || "";

        if (!code || !state) {
          throw new Error("Paramètres OAuth manquants (code/state).");
        }

        const code_verifier = sessionStorage.getItem(OAUTH_CODE_VERIFIER_KEY) || "";
        sessionStorage.removeItem(OAUTH_CODE_VERIFIER_KEY);

        if (!code_verifier) {
          throw new Error(
            "code_verifier manquant (session expirée ou page rechargée). Recommence la connexion Google."
          );
        }

        const body = {
          code,
          state,
          redirect_uri: GOOGLE_REDIRECT_URI,
          code_verifier,
        };

        const res = await fetch(`${API_URL}/api/auth/google/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });

        if (res.status === 409) {
          const txt = await res.text().catch(() => "");
          throw new Error(txt || "Ce compte est déjà lié à un autre Google.");
        }
        if (res.status === 403) {
          throw new Error("Votre email Google n'est pas vérifié.");
        }
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          throw new Error(`Google login échoué (${res.status}). ${txt}`);
        }

        const me = await fetch(`${API_URL}/api/auth/me`, {
          method: "GET",
          credentials: "include",
        });

        if (!me.ok) {
          throw new Error("Connexion réussie mais session non lisible (/me).");
        }

        setStatus("ok");
        setMessage("Connecté. Redirection…");
        nav("/app", { replace: true });
      } catch (e) {
        setStatus("error");
        setMessage(e?.message || "Erreur lors de la connexion Google.");
      }
    };

    run();
  }, [nav]);

  return (
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">Google</h1>
        <p className="mt-2 text-gray-600">{message}</p>
        {status === "error" && (
          <div className="mt-4">
            <a href="/login" className="text-blue-600 hover:underline">
              Retour au login
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
