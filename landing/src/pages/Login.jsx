import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { api, getTenantToken } from "../lib/api.js";
import { Link, Navigate } from "react-router-dom";
import { GoogleLoginButton } from "../components/GoogleLoginButton.jsx";
import { getApiUrl } from "../lib/authConfig.js";

export default function Login() {
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const submitRef = useRef(null);

  // Pré-remplir l’email depuis l’URL (ex. lien admin ?email=...&from=admin&tenant=...)
  useEffect(() => {
    const q = searchParams.get("email");
    if (q && typeof q === "string" && q.trim()) {
      setEmail(q.trim());
    }
  }, [searchParams]);

  // Focus sur le bouton "Envoyer le lien" quand l’email est déjà pré-rempli (UX support)
  useEffect(() => {
    if (email && submitRef.current) {
      submitRef.current.focus();
    }
  }, [email]);

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
      const fromParam = searchParams.get("from") || undefined;
      const tenantParam = searchParams.get("tenant") || undefined;
      const r = await api.authRequestLink(email.trim(), {
        ...(fromParam && { from: fromParam }),
        ...(tenantParam && { tenant: tenantParam }),
      });
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
    const debugUrl = err?.startsWith("Mode debug: lien = ")
      ? err.replace("Mode debug: lien = ", "").trim()
      : null;
    return (
      <div className="mx-auto max-w-md p-8">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-bold text-gray-900">Vérifiez votre email</h1>
          <p className="mt-2 text-gray-600">
            Si un compte existe pour cet email, vous recevrez un lien de connexion.
          </p>
          {debugUrl ? (
            <div className="mt-4 rounded-lg bg-amber-50 p-3">
              <p className="text-sm text-amber-800 font-medium">Mode debug — lien direct :</p>
              <a
                href={debugUrl}
                className="mt-2 block truncate text-sm text-blue-600 hover:underline"
              >
                {debugUrl}
              </a>
              <a
                href={debugUrl}
                className="mt-2 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Se connecter
              </a>
            </div>
          ) : err ? (
            <p className="mt-2 text-amber-600 text-sm">{err}</p>
          ) : null}
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
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <button
            ref={submitRef}
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
