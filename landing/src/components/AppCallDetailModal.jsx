import { useState } from "react";

const T = {
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
  text: "#0f172a",
  textMid: "#334155",
  textSoft: "#64748b",
  textFaint: "#94a3b8",
  border: "#e2e8f0",
  borderLight: "#f1f5f9",
  bg: "#f1f5f9",
  card: "#ffffff",
};

function getActionLabel(call) {
  return call?.contextual_action?.label || "Voir le détail";
}

function getDialablePhone(value) {
  const raw = String(value || "").trim();
  if (!raw || /num[eé]ro non identifi[eé]/i.test(raw)) return "";
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("00")) return `+${cleaned.slice(2)}`;
  return cleaned;
}

function getIntentGlyph(intent) {
  switch (intent) {
    case "rdv":
      return "📅";
    case "cancel":
      return "❌";
    case "hours":
      return "🕒";
    case "urgent":
      return "🚨";
    case "reschedule":
      return "🔁";
    case "info":
    default:
      return "💬";
  }
}

function AIScoreCard({ score }) {
  if (!score) {
    return (
      <div style={{ background: T.bg, border: `1px solid ${T.borderLight}`, borderRadius: "12px", padding: "16px", textAlign: "center", color: T.textFaint, fontSize: "12px" }}>
        Aucune analyse disponible pour cet appel
      </div>
    );
  }
  const confColor = score.confidence >= 90 ? T.tealDark : score.confidence >= 75 ? T.orange : T.red;
  const sentEmoji = score.sentiment === "positif" ? "😊" : score.sentiment === "négatif" ? "😟" : "😐";
  const sentColor = score.sentiment === "positif" ? T.tealDark : score.sentiment === "négatif" ? T.red : T.textSoft;
  return (
    <div style={{ background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "12px", padding: "16px" }}>
      <div style={{ fontSize: "11px", fontWeight: 700, color: T.purple, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "14px" }}>Analyse UWI</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Confiance</div>
          <div style={{ position: "relative", width: "56px", height: "56px", margin: "0 auto 6px" }}>
            <svg width="56" height="56" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="28" cy="28" r="22" fill="none" stroke={T.purpleBorder} strokeWidth="5" />
              <circle
                cx="28"
                cy="28"
                r="22"
                fill="none"
                stroke={confColor}
                strokeWidth="5"
                strokeDasharray={`${2 * Math.PI * 22}`}
                strokeDashoffset={`${2 * Math.PI * 22 * (1 - score.confidence / 100)}`}
                strokeLinecap="round"
              />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "13px", fontWeight: 800, color: confColor }}>
              {score.confidence}%
            </div>
          </div>
          <div style={{ fontSize: "10px", color: confColor, fontWeight: 600 }}>
            {score.confidence >= 90 ? "Élevée" : score.confidence >= 75 ? "Bonne" : "Faible"}
          </div>
        </div>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Sentiment</div>
          <div style={{ fontSize: "32px", marginBottom: "4px" }}>{sentEmoji}</div>
          <div style={{ fontSize: "11px", fontWeight: 600, color: sentColor }}>{score.sentiment}</div>
        </div>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Résolution</div>
          <div style={{ fontSize: "32px", marginBottom: "4px" }}>{score.resolved ? "✅" : "❌"}</div>
          <div style={{ fontSize: "11px", fontWeight: 600, color: score.resolved ? T.tealDark : T.red }}>
            {score.resolved ? "Résolu" : "Escalade"}
          </div>
        </div>
      </div>
    </div>
  );
}

