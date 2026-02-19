import { CopyButton } from "./copyButton";

export default function TenantCardVapi({ tenant }) {
  const params = tenant?.params || {};
  const assistantId = params.vapi_assistant_id ?? "";
  const voiceId = params.vapi_voice_id ?? "";

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Vapi</h2>
      <dl className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <dt className="text-gray-500 w-36">Assistant ID</dt>
          <dd className="flex items-center gap-1 font-mono text-gray-900">
            {assistantId || "—"}
            {assistantId && <CopyButton value={assistantId} />}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="text-gray-500 w-36">Voice ID</dt>
          <dd className="font-mono text-gray-900">{voiceId || "—"}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="text-gray-500 w-36">metadata tenant_id</dt>
          <dd className="text-gray-900">{tenant?.tenant_id != null ? `Présent (${tenant.tenant_id})` : "—"}</dd>
        </div>
      </dl>
      <div className="mt-3 flex gap-2">
        <span className="text-xs text-gray-400">Vérifier config Vapi (bientôt)</span>
      </div>
    </section>
  );
}
