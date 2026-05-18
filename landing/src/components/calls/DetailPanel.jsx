import { AlertCircle, Calendar, Clock3, FileText, Headphones, User, UserPlus, X } from "lucide-react";
import CallActions from "./CallActions.jsx";
import TypeBadge from "./TypeBadge.jsx";

function statusLabel(status) {
  if (status === "à traiter") return "À traiter";
  if (status === "manqué") return "Manqué";
  if (status === "résolu") return "Résolu";
  return "Traité";
}

export default function DetailPanel({
  call,
  noteDraft,
  onNoteChange,
  onClose,
  canCreatePatient,
  onOpenRecording,
  onOpenPatient,
  onCreatePatient,
  onRecall,
  onAddNote,
  onMarkHandled,
  onOpenAgenda,
}) {
  if (!call) return null;
  const recordingAvailable = Boolean(call?.recordingUrl);

  return (
    <div className="rounded-[24px] border border-[#E2E8F0] bg-[#F7F8FA] p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-black">Détail de l&apos;appel</h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer le détail"
          className="rounded-full p-2 text-[#64748B] hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          <X size={16} />
        </button>
      </div>

      <div className="rounded-3xl border border-[#E2E8F0] bg-white p-5 text-center">
        <div className="mx-auto grid h-24 w-24 place-items-center rounded-full bg-[#E6F7F8] text-[#64748B]">
          <User size={30} />
        </div>
        <div className="mt-4 text-[34px] font-black leading-none tracking-tight text-[#0F172A]">
          {call?.patient?.name || "Patient"}
        </div>
        <div className="mt-2 text-xl font-medium text-[#667085]">{call?.phone || "Numéro non disponible"}</div>
        {!call?.patient?.known ? (
          <div className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-[#FFF4EA] px-3 py-1.5 text-xs font-black text-[#C76A18]">
            <AlertCircle size={14} />
            Aucun dossier patient lié
          </div>
        ) : null}
        {canCreatePatient ? (
          <button
            type="button"
            onClick={onCreatePatient}
            className="mt-5 inline-flex w-full items-center justify-center rounded-2xl bg-[#009CA4] px-4 py-3 text-sm font-extrabold text-white shadow-[0_10px_20px_rgba(0,156,164,.22)] hover:bg-[#008990] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            <UserPlus size={16} className="mr-2" />
            Créer une fiche patient
          </button>
        ) : null}
      </div>

      <section className="mt-6">
        <div className="mb-2 inline-flex items-center gap-2 text-[26px] font-black tracking-tight text-[#0F172A]">
          <Headphones size={20} className="text-[#009CA4]" />
          Résumé de Clara
        </div>
        <div className="rounded-2xl border border-[#CBECEF] bg-[#EAF6F8] p-4">
          <p className="text-[26px] leading-relaxed text-[#0F172A]">
          {call?.claraResume || call?.summary || "Aucun résumé Clara disponible."}
          </p>
        </div>
      </section>

      <section className="mt-6">
        <div className="mb-2 text-[26px] font-black tracking-tight text-[#0F172A]">Informations</div>
        <div className="space-y-3 rounded-2xl border border-[#E2E8F0] bg-white p-4 text-sm">
          <div className="flex items-center gap-3 text-[#677487]">
            <Calendar size={16} />
            <span>Date</span>
            <span className="ml-auto text-[22px] font-black text-[#0F172A]">{call?.date || "—"} · {call?.time || "—"}</span>
          </div>
          <div className="flex items-center gap-3 text-[#677487]">
            <Clock3 size={16} />
            <span>Durée</span>
            <span className="ml-auto text-[22px] font-black text-[#0F172A]">{call?.duration || "—"}</span>
          </div>
          <div className="flex items-center gap-3 text-[#677487]">
            <FileText size={16} />
            <span>Statut</span>
            <span className="ml-auto rounded-md bg-[#FFF4EA] px-2.5 py-0.5 text-xs font-black uppercase tracking-wide text-[#C76A18]">
              {statusLabel(call?.status)}
            </span>
          </div>
          <div className="flex items-center gap-3 text-[#677487]">
            <span>Type</span>
            <span className="ml-auto">
              <TypeBadge type={call?.type} />
            </span>
          </div>
          <div className="flex items-center gap-3 text-[#677487]">
            <User size={16} />
            <span>Patient</span>
            <span className="ml-auto text-[22px] font-black text-[#0F172A]">
              {call?.patient?.known ? "Fiche existante" : "Non rattaché"}
            </span>
          </div>
          {!recordingAvailable ? (
            <div className="rounded-lg bg-[#F8FAFC] px-3 py-2 text-xs font-semibold text-[#64748B]">
              Aucun enregistrement disponible
            </div>
          ) : null}
        </div>
      </section>

      <CallActions
        call={call}
        recordingAvailable={recordingAvailable}
        noteDraft={noteDraft}
        onNoteChange={onNoteChange}
        onOpenRecording={onOpenRecording}
        onOpenPatient={onOpenPatient}
        onRecall={onRecall}
        onAddNote={onAddNote}
        onMarkHandled={onMarkHandled}
        onOpenAgenda={onOpenAgenda}
      />
    </div>
  );
}