function TranscriptView({ lines }) {
  if (!lines || lines.length === 0) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center", color: T.textFaint, fontSize: "12px" }}>
        <div style={{ fontSize: "28px", marginBottom: "8px" }}>💬</div>
        Aucune transcription disponible
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {lines.map((line, index) => {
        const isAgent = line.speaker === "agent";
        return (
          <div key={`${line.text}-${index}`} style={{ display: "flex", flexDirection: isAgent ? "row-reverse" : "row", alignItems: "flex-start", gap: "9px" }}>
            <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: isAgent ? T.tealLight : "#f0f4ff", border: `1px solid ${isAgent ? T.tealBorder : T.blueBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", flexShrink: 0 }}>
              {isAgent ? "🤖" : "👤"}
            </div>
            <div style={{ maxWidth: "78%", background: isAgent ? T.tealLight : "#f8fafc", border: `1px solid ${isAgent ? T.tealBorder : T.borderLight}`, borderRadius: isAgent ? "14px 4px 14px 14px" : "4px 14px 14px 14px", padding: "9px 12px" }}>
              <div style={{ fontSize: "9px", fontWeight: 700, color: isAgent ? T.tealDark : T.textFaint, marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.07em" }}>
                {isAgent ? "Agent UWI" : "Patient"}
              </div>
              <div style={{ fontSize: "12px", color: T.textMid, lineHeight: 1.55 }}>{line.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AppCallDetailModal({
  call,
  onClose,
  onRecall,
  onContextAction,
  onMarkCallback,
  onMarkProcessed,
  onCopyTranscript,
  onCopySummary,
  onCopyId,
  followupNotes,
  setFollowupNotes,
  onSaveNotes,
  patientNameDraft,
  setPatientNameDraft,
  onSavePatientName,
  patientSaving,
  followupLoading,
  actionMessage,
}) {
  const [tab, setTab] = useState("summary");
  if (!call) return null;
  const dialablePhone = getDialablePhone(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
  const intentGlyph = getIntentGlyph(call.intent);
  const primaryActionLabel = getActionLabel(call?.raw || call);
  const followupState = call?.raw?.followup_state || "new";
  const followupBadge =
    followupState === "processed"
      ? { label: "Traité", color: T.tealDark, bg: T.tealLight, border: T.tealBorder }
      : followupState === "callback"
        ? { label: "À rappeler", color: T.orange, bg: T.orangeLight, border: T.orangeBorder }
        : { label: "Nouveau", color: T.textSoft, bg: T.bg, border: T.border };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(15,23,42,0.3)", backdropFilter: "blur(5px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div className="calls-modal-panel" style={{ background: T.card, borderRadius: "20px", width: "540px", maxWidth: "94vw", maxHeight: "88vh", boxShadow: "0 24px 60px rgba(0,0,0,0.15)", overflow: "hidden", display: "flex", flexDirection: "column" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ height: "4px", background: call.status === "ok" ? `linear-gradient(90deg,${T.teal},${T.tealDark})` : call.statusUi.color }} />

        <div style={{ padding: "20px 22px 0", flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: call.intentUi.bg, border: `1px solid ${call.intent === "urgent" ? T.redBorder : call.intent === "reschedule" ? T.purpleBorder : call.intent === "hours" ? T.orangeBorder : call.intent === "info" ? T.blueBorder : T.tealBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px" }}>
                {intentGlyph}
              </div>
              <div>
                <div style={{ fontSize: "17px", fontWeight: 800, color: T.text }}>{call.name}</div>
                <div style={{ fontSize: "12px", color: T.textSoft, marginTop: "1px" }}>
                  {dialablePhone ? (
                    <a href={`tel:${dialablePhone}`} style={{ color: call.statusUi.color, fontWeight: 700, textDecoration: "none" }}>
                      {call.phone}
                    </a>
                  ) : (
                    call.phone
                  )}
                  {" · "}
                  {call.time}
                  {" · "}
                  {call.durationFmt}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: call.intentUi.color, background: call.intentUi.bg, borderRadius: 999, padding: "3px 8px" }}>
                    {call.intentUi.label}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: followupBadge.color, background: followupBadge.bg, border: `1px solid ${followupBadge.border}`, borderRadius: 999, padding: "3px 8px" }}>
                    {followupBadge.label}
                  </span>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: "7px", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 700, color: call.statusUi.color, background: call.statusUi.bg, border: `1px solid ${call.statusUi.border}`, borderRadius: "20px", padding: "3px 10px" }}>{call.statusUi.label}</span>
              {call.aiHandled ? <span style={{ fontSize: "10px", fontWeight: 800, color: T.purple, background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "20px", padding: "3px 9px" }}>🤖 IA</span> : null}
              <button type="button" onClick={onClose} style={{ background: "#f8fafc", border: `1px solid ${T.border}`, borderRadius: "8px", width: "30px", height: "30px", cursor: "pointer", color: T.textSoft, fontSize: "13px", display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
            </div>
          </div>

          <div style={{ display: "flex", borderBottom: `1px solid ${T.borderLight}` }}>
            {[["summary", "Résumé"], ["transcript", "Transcription"], ["ai", "Analyse IA"]].map(([key, label]) => (
              <button className="calls-modal-tab" key={key} type="button" onClick={() => setTab(key)} style={{ padding: "10px 16px", fontSize: "13px", fontWeight: tab === key ? 700 : 500, color: tab === key ? T.tealDark : T.textSoft, background: "transparent", border: "none", borderBottom: tab === key ? `2px solid ${T.teal}` : "2px solid transparent", cursor: "pointer", marginBottom: "-1px", transition: "all 0.15s" }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px 22px" }}>
          {actionMessage ? <div style={{ marginBottom: 12, borderRadius: 12, border: `1px solid ${T.tealBorder}`, background: T.tealLight, color: T.tealDark, padding: "10px 12px", fontSize: 12, fontWeight: 700 }}>{actionMessage}</div> : null}

          {tab === "summary" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
                {[
                  { label: "Heure", value: call.time },
                  { label: "Durée", value: call.durationFmt },
                  { label: "Intent", value: <span style={{ fontSize: "11px", fontWeight: 700, color: call.intentUi.color, background: call.intentUi.bg, borderRadius: "5px", padding: "2px 8px" }}>{call.intentUi.label}</span> },
                ].map((row, index) => (
                  <div key={`${row.label}-${index}`} style={{ background: T.bg, borderRadius: "10px", padding: "11px 13px", border: `1px solid ${T.borderLight}` }}>
                    <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "5px" }}>{row.label}</div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: T.textMid }}>{row.value}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
                <div style={{ background: T.bg, borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "6px" }}>Résumé</div>
                  <div style={{ fontSize: "13px", color: T.textMid, lineHeight: 1.55 }}>{call.summary}</div>
                </div>

                <div style={{ background: "#f8fafc", borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "8px" }}>Action recommandée</div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: T.text, marginBottom: "4px" }}>{primaryActionLabel}</div>
                  <div style={{ fontSize: "11px", lineHeight: 1.5, color: T.textSoft }}>
                    {call.status === "missed" || call.status === "callback"
                      ? "Prioriser un rappel manuel pour ne pas perdre le patient."
                      : call.rdv
                        ? "Le rendez-vous détecté peut être revu ou confirmé dans l'agenda."
                        : "Utilisez l'action métier pour ouvrir la bonne suite côté client."}
                  </div>
                </div>
              </div>

              <div style={{ background: "#fff", borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "8px" }}>Fiche patient cabinet</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
                  <div style={{ background: T.bg, borderRadius: 10, padding: "10px 12px", border: `1px solid ${T.borderLight}` }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>Nom retranscrit</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{call?.patient?.raw_name || "Non capté"}</div>
                  </div>
                  <div style={{ background: T.bg, borderRadius: 10, padding: "10px 12px", border: `1px solid ${T.borderLight}` }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>Statut</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: call?.patient?.is_validated ? T.tealDark : T.orange }}>
                      {call?.patient?.is_validated ? "Validé et enregistré" : "À valider"}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    value={patientNameDraft}
                    onChange={(e) => setPatientNameDraft(e.target.value)}
                    placeholder="Nom et prénom validés"
                    style={{ flex: 1, height: 42, border: `1px solid ${T.border}`, borderRadius: 10, padding: "0 12px", fontSize: 13, color: T.text, outline: "none" }}
                  />
                  <button
                    className="calls-primary-btn"
                    type="button"
                    onClick={onSavePatientName}
                    disabled={patientSaving}
                    style={{ padding: "11px 14px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: 10, color: "#fff", fontSize: 12, fontWeight: 800, cursor: "pointer", whiteSpace: "nowrap" }}
                  >
                    {patientSaving ? "Enregistrement..." : "Valider le nom"}
                  </button>
                </div>
              </div>

              {call.rdv ? (
                <div style={{ background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "12px", padding: "13px 15px", display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "22px" }}>📅</span>
                  <div>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: T.tealDark, marginBottom: "2px" }}>RDV détecté / créé</div>
                    <div style={{ fontSize: "12px", color: T.textSoft }}>{call.rdv.type} · {call.rdv.date} à {call.rdv.time}</div>
                  </div>
                </div>
              ) : null}

              {call.status === "missed" && !call.aiHandled ? (
                <div style={{ background: T.redLight, border: `1px solid ${T.redBorder}`, borderRadius: "12px", padding: "13px 15px" }}>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: T.red, marginBottom: "3px" }}>⚠ Appel manqué non traité par l'IA</div>
                  <div style={{ fontSize: "11px", color: "#ef9999", lineHeight: 1.5 }}>Ce patient attend un rappel manuel.</div>
                </div>
              ) : null}

              {call.aiScore ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                  {[
                    { label: "Confiance IA", value: `${call.aiScore.confidence}%`, accent: call.aiScore.confidence >= 90 ? T.tealDark : call.aiScore.confidence >= 75 ? T.orange : T.red },
                    { label: "Sentiment", value: call.aiScore.sentiment, accent: call.aiScore.sentiment === "positif" ? T.tealDark : call.aiScore.sentiment === "négatif" ? T.red : T.textSoft },
                    { label: "Résolution", value: call.aiScore.resolved ? "Résolu" : "Escalade", accent: call.aiScore.resolved ? T.tealDark : T.red },
                  ].map((item) => (
                    <div key={item.label} style={{ background: "#fff", border: `1px solid ${T.borderLight}`, borderRadius: 12, padding: "12px 13px" }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{item.label}</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: item.accent }}>{item.value}</div>
                    </div>
                  ))}
                </div>
              ) : null}

              <div style={{ display: "flex", gap: "8px", marginTop: "4px", flexWrap: "wrap" }}>
                {(call.status === "missed" || call.status === "callback") ? (
                  <button className="calls-primary-btn" type="button" onClick={onRecall} style={{ flex: 2, padding: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: "10px", color: "#fff", fontSize: "13px", fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 14px ${T.teal}40` }}>
                    📞 Rappeler maintenant
                  </button>
                ) : (
                  <button className="calls-primary-btn" type="button" onClick={onContextAction} style={{ flex: 2, padding: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: "10px", color: "#fff", fontSize: "13px", fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 14px ${T.teal}40` }}>
                    📅 {primaryActionLabel}
                  </button>
                )}
                <button className="calls-secondary-btn" type="button" onClick={onCopySummary} style={{ flex: 1, padding: "11px", background: T.bg, border: `1px solid ${T.border}`, borderRadius: "10px", color: T.textSoft, fontSize: "13px", fontWeight: 600, cursor: "pointer" }}>
                  Copier résumé
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                <button className="calls-secondary-btn" type="button" onClick={onMarkCallback} disabled={followupLoading} style={{ padding: "10px 11px", background: T.orangeLight, border: `1px solid ${T.orangeBorder}`, borderRadius: "10px", color: T.orange, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  À rappeler
                </button>
                <button className="calls-secondary-btn" type="button" onClick={onMarkProcessed} disabled={followupLoading} style={{ padding: "10px 11px", background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "10px", color: T.tealDark, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  Marquer traité
                </button>
                <button className="calls-secondary-btn" type="button" onClick={onCopyId} style={{ padding: "10px 11px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: "10px", color: T.textSoft, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  Copier ID
                </button>
              </div>

              <div style={{ background: T.bg, borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "6px" }}>Suivi métier</div>
                <textarea
                  value={followupNotes}
                  onChange={(e) => setFollowupNotes(e.target.value)}
                  placeholder="Ajoutez une note interne."
                  style={{ width: "100%", minHeight: 86, resize: "vertical", border: `1px solid ${T.border}`, borderRadius: 10, padding: 10, fontSize: 12, color: T.textMid, background: "#fff", fontFamily: "inherit", outline: "none", boxSizing: "border-box" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 10 }}>
                  <button className="calls-secondary-btn" type="button" onClick={onSaveNotes} disabled={followupLoading} style={{ flex: 1, padding: "10px 12px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: 10, color: T.textSoft, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Enregistrer la note
                  </button>
                  <button className="calls-secondary-btn" type="button" onClick={onCopyTranscript} style={{ flex: 1, padding: "10px 12px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: 10, color: T.textSoft, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Copier transcription
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          {tab === "transcript" ? <TranscriptView lines={call.transcript} /> : null}
          {tab === "ai" ? <AIScoreCard score={call.aiScore} /> : null}
        </div>
      </div>
    </div>
  );
}
