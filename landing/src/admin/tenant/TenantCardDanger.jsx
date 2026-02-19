import { useState } from "react";
import ConfirmDialog from "../components/ConfirmDialog";

export default function TenantCardDanger({ tenant, onDelete, deleteLoading }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmName, setConfirmName] = useState("");

  const canDelete = tenant?.status !== "inactive";
  const nameMatch = (confirmName || "").trim().toLowerCase() === (tenant?.name || "").trim().toLowerCase();

  return (
    <section className="rounded-xl border border-red-200 bg-red-50/50 p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-red-900 mb-4">Danger Zone</h2>
      <p className="text-sm text-gray-700 mb-3">
        Soft delete : le client sera désactivé (statut inactive). Postgres uniquement.
      </p>
      {canDelete ? (
        <>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            className="px-4 py-2 border border-red-300 text-red-700 text-sm font-medium rounded-lg hover:bg-red-100"
          >
            Supprimer le client (soft delete)
          </button>
          <ConfirmDialog
            open={confirmOpen}
            title="Supprimer le client"
            message={
              <div className="space-y-2">
                <p>Pour confirmer, tapez le nom du client : <strong>{tenant?.name}</strong></p>
                <input
                  type="text"
                  value={confirmName}
                  onChange={(e) => setConfirmName(e.target.value)}
                  placeholder="Nom du client"
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
                {confirmName && !nameMatch && <p className="text-red-600 text-sm">Le nom ne correspond pas.</p>}
              </div>
            }
            confirmLabel="Supprimer"
            cancelLabel="Annuler"
            danger
            loading={deleteLoading}
            confirmDisabled={!nameMatch}
            onConfirm={() => nameMatch && onDelete?.()}
            onCancel={() => { setConfirmOpen(false); setConfirmName(""); }}
          />
        </>
      ) : (
        <p className="text-sm text-gray-500">Client déjà désactivé.</p>
      )}
    </section>
  );
}
