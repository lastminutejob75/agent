import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

import TenantHeader from "../components/tenant/TenantHeader";
import InlineAlert from "../components/tenant/InlineAlert";

import IdentityContactCard from "../components/tenant/cards/IdentityContactCard";
import TelephonyCard from "../components/tenant/cards/TelephonyCard";
import VapiCard from "../components/tenant/cards/VapiCard";
import BillingUsageCard from "../components/tenant/cards/BillingUsageCard";
import SuspensionCard from "../components/tenant/cards/SuspensionCard";
import DangerZoneCard from "../components/tenant/cards/DangerZoneCard";

export default function AdminTenantDetail() {
  const { id } = useParams();
  const tenantId = useMemo(() => (id ? Number(id) : NaN), [id]);
  const nav = useNavigate();

  const [loading, setLoading] = useState(true);
  const [tenant, setTenant] = useState(null);
  const [billing, setBilling] = useState(null);
  const [usageMonth, setUsageMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [err, setErr] = useState(null);

  async function refresh() {
    if (!Number.isFinite(tenantId)) return;
    setErr(null);
    setLoading(true);
    try {
      const [t, b] = await Promise.all([
        adminApi.getTenant(tenantId),
        adminApi.getTenantBilling(tenantId).catch(() => ({})),
      ]);
      setTenant(t);
      setBilling(b || {});
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!Number.isFinite(tenantId)) return;
    refresh();
  }, [tenantId]);

  if (loading) {
    return (
      <div className="p-6 text-gray-500">
        Chargement…
      </div>
    );
  }
  if (err && !tenant) {
    return (
      <div className="p-6">
        <InlineAlert kind="error" title="Erreur" message={err} />
        <Link to="/admin/tenants" className="mt-4 inline-block text-indigo-600 hover:underline">
          ← Retour Clients
        </Link>
      </div>
    );
  }
  if (!tenant) {
    return null;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Link to="/admin/tenants" className="text-gray-600 hover:text-gray-900">
          ← Retour Clients
        </Link>
        <div className="flex-1" />
        <Link to={`/admin/tenants/${tenantId}/dashboard`} className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">
          Dashboard tenant
        </Link>
        <Link to={`/admin/tenants/${tenantId}/calls`} className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
          Appels
        </Link>
        <Link to="/admin/quality" className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
          Quality
        </Link>
      </div>

      <TenantHeader tenant={tenant} billing={billing} tenantId={tenantId} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 align-top">
        {/* Colonne gauche */}
        <div className="lg:col-span-2 space-y-4">
          <IdentityContactCard tenant={tenant} onSaved={refresh} />
          <TelephonyCard tenant={tenant} tenantId={tenantId} onSaved={refresh} />
          <VapiCard tenant={tenant} tenantId={tenantId} onSaved={refresh} />
          <BillingUsageCard
            tenantId={tenantId}
            tenant={tenant}
            billing={billing}
            usageMonth={usageMonth}
            setUsageMonth={setUsageMonth}
            onSaved={refresh}
            onCreateStripeCustomer={async () => {
              await adminApi.createStripeCustomer(tenantId);
              await refresh();
            }}
          />
          <DangerZoneCard
            tenantId={tenantId}
            tenantName={tenant?.name}
            onDeleted={() => nav("/admin/tenants")}
          />
        </div>

        {/* Colonne droite */}
        <div className="space-y-4">
          <SuspensionCard tenantId={tenantId} billing={billing} onChanged={refresh} />
        </div>
      </div>
    </div>
  );
}
