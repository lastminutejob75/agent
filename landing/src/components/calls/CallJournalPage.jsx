import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, LayoutList, Search, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import CallRow from "./CallRow.jsx";
import CallTabs from "./CallTabs.jsx";
import CreatePatientFromCallModal from "./CreatePatientFromCallModal.jsx";
import DetailPanel from "./DetailPanel.jsx";
import EmptyDetailPanel from "./EmptyDetailPanel.jsx";
import KpiCard from "./KpiCard.jsx";
import { api } from "../../lib/api.js";
import { useCalls } from "../../lib/useCalls.js";
import { canCreatePatientFromCall, filterCalls, getCallCounts } from "../../lib/callJournal.utils.js";

function splitName(value) {
  const full = String(value || "").trim();
  if (!full) return { firstName: "", lastName: "" };
  const parts = full.split(/\s+/);
  if (parts.length === 1) return { firstName: "", lastName: parts[0] };
  return { firstName: parts.slice(0, -1).join(" "), lastName: parts.slice(-1)[0] };
}

function buildCreateForm(call) {
  const fromName = splitName(call?.patient?.name);
  const fallbackNote = call?.claraResume || call?.summary || "Aucun résumé Clara disponible.";
  return {
    firstName: fromName.firstName,
    lastName: fromName.lastName,
    phone: call?.phone || "",
    initialNote: fallbackNote,
    callId: call?.id || "",
  };
}

function composePatientName({ firstName, lastName }) {
  return [String(firstName || "").trim(), String(lastName || "").trim()].filter(Boolean).join(" ").trim();
}

