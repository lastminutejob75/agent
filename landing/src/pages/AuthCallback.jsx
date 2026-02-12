import { useEffect, useState } from "react";
import { useSearchParams, Navigate } from "react-router-dom";
import { api, setTenantToken } from "../lib/api.js";

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setErr("Token manquant");
      return;
    }
    api
      .authVerify(token)
      .then((r) => {
        setTenantToken(r.access_token);
        setDone(true);
      })
      .catch((e) => setErr(e.message || "Token invalide ou expiré"));
  }, [token]);

  if (err) {
    return (
      <div className="mx-auto max-w-md p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6">
          <h1 className="text-xl font-bold text-red-800">Connexion échouée</h1>
          <p className="mt-2 text-red-700">{err}</p>
          <a href="/login" className="mt-4 inline-block text-blue-600 hover:underline">
            Réessayer
          </a>
        </div>
      </div>
    );
  }

  if (done) {
    return <Navigate to="/app" replace />;
  }

  return (
    <div className="mx-auto max-w-md p-8 text-center">
      <p className="text-gray-600">Vérification en cours...</p>
    </div>
  );
}
