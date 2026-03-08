import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const TEXT = "#111827";
const MUTED = "#6b7280";
const BORDER = "#e5e7eb";
const BG = "#f5f6f8";
const CARD = "#ffffff";
const BLUE = "#2563eb";
const SUCCESS = "#10b981";
const WARNING = "#f59e0b";
const DANGER = "#ef4444";

const STATUS_UI = {
  CONFIRMED: { label: "Confirmé", bg: "#dcfce7", color: "#15803d", border: "#bbf7d0" },
  FAQ: { label: "Info", bg: "#dbeafe", color: "#1d4ed8", border: "#bfdbfe" },
  TRANSFERRED: { label: "Transféré", bg: "#fee2e2", color: "#b91c1c", border: "#fecaca" },
  ABANDONED: { label: "Abandonné", bg: "#fef3c7", color: "#b45309", border: "#fcd34d" },
};

const FOLLOWUP_UI = {
  new: { label: "Nouveau", bg: "#f8fafc", color: "#475569", border: "#e2e8f0" },
  callback: { label: "À rappeler", bg: "#fff7ed", color: "#c2410c", border: "#fdba74" },
  processed: { label: "Traité", bg: "#ecfdf5", color: "#047857", border: "#a7f3d0" },
};

const REASON_UI = {
  urgency: { label: "Urgence", bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
  callback: { label: "Rappel", bg: "#fff7ed", color: "#c2410c", border: "#fdba74" },
  prescription: { label: "Ordonnance", bg: "#f5f3ff", color: "#7c3aed", border: "#ddd6fe" },
  agenda: { label: "Agenda", bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  general: { label: "Suivi", bg: "#f8fafc", color: "#475569", border: "#e2e8f0" },
};

function getStatusUi(status) {
  return STATUS_UI[status] || STATUS_UI.FAQ;
}

function getFollowupUi(state) {
  return FOLLOWUP_UI[state] || FOLLOWUP_UI.new;
}

function getReasonUi(category) {
  return REASON_UI[category] || REASON_UI.general;
}

function getCallInitials(name) {
  return String(name || "Patient")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "PT";
}

function humanizeEventLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "Événement";
  return text
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/^\w/, (char) => char.toUpperCase());
}

