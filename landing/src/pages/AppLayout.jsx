import { useState, useEffect } from "react";
import { Outlet, Link, Navigate } from "react-router-dom";
import { api, getTenantToken, clearTenantToken, isTenantUnauthorized } from "../lib/api.js";
import { getImpersonation, setImpersonation } from "./Impersonate";

export default function AppLayout() {
  const [me, setMe] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .tenantMe()
      .then(setMe)
      .catch((e) => {
        if (isTenantUnauthorized(e)) {
          setImpersonation(null);
          clearTenantToken();
          window.location.href = "/";
          return;
        }
        setErr(e.message || "Erreur");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-8 text-gray-600">Chargement...</p>;
  if (err) return <p className="p-8 text-red-600">{err}</p>;
  if (!me) return null;

  const impersonation = getImpersonation();

  const handleLogout = () => {
    setImpersonation(null);
    clearTenantToken();
    window.location.href = "/";
  };

  return (
    <div className="mx-auto max-w-4xl p-6 md:p-8">
      {impersonation && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-900" role="alert">
          Mode admin – vous visualisez le compte de <strong>{impersonation.tenant_name}</strong>
        </div>
      )}
      <header className="mb-6 flex items-center justify-between border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{me.tenant_name || "Mon tableau de bord"}</h1>
          <p className="text-sm text-gray-500">{me.email}</p>
        </div>
        <nav className="flex gap-4">
          <Link to="/app" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
          <Link to="/app/status" className="text-gray-600 hover:text-gray-900">Statut</Link>
          <Link to="/app/rgpd" className="text-gray-600 hover:text-gray-900">RGPD</Link>
          <Link to="/app/settings" className="text-gray-600 hover:text-gray-900">Paramètres</Link>
          <button
            onClick={handleLogout}
            className="text-gray-500 hover:text-red-600 text-sm"
          >
            Déconnexion
          </button>
        </nav>
      </header>
      <Outlet context={{ me }} />
    </div>
  );
}
