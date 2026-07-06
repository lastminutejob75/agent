import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getMotifSuggestions } from "../../utils/motifReformulations.js";
import {
  hasContextFieldSignal,
  isKnownNegative,
} from "../../utils/medicalContext.js";
import {
  DECISION_TAGS,
  FIELD_LABELS,
  NR_TEXT,
  buildChecklist,
  buildConsultationPayloadFromBlocks,
  buildDossierTiles,
  computeImcFrontend,
  isDossierFieldKnown,
  markChecklistCaptured,
  pendingCriticalLabels,
  prepareReviewBlocks,
  splitBlocks,
  DAY_FIELDS,
} from "../../utils/dictationBlocks.js";

/**
 * Dictée ambiante UWi — fiche consultation en 4 moments.
 * =======================================================
 * prep → listen → (structuring) → review → done. Un moment = un écran, un seul
 * CTA en bas, l'état d'avancement vit uniquement dans la note au-dessus du CTA.
 *
 * UWi ne génère jamais de contenu médical : il route et reformule ce que le
 * praticien a dicté (provenance auditable). La transcription brute est un
 * brouillon repliable, jamais persistée après enregistrement.
 */

const PHASE_LABELS = {
  prep: "Avant l'examen",
  listen: "Pendant — dictée en cours",
  structuring: "Pendant — dictée en cours",
  review: "Après — relecture",
  done: "Terminé",
};

function formatElapsed(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function buildDictationAccessError(err) {
  const name = String(err?.name || "");
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Micro refusé. Autorisez le micro dans le navigateur puis réessayez.";
  }
  if (name === "NotFoundError") {
    return "Aucun micro détecté sur cet appareil.";
  }
  return "Impossible de démarrer la dictée (micro indisponible ou page non sécurisée).";
}

function localDegradedBlocks(text) {
  return [{
    id: "elements-0",
    field: "elements",
    dest: "day",
    label: "Éléments",
    text: String(text || "").trim(),
    sourceSpans: [],
    provenance: "dictee",
    critical: false,
    danger: false,
    confirmed: true,
    status: "propose",
  }];
}

function provenanceTag(block) {
  if (block.status === "non_renseigne") return "non renseigné";
  if (block.status === "modifie") return "corrigé";
  if (block.confirmed && block.critical) return "confirmé";
  if (!block.confirmed) return "à confirmer";
  if (block.provenance === "motif_patient") return "motif patient";
  if (block.provenance === "calcule") return "calculé";
  return "dictée";
}

function ChecklistChip({ item }) {
  const got = item.captured;
  const prio = item.priority && !got;
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border-[1.5px] px-3 py-2 text-[13.5px] font-extrabold transition",
        got
          ? "border-[#B5E4D3] bg-[#EBF9F3] text-[#12805C]"
          : prio
            ? "border-[#F2D7A7] bg-[#FFF8EA] text-[#9A5B13]"
            : "border-[#EAECF0] bg-white text-[#475467]",
      ].join(" ")}
    >
      <span
        className={[
          "h-2 w-2 rounded-full",
          got ? "bg-[#12805C]" : prio ? "bg-[#9A5B13]" : "bg-[#D0D5DD]",
        ].join(" ")}
      />
      {item.label}
    </span>
  );
}

function Orb({ active, size = "lg", onClick, label }) {
  const dim = size === "lg" ? "h-[138px] w-[138px] text-[46px]" : "h-[118px] w-[118px] text-[40px]";
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-label={label}
      className={[
        "relative mx-auto grid place-items-center rounded-full text-white transition",
        dim,
        active
          ? "animate-pulse bg-gradient-to-br from-[#2BC1BE] via-[#009CA4] to-[#087981] shadow-[0_22px_58px_rgba(0,156,164,0.34)]"
          : "bg-gradient-to-br from-[#2BC1BE] via-[#009CA4] to-[#087981] opacity-55 grayscale-[0.55] shadow-[0_12px_30px_rgba(16,24,40,0.12)]",
      ].join(" ")}
    >
      🎙️
    </Comp>
  );
}

