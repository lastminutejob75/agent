import { useState } from "react";
import { Calendar, Check, FileText, PhoneCall, Play } from "lucide-react";
import { isAppointmentType } from "../../lib/callJournal.utils.js";

function toDialable(phone) {
  return String(phone || "").replace(/[^\d+]/g, "");
}

export default function CallActions({
  call,
  recordingAvailable,
  noteDraft,
  onNoteChange,
  onOpenRecording,
  onOpenPatient,
  onRecall,
  onAddNote,
  onMarkHandled,
  onOpenAgenda,
}) {
  if (!call) return null;
  const [noteOpen, setNoteOpen] = useState(false);

  function ActionRow({ icon: Icon, label, right, onClick, asLink = false, href }) {
    if (asLink) {
      return (
        <a
          href={href}
          onClick={onClick}
          className="flex w-full items-center justify-between rounded-2xl border border-[#E5E7EB] bg-white px-4 py-3 text-sm font-bold text-[#0F172A] hover:bg-[#F8FAFC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          <span className="inline-flex items-center gap-2">
            <Icon size={18} className="text-[#0F172A]" />
            {label}
          </span>
          {right ? <span className="text-xs font-semibold text-[#6B7280]">{right}</span> : null}
        </a>
      );
    }
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center justify-between rounded-2xl border border-[#E5E7EB] bg-white px-4 py-3 text-sm font-bold text-[#0F172A] hover:bg-[#F8FAFC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
      >
        <span className="inline-flex items-center gap-2">
          <Icon size={18} className="text-[#0F172A]" />
          {label}
        </span>
        {right ? <span className="text-xs font-semibold text-[#6B7280]">{right}</span> : null}
      </button>
    );
  }

  return (
    <section className="mt-4">
      <div className="mb-2 text-[26px] font-black tracking-tight">Actions</div>
      <div className="space-y-2.5">
        {recordingAvailable ? (
          <ActionRow
            icon={Play}
            label="Écouter l'enregistrement"
            right={call?.duration || ""}
            onClick={onOpenRecording}
          />
        ) : null}

        {call?.patient?.known && call?.phone ? (
          <ActionRow
            icon={FileText}
            label="Voir la fiche patient"
            onClick={onOpenPatient}
          />
        ) : null}

        {call?.phone && !call?.patient?.masked ? (
          <ActionRow
            asLink
            icon={PhoneCall}
            label="Rappeler le patient"
            href={`tel:${toDialable(call.phone)}`}
            onClick={onRecall}
          />
        ) : null}

        <ActionRow icon={FileText} label="Ajouter une note" onClick={() => setNoteOpen((prev) => !prev)} />
        {noteOpen ? (
          <div className="rounded-2xl border border-[#E2E8F0] bg-white p-3">
            <textarea
              value={noteDraft}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="Ajouter une note..."
              className="h-20 w-full resize-none rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
            />
            <button
              type="button"
              onClick={onAddNote}
              className="mt-2 w-full rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-sm font-extrabold hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
            >
              Enregistrer la note
            </button>
          </div>
        ) : null}

        {call?.status !== "traité" && call?.status !== "résolu" ? (
          <ActionRow icon={Check} label="Marquer comme traité" onClick={onMarkHandled} />
        ) : null}

        {isAppointmentType(call?.type) ? (
          <ActionRow icon={Calendar} label="Ouvrir l'agenda" onClick={onOpenAgenda} />
        ) : null}
      </div>
    </section>
  );
}
