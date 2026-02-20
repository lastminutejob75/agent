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
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">Connexion</h1>
        <p className="mt-1 text-sm text-gray-500">
          Connectez-vous avec votre compte ou avec Google.
        </p>

        <div className="mt-4">
          <GoogleLoginButton />
        </div>
        <hr className="my-4 border-gray-200" />

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@exemple.com"
            required
            autoComplete="email"
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Mot de passe"
            required
            autoComplete="current-password"
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>
        <Link to="/" className="mt-4 inline-block text-gray-600 hover:underline">
          Retour à l'accueil
        </Link>
      </div>
    </div>
  );
}
