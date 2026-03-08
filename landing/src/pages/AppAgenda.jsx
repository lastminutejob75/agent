import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const BLUE = "#2563eb";
const BLUE_DARK = "#1d4ed8";
const TEXT = "#111827";
const MUTED = "#6b7280";
const BORDER = "#e5e7eb";
const BG = "#f5f6f8";
const CARD = "#ffffff";
const SUCCESS = "#10b981";
const SUCCESS_SOFT = "#dcfce7";
const WARNING = "#f59e0b";
const WARNING_SOFT = "#fef3c7";
const INFO = "#64748b";
const INFO_SOFT = "#f1f5f9";

function shiftDate(dateStr, diff) {
  const date = new Date(`${dateStr}T12:00:00`);
  date.setDate(date.getDate() + diff);
  return date.toISOString().slice(0, 10);
}

function formatLongDate(dateStr) {
  if (!dateStr) return "—";
  const date = new Date(`${dateStr}T12:00:00`);
  const text = date.toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatTimeLabel(hour) {
  const value = String(hour || "").trim();
  if (!value) return "—";
  if (/^\d{2}h$/.test(value)) return `${value.slice(0, 2)}:00`;
  if (/^\d{1,2}h$/.test(value)) return `${value.replace("h", "").padStart(2, "0")}:00`;
  if (/^\d{2}:\d{2}$/.test(value)) return value;
  return value.replace("h", ":");
}

function getInitials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() || "").join("") || "RDV";
}

function getPythonWeekday(dateStr) {
  const jsDay = new Date(`${dateStr}T12:00:00`).getDay();
  return (jsDay + 6) % 7;
}

function buildEmptyTimeline(dateStr, horaires) {
  const days = Array.isArray(horaires?.booking_days) ? horaires.booking_days : [];
  const start = Number(horaires?.booking_start_hour ?? 9);
  const end = Number(horaires?.booking_end_hour ?? 18);
  if (!days.length || start >= end) {
    return { closed: false, rows: [] };
  }
  if (!days.includes(getPythonWeekday(dateStr))) {
    return { closed: true, rows: [] };
  }
  const rows = [];
  for (let hour = start; hour < end; hour += 1) {
    rows.push(`${String(hour).padStart(2, "0")}:00`);
  }
  return { closed: false, rows };
}

