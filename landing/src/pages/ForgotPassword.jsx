import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await api.authForgotPassword(email.trim());
      setSent(true);
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
          <h1 className="text-xl font-bold text-gray-900">Email envoyé</h1>
          <p className="mt-2 text-gray-600">
            Si un compte existe pour cet email, vous recevrez un lien pour réinitialiser votre mot de passe.
          </p>
          <Link to="/login" className="mt-4 inline-block text-blue-600 hover:underline">
            Retour à la connexion
          </Link>
          <Link to="/" className="mt-2 ml-4 inline-block text-gray-600 hover:underline">
            Accueil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md p-8">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">Mot de passe oublié</h1>
        <p className="mt-1 text-sm text-gray-500">
          Saisissez votre email pour recevoir un lien de réinitialisation.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@exemple.com"
            required
            autoComplete="email"
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
        <Link to="/login" className="mt-4 inline-block text-gray-600 hover:underline">
          Retour à la connexion
        </Link>
      </div>
    </div>
  );
}
