import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { api } from "../../lib/api";
import PatientQuestionnaireFields from "./PatientQuestionnaireFields";

const STATUS_LABEL = {
  draft: "Pas encore rempli",
  sent: "Envoyé au patient · en attente de réponse",
  completed: "Complété",
};

function statusLine(state) {
  if (!state) return STATUS_LABEL.draft;
  if (state.status === "completed") {
    const who = state.filled_by === "patient" ? "par le patient" : "par le praticien";
    return `Complété ${who}`;
  }
  if (state.status === "sent") {
    return state.sent_to_email
      ? `Envoyé à ${state.sent_to_email} · en attente de réponse`
      : STATUS_LABEL.sent;
  }
  return STATUS_LABEL.draft;
}

export default function PatientQuestionnaireCard({ phone, patientEmail, notify, onApplied, disabled = false }) {
  const [schema, setSchema] = useState([]);
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  const notifyFn = useCallback(
    (msg, opts) => {
      if (typeof notify === "function") notify(msg, opts);
    },
    [notify],
  );

  const load = useCallback(async () => {
    if (!phone) return;
    setLoading(true);
    try {
      const res = await api.tenantGetPatientQuestionnaire(phone);
      setSchema(Array.isArray(res?.schema) ? res.schema : []);
      setState(res?.questionnaire || null);
    } catch (e) {
      if (e?.status !== 404) {
        notifyFn(e?.message || "Impossible de charger le questionnaire", { sticky: true });
      }
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [phone, notifyFn]);

  useEffect(() => {
    void load();
  }, [load]);

  const openModal = () => {
    setDraft({ ...(state?.answers || {}) });
    setModalOpen(true);
  };

  const handleChange = (id, value) => {
    setDraft((prev) => ({ ...prev, [id]: value }));
  };

  const handleSave = async () => {
    if (!phone) return;
    setSaving(true);
    try {
      const res = await api.tenantSavePatientQuestionnaire(phone, { answers: draft });
      setState(res?.questionnaire || null);
      setModalOpen(false);
      notifyFn("Questionnaire enregistré");
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Impossible d'enregistrer le questionnaire", { sticky: true });
    } finally {
      setSaving(false);
    }
  };

  const handleSend = async () => {
    if (!phone) return;
    if (!patientEmail) {
      notifyFn("Ajoutez d'abord l'email du patient pour lui envoyer le questionnaire.", { sticky: true });
      return;
    }
    setSending(true);
    try {
      const res = await api.tenantSendPatientQuestionnaire(phone);
      setState(res?.questionnaire || null);
      notifyFn(`Questionnaire envoyé à ${res?.sent_to || patientEmail}`);
    } catch (e) {
      notifyFn(e?.message || "Impossible d'envoyer le questionnaire", { sticky: true });
    } finally {
      setSending(false);
    }
  };

  const completed = state?.status === "completed";
  const sent = state?.status === "sent";

  return (
    <section className="rounded-[24px] border border-[#E3EAF2] bg-white p-4 shadow-[0_8px_20px_rgba(15,23,42,0.06)] sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-[#0B1628] text-[20px]">
          ◰
        </div>
        <div className="min-w-0 flex-1">
          <strong className="block text-base font-black text-[#0B1628]">Questionnaire médical</strong>
          <p className="m-0 mt-1 text-[13px] text-[#667085]">
            {loading ? "Chargement…" : statusLine(state)}
          </p>
        </div>
        {completed ? (
          <span className="shrink-0 rounded-full bg-[#E6FAED] px-2.5 py-1 text-[11px] font-black text-[#0BA64B]">
            Complété
          </span>
        ) : sent ? (
          <span className="shrink-0 rounded-full bg-[#FFF7ED] px-2.5 py-1 text-[11px] font-black text-[#C2410C]">
            Envoyé
          </span>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={openModal}
          disabled={disabled || !phone}
          className="rounded-[14px] bg-[#009CA4] px-3.5 py-2.5 text-xs font-black text-white hover:bg-[#007F87] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {completed ? "Voir / modifier" : "Remplir le questionnaire"}
        </button>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !phone || sending || !patientEmail}
          title={patientEmail ? `Envoyer à ${patientEmail}` : "Ajoutez un email patient"}
          className="rounded-[14px] border border-[#BFE9EC] bg-white px-3.5 py-2.5 text-xs font-black text-[#007F88] hover:bg-[#F0FAFB] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {sending ? "Envoi…" : "Envoyer au patient"}
        </button>
      </div>

      {modalOpen && typeof document !== "undefined"
        ? createPortal(
            <div
              className="fixed inset-0 z-[120] flex items-center justify-center bg-[#0A1628]/50 p-4"
              role="dialog"
              aria-modal="true"
              aria-labelledby="patient-questionnaire-heading"
            >
              <div className="flex max-h-[90vh] w-full max-w-[560px] flex-col rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl">
                <div className="flex items-center justify-between border-b border-[#EEF3F8] px-5 py-4">
                  <h3 id="patient-questionnaire-heading" className="text-lg font-black text-[#0A1628]">
                    Questionnaire médical
                  </h3>
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    aria-label="Fermer"
                    className="rounded-full p-2 text-[#64748B] hover:bg-slate-100"
                  >
                    <X size={16} />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4">
                  <PatientQuestionnaireFields schema={schema} values={draft} onChange={handleChange} />
                </div>
                <div className="flex items-center justify-end gap-2 border-t border-[#EEF3F8] px-5 py-4">
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="rounded-xl border border-[#E2E8F0] px-4 py-2 text-sm font-bold text-[#334155] hover:bg-slate-50"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-xl bg-[#009CA4] px-4 py-2 text-sm font-extrabold text-white hover:bg-[#007F87] disabled:opacity-70"
                  >
                    {saving ? "Enregistrement…" : "Enregistrer"}
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </section>
  );
}