export default function CallJournalPage() {
  const navigate = useNavigate();
  const {
    calls,
    loading,
    error,
    selectedCallId,
    selectedCall,
    detailLoading,
    selectCall,
    clearSelection,
    markAsHandled,
    createPatientFromCall,
    addCallNote,
  } = useCalls({ days: 30 });

  const [activeTab, setActiveTab] = useState("tous");
  const [query, setQuery] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [lastCreatedPhone, setLastCreatedPhone] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createdOverrides, setCreatedOverrides] = useState({});
  const [createdBadges, setCreatedBadges] = useState({});
  const toastTimerRef = useRef(0);
  const badgeTimersRef = useRef({});
  const [createForm, setCreateForm] = useState({
    firstName: "",
    lastName: "",
    phone: "",
    initialNote: "",
    callId: "",
  });

  const displayCalls = useMemo(
    () =>
      calls.map((call) => {
        const override = createdOverrides[call.id];
        if (!override) return call;
        return {
          ...call,
          phone: override.phone || call.phone,
          patient: {
            ...call.patient,
            known: true,
            masked: false,
            name: override.name || call.patient?.name || "Patient",
            phone: override.phone || call.patient?.phone || call.phone,
          },
        };
      }),
    [calls, createdOverrides],
  );

  const counts = useMemo(() => getCallCounts(displayCalls), [displayCalls]);
  const filteredCalls = useMemo(() => filterCalls(displayCalls, activeTab, query), [displayCalls, activeTab, query]);
  const selectedBase = selectedCall || displayCalls.find((item) => item.id === selectedCallId) || null;
  const selectedOverride = selectedBase ? createdOverrides[selectedBase.id] : null;
  const selected = selectedBase
    ? {
        ...selectedBase,
        phone: selectedOverride?.phone || selectedBase.phone,
        patient: selectedOverride
          ? {
              ...selectedBase.patient,
              known: true,
              masked: false,
              name: selectedOverride.name || selectedBase.patient?.name || "Patient",
              phone: selectedOverride.phone || selectedBase.patient?.phone || selectedBase.phone,
            }
          : selectedBase.patient,
      }
    : null;
  const selectedCanCreate = canCreatePatientFromCall(selected);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
      Object.values(badgeTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
    };
  }, []);

  function notify(message, { keepCreatedPhone = false } = {}) {
    if (!keepCreatedPhone) setLastCreatedPhone("");
    setActionMsg(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setActionMsg(""), 2200);
  }

  function openCreateModal(call) {
    setCreateForm(buildCreateForm(call));
    setCreateModalOpen(true);
  }

  function handlePrimaryAction(call) {
    if (canCreatePatientFromCall(call)) {
      openCreateModal(call);
      return;
    }
    if (call?.patient?.known && call?.phone) {
      navigate(`/app/patient-dashboard?phone=${encodeURIComponent(call.phone)}`);
      return;
    }
    selectCall(call.id);
  }

  async function handleCreatePatientSubmit() {
    const currentCallId = createForm.callId;
    const patientName = composePatientName(createForm);
    const phone = String(createForm.phone || "").trim();
    if (!currentCallId) return;
    if (!phone) {
      notify("Le téléphone est requis pour créer un profil patient.");
      return;
    }
    setCreateLoading(true);
    try {
      const result = await createPatientFromCall(currentCallId, {
        validated_name: patientName || "Patient",
        raw_name: patientName || "Patient inconnu",
        patient_phone: phone,
      });
      const linkedPhone = String(result?.patient?.phone || phone).trim();
      if (!linkedPhone) throw new Error("Profil créé mais téléphone introuvable.");
      const linkedName = String(result?.patient?.display_name || patientName || "Patient").trim();

      setCreatedOverrides((prev) => ({
        ...prev,
        [currentCallId]: {
          phone: linkedPhone,
          name: linkedName,
        },
      }));
      setCreatedBadges((prev) => ({ ...prev, [currentCallId]: true }));
      if (badgeTimersRef.current[currentCallId]) {
        window.clearTimeout(badgeTimersRef.current[currentCallId]);
      }
      badgeTimersRef.current[currentCallId] = window.setTimeout(() => {
        setCreatedBadges((prev) => {
          if (!prev[currentCallId]) return prev;
          const next = { ...prev };
          delete next[currentCallId];
          return next;
        });
        delete badgeTimersRef.current[currentCallId];
      }, 3000);
      setLastCreatedPhone(linkedPhone);

      if (createForm.initialNote.trim()) {
        try {
          await api.tenantCreatePatientNote(linkedPhone, {
            text: createForm.initialNote.trim(),
            author: "Cabinet",
          });
        } catch {
          await addCallNote(currentCallId, createForm.initialNote.trim());
        }
      }

      // Vérification explicite: le profil doit être récupérable après création.
      await api.tenantGetPatient(linkedPhone);
      setCreateModalOpen(false);
      notify("Profil patient créé avec succès.", { keepCreatedPhone: true });
      await selectCall(currentCallId);
    } catch (e) {
      notify(e?.message || "Impossible de créer la fiche patient.");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleMarkHandled(call) {
    if (!call?.id) return;
    try {
      await markAsHandled(call.id);
      notify("Appel marqué comme traité.");
      if (activeTab === "a-traiter") {
        clearSelection();
      }
    } catch (e) {
      notify(e?.message || "Impossible de marquer cet appel.");
    }
  }

  async function handleAddNote(call) {
    const text = String(noteDraft || "").trim();
    if (!text || !call?.id) return;
    try {
      await addCallNote(call.id, text);
      setNoteDraft("");
      notify("Note ajoutée.");
      await selectCall(call.id);
    } catch (e) {
      notify(e?.message || "Impossible d'ajouter la note.");
    }
  }

  return (
    <div className="min-h-full bg-[#F5F9FA] px-4 py-6 text-[#0A1628] sm:px-6">
      <div className="mx-auto max-w-[1480px]">
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight">Journal d&apos;appels</h1>
            <p className="mt-1 text-sm text-[#52637A]">
              Suivez les appels traités par Clara et les actions à réaliser.
            </p>
          </div>
          <label className="flex h-12 w-full max-w-[420px] items-center gap-3 rounded-2xl border border-[#E2E8F0] bg-white px-4 shadow-sm">
            <Search size={18} className="text-[#64748B]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher un patient, un numéro..."
              className="w-full bg-transparent text-sm font-medium outline-none placeholder:text-[#94A3B8]"
            />
          </label>
        </header>

        <section className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-3">
          <KpiCard value={counts.total} label="Appels" subLabel="30 derniers jours" />
          <KpiCard value={counts.appointmentsTaken} label="Rendez-vous pris" subLabel="ajoutés à l&apos;agenda" />
          <KpiCard value={counts.toProcess} label="À traiter" subLabel="action nécessaire" />
        </section>

        <div className="mb-4">
          <CallTabs
            activeTab={activeTab}
            onChange={setActiveTab}
            toProcessCount={counts.toProcess}
            unknownCount={counts.unknownWithPhone}
          />
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("a-traiter")}
            className="inline-flex h-12 items-center rounded-xl bg-[#009CA4] px-5 text-sm font-extrabold text-white shadow-[0_12px_24px_rgba(0,156,164,.22)] transition hover:bg-[#007F87] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            <LayoutList size={17} className="mr-2" />
            Voir les appels à traiter
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("sans-fiche")}
            className="inline-flex items-center gap-2 rounded-xl border border-[#FFD7B2] bg-[#FFF3EA] px-4 py-2 text-sm font-extrabold text-[#C2410C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
          >
            <AlertCircle size={16} />
            {counts.unknownWithPhone} numéro{counts.unknownWithPhone > 1 ? "s" : ""} sans fiche patient
          </button>
        </div>

        {actionMsg ? (
          <div className="mb-4 rounded-xl border border-[#BFEAF0] bg-[#E6F7F8] px-4 py-3 text-sm font-bold text-[#007F87]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{actionMsg}</span>
              {lastCreatedPhone ? (
                <button
                  type="button"
                  onClick={() => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(lastCreatedPhone)}`)}
                  className="rounded-lg border border-[#009CA4] bg-white px-3 py-1 text-xs font-extrabold text-[#007F87] hover:bg-[#F0FAFB] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
                >
                  Ouvrir la fiche patient
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="mb-4 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm font-bold text-[#B91C1C]">
            {error}
          </div>
        ) : null}

        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="overflow-hidden rounded-[24px] border border-[#E2E8F0] bg-white shadow-sm">
            <div className="hidden grid-cols-[1.45fr_1.05fr_2.1fr_.75fr_1.25fr] gap-5 border-b border-[#E2E8F0] bg-[#FAFCFD] px-5 py-3 text-[11px] font-extrabold uppercase tracking-[0.08em] text-[#94A3B8] md:grid">
              <div>Patient</div>
              <div>Type</div>
              <div>Résumé</div>
              <div>Heure</div>
              <div className="text-right">Action</div>
            </div>

            {loading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-16 animate-pulse rounded-xl bg-[#F3F6FA]" />
                ))}
              </div>
            ) : filteredCalls.length === 0 ? (
              <div className="p-12 text-center text-sm font-semibold text-[#64748B]">
                {query ? "Aucun résultat pour cette recherche." : "Aucun appel trouvé pour ces filtres."}
              </div>
            ) : (
              filteredCalls.map((call) => (
                <CallRow
                  key={call.id}
                  call={call}
                  isSelected={call.id === selectedCallId}
                  canCreatePatient={canCreatePatientFromCall(call)}
                  justCreated={Boolean(createdBadges[call.id])}
                  onSelect={selectCall}
                  onPrimaryAction={handlePrimaryAction}
                />
              ))
            )}
          </section>

          <aside className="hidden xl:sticky xl:top-4 xl:block xl:h-[calc(100vh-128px)] xl:overflow-y-auto">
            {detailLoading ? (
              <div className="space-y-3 rounded-[24px] border border-[#E2E8F0] bg-white p-4">
                <div className="h-16 animate-pulse rounded-xl bg-[#F3F6FA]" />
                <div className="h-28 animate-pulse rounded-xl bg-[#F3F6FA]" />
                <div className="h-28 animate-pulse rounded-xl bg-[#F3F6FA]" />
              </div>
            ) : selected ? (
              <DetailPanel
                call={selected}
                noteDraft={noteDraft}
                onNoteChange={setNoteDraft}
                onClose={clearSelection}
                canCreatePatient={selectedCanCreate}
                onOpenRecording={() => window.open(selected.recordingUrl, "_blank", "noopener,noreferrer")}
                onOpenPatient={() => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(selected.phone)}`)}
                onCreatePatient={() => openCreateModal(selected)}
                onRecall={() => {}}
                onAddNote={() => handleAddNote(selected)}
                onMarkHandled={() => handleMarkHandled(selected)}
                onOpenAgenda={() => navigate("/app/agenda")}
              />
            ) : (
              <EmptyDetailPanel />
            )}
          </aside>
        </div>
      </div>

      {selected ? (
        <div className="fixed inset-0 z-50 bg-[#0A1628]/45 xl:hidden">
          <div className="absolute inset-x-0 bottom-0 top-[12%] overflow-y-auto rounded-t-2xl bg-[#F5F9FA] p-4 sm:top-[8%]">
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={clearSelection}
                aria-label="Fermer le panneau détail"
                className="rounded-full bg-white p-2 text-[#64748B] shadow hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
              >
                <X size={16} />
              </button>
            </div>
            <DetailPanel
              call={selected}
              noteDraft={noteDraft}
              onNoteChange={setNoteDraft}
              onClose={clearSelection}
              canCreatePatient={selectedCanCreate}
              onOpenRecording={() => window.open(selected.recordingUrl, "_blank", "noopener,noreferrer")}
              onOpenPatient={() => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(selected.phone)}`)}
              onCreatePatient={() => openCreateModal(selected)}
              onRecall={() => {}}
              onAddNote={() => handleAddNote(selected)}
              onMarkHandled={() => handleMarkHandled(selected)}
              onOpenAgenda={() => navigate("/app/agenda")}
            />
          </div>
        </div>
      ) : null}

      <CreatePatientFromCallModal
        open={createModalOpen}
        loading={createLoading}
        form={createForm}
        onChange={(field, value) => setCreateForm((prev) => ({ ...prev, [field]: value }))}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={handleCreatePatientSubmit}
      />
    </div>
  );
}
