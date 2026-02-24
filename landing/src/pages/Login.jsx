import { useState, useEffect, useRef } from "react";
import { api } from "../lib/api.js";
import { Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { GoogleLoginButton } from "../components/GoogleLoginButton.jsx";
import { getApiUrl } from "../lib/authConfig.js";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendCheck, setBackendCheck] = useState("idle"); // idle | checking | ok | fail
  const [alreadyLoggedIn, setAlreadyLoggedIn] = useState(false); // session valide côté serveur
  const [showPassword, setShowPassword] = useState(false);
  const userHasInteractedWithForm = useRef(false);

  const apiUrl = getApiUrl();

  // Vérification « déjà connecté » au montage : on affiche un bandeau + lien au lieu de rediriger automatiquement.
  useEffect(() => {
    if (!apiUrl) return;
    fetch(`${apiUrl}/api/auth/me`, { method: "GET", credentials: "include" })
      .then((r) => {
        if (r.ok) setAlreadyLoggedIn(true);
      })
      .catch(() => {});
  }, [apiUrl]);

  // Test /health au chargement pour afficher si le backend est joignable (diagnostic CORS / URL).
  useEffect(() => {
    if (!apiUrl) {
      setBackendCheck("idle");
      return;
    }
    setBackendCheck("checking");
    fetch(`${apiUrl}/health`, { method: "GET", credentials: "include" })
      .then((r) => setBackendCheck(r.ok ? "ok" : "fail"))
      .catch(() => setBackendCheck("fail"));
  }, [apiUrl]);

  // Ne pas rediriger sur le seul token localStorage (il peut être expiré) → seule la réponse /api/auth/me (cookie valide) déclenche la redirection.

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
        {alreadyLoggedIn && (
          <div className="mb-4 rounded-xl bg-green-500/20 border border-green-500/50 text-green-200 text-sm p-3 flex items-center justify-between gap-3">
            <span>Vous êtes déjà connecté.</span>
            <Link to="/app" className="font-semibold text-green-300 hover:text-green-100 underline shrink-0">Accéder au dashboard →</Link>
          </div>
        )}
        {!apiUrl && (
          <p className="mb-4 rounded-xl bg-amber-500/20 border border-amber-500/50 text-amber-200 text-sm p-3" role="alert">
            Backend non configuré : définir <code className="font-mono text-xs">VITE_UWI_API_BASE_URL</code> (ex. URL de l'API), puis reconstruire le front.
          </p>
        )}
        {apiUrl && (
          <div className="mb-4 rounded-xl border border-slate-600 bg-slate-800/80 p-3 text-xs text-slate-300">
            <p className="font-semibold text-slate-200 mb-1">Diagnostic</p>
            <p>Origine : <code className="font-mono text-cyan-300 break-all">{typeof window !== "undefined" ? window.location.origin : ""}</code></p>
            <p className="mt-1">Backend : <a href={`${apiUrl}/health`} target="_blank" rel="noopener noreferrer" className="font-mono text-cyan-300 underline break-all">{apiUrl}</a></p>
            <p className="mt-1">
              Test <code className="font-mono">/health</code> :{" "}
              {backendCheck === "checking" && <span className="text-slate-400">vérification…</span>}
              {backendCheck === "ok" && <span className="text-green-400 font-medium">OK</span>}
              {backendCheck === "fail" && (
                <span className="text-red-400">
                  Échec. Pour <strong>www.uwiapp.com</strong> le backend autorise cette origine par défaut → soit <code>CORS_ORIGINS</code> sur Railway écrase le défaut (le définir à <code>https://www.uwiapp.com,https://uwiapp.com</code>), soit l’URL backend ci-dessus est incorrecte ou le service ne répond pas. Ouvrez le lien Backend ci-dessus pour tester <code>/health</code> dans un onglet.
                </span>
              )}
            </p>
          </div>
        )}
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
          <div className="relative">
            <label htmlFor="login-password" className="sr-only">Mot de passe</label>
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={markFormInteracted}
              placeholder="Mot de passe"
              required
              autoComplete="current-password"
              className={`${inputClass} pr-11`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 focus:outline-none focus:ring-2 focus:ring-teal-500/50"
              title={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
              aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
            <p className="mt-1.5 text-right">
              <Link to="/forgot-password" className="text-sm text-teal-400 hover:text-teal-300 transition-colors">
                Mot de passe oublié ?
              </Link>
            </p>
          </div>
          {err && (
            <div className="space-y-3" role="alert">
              <p className="text-red-400 text-sm">{err}</p>
              {err.includes("Impossible de joindre le serveur") && typeof window !== "undefined" && (
                <div className="rounded-xl bg-slate-800 border border-slate-600 p-3 text-xs text-slate-300 space-y-2">
                  <p className="font-semibold text-amber-300">Que faire ?</p>
                  <p>Origine de cette page (à autoriser côté backend) :</p>
                  <p className="font-mono bg-slate-900/80 px-2 py-1.5 rounded break-all text-cyan-300">{window.location.origin}</p>
                  <ol className="list-decimal list-inside space-y-1">
                    <li><strong>Backend (Railway)</strong> → Variables → <code>CORS_ORIGINS</code> = cette URL (ou liste séparée par des virgules, ex. <code>https://www.uwiapp.com,{window.location.origin}</code>), puis redéployer le backend.</li>
                    <li><strong>Front (Vercel / build)</strong> → Variables → <code>VITE_UWI_API_BASE_URL</code> = URL du backend (ex. <code>https://xxx.up.railway.app</code>), puis <strong>redéployer le front</strong> (obligatoire, les VITE_* sont lues au build).</li>
                    <li>Vérifier que le backend répond : ouvrir <code className="text-cyan-300">https://votre-backend.up.railway.app/health</code> dans un onglet.</li>
                  </ol>
                </div>
              )}
            </div>
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
