import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";

export default function AdminLogin() {
  const { login, isAuthed, sessionPersistError } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/admin";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (isAuthed) navigate(from, { replace: true });
  }, [isAuthed, from, navigate]);

  if (isAuthed) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4 text-gray-500">
        Redirection…
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

  const inputClass =
    "block w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-gray-900";
  const labelClass = "block text-sm font-medium text-gray-700";

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-gray-200 rounded-xl shadow-sm p-8">
        <h1 className="text-xl font-bold text-gray-900">Connexion Admin</h1>
        <p className="text-gray-500 text-sm mt-1">Accès réservé.</p>

        {sessionPersistError && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
            Session non persistée. Vérifiez SameSite=None + Secure, et CORS allow-credentials (voir docs/ADMIN_LOGIN_COOKIE.md).
          </div>
        )}
        {err && !sessionPersistError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            {err}
          </div>
        )}

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
          <label className={labelClass}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className={inputClass}
            />
          </label>
          <label className={labelClass}>
            Mot de passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className={inputClass}
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Connexion…" : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  );
}
