import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";

export default function AdminLogin() {
  const { login, loginWithToken, isAuthed, sessionPersistError } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/admin";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [tokenErr, setTokenErr] = useState(null);

  useEffect(() => {
    if (isAuthed) navigate(from, { replace: true });
  }, [isAuthed, from, navigate]);

  if (isAuthed) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="h-8 w-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span>Redirection…</span>
        </div>
      </div>
    );
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result?.sessionPersistError) return;
      navigate(from, { replace: true });
    } catch {
      setErr("Identifiants invalides.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500 text-white font-bold text-2xl shadow-lg shadow-indigo-500/30">
            U
          </div>
          <h1 className="mt-4 text-2xl font-bold text-white">UWi Admin</h1>
          <p className="mt-1 text-slate-400 text-sm">Connexion sécurisée</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl shadow-xl p-8">
          {sessionPersistError && (
            <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 text-amber-200 rounded-xl text-sm">
              Session non persistée. Vérifiez SameSite=None + Secure (voir docs/ADMIN_LOGIN_COOKIE.md).
            </div>
          )}
          {err && !sessionPersistError && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 text-red-200 rounded-xl text-sm">
              {err}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-5">
            <label className="block">
              <span className="block text-sm font-medium text-slate-300 mb-1.5">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="block w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="admin@exemple.fr"
              />
            </label>
            <label className="block">
              <span className="block text-sm font-medium text-slate-300 mb-1.5">Mot de passe</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="block w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="••••••••"
              />
            </label>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-indigo-500 text-white font-semibold rounded-xl hover:bg-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Connexion…" : "Se connecter"}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-600">
            <p className="text-sm font-medium text-slate-400 mb-2">Ou avec le token API</p>
            <p className="text-xs text-slate-500 mb-3">
              Colle la valeur de <code className="bg-slate-700 px-1 rounded">ADMIN_API_TOKEN</code> (Railway).
            </p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setTokenErr(null);
                setTokenLoading(true);
                try {
                  await loginWithToken(token);
                  navigate(from, { replace: true });
                } catch {
                  setTokenErr("Token invalide ou expiré.");
                } finally {
                  setTokenLoading(false);
                }
              }}
              className="flex gap-2"
            >
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Token API admin"
                className="flex-1 px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:ring-2 focus:ring-indigo-500 text-sm"
              />
              <button
                type="submit"
                disabled={tokenLoading || !token.trim()}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white text-sm font-medium rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {tokenLoading ? "…" : "OK"}
              </button>
            </form>
            {tokenErr && (
              <p className="mt-2 text-sm text-red-400">{tokenErr}</p>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-slate-500 text-xs">
          Accès réservé aux administrateurs.
        </p>
      </div>
    </div>
  );
}
