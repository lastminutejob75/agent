import { useState, useEffect } from "react";
import { CopyButton } from "./copyButton";

const labelClass = "block text-sm font-medium text-gray-500 mt-2 first:mt-0";
const inputClass = "block w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white";

export default function TenantCardIdentity({ tenant, onSave, saving }) {
  const params = tenant?.params || {};
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({
    contact_email: params.contact_email ?? tenant?.contact_email ?? "",
    billing_email: params.billing_email ?? "",
    responsible_phone: params.responsible_phone ?? "",
    business_type: params.business_type ?? "",
    notes: params.notes ?? "",
  });

  useEffect(() => {
    const p = tenant?.params || {};
    setForm({
      contact_email: p.contact_email ?? tenant?.contact_email ?? "",
      billing_email: p.billing_email ?? "",
      responsible_phone: p.responsible_phone ?? "",
      business_type: p.business_type ?? "",
      notes: p.notes ?? "",
    });
  }, [tenant?.tenant_id, tenant?.params, tenant?.contact_email]);

  const handleSave = async () => {
    await onSave(form);
    setEdit(false);
  };

  const copyFiche = () => {
    const lines = [
      `Client: ${tenant?.name}`,
      `Tenant ID: ${tenant?.tenant_id}`,
      `Email: ${form.contact_email || "—"}`,
      `Tél: ${form.responsible_phone || "—"}`,
      `Facturation: ${form.billing_email || "—"}`,
      `Business: ${form.business_type || "—"}`,
      `Fuseau: ${tenant?.timezone || "Europe/Paris"}`,
      `Notes: ${form.notes || "—"}`,
    ];
    navigator.clipboard.writeText(lines.join("\n"));
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Identité & Contact</h2>
      <div className="space-y-3 text-sm">
        <div>
          <span className={labelClass}>Nom entreprise</span>
          <p className="text-gray-900 font-medium">{tenant?.name}</p>
        </div>
        <div>
          <span className={labelClass}>Type de business</span>
          {edit ? (
            <input
              type="text"
              value={form.business_type}
              onChange={(e) => setForm((f) => ({ ...f, business_type: e.target.value }))}
              className={inputClass}
              placeholder="medical / artisan / …"
            />
          ) : (
            <p className="text-gray-900">{form.business_type || "—"}</p>
          )}
        </div>
        <div>
          <span className={labelClass}>Fuseau horaire</span>
          <p className="text-gray-900">{tenant?.timezone || "Europe/Paris"}</p>
        </div>
        <div>
          <span className={labelClass}>Email contact</span>
          {edit ? (
            <input
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))}
              className={inputClass}
            />
          ) : (
            <p className="text-gray-900">{form.contact_email || "—"}</p>
          )}
        </div>
        <div>
          <span className={labelClass}>Téléphone responsable</span>
          {edit ? (
            <input
              type="text"
              value={form.responsible_phone}
              onChange={(e) => setForm((f) => ({ ...f, responsible_phone: e.target.value }))}
              className={inputClass}
              placeholder="E.164"
            />
          ) : (
            <span className="flex items-center gap-1">
              <span className="text-gray-900">{form.responsible_phone || "—"}</span>
              {form.responsible_phone && <CopyButton value={form.responsible_phone} />}
            </span>
          )}
        </div>
        <div>
          <span className={labelClass}>Email facturation</span>
          {edit ? (
            <input
              type="email"
              value={form.billing_email}
              onChange={(e) => setForm((f) => ({ ...f, billing_email: e.target.value }))}
              className={inputClass}
            />
          ) : (
            <p className="text-gray-900">{form.billing_email || "—"}</p>
          )}
        </div>
        <div>
          <span className={labelClass}>Notes internes</span>
          {edit ? (
            <textarea
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              rows={3}
              className={inputClass + " resize-y"}
            />
          ) : (
            <p className="text-gray-900 whitespace-pre-wrap">{form.notes || "—"}</p>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {edit ? (
          <>
            <button type="button" onClick={handleSave} disabled={saving} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50">
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
            <button type="button" onClick={() => setEdit(false)} className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50">
              Annuler
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => setEdit(true)} className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50">
              Modifier
            </button>
            <button type="button" onClick={copyFiche} className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50">
              Copier fiche client
            </button>
          </>
        )}
      </div>
    </section>
  );
}
