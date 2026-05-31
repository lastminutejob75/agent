import { useEffect, useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { usePatientListContext } from "./AppPatientsLayout.jsx";
import {
  checkPatientDuplicates,
  formatPatientDuplicateConflict,
  parsePatientDuplicateError,
} from "../lib/patientDuplicateCheck.js";

const NAVY = "#111827";
const TEAL = "#0DC991";
const TEAL_DARK = "#0AAF7A";
const BLUE = "#2563EB";
const BORDER = "#e5e7eb";

function formatPhone(phone) {
  const raw = String(phone || "").trim();
  if (!raw) return "—";
  if (raw.startsWith("+33") && raw.length === 12)
    return `0${raw.slice(3, 4)} ${raw.slice(4, 6)} ${raw.slice(6, 8)} ${raw.slice(8, 10)} ${raw.slice(10)}`;
  return raw;
}

function timeAgo(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Date.now() - date.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return `Il y a ${days}j`;
  if (days < 30) return `Il y a ${Math.floor(days / 7)} sem.`;
  if (days < 365) return `Il y a ${Math.floor(days / 30)} mois`;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function localDateOnly(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatDateFull(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
}

function formatTime(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function derivePatientStatus(patient) {
  const now = Date.now();
  const updatedAt = new Date(patient.updated_at || 0).getTime();
  const createdAt = new Date(patient.created_at || 0).getTime();
  const daysSinceUpdate = (now - updatedAt) / 86400000;
  const daysSinceCreation = (now - createdAt) / 86400000;
  if (daysSinceCreation < 14 && patient.validation_status !== "validated") return "new";
  if (daysSinceUpdate > 60) return "inactive";
  return "active";
}

const STATUS_MAP = {
  active: { label: "Actif", color: "#22c55e", bg: "#dcfce7", icon: "🟢" },
  new: { label: "Nouveau", color: "#f59e0b", bg: "#fef3c7", icon: "🟡" },
  inactive: { label: "Inactif", color: "#94a3b8", bg: "#f1f5f9", icon: "⚪" },
};

const CHANNEL_CONFIG = {
  CONFIRMED: { label: "RDV confirmé", color: BLUE, icon: "📅" },
  TRANSFERRED: { label: "Transféré", color: "#ef4444", icon: "⚠️" },
  RESCHEDULED: { label: "RDV déplacé", color: "#8b5cf6", icon: "🔁" },
  CANCELLED: { label: "RDV annulé", color: "#ef4444", icon: "❌" },
  MISSED: { label: "Appel manqué", color: "#ef4444", icon: "📵" },
  ANSWERED: { label: "Appel traité", color: "#22c55e", icon: "📞" },
  DEFAULT: { label: "Appel", color: "#6b7280", icon: "📞" },
};

const CATEGORY_LABELS = {
  prescription: { label: "Ordonnance", icon: "💊" },
  callback: { label: "Rappel demandé", icon: "📞" },
  urgency: { label: "Urgence", icon: "🚨" },
  agenda: { label: "Rendez-vous", icon: "📅" },
  consultation: { label: "Consultation", icon: "🩺" },
  suivi: { label: "Suivi", icon: "🔄" },
  administratif: { label: "Administratif", icon: "📋" },
  resultats: { label: "Résultats", icon: "📊" },
  general: { label: "Général", icon: "📋" },
};

const TAGS_KEY = "uwi_patient_tags_";
function loadTags(phone) { try { return JSON.parse(localStorage.getItem(TAGS_KEY + phone) || "[]"); } catch { return []; } }
function saveTags(phone, tags) { localStorage.setItem(TAGS_KEY + phone, JSON.stringify(tags)); }
function migrateTags(oldPhone, newPhone) {
  if (!oldPhone || !newPhone || oldPhone === newPhone) return;
  const tags = loadTags(oldPhone);
  if (tags.length) {
    saveTags(newPhone, tags);
    localStorage.removeItem(TAGS_KEY + oldPhone);
  }
}

export default function AppPatientDetail() {
  const { phone } = useParams();
  const navigate = useNavigate();

  let ctx;
  try { ctx = usePatientListContext(); } catch { ctx = null; }
  const { goPrev, goNext, hasPrev, hasNext, selectedIndex, filtered, updatePatientInList, replacePatientInList } = ctx || {};

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [notes, setNotes] = useState([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [deletingNoteId, setDeletingNoteId] = useState(null);
  const [tags, setTags] = useState([]);
  const [tagDraft, setTagDraft] = useState("");
  const [expandedCallId, setExpandedCallId] = useState(null);
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [savingEmail, setSavingEmail] = useState(false);
  const [editingPhone, setEditingPhone] = useState(false);
  const [phoneDraft, setPhoneDraft] = useState("");
  const [savingPhone, setSavingPhone] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [sendingDocId, setSendingDocId] = useState(null);

  useEffect(() => {
    if (!phone) return;
    setNotes([]);
    setTags(loadTags(phone));
    setExpandedCallId(null);
    setEditingName(false);
  }, [phone]);

  useEffect(() => {
    if (!phone) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    api.tenantGetPatient(phone)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setDocuments(res.documents || []);
          setNotes(Array.isArray(res.notes) ? res.notes : []);
        }
      })
      .catch((e) => { if (!cancelled) setError(e?.message || "Patient introuvable."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [phone]);

  useEffect(() => {
    if (!toast) return undefined;
    const t = window.setTimeout(() => setToast(""), 3000);
    return () => window.clearTimeout(t);
  }, [toast]);

  // Keyboard shortcuts: arrow keys for prev/next
  useEffect(() => {
    function handleKey(e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowLeft" && hasPrev) { e.preventDefault(); goPrev(); }
      if (e.key === "ArrowRight" && hasNext) { e.preventDefault(); goNext(); }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [hasPrev, hasNext, goPrev, goNext]);

  const patient = data?.patient || {};
  const calls = data?.calls || [];
  const handoffs = data?.handoffs || [];
  const displayName = patient.display_name || patient.raw_name || "Patient";
  const patientStatus = derivePatientStatus(patient);
  const stConfig = STATUS_MAP[patientStatus];

  const pendingItems = useMemo(() => {
    const items = [];
    for (const h of handoffs) {
      if (h.status === "processed" || h.status === "cancelled") continue;
      items.push({ id: `ho-${h.id || h.created_at}`, type: "handoff", date: h.created_at, icon: "✉️", label: "Demande en attente", color: "#f59e0b", summary: h.summary || h.reason || "", time: formatTime(h.created_at), priority: h.priority, handoffId: h.id, reason: h.reason || "" });
    }
    for (const c of calls) {
      if (c.followup_state === "pending" || c.followup_state === "new") {
        const ch = CHANNEL_CONFIG[c.status] || CHANNEL_CONFIG.DEFAULT;
        if (c.status === "TRANSFERRED" || c.status === "MISSED") {
          items.push({ id: `call-${c.call_id}`, type: "call", date: c.started_at, icon: ch.icon, label: ch.label, color: ch.color, summary: c.summary || "", time: c.time || formatTime(c.started_at), callId: c.call_id });
        }
      }
    }
    items.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
    return items;
  }, [calls, handoffs]);

  const timeline = useMemo(() => {
    const items = [];
    for (const c of calls) {
      const ch = CHANNEL_CONFIG[c.status] || CHANNEL_CONFIG.DEFAULT;
      items.push({ id: `call-${c.call_id}`, type: "call", date: c.started_at, icon: ch.icon, label: ch.label, color: ch.color, summary: c.summary || "", duration: c.duration || "", time: c.time || formatTime(c.started_at), category: c.reason_category, callId: c.call_id });
    }
    for (const h of handoffs) {
      items.push({ id: `ho-${h.id || h.created_at}`, type: "handoff", date: h.created_at, icon: "✉️", label: h.status === "processed" ? "Demande traitée" : "Demande en attente", color: h.status === "processed" ? "#22c55e" : "#f59e0b", summary: h.summary || h.reason || "", duration: "", time: formatTime(h.created_at), category: "callback" });
    }
    items.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
    return items;
  }, [calls, handoffs]);


  async function handleSaveName() {
    const name = nameDraft.trim();
    if (name.length < 2) { setToast("Minimum 2 caractères."); return; }
    const callId = patient.source_call_id || patient.last_call_id || calls[0]?.call_id;
    setSaving(true);
    try {
      if (callId) {
        await api.tenantUpdateCallPatient(callId, { validated_name: name, raw_name: patient.raw_name || "" });
      } else {
        await api.tenantRegisterPatient({
          patient_phone: phone,
          validated_name: name,
          raw_name: (patient.raw_name || patient.display_name || "").trim() || name,
        });
      }
      const updates = { validated_name: name, display_name: name, validation_status: "validated" };
      setData((prev) => prev ? { ...prev, patient: { ...prev.patient, ...updates } } : prev);
      if (updatePatientInList) updatePatientInList(phone, updates);
      setEditingName(false);
      setToast("Nom enregistré");
    } catch (e) { setToast(e?.message || "Erreur"); }
    finally { setSaving(false); }
  }

  async function addNote() {
    const text = noteDraft.trim();
    if (!text) return;
    setAddingNote(true);
    try {
      const res = await api.tenantCreatePatientNote(phone, { text, author: "Praticien" });
      const created = res?.item || { id: `tmp-${Date.now()}`, text, author: "Praticien", created_at: new Date().toISOString() };
      setNotes((prev) => [created, ...prev]);
      setNoteDraft("");
      setToast("Note ajoutée");
    } catch (e) {
      setToast(e?.message || "Erreur ajout note");
    } finally {
      setAddingNote(false);
    }
  }
  async function removeNote(noteId) {
    if (!noteId) return;
    setDeletingNoteId(noteId);
    try {
      await api.tenantDeletePatientNote(phone, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
      setToast("Note supprimée");
    } catch (e) {
      setToast(e?.message || "Erreur suppression note");
    } finally {
      setDeletingNoteId(null);
    }
  }
  function addTag() {
    const t = tagDraft.trim();
    if (!t || tags.includes(t)) return;
    const u = [...tags, t];
    setTags(u);
    saveTags(phone, u);
    setTagDraft("");
  }
  function removeTag(tag) { const u = tags.filter((t) => t !== tag); setTags(u); saveTags(phone, u); }

  async function handleSaveEmail() {
    const email = emailDraft.trim();
    setSavingEmail(true);
    try {
      const res = await api.tenantUpdatePatient(phone, { email });
      setData((prev) => prev ? { ...prev, patient: { ...prev.patient, email } } : prev);
      setEditingEmail(false);
      setToast(email ? "Email enregistré" : "Email supprimé");
    } catch (e) { setToast(e?.message || "Erreur"); }
    finally { setSavingEmail(false); }
  }

  async function handleSavePhone() {
    const next = phoneDraft.trim();
    if (!next) {
      setToast("Indiquez un numéro de téléphone");
      return;
    }
    setSavingPhone(true);
    try {
      const dup = await checkPatientDuplicates({ phone: next, excludePhone: phone });
      if (dup?.has_conflict) {
        setToast(formatPatientDuplicateConflict(dup.conflicts?.[0]) || "Ce numéro est déjà utilisé");
        return;
      }
      const res = await api.tenantUpdatePatient(phone, { phone: next });
      const newPhone = res?.patient?.phone || next;
      migrateTags(phone, newPhone);
      if (replacePatientInList) replacePatientInList(phone, res.patient);
      else if (updatePatientInList) updatePatientInList(phone, { phone: newPhone });
      navigate(`/app/patients/${encodeURIComponent(newPhone)}`, { replace: true });
      setEditingPhone(false);
      setToast("Numéro mis à jour");
    } catch (e) {
      const dup = parsePatientDuplicateError(e);
      setToast(dup.message || e?.message || "Erreur");
    } finally {
      setSavingPhone(false);
    }
  }

  async function handleUploadDoc(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.tenantUploadPatientDocument(phone, file);
      if (res?.document) setDocuments((prev) => [res.document, ...prev]);
      setToast("Document ajouté");
    } catch (err) { setToast(err?.message || "Erreur upload"); }
    finally { setUploading(false); e.target.value = ""; }
  }

  async function handleDownloadDoc(doc) {
    try {
      const url = api.tenantDownloadPatientDocument(phone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Téléchargement échoué");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = doc.original_name || "document";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (err) { setToast(err?.message || "Erreur téléchargement"); }
  }

  async function handlePreviewDoc(doc) {
    try {
      const url = api.tenantDownloadPatientDocument(phone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Impossible de charger le document");
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      setPreviewDoc(doc);
      setPreviewUrl(objUrl);
    } catch (err) { setToast(err?.message || "Erreur prévisualisation"); }
  }

  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewDoc(null);
    setPreviewUrl(null);
  }

  async function handleSendDoc(docId) {
    if (!patient.email) { setToast("Ajoutez d'abord l'email du patient"); return; }
    setSendingDocId(docId);
    try {
      await api.tenantSendPatientDocument(phone, docId);
      setToast(`Document envoyé à ${patient.email}`);
    } catch (err) { setToast(err?.message || "Erreur envoi"); }
    finally { setSendingDocId(null); }
  }

  async function handleDeleteDoc(docId) {
    try {
      await api.tenantDeletePatientDocument(phone, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setToast("Document supprimé");
    } catch (err) { setToast(err?.message || "Erreur"); }
  }

  // Navigation bar
  const positionLabel = ctx && selectedIndex >= 0 ? `${selectedIndex + 1} / ${filtered.length}` : null;

  if (loading) {
    return (
      <div style={S.panel}><style>{CSS}</style>
        <div style={S.navBar}><button type="button" onClick={() => navigate("/app/patients")} className="mobile-back-btn" style={S.backBtn}>← Liste</button></div>
        <div style={S.skeletonBlock} /><div style={{ height: 16 }} /><div style={{ ...S.skeletonBlock, height: 200 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={S.panel}><style>{CSS}</style>
        <div style={S.navBar}><button type="button" onClick={() => navigate("/app/patients")} className="mobile-back-btn" style={S.backBtn}>← Liste</button></div>
        <div style={S.errorBox}>{error}</div>
      </div>
    );
  }

  return (
    <div style={S.panel}>
      <style>{CSS}</style>

      {/* ─── TOP NAVIGATION BAR ─── */}
      <div style={S.navBar}>
        <button type="button" onClick={() => navigate("/app/patients")} className="mobile-back-btn" style={S.backBtn}>← Liste</button>
        {positionLabel ? (
          <div style={S.navCenter}>
            <button type="button" onClick={goPrev} disabled={!hasPrev} style={hasPrev ? S.navArrow : S.navArrowDisabled} title="Patient précédent (←)">‹</button>
            <span style={S.navPos}>{positionLabel}</span>
            <button type="button" onClick={goNext} disabled={!hasNext} style={hasNext ? S.navArrow : S.navArrowDisabled} title="Patient suivant (→)">›</button>
          </div>
        ) : null}
        <div style={S.navActions}>
          <a href={`tel:${phone}`} style={S.navActionBtn}>📞</a>
          <button type="button" onClick={() => navigate("/app/agenda")} style={S.navActionBtn}>📅</button>
        </div>
      </div>

      {toast ? <div style={S.toast}>{toast}</div> : null}

      {/* ─── PROFILE HEADER ─── */}
      <div style={S.profileCard}>
        <div style={S.profileTop}>
          <div style={S.avatar}>{displayName[0]?.toUpperCase()}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={S.nameRow}>
              {editingName ? (
                <div style={S.editRow}>
                  <input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleSaveName(); if (e.key === "Escape") setEditingName(false); }} autoFocus style={S.editInput} />
                  <button type="button" onClick={handleSaveName} disabled={saving} style={S.saveBtn}>{saving ? "…" : "OK"}</button>
                  <button type="button" onClick={() => setEditingName(false)} style={S.cancelEditBtn}>✕</button>
                </div>
              ) : (
                <>
                  <h1 style={S.name} onClick={() => { setEditingName(true); setNameDraft(displayName); }} title="Cliquer pour modifier">{displayName}</h1>
                  {patient.validation_status !== "validated" && (
                    <button type="button" onClick={() => { setEditingName(true); setNameDraft(displayName); }} style={S.confirmNameBtn}>✏️ Confirmer</button>
                  )}
                </>
              )}
            </div>
            <div style={S.metaRow}>
              {editingPhone ? (
                <div style={S.editRow}>
                  <input
                    type="tel"
                    value={phoneDraft}
                    onChange={(e) => setPhoneDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") handleSavePhone(); if (e.key === "Escape") setEditingPhone(false); }}
                    autoFocus
                    placeholder="06 12 34 56 78"
                    style={S.editInput}
                  />
                  <button type="button" onClick={handleSavePhone} disabled={savingPhone} style={S.saveBtn}>{savingPhone ? "…" : "OK"}</button>
                  <button type="button" onClick={() => setEditingPhone(false)} style={S.cancelEditBtn}>✕</button>
                </div>
              ) : (
                <>
                  <a href={`tel:${phone}`} style={S.phoneLink}>{formatPhone(phone)}</a>
                  <button type="button" onClick={() => { setEditingPhone(true); setPhoneDraft(phone); }} style={S.editNameBtn}>Modifier</button>
                </>
              )}
              <span style={S.dot} />
              <span style={{ ...S.statusBadge, color: stConfig.color, background: stConfig.bg }}>{stConfig.icon} {stConfig.label}</span>
              <span style={S.dot} />
              <span style={S.metaText}>Depuis {timeAgo(patient.created_at)}</span>
              {patient.updated_at && <><span style={S.dot} /><span style={S.metaText}>Contact {timeAgo(patient.updated_at)}</span></>}
            </div>
            <div style={S.emailRow}>
              <span style={S.emailIcon}>✉️</span>
              {editingEmail ? (
                <div style={S.editRow}>
                  <input type="email" value={emailDraft} onChange={(e) => setEmailDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleSaveEmail(); if (e.key === "Escape") setEditingEmail(false); }} autoFocus placeholder="email@exemple.com" style={S.editInput} />
                  <button type="button" onClick={handleSaveEmail} disabled={savingEmail} style={S.saveBtn}>{savingEmail ? "…" : "OK"}</button>
                  <button type="button" onClick={() => setEditingEmail(false)} style={S.cancelEditBtn}>✕</button>
                </div>
              ) : (
                <>
                  {patient.email ? (
                    <a href={`mailto:${patient.email}`} style={S.emailLink}>{patient.email}</a>
                  ) : (
                    <span style={S.emailPlaceholder}>Aucun email</span>
                  )}
                  <button type="button" onClick={() => { setEditingEmail(true); setEmailDraft(patient.email || ""); }} style={S.editNameBtn}>
                    {patient.email ? "Modifier" : "Ajouter"}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* ─── CONTENT SPLIT ─── */}
      <div className="detail-split" style={S.split}>

        {/* LEFT: Unified activity feed */}
        <div style={S.mainCol}>
          <div style={S.section}>
            <div style={S.sectionHeader}>
              <h2 style={S.sectionTitle}>Activité</h2>
              {pendingItems.length > 0 && <span style={S.pendingBadge}>{pendingItems.length} en attente</span>}
            </div>
            {timeline.length === 0 ? (
              <div style={S.emptySection}>Aucune interaction enregistrée.</div>
            ) : (
              <div style={S.timelineList}>
                {timeline.map((item) => {
                  const isPending = item.type === "handoff" && item.label === "Demande en attente";
                  const isExpanded = expandedCallId === item.id;
                  return (
                    <div key={item.id} className="tl-item" style={{ ...S.tlItem, ...(isPending ? S.tlItemPending : {}) }} onClick={() => setExpandedCallId(isExpanded ? null : item.id)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") setExpandedCallId(isExpanded ? null : item.id); }}>
                      <div style={{ ...S.tlBar, background: item.color }} />
                      <div style={S.tlContent}>
                        <div style={S.tlTop}>
                          <span style={S.tlIcon}>{item.icon}</span>
                          <span style={S.tlLabel}>{item.label}</span>
                          {isPending && <span style={S.tlPendingTag}>À traiter</span>}
                          {item.duration ? <span style={S.tlDuration}>{item.duration}</span> : null}
                          <span style={S.tlTime}>{item.time}</span>
                          <span style={S.tlDate}>{timeAgo(item.date)}</span>
                        </div>
                        {item.summary ? (
                          <div style={{ ...S.tlSummary, ...(isExpanded ? {} : { WebkitLineClamp: 2, display: "-webkit-box", WebkitBoxOrient: "vertical", overflow: "hidden" }) }}>
                            {item.summary}
                          </div>
                        ) : null}
                        {isPending && isExpanded && (
                          <div style={S.pendingActions}>
                            <a href={`tel:${phone}`} style={S.pendingCallBtn}>📞 Rappeler</a>
                            <button type="button" onClick={(e) => { e.stopPropagation(); const ds = localDateOnly(patient.last_booking_start); navigate(ds ? `/app/agenda?date=${ds}&phone=${encodeURIComponent(phone)}` : "/app/agenda"); }} style={S.pendingAgendaBtn}>📅 Voir le RDV</button>
                          </div>
                        )}
                        {!isPending && item.category && item.category !== "general" ? (
                          <span style={S.tlCat}>{(CATEGORY_LABELS[item.category] || CATEGORY_LABELS.general).icon} {(CATEGORY_LABELS[item.category] || CATEGORY_LABELS.general).label}</span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Sidebar */}
        <div style={S.sideCol}>
          {/* RDV */}
          <div style={S.sideCard}>
            <h3 style={S.sideTitle}>📅 Rendez-vous</h3>
            {patient.last_booking_start ? (
              <div style={S.rdvCard} onClick={() => { const ds = localDateOnly(patient.last_booking_start); if (ds) navigate(`/app/agenda?date=${ds}&phone=${encodeURIComponent(phone)}`); }} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") { const ds = localDateOnly(patient.last_booking_start); if (ds) navigate(`/app/agenda?date=${ds}&phone=${encodeURIComponent(phone)}`); } }}>
                <div style={S.rdvDate}>{formatDateFull(patient.last_booking_start)}</div>
                <div style={S.rdvMotif}>{patient.last_booking_motif || "Consultation"}</div>
                <span style={S.rdvLink}>Voir dans l'agenda →</span>
              </div>
            ) : <div style={S.sideEmpty}>Aucun RDV</div>}
          </div>

          {/* Documents */}
          <div style={S.sideCard}>
            <h3 style={S.sideTitle}>📎 Documents</h3>
            <label style={S.uploadBtn}>
              {uploading ? "Envoi…" : "📤 Ajouter un document"}
              <input type="file" onChange={handleUploadDoc} disabled={uploading} style={{ display: "none" }} accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.txt" />
            </label>
            {documents.length === 0 ? (
              <div style={S.sideEmpty}>Aucun document</div>
            ) : (
              <div style={S.docList}>
                {documents.map((doc) => {
                  const sizeLabel = doc.size_bytes > 1048576 ? `${(doc.size_bytes / 1048576).toFixed(1)} Mo` : `${Math.round(doc.size_bytes / 1024)} Ko`;
                  const canPreview = (doc.mime_type || "").includes("pdf") || (doc.mime_type || "").startsWith("image");
                  const icon = (doc.mime_type || "").includes("pdf") ? "📄" : (doc.mime_type || "").startsWith("image") ? "🖼️" : "📎";
                  const isSending = sendingDocId === doc.id;
                  return (
                    <div key={doc.id} style={S.docItem}>
                      <span style={S.docIcon}>{icon}</span>
                      <div style={S.docInfo}>
                        <button type="button" onClick={() => canPreview ? handlePreviewDoc(doc) : handleDownloadDoc(doc)} style={S.docName} title={canPreview ? "Consulter" : "Télécharger"}>{doc.original_name}</button>
                        <span style={S.docMeta}>{sizeLabel}{doc.created_at ? ` · ${timeAgo(doc.created_at)}` : ""}</span>
                      </div>
                      <div style={S.docActions}>
                        {canPreview && <button type="button" onClick={() => handlePreviewDoc(doc)} style={S.docActionBtn} title="Consulter">👁️</button>}
                        <button type="button" onClick={() => handleDownloadDoc(doc)} style={S.docActionBtn} title="Télécharger">⬇️</button>
                        <button type="button" onClick={() => handleSendDoc(doc.id)} disabled={isSending} style={{ ...S.docActionBtn, ...(patient.email ? {} : { opacity: 0.4, cursor: "default" }) }} title={patient.email ? `Envoyer à ${patient.email}` : "Ajoutez d'abord l'email du patient"}>{isSending ? "…" : "📧"}</button>
                        <button type="button" onClick={() => handleDeleteDoc(doc.id)} style={S.docDeleteBtn} title="Supprimer">✕</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Notes */}
          <div style={S.sideCard}>
            <h3 style={S.sideTitle}>📝 Notes</h3>
            <textarea value={noteDraft} onChange={(e) => setNoteDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); addNote(); } }} placeholder="Ajouter une note…" style={S.noteInput} rows={2} />
            <button type="button" onClick={addNote} disabled={!noteDraft.trim() || addingNote} style={S.noteAddBtn}>{addingNote ? "Ajout…" : "Ajouter"}</button>
            {notes.map((n, i) => (
              <div key={n.id || i} style={S.noteCard}>
                <div style={S.noteText}>{n.text}</div>
                <div style={S.noteFooter}>
                  <span style={S.noteMeta}>{n.author || "Cabinet"} · {timeAgo(n.created_at || n.date)}</span>
                  <button type="button" onClick={() => removeNote(n.id)} disabled={!n.id || deletingNoteId === n.id} style={S.noteRemoveBtn}>
                    {deletingNoteId === n.id ? "…" : "✕"}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Tags */}
          <div style={S.sideCard}>
            <h3 style={S.sideTitle}>🏷️ Tags</h3>
            <div style={S.tagsRow}>
              {tags.map((t) => <span key={t} style={S.tag}>{t}<button type="button" onClick={() => removeTag(t)} style={S.tagX}>×</button></span>)}
            </div>
            <div style={S.tagInputRow}>
              <input value={tagDraft} onChange={(e) => setTagDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addTag(); }} placeholder="Nouveau tag…" style={S.tagInput} />
              <button type="button" onClick={addTag} style={S.tagAddBtn}>+</button>
            </div>
          </div>
        </div>
      </div>

      {/* ─── DOCUMENT PREVIEW MODAL ─── */}
      {previewDoc && previewUrl && (
        <div style={S.previewOverlay} onClick={closePreview}>
          <div style={S.previewModal} onClick={(e) => e.stopPropagation()}>
            <div style={S.previewHeader}>
              <span style={S.previewTitle}>{previewDoc.original_name}</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button type="button" onClick={() => handleDownloadDoc(previewDoc)} style={S.previewActionBtn} title="Télécharger">⬇️</button>
                <button type="button" onClick={() => { handleSendDoc(previewDoc.id); }} disabled={sendingDocId === previewDoc.id} style={{ ...S.previewActionBtn, ...(patient.email ? {} : { opacity: 0.4 }) }} title={patient.email ? `Envoyer à ${patient.email}` : "Pas d'email"}>
                  {sendingDocId === previewDoc.id ? "…" : "📧"}
                </button>
                <button type="button" onClick={closePreview} style={S.previewCloseBtn}>✕</button>
              </div>
            </div>
            <div style={S.previewBody}>
              {(previewDoc.mime_type || "").includes("pdf") ? (
                <iframe src={previewUrl} style={S.previewIframe} title="Document PDF" />
              ) : (previewDoc.mime_type || "").startsWith("image") ? (
                <img src={previewUrl} alt={previewDoc.original_name} style={S.previewImg} />
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const S = {
  panel: { padding: "16px 20px 24px", maxWidth: 1000, margin: "0 auto", fontFamily: "'Inter', 'DM Sans', sans-serif", color: NAVY },

  // Nav bar
  navBar: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, gap: 12 },
  backBtn: { background: "none", border: "none", color: "#6b7280", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", padding: "4px 0", display: "none" },
  navCenter: { display: "flex", alignItems: "center", gap: 6 },
  navPos: { fontSize: 12, color: "#94a3b8", fontWeight: 600, minWidth: 48, textAlign: "center" },
  navArrow: { width: 30, height: 30, borderRadius: 8, border: `1px solid ${BORDER}`, background: "#fff", color: NAVY, fontSize: 18, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" },
  navArrowDisabled: { width: 30, height: 30, borderRadius: 8, border: `1px solid #f0f0f0`, background: "#fafafa", color: "#d1d5db", fontSize: 18, fontWeight: 700, cursor: "default", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" },
  navActions: { display: "flex", gap: 6 },
  navActionBtn: { width: 34, height: 34, borderRadius: 8, border: `1px solid ${BORDER}`, background: "#fff", fontSize: 16, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", fontFamily: "inherit", color: NAVY },

  toast: { marginBottom: 12, borderRadius: 10, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", padding: "10px 14px", fontSize: 13, fontWeight: 700 },
  errorBox: { borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "20px", fontSize: 14, fontWeight: 600 },
  skeletonBlock: { height: 80, borderRadius: 12, background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)", backgroundSize: "200% 100%", animation: "uwi-pd-shimmer 1.35s infinite linear" },

  // Profile
  profileCard: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 14, padding: "18px 20px", boxShadow: "0 2px 8px rgba(15,23,42,.03)", marginBottom: 12 },
  profileTop: { display: "flex", alignItems: "flex-start", gap: 14 },
  avatar: { width: 48, height: 48, borderRadius: 14, background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 800, flexShrink: 0, boxShadow: "0 4px 12px rgba(13,201,145,.15)" },
  nameRow: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  name: { margin: 0, fontSize: 20, fontWeight: 800, color: NAVY, cursor: "pointer" },
  editNameBtn: { padding: "3px 10px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "#fff", color: "#475569", fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  confirmNameBtn: { padding: "3px 10px", borderRadius: 6, border: "1px solid #fde68a", background: "#fffbeb", color: "#92400e", fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  editRow: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" },
  editInput: { border: `2px solid ${TEAL}`, borderRadius: 8, padding: "5px 10px", fontSize: 15, fontWeight: 700, color: NAVY, outline: "none", width: 200, fontFamily: "inherit" },
  saveBtn: { padding: "5px 12px", borderRadius: 6, border: "none", background: TEAL_DARK, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  cancelEditBtn: { padding: "5px 8px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "#fff", color: "#6b7280", fontSize: 13, cursor: "pointer", fontFamily: "inherit" },
  metaRow: { display: "flex", alignItems: "center", gap: 6, marginTop: 6, flexWrap: "wrap" },
  phoneLink: { fontSize: 13, color: TEAL_DARK, fontWeight: 700, textDecoration: "none" },
  dot: { width: 3, height: 3, borderRadius: "50%", background: "#d1d5db", flexShrink: 0 },
  statusBadge: { fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 999 },
  metaText: { fontSize: 12, color: "#6b7280" },


  // Pending highlight
  pendingBadge: { fontSize: 11, fontWeight: 700, color: "#92400e", background: "#fef3c7", padding: "2px 8px", borderRadius: 999 },
  tlItemPending: { background: "#fffbeb", borderLeft: "3px solid #f59e0b" },
  tlPendingTag: { fontSize: 10, fontWeight: 700, color: "#92400e", background: "#fde68a", padding: "1px 6px", borderRadius: 4 },
  pendingActions: { display: "flex", gap: 8, marginTop: 10 },
  pendingCallBtn: { padding: "6px 14px", borderRadius: 8, background: TEAL, color: "#fff", fontSize: 12, fontWeight: 700, textDecoration: "none", border: "none", cursor: "pointer", fontFamily: "inherit" },
  pendingAgendaBtn: { padding: "6px 14px", borderRadius: 8, background: "#fff", color: NAVY, fontSize: 12, fontWeight: 600, border: `1px solid ${BORDER}`, cursor: "pointer", fontFamily: "inherit" },

  // Split
  split: { display: "grid", gridTemplateColumns: "1fr 280px", gap: 14 },
  mainCol: { display: "flex", flexDirection: "column", gap: 12 },
  sideCol: { display: "flex", flexDirection: "column", gap: 10 },

  // Sections
  section: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, overflow: "hidden" },
  sectionHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: `1px solid ${BORDER}`, background: "#fafafa" },
  sectionTitle: { margin: 0, fontSize: 13, fontWeight: 700, color: NAVY },
  sectionCount: { fontSize: 11, fontWeight: 600, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 999 },
  emptySection: { padding: "28px 16px", textAlign: "center", fontSize: 13, color: "#94a3b8" },

  // Timeline
  timelineList: { display: "flex", flexDirection: "column" },
  tlItem: { display: "flex", cursor: "pointer", borderBottom: `1px solid #f5f5f5` },
  tlBar: { width: 4, flexShrink: 0 },
  tlContent: { flex: 1, padding: "10px 14px" },
  tlTop: { display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" },
  tlIcon: { fontSize: 13, flexShrink: 0 },
  tlLabel: { fontSize: 12, fontWeight: 700, color: NAVY },
  tlDuration: { fontSize: 11, color: "#6b7280", background: "#f1f5f9", padding: "1px 6px", borderRadius: 4 },
  tlTime: { fontSize: 11, color: "#6b7280" },
  tlDate: { fontSize: 10, color: "#94a3b8", marginLeft: "auto" },
  tlSummary: { fontSize: 12, color: "#475569", lineHeight: 1.5, marginTop: 4 },
  tlCat: { fontSize: 10, color: "#6b7280", background: "#f8fafc", border: "1px solid #e2e8f0", padding: "1px 6px", borderRadius: 4, display: "inline-block", marginTop: 4 },

  // Side cards
  sideCard: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "12px 14px" },
  sideTitle: { margin: "0 0 8px", fontSize: 12, fontWeight: 700, color: NAVY },
  sideEmpty: { fontSize: 12, color: "#94a3b8", fontStyle: "italic" },

  rdvCard: { padding: "8px 10px", background: "#f0f9ff", borderRadius: 8, border: "1px solid #bae6fd", cursor: "pointer", transition: "background .1s" },
  rdvDate: { fontSize: 12, fontWeight: 700, color: "#0369a1" },
  rdvMotif: { fontSize: 11, color: "#64748b", marginTop: 1 },
  rdvLink: { fontSize: 10, color: "#2563EB", fontWeight: 600, marginTop: 4, display: "block" },

  tagsRow: { display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 },
  tag: { display: "inline-flex", alignItems: "center", gap: 3, padding: "3px 8px", borderRadius: 999, background: "#f1f5f9", color: "#475569", fontSize: 11, fontWeight: 600 },
  tagX: { background: "none", border: "none", color: "#94a3b8", fontSize: 13, cursor: "pointer", padding: 0, lineHeight: 1 },
  tagInputRow: { display: "flex", gap: 4 },
  tagInput: { flex: 1, border: `1px solid ${BORDER}`, borderRadius: 6, padding: "5px 8px", fontSize: 11, color: NAVY, outline: "none", fontFamily: "inherit" },
  tagAddBtn: { width: 26, height: 26, borderRadius: 6, border: `1px solid ${BORDER}`, background: "#fff", color: NAVY, fontSize: 14, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" },

  noteInput: { width: "100%", border: `1px solid ${BORDER}`, borderRadius: 8, padding: "6px 10px", fontSize: 12, color: NAVY, outline: "none", fontFamily: "inherit", resize: "vertical", boxSizing: "border-box", marginBottom: 4 },
  noteAddBtn: { width: "100%", padding: "6px", borderRadius: 6, border: "none", background: BLUE, color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", marginBottom: 8 },
  noteCard: { padding: "8px 10px", background: "#fffbeb", borderRadius: 8, border: "1px solid #fde68a", marginBottom: 6 },
  noteText: { fontSize: 12, color: NAVY, lineHeight: 1.4 },
  noteFooter: { display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 },
  noteMeta: { fontSize: 10, color: "#92400e" },
  noteRemoveBtn: { background: "none", border: "none", color: "#d97706", fontSize: 10, cursor: "pointer", padding: 0 },

  // Email
  emailRow: { display: "flex", alignItems: "center", gap: 8, marginTop: 8, flexWrap: "wrap" },
  emailIcon: { fontSize: 14, flexShrink: 0 },
  emailLink: { fontSize: 13, color: BLUE, fontWeight: 600, textDecoration: "none" },
  emailPlaceholder: { fontSize: 12, color: "#94a3b8", fontStyle: "italic" },

  // Documents
  uploadBtn: {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
    width: "100%", padding: "8px", borderRadius: 8, border: `1px dashed ${BORDER}`,
    background: "#fafafa", color: NAVY, fontSize: 12, fontWeight: 600, cursor: "pointer",
    fontFamily: "inherit", marginBottom: 8,
  },
  docList: { display: "flex", flexDirection: "column", gap: 4 },
  docItem: { display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", background: "#f8fafc", borderRadius: 8, border: "1px solid #f0f0f0" },
  docIcon: { fontSize: 16, flexShrink: 0 },
  docInfo: { flex: 1, minWidth: 0 },
  docName: { fontSize: 11, fontWeight: 600, color: BLUE, background: "none", border: "none", padding: 0, cursor: "pointer", fontFamily: "inherit", textAlign: "left", display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", width: "100%" },
  docMeta: { fontSize: 10, color: "#94a3b8" },
  docActions: { display: "flex", gap: 2, alignItems: "center", flexShrink: 0 },
  docActionBtn: { background: "none", border: "none", fontSize: 13, cursor: "pointer", padding: "3px 4px", borderRadius: 4 },
  docDeleteBtn: { background: "none", border: "none", color: "#d1d5db", fontSize: 12, cursor: "pointer", padding: "2px 4px", flexShrink: 0 },

  // Preview modal
  previewOverlay: {
    position: "fixed", inset: 0, zIndex: 3000,
    background: "rgba(15,23,42,0.5)", backdropFilter: "blur(4px)",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
  },
  previewModal: {
    background: "#fff", borderRadius: 16, width: "90vw", maxWidth: 900,
    maxHeight: "90vh", display: "flex", flexDirection: "column",
    boxShadow: "0 20px 60px rgba(15,23,42,.25)",
    overflow: "hidden",
  },
  previewHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 18px", borderBottom: `1px solid ${BORDER}`, flexShrink: 0,
  },
  previewTitle: { fontSize: 14, fontWeight: 700, color: NAVY, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, marginRight: 12 },
  previewActionBtn: {
    width: 32, height: 32, borderRadius: 8, border: `1px solid ${BORDER}`,
    background: "#fff", fontSize: 14, cursor: "pointer", display: "flex",
    alignItems: "center", justifyContent: "center", fontFamily: "inherit",
  },
  previewCloseBtn: {
    width: 32, height: 32, borderRadius: 8, border: `1px solid ${BORDER}`,
    background: "#fff", color: "#6b7280", fontSize: 14, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit",
  },
  previewBody: { flex: 1, overflow: "auto", display: "flex", alignItems: "center", justifyContent: "center", background: "#f9fafb", minHeight: 300 },
  previewIframe: { width: "100%", height: "70vh", border: "none" },
  previewImg: { maxWidth: "100%", maxHeight: "70vh", objectFit: "contain" },
};

const CSS = `
  @keyframes uwi-pd-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .tl-item { transition: background .08s ease; }
  .tl-item:hover { background: #fafcfd; }
  .tl-item:last-child { border-bottom: none !important; }
  @media (max-width: 800px) {
    .detail-split { grid-template-columns: 1fr !important; }
    .mobile-back-btn { display: block !important; }
  }
`;
