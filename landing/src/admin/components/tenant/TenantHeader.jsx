function copy(text) {
  navigator.clipboard?.writeText(String(text)).catch(() => {});
}

export default function TenantHeader({ tenant, billing, tenantId }) {
  const isSusp = !!billing?.is_suspended;
  const reason = billing?.suspension_reason;
  const mode = billing?.suspension_mode;
  const stripeStatus = billing?.billing_status;

  const badges = [];
  if (isSusp) badges.push(`Suspendu (${reason || "manual"}${mode === "soft" ? ", soft" : ""})`);
  if (stripeStatus) badges.push(`Stripe: ${stripeStatus}`);
  if (tenant?.flags?.sandbox) badges.push("Sandbox");

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
