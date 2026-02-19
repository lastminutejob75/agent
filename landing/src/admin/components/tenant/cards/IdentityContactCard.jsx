import { useState, useEffect } from "react";
import InlineAlert from "../InlineAlert";
import { adminApi } from "../../../../lib/adminApi";

export default function IdentityContactCard({ tenant, onSaved }) {
  const p = tenant?.params || {};
  const [form, setForm] = useState({
    name: tenant?.name || "",
    contact_email: p.contact_email ?? tenant?.contact_email ?? "",
    timezone: tenant?.timezone || "Europe/Paris",
    manager_name: p.manager_name || "",
    manager_phone: p.responsible_phone || "",
    billing_email: p.billing_email || "",
    notes: p.notes || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    const params = tenant?.params || {};
    setForm({
      name: tenant?.name || "",
      contact_email: params.contact_email ?? tenant?.contact_email ?? "",
      timezone: tenant?.timezone || "Europe/Paris",
      manager_name: params.manager_name || "",
      manager_phone: params.responsible_phone || "",
      billing_email: params.billing_email || "",
      notes: params.notes || "",
    });
  }, [tenant?.tenant_id, tenant?.name, tenant?.timezone, tenant?.contact_email, tenant?.params]);

  function set(k, v) {
    setForm((s) => ({ ...s, [k]: v }));
  }

  async function save() {
    const id = tenant?.tenant_id ?? tenant?.id;
    if (!id) return;
    setErr(null);
    setSaving(true);
    try {
      await adminApi.updateTenant(id, {
        contact_email: form.contact_email,
        manager_name: form.manager_name,
        manager_phone: form.manager_phone,
        billing_email: form.billing_email,
        notes: form.notes,
      });
      await onSaved?.();
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  const inputClass = "block w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-900";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="font-semibold text-gray-900 mb-4">Identité & contact</div>
      {err && <InlineAlert kind="error" message={err} />}

      <div className="grid gap-4">
        <label className="block text-sm font-medium text-gray-700">
          Nom entreprise *
          <input
            value={form.name}
            readOnly
            className={inputClass + " bg-gray-50"}
            title="Modifiable côté backend (table tenants)"
          />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          Email contact *
          <input
            type="email"
            value={form.contact_email}
            onChange={(e) => set("contact_email", e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          Fuseau horaire
          <input value={form.timezone} readOnly className={inputClass + " bg-gray-50"} />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block text-sm font-medium text-gray-700">
            Nom responsable
            <input value={form.manager_name} onChange={(e) => set("manager_name", e.target.value)} className={inputClass} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Téléphone responsable
            <input value={form.manager_phone} onChange={(e) => set("manager_phone", e.target.value)} placeholder="+33…" className={inputClass} />
          </label>
        </div>
        <label className="block text-sm font-medium text-gray-700">
          Email facturation (optionnel)
          <input type="email" value={form.billing_email} onChange={(e) => set("billing_email", e.target.value)} className={inputClass} />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          Notes internes
          <textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={3} className={inputClass + " resize-y"} />
        </label>
        <div className="flex justify-end">
          <button type="button" disabled={saving} onClick={save} className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
