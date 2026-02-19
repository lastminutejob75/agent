import { useState } from "react";
import InlineAlert from "../InlineAlert";
import ConfirmDialog from "../../ConfirmDialog";
import { adminApi } from "../../../../lib/adminApi";

export default function DangerZoneCard({ tenantId, tenantName, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  const nameMatch = (confirmText || "").trim().toLowerCase() === (tenantName || "").trim().toLowerCase();

  async function del() {
    setErr(null);
    setLoading(true);
    try {
      await adminApi.deleteTenant(tenantId);
      onDeleted?.();
    } catch (e) {
      setErr(e?.data?.detail ?? e?.message ?? "Erreur.");
    } finally {
      setLoading(false);
      setOpen(false);
      setConfirmText("");
    }
  }

  return (
    <div className="rounded-xl border border-red-200 bg-red-50/50 p-6 shadow-sm">
      <div className="font-semibold text-red-900 mb-4">Danger zone</div>
      {err && <InlineAlert kind="error" message={err} />}
      <div className="text-sm text-gray-700 mb-3">
        Suppression du client (soft delete). <b>Postgres uniquement</b>.
      </div>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={loading}
        className="px-4 py-2 border border-red-300 text-red-700 text-sm font-medium rounded-lg hover:bg-red-100 disabled:opacity-50"
      >
        Supprimer le client
      </button>

      <ConfirmDialog
        open={open}
        title="Confirmer la suppression"
        message={
          <div className="space-y-2">
            <p>Pour confirmer, tapez le nom du client : <strong>{tenantName || "(nom inconnu)"}</strong></p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="Nom du client"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
            {confirmText && !nameMatch && <p className="text-red-600 text-sm">Le nom ne correspond pas.</p>}
          </div>
        }
        confirmLabel="Supprimer"
        cancelLabel="Annuler"
        danger
        loading={loading}
        confirmDisabled={!nameMatch}
        onConfirm={() => nameMatch && del()}
        onCancel={() => { setOpen(false); setConfirmText(""); }}
      />
    </div>
  );
}