function Skeleton({ height = 80, radius = 14 }) {
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

async function copyToClipboard(text) {
  if (!text || !navigator?.clipboard?.writeText) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export default function AppCalls() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState(7);
  const [followupFilter, setFollowupFilter] = useState("all");
  const [payload, setPayload] = useState({ calls: [], total: 0, date: "" });
  const [selectedCallId, setSelectedCallId] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [callDetail, setCallDetail] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [followupNotes, setFollowupNotes] = useState("");
  const [followupLoading, setFollowupLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .tenantGetCalls(`?limit=50&days=${days}`)
      .then((data) => {
        if (!cancelled) setPayload(data || { calls: [], total: 0, date: "" });
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Impossible de charger les appels.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  useEffect(() => {
    if (!selectedCallId) {
      setCallDetail(null);
      setDetailError("");
      setFollowupNotes("");
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError("");
    api
      .tenantGetCallDetail(selectedCallId)
      .then((data) => {
        if (!cancelled) {
          setCallDetail(data || null);
          setFollowupNotes(data?.followup_notes || "");
        }
      })
      .catch((e) => {
        if (!cancelled) setDetailError(e?.message || "Impossible de charger le détail de l'appel.");
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCallId]);

  useEffect(() => {
    if (!actionMessage) return undefined;
    const timeout = window.setTimeout(() => setActionMessage(""), 2200);
    return () => window.clearTimeout(timeout);
  }, [actionMessage]);

  const calls = payload?.calls || [];
  const filteredCalls = useMemo(() => {
    if (followupFilter === "all") return calls;
    return calls.filter((call) => (call.followup_state || "new") === followupFilter);
  }, [calls, followupFilter]);
  const stats = useMemo(() => {
    const counters = {
      total: calls.length,
      confirmed: 0,
      faq: 0,
      transferred: 0,
      abandoned: 0,
      callback: 0,
      processed: 0,
    };
    calls.forEach((call) => {
      if (call.status === "CONFIRMED") counters.confirmed += 1;
      else if (call.status === "FAQ") counters.faq += 1;
      else if (call.status === "TRANSFERRED") counters.transferred += 1;
      else if (call.status === "ABANDONED") counters.abandoned += 1;
      if ((call.followup_state || "new") === "callback") counters.callback += 1;
      if ((call.followup_state || "new") === "processed") counters.processed += 1;
    });
    return counters;
  }, [calls]);

  async function saveFollowupState(nextState, notesOverride = followupNotes) {
    if (!selectedCallId) return;
    setFollowupLoading(true);
    try {
      const data = await api.tenantUpdateCallFollowup(selectedCallId, {
        followup_state: nextState,
        notes: notesOverride || "",
      });
      setCallDetail((prev) =>
        prev
          ? {
              ...prev,
              followup_state: data?.followup_state || nextState,
              followup_notes: data?.followup_notes || "",
              followup_updated_at: data?.followup_updated_at || "",
            }
          : prev,
      );
      setPayload((prev) => ({
        ...(prev || { calls: [] }),
        calls: (prev?.calls || []).map((call) =>
          (call.call_id || call.id) === selectedCallId
            ? {
                ...call,
                followup_state: data?.followup_state || nextState,
                followup_notes: data?.followup_notes || "",
              }
            : call,
        ),
      }));
      setFollowupNotes(data?.followup_notes || "");
      setActionMessage(
        nextState === "callback"
          ? "Appel marqué à rappeler."
          : nextState === "processed"
            ? "Appel marqué comme traité."
            : "Suivi réinitialisé.",
      );
    } catch (e) {
      setActionMessage(e?.message || "Impossible d'enregistrer le suivi.");
    } finally {
      setFollowupLoading(false);
    }
  }

  async function runContextualAction(detail) {
    const action = detail?.contextual_action?.kind || "open_detail";
    if (action === "followup_callback") {
      await saveFollowupState("callback");
      return;
    }
    if (action === "open_agenda") {
      navigate("/app/agenda");
      return;
    }
    if (action === "open_faq") {
      navigate("/app/faq");
      return;
    }
    setActionMessage("Les détails de l'appel sont déjà affichés.");
  }

  return (
    <div style={S.page}>
      <style>{CSS}</style>

      <div style={S.header}>
        <div>
          <h1 style={S.title}>Appels</h1>
          <p style={S.subtitle}>Consultez l&apos;historique des appels traités par votre assistante</p>
        </div>

        <div style={S.filters}>
          {[1, 7, 30].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setDays(value)}
              style={{
                ...S.filterButton,
                ...(days === value ? S.filterButtonActive : null),
              }}
            >
              {value === 1 ? "24h" : `${value} jours`}
            </button>
          ))}
        </div>
      </div>

      <div className="calls-stats-grid" style={S.statsGrid}>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Total appels</div>
            <div style={S.statValue}>{loading ? "—" : stats.total}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}>☎</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>RDV confirmés</div>
            <div style={{ ...S.statValue, color: SUCCESS }}>{loading ? "—" : stats.confirmed}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #10b981, #059669)" }}>✓</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Infos</div>
            <div style={{ ...S.statValue, color: BLUE }}>{loading ? "—" : stats.faq}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #60a5fa, #2563eb)" }}>i</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>À rappeler</div>
            <div style={{ ...S.statValue, color: WARNING }}>{loading ? "—" : stats.callback}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #f59e0b, #ea580c)" }}>↺</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Traités</div>
            <div style={{ ...S.statValue, color: SUCCESS }}>{loading ? "—" : stats.processed}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #10b981, #047857)" }}>✓</div>
        </div>
      </div>

      {error ? <div style={S.errorBox}>Erreur: {error}</div> : null}

      <div style={S.panel}>
        <div style={S.panelHeader}>
          <div>
            <div style={S.panelTitle}>Journal des appels</div>
            <div style={S.panelSub}>
              {days === 1 ? "Dernières 24 heures" : `Sur les ${days} derniers jours`}
            </div>
          </div>
          <div style={S.followupFilters}>
            {[
              ["all", "Tous"],
              ["new", "Nouveaux"],
              ["callback", "À rappeler"],
              ["processed", "Traités"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFollowupFilter(value)}
                style={{
                  ...S.followupButton,
                  ...(followupFilter === value ? S.followupButtonActive : null),
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div style={S.listWrap}>
          {loading ? (
            <div style={S.list}>
              {[1, 2, 3, 4, 5].map((item) => (
                <Skeleton key={item} height={90} />
              ))}
            </div>
          ) : filteredCalls.length === 0 ? (
            <div style={S.emptyState}>
              <div style={S.emptyTitle}>
                {calls.length === 0 ? "Aucun appel sur cette période" : "Aucun appel dans ce filtre"}
              </div>
              <div style={S.emptyText}>
                {calls.length === 0
                  ? "Les appels traités par UWI apparaîtront ici automatiquement."
                  : "Essayez un autre filtre de suivi pour retrouver vos appels."}
              </div>
            </div>
          ) : (
            <div style={S.list}>
              {filteredCalls.map((call) => {
                const status = getStatusUi(call.status);
                const followup = getFollowupUi(call.followup_state);
                const reason = getReasonUi(call.reason_category);
                return (
                  <button key={call.id} type="button" className="calls-row" style={S.callRow} onClick={() => setSelectedCallId(call.call_id || call.id)}>
                    <div style={S.avatar}>{getCallInitials(call.patient_name)}</div>

                    <div style={S.callMain}>
                      <div style={S.callTop}>
                        <div style={S.callName}>{call.patient_name || "Patient"}</div>
                        <div style={S.badgesRow}>
                          <span
                            style={{
                              ...S.statusBadge,
                              background: status.bg,
                              color: status.color,
                              borderColor: status.border,
                            }}
                          >
                            {status.label}
                          </span>
                          <span
                            style={{
                              ...S.statusBadge,
                              background: followup.bg,
                              color: followup.color,
                              borderColor: followup.border,
                            }}
                          >
                            {followup.label}
                          </span>
                        </div>
                      </div>

                      <div style={S.callAgent}>Assistante : {call.agent_name || "UWI"}</div>
                      <div style={S.callSummary}>{call.summary || "Aucun résumé disponible."}</div>
                      {call.reason_label ? (
                        <div style={S.reasonRow}>
                          <span
                            style={{
                              ...S.reasonBadge,
                              background: reason.bg,
                              color: reason.color,
                              borderColor: reason.border,
                            }}
                          >
                            {reason.label}
                          </span>
                          <span style={S.reasonText}>{call.reason_label}</span>
                        </div>
                      ) : null}

                      <div style={S.callMeta}>
                        <span>🕘 {call.time || "—"}</span>
                        <span>⏱ {call.duration || "—"}</span>
                        <span>ID: {call.call_id || call.id}</span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {selectedCallId ? (
        <div style={S.modalOverlay} onClick={() => setSelectedCallId("")}>
          <div style={S.modalCard} onClick={(e) => e.stopPropagation()}>
            <div style={S.modalHeader}>
              <div>
                <div style={S.modalTitle}>Détail de l&apos;appel</div>
                <div style={S.modalSub}>ID: {selectedCallId}</div>
              </div>
              <button type="button" style={S.closeButton} onClick={() => setSelectedCallId("")}>
                ✕
              </button>
            </div>

            {detailLoading ? (
              <div style={S.modalBody}>
                <Skeleton height={80} />
                <Skeleton height={140} />
              </div>
            ) : detailError ? (
              <div style={S.modalBody}>
                <div style={S.errorBox}>Erreur: {detailError}</div>
              </div>
            ) : callDetail ? (
              <div style={S.modalBody}>
                <div style={S.actionRow}>
                  <button
                    type="button"
                    style={S.actionButtonPrimary}
                    onClick={async () => {
                      const ok = await copyToClipboard(callDetail.transcript || "");
                      setActionMessage(ok ? "Transcription copiée." : "Impossible de copier la transcription.");
                    }}
                  >
                    Copier la transcription
                  </button>
                  <button
                    type="button"
                    style={S.actionButton}
                    onClick={async () => {
                      const ok = await copyToClipboard(callDetail.summary || "");
                      setActionMessage(ok ? "Résumé copié." : "Impossible de copier le résumé.");
                    }}
                  >
                    Copier le résumé
                  </button>
                  <button
                    type="button"
                    style={S.actionButton}
                    onClick={async () => {
                      const ok = await copyToClipboard(callDetail.call_id || selectedCallId);
                      setActionMessage(ok ? "ID d'appel copié." : "Impossible de copier l'identifiant.");
                    }}
                  >
                    Copier l&apos;ID
                  </button>
                  <button
                    type="button"
                    style={S.actionButton}
                    disabled={followupLoading}
                    onClick={() => saveFollowupState("callback")}
                  >
                    Marquer à rappeler
                  </button>
                  <button
                    type="button"
                    style={S.actionButton}
                    disabled={followupLoading}
                    onClick={() => saveFollowupState("processed")}
                  >
                    Marquer traité
                  </button>
                  <button
                    type="button"
                    style={S.actionButton}
                    disabled={followupLoading}
                    onClick={() => runContextualAction(callDetail)}
                  >
                    {callDetail.contextual_action?.label || "Action conseillée"}
                  </button>
                </div>

                {actionMessage ? <div style={S.successInline}>{actionMessage}</div> : null}

                <div className="calls-detail-grid" style={S.detailTopGrid}>
                  <div style={S.detailInfoCard}>
                    <div style={S.detailLabel}>Statut</div>
                    <div style={S.detailValue}>
                      <span
                        style={{
                          ...S.statusBadge,
                          background: getStatusUi(callDetail.status).bg,
                          color: getStatusUi(callDetail.status).color,
                          borderColor: getStatusUi(callDetail.status).border,
                        }}
                      >
                        {getStatusUi(callDetail.status).label}
                      </span>
                    </div>
                  </div>
                  <div style={S.detailInfoCard}>
                    <div style={S.detailLabel}>Heure</div>
                    <div style={S.detailValue}>{callDetail.started_time || "—"}</div>
                  </div>
                  <div style={S.detailInfoCard}>
                    <div style={S.detailLabel}>Durée</div>
                    <div style={S.detailValue}>{callDetail.duration || "—"}</div>
                  </div>
                  <div style={S.detailInfoCard}>
                    <div style={S.detailLabel}>Suivi</div>
                    <div style={S.detailValue}>
                      <span
                        style={{
                          ...S.statusBadge,
                          background: getFollowupUi(callDetail.followup_state).bg,
                          color: getFollowupUi(callDetail.followup_state).color,
                          borderColor: getFollowupUi(callDetail.followup_state).border,
                        }}
                      >
                        {getFollowupUi(callDetail.followup_state).label}
                      </span>
                    </div>
                  </div>
                  <div style={S.detailInfoCard}>
                    <div style={S.detailLabel}>Motif</div>
                    <div style={S.detailValue}>
                      <span
                        style={{
                          ...S.statusBadge,
                          background: getReasonUi(callDetail.reason_category).bg,
                          color: getReasonUi(callDetail.reason_category).color,
                          borderColor: getReasonUi(callDetail.reason_category).border,
                        }}
                      >
                        {getReasonUi(callDetail.reason_category).label}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={S.detailSection}>
                  <div style={S.detailSectionTitle}>Résumé</div>
                  <div style={S.detailText}>{callDetail.summary || "Aucun résumé disponible."}</div>
                </div>

                {callDetail.reason_label || callDetail.reason_context ? (
                  <div style={S.detailSection}>
                    <div style={S.detailSectionTitle}>Raison de transfert / demande</div>
                    <div style={S.reasonCard}>
                      {callDetail.reason_label ? <div style={S.reasonCardTitle}>{callDetail.reason_label}</div> : null}
                      {callDetail.reason_context ? <div style={S.detailText}>{callDetail.reason_context}</div> : null}
                    </div>
                  </div>
                ) : null}

                <div style={S.detailSection}>
                  <div style={S.detailSectionTitle}>Suivi métier</div>
                  <div style={S.followupCard}>
                    <textarea
                      value={followupNotes}
                      onChange={(e) => setFollowupNotes(e.target.value)}
                      placeholder="Ajoutez une note interne, un contexte de rappel ou une action réalisée."
                      style={S.followupTextarea}
                    />
                    <div style={S.followupActions}>
                      <button
                        type="button"
                        style={S.actionButtonPrimary}
                        disabled={followupLoading}
                        onClick={() => saveFollowupState(callDetail.followup_state || "new", followupNotes)}
                      >
                        Enregistrer la note
                      </button>
                      <button
                        type="button"
                        style={S.actionButton}
                        disabled={followupLoading}
                        onClick={() => saveFollowupState("new", followupNotes)}
                      >
                        Réinitialiser le suivi
                      </button>
                    </div>
                  </div>
                </div>

                <div style={S.detailSection}>
                  <div style={S.detailSectionTitle}>Transcription</div>
                  <div style={S.transcriptBox}>
                    {callDetail.transcript ? (
                      <pre style={S.transcriptText}>{callDetail.transcript}</pre>
                    ) : (
                      <div style={S.detailText}>Aucune transcription disponible pour cet appel.</div>
                    )}
                  </div>
                </div>

                <div style={S.detailSection}>
                  <div style={S.detailSectionTitle}>Événements</div>
                  <div style={S.timelineList}>
                    {(callDetail.events || []).length > 0 ? (
                      callDetail.events.map((event, index) => (
                        <div key={`${event.created_at || event.time}-${index}`} style={S.timelineRow}>
                          <div style={S.timelineTime}>{event.time || "—"}</div>
                          <div style={S.timelineContent}>
                            <div style={S.timelineEvent}>{humanizeEventLabel(event.event)}</div>
                            {event.reason ? <div style={S.timelineMeta}>Raison : {event.reason}</div> : null}
                            {event.context ? <div style={S.timelineMeta}>Contexte : {event.context}</div> : null}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={S.detailText}>Aucun événement détaillé disponible.</div>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

const S = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: 18,
    paddingBottom: 24,
    color: TEXT,
    background: BG,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 18,
    lineHeight: 1.1,
    fontWeight: 800,
    color: TEXT,
  },
  subtitle: {
    margin: "6px 0 0",
    fontSize: 12,
    color: MUTED,
  },
  filters: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  filterButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    padding: "9px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  filterButtonActive: {
    borderColor: "#bfdbfe",
    background: "#eff6ff",
    color: "#1d4ed8",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
    gap: 16,
  },
  statCard: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    padding: "14px 16px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  statLabel: {
    fontSize: 12,
    color: MUTED,
    marginBottom: 8,
  },
  statValue: {
    fontSize: 18,
    lineHeight: 1,
    fontWeight: 700,
    color: TEXT,
  },
  statIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#fff",
    fontSize: 14,
    fontWeight: 800,
    boxShadow: "0 8px 18px rgba(37,99,235,.16)",
    flexShrink: 0,
  },
  errorBox: {
    borderRadius: 14,
    border: "1px solid #fecaca",
    background: "#fef2f2",
    color: "#b91c1c",
    padding: "12px 14px",
    fontSize: 14,
    fontWeight: 600,
  },
  panel: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  panelHeader: {
    padding: "18px 18px 14px",
    background: "#fafafa",
    borderBottom: `1px solid ${BORDER}`,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
    flexWrap: "wrap",
  },
  panelTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: TEXT,
  },
  panelSub: {
    marginTop: 4,
    fontSize: 12,
    color: MUTED,
  },
  listWrap: {
    padding: 18,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  followupFilters: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  followupButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#64748b",
    borderRadius: 999,
    padding: "7px 11px",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
  },
  followupButtonActive: {
    borderColor: "#99f6e4",
    background: "#ecfeff",
    color: "#0f766e",
  },
  callRow: {
    width: "100%",
    textAlign: "left",
    display: "flex",
    gap: 14,
    alignItems: "flex-start",
    padding: "14px 16px",
    borderRadius: 14,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    boxShadow: "0 1px 4px rgba(15,23,42,.02)",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 10,
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 12,
    fontWeight: 800,
    flexShrink: 0,
    boxShadow: "0 6px 12px rgba(37,99,235,.12)",
  },
  callMain: {
    flex: 1,
    minWidth: 0,
  },
  callTop: {
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "flex-start",
    flexWrap: "wrap",
  },
  badgesRow: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  callName: {
    fontSize: 15,
    fontWeight: 700,
    color: TEXT,
    lineHeight: 1.1,
  },
  statusBadge: {
    borderRadius: 999,
    padding: "5px 10px",
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid",
  },
  callAgent: {
    marginTop: 6,
    fontSize: 12,
    color: "#4b5563",
  },
  callSummary: {
    marginTop: 5,
    fontSize: 11,
    color: "#6b7280",
    lineHeight: 1.5,
  },
  reasonRow: {
    marginTop: 8,
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  reasonBadge: {
    borderRadius: 999,
    padding: "4px 8px",
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid",
  },
  reasonText: {
    fontSize: 11,
    color: "#475569",
    lineHeight: 1.5,
  },
  callMeta: {
    marginTop: 10,
    display: "flex",
    gap: 12,
    flexWrap: "wrap",
    fontSize: 11,
    color: MUTED,
  },
  emptyState: {
    padding: "28px 18px 20px",
    textAlign: "center",
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: 800,
    color: TEXT,
  },
  emptyText: {
    marginTop: 8,
    fontSize: 14,
    color: MUTED,
  },
  modalOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(15,23,42,.38)",
    display: "flex",
    justifyContent: "flex-end",
    zIndex: 50,
  },
  modalCard: {
    width: "min(640px, 100vw)",
    height: "100%",
    background: "#fff",
    borderLeft: `1px solid ${BORDER}`,
    boxShadow: "-12px 0 40px rgba(15,23,42,.12)",
    display: "flex",
    flexDirection: "column",
  },
  modalHeader: {
    padding: "18px 18px 14px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#fafafa",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: TEXT,
  },
  modalSub: {
    marginTop: 4,
    fontSize: 12,
    color: MUTED,
  },
  closeButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    width: 34,
    height: 34,
    cursor: "pointer",
  },
  actionRow: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  actionButtonPrimary: {
    border: "none",
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  actionButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  modalBody: {
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 16,
    overflowY: "auto",
  },
  detailTopGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 12,
  },
  detailInfoCard: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#fff",
    padding: "14px 16px",
  },
  detailLabel: {
    fontSize: 12,
    color: MUTED,
    marginBottom: 8,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: 700,
    color: TEXT,
  },
  detailSection: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  detailSectionTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: TEXT,
  },
  detailText: {
    fontSize: 13,
    lineHeight: 1.6,
    color: "#4b5563",
  },
  reasonCard: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#fff",
    padding: "14px 16px",
  },
  reasonCardTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: TEXT,
    marginBottom: 6,
  },
  followupCard: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  followupTextarea: {
    width: "100%",
    minHeight: 110,
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    padding: "12px 14px",
    fontSize: 13,
    lineHeight: 1.6,
    color: TEXT,
    resize: "vertical",
    fontFamily: "inherit",
    outline: "none",
  },
  followupActions: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  transcriptBox: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
  },
  transcriptText: {
    margin: 0,
    whiteSpace: "pre-wrap",
    fontFamily: "inherit",
    fontSize: 13,
    lineHeight: 1.7,
    color: "#334155",
  },
  successInline: {
    borderRadius: 12,
    border: "1px solid #a7f3d0",
    background: "#ecfdf5",
    color: "#047857",
    padding: "10px 12px",
    fontSize: 13,
    fontWeight: 600,
  },
  timelineList: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  timelineRow: {
    display: "grid",
    gridTemplateColumns: "64px 1fr",
    gap: 12,
    alignItems: "flex-start",
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#fff",
    padding: "12px 14px",
  },
  timelineTime: {
    fontSize: 12,
    fontWeight: 700,
    color: "#1f2937",
  },
  timelineContent: {
    minWidth: 0,
  },
  timelineEvent: {
    fontSize: 13,
    fontWeight: 700,
    color: TEXT,
  },
  timelineMeta: {
    marginTop: 4,
    fontSize: 12,
    color: "#64748b",
    lineHeight: 1.5,
  },
};

const CSS = `
  @keyframes uwi-calls-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .calls-row {
    transition: background .16s ease, transform .16s ease, box-shadow .16s ease;
  }

  .calls-row:hover {
    background: #fafcfd;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(15,23,42,.05);
  }

  @media (max-width: 1100px) {
    .calls-stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
  }

  @media (max-width: 760px) {
    .calls-stats-grid {
      grid-template-columns: 1fr !important;
    }

    .calls-row {
      flex-direction: column;
    }
  }

  @media (max-width: 720px) {
    .calls-detail-grid {
      grid-template-columns: 1fr !important;
    }
  }
`;
