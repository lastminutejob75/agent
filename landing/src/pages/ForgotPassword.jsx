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

  const inputClass =
    "w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-2.5 text-white placeholder-slate-500 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-colors";
  const btnPrimaryClass =
    "w-full rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black px-4 py-2.5 hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 transition-all";

  if (sent) {
    return (
      <div className="flex justify-center">
        <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
          <h1 className="text-2xl font-black text-white">Email envoyé</h1>
          <p className="mt-2 text-slate-400">
            Si un compte existe pour cet email, vous recevrez un lien pour réinitialiser votre mot de passe.
          </p>
          <Link to="/login" className="mt-4 inline-block text-teal-400 hover:text-teal-300 transition-colors">
            Retour à la connexion
          </Link>
          <Link to="/" className="mt-2 ml-4 inline-block text-slate-400 hover:text-teal-400 transition-colors">
            Accueil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
        <h1 className="text-2xl font-black text-white">Mot de passe oublié</h1>
        <p className="mt-1 text-sm text-slate-400">
          Saisissez votre email pour recevoir un lien de réinitialisation.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@exemple.com"
            required
            autoComplete="email"
            className={inputClass}
          />
          {err && <p className="text-red-400 text-sm">{err}</p>}
          <button type="submit" disabled={loading} className={btnPrimaryClass}>
            {loading ? "Envoi..." : "Envoyer le lien"}
          </button>
        </form>
        <Link to="/login" className="mt-4 inline-block text-slate-400 hover:text-teal-400 transition-colors">
          Retour à la connexion
        </Link>
      </div>
    </div>
  );
}