function DayBlockCard({ block, editing, onStartEdit, onConfirm, onOk, onDelete, confirmingDelete, onMove, moveTargets }) {
  const taRef = useRef(null);
  const [draft, setDraft] = useState(block.text);

  useEffect(() => {
    setDraft(block.text);
  }, [block.text, editing]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  }, [draft, editing]);

  const needs = !block.confirmed;
  return (
    <div
      className={[
        "relative overflow-hidden rounded-[20px] border bg-white py-[15px] pl-[17px] pr-4 shadow-[0_8px_22px_rgba(16,24,40,0.05)]",
        editing ? "border-[#009CA4] ring-[3px] ring-[#E8F7F7]" : "border-[#EAECF0]",
      ].join(" ")}
      onClick={() => {
        if (!editing) onStartEdit(block.id);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (!editing && (e.key === "Enter" || e.key === " ")) onStartEdit(block.id);
      }}
    >
      <span
        className={[
          "absolute bottom-0 left-0 top-0 w-1",
          editing ? "bg-[#009CA4]" : needs ? "bg-[#F2D7A7]" : "bg-[#B5E4D3]",
        ].join(" ")}
      />
      <div className="flex items-center gap-2.5">
        <span
          className={[
            "grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-black",
            needs ? "bg-[#FFF8EA] text-[#9A5B13]" : "bg-[#EBF9F3] text-[#12805C]",
          ].join(" ")}
        >
          {needs ? "!" : "✓"}
        </span>
        <span className={["flex-1 text-[13px] font-black uppercase tracking-[0.045em]", needs ? "text-[#101828]" : "text-[#087981]"].join(" ")}>
          {block.label}
        </span>
        <span
          className={[
            "rounded-full border px-2 py-1 text-[11px] font-extrabold",
            needs
              ? "border-[#F2D7A7] bg-[#FFF8EA] text-[#9A5B13]"
              : "border-[#EAECF0] bg-[#F7F9FA] text-[#98A2B3]",
          ].join(" ")}
        >
          {provenanceTag(block)}
        </span>
      </div>

      <textarea
        ref={taRef}
        rows={1}
        readOnly={!editing}
        value={editing ? draft : block.text}
        onChange={(e) => setDraft(e.target.value)}
        onClick={(e) => {
          if (editing) e.stopPropagation();
        }}
        className="mt-2 block min-h-[34px] w-full resize-none border-0 bg-transparent p-0 text-base leading-[1.52] text-[#101828] outline-none"
      />

      {!editing && block.critical && !block.confirmed ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onConfirm(block.id);
            }}
            className="min-h-[42px] rounded-full bg-[#009CA4] px-4 py-2.5 text-sm font-black text-white shadow-[0_8px_16px_rgba(0,156,164,0.16)]"
          >
            Confirmer
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onStartEdit(block.id);
            }}
            className="min-h-[42px] rounded-full border-[1.5px] border-[#EAECF0] bg-white px-3.5 py-2 text-[13px] font-extrabold text-[#475467]"
          >
            Modifier
          </button>
        </div>
      ) : null}

      {editing ? (
        <div className="mt-3 flex flex-wrap items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            onClick={() => onOk(block.id, draft)}
            className="min-h-[42px] rounded-full bg-[#009CA4] px-4 py-2 text-[13px] font-extrabold text-white"
          >
            OK
          </button>
          {moveTargets.length ? (
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) onMove(block.id, e.target.value);
              }}
              className="min-h-[42px] rounded-full border-[1.5px] border-[#EAECF0] bg-white px-3 py-2 text-[13px] font-extrabold text-[#475467]"
            >
              <option value="">Déplacer vers…</option>
              {moveTargets.map((f) => (
                <option key={f} value={f}>{FIELD_LABELS[f]}</option>
              ))}
            </select>
          ) : null}
          <button
            type="button"
            onClick={() => onDelete(block.id)}
            className={[
              "min-h-[42px] rounded-full border-[1.5px] px-3.5 py-2 text-[13px] font-extrabold",
              confirmingDelete
                ? "border-[#F6C6C2] bg-[#FFF2F2] text-[#D92D20]"
                : "border-[#EAECF0] bg-white text-[#D92D20]",
            ].join(" ")}
          >
            {confirmingDelete ? "Confirmer la suppression ?" : "Supprimer"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function tileStatusLabel(tile) {
  if (tile.calc) return tile.missing ? "en attente du poids/taille" : "calculé automatiquement";
  if (tile.status === "non_renseigne") return "non renseigné";
  if (!tile.confirmed) return tile.danger ? "sécurité — à confirmer" : "à confirmer";
  return tile.status === "modifie" ? "corrigé" : "confirmé";
}

export default function ConsultationDictee({
  patient = {},
  initialDraft = {},
  saving = false,
  onLoadPrefill,
  onReformulateMotif,
  onTranscribe,
  onStructure,
  onSave,
  onClose,
}) {
  const today = new Date().toISOString().slice(0, 10);
  const consultDate = initialDraft?.date || today;
  const heroTime = useMemo(
    () => new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    [],
  );

  // « 1re consultation » = aucune consultation enregistrée pour ce patient.
  // Calculé côté backend (GET patient), jamais déduit du contenu du dossier.
  const firstConsultation = Boolean(patient?.is_first_consultation);
  const checklistBase = useMemo(
    () => buildChecklist(patient, { mesuresConnues: Boolean(patient?.mesures_connues) }),
    [patient],
  );

  const [phase, setPhase] = useState("prep");
  const [consent, setConsent] = useState(false);
  const [dictError, setDictError] = useState("");
  const [pendingBlob, setPendingBlob] = useState(null);

  // ---- motif : verbatim patient + chips de reformulation ----
  const [prefill, setPrefill] = useState(null);
  const [motifChoisi, setMotifChoisi] = useState(null);
  const [motifSource, setMotifSource] = useState("praticien");
  const [motifSheetOpen, setMotifSheetOpen] = useState(false);
  const [llmMotifSuggestions, setLlmMotifSuggestions] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (typeof onLoadPrefill !== "function") return undefined;
    (async () => {
      try {
        const res = await onLoadPrefill(patient?.id);
        if (!cancelled && res) setPrefill(res);
      } catch {
        /* prépa indisponible : la dictée reste utilisable */
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient?.id]);

  const motifRawPatient = useMemo(() => {
    const fromPrefill = String(prefill?.extraction?.motif || "").trim();
    if (fromPrefill) return fromPrefill;
    const fromCall = String(prefill?.resume_appel || "").trim().replace(/^«\s*|\s*»$/g, "");
    if (fromCall) return fromCall;
    const fromDraft = String(initialDraft?.motif || "").trim();
    return fromDraft && fromDraft.toLowerCase() !== "consultation" ? fromDraft : null;
  }, [prefill, initialDraft?.motif]);

  const localMotifSuggestions = useMemo(
    () => (motifRawPatient ? getMotifSuggestions(motifRawPatient) : []),
    [motifRawPatient],
  );
  const motifSuggestions = llmMotifSuggestions ?? localMotifSuggestions;

  useEffect(() => {
    if (!motifRawPatient || typeof onReformulateMotif !== "function") {
      setLlmMotifSuggestions(null);
      return undefined;
    }
    let cancelled = false;
    const controller = new AbortController();
    setLlmMotifSuggestions(null);
    (async () => {
      try {
        const res = await onReformulateMotif({
          raw_motif: motifRawPatient,
          patient_age: patient?.age ?? undefined,
          signal: controller.signal,
        });
        if (cancelled) return;
        const next = Array.isArray(res?.suggestions)
          ? res.suggestions.map((s) => String(s || "").trim()).filter(Boolean).slice(0, 3)
          : [];
        if (next.length) setLlmMotifSuggestions(next);
      } catch {
        /* fallback silencieux sur le niveau A */
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [motifRawPatient, onReformulateMotif, patient?.age]);

  const motifHero = motifChoisi || motifRawPatient || String(initialDraft?.motif || "").trim() || "Consultation";

  // ---- enregistrement audio ----
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef(0);

  const stopStream = useCallback(() => {
    clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => {
    clearInterval(timerRef.current);
    if (recorderRef.current?.state === "recording") {
      try { recorderRef.current.stop(); } catch { /* noop */ }
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  // Quitter la page pendant la dictée = perdre l'audio : on demande confirmation.
  useEffect(() => {
    if (phase !== "listen") return undefined;
    const guard = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [phase]);

  // ---- structuration / relecture ----
  const [blocks, setBlocks] = useState([]);
  const [degraded, setDegraded] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [rawOpen, setRawOpen] = useState(false);
  const [peekOpen, setPeekOpen] = useState(false);
  const [decisionTags, setDecisionTags] = useState([]);

  const [editingDayId, setEditingDayId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [selectedTileKey, setSelectedTileKey] = useState(null);
  const [tileDraft, setTileDraft] = useState("");
  const [toast, setToast] = useState("");
  const toastTimerRef = useRef(null);

  const [savingLocal, setSavingLocal] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [savedSummary, setSavedSummary] = useState(null);

  const showToast = useCallback((message) => {
    setToast(message);
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(""), 1800);
  }, []);
  useEffect(() => () => clearTimeout(toastTimerRef.current), []);

  // Un champ marqué « non renseigné » lors d'une consultation précédente n'est
  // PAS connu : la question reste ouverte pour la structuration.
  const dossierState = useMemo(() => ({
    allergies_connues: isDossierFieldKnown(patient?.allergies),
    antecedents_connus: isDossierFieldKnown(patient?.antecedents_medicaux)
      || isDossierFieldKnown(patient?.antecedents_chirurgicaux),
    traitements_connus: isDossierFieldKnown(patient?.traitements),
    mesures_connues: Boolean(patient?.mesures_connues),
  }), [patient]);

  const runStructuring = useCallback(async (blob) => {
    setPhase("structuring");
    setDictError("");
    let text = "";
    try {
      const sttRes = await onTranscribe(blob, { transcriptionOnly: true });
      text = String(sttRes?.transcription || "").trim();
    } catch (err) {
      setPendingBlob(blob);
      setDictError(
        `La dictée n'a pas pu être transcrite (${String(err?.message || "réseau")}). Elle est conservée : réessayez.`,
      );
      setPhase("prep");
      return;
    }
    if (!text) {
      setDictError("Aucune parole détectée. Réessayez en parlant plus près du micro.");
      setPhase("prep");
      return;
    }
    setPendingBlob(null);
    setTranscript(text);

    let result;
    try {
      result = await onStructure({
        transcript: text,
        motif_choisi: motifChoisi,
        motif_patient_verbatim: motifRawPatient,
        dossier_state: dossierState,
      });
    } catch {
      result = { blocks: localDegradedBlocks(text), degraded: true };
    }
    const isDegraded = Boolean(result?.degraded);
    const prepared = prepareReviewBlocks(result?.blocks, {
      checklist: checklistBase,
      degraded: isDegraded,
      firstConsultation,
      // Un état allergies existe (contenu, négation ou « non renseigné » tracé) :
      // la tuile synthétique ne bloque plus (invariant 3).
      allergiesAsked: hasContextFieldSignal(patient?.allergies),
    });
    setBlocks(prepared);
    setDegraded(isDegraded);
    setDecisionTags([]);
    setEditingDayId(null);
    setSelectedTileKey(null);
    setRawOpen(false);
    setPhase("review");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [onTranscribe, onStructure, motifChoisi, motifRawPatient, dossierState, checklistBase, firstConsultation, patient?.allergies]);

  const startListen = useCallback(async () => {
    if (!consent) return;
    setDictError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        stopStream();
        runStructuring(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setElapsed(0);
      elapsedRef.current = 0;
      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setElapsed(elapsedRef.current);
      }, 1000);
      setPhase("listen");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setDictError(buildDictationAccessError(err));
    }
  }, [consent, runStructuring, stopStream]);

  const stopListen = useCallback(() => {
    clearInterval(timerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    else stopStream();
  }, [stopStream]);

  // ---- édition des blocs ----
  const updateBlock = useCallback((id, patch) => {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  }, []);

  const confirmDayBlock = useCallback((id) => {
    updateBlock(id, { confirmed: true, status: "confirme" });
  }, [updateBlock]);

  const okDayBlock = useCallback((id, draft) => {
    setBlocks((prev) => prev.map((b) => {
      if (b.id !== id) return b;
      const text = String(draft || "").trim();
      const changed = text !== String(b.text || "").trim();
      return { ...b, text, confirmed: true, status: changed ? "modifie" : (b.critical ? "confirme" : b.status) };
    }));
    setEditingDayId(null);
    setConfirmDeleteId(null);
  }, []);

  const deleteDayBlock = useCallback((id) => {
    // Aucune action destructrice silencieuse : premier tap = demande de confirmation.
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      return;
    }
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    setEditingDayId(null);
    setConfirmDeleteId(null);
    showToast("Bloc supprimé");
  }, [confirmDeleteId, showToast]);

  const moveDayBlock = useCallback((id, targetField) => {
    setBlocks((prev) => {
      const source = prev.find((b) => b.id === id);
      if (!source || !DAY_FIELDS.includes(targetField)) return prev;
      const target = prev.find((b) => b.dest === "day" && b.field === targetField);
      const next = prev.filter((b) => b.id !== id);
      if (target) {
        return next.map((b) => {
          if (b.id !== target.id) return b;
          const mergedText = [String(b.text || "").trim(), String(source.text || "").trim()]
            .filter(Boolean)
            .join("\n");
          return {
            ...b,
            text: mergedText,
            status: "modifie",
            // Déplacer vers un bloc critique le repasse "à confirmer".
            confirmed: b.critical ? false : b.confirmed,
            sourceSpans: [...(b.sourceSpans || []), ...(source.sourceSpans || [])],
          };
        });
      }
      const meta = {
        impression: { critical: true }, decision: { critical: true },
      }[targetField] || { critical: false };
      next.push({
        ...source,
        id: `${targetField}-moved-${Date.now()}`,
        field: targetField,
        label: FIELD_LABELS[targetField],
        critical: meta.critical,
        confirmed: !meta.critical,
        status: "modifie",
      });
      return next;
    });
    setEditingDayId(null);
    setConfirmDeleteId(null);
  }, []);

  // ---- tuiles fiche patient ----
  const tiles = useMemo(() => buildDossierTiles(blocks), [blocks]);
  const selectedTile = tiles.find((t) => t.key === selectedTileKey) || null;

  const openTile = useCallback((tile) => {
    if (tile.calc) return;
    setSelectedTileKey(tile.key);
    setTileDraft(tile.status === "non_renseigne" || tile.value === "À renseigner" ? "" : tile.value);
  }, []);

  const closeTileEditor = useCallback(() => {
    setSelectedTileKey(null);
    setTileDraft("");
  }, []);

  const applyMesureEdit = useCallback((key, rawValue) => {
    setBlocks((prev) => prev.map((b) => {
      if (b.field !== "mesures" || b.dest !== "dossier") return b;
      const structured = { ...(b.structured || {}) };
      const numeric = Number(String(rawValue || "").replace(",", ".").replace(/[^\d.]/g, ""));
      const prop = key === "poids" ? "poids_kg" : "taille_cm";
      structured[prop] = Number.isFinite(numeric) && numeric > 0 ? numeric : null;
      const imc = computeImcFrontend(structured.poids_kg, structured.taille_cm);
      structured.imc = imc;
      const parts = [];
      if (structured.poids_kg != null) parts.push(`Poids ${String(structured.poids_kg).replace(".", ",")} kg`);
      if (structured.taille_cm != null) parts.push(`taille ${String(structured.taille_cm).replace(".", ",")} cm`);
      return {
        ...b,
        structured,
        text: parts.join(", ") || NR_TEXT,
        status: "modifie",
        confirmed: true,
        extra: imc != null ? `IMC calculé : ${String(imc).replace(".", ",")}` : null,
      };
    }));
  }, []);

  const tileOk = useCallback(() => {
    if (!selectedTile) return;
    const value = String(tileDraft || "").trim();
    if (!value) {
      closeTileEditor();
      return;
    }
    if (selectedTile.key === "poids" || selectedTile.key === "taille") {
      applyMesureEdit(selectedTile.key, value);
    } else {
      updateBlock(selectedTile.blockId, {
        text: value,
        status: "modifie",
        confirmed: true,
        synthetic: false,
      });
    }
    closeTileEditor();
  }, [selectedTile, tileDraft, applyMesureEdit, updateBlock, closeTileEditor]);

  const tileConfirm = useCallback(() => {
    if (!selectedTile) return;
    updateBlock(selectedTile.blockId, { confirmed: true, status: "confirme" });
    closeTileEditor();
  }, [selectedTile, updateBlock, closeTileEditor]);

  const tileNonRenseigne = useCallback(() => {
    if (!selectedTile) return;
    if (selectedTile.key === "poids" || selectedTile.key === "taille") {
      applyMesureEdit(selectedTile.key, "");
    } else {
      updateBlock(selectedTile.blockId, {
        status: "non_renseigne",
        confirmed: true,
      });
    }
    closeTileEditor();
    showToast("Marqué non renseigné");
  }, [selectedTile, applyMesureEdit, updateBlock, closeTileEditor, showToast]);

  // ---- état d'avancement (un seul endroit : la note au-dessus du CTA) ----
  const { day: dayBlocks, dossier: dossierBlocks } = useMemo(() => splitBlocks(blocks), [blocks]);
  const pendingLabels = useMemo(() => pendingCriticalLabels(blocks), [blocks]);
  const checklist = useMemo(
    () => markChecklistCaptured(checklistBase, phase === "review" || phase === "done" ? dossierBlocks.filter((b) => !b.synthetic) : []),
    [checklistBase, dossierBlocks, phase],
  );
  const capturedCount = checklist.filter((c) => c.captured).length;
  const hasDossierSection = dossierBlocks.length > 0;
  const dossierBlocksToSave = dossierBlocks.filter(
    (b) => !b.synthetic || b.status === "non_renseigne" || b.status === "modifie",
  );

  const knownAllergy = isDossierFieldKnown(patient?.allergies) && !isKnownNegative(patient?.allergies);

  const busy = savingLocal || saving;

  const handleSave = useCallback(async () => {
    if (pendingLabels.length || busy) return;
    const payload = buildConsultationPayloadFromBlocks({
      blocks,
      decisionTags,
      date: consultDate,
      appointmentId: String(initialDraft?.appointment_id || ""),
      motifSource,
      motifRawPatient,
      durationSeconds: elapsedRef.current || null,
      degraded,
    });
    setSavingLocal(true);
    setSaveError("");
    try {
      await onSave(payload);
      setSavedSummary({
        // Figé au moment de l'enregistrement : le rechargement du patient après
        // sauvegarde fait passer is_first_consultation à false, pas l'écran done.
        firstConsultation,
        motif: payload.motif,
        impression: payload.impression_clinique || "—",
        decision: payload.conduite_a_tenir?.suivi?.consignes || "—",
        dossierItems: dossierBlocksToSave.map((b) => ({
          label: b.label || FIELD_LABELS[b.field],
          value: b.status === "non_renseigne" ? NR_TEXT : b.text,
        })),
      });
      // La transcription brute est un brouillon : jamais conservée après enregistrement.
      setTranscript("");
      setPhase("done");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setSaveError(String(err?.message || "Impossible d'enregistrer la consultation."));
    } finally {
      setSavingLocal(false);
    }
  }, [
    pendingLabels.length, busy, blocks, decisionTags, consultDate, initialDraft?.appointment_id,
    motifSource, motifRawPatient, degraded, onSave, dossierBlocksToSave, firstConsultation,
  ]);

  // ---- CTA unique ----
  let ctaLabel = "Commencer la dictée";
  let ctaDisabled = !consent;
  let ctaClass = "bg-[#009CA4] shadow-[0_12px_28px_rgba(0,156,164,0.28)]";
  let note = consent
    ? "Un seul geste — ensuite, regardez votre patient"
    : "Activez l'accord patient pour commencer";
  let noteClass = "text-[#98A2B3]";

  if (phase === "listen") {
    ctaLabel = "Terminer la dictée";
    ctaDisabled = false;
    ctaClass = "bg-[#0A1628] shadow-[0_12px_28px_rgba(10,22,40,0.24)]";
    note = "Patient informé · dictée en cours";
  } else if (phase === "structuring") {
    ctaLabel = "Terminer la dictée";
    ctaDisabled = true;
    ctaClass = "bg-[#0A1628]";
    note = "UWi répartit votre dictée…";
  } else if (phase === "review") {
    ctaLabel = dossierBlocksToSave.length ? "Enregistrer consultation + dossier" : "Enregistrer la consultation";
    ctaDisabled = pendingLabels.length > 0 || busy;
    ctaClass = "bg-[#009CA4] shadow-[0_12px_28px_rgba(0,156,164,0.28)]";
    if (busy) {
      note = "Enregistrement…";
    } else if (saveError) {
      note = saveError;
      noteClass = "text-[#D92D20]";
    } else if (pendingLabels.length) {
      note = `${pendingLabels.length} à confirmer : ${pendingLabels.join(", ")}`;
      noteClass = "text-[#9A5B13]";
    } else {
      note = dossierBlocksToSave.length
        ? "Tout est confirmé — la note et la fiche patient seront enregistrées"
        : "Tout est confirmé — la note du jour sera enregistrée";
      noteClass = "text-[#12805C]";
    }
  } else if (phase === "done") {
    ctaLabel = "Retour au dossier";
    ctaDisabled = false;
    ctaClass = "border-[1.5px] border-[#009CA4] bg-white !text-[#087981] shadow-none";
    note = "";
  } else if (phase === "prep" && dictError) {
    note = dictError;
    noteClass = "text-[#D92D20]";
  }

  const onCta = () => {
    if (ctaDisabled) return;
    if (phase === "prep") startListen();
    else if (phase === "listen") stopListen();
    else if (phase === "review") handleSave();
    else if (phase === "done") onClose?.();
  };

  const patientName = String(patient?.nom || "Patient");
  const patientAge = Number(patient?.age) > 0 ? `${patient.age} ans` : "";
  // Le patient est rechargé après enregistrement (is_first_consultation passe à
  // false) : sur l'écran done, le badge suit la valeur figée à la sauvegarde.
  const showFirstBadge = phase === "done" && savedSummary
    ? Boolean(savedSummary.firstConsultation)
    : firstConsultation;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[560px] flex-col text-[#101828]">
      {/* ---- header ---- */}
      <header className="sticky top-0 z-20 border-b border-[#EAECF0]/90 bg-[#F7F9FA]/90 px-4 pb-2.5 pt-3.5 backdrop-blur-xl">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-[19px] font-extrabold tracking-[-0.03em] text-[#0A1628]">{patientName}</span>
          <span className="text-[13px] font-semibold text-[#98A2B3]">
            {[patientAge, heroTime].filter(Boolean).join(" · ")}
          </span>
          {showFirstBadge ? (
            <span className="rounded-full bg-[#0A1628] px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.04em] text-white">
              1re consultation
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 text-[13px] font-extrabold text-[#087981]">{PHASE_LABELS[phase]}</div>
      </header>

      <main className="flex-1 px-4 pb-[132px]">
        {/* ================= MOMENT 1 : PREP ================= */}
        {phase === "prep" ? (
          <section className="flex flex-col gap-3 pt-4">
            <div className="px-2 pb-3.5 pt-6 text-center">
              <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-[#EAECF0] bg-white px-3 py-2 text-[13px] font-bold text-[#475467] shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
                Motif · <strong className="truncate font-extrabold text-[#101828]">{motifHero}</strong>
              </div>
              <div className="mt-7">
                <Orb active={consent} onClick={startListen} label="Commencer la dictée" />
              </div>
              <h1 className="mt-6 text-[30px] font-black leading-[1.05] tracking-[-0.055em] text-[#0A1628]">
                {consent ? "Prêt à dicter" : "Avant de dicter"}
              </h1>
              <p className="mx-auto mt-2 max-w-[350px] text-[15px] leading-normal text-[#475467]">
                {consent
                  ? "Touchez le micro. Dictez la consultation ET les antécédents — UWi triera."
                  : "Confirmez que le patient est informé, puis touchez le micro."}
              </p>
            </div>

            {checklistBase.length ? (
              <div className="rounded-[20px] border border-[#EAECF0] bg-white p-4 shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
                <div className="text-[15px] font-black text-[#0A1628]">
                  {firstConsultation ? "Dossier à construire" : "Dossier à compléter"}
                </div>
                <div className="mb-3 mt-0.5 text-[13px] text-[#475467]">
                  {firstConsultation
                    ? "Premier passage : ce que vous dictez ira aussi nourrir la fiche patient."
                    : "Ces éléments manquent au dossier : ce que vous dictez ira aussi nourrir la fiche patient."}
                </div>
                <div className="flex flex-wrap gap-2">
                  {checklist.map((item) => <ChecklistChip key={item.key} item={item} />)}
                </div>
              </div>
            ) : null}

            {knownAllergy ? (
              <div className="rounded-2xl border-[1.5px] border-[#F6C6C2] bg-[#FFF2F2] px-4 py-3.5 text-sm font-extrabold text-[#D92D20]">
                ⚠ Allergie connue : {String(patient.allergies)}
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => setConsent((v) => !v)}
              className={[
                "flex min-h-[56px] w-full select-none items-center gap-3 rounded-2xl border-[1.5px] p-3.5 text-left transition",
                consent ? "border-[#B5E4D3] bg-[#EBF9F3]" : "border-[#EAECF0] bg-white",
              ].join(" ")}
              aria-pressed={consent}
            >
              <span
                className={[
                  "relative h-7 w-[46px] shrink-0 rounded-full transition",
                  consent ? "bg-[#12805C]" : "bg-[#D0D5DD]",
                ].join(" ")}
              >
                <span
                  className={[
                    "absolute top-[3px] h-[22px] w-[22px] rounded-full bg-white shadow transition-all",
                    consent ? "left-[21px]" : "left-[3px]",
                  ].join(" ")}
                />
              </span>
              <span className={["text-[15px] font-bold", consent ? "text-[#12805C]" : "text-[#475467]"].join(" ")}>
                {consent ? "Patient informé — dictée autorisée" : "Patient informé de la dictée"}
              </span>
            </button>

            {motifSuggestions.length ? (
              <div className="overflow-hidden rounded-[20px] border border-[#EAECF0] bg-white">
                <button
                  type="button"
                  onClick={() => setMotifSheetOpen((v) => !v)}
                  className="flex min-h-[52px] w-full items-center justify-between gap-2.5 px-4 py-3.5 text-left text-[14.5px] font-extrabold text-[#101828]"
                >
                  <span>Reformuler le motif</span>
                  <span className={["text-[#98A2B3] transition-transform", motifSheetOpen ? "rotate-180" : ""].join(" ")}>▾</span>
                </button>
                {motifSheetOpen ? (
                  <div className="border-t border-[#EAECF0] p-3">
                    {motifSuggestions.map((s) => {
                      const on = motifChoisi === s;
                      return (
                        <button
                          key={s}
                          type="button"
                          onClick={() => {
                            setMotifChoisi(on ? null : s);
                            setMotifSource(on ? "praticien" : "uwi_suggestion");
                            setMotifSheetOpen(false);
                          }}
                          className={[
                            "mb-2 block min-h-[48px] w-full rounded-[14px] border-[1.5px] p-3.5 text-left text-[15px] last:mb-0",
                            on
                              ? "border-[#009CA4] bg-[#E8F7F7] font-extrabold text-[#087981]"
                              : "border-[#EAECF0] bg-white font-semibold text-[#101828]",
                          ].join(" ")}
                        >
                          {s}{on ? " ✓" : ""}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}

            {pendingBlob ? (
              <button
                type="button"
                onClick={() => runStructuring(pendingBlob)}
                className="min-h-[48px] rounded-2xl border-[1.5px] border-[#009CA4] bg-white px-4 py-3 text-sm font-black text-[#087981]"
              >
                Réessayer avec la dictée conservée
              </button>
            ) : null}
          </section>
        ) : null}

        {/* ================= MOMENT 2 : LISTEN (+ structuring) ================= */}
        {phase === "listen" || phase === "structuring" ? (
          <section className="flex flex-col items-center px-2 pb-2 pt-9 text-center">
            <Orb active={phase === "listen"} size="sm" />
            <div className="mt-5 text-[48px] font-black leading-none tracking-[-0.07em] text-[#0A1628] tabular-nums">
              {formatElapsed(elapsed)}
            </div>
            <div className="mt-2 text-[22px] font-black tracking-[-0.045em]">
              {phase === "structuring" ? "UWi répartit votre dictée" : "UWi écoute"}
            </div>
            <div className="mt-1.5 max-w-[340px] text-[14.5px] text-[#475467]">
              {phase === "structuring"
                ? "Quelques secondes — la note du jour et la fiche patient se préparent."
                : "Parlez naturellement. Un coup d'œil ci-dessous : ce qui reste à demander."}
            </div>

            {checklist.length ? (
              <div className="mt-6 w-full rounded-[20px] border border-[#EAECF0] bg-white p-4 text-left shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
                <div className="flex items-baseline justify-between gap-2.5">
                  <div className="text-[15px] font-black text-[#0A1628]">Recueil dossier</div>
                  <span className="rounded-full border border-[#CDECEC] bg-[#E8F7F7] px-2 py-0.5 text-xs font-black text-[#087981]">
                    {capturedCount}/{checklist.length}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {checklist.map((item) => <ChecklistChip key={item.key} item={item} />)}
                </div>
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => setPeekOpen((v) => !v)}
              className="mt-3 flex min-h-[52px] w-full items-center justify-between rounded-2xl border border-[#EAECF0] bg-white p-3.5 text-left text-sm font-extrabold text-[#101828]"
            >
              <span>Voir les derniers mots</span>
              <span className={["text-[#98A2B3] transition-transform", peekOpen ? "rotate-180" : ""].join(" ")}>▾</span>
            </button>
            {peekOpen ? (
              <div className="w-full rounded-b-2xl border border-t-0 border-[#EAECF0] bg-white p-3.5 text-left text-[13.5px] leading-relaxed text-[#475467]">
                La transcription s'affichera d'un bloc à la relecture — Dictée UWi traite l'audio à la fin.
              </div>
            ) : null}
            <div className="mt-3 text-[12.5px] text-[#98A2B3]">
              Brouillon — rien n'est enregistré sans votre validation.
            </div>
          </section>
        ) : null}

        {/* ================= MOMENT 3 : REVIEW ================= */}
        {phase === "review" ? (
          <section className="flex flex-col gap-3 pt-4">
            <div className="px-0.5 text-sm leading-normal text-[#475467]">
              {degraded ? (
                <>UWi n'a pas pu structurer — la dictée est conservée telle quelle, éditable ci-dessous.</>
              ) : (
                <>
                  UWi a séparé la note du jour et le socle patient. Touchez une tuile ou un bloc pour
                  corriger — les éléments <b className="text-[#9A5B13]">colorés</b> attendent votre confirmation.
                </>
              )}
            </div>

            {transcript ? (
              <div>
                <button
                  type="button"
                  onClick={() => setRawOpen((v) => !v)}
                  className={[
                    "flex min-h-[52px] w-full items-center justify-between gap-2.5 border border-[#EAECF0] bg-white px-4 py-[15px] text-left text-[14.5px] font-extrabold text-[#101828] shadow-[0_8px_22px_rgba(16,24,40,0.05)]",
                    rawOpen ? "rounded-t-[20px]" : "rounded-[20px]",
                  ].join(" ")}
                >
                  <span>Voir la transcription brute</span>
                  <span className={["text-[#98A2B3] transition-transform", rawOpen ? "rotate-180" : ""].join(" ")}>▾</span>
                </button>
                {rawOpen ? (
                  <div className="rounded-b-[20px] border border-t-0 border-[#EAECF0] bg-white p-4 text-sm leading-relaxed text-[#475467]">
                    {transcript}
                    <div className="mt-2 text-xs text-[#98A2B3]">
                      Brouillon temporaire — non conservé après enregistrement.
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* --- Note du jour : cartes empilées --- */}
            <div className="flex items-center gap-2 px-0.5 pt-2">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-[10px] bg-[#E8F7F7] text-sm font-black text-[#087981]">◧</span>
              <div>
                <div className="text-[15px] font-black text-[#0A1628]">Note du jour</div>
                <div className="text-[12.5px] font-semibold text-[#98A2B3]">La consultation d'aujourd'hui</div>
              </div>
            </div>
            <div className="flex flex-col gap-3">
              {dayBlocks.map((block) => (
                <DayBlockCard
                  key={block.id}
                  block={block}
                  editing={editingDayId === block.id}
                  onStartEdit={(id) => {
                    setEditingDayId(id);
                    setConfirmDeleteId(null);
                  }}
                  onConfirm={confirmDayBlock}
                  onOk={okDayBlock}
                  onDelete={deleteDayBlock}
                  confirmingDelete={confirmDeleteId === block.id}
                  onMove={moveDayBlock}
                  moveTargets={DAY_FIELDS.filter((f) => f !== block.field)}
                />
              ))}
              {!dayBlocks.length ? (
                <div className="rounded-[20px] border border-dashed border-[#EAECF0] bg-white p-4 text-sm text-[#475467]">
                  Aucun contenu pour la note du jour.
                </div>
              ) : null}
            </div>

            {/* --- Fiche patient : grille interactive (LA zone d'édition) --- */}
            {hasDossierSection ? (
              <>
                <div className="flex items-center gap-2 px-0.5 pt-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-[10px] bg-[#0A1628] text-sm font-black text-white">＋</span>
                  <div>
                    <div className="text-[15px] font-black text-[#0A1628]">Fiche patient</div>
                    <div className="text-[12.5px] font-semibold text-[#98A2B3]">
                      Durable — reprise à chaque consultation et par Clara. Touchez une tuile pour corriger.
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 overflow-hidden rounded-[20px] border border-[#EAECF0] bg-white shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
                  {tiles.map((tile, idx) => {
                    const needs = !tile.calc && !tile.confirmed;
                    const isSelected = selectedTileKey === tile.key;
                    const okState = !tile.calc && tile.confirmed && tile.status !== "non_renseigne";
                    const lastRow = idx >= tiles.length - (tiles.length % 2 === 0 ? 2 : 1);
                    return (
                      <button
                        key={tile.key}
                        type="button"
                        onClick={() => openTile(tile)}
                        className={[
                          "relative min-h-[96px] px-4 py-3.5 text-left transition",
                          idx % 2 === 0 ? "border-r border-[#EAECF0]" : "",
                          lastRow ? "" : "border-b border-[#EAECF0]",
                          tile.calc ? "cursor-default" : "",
                          needs && tile.danger ? "bg-[#FFF2F2]" : needs ? "bg-[#FFF8EA]" : tile.status === "non_renseigne" ? "bg-[#FAFBFC]" : "bg-white",
                          isSelected ? "bg-[#E8F7F7] outline outline-2 -outline-offset-2 outline-[#009CA4]" : "",
                        ].join(" ")}
                      >
                        <div
                          className={[
                            "flex items-center gap-1.5 text-xs font-black",
                            needs && tile.danger ? "text-[#D92D20]" : needs ? "text-[#9A5B13]" : "text-[#98A2B3]",
                          ].join(" ")}
                        >
                          {tile.label}
                        </div>
                        <div
                          className={[
                            "mt-1 line-clamp-2 leading-[1.3]",
                            tile.status === "non_renseigne"
                              ? "text-sm font-semibold text-[#475467]"
                              : "text-base font-black text-[#101828]",
                          ].join(" ")}
                        >
                          {tile.value}
                        </div>
                        <div
                          className={[
                            "mt-[3px] text-[11.5px] font-extrabold",
                            okState ? "text-[#12805C]" : needs && tile.danger ? "text-[#D92D20]" : needs ? "text-[#9A5B13]" : "text-[#98A2B3]",
                          ].join(" ")}
                        >
                          {tileStatusLabel(tile)}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* panneau d'édition unique sous la grille */}
                {selectedTile ? (
                  <div className="rounded-[20px] border border-[#009CA4] bg-white p-4 shadow-[0_0_0_3px_#E8F7F7,0_8px_22px_rgba(16,24,40,0.05)]">
                    <div className="mb-2 flex items-center justify-between gap-2.5">
                      <span className="text-[13px] font-black uppercase tracking-[0.045em] text-[#087981]">
                        {selectedTile.label}
                      </span>
                      <button
                        type="button"
                        onClick={closeTileEditor}
                        className="px-2.5 py-1.5 text-[13px] font-extrabold text-[#98A2B3]"
                      >
                        Fermer ✕
                      </button>
                    </div>
                    <textarea
                      rows={1}
                      value={tileDraft}
                      onChange={(e) => setTileDraft(e.target.value)}
                      placeholder={selectedTile.status === "non_renseigne" ? NR_TEXT : ""}
                      className="block min-h-[34px] w-full resize-none border-0 bg-transparent p-0 text-base leading-normal text-[#101828] outline-none"
                    />
                    {(selectedTile.key === "poids" || selectedTile.key === "taille") ? (
                      <div className="mt-1.5 text-[12.5px] font-extrabold text-[#98A2B3]">
                        L'IMC se recalcule automatiquement.
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedTile.critical && !selectedTile.confirmed && String(tileDraft || "").trim() ? (
                        <button
                          type="button"
                          onClick={tileConfirm}
                          className="min-h-[42px] rounded-full bg-[#009CA4] px-4 py-2.5 text-sm font-black text-white shadow-[0_8px_16px_rgba(0,156,164,0.16)]"
                        >
                          Confirmer
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={tileOk}
                        className="min-h-[42px] rounded-full border-[1.5px] border-[#009CA4] bg-[#009CA4] px-3.5 py-2 text-[13px] font-extrabold text-white"
                      >
                        OK
                      </button>
                      {selectedTile.nrable && selectedTile.status !== "non_renseigne" ? (
                        <button
                          type="button"
                          onClick={tileNonRenseigne}
                          className="min-h-[42px] rounded-full border-[1.5px] border-[#CDECEC] bg-[#E8F7F7] px-3.5 py-2 text-[13px] font-extrabold text-[#087981]"
                        >
                          Non renseigné
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}

            {/* --- Décision du jour --- */}
            <div className="rounded-[20px] border border-[#EAECF0] bg-white p-4 shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
              <div className="mb-1 text-[15px] font-black text-[#0A1628]">Décision du jour</div>
              <div className="mb-3 text-[13px] text-[#475467]">
                Ces tags structurent le dossier. Ils ne remplacent pas la note.
              </div>
              <div className="flex flex-wrap gap-2">
                {DECISION_TAGS.map((tag) => {
                  const on = decisionTags.includes(tag);
                  return (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => setDecisionTags((prev) => (
                        on ? prev.filter((t) => t !== tag) : [...prev, tag]
                      ))}
                      className={[
                        "min-h-[42px] rounded-full border-[1.5px] px-3.5 py-2.5 text-sm font-extrabold",
                        on
                          ? "border-[#CDECEC] bg-[#E8F7F7] text-[#087981]"
                          : "border-[#EAECF0] bg-white text-[#475467]",
                      ].join(" ")}
                    >
                      {tag}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        ) : null}

        {/* ================= MOMENT 4 : DONE ================= */}
        {phase === "done" && savedSummary ? (() => {
          const wasFirst = Boolean(savedSummary.firstConsultation);
          const dossierCard = savedSummary.dossierItems.length ? (
            <div key="dossier" className="mt-3 w-full rounded-[20px] border border-[#EAECF0] bg-white p-4 text-left shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
              <div className="flex items-center gap-2 text-sm font-black text-[#0A1628]">
                <span>Fiche patient {wasFirst ? "créée" : "enrichie"}</span>
                <span className="rounded-full bg-[#0A1628] px-2 py-0.5 text-xs font-black text-white">
                  {savedSummary.dossierItems.length} élément{savedSummary.dossierItems.length > 1 ? "s" : ""}
                </span>
              </div>
              {savedSummary.dossierItems.map((item) => (
                <div key={item.label}>
                  <div className="mt-3 text-[13px] font-black text-[#101828]">{item.label}</div>
                  <div className="mt-0.5 text-sm leading-normal text-[#475467]">{item.value}</div>
                </div>
              ))}
            </div>
          ) : null;
          const noteCard = (
            <div key="note" className="mt-3 w-full rounded-[20px] border border-[#EAECF0] bg-white p-4 text-left shadow-[0_8px_22px_rgba(16,24,40,0.05)]">
              <div className="flex items-center gap-2 text-sm font-black text-[#087981]">Note du jour</div>
              <div className="mt-3 text-[13px] font-black text-[#101828]">Motif</div>
              <div className="mt-0.5 text-sm text-[#475467]">{savedSummary.motif}</div>
              <div className="mt-3 text-[13px] font-black text-[#101828]">Impression</div>
              <div className="mt-0.5 text-sm text-[#475467]">{savedSummary.impression}</div>
              <div className="mt-3 text-[13px] font-black text-[#101828]">Conduite</div>
              <div className="mt-0.5 text-sm text-[#475467]">{savedSummary.decision}</div>
            </div>
          );
          return (
            <section className="flex flex-col items-center px-3 pb-3 pt-12 text-center">
              <div className="grid h-[82px] w-[82px] place-items-center rounded-full bg-[#EBF9F3] text-4xl text-[#12805C] shadow-[0_12px_28px_rgba(18,128,92,0.10)]">
                ✓
              </div>
              <div className="mt-5 text-[25px] font-black tracking-[-0.05em] text-[#0A1628]">
                {wasFirst ? "Première consultation enregistrée" : "Consultation enregistrée"}
              </div>
              <div className="mb-2 mt-2 max-w-[340px] text-[15px] text-[#475467]">
                {savedSummary.dossierItems.length
                  ? `La note est dans le dossier de ${patientName} — et sa fiche patient est ${wasFirst ? "née" : "enrichie"}.`
                  : `La note est dans le dossier de ${patientName}.`}
              </div>
              {/* 1re consultation : la fiche patient créée d'abord. Ensuite : la note du jour d'abord. */}
              {wasFirst ? [dossierCard, noteCard] : [noteCard, dossierCard]}
            </section>
          );
        })() : null}
      </main>

      {/* ---- LE bouton (état d'avancement : uniquement la note ci-dessous) ---- */}
      <div className="fixed inset-x-0 bottom-0 z-[105] bg-gradient-to-b from-transparent via-[#F7F9FA]/95 to-[#F7F9FA] px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
        <div className="mx-auto flex max-w-[560px] flex-col gap-2">
          <div className={["min-h-4 text-center text-[12.5px] font-bold", noteClass].join(" ")}>{note}</div>
          <button
            type="button"
            disabled={ctaDisabled}
            onClick={onCta}
            className={[
              "min-h-[58px] w-full rounded-[18px] text-[17px] font-black tracking-[-0.01em] text-white transition active:scale-[0.985]",
              ctaDisabled ? "cursor-not-allowed bg-[#D0D5DD] shadow-none" : ctaClass,
            ].join(" ")}
          >
            {phase === "structuring" || busy ? (
              <span className="inline-flex items-center gap-2">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                {phase === "structuring" ? "Structuration…" : "Enregistrement…"}
              </span>
            ) : ctaLabel}
          </button>
        </div>
      </div>

      {toast ? (
        <div className="fixed bottom-[calc(102px+env(safe-area-inset-bottom))] left-1/2 z-[110] -translate-x-1/2 rounded-[14px] bg-[#0A1628] px-[18px] py-3 text-sm font-extrabold text-white shadow-lg">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
