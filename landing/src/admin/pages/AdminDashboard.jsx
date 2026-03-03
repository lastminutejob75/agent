import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import CreateTenantModal from "../components/CreateTenantModal";

export default function AdminDashboard() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => {
    setLoading(true);
    setErr(null);
    adminApi
      .listTenants("?include_inactive=true")
      .then((r) => {
        const raw = r?.tenants ?? r;
        setTenants(Array.isArray(raw) ? raw : []);
      })
      .catch((e) => setErr(e?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const activeCount = tenants.filter((t) => (t.status || "active") === "active").length;
  const lastTenants = [...tenants].sort((a, b) => {
    const aid = a.tenant_id ?? a.id ?? 0;
    const bid = b.tenant_id ?? b.id ?? 0;
    return bid - aid;
  }).slice(0, 10);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <div className="h-5 w-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        Chargement…
      </div>
    );
  }

  if (err) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
        <p className="font-medium">Erreur</p>
        <p className="mt-1 text-sm">{err}</p>
        <button
          type="button"
          onClick={load}
          className="mt-4 px-4 py-2 text-sm font-medium text-red-700 bg-white border border-red-200 rounded-lg hover:bg-red-50"
        >
          Réessayer
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center justify-center px-4 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
        >
          + Nouveau client
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Clients</h2>
          <p className="mt-2 text-3xl font-bold text-slate-900">{tenants.length}</p>
          <p className="mt-1 text-sm text-slate-500">
            {activeCount} actif{activeCount > 1 ? "s" : ""}
          </p>
          <Link
            to="/admin/tenants"
            className="mt-3 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700"
          >
            Voir tous les clients →
          </Link>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Derniers clients</h2>
          {lastTenants.length === 0 ? (
            <p className="mt-4 text-slate-500 text-sm">Aucun client.</p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {lastTenants.map((t) => {
                const id = t.tenant_id ?? t.id;
                const name = t.name || "Sans nom";
                const status = t.status || "active";
                return (
                  <li key={id} className="flex items-center justify-between py-3 first:pt-0">
                    <div>
                      <span className="font-medium text-slate-900">{name}</span>
                      <span className="text-slate-400 text-sm ml-2">#{id}</span>
                      {status !== "active" && (
                        <span className="ml-2 text-xs px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                          {status}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Link
                        to={`/admin/tenants/${id}`}
                        className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200"
                      >
                        Détail
                      </Link>
                      {status === "active" && (
                        <Link
                          to={`/admin/tenants/${id}/dashboard`}
                          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
                        >
                          Dashboard
                        </Link>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <Link
            to="/admin/tenants"
            className="mt-3 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-700"
          >
            Voir tous →
          </Link>
        </div>
      </div>

      <div className="mt-6">
        <Link
          to="/admin/monitoring"
          className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 font-medium"
        >
          <span>📈</span> Voir les stats et KPIs (Monitoring)
        </Link>
      </div>

      {showCreate && (
        <CreateTenantModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}
