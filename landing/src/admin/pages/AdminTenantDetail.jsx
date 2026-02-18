import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import ConfirmDialog from "../components/ConfirmDialog";

export default function AdminTenantDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tenant, setTenant] = useState(null);
  const [stats7d, setStats7d] = useState(null);
  const [stats30d, setStats30d] = useState(null);
  const [billing, setBilling] = useState(null);
  const [techStatus, setTechStatus] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [routingDid, setRoutingDid] = useState("");
  const [routingLoading, setRoutingLoading] = useState(false);
  const [routingErr, setRoutingErr] = useState("");
  const [routingSuccess, setRoutingSuccess] = useState(false);
  const [stripeLoading, setStripeLoading] = useState(false);
  const [usageMonth, setUsageMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [usageData, setUsageData] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  function loadTenant() {
    if (!id) return;
    setLoading(true);
    setErr("");
    Promise.all([
      adminApi.getTenant(id),
      adminApi.tenantStats(id, 7).catch(() => null),
      adminApi.tenantStats(id, 30).catch(() => null),
      adminApi.getTenantBilling(id).catch(() => ({})),
      adminApi.getTenantTechnicalStatus(id).catch(() => null),
    ])
      .then(([t, s7, s30, b, ts]) => {
        setTenant(t);
        setStats7d(s7);
        setStats30d(s30);
        setBilling(b || {});
        setTechStatus(ts);
      })
      .catch((e) => setErr(e.message || "Erreur"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTenant();
  }, [id]);

  async function onActivateNumber(e) {
    e.preventDefault();
    const did = (routingDid || "").trim().replace(/\s/g, "");
    if (!did) {
      setRoutingErr("Saisissez un numéro (E.164 ou FR).");
      return;
    }
    setRoutingErr("");
    setRoutingSuccess(false);
    setRoutingLoading(true);
    try {
      await adminApi.addRouting({
        channel: "vocal",
        key: did.startsWith("+") ? did : did.startsWith("0") ? "+33" + did.slice(1) : "+33" + did,
        tenant_id: parseInt(id, 10),
      });
      setRoutingSuccess(true);
      setRoutingDid("");
      loadTenant();
    } catch (e) {
      const code = e?.data?.error_code;
      if (e?.status === 409 && code === "TEST_NUMBER_IMMUTABLE") {
        setRoutingErr("Numéro test immuable : ce numéro est réservé à la démo.");
      } else {
        setRoutingErr(e?.message || "Erreur lors de l'activation.");
      }
    } finally {
      setRoutingLoading(false);
    }
  }

  async function onDeleteConfirm() {
    setDeleteLoading(true);
    setErr("");
    try {
      await adminApi.deleteTenant(id);
      setDeleteConfirm(false);
      navigate("/admin/tenants");
    } catch (e) {
      if (e.status === 501) {
        setErr("La suppression de client nécessite Postgres (mode actuel : fallback SQLite).");
      } else {
        setErr(e.message || "Erreur lors de la suppression.");
      }
    } finally {
      setDeleteLoading(false);
    }
  }

  if (loading) return <div className="text-gray-500">Chargement…</div>;
  if (err) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {err}
        <Link to="/admin/tenants" className="block mt-2 text-indigo-600 hover:underline">
          ← Retour aux clients
        </Link>
      </div>
    );
  }
  if (!tenant) return null;

  const routing = tenant.routing || [];
  const status = techStatus?.status;

  return (
    <div className="max-w-4xl">
      <div className="flex flex-wrap items-center gap-2">
        <Link to="/admin/tenants" className="text-gray-600 hover:text-gray-900">
          ← Clients
        </Link>
        <span className="text-gray-400">/</span>
        <span className="font-medium text-gray-900">{tenant.name}</span>
        <span className="text-gray-400 text-sm">#{tenant.tenant_id}</span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold text-gray-900">{tenant.name}</h1>
        {billing?.is_suspended && (
          <span className="px-2 py-0.5 text-sm font-medium rounded bg-amber-100 text-amber-800">
            Suspendu{billing?.suspension_reason ? ` (${billing.suspension_reason}${billing?.suspension_mode === "soft" ? ", soft" : ""})` : ""}
          </span>
        )}
      </div>
      <p className="text-gray-500 mt-1">
        {(tenant.params?.contact_email || tenant.contact_email) || "—"} · {tenant.timezone || "Europe/Paris"}
      </p>

      {stats7d && (
        <div className="mt-6 grid grid-cols-3 gap-4 max-w-xl">
          <div className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
            <div className="text-xs font-medium text-gray-500">Appels (7j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats7d.calls_total ?? "—"}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
            <div className="text-xs font-medium text-gray-500">RDV (7j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats7d.appointments_total ?? "—"}</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
            <div className="text-xs font-medium text-gray-500">Transferts (7j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats7d.transfers_total ?? "—"}</div>
          </div>
        </div>
      )}

      {/* Usage Vapi (7j / 30j) */}
      <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage (Vapi)</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="text-xs font-medium text-gray-500">Minutes (7j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats7d?.minutes_total ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500">Coût USD (7j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats7d?.cost_usd != null ? Number(stats7d.cost_usd).toFixed(2) : "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500">Minutes (30j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats30d?.minutes_total ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500">Coût USD (30j)</div>
            <div className="text-lg font-bold text-gray-900 mt-0.5">{stats30d?.cost_usd != null ? Number(stats30d.cost_usd).toFixed(2) : "—"}</div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm text-gray-600">Usage du mois :</label>
            <input
              type="month"
              value={usageMonth}
              onChange={(e) => setUsageMonth(e.target.value)}
              onBlur={() => id && adminApi.getTenantUsage(id, usageMonth).then(setUsageData).catch(() => setUsageData(null))}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={() => id && adminApi.getTenantUsage(id, usageMonth).then(setUsageData).catch(() => setUsageData(null))}
              className="px-2 py-1 text-sm text-indigo-600 hover:underline"
            >
              Actualiser
            </button>
          </div>
          {usageData && (
            <p className="text-sm text-gray-600 mt-2">
              {usageData.minutes_total ?? 0} min · {Number(usageData.cost_usd ?? 0).toFixed(2)} $ · {usageData.calls_count ?? 0} appels
            </p>
          )}
        </div>
      </section>

      {/* Suspension (past_due / manuel) */}
      <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Suspension</h2>
        <p className="text-sm text-gray-500 mb-3">
          {billing?.is_suspended
            ? "Le client est suspendu : l'agent vocal répond par une phrase fixe et ne prend plus de RDV."
            : "Suspendre manuellement ou forcer actif (ignorer past_due) pour une période."}
        </p>
        <div className="flex flex-wrap gap-2">
          {billing?.is_suspended ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  await adminApi.tenantUnsuspend(id);
                  loadTenant();
                } catch (e) {
                  setErr(e?.message || "Erreur");
                }
              }}
              className="px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700"
            >
              Lever la suspension
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await adminApi.tenantForceActive(id, 7);
                    loadTenant();
                  } catch (e) {
                    setErr(e?.message || "Erreur");
                  }
                }}
                className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
              >
                Forcer actif (7 jours)
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!window.confirm("Suspendre (hard) : phrase fixe, zero LLM. Confirmer ?")) return;
                  try {
                    await adminApi.tenantSuspend(id, "hard");
                    loadTenant();
                  } catch (e) {
                    setErr(e?.message || "Erreur");
                  }
                }}
                className="px-4 py-2 border border-amber-300 text-amber-800 font-medium rounded-lg hover:bg-amber-50"
              >
                Suspendre (hard)
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!window.confirm("Suspendre en mode soft : message poli, infos pratiques possibles, pas de RDV. Continuer ?")) return;
                  try {
                    await adminApi.tenantSuspend(id, "soft");
                    loadTenant();
                  } catch (e) {
                    setErr(e?.message || "Erreur");
                  }
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
              >
                Suspendre (soft)
              </button>
            </>
          )}
        </div>
        {billing?.force_active_override && billing?.force_active_until && (
          <p className="text-sm text-gray-500 mt-2">
            Forcé actif jusqu'au {new Date(billing.force_active_until).toLocaleDateString("fr-FR")}.
          </p>
        )}
      </section>

      {/* Stripe (placeholder) */}
      <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Stripe</h2>
        {billing?.stripe_customer_id ? (
          <div className="space-y-2 text-sm">
            <p><span className="text-gray-500">Customer:</span> <code className="bg-gray-100 px-1 rounded">{billing.stripe_customer_id.slice(0, 20)}…</code></p>
            {billing.billing_status && <p><span className="text-gray-500">Statut:</span> <span className="font-medium">{billing.billing_status}</span></p>}
            {billing.plan_key && <p><span className="text-gray-500">Plan:</span> {billing.plan_key}</p>}
            {billing.current_period_end && <p><span className="text-gray-500">Fin période:</span> {new Date(billing.current_period_end).toLocaleDateString("fr-FR")}</p>}
            {billing.trial_ends_at && <p><span className="text-gray-500">Essai jusqu'au:</span> {new Date(billing.trial_ends_at).toLocaleDateString("fr-FR")}</p>}
          </div>
        ) : (
          <p className="text-gray-500 text-sm mb-3">Aucun customer Stripe. Créez-en un pour lier un abonnement plus tard.</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {!billing?.stripe_customer_id && (
            <button
              type="button"
              disabled={stripeLoading}
              onClick={async () => {
                setStripeLoading(true);
                try {
                  await adminApi.createStripeCustomer(id);
                  loadTenant();
                } catch (e) {
                  setErr(e?.message || "Erreur Stripe");
                } finally {
                  setStripeLoading(false);
                }
              }}
              className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {stripeLoading ? "Création…" : "Créer customer"}
            </button>
          )}
          <span className="text-xs text-gray-400 self-center">Lier abonnement : bientôt</span>
        </div>
      </section>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          to={`/admin/tenants/${id}/dashboard`}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700"
        >
          Voir dashboard tenant
        </Link>
        <Link
          to={`/admin/tenants/${id}/calls`}
          className="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          Voir appels
        </Link>
        {tenant.status !== "inactive" && (
          <span className="inline-flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDeleteConfirm(true)}
              className="inline-flex items-center px-4 py-2 border border-red-300 text-red-700 font-medium rounded-lg hover:bg-red-50"
            >
              Supprimer le client
            </button>
            <span className="text-xs text-gray-500">(Postgres uniquement)</span>
          </span>
        )}
      </div>

      {/* Statut technique */}
      {status && (
        <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Statut technique</h2>
          <pre className="text-sm text-gray-600 overflow-auto rounded bg-gray-50 p-3">
            {JSON.stringify(techStatus, null, 2)}
          </pre>
        </section>
      )}

      {/* Raccorder un numéro */}
      <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Raccorder un numéro</h2>
        {routingSuccess && (
          <p className="mb-3 text-sm text-green-600">Numéro enregistré.</p>
        )}
        {routingErr && (
          <p className="mb-3 text-sm text-red-600">{routingErr}</p>
        )}
        <form onSubmit={onActivateNumber} className="flex flex-wrap items-end gap-4">
          <label className="flex-1 min-w-[200px]">
            <span className="block text-sm font-medium text-gray-700 mb-1">Numéro (DID)</span>
            <input
              type="text"
              value={routingDid}
              onChange={(e) => setRoutingDid(e.target.value)}
              placeholder="+33987654321 ou 09 87 65 43 21"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
            />
          </label>
          <button
            type="submit"
            disabled={routingLoading}
            className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {routingLoading ? "Enregistrement…" : "Activer"}
          </button>
        </form>
        {routing.length > 0 && (
          <ul className="mt-4 text-sm text-gray-600">
            {routing.map((r, i) => (
              <li key={i}>
                {r.channel} : {r.key}
              </li>
            ))}
          </ul>
        )}
      </section>

      <ConfirmDialog
        open={deleteConfirm}
        title="Supprimer le client"
        message="Le client sera désactivé (soft delete). Vous pourrez le voir dans la liste avec le statut « inactive ». Confirmer ?"
        confirmLabel="Supprimer"
        cancelLabel="Annuler"
        danger
        loading={deleteLoading}
        onConfirm={onDeleteConfirm}
        onCancel={() => setDeleteConfirm(false)}
      />
    </div>
  );
}
