import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const AppCallDetailModal = lazy(() => import("../components/AppCallDetailModal.jsx"));

function Skeleton({ height = 64, radius = 12 }) {
  return (
    <div
      style={{
        height,
        borderRadius: radius,
        background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-calls-shimmer 1.35s infinite linear",
      }}
    />
  );
}

const C = {
  teal: "#0DC991",
  tealDark: "#0AAF7A",
  tealLight: "#E8FAF4",
  tealBorder: "#A7F3D0",
  orange: "#F97316",
  orangeLight: "#FFF7ED",
  orangeBorder: "#FDBA74",
  purple: "#8B5CF6",
  purpleLight: "#F5F3FF",
  purpleBorder: "#DDD6FE",
  red: "#EF4444",
  redLight: "#FEF2F2",
  redBorder: "#FCA5A5",
  blue: "#3B82F6",
  blueLight: "#EFF6FF",
  blueBorder: "#BFDBFE",
  navy: "#0f172a",
  textMid: "#334155",
  textSoft: "#64748b",
  textFaint: "#94a3b8",
  border: "#e2e8f0",
  borderLight: "#f1f5f9",
  bg: "#f8fafc",
  card: "#ffffff",
};

const STATUS_CFG = {
  ok: { label: "Résolu", color: C.tealDark, bg: C.tealLight, border: C.tealBorder },
  missed: { label: "Manqué", color: C.red, bg: C.redLight, border: C.redBorder },
  planned: { label: "Prévu", color: C.blue, bg: C.blueLight, border: C.blueBorder },
  callback: { label: "À rappeler", color: C.orange, bg: C.orangeLight, border: C.orangeBorder },
};

const INTENT_CFG = {
  rdv: { label: "Prise de RDV", icon: "📅", color: C.tealDark, bg: C.tealLight },
  cancel: { label: "Annulation", icon: "❌", color: C.red, bg: C.redLight },
  info: { label: "Information", icon: "💬", color: C.blue, bg: C.blueLight },
  hours: { label: "Horaires", icon: "🕒", color: C.orange, bg: C.orangeLight },
  urgent: { label: "Urgence", icon: "🚨", color: "#DC2626", bg: C.redLight },
  reschedule: { label: "Reprogrammation", icon: "🔁", color: C.purple, bg: C.purpleLight },
};

function resolveStatusKey(call) {
  if ((call?.followup_state || "") === "callback") return "callback";
  if (call?.status === "ABANDONED" || call?.status === "TRANSFERRED") return "missed";
  if (call?.contextual_action?.kind === "followup_callback") return "planned";
  return "ok";
}

function resolveIntentKey(call) {
  const s = String(call?.summary || "").toLowerCase();
  if (call?.reason_category === "urgency") return "urgent";
  if (call?.reason_category === "agenda" || call?.status === "CONFIRMED") {
    if (/annul/.test(s)) return "cancel";
    if (/reprogramm|déplac|deplac/.test(s)) return "reschedule";
    return "rdv";
  }
  if (/horaire/.test(s)) return "hours";
  return "info";
}

function getDialable(value) {
  const raw = String(value || "").trim();
  if (!raw || /num[eé]ro non identifi[eé]/i.test(raw)) return "";
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("00")) return `+${cleaned.slice(2)}`;
  return cleaned;
}

function getDisplayPhone(value) {
  return String(value || "").trim() || "Numéro non identifié";
}

function fmtDuration(call) {
  const txt = String(call?.duration || "").trim();
  if (txt && txt !== "—" && txt !== "-") return txt;
  const sec = Number(call?.duration_sec);
  if (Number.isFinite(sec) && sec >= 0) {
    return `${Math.floor(sec / 60)}'${String(sec % 60).padStart(2, "0")}`;
  }
  const mins = Number(call?.duration_min);
  if (Number.isFinite(mins) && mins >= 0) return `${Math.floor(mins)}'00`;
  const s = String(call?.started_at || "").trim();
  const e = String(call?.last_event_at || "").trim();
  if (s && e) {
    const diff = Math.floor((new Date(e).getTime() - new Date(s).getTime()) / 1000);
    if (diff >= 0) return `${Math.floor(diff / 60)}'${String(diff % 60).padStart(2, "0")}`;
  }
  return "0'00";
}

