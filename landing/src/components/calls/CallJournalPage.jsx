import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, LayoutList, Search, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import CallRow from "./CallRow.jsx";
import CallTabs from "./CallTabs.jsx";
import CreatePatientFromCallModal from "./CreatePatientFromCallModal.jsx";
import DetailPanel from "./DetailPanel.jsx";
import EmptyDetailPanel from "./EmptyDetailPanel.jsx";
import KpiCard from "./KpiCard.jsx";
import PatientDuplicateBanner from "../patients/PatientDuplicateBanner.jsx";
import { api } from "../../lib/api.js";
import { useCalls } from "../../lib/useCalls.js";
import { canCreatePatientFromCall, filterCalls, getCallCounts } from "../../lib/callJournal.utils.js";
import {
  buildCallPatientApiPayload,
  buildPatientCreateFormFromCall,
  computePatientCreateFieldErrors,
  isPatientCreateSubmitBlocked,
  PATIENT_CREATE_FORM_EMPTY,
  usePatientCreateDuplicateCheck,
  validatePatientCreateFormForSubmit,
} from "../../lib/patientCreateForm.js";
import {
  checkPatientDuplicates,
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  parsePatientDuplicateError,
} from "../../lib/patientDuplicateCheck.js";

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
  const [createForm, setCreateForm] = useState(PATIENT_CREATE_FORM_EMPTY);
  const [createConflicts, setCreateConflicts] = useState([]);

  const createFieldErrors = useMemo(() => computePatientCreateFieldErrors(createForm), [createForm]);
  const createSubmitBlocked = useMemo(
    () => isPatientCreateSubmitBlocked(createFieldErrors, createConflicts),
    [createFieldErrors, createConflicts],
  );

  const handleCreateConflicts = useCallback((conflicts) => {
    setCreateConflicts(conflicts);
  }, []);

  usePatientCreateDuplicateCheck({
    enabled: createModalOpen,
    phone: createForm.phone,
    email: createForm.email,
    onConflicts: handleCreateConflicts,
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
    setCreateForm(buildPatientCreateFormFromCall(call));
    setCreateConflicts([]);
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
    if (!currentCallId) return;

    const validated = validatePatientCreateFormForSubmit(createForm);
    if (!validated.ok) {
      notify(validated.message || "Complétez le formulaire.");
      return;
    }

    let conflicts = createConflicts;
    try {
      const dupRes = await checkPatientDuplicates({
        phone: validated.phone,
        email: validated.email,
      });
      conflicts = Array.isArray(dupRes?.conflicts) ? dupRes.conflicts : [];
      setCreateConflicts(conflicts);
    } catch {
      /* conserve les conflits affichés */
    }
    if (hasBlockingPatientDuplicate(conflicts)) {
      notify(formatPatientDuplicateConflict(conflicts[0]) || "Doublon téléphone ou e-mail.");
      return;
    }

    const payload = buildCallPatientApiPayload(createForm, {
      validatedName: validated.name,
      rawName: validated.name,
    });
    if (!payload.ok) {
      notify(payload.message || "Formulaire incomplet.");
      return;
    }

    setCreateLoading(true);
    try {
      const result = await createPatientFromCall(currentCallId, payload.body);
      const linkedPhone = String(result?.patient?.phone || validated.phone).trim();
      if (!linkedPhone) throw new Error("Profil créé mais téléphone introuvable.");
      const linkedName = String(result?.patient?.display_name || validated.name || "Patient").trim();

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

      await api.tenantGetPatient(linkedPhone);
      setCreateModalOpen(false);
      setCreateConflicts([]);
      notify("Profil patient créé avec succès.", { keepCreatedPhone: true });
      await selectCall(currentCallId);
    } catch (e) {
      const dup = parsePatientDuplicateError(e);
      notify(dup.message || e?.message || "Impossible de créer la fiche patient.");
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
    if (!call?.id || !noteDraft.trim()) return;
    try {
      await addCallNote(call.id, noteDraft.trim());
      setNoteDraft("");
      notify("Note ajoutée.");
      await selectCall(call.id);
    } catch (e) {
      notify(e?.message || "Impossible d'ajouter la note.");
    }
  }

  return (
    <div className="min-h-full bg-[#F5F9FA]">
      <div className="mx-auto max-w-[1440px] px-4 py-5 lg:px-6">
        {actionMsg ? (
          <div className="mb-4 rounded-xl border border-[#CFE8EA] bg-[#E8F7F8] px-4 py-3 text-sm font-semibold text-[#0A5C62]">
            {actionMsg}
            {lastCreatedPhone ? (
              <button
                type="button"
                className="ml-3 font-extrabold text-[#009CA4] underline"
                onClick={() => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(lastCreatedPhone)}`)}
              >
                Ouvrir la fiche
              </button>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : null}

        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KpiCard label="Total" value={counts.total} />
          <KpiCard label="À traiter" value={counts.aTraiter} accent="orange" />
          <KpiCard label="RDV" value={counts.rdv} accent="teal" />
          <KpiCard label="Rappels" value={counts.rappel} accent="blue" />
        </div>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CallTabs activeTab={activeTab} onChange={setActiveTab} counts={counts} />
          <label className="relative w-full sm:max-w-xs">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher un appel..."
              className="w-full rounded-xl border border-[#E2E8F0] py-2.5 pl-9 pr-3 text-sm outline-none focus:border-[#009CA4]"
            />
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="rounded-[24px] border border-[#E2E8F0] bg-white">
            <div className="flex items-center justify-between border-b border-[#EEF2F6] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-extrabold text-[#0A1628]">
                <LayoutList size={16} />
                Journal des appels
              </div>
              <span className="text-xs font-semibold text-[#64748B]">{filteredCalls.length} résultat(s)</span>
            </div>

            <div className="divide-y divide-[#EEF2F6]">
              {loading ? (
                <div className="p-6 text-sm text-[#64748B]">Chargement des appels...</div>
              ) : filteredCalls.length === 0 ? (
                <div className="p-6 text-sm text-[#64748B]">Aucun appel pour ce filtre.</div>
              ) : (
                filteredCalls.map((call) => (
                  <CallRow
                    key={call.id}
                    call={call}
                    selected={selectedCallId === call.id}
                    createdBadge={Boolean(createdBadges[call.id])}
                    onSelect={() => selectCall(call.id)}
                    onPrimaryAction={() => handlePrimaryAction(call)}
                  />
                ))
              )}
            </div>
          </section>

          <aside className="hidden xl:block">
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
        showEmail
        emailRequired
        extendedProfile
        phoneError={createFieldErrors.phoneError}
        emailError={createFieldErrors.emailError}
        birthDateError={createFieldErrors.birthDateError}
        physicianNameError={createFieldErrors.physicianNameError}
        physicianCityError={createFieldErrors.physicianCityError}
        submitDisabled={createSubmitBlocked}
        onChange={(field, value) => setCreateForm((prev) => ({ ...prev, [field]: value }))}
        onClose={() => {
          setCreateModalOpen(false);
          setCreateConflicts([]);
        }}
        onSubmit={handleCreatePatientSubmit}
        subtitleLine={
          <>
            {createConflicts.length ? (
              <PatientDuplicateBanner conflicts={createConflicts} className="mb-3" />
            ) : null}
            <span>
              Source : <strong>appel entrant</strong>
            </span>
          </>
        }
      />
    </div>
  );
}
