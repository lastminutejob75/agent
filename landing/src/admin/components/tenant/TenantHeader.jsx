import { useState } from "react";
import { getClientLoginUrl, getClientImpersonateUrl } from "../../../lib/clientAppUrl";
import { adminApi } from "../../../lib/adminApi";

function copy(text) {
  navigator.clipboard?.writeText(String(text)).catch(() => {});
}

export default function TenantHeader({ tenant, billing, tenantId }) {
  const isSusp = !!billing?.is_suspended;
  const reason = billing?.suspension_reason;
  const mode = billing?.suspension_mode;
  const stripeStatus = billing?.billing_status;
  const contactEmail = tenant?.params?.contact_email || tenant?.contact_email || "";

  const badges = [];
  if (isSusp) badges.push(`Suspendu (${reason || "manual"}${mode === "soft" ? ", soft" : ""})`);
  if (stripeStatus) badges.push(`Stripe: ${stripeStatus}`);
  if (tenant?.flags?.sandbox) badges.push("Sandbox");

  const [impersonateLoading, setImpersonateLoading] = useState(false);
  const [impersonateErr, setImpersonateErr] = useState(null);

  const openClientLogin = () => {
    window.open(getClientLoginUrl(contactEmail, tenantId), "_blank", "noopener,noreferrer");
  };

  const openAsClient = async () => {
    setImpersonateErr(null);
    setImpersonateLoading(true);
    try {
      const r = await adminApi.impersonate(tenantId);
      if (r?.token) {
        window.open(getClientImpersonateUrl(r.token), "_blank", "noopener,noreferrer");
      } else {
        setImpersonateErr("Pas de token reçu");
      }
    } catch (e) {
      setImpersonateErr(e?.data?.detail ?? e?.message ?? "Erreur");
    } finally {
      setImpersonateLoading(false);
    }
  };

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>{tenant?.name || "Tenant"}</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {badges.map((b) => (
            <span key={b} style={{ fontSize: 12, padding: "4px 8px", borderRadius: 999, background: "#f3f4f6" }}>
              {b}
            </span>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={openAsClient}
          disabled={impersonateLoading}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 border border-indigo-700 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          title="Voir le dashboard comme ce client (impersonation 5 min)"
        >
          {impersonateLoading ? "…" : "Voir comme le client"}
        </button>
        <button
          type="button"
          onClick={openClientLogin}
          className="px-3 py-1.5 text-sm font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100"
          title={contactEmail ? `Page de connexion (${contactEmail})` : "Page de connexion client"}
        >
          Ouvrir la page de connexion client
        </button>
        {impersonateErr && <span style={{ fontSize: 12, color: "#b91c1c" }}>{impersonateErr}</span>}
        <button
          type="button"
          onClick={() => copy(tenantId)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          Copier Tenant ID
        </button>
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>
        Tenant ID: <code>{tenantId}</code>
      </div>
    </div>
  );
}
