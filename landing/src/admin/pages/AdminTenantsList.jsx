import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

export default function AdminTenantsList() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    adminApi
      .listTenants("?include_inactive=true")
      .then((r) => setTenants(r.tenants || r || []))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = tenants.filter((t) => {
    const name = (t.name || "").toLowerCase();
    const email = (t.contact_email || "").toLowerCase();
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return name.includes(q) || email.includes(q) || String(t.tenant_id ?? t.id).includes(q);
  });

  if (loading) {
    return <div className="text-gray-500">Chargement des clients…</div>;
  }
  if (err) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{err}</div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
        <Link
          to="/admin/tenants/new"
          className="inline-flex items-center justify-center px-4 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
        >
          Créer un client
        </Link>
      </div>

      <div className="mt-4">
        <input
          type="search"
          placeholder="Rechercher (nom, email, id…)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="block w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-gray-900"
        />
      </div>

      <div className="mt-4 bg-white rounded-xl border border-gray-200 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-500">
            {tenants.length === 0
              ? "Aucun client. Cliquez sur « Créer un client » pour commencer."
              : "Aucun résultat pour cette recherche."}
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {filtered.map((t) => {
              const id = t.tenant_id ?? t.id;
              const name = t.name || "Sans nom";
              const status = t.status || "active";
              return (
                <li
                  key={id}
                  className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 hover:bg-gray-50"
                >
                  <div>
                    <span className="font-medium text-gray-900">{name}</span>
                    <span className="text-gray-400 text-sm ml-2">#{id}</span>
                    {status !== "active" && (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded bg-gray-200 text-gray-600">
                        {status}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Link
                      to={`/admin/tenants/${id}`}
                      className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
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
      </div>
    </div>
  );
}
