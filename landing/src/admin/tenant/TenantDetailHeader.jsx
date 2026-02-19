import { Link } from "react-router-dom";
import { CopyButton } from "./copyButton";

export default function TenantDetailHeader({ tenant, billing, stats7d, tenantId }) {
  const lastAt = stats7d?.last_activity_at;
  const lastLabel = lastAt
    ? (() => {
        const d = new Date(lastAt);
        const min = Math.floor((Date.now() - d.getTime()) / 60000);
        if (min < 1) return "à l’instant";
        if (min < 60) return `il y a ${min} min`;
        const h = Math.floor(min / 60);
        if (h < 24) return `il y a ${h} h`;
        return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
      })()
    : null;

  return (
    <header className="sticky top-0 z-10 bg-slate-100 border-b border-slate-200 -mx-6 -mt-6 px-6 py-4 mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-bold text-gray-900">{tenant?.name}</h1>
          {/* Badges statut */}
          <span
            className={`px-2 py-0.5 text-xs font-medium rounded ${
              tenant?.status === "active" && !billing?.is_suspended
                ? "bg-green-100 text-green-800"
                : billing?.is_suspended
                ? "bg-amber-100 text-amber-800"
                : "bg-gray-100 text-gray-700"
            }`}
          >
            {billing?.is_suspended ? "Suspendu" : tenant?.status === "active" ? "Actif" : tenant?.status || "—"}
          </span>
          {billing?.billing_status && (
            <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-200 text-slate-700">
              Stripe: {billing.billing_status}
            </span>
          )}
          <span className="text-gray-400 text-sm font-mono">#{tenantId}</span>
          <CopyButton value={tenantId} label="Copier ID" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {lastLabel && (
            <span className="text-sm text-gray-500">Dernière activité : {lastLabel}</span>
          )}
          <Link
            to={`/admin/tenants/${tenantId}/dashboard`}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            Dashboard
          </Link>
          <Link
            to={`/admin/tenants/${tenantId}/calls`}
            className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50"
          >
            Appels
          </Link>
          <Link
            to="/admin/quality"
            className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50"
          >
            Quality
          </Link>
          <Link
            to="/admin/operations"
            className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50"
          >
            Operations
          </Link>
        </div>
      </div>
    </header>
  );
}
