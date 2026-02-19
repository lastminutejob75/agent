import { useState } from "react";
import InlineAlert from "../InlineAlert";
import { adminApi } from "../../../../lib/adminApi";

export default function SuspensionCard({ tenantId, billing, onChanged }) {
  const [err, setErr] = useState(null);
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  const isSusp = !!billing?.is_suspended;
  const reason = billing?.suspension_reason;
  const mode = billing?.suspension_mode;
  const forceUntil = billing?.force_active_until;

  async function act(fn) {
    setErr(null);
    setInfo(null);
    setLoading(true);
    try {
      await fn();
      await onChanged?.();
      setInfo("OK.");
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="font-semibold text-gray-900 mb-4">Suspension</div>
      {err && <InlineAlert kind="error" message={err} />}
      {info && <InlineAlert kind="info" message={info} />}

      <div className="text-sm text-gray-700 mb-3">
        État: <b>{isSusp ? `Suspendu (${reason || "manual"}${mode === "soft" ? ", soft" : ""})` : "Actif"}</b>
        {forceUntil && <div className="mt-1">Forcé actif jusqu'au {String(forceUntil).slice(0, 10)}</div>}
      </div>

      <div className="flex flex-wrap gap-2">
        {isSusp ? (
          <button
            type="button"
            disabled={loading}
            onClick={() => act(() => adminApi.tenantUnsuspend(tenantId))}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            Lever la suspension
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => adminApi.tenantForceActive(tenantId, 7))}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              Forcer actif (7 jours)
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => adminApi.tenantSuspend(tenantId, "hard"))}
              className="px-4 py-2 border border-amber-300 text-amber-800 text-sm font-medium rounded-lg hover:bg-amber-50 disabled:opacity-50"
            >
              Suspendre (hard)
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => adminApi.tenantSuspend(tenantId, "soft"))}
              className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Suspendre (soft)
            </button>
          </>
        )}
      </div>
    </div>
  );
}
