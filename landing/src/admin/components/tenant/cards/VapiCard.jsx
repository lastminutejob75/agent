import { useState, useEffect } from "react";
import InlineAlert from "../InlineAlert";
import { adminApi } from "../../../../lib/adminApi";

function copy(text) {
  navigator.clipboard?.writeText(String(text)).catch(() => {});
}

export default function VapiCard({ tenant, tenantId, onSaved }) {
  const assistantIdFromParams = tenant?.params?.vapi_assistant_id ?? "";
  const [assistantId, setAssistantId] = useState(assistantIdFromParams);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    setAssistantId(tenant?.params?.vapi_assistant_id ?? "");
  }, [tenant?.tenant_id, tenant?.params?.vapi_assistant_id]);

  async function save() {
    setErr(null);
    setInfo(null);
    setSaving(true);
    try {
      await adminApi.updateTenantVapi(tenantId, { vapi_assistant_id: assistantId });
      setInfo("Vapi mis à jour.");
      await onSaved?.();
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  const inputClass = "block w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-900 font-mono";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="font-semibold text-gray-900 mb-4">Vapi</div>
      {err && <InlineAlert kind="error" message={err} />}
      {info && <InlineAlert kind="info" message={info} />}

      <div className="grid gap-4">
        <label className="block text-sm font-medium text-gray-700">
          assistant_id
          <input value={assistantId} onChange={(e) => setAssistantId(e.target.value)} className={inputClass} />
        </label>
        <div className="flex flex-wrap gap-2 justify-end items-center">
          <button
            type="button"
            onClick={() => copy(assistantId)}
            disabled={!assistantId}
            className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Copier assistant_id
          </button>
          <a
            href="https://dashboard.vapi.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50 text-gray-700"
          >
            Vapi Dashboard
          </a>
          <button type="button" disabled={saving} onClick={save} className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
