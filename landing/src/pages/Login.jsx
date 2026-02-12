import { useState } from "react";
import { api, getTenantToken } from "../lib/api.js";
import { Link, Navigate } from "react-router-dom";

export default function Login() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  if (getTenantToken()) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const r = await api.authRequestLink(email.trim());
      setSent(true);
      if (r.debug_login_url) {
        setErr("Mode debug: lien = " + r.debug_login_url);
      }
    } catch (e) {
      setErr(e.message || "Erreur");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-md p-8">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-bold text-gray-900">Vérifiez votre email</h1>
          <p className="mt-2 text-gray-600">
            Si un compte existe pour cet email, vous recevrez un lien de connexion.
          </p>
          {err && <p className="mt-2 text-amber-600 text-sm">{err}</p>}
          <Link to="/login" className="mt-4 inline-block text-blue-600 hover:underline">
            Nouvelle demande
          </Link>
          <Link to="/" className="mt-2 ml-4 inline-block text-gray-600 hover:underline">
            Retour à l'accueil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">Connexion</h1>
        <p className="mt-1 text-sm text-gray-500">
          Si un compte existe pour cet email, vous recevrez un lien de connexion.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@exemple.com"
            required
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Envoi..." : "Envoyer le lien"}
          </button>
        </form>
        <Link to="/" className="mt-4 inline-block text-gray-600 hover:underline">
          Retour à l'accueil
        </Link>
      </div>
    </div>
  );
}
