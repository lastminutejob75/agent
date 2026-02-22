import { useState, useEffect } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const MIN_PASSWORD_LENGTH = 10;

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const emailFromUrl = searchParams.get("email") || "";
  const tokenFromUrl = searchParams.get("token") || "";
  const [email, setEmail] = useState(emailFromUrl);
  const [token, setToken] = useState(tokenFromUrl);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (emailFromUrl) setEmail(emailFromUrl);
    if (tokenFromUrl) setToken(tokenFromUrl);
  }, [emailFromUrl, tokenFromUrl]);

  // Ne pas laisser token/email dans l’URL (historique, screenshots)
  useEffect(() => {
    if (tokenFromUrl || emailFromUrl) {
      window.history.replaceState({}, "", "/reset-password");
    }
  }, [tokenFromUrl, emailFromUrl]);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    if (password !== confirm) {
      setErr("Les deux mots de passe ne correspondent pas.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setErr(`Le mot de passe doit contenir au moins ${MIN_PASSWORD_LENGTH} caractères.`);
      return;
    }
    if (!email.trim() || !token.trim()) {
      setErr("Lien invalide. Utilisez le lien reçu par email.");
      return;
    }
    setLoading(true);
    try {
      await api.authResetPassword(email.trim(), token.trim(), password);
      navigate("/app", { replace: true });
    } catch (e) {
      setErr(e.message || "Lien invalide ou expiré.");
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-2.5 text-white placeholder-slate-500 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-colors";
  const btnPrimaryClass =
    "w-full rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black px-4 py-2.5 hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 transition-all";

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
        <h1 className="text-2xl font-black text-white">Nouveau mot de passe</h1>
        <p className="mt-1 text-sm text-slate-400">
          Choisissez un mot de passe d’au moins {MIN_PASSWORD_LENGTH} caractères.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {!emailFromUrl && (
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@exemple.com"
              required
              autoComplete="email"
              className={inputClass}
            />
          )}
          {!tokenFromUrl && (
            <input
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Token du lien reçu par email"
              className={inputClass}
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Nouveau mot de passe"
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            className={inputClass}
          />
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Confirmer le mot de passe"
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            className={inputClass}
          />
          {err && <p className="text-red-400 text-sm">{err}</p>}
          <button type="submit" disabled={loading} className={btnPrimaryClass}>
            {loading ? "Enregistrement..." : "Enregistrer le mot de passe"}
          </button>
        </form>
        <Link to="/login" className="mt-4 inline-block text-slate-400 hover:text-teal-400 transition-colors">
          Retour à la connexion
        </Link>
      </div>
    </div>
  );
}
