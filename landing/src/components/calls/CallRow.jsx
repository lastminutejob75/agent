import PatientAvatar from "./PatientAvatar.jsx";
import TypeBadge from "./TypeBadge.jsx";

const STATUS_UI = {
  traité: { label: "Traité", className: "bg-[#EAF9F0] text-[#166534]" },
  "à traiter": { label: "À traiter", className: "bg-[#FFF3EA] text-[#C2410C]" },
  manqué: { label: "Manqué", className: "bg-[#FEF2F2] text-[#B91C1C]" },
  résolu: { label: "Résolu", className: "bg-[#EAF9F0] text-[#166534]" },
};

function StatusBadge({ status }) {
  const conf = STATUS_UI[status] || STATUS_UI["à traiter"];
  return (
    <span className={`inline-flex rounded-lg px-2.5 py-1 text-xs font-extrabold ${conf.className}`}>
      {conf.label}
    </span>
  );
}

function actionLabel(call, canCreatePatient) {
  if (canCreatePatient) return "Créer une fiche patient";
  if (call?.patient?.known && call?.phone) return "Voir la fiche patient";
  return "Voir le détail";
}

export default function CallRow({ call, isSelected, canCreatePatient, justCreated = false, onSelect, onPrimaryAction }) {
  const primaryLabel = actionLabel(call, canCreatePatient);

  return (
    <>
      <div
        className={`hidden w-full grid-cols-[1.45fr_1.05fr_2.1fr_.75fr_1.25fr] items-center gap-5 border-b border-[#EDF2F7] px-5 py-4 transition last:border-b-0 md:grid ${
          isSelected ? "bg-[#F0FAFB]" : "hover:bg-[#FAFCFD]"
        }`}
      >
        <button
          type="button"
          onClick={() => onSelect(call.id)}
          className="col-span-4 grid grid-cols-[1.45fr_1.05fr_2.1fr_.75fr] items-center gap-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          <div className="flex min-w-0 items-center gap-3">
            <PatientAvatar patient={call.patient} />
            <div className="min-w-0">
              <div className="truncate text-sm font-black">{call.patient?.name || "Patient"}</div>
              <div className="truncate text-sm text-[#64748B]">{call.phone || "Numéro non disponible"}</div>
            </div>
          </div>
          <TypeBadge type={call.type} />
          <div className="truncate text-sm text-[#334155]">{call.summary || "Aucun résumé Clara disponible."}</div>
          <div>
            <div className="text-xs font-semibold text-[#7A8A9E]">{call.date}</div>
            <div className="text-sm font-black">{call.time}</div>
          </div>
        </button>

        <div className="flex items-center justify-end gap-2">
          {justCreated ? (
            <span className="inline-flex rounded-lg bg-[#EAF9F0] px-2.5 py-1 text-xs font-extrabold text-[#166534]">
              Fiche créée
            </span>
          ) : null}
          <StatusBadge status={call.status} />
          <button
            type="button"
            onClick={() => onPrimaryAction(call)}
            className="inline-flex items-center rounded-xl border border-[#E2E8F0] px-3 py-1.5 text-xs font-extrabold text-[#0A1628] hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            {primaryLabel}
          </button>
        </div>
      </div>

      <div
        className={`block w-full border-b border-[#EDF2F7] px-4 py-4 text-left transition last:border-b-0 md:hidden ${
          isSelected ? "bg-[#F0FAFB]" : "bg-white hover:bg-[#FAFCFD]"
        }`}
      >
        <button
          type="button"
          onClick={() => onSelect(call.id)}
          className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <PatientAvatar patient={call.patient} />
              <div className="min-w-0">
                <div className="truncate text-sm font-black">{call.patient?.name || "Patient"}</div>
                <div className="truncate text-sm text-[#64748B]">{call.phone || "Numéro non disponible"}</div>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              {justCreated ? (
                <span className="inline-flex rounded-lg bg-[#EAF9F0] px-2 py-0.5 text-[10px] font-extrabold text-[#166534]">
                  Fiche créée
                </span>
              ) : null}
              <StatusBadge status={call.status} />
            </div>
          </div>
          <div className="mt-3">
            <TypeBadge type={call.type} />
          </div>
          <p className="mt-3 line-clamp-2 text-sm text-[#334155]">{call.summary || "Aucun résumé Clara disponible."}</p>
          <div className="mt-3 text-xs font-semibold text-[#7A8A9E]">
            {call.date} · {call.time}
          </div>
        </button>

        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={() => onPrimaryAction(call)}
            className="rounded-xl border border-[#E2E8F0] px-3 py-1.5 text-xs font-extrabold text-[#0A1628] hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            {primaryLabel}
          </button>
        </div>
      </div>
    </>
  );
}
