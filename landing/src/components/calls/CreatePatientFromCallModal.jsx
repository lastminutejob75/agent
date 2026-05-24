import { X } from "lucide-react";

export default function CreatePatientFromCallModal({
  open,
  loading,
  form,
  onChange,
  onClose,
  onSubmit,
  subtitleLine,
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0A1628]/50 p-4">
      <div className="w-full max-w-[560px] rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-black text-[#0A1628]">Créer une fiche patient</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la modale"
            className="rounded-full p-2 text-[#64748B] hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            <X size={16} />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
            Nom
            <input
              value={form.lastName}
              onChange={(event) => onChange("lastName", event.target.value)}
              className="rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
            Prénom
            <input
              value={form.firstName}
              onChange={(event) => onChange("firstName", event.target.value)}
              className="rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
            />
          </label>
        </div>

        <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
          Téléphone
          <input
            value={form.phone}
            onChange={(event) => onChange("phone", event.target.value)}
            className="rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
          />
        </label>

        <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
          Note initiale
          <textarea
            value={form.initialNote}
            onChange={(event) => onChange("initialNote", event.target.value)}
            className="h-24 resize-none rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
          />
        </label>

        <div className="mt-2 text-xs text-[#64748B]">
          {subtitleLine || (
            <>
              Source : <strong>appel téléphonique</strong> · Call ID : <strong>{form.callId || "—"}</strong>
            </>
          )}
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-[#E2E8F0] px-4 py-2 text-sm font-bold text-[#334155] hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={loading}
            className="rounded-xl bg-[#009CA4] px-4 py-2 text-sm font-extrabold text-white hover:bg-[#007F87] disabled:cursor-not-allowed disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            {loading ? "Création..." : "Créer la fiche"}
          </button>
        </div>
      </div>
    </div>
  );
}
