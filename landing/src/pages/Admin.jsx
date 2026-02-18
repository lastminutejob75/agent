import { useEffect, useState } from "react";
import { api, getAdminToken, setAdminToken } from "../lib/api.js";
import { Link } from "react-router-dom";

export default function Admin() {
  const [token, setToken] = useState(getAdminToken() || "");
  const [tenants, setTenants] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setErr("");
    setLoading(true);
    try {
      const r = await api.adminListTenants();
      setTenants(r.tenants || r || []);
    } catch (e) {
      setErr(e.message || "Erreur");
    } finally {
      setLoading(false);
    }
  }

  function handleConnect() {
    const t = token.trim();
    if (!t) {
      setErr("Saisissez le token API admin.");
      return;
    }
    setAdminToken(t);
    setErr("");
    load();
  }

  useEffect(() => {
    if (getAdminToken()) load();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900">Admin</h1>
        <p className="text-gray-500 text-sm mt-1">Gestion des clients et des tenants</p>

        {/* Connexion */}
        <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Connexion</h2>
          <label className="block text-sm font-medium text-gray-700 mb-1">Token API admin</label>
          <div className="flex flex-wrap gap-3">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleConnect()}
              placeholder="Collez votre token admin"
              className="flex-1 min-w-[200px] px-3 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-[#0066CC] focus:border-[#0066CC] text-gray-900"
            />
            <button
              type="button"
              onClick={handleConnect}
              disabled={loading}
              className="px-5 py-2.5 bg-[#0066CC] text-white font-medium rounded-lg hover:bg-[#0052A3] disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading ? "Chargement…" : "Charger les clients"}
            </button>
          </div>
          {err && (
            <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>
          )}
        </div>

        {/* Actions + liste */}
        <div className="mt-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 className="text-base font-semibold text-gray-800">Clients</h2>
          <Link
            to="/admin/clients/new"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#0066CC] text-white font-medium rounded-lg hover:bg-[#0052A3] shadow-sm"
          >
            Créer un client
          </Link>
        </div>

        <div className="mt-4 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {tenants.length === 0 && !loading && (
            <div className="px-6 py-12 text-center text-gray-500">
              {getAdminToken() ? "Aucun client. Cliquez sur « Créer un client » pour commencer." : "Saisissez le token et cliquez sur « Charger les clients »."}
            </div>
          )}
          {tenants.length > 0 && (
            <ul className="divide-y divide-gray-200">
              {tenants.map((t) => {
                const id = t.tenant_id ?? t.id;
                const name = t.name || "Sans nom";
                return (
                  <li key={id} className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 hover:bg-gray-50">
                    <div>
                      <span className="font-medium text-gray-900">{name}</span>
                      <span className="text-gray-400 text-sm ml-2">#{id}</span>
                    </div>
                    <div className="flex gap-2">
                      <Link
                        to={`/admin/tenants/${id}`}
                        className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                      >
                        Détail
                      </Link>
                      <Link
                        to={`/admin/tenants/${id}/dashboard`}
                        className="px-3 py-1.5 text-sm font-medium text-white bg-[#0066CC] rounded-md hover:bg-[#0052A3]"
                      >
                        Dashboard
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
