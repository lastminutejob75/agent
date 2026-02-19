import { useState, useEffect } from "react";
import { CopyButton } from "./copyButton";

export default function TenantCardTelephony({
  tenant,
  routingDid,
  setRoutingDid,
  onActivateNumber,
  routingLoading,
  routingErr,
  routingSuccess,
  onSaveParams,
  paramsSaving,
}) {
  const routing = tenant?.routing || [];
  const vocalDids = routing.filter((r) => r.channel === "vocal").map((r) => r.key);
  const params = tenant?.params || {};
  const [transferNumber, setTransferNumber] = useState(params.transfer_number ?? "");
  const [transferEnabled, setTransferEnabled] = useState(params.transfer_enabled !== "false");
  const [editTransfer, setEditTransfer] = useState(false);

  useEffect(() => {
    setTransferNumber(params.transfer_number ?? "");
    setTransferEnabled(params.transfer_enabled !== "false");
  }, [tenant?.tenant_id, params.transfer_number, params.transfer_enabled]);

  const saveTransfer = async () => {
    await onSaveParams({
      transfer_number: transferNumber,
      transfer_enabled: transferEnabled ? "true" : "false",
    });
    setEditTransfer(false);
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Téléphonie</h2>

      <div className="space-y-4">
        <div>
          <span className="block text-sm font-medium text-gray-500 mb-1">DID entrant principal (Twilio / Vapi)</span>
          {vocalDids.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {vocalDids.map((did, i) => (
                <span key={i} className="flex items-center gap-1 font-mono text-gray-900">
                  {did}
                  <CopyButton value={did} />
                  <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-800">routé</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Aucun numéro raccordé</p>
          )}
        </div>

        <div>
          <span className="block text-sm font-medium text-gray-500 mb-1">Numéro de transfert humain</span>
          {editTransfer ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={transferNumber}
                onChange={(e) => setTransferNumber(e.target.value)}
                placeholder="E.164"
                className="flex-1 min-w-[120px] rounded border border-gray-300 px-2 py-1 text-sm"
              />
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={transferEnabled} onChange={(e) => setTransferEnabled(e.target.checked)} />
                Transfert activé
              </label>
              <button type="button" onClick={saveTransfer} disabled={paramsSaving} className="px-2 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50">
                {paramsSaving ? "…" : "OK"}
              </button>
              <button type="button" onClick={() => setEditTransfer(false)} className="px-2 py-1 border border-gray-300 text-sm rounded hover:bg-gray-50">
                Annuler
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="font-mono text-gray-900">{params.transfer_number || "—"}</span>
              {params.transfer_number && <CopyButton value={params.transfer_number} />}
              <span className="text-xs text-gray-500">Transfert {params.transfer_enabled === "false" ? "désactivé" : "activé"}</span>
              <button type="button" onClick={() => setEditTransfer(true)} className="text-xs text-indigo-600 hover:underline">
                Modifier
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-100">
        <span className="block text-sm font-medium text-gray-700 mb-2">Raccorder / Mettre à jour routing</span>
        {routingSuccess && <p className="text-sm text-green-600 mb-2">Numéro enregistré.</p>}
        {routingErr && <p className="text-sm text-red-600 mb-2">{routingErr}</p>}
        <form onSubmit={onActivateNumber} className="flex flex-wrap items-end gap-2">
          <input
            type="text"
            value={routingDid}
            onChange={(e) => setRoutingDid(e.target.value)}
            placeholder="+33987654321 ou 09 87 65 43 21"
            className="flex-1 min-w-[180px] rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
          />
          <button type="submit" disabled={routingLoading} className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {routingLoading ? "Enregistrement…" : "Raccorder"}
          </button>
        </form>
      </div>
    </section>
  );
}
