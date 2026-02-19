export default function TenantCardSuspension({ billing, tenantId, onUnsuspend, onForceActive, onSuspend, setError }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Suspension & Actions Ops</h2>
      <div className="text-sm text-gray-600 mb-3">
        {billing?.is_suspended ? (
          <p>
            État : <strong>Suspendu</strong>
            {billing?.suspension_reason && <> · Raison : {billing.suspension_reason}</>}
            {billing?.suspension_mode && <> · Mode : {billing.suspension_mode}</>}
          </p>
        ) : (
          <p>État : <strong>Non suspendu</strong></p>
        )}
        {billing?.force_active_override && billing?.force_active_until && (
          <p className="mt-1 text-amber-700">Forcé actif jusqu'au {new Date(billing.force_active_until).toLocaleDateString("fr-FR")}.</p>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {billing?.is_suspended ? (
          <button
            type="button"
            onClick={async () => {
              try {
                await onUnsuspend();
              } catch (e) {
                setError?.(e?.message || "Erreur");
              }
            }}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700"
          >
            Lever la suspension
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={async () => {
                try {
                  await onForceActive(7);
                } catch (e) {
                  setError?.(e?.message || "Erreur");
                }
              }}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
            >
              Forcer actif (7 jours)
            </button>
            <button
              type="button"
              onClick={async () => {
                if (!window.confirm("Suspendre (hard) : phrase fixe, zero LLM. Confirmer ?")) return;
                try {
                  await onSuspend("hard");
                } catch (e) {
                  setError?.(e?.message || "Erreur");
                }
              }}
              className="px-4 py-2 border border-amber-300 text-amber-800 text-sm font-medium rounded-lg hover:bg-amber-50"
            >
              Suspendre (hard)
            </button>
            <button
              type="button"
              onClick={async () => {
                if (!window.confirm("Suspendre en mode soft : message poli, pas de RDV. Continuer ?")) return;
                try {
                  await onSuspend("soft");
                } catch (e) {
                  setError?.(e?.message || "Erreur");
                }
              }}
              className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50"
            >
              Suspendre (soft)
            </button>
          </>
        )}
      </div>
    </section>
  );
}
