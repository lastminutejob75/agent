import { useState, useEffect } from "react";
import InlineAlert from "../InlineAlert";
import { adminApi } from "../../../../lib/adminApi";

/** Autorise + et chiffres uniquement (E.164 léger). Retourne la chaîne normalisée ou null si invalide. */
function normalizeE164(input) {
  const s = (input || "").trim().replace(/\s/g, "");
  if (!s) return null;
  if (!/^\+?[0-9]+$/.test(s)) return null;
  return s.startsWith("+") ? s : s.startsWith("0") ? "+33" + s.slice(1) : "+33" + s;
}

function copyDid(text) {
  navigator.clipboard?.writeText(String(text)).catch(() => {});
}

export default function TelephonyCard({ tenant, tenantId, onSaved }) {
  const p = tenant?.params || {};
  const routing = tenant?.routing || [];
  const vocalDids = routing.filter((r) => r.channel === "vocal").map((r) => r.key);

  const [transferNumber, setTransferNumber] = useState(p.transfer_number || "");
  const [newDid, setNewDid] = useState("");
  const [saving, setSaving] = useState(false);
  const [routingLoading, setRoutingLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    setTransferNumber(tenant?.params?.transfer_number || "");
  }, [tenant?.tenant_id, tenant?.params?.transfer_number]);

  async function saveTelephony() {
    const toSave = transferNumber.trim();
    if (toSave) {
      const normalized = normalizeE164(transferNumber);
      if (!normalized) {
        setErr("Format attendu : +33… (E.164, uniquement + et chiffres).");
        return;
      }
    }
    setErr(null);
    setInfo(null);
    setSaving(true);
    try {
      const value = transferNumber.trim() ? (normalizeE164(transferNumber) || transferNumber) : "";
      await adminApi.updateTenantTelephony(tenantId, { transfer_number: value });
      if (value) setTransferNumber(value);
      setInfo("Téléphonie mise à jour.");
      await onSaved?.();
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  async function addDid(e) {
    e.preventDefault();
    const raw = (newDid || "").trim().replace(/\s/g, "");
    if (!raw) {
      setErr("Saisissez un numéro (E.164 ou FR).");
      return;
    }
    const key = normalizeE164(newDid);
    if (!key) {
      setErr("Format attendu : +33… (E.164, uniquement + et chiffres).");
      return;
    }
    setErr(null);
    setInfo(null);
    setRoutingLoading(true);
    try {
      await adminApi.addRouting({ channel: "vocal", key, tenant_id: parseInt(tenantId, 10) });
      setInfo("Numéro raccordé.");
      setNewDid("");
      await onSaved?.();
    } catch (e) {
      const code = e?.data?.error_code;
      if (e?.status === 409) {
        setErr(code === "TEST_NUMBER_IMMUTABLE" ? "Ce numéro est réservé à la démo." : "Ce numéro est déjà associé à un autre client.");
      } else {
        setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
      }
    } finally {
      setRoutingLoading(false);
    }
  }

  const inputClass = "block w-full mt-1 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-900";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="font-semibold text-gray-900 mb-4">Téléphonie</div>
      {err && <InlineAlert kind="error" message={err} />}
      {info && <InlineAlert kind="info" message={info} />}

      <div className="grid gap-4">
        <div>
          <div className="text-sm font-medium text-gray-700 mb-1">Numéros entrant (DID Twilio/Vapi)</div>
          {vocalDids.length > 0 ? (
            <ul className="text-sm text-gray-900 font-mono space-y-2">
              {vocalDids.map((did, i) => (
                <li key={i} className="flex items-center gap-2 flex-wrap">
                  <span>{did}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">vocal</span>
                  <button type="button" onClick={() => copyDid(did)} className="text-xs text-indigo-600 hover:underline">Copier</button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">Aucun numéro raccordé.</p>
          )}
        </div>
        <form onSubmit={addDid} className="flex flex-wrap items-end gap-2">
          <label className="flex-1 min-w-[180px]">
            <span className="block text-sm font-medium text-gray-700">Ajouter un DID</span>
            <input
              value={newDid}
              onChange={(e) => setNewDid(e.target.value)}
              placeholder="+33987654321 ou 09 87 65 43 21"
              className={inputClass}
            />
          </label>
          <button type="submit" disabled={routingLoading} className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {routingLoading ? "Enregistrement…" : "Raccorder"}
          </button>
        </form>

        <label className="block text-sm font-medium text-gray-700">
          Numéro de transfert humain (optionnel)
          <input
            value={transferNumber}
            onChange={(e) => setTransferNumber(e.target.value)}
            placeholder="+33…"
            className={inputClass}
          />
        </label>

        <div className="flex justify-end">
          <button type="button" disabled={saving} onClick={saveTelephony} className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
