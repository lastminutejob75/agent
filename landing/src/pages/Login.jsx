import { useState, useEffect, useRef } from "react";
import { api, getTenantToken } from "../lib/api.js";
import { Link, Navigate } from "react-router-dom";
import { GoogleLoginButton } from "../components/GoogleLoginButton.jsx";
import { getApiUrl } from "../lib/authConfig.js";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const userHasInteractedWithForm = useRef(false);

  // Vérification « déjà connecté » au montage (cookie). Redirection uniquement si /me répond ok.
  useEffect(() => {
    const apiUrl = getApiUrl();
    if (!apiUrl) return;
    fetch(`${apiUrl}/api/auth/me`, { method: "GET", credentials: "include" })
      .then((r) => {
        if (r.ok) window.location.replace("/app");
      })
      .catch(() => {});
  }, []);

  if (getTenantToken()) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    // Ne pas accepter de soumission tant que l'utilisateur n'a pas interagi avec le formulaire
    // (évite la connexion automatique déclenchée par l'autofill du navigateur)
    if (!userHasInteractedWithForm.current) {
      return;
    }
    setErr("");
    setLoading(true);
    try {
      await api.authLogin(email.trim(), password);
      window.location.replace("/app");
    } catch (e) {
      setErr(e.message || "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  }

  function markFormInteracted() {
    userHasInteractedWithForm.current = true;
  }

  const inputClass =
    "w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-2.5 text-white placeholder-slate-500 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-colors";
  const btnPrimaryClass =
    "w-full rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black px-4 py-2.5 hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 transition-all";

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
        <h1 className="text-2xl font-black text-white">Connexion</h1>
        <p className="mt-1 text-sm text-slate-400">
          Connectez-vous avec votre email et mot de passe, ou avec Google.
        </p>

        <p className="mt-6 text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Email et mot de passe
        </p>
        <form onSubmit={handleSubmit} className="mt-2 space-y-4">
          <div>
            <label htmlFor="login-email" className="sr-only">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onFocus={markFormInteracted}
              placeholder="email@exemple.com"
              required
              autoComplete="email"
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="login-password" className="sr-only">Mot de passe</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={markFormInteracted}
              placeholder="Mot de passe"
              required
              autoComplete="current-password"
              className={inputClass}
            />
            <p className="mt-1.5 text-right">
              <Link to="/forgot-password" className="text-sm text-teal-400 hover:text-teal-300 transition-colors">
                Mot de passe oublié ?
              </Link>
            </p>
          </div>
          {err && (
            <p className="text-red-400 text-sm" role="alert">{err}</p>
          )}
          <button type="submit" disabled={loading} onClick={markFormInteracted} className={btnPrimaryClass}>
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <span className="flex-1 border-t border-slate-700" />
          <span className="text-xs text-slate-500 uppercase tracking-wide">ou</span>
          <span className="flex-1 border-t border-slate-700" />
        </div>

        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Avec Google
        </p>
        <GoogleLoginButton />

        <p className="mt-6 text-center">
          <Link to="/" className="text-sm text-slate-400 hover:text-teal-400 transition-colors">
            Retour à l'accueil
          </Link>
        </p>
      </div>
    </div>
  );
}
