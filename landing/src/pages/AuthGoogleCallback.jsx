import React from "react";
import { API_URL, GOOGLE_REDIRECT_URI, OAUTH_CODE_VERIFIER_KEY } from "../lib/authConfig.js";
import { setTenantToken } from "../lib/api.js";

export default function AuthGoogleCallback() {
  const [status, setStatus] = React.useState("loading");
  const [message, setMessage] = React.useState("Connexion en cours…");

  React.useEffect(() => {
    const run = async () => {
      try {
        if (!API_URL) {
          throw new Error("Backend non configuré (VITE_UWI_API_BASE_URL).");
        }
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code") || "";
        const state = params.get("state") || "";

        if (!code || !state) {
          const err = params.get("error");
          if (err === "access_denied") {
            throw new Error("Connexion Google annulée.");
          }
          if (err) {
            throw new Error(`Google a refusé l’accès : ${err}. Vérifiez l’URI de redirection dans la Google Cloud Console.`);
          }
          throw new Error("Paramètres OAuth manquants (code/state).");
        }

        const code_verifier = sessionStorage.getItem(OAUTH_CODE_VERIFIER_KEY) || "";
        sessionStorage.removeItem(OAUTH_CODE_VERIFIER_KEY);

        // Envoyé uniquement si dispo (sur mobile / autre onglet le sessionStorage est souvent vide ; le backend utilise alors le code_verifier stocké côté serveur).
        const body = {
          code,
          state,
          redirect_uri: GOOGLE_REDIRECT_URI,
          ...(code_verifier ? { code_verifier } : {}),
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
        if (res.status === 503) {
          throw new Error("Google SSO désactivé côté serveur. Contactez l’administrateur.");
        }
        if (!res.ok) {
          const txt = await res.text().catch(() => "") || res.statusText;
          throw new Error(`Connexion Google échouée (${res.status}). ${txt}`);
        }

        const data = await res.json().catch(() => ({}));
        // Sur mobile les cookies tiers sont souvent bloqués : on stocke le token et on l'envoie en Bearer
        if (data.token) {
          setTenantToken(data.token);
        }

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
