import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import PatientQuestionnaireFields from "../components/patients/PatientQuestionnaireFields.jsx";

export default function PatientQuestionnairePage() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [schema, setSchema] = useState([]);
  const [answers, setAnswers] = useState({});
  const [cabinetName, setCabinetName] = useState("");
  const [patientName, setPatientName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.publicGetPatientQuestionnaire(token);
      setSchema(Array.isArray(res?.schema) ? res.schema : []);
      setAnswers(res?.answers && typeof res.answers === "object" ? res.answers : {});
      setCabinetName(String(res?.cabinet_name || ""));
      setPatientName(String(res?.patient_name || ""));
      if (res?.already_completed) setDone(true);
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.publicSubmitPatientQuestionnaire(token, { answers });
      setDone(true);
    } catch (err) {
      setError(err?.message || "Impossible d'envoyer vos réponses. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F4F8FB] px-4 py-10 font-[Inter,'DM_Sans',sans-serif] text-[#0A1628]">
      <div className="mx-auto w-full max-w-[620px]">
        <div className="mb-6 text-center">
          <div className="text-2xl font-black tracking-tight text-[#009CA4]">UWI</div>
          {cabinetName ? (
            <p className="mt-1 text-sm font-bold text-[#64748B]">{cabinetName}</p>
          ) : null}
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
          ) : error ? (
            <div className="text-center">
              <h1 className="text-xl font-black">Lien indisponible</h1>
              <p className="mt-2 text-sm font-semibold text-[#B91C1C]">{error}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <h1 className="text-xl font-black">Questionnaire médical</h1>
              <p className="mt-1.5 mb-5 text-sm font-semibold text-[#61708B]">
                {patientName ? `${patientName}, merci` : "Merci"} de compléter ces informations avant votre rendez-vous.
              </p>
              <PatientQuestionnaireFields schema={schema} values={answers} onChange={handleChange} disabled={submitting} />
              <button
                type="submit"
                disabled={submitting}
                className="mt-6 w-full rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#007F87] disabled:opacity-70"
              >
                {submitting ? "Envoi…" : "Envoyer mes réponses"}
              </button>
              <p className="mt-3 text-center text-xs text-[#94A3B8]">
                Vos données sont transmises de façon sécurisée à votre cabinet.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
