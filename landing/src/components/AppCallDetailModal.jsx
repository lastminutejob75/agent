import { useState } from "react";

const NAVY = "#0f172a";
const TEAL = "#0DC991";
const TEAL_DARK = "#0AAF7A";
const BORDER = "#e2e8f0";
const MUTED = "#64748b";
const ORANGE = "#f59e0b";

function getDialablePhone(value) {
  const raw = String(value || "").trim();
  if (!raw || /num[eé]ro non identifi[eé]/i.test(raw)) return "";
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("00")) return `+${cleaned.slice(2)}`;
  return cleaned;
}

function IntentBadge({ call }) {
  const ui = call?.intentUi;
  if (!ui) return null;
  return <span style={{ fontSize: 10, fontWeight: 700, color: ui.color, background: ui.bg, borderRadius: 999, padding: "3px 9px" }}>{ui.label}</span>;
}

function FollowupBadge({ state }) {
  if (state === "processed") return <span style={{ fontSize: 10, fontWeight: 700, color: TEAL_DARK, background: "#e8faf4", border: "1px solid #a7f3d0", borderRadius: 999, padding: "3px 9px" }}>Traité</span>;
  if (state === "callback") return <span style={{ fontSize: 10, fontWeight: 700, color: ORANGE, background: "#fff7ed", border: "1px solid #fdba74", borderRadius: 999, padding: "3px 9px" }}>À rappeler</span>;
  return <span style={{ fontSize: 10, fontWeight: 700, color: MUTED, background: "#f1f5f9", border: `1px solid ${BORDER}`, borderRadius: 999, padding: "3px 9px" }}>Nouveau</span>;
}

