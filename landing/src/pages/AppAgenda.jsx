import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, Plus } from "lucide-react";
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

function startOfWeek(dateStr) {
  const date = new Date(`${dateStr}T12:00:00`);
  const diff = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - diff);
  return date.toISOString().slice(0, 10);
}

function buildWeekDates(dateStr) {
  const start = new Date(`${startOfWeek(dateStr)}T12:00:00`);
  return Array.from({ length: 7 }, (_, index) => {
    const next = new Date(start);
    next.setDate(start.getDate() + index);
    return next.toISOString().slice(0, 10);
  });
}

function formatWeekTitle(dateStr) {
  const dates = buildWeekDates(dateStr);
  const first = new Date(`${dates[0]}T12:00:00`);
  const last = new Date(`${dates[6]}T12:00:00`);
  const firstLabel = first.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  const lastLabel = last.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  return `Semaine du ${firstLabel}${firstLabel === lastLabel ? "" : ` au ${lastLabel}`}`;
}

function shiftMonth(dateStr, diff) {
  const date = new Date(`${dateStr}T12:00:00`);
  date.setMonth(date.getMonth() + diff);
  return date.toISOString().slice(0, 10);
}

function formatMonthTitle(dateStr) {
  const date = new Date(`${dateStr}T12:00:00`);
  const text = date.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatWeekdayLabel(dateStr) {
  const label = new Date(`${dateStr}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short" });
  return label.replace(".", "").toUpperCase();
}

function formatDayNumber(dateStr) {
  return new Date(`${dateStr}T12:00:00`).toLocaleDateString("fr-FR", { day: "numeric" });
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

function buildTimelineHours(horaires) {
  const start = Number(horaires?.booking_start_hour ?? 7);
  const end = Number(horaires?.booking_end_hour ?? 19);
  const safeStart = Number.isFinite(start) ? start : 7;
  const safeEnd = Number.isFinite(end) ? end : 19;
  const first = safeStart < safeEnd ? safeStart : 7;
  const last = safeStart < safeEnd ? safeEnd : 19;
  const rows = [];
  for (let hour = first; hour < last; hour += 1) {
    rows.push(`${String(hour).padStart(2, "0")}:00`);
  }
  return rows;
}

function buildMonthGrid(dateStr) {
  const anchor = new Date(`${dateStr}T12:00:00`);
  const monthStart = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 12, 0, 0);
  const offset = (monthStart.getDay() + 6) % 7;
  monthStart.setDate(monthStart.getDate() - offset);
  return Array.from({ length: 35 }, (_, index) => {
    const cell = new Date(monthStart);
    cell.setDate(monthStart.getDate() + index);
    return cell.toISOString().slice(0, 10);
  });
}

function isSameMonth(dateStr, compareTo) {
  const a = new Date(`${dateStr}T12:00:00`);
  const b = new Date(`${compareTo}T12:00:00`);
  return a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear();
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
  const [agendaByDate, setAgendaByDate] = useState({});
  const [horaires, setHoraires] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [viewMode, setViewMode] = useState("week");
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
  const weekDates = useMemo(() => buildWeekDates(selectedDate), [selectedDate]);
  const visibleDates = useMemo(() => {
    if (viewMode === "month") return buildMonthGrid(selectedDate);
    if (viewMode === "day") return [selectedDate];
    return weekDates;
  }, [selectedDate, viewMode, weekDates]);

  const loadAgenda = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextMe, nextConfig, nextHoraires, ...agendaResponses] = await Promise.all([
        api.tenantMe(),
        api.agendaConfig(),
        api.tenantGetHoraires(),
        ...visibleDates.map((date) => api.tenantGetAgenda(`?date=${date}`).catch(() => ({ slots: [], date, total: 0, done: 0, remaining: 0 }))),
      ]);
      const nextAgendaByDate = {};
      visibleDates.forEach((date, index) => {
        nextAgendaByDate[date] = agendaResponses[index] || { slots: [], date, total: 0, done: 0, remaining: 0 };
      });
      setMe(nextMe);
      setConfig(nextConfig);
      setAgenda(nextAgendaByDate[selectedDate] || null);
      setAgendaByDate(nextAgendaByDate);
      setHoraires(nextHoraires);
      setCalendarId(nextMe?.calendar_id || "");
    } catch (e) {
      setError(e?.message || "Impossible de charger l'agenda.");
    } finally {
      setLoading(false);
    }
  }, [selectedDate, visibleDates]);

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
      visibleDates.flatMap((date) =>
        (agendaByDate?.[date]?.slots || []).map((slot, index) => ({
          ...slot,
          id: `${date}-${slot.event_id || slot.appointment_id || `${slot.hour || "slot"}-${index}`}`,
          date,
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
      ),
    [agendaByDate, horaires, visibleDates],
  );

  const emptyTimeline = useMemo(() => buildEmptyTimeline(selectedDate, horaires), [selectedDate, horaires]);
  const totalAppointments = appointments.length;
  const doneAppointments = appointments.filter((appointment) => appointment.done).length;
  const upcomingAppointments = Math.max(0, totalAppointments - doneAppointments);
  const timelineHours = useMemo(() => buildTimelineHours(horaires), [horaires]);
  const appointmentsByCell = useMemo(() => {
    const map = {};
    appointments.forEach((appointment) => {
      const key = `${appointment.date}-${appointment.displayTime}`;
      if (!map[key]) map[key] = [];
      map[key].push(appointment);
    });
    return map;
  }, [appointments]);
  const selectedDayAppointments = useMemo(
    () =>
      (agendaByDate?.[selectedDate]?.slots || []).map((slot, index) => ({
        ...slot,
        id: `${selectedDate}-${slot.event_id || slot.appointment_id || `${slot.hour || "slot"}-${index}`}`,
        date: selectedDate,
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
    [agendaByDate, horaires, selectedDate],
  );
  const currentTitle =
    viewMode === "month" ? formatMonthTitle(selectedDate) : viewMode === "day" ? formatLongDate(selectedDate) : formatWeekTitle(selectedDate);
  const currentPanelTitle =
    viewMode === "month" ? "Vue mensuelle" : viewMode === "day" ? "Planning de la journée" : "Planning de la semaine";
  const navigatePrevious = () => {
    setSelectedDate((value) => {
      if (viewMode === "month") return shiftMonth(value, -1);
      if (viewMode === "day") return shiftDate(value, -1);
      return shiftDate(value, -7);
    });
  };
  const navigateNext = () => {
    setSelectedDate((value) => {
      if (viewMode === "month") return shiftMonth(value, 1);
      if (viewMode === "day") return shiftDate(value, 1);
      return shiftDate(value, 7);
    });
  };

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
          <Plus size={16} strokeWidth={2.4} />
          <span>Nouveau rendez-vous</span>
        </button>
      </div>

      <div className="agenda-page-stats" style={S.statsGrid}>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Total rendez-vous</div>
            <div style={S.statValue}>{totalAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}>
            <CalendarDays size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Confirmés</div>
            <div style={{ ...S.statValue, color: SUCCESS }}>{doneAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #10b981, #059669)" }}>
            <Check size={16} strokeWidth={2.4} />
          </div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>En attente</div>
            <div style={{ ...S.statValue, color: WARNING }}>{upcomingAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
            <Clock3 size={16} strokeWidth={2.2} />
          </div>
        </div>
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
        <div style={S.calendarTopBar}>
          <button type="button" onClick={navigatePrevious} style={S.navButton}>
            <ChevronLeft size={18} strokeWidth={2.2} />
          </button>
          <div style={S.calendarTopCenter}>
            <div style={S.dateTitle}>{currentTitle}</div>
            <div style={S.viewSwitch}>
              <button type="button" onClick={() => setViewMode("month")} style={viewMode === "month" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Mois
              </button>
              <button type="button" onClick={() => setViewMode("week")} style={viewMode === "week" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Semaine
              </button>
              <button type="button" onClick={() => setViewMode("day")} style={viewMode === "day" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Jour
              </button>
            </div>
          </div>
          <button type="button" onClick={navigateNext} style={S.navButton}>
            <ChevronRight size={18} strokeWidth={2.2} />
          </button>
        </div>

        <div style={S.calendarPanelHeader}>
          <div style={S.panelTitle}>{currentPanelTitle}</div>
        </div>

        {timelineHours.length > 0 ? (
          viewMode === "day" ? (
            <div className="agenda-day-layout" style={S.dayLayout}>
              <div style={S.dayMain}>
                <div style={S.daySummaryBar}>
                  <div>
                    <div style={S.daySummaryTitle}>Planning de la journée</div>
                    <div style={S.daySummaryText}>{selectedDayAppointments.length} rendez-vous prévus</div>
                  </div>
                </div>
                <div style={S.dayTimeline}>
                  {timelineHours.map((hour) => {
                    const items = appointmentsByCell[`${selectedDate}-${hour}`] || [];
                    return (
                      <div key={hour} style={S.dayRow}>
                        <div style={S.dayHour}>{hour}</div>
                        <div style={S.dayCell}>
                          {items.length > 0
                            ? items.map((appointment) => (
                                <button
                                  key={appointment.id}
                                  type="button"
                                  onClick={() => setSelectedAppointment(appointment)}
                                  style={{
                                    ...S.dayAppointmentCard,
                                    borderColor: appointment.status.border,
                                    background: appointment.current ? "#fff7ed" : "#ffffff",
                                  }}
                                >
                                  <div style={S.dayAppointmentTop}>
                                    <div>
                                      <div style={S.weekAppointmentName}>{appointment.patient || "Patient"}</div>
                                      <div style={S.weekAppointmentType}>{appointment.type || "Consultation"}</div>
                                    </div>
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
                                  <div style={S.weekAppointmentMeta}>
                                    <span>{appointment.displayTime}</span>
                                    <span>{appointment.duration} min</span>
                                    <span>{appointment.sourceLabel}</span>
                                  </div>
                                </button>
                              ))
                            : <div style={S.dayEmptyCell} />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div style={S.daySidebar}>
                <div style={S.sideCard}>
                  <div style={S.sideCardTitle}>Détails</div>
                  {selectedAppointment && selectedAppointment.date === selectedDate ? (
                    <div style={S.sideDetailBody}>
                      <div style={S.sideDetailName}>{selectedAppointment.patient || "Patient"}</div>
                      <div style={S.sideDetailText}>{selectedAppointment.type || "Consultation"}</div>
                      <div style={S.sideDetailText}>{selectedAppointment.displayTime || "—"} · {selectedAppointment.duration || "—"} min</div>
                      <div style={S.sideDetailText}>{selectedAppointment.sourceLabel || "UWI"}</div>
                    </div>
                  ) : (
                    <div style={S.sideEmpty}>Sélectionnez un rendez-vous pour voir les détails</div>
                  )}
                </div>
                <div style={{ ...S.sideCard, ...S.quickActionsCard }}>
                  <div style={S.sideCardTitle}>Actions rapides</div>
                  <button type="button" onClick={scrollToSetup} style={S.quickActionButton}>+ Nouveau RDV</button>
                  <button type="button" onClick={() => navigate("/app/appels")} style={S.quickActionButton}>Ouvrir appels</button>
                  <button type="button" onClick={() => navigate("/app/horaires")} style={S.quickActionButton}>Modifier horaires</button>
                </div>
              </div>
            </div>
          ) : viewMode === "month" ? (
            <div style={S.monthWrap}>
              <div className="agenda-month-grid" style={S.monthGrid}>
                {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((label) => (
                  <div key={label} style={S.monthWeekday}>{label}</div>
                ))}
                {buildMonthGrid(selectedDate).map((date) => {
                  const items = agendaByDate?.[date]?.slots || [];
                  const inCurrentMonth = isSameMonth(date, selectedDate);
                  return (
                    <button
                      key={date}
                      type="button"
                      onClick={() => {
                        setSelectedDate(date);
                        setViewMode("day");
                      }}
                      style={{
                        ...S.monthCell,
                        ...(date === selectedDate ? S.monthCellActive : null),
                        ...(inCurrentMonth ? null : S.monthCellMuted),
                      }}
                    >
                      <div style={S.monthCellDate}>{formatDayNumber(date)}</div>
                      {items.length > 0 ? (
                        <div style={S.monthDotWrap}>
                          <span style={S.monthDot}>{items.length}</span>
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={S.weekCalendarWrap}>
              <div className="agenda-week-calendar" style={S.weekCalendar}>
                <div style={S.weekCorner} />
                {weekDates.map((date) => (
                  <button
                    key={date}
                    type="button"
                    onClick={() => setSelectedDate(date)}
                    style={{
                      ...S.weekDayHeader,
                      ...(date === selectedDate ? S.weekDayHeaderActive : null),
                    }}
                  >
                    <span style={S.weekDayLabel}>{formatWeekdayLabel(date)}</span>
                    <span style={S.weekDayNumber}>{formatDayNumber(date)}</span>
                  </button>
                ))}

                {timelineHours.map((hour) => (
                  <Fragment key={hour}>
                    <div style={S.timeCell}>{hour}</div>
                    {weekDates.map((date) => {
                      const items = appointmentsByCell[`${date}-${hour}`] || [];
                      return (
                        <div
                          key={`${date}-${hour}`}
                          style={{
                            ...S.weekCell,
                            ...(date === selectedDate ? S.weekCellActive : null),
                          }}
                        >
                          {items.length > 0
                            ? items.map((appointment) => (
                                <button
                                  key={appointment.id}
                                  className="agenda-week-appointment"
                                  type="button"
                                  onClick={() => setSelectedAppointment(appointment)}
                                  style={{
                                    ...S.weekAppointmentCard,
                                    borderColor: appointment.status.border,
                                    background: appointment.current ? "#fff7ed" : "#ffffff",
                                  }}
                                >
                                  <div style={S.weekAppointmentTop}>
                                    <div style={S.weekAppointmentName}>{appointment.patient || "Patient"}</div>
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
                                  <div style={S.weekAppointmentType}>{appointment.type || "Consultation"}</div>
                                  <div style={S.weekAppointmentMeta}>
                                    <span>{appointment.displayTime}</span>
                                    <span>{appointment.sourceLabel}</span>
                                  </div>
                                </button>
                              ))
                            : null}
                        </div>
                      );
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
          )
        ) : emptyTimeline.closed ? (
          <div style={S.emptyState}>
            <div style={S.emptyTitle}>Cabinet fermé ce jour</div>
            <div style={S.emptyText}>Aucun créneau prévu selon vos horaires actuels.</div>
            <button type="button" onClick={() => navigate("/app/horaires")} style={S.secondaryButton}>
              Modifier mes horaires
            </button>
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
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
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
  navButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#f8fafc",
    color: "#475569",
    cursor: "pointer",
    justifySelf: "center",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  },
  dateTitle: {
    textAlign: "center",
    fontSize: 15,
    fontWeight: 800,
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
    borderRadius: 18,
    padding: 0,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  calendarTopBar: {
    padding: "18px 18px 14px",
    display: "grid",
    gridTemplateColumns: "48px 1fr 48px",
    alignItems: "center",
    gap: 12,
    borderBottom: `1px solid ${BORDER}`,
    background: "#ffffff",
  },
  calendarTopCenter: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
  },
  viewSwitch: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: 4,
    borderRadius: 12,
    background: "#f8fafc",
    border: `1px solid ${BORDER}`,
  },
  viewSwitchGhost: {
    border: "none",
    background: "transparent",
    color: "#6b7280",
    borderRadius: 10,
    padding: "7px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  viewSwitchActive: {
    border: "none",
    background: "linear-gradient(135deg, #14b8a6, #0f766e)",
    color: "#fff",
    borderRadius: 10,
    padding: "7px 12px",
    fontSize: 12,
    fontWeight: 700,
    boxShadow: "0 8px 18px rgba(20,184,166,.18)",
  },
  calendarPanelHeader: {
    padding: "16px 18px",
    background: "#fafafa",
    borderBottom: `1px solid ${BORDER}`,
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
  weekCalendarWrap: {
    padding: 18,
    overflowX: "auto",
  },
  dayLayout: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.8fr) minmax(280px, .9fr)",
    gap: 18,
    padding: 18,
  },
  dayMain: {
    border: `1px solid ${BORDER}`,
    borderRadius: 18,
    overflow: "hidden",
    background: "#fff",
  },
  daySummaryBar: {
    padding: "18px 18px 16px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#f6fffd",
  },
  daySummaryTitle: {
    fontSize: 15,
    fontWeight: 800,
    color: TEXT,
  },
  daySummaryText: {
    marginTop: 6,
    fontSize: 13,
    color: MUTED,
  },
  dayTimeline: {
    display: "flex",
    flexDirection: "column",
  },
  dayRow: {
    display: "grid",
    gridTemplateColumns: "72px minmax(0, 1fr)",
    minHeight: 66,
    borderBottom: `1px solid ${BORDER}`,
  },
  dayHour: {
    padding: "12px 10px",
    fontSize: 12,
    fontWeight: 700,
    color: "#6b7280",
    background: "#fff",
    borderRight: `1px solid ${BORDER}`,
  },
  dayCell: {
    padding: 10,
    background: "#fff",
  },
  dayEmptyCell: {
    height: "100%",
    minHeight: 42,
    borderRadius: 12,
    background: "#ffffff",
  },
  dayAppointmentCard: {
    width: "100%",
    border: "1px solid",
    borderRadius: 14,
    background: "#fff",
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 6px 18px rgba(15,23,42,.05)",
  },
  dayAppointmentTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  daySidebar: {
    display: "flex",
    flexDirection: "column",
    gap: 18,
  },
  sideCard: {
    border: `1px solid ${BORDER}`,
    borderRadius: 18,
    background: "#fff",
    padding: 18,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  sideCardTitle: {
    fontSize: 15,
    fontWeight: 800,
    color: TEXT,
  },
  sideEmpty: {
    marginTop: 18,
    fontSize: 13,
    color: MUTED,
    lineHeight: 1.6,
  },
  sideDetailBody: {
    marginTop: 16,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sideDetailName: {
    fontSize: 16,
    fontWeight: 800,
    color: TEXT,
  },
  sideDetailText: {
    fontSize: 13,
    color: "#4b5563",
    lineHeight: 1.5,
  },
  quickActionsCard: {
    background: "#f6fffd",
    borderColor: "#ccfbf1",
  },
  quickActionButton: {
    width: "100%",
    marginTop: 12,
    textAlign: "left",
    border: "1px solid #d1fae5",
    background: "#fff",
    color: "#334155",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  weekCalendar: {
    minWidth: 980,
    display: "grid",
    gridTemplateColumns: "88px repeat(7, minmax(120px, 1fr))",
    borderTop: `1px solid ${BORDER}`,
    borderLeft: `1px solid ${BORDER}`,
    background: "#fff",
  },
  weekCorner: {
    minHeight: 52,
    background: "#fff",
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
  },
  weekDayHeader: {
    minHeight: 52,
    border: "none",
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
    background: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  weekDayHeaderActive: {
    background: "#f0fdfa",
  },
  weekDayLabel: {
    fontSize: 10,
    fontWeight: 800,
    color: "#6b7280",
    letterSpacing: "0.05em",
  },
  weekDayNumber: {
    fontSize: 22,
    fontWeight: 800,
    color: TEXT,
    lineHeight: 1,
  },
  timeCell: {
    minHeight: 92,
    padding: "8px 10px",
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
    fontSize: 12,
    fontWeight: 700,
    color: "#6b7280",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "center",
    background: "#fff",
  },
  weekCell: {
    minHeight: 92,
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
    padding: 8,
    background: "#fff",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  weekCellActive: {
    background: "#fcfffe",
  },
  weekAppointmentCard: {
    width: "100%",
    border: "1px solid",
    borderRadius: 14,
    background: "#fff",
    padding: "10px 10px 9px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 4px 14px rgba(15,23,42,.05)",
  },
  weekAppointmentTop: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 8,
  },
  weekAppointmentName: {
    fontSize: 13,
    fontWeight: 800,
    color: TEXT,
    lineHeight: 1.25,
  },
  weekAppointmentType: {
    fontSize: 12,
    color: "#4b5563",
    lineHeight: 1.4,
  },
  weekAppointmentMeta: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
    fontSize: 11,
    color: "#6b7280",
  },
  monthWrap: {
    padding: 18,
    overflowX: "auto",
  },
  monthGrid: {
    minWidth: 860,
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    borderTop: `1px solid ${BORDER}`,
    borderLeft: `1px solid ${BORDER}`,
    background: "#fff",
  },
  monthWeekday: {
    padding: "14px 10px",
    textAlign: "center",
    fontSize: 12,
    fontWeight: 700,
    color: "#475569",
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
    background: "#fff",
  },
  monthCell: {
    minHeight: 108,
    border: "none",
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
    background: "#fff",
    padding: 12,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    position: "relative",
  },
  monthCellActive: {
    background: "#f0fdfa",
  },
  monthCellMuted: {
    color: "#94a3b8",
    background: "#fafafa",
  },
  monthCellDate: {
    fontSize: 14,
    fontWeight: 800,
    color: "inherit",
  },
  monthDotWrap: {
    marginTop: 18,
    display: "flex",
    justifyContent: "center",
  },
  monthDot: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: "linear-gradient(135deg, #14b8a6, #0f766e)",
    color: "#fff",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 12,
    fontWeight: 800,
    boxShadow: "0 8px 18px rgba(20,184,166,.18)",
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

  @media (max-width: 1080px) {
    .agenda-day-layout {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 720px) {
    .agenda-appointment-card {
      flex-direction: column;
      align-items: flex-start !important;
    }

    .agenda-week-calendar {
      min-width: 760px !important;
    }

    .agenda-week-appointment {
      padding: 8px !important;
    }

    .agenda-month-grid {
      min-width: 760px !important;
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
