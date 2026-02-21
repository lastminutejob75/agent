import { useState, useEffect } from "react";
import { api, getTenantToken } from "../lib/api.js";
import { Link, Navigate } from "react-router-dom";
import { GoogleLoginButton } from "../components/GoogleLoginButton.jsx";
import { getApiUrl } from "../lib/authConfig.js";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirection si déjà connecté via cookie (email+mdp ou Google)
  useEffect(() => {
    const apiUrl = getApiUrl();
    if (!apiUrl) return;
    fetch(`${apiUrl}/api/auth/me`, { method: "GET", credentials: "include" })
      .then((r) => { if (r.ok) window.location.replace("/app"); })
      .catch(() => {});
  }, []);

  if (getTenantToken()) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
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

  return (
    <div className="mx-auto max-w-md p-6 sm:p-8">
      <div className="rounded-xl border border-gray-200 bg-white p-6 sm:p-8 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">Connexion</h1>
        <p className="mt-1 text-sm text-gray-500">
          Connectez-vous avec votre email et mot de passe, ou avec Google.
        </p>

        {/* Connexion avec email et mot de passe */}
        <p className="mt-5 text-xs font-medium text-gray-500 uppercase tracking-wide">
          Email et mot de passe
        </p>
        <form onSubmit={handleSubmit} className="mt-2 space-y-4">
          <div>
            <label htmlFor="login-email" className="sr-only">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@exemple.com"
              required
              autoComplete="email"
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="sr-only">
              Mot de passe
            </label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mot de passe"
              required
              autoComplete="current-password"
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1.5 text-right">
              <Link to="/forgot-password" className="text-sm text-blue-600 hover:underline">
                Mot de passe oublié ?
              </Link>
            </p>
          </div>
          {err && (
            <p className="text-red-600 text-sm" role="alert">
              {err}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <span className="flex-1 border-t border-gray-200" />
          <span className="text-xs text-gray-400 uppercase tracking-wide">ou</span>
          <span className="flex-1 border-t border-gray-200" />
        </div>

        {/* Connexion avec Google */}
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
          Avec Google
        </p>
        <GoogleLoginButton />

        <p className="mt-6 text-center">
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-700 hover:underline">
            Retour à l'accueil
          </Link>
        </p>
      </div>
    </div>
  );
}