export default function AppCallDetailModal({
  call,
  onClose,
  onRecall,
  onMarkCallback,
  onMarkProcessed,
  followupNotes,
  setFollowupNotes,
  onSaveNotes,
  patientNameDraft,
  setPatientNameDraft,
  patientEmailDraft,
  setPatientEmailDraft,
  patientInitialNoteDraft,
  setPatientInitialNoteDraft,
  patientDocFiles,
  setPatientDocFiles,
  onSavePatientName,
  patientSaving,
  followupLoading,
  actionMessage,
  // unused props kept for backwards compatibility
  onContextAction,
  onCopyTranscript,
  onCopySummary,
  onCopyId,
}) {
  const [tab, setTab] = useState("summary");
  if (!call) return null;

  const dialablePhone = getDialablePhone(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
  const followupState = call?.raw?.followup_state || "new";
  const isMissed = call.status === "missed" || call.status === "callback";
  const transcript = call.transcript || [];

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.panel} onClick={(e) => e.stopPropagation()}>
        {/* Status bar */}
        <div style={{ height: 3, background: call.status === "ok" ? `linear-gradient(90deg,${TEAL},${TEAL_DARK})` : (call.statusUi?.color || MUTED) }} />

        {/* Header */}
        <div style={S.header}>
          <div style={S.headerLeft}>
            <div style={S.avatar}>{(call.name || "?")[0]?.toUpperCase()}</div>
            <div>
              <div style={S.name}>{call.name || "Patient"}</div>
              <div style={S.meta}>
                {dialablePhone ? (
                  <a href={`tel:${dialablePhone}`} style={S.phoneLink}>{call.phone}</a>
                ) : (
                  <span>{call.phone}</span>
                )}
                <span style={S.dot}>·</span>
                <span>{call.time}</span>
                <span style={S.dot}>·</span>
                <span>{call.durationFmt}</span>
              </div>
              <div style={S.badges}>
                <IntentBadge call={call} />
                <FollowupBadge state={followupState} />
              </div>
            </div>
          </div>
          <button type="button" onClick={onClose} style={S.closeBtn}>✕</button>
        </div>

        {/* Tabs */}
        <div style={S.tabBar}>
          {[["summary", "Résumé"], ["transcript", "Transcription"]].map(([key, label]) => (
            <button key={key} type="button" onClick={() => setTab(key)} style={tab === key ? S.tabActive : S.tab}>{label}</button>
          ))}
        </div>

        {/* Content */}
        <div style={S.body}>
          {actionMessage ? <div style={S.toast}>{actionMessage}</div> : null}

          {tab === "summary" ? (
            <div style={S.content}>

              {/* AI Summary */}
              {call.summary ? (
                <div style={S.summaryCard}>
                  <div style={S.summaryLabel}>🧠 Résumé IA</div>
                  <div style={S.summaryText}>{call.summary}</div>
                </div>
              ) : null}

              {/* Missed call alert */}
              {isMissed && !call.aiHandled ? (
                <div style={S.alertCard}>
                  <span>⚠️</span>
                  <div>
                    <div style={S.alertTitle}>Appel manqué</div>
                    <div style={S.alertText}>Ce patient attend un rappel.</div>
                  </div>
                </div>
              ) : null}

              {/* RDV detected */}
              {call.rdv ? (
                <div style={S.rdvCard}>
                  <span style={{ fontSize: 18 }}>📅</span>
                  <div>
                    <div style={S.rdvTitle}>RDV confirmé</div>
                    <div style={S.rdvDetail}>{call.rdv.type} · {call.rdv.date} à {call.rdv.time}</div>
                  </div>
                </div>
              ) : null}

              {/* Patient name validation */}
              <div style={S.section}>
                <div style={S.sectionTitle}>Fiche patient</div>
                <div style={S.patientStatus}>
                  <span style={S.patientLabel}>Nom IA :</span>
                  <span style={S.patientRaw}>{call?.patient?.raw_name || "Non capté"}</span>
                  <span style={S.dot}>·</span>
                  <span style={{ color: call?.patient?.is_validated ? TEAL_DARK : ORANGE, fontWeight: 700, fontSize: 12 }}>
                    {call?.patient?.is_validated ? "✓ Confirmé" : "À confirmer"}
                  </span>
                </div>
                <div style={S.nameRow}>
                  <input
                    value={patientNameDraft}
                    onChange={(e) => setPatientNameDraft(e.target.value)}
                    placeholder="Nom et prénom du patient"
                    style={S.nameInput}
                  />
                  <button type="button" onClick={onSavePatientName} disabled={patientSaving} style={S.nameBtn}>
                    {patientSaving ? "…" : "Valider"}
                  </button>
                </div>
                <div style={{ ...S.nameRow, marginTop: 8 }}>
                  <input
                    value={patientEmailDraft || ""}
                    onChange={(e) => setPatientEmailDraft(e.target.value)}
                    placeholder="Email patient (optionnel)"
                    style={S.nameInput}
                  />
                </div>
                <div style={{ marginTop: 8 }}>
                  <textarea
                    value={patientInitialNoteDraft || ""}
                    onChange={(e) => setPatientInitialNoteDraft(e.target.value)}
                    placeholder="Note initiale de création de fiche (optionnel)"
                    rows={2}
                    style={S.noteInput}
                  />
                </div>
                <div style={{ marginTop: 8 }}>
                  <label style={S.uploadBtn}>
                    📎 Joindre des documents (optionnel)
                    <input
                      type="file"
                      multiple
                      onChange={(e) => {
                        const files = Array.from(e.target.files || []);
                        if (!files.length) return;
                        setPatientDocFiles([...(patientDocFiles || []), ...files]);
                        e.target.value = "";
                      }}
                      style={{ display: "none" }}
                    />
                  </label>
                  {Array.isArray(patientDocFiles) && patientDocFiles.length > 0 ? (
                    <div style={S.fileList}>
                      {patientDocFiles.map((file, idx) => (
                        <div key={`${file.name}-${idx}`} style={S.fileItem}>
                          <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</span>
                          <button
                            type="button"
                            onClick={() => setPatientDocFiles((patientDocFiles || []).filter((_, i) => i !== idx))}
                            style={S.fileRemoveBtn}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>

              {/* Actions */}
              <div style={S.actionsRow}>
                {isMissed ? (
                  <button type="button" onClick={onRecall} style={S.primaryBtn}>📞 Rappeler</button>
                ) : null}
                <button type="button" onClick={onMarkCallback} disabled={followupLoading} style={S.orangeBtn}>À rappeler</button>
                <button type="button" onClick={onMarkProcessed} disabled={followupLoading} style={S.greenBtn}>Traité</button>
              </div>

              {/* Notes */}
              <div style={S.section}>
                <div style={S.sectionTitle}>Note interne</div>
                <textarea
                  value={followupNotes}
                  onChange={(e) => setFollowupNotes(e.target.value)}
                  placeholder="Ajouter une note…"
                  style={S.noteInput}
                  rows={3}
                />
                <button type="button" onClick={onSaveNotes} disabled={followupLoading} style={S.saveNoteBtn}>Enregistrer</button>
              </div>
            </div>
          ) : null}

          {tab === "transcript" ? (
            transcript.length === 0 ? (
              <div style={S.emptyTranscript}>
                <div style={{ fontSize: 24 }}>💬</div>
                <div style={{ fontSize: 13, color: MUTED, marginTop: 8 }}>Aucune transcription disponible</div>
              </div>
            ) : (
              <div style={S.transcriptList}>
                {transcript.map((line, i) => {
                  const isAgent = line.speaker === "agent";
                  return (
                    <div key={i} style={{ ...S.bubble, flexDirection: isAgent ? "row-reverse" : "row" }}>
                      <div style={{ ...S.bubbleAvatar, background: isAgent ? "#e8faf4" : "#f0f4ff", borderColor: isAgent ? "#a7f3d0" : "#bfdbfe" }}>
                        {isAgent ? "🤖" : "👤"}
                      </div>
                      <div style={{ ...S.bubbleContent, background: isAgent ? "#e8faf4" : "#f8fafc", borderRadius: isAgent ? "12px 4px 12px 12px" : "4px 12px 12px 12px" }}>
                        <div style={{ fontSize: 9, fontWeight: 700, color: isAgent ? TEAL_DARK : MUTED, textTransform: "uppercase", marginBottom: 3 }}>
                          {isAgent ? "Agent UWI" : "Patient"}
                        </div>
                        <div style={{ fontSize: 12, color: "#334155", lineHeight: 1.5 }}>{line.text}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}

const S = {
  overlay: { position: "fixed", inset: 0, zIndex: 2000, background: "rgba(15,23,42,0.3)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center" },
  panel: { background: "#fff", borderRadius: 16, width: 480, maxWidth: "94vw", maxHeight: "85vh", boxShadow: "0 20px 50px rgba(0,0,0,0.15)", overflow: "hidden", display: "flex", flexDirection: "column" },

  header: { padding: "18px 20px 14px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" },
  headerLeft: { display: "flex", gap: 12, alignItems: "flex-start" },
  avatar: { width: 40, height: 40, borderRadius: 12, background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 800, flexShrink: 0 },
  name: { fontSize: 16, fontWeight: 800, color: NAVY },
  meta: { fontSize: 12, color: MUTED, marginTop: 2, display: "flex", alignItems: "center", gap: 4 },
  phoneLink: { color: TEAL_DARK, fontWeight: 700, textDecoration: "none" },
  dot: { color: "#d1d5db" },
  badges: { display: "flex", gap: 6, marginTop: 8 },
  closeBtn: { width: 28, height: 28, borderRadius: 8, border: `1px solid ${BORDER}`, background: "#f8fafc", color: MUTED, fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit", flexShrink: 0 },

  tabBar: { display: "flex", borderBottom: `1px solid #f1f5f9`, padding: "0 20px" },
  tab: { padding: "9px 14px", fontSize: 13, fontWeight: 500, color: MUTED, background: "none", border: "none", borderBottom: "2px solid transparent", cursor: "pointer", fontFamily: "inherit" },
  tabActive: { padding: "9px 14px", fontSize: 13, fontWeight: 700, color: TEAL_DARK, background: "none", border: "none", borderBottom: `2px solid ${TEAL}`, cursor: "pointer", fontFamily: "inherit", marginBottom: -1 },

  body: { flex: 1, overflowY: "auto", padding: "16px 20px 20px" },
  toast: { marginBottom: 12, borderRadius: 10, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", padding: "9px 12px", fontSize: 12, fontWeight: 700 },

  content: { display: "flex", flexDirection: "column", gap: 12 },

  summaryCard: { padding: "14px 16px", background: "#f0fdf4", borderRadius: 12, border: "1px solid #bbf7d0" },
  summaryLabel: { fontSize: 11, fontWeight: 800, color: TEAL_DARK, marginBottom: 4 },
  summaryText: { fontSize: 13, color: "#1e3a2f", lineHeight: 1.5 },

  alertCard: { display: "flex", gap: 10, padding: "12px 14px", background: "#fef2f2", borderRadius: 10, border: "1px solid #fecaca" },
  alertTitle: { fontSize: 12, fontWeight: 700, color: "#dc2626" },
  alertText: { fontSize: 11, color: "#ef9999", marginTop: 2 },

  rdvCard: { display: "flex", gap: 10, padding: "12px 14px", background: "#e8faf4", borderRadius: 10, border: "1px solid #a7f3d0", alignItems: "center" },
  rdvTitle: { fontSize: 12, fontWeight: 700, color: TEAL_DARK },
  rdvDetail: { fontSize: 12, color: MUTED, marginTop: 1 },

  section: { background: "#f9fafb", borderRadius: 12, padding: "14px 16px", border: `1px solid #f1f5f9` },
  sectionTitle: { fontSize: 11, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 },

  patientStatus: { display: "flex", alignItems: "center", gap: 6, marginBottom: 10, fontSize: 12 },
  patientLabel: { color: MUTED },
  patientRaw: { fontWeight: 600, color: NAVY },

  nameRow: { display: "flex", gap: 8 },
  nameInput: { flex: 1, border: `1px solid ${BORDER}`, borderRadius: 8, padding: "8px 12px", fontSize: 13, color: NAVY, outline: "none", fontFamily: "inherit" },
  nameBtn: { padding: "8px 16px", borderRadius: 8, border: "none", background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" },
  uploadBtn: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    border: `1px dashed ${BORDER}`,
    background: "#fff",
    color: MUTED,
    borderRadius: 8,
    padding: "7px 10px",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  fileList: { marginTop: 6, display: "flex", flexDirection: "column", gap: 4, maxHeight: 90, overflowY: "auto" },
  fileItem: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: "4px 8px",
    fontSize: 11,
    color: NAVY,
    background: "#fff",
  },
  fileRemoveBtn: {
    border: "none",
    background: "transparent",
    color: MUTED,
    cursor: "pointer",
    fontSize: 11,
    fontFamily: "inherit",
  },

  actionsRow: { display: "flex", gap: 8 },
  primaryBtn: { flex: 1, padding: "10px", borderRadius: 8, border: "none", background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  orangeBtn: { flex: 1, padding: "10px", borderRadius: 8, border: "1px solid #fdba74", background: "#fff7ed", color: "#d97706", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  greenBtn: { flex: 1, padding: "10px", borderRadius: 8, border: "1px solid #a7f3d0", background: "#e8faf4", color: TEAL_DARK, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },

  noteInput: { width: "100%", border: `1px solid ${BORDER}`, borderRadius: 8, padding: "8px 10px", fontSize: 12, color: NAVY, outline: "none", fontFamily: "inherit", resize: "vertical", boxSizing: "border-box" },
  saveNoteBtn: { marginTop: 8, width: "100%", padding: "8px", borderRadius: 8, border: `1px solid ${BORDER}`, background: "#fff", color: MUTED, fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },

  emptyTranscript: { padding: "32px 0", textAlign: "center" },
  transcriptList: { display: "flex", flexDirection: "column", gap: 10 },
  bubble: { display: "flex", alignItems: "flex-start", gap: 8 },
  bubbleAvatar: { width: 26, height: 26, borderRadius: "50%", border: "1px solid", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, flexShrink: 0 },
  bubbleContent: { maxWidth: "80%", padding: "8px 12px" },
};