function parseTs(value) {
  const t = new Date(String(value || "")).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function extractRdv(call) {
  const booking = call?.booking || call?.raw?.booking;
  if (booking?.start_iso || booking?.slot_label) {
    const start = booking?.start_iso ? new Date(booking.start_iso) : null;
    const valid = start && !Number.isNaN(start.getTime()) ? start : null;
    return {
      date: valid ? valid.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }) : booking?.slot_label || "Date à confirmer",
      time: valid ? valid.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "—",
      type: booking?.motif || call?.reason_label || "Consultation",
    };
  }
  const summary = String(call?.summary || "");
  if (!(call?.status === "CONFIRMED" || call?.reason_category === "agenda" || /rdv|rendez-vous/i.test(summary))) return null;
  const dateMatch = summary.match(/\b(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\b/);
  const timeMatch = summary.match(/(?:à|a)\s*(\d{1,2}(?::\d{2}|h\d{0,2})?)/i) || summary.match(/\b(\d{1,2}:\d{2})\b/);
  return {
    date: dateMatch?.[1] || "Date à confirmer",
    time: (timeMatch?.[1] || call?.time || "—").replace(/^(\d{1,2})h$/, "$1h00"),
    type: call?.reason_label || "Consultation",
  };
}

function buildTranscriptLines(transcript) {
  const text = String(transcript || "").trim();
  if (!text) return [];
  return text.split(/\n+/).map((l) => l.trim()).filter(Boolean).map((line, i) => {
    if (/^(agent|uwi|assistant)\s*:/i.test(line)) return { speaker: "agent", text: line.replace(/^[^:]+:\s*/i, "") };
    if (/^(patient|client|caller|appelant)\s*:/i.test(line)) return { speaker: "patient", text: line.replace(/^[^:]+:\s*/i, "") };
    return { speaker: i % 2 === 0 ? "patient" : "agent", text: line };
  });
}

function deriveAiScore(call) {
  const confidence = call?.status === "CONFIRMED" ? 94 : call?.status === "FAQ" ? 86 : call?.status === "TRANSFERRED" ? 62 : call?.status === "ABANDONED" ? 38 : 72;
  const sentiment = call?.reason_category === "urgency" ? "négatif" : call?.status === "CONFIRMED" ? "positif" : "neutre";
  const resolved = Boolean(call?.status === "CONFIRMED" || call?.status === "FAQ" || call?.followup_state === "processed");
  return { confidence, sentiment, resolved };
}

function normalize(call) {
  const patient = call?.patient || {};
  const stKey = resolveStatusKey(call);
  const intKey = resolveIntentKey(call);
  const hasPatientValidatedFile = String(patient?.validated_name || "").trim().length >= 2;
  return {
    id: call?.call_id || call?.id || "",
    name: patient?.display_name || call?.patient_name || "Patient",
    phone: getDisplayPhone(call?.customer_number),
    dialablePhone: getDialable(call?.customer_number),
    time: call?.time || "—",
    durationFmt: fmtDuration(call),
    status: stKey,
    statusUi: STATUS_CFG[stKey] || STATUS_CFG.ok,
    intent: intKey,
    intentUi: INTENT_CFG[intKey] || INTENT_CFG.info,
    aiHandled: call?.status !== "ABANDONED",
    recalled: call?.followup_state === "processed",
    summary: call?.summary || "",
    rdv: extractRdv(call),
    aiScore: deriveAiScore(call),
    transcript: [],
    patient,
    hasPatientValidatedFile,
    booking: call?.booking || null,
    sortValue: parseTs(call?.last_event_at || call?.started_at),
    raw: call,
  };
}

