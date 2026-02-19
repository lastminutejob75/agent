import { useState, useEffect } from "react";

const PLAN_OPTIONS = ["", "starter", "pro", "business", "custom"];

export default function TenantCardProductFeatures({ tenant, billing, onSavePlan, onSaveFlags, saving }) {
  const params = tenant?.params || {};
  const flags = tenant?.flags || {};
  const planKey = params.plan_key ?? billing?.plan_key ?? "";
  const [plan, setPlan] = useState(planKey);
  const [editPlan, setEditPlan] = useState(false);
  const [editFlags, setEditFlags] = useState(false);
  const [localFlags, setLocalFlags] = useState({
    faq_enabled: flags.faq_enabled ?? true,
    booking_enabled: flags.booking_enabled ?? true,
    transfer_enabled: flags.transfer_enabled ?? true,
    hours_enabled: flags.hours_enabled ?? false,
    sandbox: flags.sandbox ?? false,
  });

  useEffect(() => {
    setPlan(planKey);
  }, [planKey]);

  useEffect(() => {
    setLocalFlags({
      faq_enabled: flags.faq_enabled ?? true,
      booking_enabled: flags.booking_enabled ?? true,
      transfer_enabled: flags.transfer_enabled ?? true,
      hours_enabled: flags.hours_enabled ?? false,
      sandbox: flags.sandbox ?? false,
    });
  }, [tenant?.tenant_id, flags.faq_enabled, flags.booking_enabled, flags.transfer_enabled, flags.hours_enabled, flags.sandbox]);

  const handleSavePlan = async () => {
    await onSavePlan(plan);
    setEditPlan(false);
  };

  const handleSaveFlags = async () => {
    await onSaveFlags(localFlags);
    setEditFlags(false);
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Produit & Features</h2>
      <div className="space-y-4">
        <div>
          <span className="block text-sm font-medium text-gray-500 mb-1">Plan (plan_key)</span>
          {editPlan ? (
            <div className="flex items-center gap-2">
              <select
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
                className="rounded border border-gray-300 px-2 py-1 text-sm"
              >
                {PLAN_OPTIONS.map((p) => (
                  <option key={p || "none"} value={p}>{p || "Aucun"}</option>
                ))}
              </select>
              <button type="button" onClick={handleSavePlan} disabled={saving} className="px-2 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50">
                OK
              </button>
              <button type="button" onClick={() => setEditPlan(false)} className="px-2 py-1 border border-gray-300 text-sm rounded hover:bg-gray-50">
                Annuler
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-gray-900">{planKey || "—"}</span>
              <button type="button" onClick={() => setEditPlan(true)} className="text-xs text-indigo-600 hover:underline">
                Modifier
              </button>
            </div>
          )}
        </div>
        <div>
          <span className="block text-sm font-medium text-gray-500 mb-2">Features</span>
          {editFlags ? (
            <div className="space-y-1">
              {[
                { key: "faq_enabled", label: "FAQ activées" },
                { key: "booking_enabled", label: "RDV activé" },
                { key: "transfer_enabled", label: "Transfert activé" },
                { key: "hours_enabled", label: "Horaires activés" },
                { key: "sandbox", label: "Mode sandbox" },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!localFlags[key]}
                    onChange={(e) => setLocalFlags((f) => ({ ...f, [key]: e.target.checked }))}
                  />
                  {label}
                </label>
              ))}
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={handleSaveFlags} disabled={saving} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50">
                  Enregistrer
                </button>
                <button type="button" onClick={() => setEditFlags(false)} className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50">
                  Annuler
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {[
                { key: "faq_enabled", label: "FAQ" },
                { key: "booking_enabled", label: "RDV" },
                { key: "transfer_enabled", label: "Transfert" },
                { key: "hours_enabled", label: "Horaires" },
                { key: "sandbox", label: "Sandbox" },
              ].map(({ key, label }) => (
                <span
                  key={key}
                  className={`text-xs px-2 py-0.5 rounded ${flags[key] ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}
                >
                  {label}: {flags[key] ? "on" : "off"}
                </span>
              ))}
              <button type="button" onClick={() => setEditFlags(true)} className="text-xs text-indigo-600 hover:underline">
                Modifier
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
