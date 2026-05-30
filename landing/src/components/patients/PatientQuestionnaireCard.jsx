import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { api } from "../../lib/api";
import PatientQuestionnaireFields from "./PatientQuestionnaireFields";

const MVP_STATUS_LABEL = {
  draft: "Pas encore rempli",
  sent: "Envoyé au patient · en attente de réponse",
  completed: "Complété",
};

const V2_STATUS_LABEL = {
  sent: "Questionnaire administratif envoyé",
  opened: "Ouvert par le patient",
  started: "En cours de saisie",
  completed: "Réponses reçues · à valider",
  integrated: "Intégré au dossier",
  expired: "Lien expiré",
};

const PROFILE_PREFILL_KEYS = ["birth_date", "treating_physician_name", "treating_physician_city"];

function prefillFromProfile(answers, profile) {
  const merged = { ...(answers || {}) };
  if (!profile || typeof profile !== "object") return merged;
  for (const key of PROFILE_PREFILL_KEYS) {
    if (String(merged[key] ?? "").trim()) continue;
    const raw = profile[key];
    if (raw == null) continue;
    let value = String(raw).trim();
    if (key === "birth_date") value = value.slice(0, 10);
    if (value) merged[key] = value;
  }
  return merged;
}

function mvpStatusLine(state) {
  if (!state) return MVP_STATUS_LABEL.draft;
  if (state.status === "completed") {
    const who = state.filled_by === "patient" ? "par le patient" : "par le praticien";
    return `Questionnaire médical complété ${who}`;
  }
  if (state.status === "sent") {
    return state.sent_to_email
      ? `Questionnaire médical envoyé à ${state.sent_to_email}`
      : MVP_STATUS_LABEL.sent;
  }
  return MVP_STATUS_LABEL.draft;
}

function latestV2Request(requests) {
  if (!Array.isArray(requests) || !requests.length) return null;
  return requests[0];
}

export default function PatientQuestionnaireCard({
  phone,
  patientEmail,
  profile,
  notify,
  onApplied,
  disabled = false,
  summaryRefreshNonce = 0,
}) {
  const [schema, setSchema] = useState([]);
  const [mvpState, setMvpState] = useState(null);
  const [v2Requests, setV2Requests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [integrating, setIntegrating] = useState(false);

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
      const [mvpRes, v2Res] = await Promise.all([
        api.tenantGetPatientQuestionnaire(phone).catch(() => null),
        api.tenantListPatientQuestionnairesV2(phone).catch(() => ({ requests: [] })),
      ]);
      setSchema(Array.isArray(mvpRes?.schema) ? mvpRes.schema : []);
      setMvpState(mvpRes?.questionnaire || null);
      setV2Requests(Array.isArray(v2Res?.requests) ? v2Res.requests : []);
    } catch (e) {
      if (e?.status !== 404) {
        notifyFn(e?.message || "Impossible de charger les questionnaires", { sticky: true });
      }
    } finally {
      setLoading(false);
    }
  }, [phone, notifyFn]);

  useEffect(() => {
    void load();
  }, [load, summaryRefreshNonce]);

  const latestV2 = latestV2Request(v2Requests);
  const v2Status = latestV2?.status || "";
  const v2Line = v2Status ? V2_STATUS_LABEL[v2Status] || v2Status : "Aucun questionnaire administratif envoyé";

  const openModal = () => {
    setDraft(prefillFromProfile(mvpState?.answers, profile));
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
      setMvpState(res?.questionnaire || null);
      setModalOpen(false);
      notifyFn("Questionnaire médical enregistré");
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Impossible d'enregistrer le questionnaire", { sticky: true });
    } finally {
      setSaving(false);
    }
  };

  const handleSendV2 = async () => {
    if (!phone) return;
    if (!patientEmail) {
      notifyFn("Ajoutez d'abord l'email du patient pour lui envoyer le questionnaire.", { sticky: true });
      return;
    }
    setSending(true);
    try {
      const res = await api.tenantCreatePatientQuestionnaireV2(phone, {
        sent_to_email: patientEmail,
        send_email: true,
      });
      notifyFn(`Questionnaire envoyé à ${res?.request?.sent_to_email || patientEmail}`);
      await load();
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Impossible d'envoyer le questionnaire", { sticky: true });
    } finally {
      setSending(false);
    }
  };

  const handleIntegrate = async () => {
    const responseId = latestV2?.response_id;
    if (!responseId) {
      notifyFn("Aucune réponse patient à intégrer.", { sticky: true });
      return;
    }
    setIntegrating(true);
    try {
      await api.tenantIntegrateQuestionnaireV2(responseId);
      notifyFn("Questionnaire intégré au dossier");
      await load();
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Impossible d'intégrer le questionnaire", { sticky: true });
    } finally {
      setIntegrating(false);
    }
  };

  const mvpCompleted = mvpState?.status === "completed";

  return (
    <section className="rounded-[24px] border border-[#E3EAF2] bg-white p-4 shadow-[0_8px_20px_rgba(15,23,42,0.06)] sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-[#0B1628] text-[20px]">
          ◰
        </div>
        <div className="min-w-0 flex-1">
          <strong className="block text-base font-black text-[#0B1628]">Questionnaires patient</strong>
          <p className="m-0 mt-1 text-[13px] text-[#667085]">
            {loading ? "Chargement…" : mvpStatusLine(mvpState)}
          </p>
          <p className="m-0 mt-1 text-[12px] font-semibold text-[#008EA1]">{v2Line}</p>
        </div>
        {mvpCompleted ? (
          <span className="shrink-0 rounded-full bg-[#E6FAED] px-2.5 py-1 text-[11px] font-black text-[#0BA64B]">
            Médical OK
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
          {mvpCompleted ? "Voir / modifier (médical)" : "Remplir le questionnaire médical"}
        </button>
        <button
          type="button"
          onClick={handleSendV2}
          disabled={disabled || !phone || sending || !patientEmail}
          title={patientEmail ? `Envoyer le formulaire administratif à ${patientEmail}` : "Ajoutez un email patient"}
          className="rounded-[14px] border border-[#BFE9EC] bg-white px-3.5 py-2.5 text-xs font-black text-[#007F88] hover:bg-[#F0FAFB] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {sending ? "Envoi…" : "Envoyer au patient (admin)"}
        </button>
        {v2Status === "completed" ? (
          <button
            type="button"
            onClick={handleIntegrate}
            disabled={disabled || integrating}
            className="rounded-[14px] border border-[#86EFAC] bg-[#F0FDF4] px-3.5 py-2.5 text-xs font-black text-[#15803D] hover:bg-[#DCFCE7] disabled:opacity-60"
          >
            {integrating ? "Intégration…" : "Valider les réponses reçues"}
          </button>
        ) : null}
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