function normalizeDetail(detail, fallback) {
  const base = detail || fallback?.raw || {};
  const patient = base?.patient || fallback?.patient || {};
  const stKey = resolveStatusKey(base);
  const intKey = resolveIntentKey(base);
  const hasPatientValidatedFile = String(patient?.validated_name || "").trim().length >= 2;
  return {
    id: base?.call_id || fallback?.id || "",
    name: patient?.display_name || fallback?.name || base?.patient_name || "Patient",
    phone: getDisplayPhone(base?.customer_number || fallback?.phone),
    dialablePhone: getDialable(base?.customer_number || fallback?.dialablePhone),
    time: base?.started_time || fallback?.time || "—",
    durationFmt: fmtDuration(base) || fallback?.durationFmt || "0'00",
    status: stKey,
    statusUi: STATUS_CFG[stKey] || STATUS_CFG.ok,
    intent: intKey,
    intentUi: INTENT_CFG[intKey] || INTENT_CFG.info,
    aiHandled: base?.status !== "ABANDONED",
    recalled: base?.followup_state === "processed",
    summary: base?.summary || fallback?.summary || "Aucun résumé disponible.",
    rdv: extractRdv(base) || fallback?.rdv || null,
    aiScore: deriveAiScore(base),
    transcript: buildTranscriptLines(base?.transcript),
    patient,
    hasPatientValidatedFile,
    booking: base?.booking || fallback?.booking || null,
    sortValue: parseTs(base?.last_event_at || base?.started_at || fallback?.raw?.last_event_at || fallback?.raw?.started_at),
    raw: base,
  };
}

function normalizePayload(payload) {
  const src = Array.isArray(payload?.calls) ? payload.calls : Array.isArray(payload?.items) ? payload.items : [];
  return { ...(payload && typeof payload === "object" ? payload : {}), calls: src, total: Number.isFinite(Number(payload?.total)) ? Number(payload.total) : src.length };
}

function CallRow({ call, onOpen, onRecall }) {
  const intent = INTENT_CFG[call.intent] || INTENT_CFG.info;
  const status = call.statusUi;
  const needsAction = (call.status === "missed" || call.status === "callback") && !call.recalled;

  return (
    <div
      className="call-row"
      onClick={() => onOpen(call)}
      style={S.row}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen(call); }}
    >
      <div style={{ ...S.statusDot, background: status.color }} />

      <div style={S.intentCol}>
        <span style={S.intentIcon}>{intent.icon}</span>
      </div>

      <div style={S.mainCol}>
        <div style={S.nameRow}>
          <span style={S.name}>{call.name}</span>
          <span style={call.hasPatientValidatedFile ? S.patientFileOk : S.patientFileTodo}>
            {call.hasPatientValidatedFile ? "Fiche OK" : "Sans fiche"}
          </span>
          {call.aiHandled && <span style={S.iaBadge}>IA</span>}
          {call.intent === "urgent" && <span style={S.urgentBadge}>URGENT</span>}
          {call.rdv && <span style={S.rdvBadge}>RDV pris</span>}
        </div>
        <div style={S.summaryRow}>
          <span style={{ ...S.intentLabel, color: intent.color, background: intent.bg }}>{intent.label}</span>
          {call.summary && <span style={S.summary}>{call.summary}</span>}
        </div>
      </div>

      <div style={S.metaCol}>
        <span style={S.time}>{call.time}</span>
        <span style={S.duration}>{call.durationFmt}</span>
      </div>

      <div style={S.statusCol}>
        <span style={{ ...S.statusBadge, color: status.color, background: status.bg, borderColor: status.border }}>
          {status.label}
        </span>
        {needsAction && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onRecall(call); }}
            style={S.recallBtn}
          >
            Rappeler
          </button>
        )}
      </div>
    </div>
  );
}

