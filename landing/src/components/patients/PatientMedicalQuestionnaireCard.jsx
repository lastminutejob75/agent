import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { api } from "../../lib/api";
import QuestionnaireV2DocumentsList from "./QuestionnaireV2DocumentsList.jsx";

const STATUS_LABEL = {
  sent: "Envoyé · en attente",
  opened: "Ouvert par le patient",
  started: "En cours",
  completed: "Réponses reçues · à valider",
  integrated: "Intégré au dossier",
  expired: "Lien expiré",
};

function fmtDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
}

/** Questionnaire médical V2 (HDS) — envoi lien /q/ + historique. */
export default function PatientMedicalQuestionnaireCard({
  phone,
  patientEmail,
  notify,
  onApplied,
  disabled = false,
  summaryRefreshNonce = 0,
}) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [integratingId, setIntegratingId] = useState("");
  const [lastLink, setLastLink] = useState("");
  const [viewResponse, setViewResponse] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [hdsEnabled, setHdsEnabled] = useState(null);
  const [capsLoading, setCapsLoading] = useState(true);

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
      const res = await api.tenantListPatientQuestionnairesV2(phone, { templateType: "medical" });
      setRequests(Array.isArray(res?.requests) ? res.requests : []);
    } catch (e) {
      notifyFn(e?.message || "Impossible de charger les questionnaires médicaux", { sticky: true });
    } finally {
      setLoading(false);
    }
  }, [phone, notifyFn]);

  useEffect(() => {
    void load();
  }, [load, summaryRefreshNonce]);

  useEffect(() => {
    let cancelled = false;
    setCapsLoading(true);
    void api
      .tenantGetCapabilities()
      .then((res) => {
        if (!cancelled) setHdsEnabled(Boolean(res?.hds_enabled));
      })
      .catch(() => {
        if (!cancelled) setHdsEnabled(false);
      })
      .finally(() => {
        if (!cancelled) setCapsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hdsBlocked = hdsEnabled === false;
  const cardDisabled = disabled || hdsBlocked;

  const handleSend = async () => {
    if (!phone) return;
    if (hdsBlocked) {
      notifyFn("Questionnaire médical indisponible : activez l’HDS pour ce cabinet.", { sticky: true });
      return;
    }
    if (!patientEmail) {
      notifyFn("Ajoutez d'abord l'email du patient.", { sticky: true });
      return;
    }
    setSending(true);
    try {
      const res = await api.tenantCreatePatientQuestionnaireV2(phone, {
        template_type: "medical",
        sent_to_email: patientEmail,
        send_email: true,
      });
      setLastLink(res?.questionnaire_url || "");
      notifyFn(`Questionnaire médical envoyé à ${res?.request?.sent_to_email || patientEmail}`);
      await load();
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Envoi impossible (HDS requis)", { sticky: true });
    } finally {
      setSending(false);
    }
  };

  const openResponse = async (responseId) => {
    if (!responseId) return;
    setViewLoading(true);
    setViewResponse({ id: responseId, loading: true });
    try {
      const res = await api.tenantGetQuestionnaireV2Response(responseId);
      setViewResponse(res?.response || null);
    } catch (e) {
      notifyFn(e?.message || "Impossible de charger les réponses", { sticky: true });
      setViewResponse(null);
    } finally {
      setViewLoading(false);
    }
  };

  const handleIntegrate = async (responseId) => {
    if (!responseId) return;
    setIntegratingId(responseId);
    try {
      await api.tenantIntegrateQuestionnaireV2(responseId);
      notifyFn("Questionnaire médical intégré au dossier");
      setViewResponse(null);
      await load();
      if (typeof onApplied === "function") onApplied();
    } catch (e) {
      notifyFn(e?.message || "Intégration impossible", { sticky: true });
    } finally {
      setIntegratingId("");
    }
  };

  const copyLink = async () => {
    if (!lastLink) return;
    try {
      await navigator.clipboard.writeText(lastLink);
      notifyFn("Lien copié");
    } catch {
      notifyFn(lastLink, { sticky: true });
    }
  };

  return (
    <section className="rounded-[24px] border border-[#E3EAF2] bg-white p-4 shadow-[0_8px_20px_rgba(15,23,42,0.06)] sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-[#0B1628] text-[20px]">
          🩺
        </div>
        <div className="min-w-0 flex-1">
          <strong className="block text-base font-black text-[#0B1628]">Questionnaire médical (patient)</strong>
          <p className="m-0 mt-1 text-[13px] text-[#667085]">
            Antécédents, allergies, traitements — données de santé (HDS). Le patient peut joindre des documents.
          </p>
        </div>
      </div>

      {!capsLoading && hdsBlocked ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm text-amber-950">
          <strong className="font-black">HDS requis.</strong> Les questionnaires médicaux et pièces jointes ne sont
          disponibles qu’avec l’hébergement de données de santé activé pour votre cabinet.
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleSend}
          disabled={cardDisabled || !phone || sending || !patientEmail || capsLoading}
          className="rounded-[14px] bg-[#0B1628] px-3.5 py-2.5 text-xs font-black text-white hover:bg-[#1E293B] disabled:opacity-60"
        >
          {sending ? "Envoi…" : "Envoyer le questionnaire médical"}
        </button>
        {lastLink ? (
          <button
            type="button"
            onClick={copyLink}
            className="rounded-[14px] border border-[#BFE9EC] bg-white px-3.5 py-2.5 text-xs font-black text-[#007F88] hover:bg-[#F0FAFB]"
          >
            Copier le dernier lien
          </button>
        ) : null}
      </div>

      <div className="mt-4">
        <div className="mb-2 text-xs font-black uppercase tracking-wide text-[#64748B]">Historique</div>
        {loading ? (
          <p className="text-sm text-[#667085]">Chargement…</p>
        ) : requests.length === 0 ? (
          <p className="text-sm text-[#667085]">Aucun questionnaire médical envoyé.</p>
        ) : (
          <ul className="space-y-2">
            {requests.map((req) => {
              const rid = req.response_id;
              const status = STATUS_LABEL[req.status] || req.status;
              return (
                <li
                  key={req.id}
                  className="rounded-xl border border-[#EEF3F8] bg-[#F8FBFD] px-3 py-2.5 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="font-black text-[#0A1628]">{status}</div>
                      <div className="text-xs text-[#64748B]">
                        {fmtDate(req.created_at)}
                        {req.sent_to_email ? ` · ${req.sent_to_email}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {rid ? (
                        <button
                          type="button"
                          disabled={hdsBlocked}
                          onClick={() => void openResponse(String(rid))}
                          className="rounded-lg border border-[#B6C3D7] px-2.5 py-1 text-xs font-black text-[#475569] hover:bg-white disabled:opacity-50"
                        >
                          Voir les réponses
                        </button>
                      ) : null}
                      {req.status === "completed" && rid ? (
                        <button
                          type="button"
                          disabled={integratingId === String(rid)}
                          onClick={() => void handleIntegrate(String(rid))}
                          className="rounded-lg border border-[#86EFAC] bg-[#F0FDF4] px-2.5 py-1 text-xs font-black text-[#15803D] hover:bg-[#DCFCE7] disabled:opacity-60"
                        >
                          {integratingId === String(rid) ? "…" : "Intégrer"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {req.ai_summary ? (
                    <p className="mt-2 text-xs leading-relaxed text-[#475569]">{String(req.ai_summary).slice(0, 160)}…</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {viewResponse && typeof document !== "undefined"
        ? createPortal(
            <div className="fixed inset-0 z-[120] flex items-center justify-center bg-[#0A1628]/50 p-4">
              <div className="flex max-h-[90vh] w-full max-w-[560px] flex-col rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl">
                <div className="flex items-center justify-between border-b border-[#EEF3F8] px-5 py-4">
                  <h3 className="text-lg font-black text-[#0A1628]">Réponses médicales</h3>
                  <button type="button" onClick={() => setViewResponse(null)} className="rounded-full p-2 hover:bg-slate-100">
                    <X size={16} />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4">
                  {viewLoading ? (
                    <p className="text-sm text-[#64748B]">Chargement…</p>
                  ) : (
                    <>
                      {viewResponse.ai_summary ? (
                        <p className="mb-4 rounded-xl bg-[#F0FAFB] px-3 py-2.5 text-sm leading-relaxed text-[#0F172A]">
                          {viewResponse.ai_summary}
                        </p>
                      ) : null}
                      <ul className="space-y-2">
                        {(viewResponse.answers_display || []).map((row) => (
                          <li key={row.field_id} className="rounded-lg border border-[#EEF3F8] px-3 py-2">
                            <div className="text-xs font-black uppercase tracking-wide text-[#64748B]">{row.label}</div>
                            <div className="text-sm font-semibold text-[#0A1628]">{row.display_value || "—"}</div>
                          </li>
                        ))}
                      </ul>
                      <QuestionnaireV2DocumentsList
                        documents={viewResponse.documents}
                        allowDelete
                        notify={notifyFn}
                        onDocumentDeleted={(docId) =>
                          setViewResponse((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  documents: (prev.documents || []).filter((d) => String(d.id) !== String(docId)),
                                }
                              : prev,
                          )
                        }
                      />
                    </>
                  )}
                </div>
                {viewResponse?.id && viewResponse?.request_status === "completed" ? (
                  <div className="border-t border-[#EEF3F8] px-5 py-4">
                    <button
                      type="button"
                      disabled={integratingId === viewResponse.id}
                      onClick={() => void handleIntegrate(viewResponse.id)}
                      className="w-full rounded-xl bg-[#15803D] px-4 py-2.5 text-sm font-black text-white hover:bg-[#166534] disabled:opacity-60"
                    >
                      {integratingId === viewResponse.id ? "Intégration…" : "Intégrer au dossier"}
                    </button>
                  </div>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}
    </section>
  );
}
