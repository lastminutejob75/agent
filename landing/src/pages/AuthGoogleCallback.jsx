import React from "react";
import { API_URL, GOOGLE_REDIRECT_URI, OAUTH_CODE_VERIFIER_KEY } from "../lib/authConfig.js";

export default function AuthGoogleCallback() {
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

        // Redirection complète pour que le navigateur recharge la page avec le cookie
        setMessage("Connecté. Redirection…");
        window.location.replace("/app");
      } catch (e) {
        setStatus("error");
        setMessage(e?.message || "Erreur lors de la connexion Google.");
      }
    };

    run();
  }, []);

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
        <h1 className="text-2xl font-black text-white">Google</h1>
        <p className="mt-2 text-slate-400">{message}</p>
        {status === "error" && (
          <div className="mt-6">
            <a href="/login" className="text-teal-400 hover:text-teal-300 transition-colors">
              Retour au login
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