export default function AppCalls() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState(30);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("all");
  const [payload, setPayload] = useState({ calls: [], total: 0 });
  const [selectedCallId, setSelectedCallId] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [callDetail, setCallDetail] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [followupNotes, setFollowupNotes] = useState("");
  const [followupLoading, setFollowupLoading] = useState(false);
  const [patientNameDraft, setPatientNameDraft] = useState("");
  const [patientEmailDraft, setPatientEmailDraft] = useState("");
  const [patientInitialNoteDraft, setPatientInitialNoteDraft] = useState("");
  const [patientDocFiles, setPatientDocFiles] = useState([]);
  const [patientSaving, setPatientSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api.tenantGetCalls(`?limit=50&days=${days}&compact=1`)
      .then((data) => { if (!cancelled) setPayload(normalizePayload(data)); })
      .catch((e) => { if (!cancelled) setError(e?.message || "Impossible de charger les appels."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  useEffect(() => {
    if (!selectedCallId) {
      setCallDetail(null);
      setDetailError("");
      setFollowupNotes("");
      setPatientNameDraft("");
      setPatientEmailDraft("");
      setPatientInitialNoteDraft("");
      setPatientDocFiles([]);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError("");
    api.tenantGetCallDetail(selectedCallId)
      .then((data) => {
        if (!cancelled) {
          setCallDetail(data || null);
          setFollowupNotes(data?.followup_notes || "");
          setPatientNameDraft(data?.patient?.validated_name || data?.patient?.raw_name || "");
          setPatientEmailDraft(data?.patient?.email || "");
          setPatientInitialNoteDraft("");
          setPatientDocFiles([]);
        }
      })
      .catch((e) => { if (!cancelled) setDetailError(e?.message || "Impossible de charger le détail."); })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [selectedCallId]);

  useEffect(() => { if (!actionMessage) return; const t = setTimeout(() => setActionMessage(""), 2200); return () => clearTimeout(t); }, [actionMessage]);
  useEffect(() => { setDays(tab === "today" ? 1 : tab === "week" ? 7 : 30); }, [tab]);

  const calls = useMemo(() => (payload?.calls || []).map(normalize).sort((a, b) => b.sortValue - a.sortValue), [payload]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return calls.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (q && ![c.name, c.phone, c.summary].join(" ").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [calls, statusFilter, search]);

  const missedCount = useMemo(() => calls.filter((c) => (c.status === "missed" || c.status === "callback") && !c.recalled).length, [calls]);

  const selectedSummary = useMemo(() => calls.find((c) => c.id === selectedCallId) || null, [calls, selectedCallId]);
  const detailModel = useMemo(() => normalizeDetail(callDetail, selectedSummary), [callDetail, selectedSummary]);

  async function persistFollowup(callId, nextState, notesVal = "", msg = "") {
    if (!callId) return;
    setFollowupLoading(true);
    try {
      const data = await api.tenantUpdateCallFollowup(callId, { followup_state: nextState, notes: notesVal || "" });
      setCallDetail((prev) => prev && (prev.call_id || selectedCallId) === callId ? { ...prev, followup_state: data?.followup_state || nextState, followup_notes: data?.followup_notes || "" } : prev);
      setPayload((prev) => ({ ...prev, calls: (prev?.calls || []).map((c) => (c.call_id || c.id) === callId ? { ...c, followup_state: data?.followup_state || nextState } : c) }));
      if ((callDetail?.call_id || selectedCallId) === callId) setFollowupNotes(data?.followup_notes || "");
      setActionMessage(msg || (nextState === "callback" ? "Appel marqué à rappeler." : nextState === "processed" ? "Appel marqué comme traité." : "Suivi réinitialisé."));
    } catch (e) {
      setActionMessage(e?.message || "Impossible d'enregistrer le suivi.");
    } finally {
      setFollowupLoading(false);
    }
  }

  async function saveFollowupState(nextState, notes = followupNotes) {
    if (!selectedCallId) return;
    await persistFollowup(selectedCallId, nextState, notes);
  }

  async function savePatientName() {
    if (!selectedCallId) return;
    const value = String(patientNameDraft || "").trim();
    if (value.length < 2) { setActionMessage("Le nom doit contenir au moins 2 caractères."); return; }
    setPatientSaving(true);
    try {
      const data = await api.tenantUpdateCallPatient(selectedCallId, { validated_name: value, raw_name: callDetail?.patient?.raw_name || selectedSummary?.patient?.raw_name || "" });
      const next = data?.patient || {};
      const phone = next?.phone || callDetail?.patient?.phone || selectedSummary?.patient?.phone || "";
      let emailSaved = false;
      let noteSaved = false;
      let docsSaved = 0;
      if (phone && String(patientEmailDraft || "").trim()) {
        await api.tenantUpdatePatient(phone, { email: String(patientEmailDraft || "").trim() });
        emailSaved = true;
      }
      if (phone && String(patientInitialNoteDraft || "").trim()) {
        await api.tenantCreatePatientNote(phone, { text: String(patientInitialNoteDraft || "").trim(), author: "Praticien" });
        noteSaved = true;
      }
      if (phone && patientDocFiles.length > 0) {
        for (const file of patientDocFiles) {
          // Upload séquentiel pour simplifier le feedback et éviter les erreurs réseau burst.
          await api.tenantUploadPatientDocument(phone, file);
          docsSaved += 1;
        }
      }
      setCallDetail((prev) => prev ? { ...prev, patient: next, patient_name: next.display_name || value } : prev);
      setPayload((prev) => ({ ...prev, calls: (prev?.calls || []).map((c) => (c.call_id || c.id) === selectedCallId ? { ...c, patient: next, patient_name: next.display_name || value } : c) }));
      setPatientNameDraft(next?.display_name || value);
      setPatientInitialNoteDraft("");
      setPatientDocFiles([]);
      setActionMessage(`Fiche patient créée${emailSaved ? " · email" : ""}${noteSaved ? " · note" : ""}${docsSaved ? ` · ${docsSaved} document(s)` : ""}.`);
    } catch (e) {
      setActionMessage(e?.message || "Impossible d'enregistrer le nom.");
    } finally {
      setPatientSaving(false);
    }
  }

  function handleRecall(call) {
    const phone = getDialable(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
    if (phone) { window.location.href = `tel:${phone}`; return; }
    setActionMessage("Numéro indisponible pour rappel.");
  }

  async function runContextualAction(detail) {
    const action = detail?.contextual_action?.kind || "open_detail";
    const callId = detail?.call_id || detail?.id || selectedCallId;
    if (action === "followup_callback") { await persistFollowup(callId, "callback", detail?.followup_notes || "", "Ajouté à la file de rappel."); return; }
    if (action === "mark_processed") { await persistFollowup(callId, "processed", detail?.followup_notes || "", "Marqué comme traité."); return; }
    if (action === "open_agenda") { navigate("/app/agenda"); return; }
    setActionMessage("Détails affichés.");
  }

  async function copyToClipboard(text) {
    if (!text || !navigator?.clipboard?.writeText) return false;
    try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
  }

  const periodLabel = tab === "today" ? "aujourd'hui" : tab === "week" ? "cette semaine" : `${days} jours`;
  const statusFilters = [
    { key: "all", label: "Tous", count: calls.length },
    { key: "ok", label: "Résolus", count: calls.filter((c) => c.status === "ok").length },
    { key: "missed", label: "Manqués", count: calls.filter((c) => c.status === "missed").length },
    { key: "callback", label: "À rappeler", count: calls.filter((c) => c.status === "callback").length },
  ];

  return (
    <div style={{ minHeight: "100%", fontFamily: "'Inter', system-ui, sans-serif", background: C.bg, color: C.navy }}>
      <style>{CSS}</style>

      <div style={S.header}>
        <div style={S.headerTop}>
          <div>
            <h1 style={S.title}>Journal d&apos;appels</h1>
            <p style={S.subtitle}>{filtered.length} appel{filtered.length !== 1 ? "s" : ""} · {periodLabel}</p>
          </div>
          <div style={S.searchBox}>
            <span style={S.searchIcon}>🔍</span>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Rechercher un patient…" style={S.searchInput} />
            {search && <button type="button" onClick={() => setSearch("")} style={S.searchClear}>✕</button>}
          </div>
        </div>

        <div style={S.tabBar}>
          <div style={S.tabs}>
            {[["today", "Aujourd'hui"], ["week", "Cette semaine"], ["all", "30 jours"]].map(([key, label]) => (
              <button key={key} type="button" onClick={() => setTab(key)} style={tab === key ? S.tabActive : S.tab}>
                {label}
              </button>
            ))}
          </div>
          <div style={S.filterPills}>
            {statusFilters.map((f) => (
              <button key={f.key} type="button" onClick={() => setStatusFilter(f.key)} style={statusFilter === f.key ? S.pillActive : S.pill}>
                {f.label}
                {f.count > 0 && <span style={statusFilter === f.key ? S.pillCountActive : S.pillCount}>{f.count}</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={S.body}>
        {error && <div style={S.errorBox}>{error}</div>}
        {actionMessage && !selectedCallId && <div style={S.toast}>{actionMessage}</div>}

        {missedCount > 0 && (
          <div style={S.alertBar}>
            <span>⚠️ {missedCount} appel{missedCount > 1 ? "s" : ""} nécessite{missedCount > 1 ? "nt" : ""} un rappel</span>
            <button type="button" onClick={() => setStatusFilter("callback")} style={S.alertBtn}>Voir →</button>
          </div>
        )}

        <div style={S.listCard}>
          <div style={S.listHeader}>
            <span style={S.listHeaderCell}>Patient</span>
            <span style={{ ...S.listHeaderCell, flex: "0 0 80px", textAlign: "right" }}>Heure</span>
            <span style={{ ...S.listHeaderCell, flex: "0 0 100px", textAlign: "center" }}>Statut</span>
          </div>

          {loading ? (
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} height={64} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div style={S.empty}>
              <div style={S.emptyIcon}>📭</div>
              <div style={S.emptyTitle}>Aucun appel trouvé</div>
              <div style={S.emptyText}>
                {search || statusFilter !== "all"
                  ? "Essayez de modifier vos filtres."
                  : "Les appels apparaîtront ici."}
              </div>
              {(search || statusFilter !== "all") && (
                <button type="button" onClick={() => { setSearch(""); setStatusFilter("all"); }} style={S.clearBtn}>Réinitialiser les filtres</button>
              )}
            </div>
          ) : (
            filtered.map((call) => (
              <CallRow key={call.id} call={call} onOpen={(c) => setSelectedCallId(c.id)} onRecall={handleRecall} />
            ))
          )}
        </div>
      </div>

      {selectedCallId && (
        detailLoading ? (
          <div style={S.overlay}>
            <div style={S.modalShell}><Skeleton height={80} /><div style={{ height: 12 }} /><Skeleton height={180} /></div>
          </div>
        ) : detailError ? (
          <div style={S.overlay} onClick={() => setSelectedCallId("")}>
            <div style={S.modalShell} onClick={(e) => e.stopPropagation()}>
              <div style={S.errorBox}>Erreur: {detailError}</div>
            </div>
          </div>
        ) : (
          <Suspense fallback={<div style={S.overlay}><div style={S.modalShell}><Skeleton height={80} /><div style={{ height: 12 }} /><Skeleton height={180} /></div></div>}>
            <AppCallDetailModal
              call={detailModel}
              onClose={() => setSelectedCallId("")}
              onRecall={() => handleRecall(detailModel)}
              onContextAction={() => runContextualAction(callDetail || selectedSummary?.raw)}
              onMarkCallback={() => saveFollowupState("callback")}
              onMarkProcessed={() => saveFollowupState("processed")}
              onCopyTranscript={async () => { const ok = await copyToClipboard(callDetail?.transcript || ""); setActionMessage(ok ? "Transcription copiée." : "Copie impossible."); }}
              onCopySummary={async () => { const ok = await copyToClipboard(callDetail?.summary || selectedSummary?.summary || ""); setActionMessage(ok ? "Résumé copié." : "Copie impossible."); }}
              onCopyId={async () => { const ok = await copyToClipboard(selectedCallId); setActionMessage(ok ? "ID copié." : "Copie impossible."); }}
              followupNotes={followupNotes}
              setFollowupNotes={setFollowupNotes}
              onSaveNotes={() => saveFollowupState(callDetail?.followup_state || "new", followupNotes)}
              patientNameDraft={patientNameDraft}
              setPatientNameDraft={setPatientNameDraft}
              patientEmailDraft={patientEmailDraft}
              setPatientEmailDraft={setPatientEmailDraft}
              patientInitialNoteDraft={patientInitialNoteDraft}
              setPatientInitialNoteDraft={setPatientInitialNoteDraft}
              patientDocFiles={patientDocFiles}
              setPatientDocFiles={setPatientDocFiles}
              onSavePatientName={savePatientName}
              patientSaving={patientSaving}
              followupLoading={followupLoading}
              actionMessage={actionMessage}
            />
          </Suspense>
        )
      )}
    </div>
  );
}

const S = {
  header: {
    background: C.card,
    borderBottom: `1px solid ${C.border}`,
    padding: "0 28px",
  },
  headerTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "20px 0 12px",
    gap: 16,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 20,
    fontWeight: 800,
    color: C.navy,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    margin: "2px 0 0",
    fontSize: 13,
    color: C.textFaint,
  },
  searchBox: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: 10,
    padding: "8px 14px",
    minWidth: 220,
  },
  searchIcon: { fontSize: 13, flexShrink: 0 },
  searchInput: {
    border: "none",
    background: "transparent",
    fontSize: 13,
    color: C.textMid,
    outline: "none",
    flex: 1,
    minWidth: 0,
  },
  searchClear: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: C.textFaint,
    fontSize: 12,
    padding: 0,
  },
  tabBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
  },
  tabs: {
    display: "flex",
    gap: 0,
  },
  tab: {
    padding: "10px 16px",
    fontSize: 13,
    fontWeight: 500,
    color: C.textSoft,
    background: "transparent",
    border: "none",
    borderBottom: "2px solid transparent",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  tabActive: {
    padding: "10px 16px",
    fontSize: 13,
    fontWeight: 700,
    color: C.tealDark,
    background: "transparent",
    border: "none",
    borderBottom: `2px solid ${C.teal}`,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  filterPills: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
  },
  pill: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "5px 12px",
    borderRadius: 20,
    border: `1px solid ${C.border}`,
    background: "transparent",
    fontSize: 12,
    fontWeight: 500,
    color: C.textSoft,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  pillActive: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "5px 12px",
    borderRadius: 20,
    border: `1px solid ${C.tealBorder}`,
    background: C.tealLight,
    fontSize: 12,
    fontWeight: 700,
    color: C.tealDark,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  pillCount: {
    fontSize: 10,
    fontWeight: 700,
    color: C.textFaint,
    background: C.borderLight,
    borderRadius: 10,
    padding: "1px 6px",
    minWidth: 18,
    textAlign: "center",
  },
  pillCountActive: {
    fontSize: 10,
    fontWeight: 700,
    color: C.tealDark,
    background: "rgba(13,201,145,0.15)",
    borderRadius: 10,
    padding: "1px 6px",
    minWidth: 18,
    textAlign: "center",
  },
  body: {
    padding: "20px 28px",
  },
  errorBox: {
    borderRadius: 12,
    border: "1px solid #fecaca",
    background: "#fef2f2",
    color: "#b91c1c",
    padding: "10px 14px",
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 14,
  },
  toast: {
    marginBottom: 14,
    borderRadius: 10,
    border: `1px solid ${C.tealBorder}`,
    background: C.tealLight,
    color: C.tealDark,
    padding: "10px 14px",
    fontSize: 12,
    fontWeight: 600,
  },
  alertBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 16px",
    borderRadius: 12,
    background: C.orangeLight,
    border: `1px solid ${C.orangeBorder}`,
    marginBottom: 16,
    fontSize: 13,
    fontWeight: 600,
    color: C.orange,
  },
  alertBtn: {
    fontSize: 12,
    fontWeight: 700,
    color: C.orange,
    background: "none",
    border: `1px solid ${C.orangeBorder}`,
    borderRadius: 8,
    padding: "4px 12px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  listCard: {
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  listHeader: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "10px 18px",
    background: "#fafbfc",
    borderBottom: `1px solid ${C.borderLight}`,
  },
  listHeaderCell: {
    fontSize: 11,
    fontWeight: 600,
    color: C.textFaint,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    flex: 1,
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "14px 18px",
    borderBottom: `1px solid ${C.borderLight}`,
    cursor: "pointer",
    transition: "background 0.12s",
  },
  statusDot: {
    width: 4,
    minHeight: 36,
    borderRadius: 2,
    flexShrink: 0,
  },
  intentCol: {
    width: 36,
    height: 36,
    borderRadius: 10,
    background: C.bg,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    fontSize: 16,
  },
  mainCol: {
    flex: 1,
    minWidth: 0,
  },
  nameRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 3,
    flexWrap: "wrap",
  },
  name: {
    fontSize: 14,
    fontWeight: 700,
    color: C.navy,
  },
  iaBadge: {
    fontSize: 9,
    fontWeight: 800,
    color: C.purple,
    background: C.purpleLight,
    border: `1px solid ${C.purpleBorder}`,
    borderRadius: 4,
    padding: "1px 5px",
    letterSpacing: "0.02em",
  },
  urgentBadge: {
    fontSize: 9,
    fontWeight: 800,
    color: C.red,
    background: C.redLight,
    border: `1px solid ${C.redBorder}`,
    borderRadius: 4,
    padding: "1px 5px",
  },
  rdvBadge: {
    fontSize: 9,
    fontWeight: 800,
    color: C.tealDark,
    background: C.tealLight,
    border: `1px solid ${C.tealBorder}`,
    borderRadius: 4,
    padding: "1px 5px",
  },
  patientFileOk: {
    fontSize: 9,
    fontWeight: 800,
    color: C.tealDark,
    background: C.tealLight,
    border: `1px solid ${C.tealBorder}`,
    borderRadius: 4,
    padding: "1px 5px",
  },
  patientFileTodo: {
    fontSize: 9,
    fontWeight: 800,
    color: C.orange,
    background: C.orangeLight,
    border: `1px solid ${C.orangeBorder}`,
    borderRadius: 4,
    padding: "1px 5px",
  },
  summaryRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    minWidth: 0,
  },
  intentLabel: {
    fontSize: 11,
    fontWeight: 700,
    borderRadius: 5,
    padding: "2px 7px",
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
  summary: {
    fontSize: 12,
    color: C.textSoft,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    minWidth: 0,
  },
  metaCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    gap: 2,
    flexShrink: 0,
    minWidth: 60,
  },
  time: {
    fontSize: 14,
    fontWeight: 700,
    color: C.textMid,
  },
  duration: {
    fontSize: 11,
    color: C.textFaint,
    fontWeight: 600,
  },
  statusCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
    flexShrink: 0,
    minWidth: 80,
  },
  statusBadge: {
    fontSize: 11,
    fontWeight: 700,
    borderRadius: 20,
    padding: "3px 10px",
    border: "1px solid",
    whiteSpace: "nowrap",
  },
  recallBtn: {
    fontSize: 11,
    fontWeight: 700,
    color: C.orange,
    background: C.orangeLight,
    border: `1px solid ${C.orangeBorder}`,
    borderRadius: 7,
    padding: "3px 10px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  empty: {
    padding: "48px 20px",
    textAlign: "center",
  },
  emptyIcon: {
    fontSize: 36,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: C.navy,
  },
  emptyText: {
    marginTop: 4,
    fontSize: 13,
    color: C.textSoft,
  },
  clearBtn: {
    marginTop: 12,
    fontSize: 12,
    fontWeight: 600,
    color: C.tealDark,
    background: C.tealLight,
    border: `1px solid ${C.tealBorder}`,
    borderRadius: 8,
    padding: "6px 14px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  overlay: {
    position: "fixed",
    inset: 0,
    zIndex: 2000,
    background: "rgba(15,23,42,0.3)",
    backdropFilter: "blur(5px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  modalShell: {
    background: "#fff",
    borderRadius: 20,
    width: 540,
    maxWidth: "94vw",
    padding: 22,
  },
};

const CSS = `
  @keyframes uwi-calls-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .call-row:hover {
    background: #f8fbff !important;
  }

  .call-row:last-child {
    border-bottom: none !important;
  }

  @media (max-width: 768px) {
    .call-row {
      flex-wrap: wrap;
      gap: 8px !important;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .call-row {
      transition: none !important;
    }
  }
`;
