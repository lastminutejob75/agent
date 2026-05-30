import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import PatientQuestionnaireFields, { normalizeQuestionnaireSchema } from "../components/patients/PatientQuestionnaireFields.jsx";

const TYPE_DEMANDE_LABELS = {
  premiere_consultation: "Première consultation",
  suivi: "Suivi",
  renouvellement: "Renouvellement",
  recuperation_document: "Récupération de document",
  question_administrative: "Question administrative",
  deplacement_rdv: "Déplacement de RDV",
  autre_administratif: "Autre (administratif)",
};

const DISPONIBILITES_LABELS = {
  matin: "Matin",
  apres_midi: "Après-midi",
  fin_de_semaine: "Fin de semaine",
  semaine_prochaine: "Semaine prochaine",
  flexible: "Flexible",
};

const OPTION_LABELS = { ...TYPE_DEMANDE_LABELS, ...DISPONIBILITES_LABELS };
const FILE_ACCEPT = ".pdf,.jpg,.jpeg,.png,.doc,.docx,.txt";

export default function PatientQuestionnaireV2Page() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [schema, setSchema] = useState([]);
  const [answers, setAnswers] = useState({});
  const [cabinetName, setCabinetName] = useState("");
  const [patientName, setPatientName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [templateType, setTemplateType] = useState("admin");
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadAllowed, setUploadAllowed] = useState(false);
  const [pendingUploads, setPendingUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.publicGetQuestionnaireV2(token);
      const tpl = res?.template || {};
      setSchema(normalizeQuestionnaireSchema(tpl.sections_json || []));
      setAnswers(res?.prefill_answers && typeof res.prefill_answers === "object" ? res.prefill_answers : {});
      setCabinetName(String(res?.cabinet_name || ""));
      setPatientName(String(res?.patient_name || ""));
      setTemplateName(String(tpl.name || "Préparer ma demande"));
      setTemplateType(String(tpl.type || "admin"));
      setUploadAllowed(Boolean(tpl.medical_upload_allowed));
      setUploadMessage(String(res?.medical_upload_message || ""));
      setPendingUploads(Array.isArray(res?.pending_uploads) ? res.pending_uploads : []);
    } catch (e) {
      setError(e?.message || "Ce lien n'est plus valide.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleChange = (id, value) => {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !token) return;
    setUploading(true);
    setError("");
    try {
      const res = await api.publicUploadQuestionnaireV2File(token, file);
      const doc = res?.document;
      if (doc) {
        setPendingUploads((prev) => [...prev, doc]);
      }
    } catch (err) {
      setError(err?.message || "Impossible d'envoyer le document.");
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!consent) {
      setError("Veuillez accepter la transmission de vos informations au cabinet.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api.publicSubmitQuestionnaireV2(token, { answers, consent_given: true });
      setDone(true);
    } catch (err) {
      setError(err?.message || "Impossible d'envoyer vos réponses. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  const isMedical = templateType === "medical";

  return (
    <div className="min-h-screen bg-[#F4F8FB] px-4 py-10 font-[Inter,'DM_Sans',sans-serif] text-[#0A1628]">
      <div className="mx-auto w-full max-w-[620px]">
        <div className="mb-6 text-center">
          <div className="text-2xl font-black tracking-tight text-[#009CA4]">UWI</div>
          {cabinetName ? <p className="mt-1 text-sm font-bold text-[#64748B]">{cabinetName}</p> : null}
        </div>

        <div className="rounded-3xl border border-[#E2EAF4] bg-white p-6 shadow-[0_18px_45px_rgba(15,23,42,0.08)] sm:p-8">
          {loading ? (
            <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
          ) : done ? (
            <div className="text-center">
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-[#E6FAED] text-2xl text-[#0BA64B]">
                ✓
              </div>
              <h1 className="text-xl font-black">Merci !</h1>
              <p className="mt-2 text-sm font-semibold text-[#61708B]">
                Vos réponses ont bien été transmises à {cabinetName || "votre cabinet"}.
                Vous pouvez fermer cette page.
              </p>
            </div>
          ) : error && !schema.length ? (
            <div className="text-center">
              <h1 className="text-xl font-black">Lien indisponible</h1>
              <p className="mt-2 text-sm font-semibold text-[#B91C1C]">{error}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <h1 className="text-xl font-black">{templateName}</h1>
              <p className="mt-1.5 mb-5 text-sm font-semibold text-[#61708B]">
                {patientName ? `${patientName}, merci` : "Merci"} de compléter ce formulaire avant votre rendez-vous.
              </p>
              {uploadMessage ? (
                <p className="mb-4 rounded-xl border border-[#FDE68A] bg-[#FFFBEB] px-3 py-2 text-xs font-semibold text-[#92400E]">
                  {uploadMessage}
                </p>
              ) : null}
              <PatientQuestionnaireFields
                schema={schema}
                values={answers}
                onChange={handleChange}
                disabled={submitting}
                optionLabels={OPTION_LABELS}
              />
              {uploadAllowed ? (
                <div className="mt-5 rounded-xl border border-dashed border-[#CBD5E1] bg-[#F8FAFC] px-4 py-4">
                  <div className="text-sm font-black text-[#334155]">Documents médicaux (optionnel)</div>
                  <p className="mt-1 text-xs text-[#64748B]">PDF, images ou Word — max 10 Mo, 5 fichiers.</p>
                  {pendingUploads.length > 0 ? (
                    <ul className="mt-3 space-y-1 text-sm text-[#475569]">
                      {pendingUploads.map((doc) => (
                        <li key={doc.id || doc.filename}>✓ {doc.filename}</li>
                      ))}
                    </ul>
                  ) : null}
                  <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[#94A3B8] bg-white px-3 py-2 text-xs font-black text-[#475569] hover:bg-slate-50">
                    {uploading ? "Envoi…" : "Ajouter un document"}
                    <input
                      type="file"
                      accept={FILE_ACCEPT}
                      className="hidden"
                      disabled={submitting || uploading || pendingUploads.length >= 5}
                      onChange={(e) => void handleFileUpload(e)}
                    />
                  </label>
                </div>
              ) : null}
              <label className="mt-5 flex items-start gap-2.5 text-sm font-semibold text-[#334155]">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  disabled={submitting}
                  className="mt-0.5 h-4 w-4 rounded border-[#CBD5E1]"
                />
                J&apos;accepte que ces informations soient transmises à mon cabinet.
              </label>
              {error ? <p className="mt-3 text-sm font-semibold text-[#B91C1C]">{error}</p> : null}
              <button
                type="submit"
                disabled={submitting}
                className="mt-6 w-full rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#007F87] disabled:opacity-70"
              >
                {submitting ? "Envoi…" : "Envoyer mes réponses"}
              </button>
              <p className="mt-3 text-center text-xs text-[#94A3B8]">
                {isMedical
                  ? "Données de santé — transmission sécurisée (HDS)."
                  : "Formulaire administratif — aucune donnée médicale n'est demandée ici."}
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