function getStatus(slot) {
  if (slot?.current) {
    return { label: "En attente", bg: WARNING_SOFT, color: "#b45309", border: "#fcd34d" };
  }
  if (slot?.done) {
    return { label: "Confirmé", bg: SUCCESS_SOFT, color: "#0f766e", border: "#a7f3d0" };
  }
  return { label: "Confirmé", bg: SUCCESS_SOFT, color: "#0f766e", border: "#a7f3d0" };
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

export default function AppAgenda() {
  const navigate = useNavigate();
  const setupRef = useRef(null);
  const [me, setMe] = useState(null);
  const [config, setConfig] = useState(null);
  const [agenda, setAgenda] = useState(null);
  const [horaires, setHoraires] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [calendarId, setCalendarId] = useState("");
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const [verifySuccess, setVerifySuccess] = useState(false);
  const [contactSoftware, setContactSoftware] = useState("pabau");
  const [contactOther, setContactOther] = useState("");
  const [contactLoading, setContactLoading] = useState(false);
  const [contactSent, setContactSent] = useState(false);
  const [noneLoading, setNoneLoading] = useState(false);
  const [noneDone, setNoneDone] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [slotOptions, setSlotOptions] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedNewSlotId, setSelectedNewSlotId] = useState("");
  const [appointmentActionLoading, setAppointmentActionLoading] = useState(false);

  const loadAgenda = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextMe, nextConfig, nextAgenda, nextHoraires] = await Promise.all([
        api.tenantMe(),
        api.agendaConfig(),
        api.tenantGetAgenda(`?date=${selectedDate}`),
        api.tenantGetHoraires(),
      ]);
      setMe(nextMe);
      setConfig(nextConfig);
      setAgenda(nextAgenda);
      setHoraires(nextHoraires);
      setCalendarId(nextMe?.calendar_id || "");
    } catch (e) {
      setError(e?.message || "Impossible de charger l'agenda.");
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    loadAgenda();
  }, [loadAgenda]);

  const isConnected = me?.calendar_provider === "google" && me?.calendar_id;
  const serviceAccountEmail =
    config?.service_account_email ||
    import.meta.env.VITE_SERVICE_ACCOUNT_EMAIL ||
    "uwi-bot@xxx.iam.gserviceaccount.com";

  const appointments = useMemo(
    () =>
      (agenda?.slots || []).map((slot, index) => ({
        ...slot,
        id: slot.event_id || `${slot.hour || "slot"}-${index}`,
        displayTime: formatTimeLabel(slot.hour),
        initials: getInitials(slot.patient),
        duration: Number(horaires?.booking_duration_minutes || 30),
        status: getStatus(slot),
        sourceLabel: slot.source === "UWI" ? "Téléphone" : "Agenda externe",
        sourceBadge: slot.source === "UWI" ? "UWI" : "Externe",
        detailLine: slot.source === "UWI" ? "Réservation via l'assistant vocal" : "Synchronisé depuis l'agenda connecté",
        appointmentId: slot.appointment_id,
        slotId: slot.slot_id,
        canCancel: !!slot.can_cancel,
        canReschedule: !!slot.can_reschedule,
      })),
    [agenda, horaires],
  );

  const emptyTimeline = useMemo(() => buildEmptyTimeline(selectedDate, horaires), [selectedDate, horaires]);
  const totalAppointments = agenda?.total || 0;
  const doneAppointments = agenda?.done || 0;
  const upcomingAppointments = agenda?.remaining || 0;

  const scrollToSetup = () => {
    setupRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleVerifyGoogle = async () => {
    if (!calendarId.trim()) return;
    setVerifyLoading(true);
    setVerifyError("");
    setVerifySuccess(false);
    try {
      const res = await api.agendaVerifyGoogle(calendarId.trim());
      if (res?.ok) {
        setVerifySuccess(true);
        await loadAgenda();
        return;
      }
      if (res?.reason === "permission") {
        setVerifyError(`Accès refusé. Vérifiez le partage avec ${serviceAccountEmail}`);
      } else if (res?.reason === "not_found") {
        setVerifyError("Calendrier introuvable. Vérifiez l'ID copié.");
      } else if (res?.reason === "error") {
        setVerifyError("Erreur technique. Réessayez dans quelques instants.");
      } else {
        setVerifyError(res?.message || "Erreur lors de la vérification.");
      }
    } catch (e) {
      setVerifyError(e?.message || "Erreur de connexion. Réessayez.");
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleContactRequest = async () => {
    setContactLoading(true);
    setContactSent(false);
    setVerifyError("");
    try {
      await api.agendaContactRequest(contactSoftware, contactSoftware === "autre" ? contactOther : "");
      setContactSent(true);
    } catch (e) {
      setVerifyError(e?.message || "Erreur lors de l'envoi. Réessayez.");
    } finally {
      setContactLoading(false);
    }
  };

  const handleActivateNone = async () => {
    setNoneLoading(true);
    setNoneDone(false);
    try {
      await api.agendaActivateNone();
      setNoneDone(true);
      await loadAgenda();
    } catch (e) {
      setVerifyError(e?.message || "Erreur. Réessayez.");
    } finally {
      setNoneLoading(false);
    }
  };

  useEffect(() => {
    if (!actionMessage) return undefined;
    const timeout = window.setTimeout(() => setActionMessage(""), 2200);
    return () => window.clearTimeout(timeout);
  }, [actionMessage]);

  useEffect(() => {
    if (!selectedAppointment?.canReschedule) {
      setSlotOptions([]);
      setSelectedNewSlotId("");
      return undefined;
    }
    let cancelled = false;
    setSlotsLoading(true);
    api
      .tenantGetAgendaAvailableSlots("?limit=8")
      .then((data) => {
        if (!cancelled) {
          const slots = (data?.slots || []).filter((slot) => String(slot.slot_id) !== String(selectedAppointment.slotId || ""));
          setSlotOptions(slots);
          setSelectedNewSlotId(slots[0]?.slot_id ? String(slots[0].slot_id) : "");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSlotOptions([]);
          setSelectedNewSlotId("");
        }
      })
      .finally(() => {
        if (!cancelled) setSlotsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAppointment]);

  if (loading) {
    return (
      <div style={S.page}>
        <div style={S.panel}>
          <p style={S.loading}>Chargement de l'agenda…</p>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <style>{CSS}</style>

      <div style={S.header}>
        <div>
          <h1 style={S.title}>Agenda</h1>
          <p style={S.subtitle}>Gérez vos rendez-vous et appels planifiés</p>
        </div>
        <button type="button" onClick={scrollToSetup} style={S.primaryButton}>
          + Nouveau rendez-vous
        </button>
      </div>

      <div className="agenda-page-stats" style={S.statsGrid}>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Total rendez-vous</div>
            <div style={S.statValue}>{totalAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}>📅</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Terminés</div>
            <div style={{ ...S.statValue, color: SUCCESS }}>{doneAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #10b981, #059669)" }}>✓</div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>À venir</div>
            <div style={{ ...S.statValue, color: WARNING }}>{upcomingAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>◌</div>
        </div>
      </div>

      <div style={S.dateBar}>
        <button type="button" onClick={() => setSelectedDate((value) => shiftDate(value, -1))} style={S.navButton}>
          ‹
        </button>
        <div style={S.dateTitle}>{formatLongDate(selectedDate)}</div>
        <button type="button" onClick={() => setSelectedDate((value) => shiftDate(value, 1))} style={S.navButton}>
          ›
        </button>
      </div>

      {!isConnected ? (
        <div style={S.notice}>
          <div>
            <div style={S.noticeTitle}>Agenda UWI déjà actif</div>
            <div style={S.noticeText}>
              Même sans agenda Google connecté, cette vue affiche les rendez-vous pris par l'assistant dans le calendrier UWI.
            </div>
          </div>
          <button type="button" onClick={scrollToSetup} style={S.noticeButton}>
            Finaliser la connexion
          </button>
        </div>
      ) : (
        <div style={{ ...S.notice, borderColor: "#bfdbfe", background: "#eff6ff" }}>
          <div>
            <div style={S.noticeTitle}>Agenda externe connecté</div>
            <div style={S.noticeText}>
              Google Calendar est bien relié. Les rendez-vous du jour remontent ici automatiquement.
            </div>
          </div>
          <div style={S.connectedBadge}>Google actif</div>
        </div>
      )}

      {error ? <div style={S.errorBox}>Erreur: {error}</div> : null}

      <div style={S.panel}>
        <div style={S.panelHeader}>
          <div style={S.panelTitle}>Planning du jour</div>
        </div>

        {appointments.length > 0 ? (
          <div style={S.appointmentsWrap}>
            <div style={S.appointmentsList}>
            {appointments.map((appointment) => (
              <button
                className="agenda-appointment-card"
                key={appointment.id}
                type="button"
                onClick={() => setSelectedAppointment(appointment)}
                style={{
                  ...S.appointmentCard,
                  borderColor: appointment.status.border,
                  background: "#ffffff",
                }}
              >
                <div style={S.avatar}>{appointment.initials}</div>
                <div style={S.appointmentContent}>
                  <div style={S.patientName}>{appointment.patient || "Patient"}</div>
                  <div style={S.appointmentType}>{appointment.type || "Consultation"}</div>
                  <div style={S.appointmentDetail}>{appointment.detailLine}</div>
                  <div style={S.metaRow}>
                    <span>🕘 {appointment.displayTime}</span>
                    <span>({appointment.duration} min)</span>
                    <span>{appointment.sourceLabel}</span>
                  </div>
                </div>
                <div className="agenda-badges-col" style={S.badgesCol}>
                  <span
                    style={{
                      ...S.statusBadge,
                      background: appointment.status.bg,
                      color: appointment.status.color,
                      borderColor: appointment.status.border,
                    }}
                  >
                    {appointment.status.label}
                  </span>
                </div>
              </button>
            ))}
            </div>
          </div>
        ) : emptyTimeline.closed ? (
          <div style={S.emptyState}>
            <div style={S.emptyTitle}>Cabinet fermé ce jour</div>
            <div style={S.emptyText}>Aucun créneau prévu selon vos horaires actuels.</div>
            <button type="button" onClick={() => navigate("/app/horaires")} style={S.secondaryButton}>
              Modifier mes horaires
            </button>
          </div>
        ) : emptyTimeline.rows.length > 0 ? (
          <div style={S.emptyTimeline}>
            <div style={S.emptyTitle}>Aucun rendez-vous planifié</div>
            <div style={S.emptyText}>Les créneaux d'ouverture restent visibles, même si aucun agenda externe n'est connecté.</div>
            <div style={S.emptyRows}>
              {emptyTimeline.rows.map((row) => (
                <div key={row} style={S.emptyRow}>
                  <span style={S.emptyHour}>{row}</span>
                  <span style={S.emptyLabel}>Libre</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={S.emptyState}>
            <div style={S.emptyTitle}>Aucun horaire configuré</div>
            <div style={S.emptyText}>Définissez vos horaires pour afficher un agenda exploitable par l'assistant.</div>
            <button type="button" onClick={() => navigate("/app/horaires")} style={S.secondaryButton}>
              Configurer mes horaires
            </button>
          </div>
        )}
      </div>

      <div ref={setupRef} style={S.setupGrid}>
        <div style={S.setupCard}>
          <div style={S.setupTitle}>Connecter Google Calendar</div>
          <div style={S.setupText}>
            Partagez votre calendrier avec <code style={S.code}>{serviceAccountEmail}</code>, puis collez son identifiant.
          </div>
          <input
            type="text"
            value={calendarId}
            onChange={(e) => setCalendarId(e.target.value)}
            placeholder="xxx@group.calendar.google.com"
            style={S.input}
          />
          <button type="button" onClick={handleVerifyGoogle} disabled={verifyLoading || !calendarId.trim()} style={S.primaryButton}>
            {verifyLoading ? "Vérification…" : "Vérifier et connecter"}
          </button>
          {verifySuccess ? <div style={S.successBox}>Agenda connecté avec succès.</div> : null}
          {verifyError ? <div style={S.errorInline}>{verifyError}</div> : null}
        </div>

        <div style={S.setupCard}>
          <div style={S.setupTitle}>Logiciel métier</div>
          <div style={S.setupText}>Pabau, Maiia, Doctolib ou autre logiciel cabinet: notre équipe finalise la connexion avec vous.</div>
          <select value={contactSoftware} onChange={(e) => setContactSoftware(e.target.value)} style={S.input}>
            <option value="pabau">Pabau</option>
            <option value="maiia">Maiia</option>
            <option value="doctolib">Doctolib</option>
            <option value="autre">Autre</option>
          </select>
          {contactSoftware === "autre" ? (
            <input
              type="text"
              value={contactOther}
              onChange={(e) => setContactOther(e.target.value)}
              placeholder="Précisez le logiciel"
              style={S.input}
            />
          ) : null}
          <button type="button" onClick={handleContactRequest} disabled={contactLoading} style={S.secondaryButton}>
            {contactLoading ? "Envoi…" : "Demander le setup"}
          </button>
          {contactSent ? <div style={S.successBox}>Demande envoyée. Notre équipe vous recontacte.</div> : null}
        </div>

        <div style={S.setupCard}>
          <div style={S.setupTitle}>Mode sans agenda externe</div>
          <div style={S.setupText}>
            Si vous ne connectez pas encore Google, UWI garde son propre agenda interne et continue de prendre les rendez-vous.
          </div>
          <button type="button" onClick={handleActivateNone} disabled={noneLoading} style={S.secondaryButton}>
            {noneLoading ? "Activation…" : "Activer ce mode"}
          </button>
          {noneDone ? <div style={S.successBox}>Mode agenda interne activé.</div> : null}
        </div>
      </div>

      {selectedAppointment ? (
        <div style={S.modalOverlay} onClick={() => setSelectedAppointment(null)}>
          <div style={S.modalCard} onClick={(e) => e.stopPropagation()}>
            <div style={S.modalHeader}>
              <div>
                <div style={S.modalTitle}>Détail du rendez-vous</div>
                <div style={S.modalSub}>{selectedAppointment.patient || "Patient"}</div>
              </div>
              <button type="button" style={S.closeButton} onClick={() => setSelectedAppointment(null)}>
                ✕
              </button>
            </div>

            <div style={S.modalBody}>
              <div style={S.actionRow}>
                <button
                  type="button"
                  style={S.actionButtonPrimary}
                  onClick={async () => {
                    const ok = await copyToClipboard(
                      [
                        selectedAppointment.patient || "Patient",
                        selectedAppointment.type || "Consultation",
                        `Heure: ${selectedAppointment.displayTime || "—"}`,
                        `Durée: ${selectedAppointment.duration || "—"} min`,
                        `Source: ${selectedAppointment.sourceLabel || "UWI"}`,
                      ].join("\n"),
                    );
                    setActionMessage(ok ? "Détails du rendez-vous copiés." : "Impossible de copier les détails.");
                  }}
                >
                  Copier les détails
                </button>
                <button type="button" style={S.actionButton} onClick={() => navigate("/app/horaires")}>
                  Modifier mes horaires
                </button>
                {selectedAppointment.canCancel ? (
                  <button
                    type="button"
                    style={S.actionDangerButton}
                    disabled={appointmentActionLoading}
                    onClick={async () => {
                      try {
                        setAppointmentActionLoading(true);
                        await api.tenantCancelAgendaAppointment(
                          selectedAppointment.appointmentId || selectedAppointment.id,
                          { source: selectedAppointment.source },
                        );
                        setActionMessage("Rendez-vous annulé.");
                        setSelectedAppointment(null);
                        await loadAgenda();
                      } catch (e) {
                        setActionMessage(e?.message || "Impossible d'annuler ce rendez-vous.");
                      } finally {
                        setAppointmentActionLoading(false);
                      }
                    }}
                  >
                    Annuler le RDV
                  </button>
                ) : null}
                {!isConnected ? (
                  <button
                    type="button"
                    style={S.actionButton}
                    onClick={() => {
                      setSelectedAppointment(null);
                      scrollToSetup();
                    }}
                  >
                    Connecter Google
                  </button>
                ) : null}
              </div>

              {actionMessage ? <div style={S.successInline}>{actionMessage}</div> : null}

              <div className="agenda-detail-grid" style={S.detailTopGrid}>
                <div style={S.detailInfoCard}>
                  <div style={S.detailLabel}>Heure</div>
                  <div style={S.detailValue}>{selectedAppointment.displayTime || "—"}</div>
                </div>
                <div style={S.detailInfoCard}>
                  <div style={S.detailLabel}>Durée</div>
                  <div style={S.detailValue}>{selectedAppointment.duration || "—"} min</div>
                </div>
                <div style={S.detailInfoCard}>
                  <div style={S.detailLabel}>Statut</div>
                  <div style={S.detailValue}>
                    <span
                      style={{
                        ...S.statusBadge,
                        background: selectedAppointment.status.bg,
                        color: selectedAppointment.status.color,
                        borderColor: selectedAppointment.status.border,
                      }}
                    >
                      {selectedAppointment.status.label}
                    </span>
                  </div>
                </div>
              </div>

              <div style={S.detailSection}>
                <div style={S.detailSectionTitle}>Motif</div>
                <div style={S.detailText}>{selectedAppointment.type || "Consultation"}</div>
              </div>

              <div style={S.detailSection}>
                <div style={S.detailSectionTitle}>Source</div>
                <div style={S.detailText}>{selectedAppointment.sourceLabel || "UWI"}</div>
              </div>

              <div style={S.detailSection}>
                <div style={S.detailSectionTitle}>Informations</div>
                <div style={S.transcriptBox}>
                  <div style={S.detailText}>{selectedAppointment.detailLine || "Aucun détail supplémentaire."}</div>
                </div>
              </div>

              {selectedAppointment.canReschedule ? (
                <div style={S.detailSection}>
                  <div style={S.detailSectionTitle}>Déplacer ce rendez-vous</div>
                  <div style={S.rescheduleBox}>
                    {slotsLoading ? (
                      <div style={S.detailText}>Chargement des créneaux disponibles…</div>
                    ) : slotOptions.length > 0 ? (
                      <>
                        <select
                          value={selectedNewSlotId}
                          onChange={(e) => setSelectedNewSlotId(e.target.value)}
                          style={S.input}
                        >
                          {slotOptions.map((slot) => (
                            <option key={slot.slot_id} value={slot.slot_id}>
                              {slot.label}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          style={S.actionButtonPrimary}
                          disabled={!selectedNewSlotId || appointmentActionLoading}
                          onClick={async () => {
                            try {
                              setAppointmentActionLoading(true);
                              await api.tenantRescheduleAgendaAppointment(selectedAppointment.appointmentId, {
                                new_slot_id: Number(selectedNewSlotId),
                              });
                              setActionMessage("Rendez-vous déplacé.");
                              setSelectedAppointment(null);
                              await loadAgenda();
                            } catch (e) {
                              setActionMessage(e?.message || "Impossible de déplacer ce rendez-vous.");
                            } finally {
                              setAppointmentActionLoading(false);
                            }
                          }}
                        >
                          Déplacer vers ce créneau
                        </button>
                      </>
                    ) : (
                      <div style={S.detailText}>Aucun autre créneau libre disponible pour le moment.</div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
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
    color: "#111827",
  },
  subtitle: {
    margin: "6px 0 0",
    fontSize: 12,
    color: MUTED,
  },
  primaryButton: {
    border: "none",
    borderRadius: 12,
    padding: "10px 18px",
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    boxShadow: "0 8px 18px rgba(37,99,235,.18)",
  },
  secondaryButton: {
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: "11px 16px",
    background: "#fff",
    color: TEXT,
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
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
  dateBar: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    padding: "14px 16px",
    display: "grid",
    gridTemplateColumns: "48px 1fr 48px",
    alignItems: "center",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  navButton: {
    width: 34,
    height: 34,
    borderRadius: 10,
    border: "none",
    background: "#fff",
    color: "#475569",
    fontSize: 22,
    cursor: "pointer",
    justifySelf: "center",
  },
  dateTitle: {
    textAlign: "center",
    fontSize: 16,
    fontWeight: 700,
    color: TEXT,
  },
  notice: {
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    padding: "12px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
    flexWrap: "wrap",
  },
  noticeTitle: {
    fontSize: 14,
    fontWeight: 800,
    color: TEXT,
  },
  noticeText: {
    marginTop: 4,
    fontSize: 12,
    color: MUTED,
    maxWidth: 720,
  },
  noticeButton: {
    border: "none",
    borderRadius: 10,
    padding: "9px 12px",
    background: BLUE,
    color: "#fff",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  connectedBadge: {
    borderRadius: 999,
    padding: "8px 12px",
    border: "1px solid #bfdbfe",
    background: "#fff",
    color: BLUE_DARK,
    fontSize: 12,
    fontWeight: 700,
  },
  panel: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    padding: 0,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  panelHeader: {
    padding: "18px 18px 14px",
    background: "#fafafa",
    borderBottom: `1px solid ${BORDER}`,
  },
  panelTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: TEXT,
  },
  appointmentsWrap: {
    padding: 18,
  },
  appointmentsList: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  appointmentCard: {
    width: "100%",
    textAlign: "left",
    border: "1px solid",
    borderRadius: 14,
    padding: "14px 16px",
    display: "flex",
    alignItems: "flex-start",
    gap: 14,
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
  appointmentContent: {
    flex: 1,
    minWidth: 0,
  },
  patientName: {
    fontSize: 15,
    fontWeight: 700,
    color: TEXT,
    lineHeight: 1.1,
  },
  appointmentType: {
    marginTop: 6,
    fontSize: 12,
    color: "#4b5563",
  },
  appointmentDetail: {
    marginTop: 4,
    fontSize: 11,
    color: "#6b7280",
  },
  metaRow: {
    marginTop: 10,
    display: "flex",
    gap: 12,
    flexWrap: "wrap",
    fontSize: 11,
    color: MUTED,
  },
  badgesCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    gap: 8,
    flexShrink: 0,
  },
  statusBadge: {
    borderRadius: 999,
    padding: "5px 10px",
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid",
  },
  emptyState: {
    padding: "28px 18px 20px",
    textAlign: "center",
  },
  emptyTimeline: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    padding: 18,
  },
  emptyRows: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10,
  },
  emptyRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    padding: "12px 14px",
    borderRadius: 14,
    background: BG,
    border: `1px solid ${BORDER}`,
  },
  emptyHour: {
    fontSize: 14,
    fontWeight: 700,
    color: "#374151",
  },
  emptyLabel: {
    fontSize: 13,
    color: "#9ca3af",
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
  setupGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
    gap: 16,
  },
  setupCard: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    padding: 18,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  setupTitle: {
    fontSize: 17,
    fontWeight: 800,
    color: TEXT,
  },
  setupText: {
    fontSize: 13,
    color: MUTED,
    lineHeight: 1.5,
  },
  code: {
    display: "inline-block",
    marginTop: 4,
    padding: "2px 6px",
    borderRadius: 8,
    background: BG,
    border: `1px solid ${BORDER}`,
    color: TEXT,
    fontSize: 12,
  },
  input: {
    width: "100%",
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    padding: "12px 14px",
    fontSize: 14,
    color: TEXT,
    outline: "none",
  },
  successBox: {
    borderRadius: 12,
    border: "1px solid #a7f3d0",
    background: "#ecfdf5",
    color: "#047857",
    padding: "10px 12px",
    fontSize: 13,
    fontWeight: 600,
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
  errorInline: {
    borderRadius: 12,
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
    padding: "10px 12px",
    fontSize: 13,
  },
  loading: {
    margin: 18,
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
    width: "min(560px, 100vw)",
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
  actionDangerButton: {
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
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
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
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
  transcriptBox: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
  },
  rescheduleBox: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 10,
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
};

const CSS = `
  @media (max-width: 900px) {
    .agenda-page-stats {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 720px) {
    .agenda-appointment-card {
      flex-direction: column;
      align-items: flex-start !important;
    }

    .agenda-badges-col {
      align-items: flex-start !important;
    }

    .agenda-detail-grid {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 980px) {
    .agenda-stats-grid {
      grid-template-columns: 1fr;
    }
  }
`;
