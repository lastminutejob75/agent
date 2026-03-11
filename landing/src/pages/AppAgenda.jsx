import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, Plus, Search } from "lucide-react";
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

function addMinutesToTimeLabel(timeLabel, durationMinutes) {
  const match = String(timeLabel || "").match(/^(\d{2}):(\d{2})$/);
  if (!match) return "—";
  const [, hh, mm] = match;
  const total = Number(hh) * 60 + Number(mm) + Number(durationMinutes || 0);
  const normalized = ((total % (24 * 60)) + (24 * 60)) % (24 * 60);
  const hours = String(Math.floor(normalized / 60)).padStart(2, "0");
  const minutes = String(normalized % 60).padStart(2, "0");
  return `${hours}:${minutes}`;
}

function createDragPreviewElement(appointment) {
  const node = document.createElement("div");
  node.style.position = "fixed";
  node.style.top = "-9999px";
  node.style.left = "-9999px";
  node.style.width = "220px";
  node.style.padding = "10px 12px";
  node.style.borderRadius = "14px";
  node.style.border = "1px solid #cbd5e1";
  node.style.borderLeft = `4px solid ${appointment?.source === "UWI" ? "#8b5cf6" : "#14b8a6"}`;
  node.style.background = "#ffffff";
  node.style.boxShadow = "0 16px 32px rgba(15,23,42,.16)";
  node.style.fontFamily = "Inter, ui-sans-serif, system-ui, sans-serif";
  node.style.pointerEvents = "none";
  node.style.zIndex = "99999";

  const time = document.createElement("div");
  time.textContent = `${appointment?.displayTime || "—"} - ${addMinutesToTimeLabel(appointment?.displayTime, appointment?.duration)}`;
  time.style.fontSize = "11px";
  time.style.fontWeight = "800";
  time.style.letterSpacing = "0.03em";
  time.style.color = "#0f766e";
  time.style.marginBottom = "4px";

  const titleRow = document.createElement("div");
  titleRow.style.display = "flex";
  titleRow.style.alignItems = "center";
  titleRow.style.gap = "6px";

  if (appointment?.source === "UWI") {
    const badge = document.createElement("span");
    badge.textContent = "IA";
    badge.style.display = "inline-flex";
    badge.style.alignItems = "center";
    badge.style.justifyContent = "center";
    badge.style.height = "18px";
    badge.style.minWidth = "26px";
    badge.style.padding = "0 6px";
    badge.style.borderRadius = "999px";
    badge.style.background = "#ede9fe";
    badge.style.border = "1px solid #ddd6fe";
    badge.style.color = "#7c3aed";
    badge.style.fontSize = "9px";
    badge.style.fontWeight = "900";
    badge.style.letterSpacing = "0.05em";
    titleRow.appendChild(badge);
  }

  const title = document.createElement("div");
  title.textContent = appointment?.patient || "Patient";
  title.style.fontSize = "13px";
  title.style.fontWeight = "800";
  title.style.color = TEXT;
  title.style.lineHeight = "1.2";
  titleRow.appendChild(title);

  const type = document.createElement("div");
  type.textContent = `${getTypeIcon(appointment?.type)} ${appointment?.type || "Consultation"}`;
  type.style.fontSize = "11px";
  type.style.color = "#475569";
  type.style.marginTop = "4px";

  node.appendChild(time);
  node.appendChild(titleRow);
  node.appendChild(type);
  document.body.appendChild(node);
  return node;
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

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstWeekday(year, month) {
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1;
}

function formatMonthShort(year, month) {
  const text = new Date(year, month, 1).toLocaleDateString("fr-FR", { month: "short", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function getViewStatusKey(appointment) {
  if (appointment?.current) return "pending";
  if (appointment?.source === "UWI") return "ai_booked";
  if (appointment?.done) return "arrived";
  return "confirmed";
}

function getFilterLabel(key) {
  if (key === "all") return "Tous";
  return getStatusConfigByKey(key).label;
}

function getStatusConfigByKey(key) {
  if (key === "pending") return { label: "En attente", color: "#f97316", light: "#fff7ed", border: "#fdba74", dot: "#f97316", grad: null };
  if (key === "ai_booked") return { label: "Via IA", color: "#8b5cf6", light: "#f5f3ff", border: "#ddd6fe", dot: "#8b5cf6", grad: null };
  if (key === "arrived") return { label: "Arrivé", color: "#10b981", light: "#f0fdf4", border: "#6ee7b7", dot: "#10b981", grad: null };
  return { label: "Confirmé", color: "#0aaf7a", light: "#e8faf4", border: "#a7f3d0", dot: "#0dc991", grad: "linear-gradient(135deg, #0dc991, #0aaf7a)" };
}

function getTypeIcon(type) {
  const value = String(type || "").toLowerCase();
  if (value.includes("ordonnance")) return "💊";
  if (value.includes("bilan")) return "📋";
  if (value.includes("vaccin")) return "💉";
  if (value.includes("suivi")) return "🔄";
  if (value.includes("prem")) return "👋";
  if (value.includes("post")) return "🏥";
  return "🩺";
}

function MiniCalendar({ selectedDate, onSelect }) {
  const selected = new Date(`${selectedDate}T12:00:00`);
  const [view, setView] = useState({ y: selected.getFullYear(), m: selected.getMonth() });
  const dim = getDaysInMonth(view.y, view.m);
  const first = getFirstWeekday(view.y, view.m);
  const cells = [...Array(first).fill(null), ...Array.from({ length: dim }, (_, index) => index + 1)];
  const today = new Date();

  return (
    <div style={S.miniCalendar}>
      <div style={S.miniCalendarHeader}>
        <button
          type="button"
          onClick={() => setView((prev) => ({ y: prev.m === 0 ? prev.y - 1 : prev.y, m: prev.m === 0 ? 11 : prev.m - 1 }))}
          style={S.miniCalendarNav}
        >
          ‹
        </button>
        <div style={S.miniCalendarTitle}>{formatMonthShort(view.y, view.m)}</div>
        <button
          type="button"
          onClick={() => setView((prev) => ({ y: prev.m === 11 ? prev.y + 1 : prev.y, m: prev.m === 11 ? 0 : prev.m + 1 }))}
          style={S.miniCalendarNav}
        >
          ›
        </button>
      </div>
      <div style={S.miniCalendarWeekdays}>
        {["L", "M", "M", "J", "V", "S", "D"].map((label, index) => (
          <div key={`${label}-${index}`} style={S.miniCalendarWeekday}>{label}</div>
        ))}
      </div>
      <div style={S.miniCalendarGrid}>
        {cells.map((day, index) => {
          if (!day) return <div key={`empty-${index}`} />;
          const date = new Date(view.y, view.m, day, 12, 0, 0);
          const iso = date.toISOString().slice(0, 10);
          const isSelected = iso === selectedDate;
          const isToday =
            date.getDate() === today.getDate() &&
            date.getMonth() === today.getMonth() &&
            date.getFullYear() === today.getFullYear();
          return (
            <button
              key={iso}
              type="button"
              onClick={() => onSelect(iso)}
              style={{
                ...S.miniCalendarDay,
                ...(isSelected ? S.miniCalendarDaySelected : null),
                ...(isToday && !isSelected ? S.miniCalendarDayToday : null),
              }}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AppointmentTooltip({ appointment, rect }) {
  if (!appointment || !rect) return null;
  const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
  const safeTop = Math.min(Math.max(rect.top + rect.height / 2, 90), window.innerHeight - 150);
  const left = Math.min(rect.right + 14, window.innerWidth - 270);
  return (
    <div
      style={{
        position: "fixed",
        top: safeTop,
        left,
        transform: "translateY(-50%)",
        zIndex: 9999,
        background: "#fff",
        border: `1px solid ${BORDER}`,
        borderRadius: 14,
        width: 250,
        boxShadow: "0 12px 40px rgba(0,0,0,0.13)",
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      <div style={{ height: 4, background: visualStatus.grad || visualStatus.dot }} />
      <div style={{ padding: "13px 15px" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: TEXT, marginBottom: 2 }}>{appointment.patient || "Patient"}</div>
        <div style={{ fontSize: 12, color: MUTED, marginBottom: 10 }}>
          {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <span style={{ fontSize: 12, color: MUTED }}>
            {appointment.displayTime} · {appointment.duration} min
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: visualStatus.color,
              background: visualStatus.light,
              padding: "2px 9px",
              borderRadius: 20,
              border: `1px solid ${visualStatus.border}`,
            }}
          >
            {visualStatus.label}
          </span>
        </div>
        {appointment.source === "UWI" ? (
          <div
            style={{
              marginTop: 9,
              background: "#f5f3ff",
              border: "1px solid #ddd6fe",
              borderRadius: 8,
              padding: "7px 9px",
              fontSize: 11,
              color: "#8b5cf6",
              fontWeight: 600,
            }}
          >
            {appointment.detailLine || "Réservé par UWI"}
          </div>
        ) : null}
      </div>
    </div>
  );
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
  const dragPreviewRef = useRef(null);
  const [me, setMe] = useState(null);
  const [config, setConfig] = useState(null);
  const [agenda, setAgenda] = useState(null);
  const [agendaByDate, setAgendaByDate] = useState({});
  const [horaires, setHoraires] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [viewMode, setViewMode] = useState("week");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
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
  const [hoveredAppointment, setHoveredAppointment] = useState(null);
  const [hoveredRect, setHoveredRect] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [slotOptions, setSlotOptions] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedNewSlotId, setSelectedNewSlotId] = useState("");
  const [appointmentActionLoading, setAppointmentActionLoading] = useState(false);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [draggedAppointment, setDraggedAppointment] = useState(null);
  const [dragOverCellKey, setDragOverCellKey] = useState("");
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
          appointmentId: slot.appointment_id || null,
          externalEventId: slot.event_id || "",
          actionId: slot.appointment_id || slot.event_id || "",
          slotId: slot.slot_id,
          canCancel: !!slot.can_cancel,
          canReschedule: !!slot.can_reschedule,
        })),
      ),
    [agendaByDate, horaires, visibleDates],
  );
  const filteredAppointments = useMemo(() => {
    return appointments.filter((appointment) => {
      const haystack = `${appointment.patient || ""} ${appointment.type || ""} ${appointment.sourceLabel || ""}`.toLowerCase();
      const matchesSearch = !search.trim() || haystack.includes(search.trim().toLowerCase());
      const statusKey = getViewStatusKey(appointment);
      const matchesStatus = statusFilter === "all" || statusKey === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [appointments, search, statusFilter]);

  const emptyTimeline = useMemo(() => buildEmptyTimeline(selectedDate, horaires), [selectedDate, horaires]);
  const totalAppointments = appointments.length;
  const doneAppointments = appointments.filter((appointment) => appointment.done).length;
  const upcomingAppointments = Math.max(0, totalAppointments - doneAppointments);
  const timelineHours = useMemo(() => buildTimelineHours(horaires), [horaires]);
  const appointmentsByCell = useMemo(() => {
    const map = {};
    filteredAppointments.forEach((appointment) => {
      const key = `${appointment.date}-${appointment.displayTime}`;
      if (!map[key]) map[key] = [];
      map[key].push(appointment);
    });
    return map;
  }, [filteredAppointments]);
  const selectedDayAppointments = useMemo(
    () =>
      filteredAppointments.filter((appointment) => appointment.date === selectedDate).map((appointment, index) => ({
        ...appointment,
        id: appointment.id || `${selectedDate}-${index}`,
      })),
    [filteredAppointments, selectedDate],
  );
  const sidebarStats = useMemo(() => {
    return {
      all: appointments.length,
      confirmed: appointments.filter((appointment) => getViewStatusKey(appointment) === "confirmed").length,
      pending: appointments.filter((appointment) => getViewStatusKey(appointment) === "pending").length,
      ai_booked: appointments.filter((appointment) => getViewStatusKey(appointment) === "ai_booked").length,
      arrived: appointments.filter((appointment) => getViewStatusKey(appointment) === "arrived").length,
    };
  }, [appointments]);
  const selectedDayCount = selectedDayAppointments.length;
  const selectedDayAiCount = selectedDayAppointments.filter((appointment) => appointment.source === "UWI").length;
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
  useEffect(() => {
    const interval = window.setInterval(() => setNowTick(Date.now()), 60_000);
    return () => window.clearInterval(interval);
  }, []);

  const now = new Date(nowTick);
  const todayIso = now.toISOString().slice(0, 10);
  const currentHourLabel = `${String(now.getHours()).padStart(2, "0")}:00`;
  const currentMinuteOffset = (now.getMinutes() / 60) * 100;

  const scrollToSetup = () => {
    setupRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const clearDragState = useCallback(() => {
    if (dragPreviewRef.current) {
      dragPreviewRef.current.remove();
      dragPreviewRef.current = null;
    }
    setDraggedAppointment(null);
    setDragOverCellKey("");
  }, []);

  useEffect(() => {
    return () => {
      if (dragPreviewRef.current) {
        dragPreviewRef.current.remove();
        dragPreviewRef.current = null;
      }
    };
  }, []);

  const handleAppointmentDragStart = useCallback((event, appointment) => {
    if (!appointment?.canReschedule || appointmentActionLoading) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(appointment.appointmentId || appointment.id || ""));
    if (dragPreviewRef.current) {
      dragPreviewRef.current.remove();
      dragPreviewRef.current = null;
    }
    dragPreviewRef.current = createDragPreviewElement(appointment);
    event.dataTransfer.setDragImage(dragPreviewRef.current, 26, 20);
    setDraggedAppointment(appointment);
    setActionMessage("");
  }, [appointmentActionLoading]);

  const handleAppointmentDragEnd = useCallback(() => {
    clearDragState();
  }, [clearDragState]);

  const handleCellDragOver = useCallback((event, date, hour) => {
    if (!draggedAppointment?.canReschedule || appointmentActionLoading) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverCellKey(`${date}-${hour}`);
  }, [appointmentActionLoading, draggedAppointment]);

  const handleCellDragLeave = useCallback((date, hour) => {
    if (dragOverCellKey === `${date}-${hour}`) {
      setDragOverCellKey("");
    }
  }, [dragOverCellKey]);

  const handleMonthCellDragOver = useCallback((event, date) => {
    if (!draggedAppointment?.canReschedule || appointmentActionLoading) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverCellKey(`month-${date}`);
  }, [appointmentActionLoading, draggedAppointment]);

  const handleMonthCellDragLeave = useCallback((date) => {
    if (dragOverCellKey === `month-${date}`) {
      setDragOverCellKey("");
    }
  }, [dragOverCellKey]);

  const handleMonthCellDrop = useCallback((event, date) => {
    event.preventDefault();
    if (!draggedAppointment?.canReschedule) {
      clearDragState();
      return;
    }
    setSelectedDate(date);
    setViewMode("day");
    setSelectedAppointment(draggedAppointment);
    setActionMessage(`Jour du ${formatLongDate(date)} ouvert. Reprenez le glisser-déposer sur un créneau horaire.`);
    setDragOverCellKey("");
  }, [clearDragState, draggedAppointment]);

  const handleCellDrop = useCallback(async (event, date, hour) => {
    event.preventDefault();
    if (!draggedAppointment?.canReschedule || appointmentActionLoading) {
      clearDragState();
      return;
    }
    if (draggedAppointment.date === date && draggedAppointment.displayTime === hour) {
      clearDragState();
      return;
    }
    try {
      setAppointmentActionLoading(true);
      const exactSlot = await api.tenantGetAgendaAvailableSlots(
        `?date=${encodeURIComponent(date)}&time=${encodeURIComponent(hour)}`,
      );
      const slotId = Number(exactSlot?.slot_id || exactSlot?.slots?.[0]?.slot_id || 0);
      if (!slotId) {
        setActionMessage("Ce créneau n'est pas disponible pour le moment.");
        return;
      }
      await api.tenantRescheduleAgendaAppointment(draggedAppointment.appointmentId, {
        new_slot_id: slotId,
        external_event_id: draggedAppointment.externalEventId || "",
      });
      if (selectedAppointment?.appointmentId === draggedAppointment.appointmentId) {
        setSelectedAppointment(null);
      }
      setActionMessage("Rendez-vous déplacé.");
      await loadAgenda();
    } catch (e) {
      setActionMessage(e?.message || "Impossible de déplacer ce rendez-vous.");
    } finally {
      setAppointmentActionLoading(false);
      clearDragState();
    }
  }, [appointmentActionLoading, clearDragState, draggedAppointment, loadAgenda, selectedAppointment]);

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
      <div className="agenda-layout-grid" style={S.layout}>
        <aside style={S.sidebar}>
          <div style={{ ...S.sidebarCard, ...S.sidebarHeroCard }}>
            <div style={S.sidebarHeroTop}>
              <div>
                <div style={S.sidebarHeroEyebrow}>Date sélectionnée</div>
                <div style={S.sidebarHeroTitle}>{formatLongDate(selectedDate)}</div>
              </div>
              <div style={S.sidebarHeroBadge}>{selectedDayCount} RDV</div>
            </div>
            <div style={S.sidebarHeroMeta}>
              <span>{selectedDayAiCount} pris par UWI</span>
              <span>{viewMode === "month" ? "Vue mois" : viewMode === "day" ? "Vue jour" : "Vue semaine"}</span>
            </div>
            <div style={S.sidebarQuickGrid}>
              <button type="button" onClick={() => { setSelectedDate(todayIso); setViewMode("day"); }} style={S.sidebarQuickButton}>
                Aujourd'hui
              </button>
              <button type="button" onClick={() => { setSelectedDate(shiftDate(todayIso, 1)); setViewMode("day"); }} style={S.sidebarQuickButton}>
                Demain
              </button>
              <button type="button" onClick={() => { setSelectedDate(todayIso); setViewMode("week"); }} style={S.sidebarQuickButton}>
                Cette semaine
              </button>
              <button type="button" onClick={() => { setSelectedDate(todayIso); setViewMode("month"); }} style={S.sidebarQuickButton}>
                Ce mois
              </button>
            </div>
          </div>

          <div style={S.sidebarCard}>
            <div style={S.sidebarTitle}>Vue</div>
            <div style={S.sidebarSegmented}>
              <button type="button" onClick={() => setViewMode("day")} style={viewMode === "day" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
                Jour
              </button>
              <button type="button" onClick={() => setViewMode("week")} style={viewMode === "week" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
                Semaine
              </button>
              <button type="button" onClick={() => setViewMode("month")} style={viewMode === "month" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
                Mois
              </button>
            </div>
          </div>

          <div style={S.sidebarCard}>
            <div style={S.sidebarTitle}>Recherche</div>
            <div style={S.searchBox}>
              <Search size={15} strokeWidth={2.2} color="#94a3b8" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Rechercher un patient…"
                style={S.searchInput}
              />
            </div>
          </div>

          <div style={S.sidebarCard}>
            <div style={S.sidebarTitle}>Filtrer</div>
            <div style={S.filterPillGrid}>
              {[
                ["all", "Tous", "#94a3b8", sidebarStats.all],
                ["confirmed", "Confirmés", "#0dc991", sidebarStats.confirmed],
                ["pending", "En attente", "#f97316", sidebarStats.pending],
                ["ai_booked", "Via IA", "#8b5cf6", sidebarStats.ai_booked],
                ["arrived", "Arrivés", "#10b981", sidebarStats.arrived],
              ].map(([value, label, dot, count]) => {
                const active = statusFilter === value;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setStatusFilter(value)}
                    style={{
                      ...S.filterPill,
                      ...(active ? S.filterPillActive : null),
                    }}
                  >
                    <span style={S.filterPillTop}>
                      <span style={{ ...S.filterDot, background: dot }} />
                      <span style={S.filterLabel}>{label}</span>
                    </span>
                    <span style={S.filterCount}>{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div style={S.sidebarCard}>
            <div style={S.sidebarTitle}>Calendrier</div>
            <MiniCalendar selectedDate={selectedDate} onSelect={setSelectedDate} />
            <div style={S.miniCalendarFooter}>
              <button type="button" onClick={() => setSelectedDate(todayIso)} style={S.miniCalendarTodayButton}>
                Revenir à aujourd'hui
              </button>
            </div>
          </div>

          <div style={{ ...S.sidebarCard, ...S.agentCard }}>
            <div style={S.agentTitle}>{isConnected ? "Agenda connecté" : "Agenda UWI actif"}</div>
            <div style={S.agentText}>
              <b>{sidebarStats.ai_booked}</b> rendez-vous gérés par UWI sur la période affichée.
            </div>
            <div style={S.agentText}>
              {isConnected ? "Google Calendar est bien synchronisé." : "Le planning UWI continue de fonctionner même sans Google."}
            </div>
            <div style={S.agentStatusRow}>
              <span style={S.agentStatusDot} />
              <span style={S.agentStatusText}>{viewMode === "month" ? "Mode mois" : viewMode === "day" ? "Mode jour" : "Mode semaine"}</span>
            </div>
          </div>
        </aside>

        <div style={S.main}>
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
          {draggedAppointment ? (
            <div style={S.dragHintBar}>
              Déplacement de <b>{draggedAppointment.patient || "ce rendez-vous"}</b>
              {viewMode === "month" ? " : déposez sur un jour pour ouvrir son planning." : " : déposez sur une case horaire libre."}
            </div>
          ) : null}
          {actionMessage && !selectedAppointment ? <div style={S.actionToast}>{actionMessage}</div> : null}

          {(search || statusFilter !== "all") ? (
            <div style={S.activeFilterBar}>
              <div style={S.activeFilterText}>
                Filtre actif
                {statusFilter !== "all" ? ` · ${getFilterLabel(statusFilter)}` : ""}
                {search ? ` · "${search}"` : ""}
              </div>
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setStatusFilter("all");
                }}
                style={S.clearFilterButton}
              >
                Réinitialiser
              </button>
            </div>
          ) : null}

          <div style={S.panel}>
        <div style={S.calendarTopBar}>
          <button type="button" onClick={navigatePrevious} style={S.navButton}>
            <ChevronLeft size={18} strokeWidth={2.2} />
          </button>
          <div style={S.calendarTopCenter}>
            <div style={S.dateTitle}>{currentTitle}</div>
            <div style={S.viewSwitch}>
              <button type="button" onClick={() => setSelectedDate(todayIso)} style={S.viewSwitchGhost}>
                Aujourd'hui
              </button>
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
                        <div style={{ ...S.dayHour, ...(selectedDate === todayIso && hour === currentHourLabel ? S.dayHourNow : null) }}>{hour}</div>
                        <div
                          style={{
                            ...S.dayCell,
                            ...(selectedDate === todayIso && hour === currentHourLabel ? S.dayCellNow : null),
                            ...(dragOverCellKey === `${selectedDate}-${hour}` ? S.dropCellActive : null),
                          }}
                          onDragOver={(event) => handleCellDragOver(event, selectedDate, hour)}
                          onDragLeave={() => handleCellDragLeave(selectedDate, hour)}
                          onDrop={(event) => handleCellDrop(event, selectedDate, hour)}
                        >
                          <div style={S.dayHalfLine} />
                          {items.length > 0
                            ? items.map((appointment) => {
                                const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
                                return (
                                  <button
                                    key={appointment.id}
                                    className="agenda-day-appointment"
                                    type="button"
                                    draggable={appointment.canReschedule}
                                    onClick={() => setSelectedAppointment(appointment)}
                                    onDragStart={(event) => handleAppointmentDragStart(event, appointment)}
                                    onDragEnd={handleAppointmentDragEnd}
                                    onMouseEnter={(event) => {
                                      setHoveredAppointment(appointment);
                                      setHoveredRect(event.currentTarget.getBoundingClientRect());
                                    }}
                                    onMouseLeave={() => {
                                      setHoveredAppointment(null);
                                      setHoveredRect(null);
                                    }}
                                    style={{
                                      ...S.dayAppointmentCard,
                                      ...(draggedAppointment?.id === appointment.id ? S.draggingAppointmentCard : null),
                                      borderColor: visualStatus.border,
                                      background: visualStatus.grad || visualStatus.light,
                                    }}
                                  >
                                    <div style={S.dayAppointmentTop}>
                                      <div>
                                        <div style={{ ...S.appointmentTime, color: visualStatus.grad ? "rgba(255,255,255,.92)" : "#0f766e" }}>
                                          {appointment.displayTime}
                                        </div>
                                        <div style={S.appointmentIdentityRow}>
                                          {appointment.source === "UWI" ? (
                                            <span
                                              style={{
                                                ...S.aiInlineBadge,
                                                background: visualStatus.grad ? "rgba(255,255,255,.18)" : "#ede9fe",
                                                color: visualStatus.grad ? "#fff" : "#7c3aed",
                                                borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : "#ddd6fe",
                                              }}
                                            >
                                              IA
                                            </span>
                                          ) : null}
                                          <div style={{ ...S.weekAppointmentName, color: visualStatus.grad ? "#fff" : TEXT }}>
                                            {appointment.patient || "Patient"}
                                          </div>
                                        </div>
                                        <div style={{ ...S.weekAppointmentType, color: visualStatus.grad ? "rgba(255,255,255,.82)" : "#4b5563" }}>
                                          {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
                                        </div>
                                      </div>
                                      <span
                                        style={{
                                          ...S.statusBadge,
                                          background: visualStatus.grad ? "rgba(255,255,255,.18)" : visualStatus.light,
                                          color: visualStatus.grad ? "#fff" : visualStatus.color,
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : visualStatus.border,
                                        }}
                                      >
                                        {visualStatus.label}
                                      </span>
                                    </div>
                                    <div style={S.weekAppointmentPills}>
                                      <span
                                        style={{
                                          ...S.sourceBadge,
                                          background: appointment.source === "UWI" ? (visualStatus.grad ? "rgba(255,255,255,.2)" : "#ede9fe") : (visualStatus.grad ? "rgba(255,255,255,.16)" : "#eef2ff"),
                                          color: visualStatus.grad ? "#fff" : appointment.source === "UWI" ? "#7c3aed" : "#4f46e5",
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.28)" : appointment.source === "UWI" ? "#ddd6fe" : "#c7d2fe",
                                        }}
                                      >
                                        {appointment.source === "UWI" ? "Réservé par UWI" : "Agenda connecté"}
                                      </span>
                                    </div>
                                    <div style={{ ...S.appointmentRange, color: visualStatus.grad ? "rgba(255,255,255,.86)" : "#475569" }}>
                                      {appointment.displayTime} - {addMinutesToTimeLabel(appointment.displayTime, appointment.duration)}
                                    </div>
                                    <div style={{ ...S.weekAppointmentMeta, color: visualStatus.grad ? "rgba(255,255,255,.76)" : "#6b7280" }}>
                                      <span>{appointment.duration} min</span>
                                      <span>{appointment.sourceLabel}</span>
                                    </div>
                                  </button>
                                );
                              })
                            : <div style={S.dayEmptyCell} />}
                          {selectedDate === todayIso && hour === currentHourLabel ? (
                            <div style={{ ...S.nowLine, top: `${currentMinuteOffset}%` }}>
                              <span style={S.nowDot} />
                              <span style={S.nowLabel}>{now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          ) : null}
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
                      onDragOver={(event) => handleMonthCellDragOver(event, date)}
                      onDragLeave={() => handleMonthCellDragLeave(date)}
                      onDrop={(event) => handleMonthCellDrop(event, date)}
                      style={{
                        ...S.monthCell,
                        ...(date === selectedDate ? S.monthCellActive : null),
                        ...(inCurrentMonth ? null : S.monthCellMuted),
                        ...(dragOverCellKey === `month-${date}` ? S.monthCellDropActive : null),
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
                      ...(date === todayIso ? S.weekDayHeaderToday : null),
                    }}
                  >
                    <span style={S.weekDayLabel}>{formatWeekdayLabel(date)}</span>
                    <span style={S.weekDayNumber}>{formatDayNumber(date)}</span>
                    {date === todayIso ? <span style={S.todayPill}>Aujourd'hui</span> : null}
                  </button>
                ))}

                {timelineHours.map((hour) => (
                  <Fragment key={hour}>
                    <div style={S.timeCell}>
                      <div style={S.timeHourLabel}>{hour}</div>
                      <div style={S.timeHalfLabel}>{hour.slice(0, 2)}:30</div>
                    </div>
                    {weekDates.map((date) => {
                      const items = appointmentsByCell[`${date}-${hour}`] || [];
                      const isTodayColumn = date === todayIso;
                      return (
                        <div
                          key={`${date}-${hour}`}
                          style={{
                            ...S.weekCell,
                            ...(date === selectedDate ? S.weekCellActive : null),
                            ...(isTodayColumn ? S.weekCellToday : null),
                            ...(isTodayColumn && hour === currentHourLabel ? S.weekCellNow : null),
                            ...(dragOverCellKey === `${date}-${hour}` ? S.dropCellActive : null),
                          }}
                          onDragOver={(event) => handleCellDragOver(event, date, hour)}
                          onDragLeave={() => handleCellDragLeave(date, hour)}
                          onDrop={(event) => handleCellDrop(event, date, hour)}
                        >
                          <div style={S.weekHalfLine} />
                          {items.length > 0
                            ? items.map((appointment) => {
                                const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
                                return (
                                  <button
                                    key={appointment.id}
                                    className="agenda-week-appointment"
                                    type="button"
                                    draggable={appointment.canReschedule}
                                    onClick={() => setSelectedAppointment(appointment)}
                                    onDragStart={(event) => handleAppointmentDragStart(event, appointment)}
                                    onDragEnd={handleAppointmentDragEnd}
                                    onMouseEnter={(event) => {
                                      setHoveredAppointment(appointment);
                                      setHoveredRect(event.currentTarget.getBoundingClientRect());
                                    }}
                                    onMouseLeave={() => {
                                      setHoveredAppointment(null);
                                      setHoveredRect(null);
                                    }}
                                    style={{
                                      ...S.weekAppointmentCard,
                                      ...(draggedAppointment?.id === appointment.id ? S.draggingAppointmentCard : null),
                                      borderColor: visualStatus.border,
                                      background: visualStatus.grad || visualStatus.light,
                                    }}
                                  >
                                    <div style={S.weekAppointmentTop}>
                                      <div>
                                        <div style={{ ...S.appointmentTime, color: visualStatus.grad ? "rgba(255,255,255,.92)" : "#0f766e" }}>
                                          {appointment.displayTime}
                                        </div>
                                        <div style={S.appointmentIdentityRow}>
                                          {appointment.source === "UWI" ? (
                                            <span
                                              style={{
                                                ...S.aiInlineBadge,
                                                background: visualStatus.grad ? "rgba(255,255,255,.18)" : "#ede9fe",
                                                color: visualStatus.grad ? "#fff" : "#7c3aed",
                                                borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : "#ddd6fe",
                                              }}
                                            >
                                              IA
                                            </span>
                                          ) : null}
                                          <div style={{ ...S.weekAppointmentName, color: visualStatus.grad ? "#fff" : TEXT }}>
                                            {appointment.patient || "Patient"}
                                          </div>
                                        </div>
                                      </div>
                                      <span
                                        style={{
                                          ...S.statusBadge,
                                          background: visualStatus.grad ? "rgba(255,255,255,.18)" : visualStatus.light,
                                          color: visualStatus.grad ? "#fff" : visualStatus.color,
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : visualStatus.border,
                                        }}
                                      >
                                        {visualStatus.label}
                                      </span>
                                    </div>
                                    <div style={{ ...S.weekAppointmentType, color: visualStatus.grad ? "rgba(255,255,255,.82)" : "#4b5563" }}>
                                      {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
                                    </div>
                                    <div style={S.weekAppointmentPills}>
                                      <span
                                        style={{
                                          ...S.sourceBadge,
                                          background: appointment.source === "UWI" ? (visualStatus.grad ? "rgba(255,255,255,.2)" : "#ede9fe") : (visualStatus.grad ? "rgba(255,255,255,.16)" : "#eef2ff"),
                                          color: visualStatus.grad ? "#fff" : appointment.source === "UWI" ? "#7c3aed" : "#4f46e5",
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.28)" : appointment.source === "UWI" ? "#ddd6fe" : "#c7d2fe",
                                        }}
                                      >
                                        {appointment.source === "UWI" ? "Réservé par UWI" : "Agenda connecté"}
                                      </span>
                                    </div>
                                    <div style={{ ...S.appointmentRange, color: visualStatus.grad ? "rgba(255,255,255,.86)" : "#475569" }}>
                                      {appointment.displayTime} - {addMinutesToTimeLabel(appointment.displayTime, appointment.duration)}
                                    </div>
                                    <div style={{ ...S.weekAppointmentMeta, color: visualStatus.grad ? "rgba(255,255,255,.76)" : "#6b7280" }}>
                                      <span>{appointment.sourceLabel}</span>
                                      <span>{appointment.duration} min</span>
                                    </div>
                                  </button>
                                );
                              })
                            : null}
                          {isTodayColumn && hour === currentHourLabel ? (
                            <div style={{ ...S.nowLine, top: `${currentMinuteOffset}%` }}>
                              <span style={S.nowDot} />
                              <span style={S.nowLabel}>{now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          ) : null}
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
                          selectedAppointment.actionId || selectedAppointment.appointmentId || selectedAppointment.externalEventId || selectedAppointment.id,
                          {
                            source: selectedAppointment.source,
                            external_event_id: selectedAppointment.externalEventId || "",
                          },
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
                                external_event_id: selectedAppointment.externalEventId || "",
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
      <AppointmentTooltip appointment={hoveredAppointment} rect={hoveredRect} />
    </div>
  );
}

const S = {
  page: {
    display: "flex",
    flexDirection: "column",
    paddingBottom: 24,
    color: TEXT,
    background: BG,
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "280px minmax(0, 1fr)",
    gap: 18,
    alignItems: "start",
  },
  sidebar: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
    position: "sticky",
    top: 16,
  },
  main: {
    display: "flex",
    flexDirection: "column",
    gap: 18,
    minWidth: 0,
  },
  sidebarCard: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 16,
    padding: 14,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  sidebarHeroCard: {
    background: "linear-gradient(180deg, #ffffff 0%, #f8fffc 100%)",
    borderColor: "#c7f9e7",
  },
  sidebarHeroTop: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 10,
  },
  sidebarHeroEyebrow: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#94a3b8",
  },
  sidebarHeroTitle: {
    marginTop: 8,
    fontSize: 16,
    lineHeight: 1.25,
    fontWeight: 800,
    color: TEXT,
  },
  sidebarHeroBadge: {
    borderRadius: 999,
    padding: "7px 10px",
    background: "#ecfdf5",
    border: "1px solid #a7f3d0",
    color: "#047857",
    fontSize: 12,
    fontWeight: 800,
    whiteSpace: "nowrap",
  },
  sidebarHeroMeta: {
    marginTop: 12,
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    fontSize: 12,
    color: "#64748b",
  },
  sidebarQuickGrid: {
    marginTop: 14,
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  sidebarQuickButton: {
    border: "1px solid #dbeafe",
    borderRadius: 12,
    background: "#fff",
    color: "#334155",
    fontSize: 12,
    fontWeight: 700,
    padding: "10px 8px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  sidebarTitle: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#94a3b8",
    marginBottom: 10,
  },
  searchBox: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#f8fafc",
    padding: "10px 12px",
  },
  searchInput: {
    border: "none",
    background: "transparent",
    outline: "none",
    width: "100%",
    fontSize: 13,
    color: TEXT,
    fontFamily: "inherit",
  },
  filterList: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  sidebarSegmented: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
  },
  sidebarSegmentButton: {
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    background: "#f8fafc",
    color: "#64748b",
    fontSize: 12,
    fontWeight: 700,
    padding: "10px 0",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  sidebarSegmentActive: {
    border: "1px solid #99f6e4",
    borderRadius: 12,
    background: "linear-gradient(135deg, #14b8a6, #0f766e)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 800,
    padding: "10px 0",
    cursor: "pointer",
    boxShadow: "0 8px 18px rgba(20,184,166,.18)",
    fontFamily: "inherit",
  },
  filterPillGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  filterPill: {
    width: "100%",
    border: "1px solid #e5e7eb",
    background: "#fff",
    borderRadius: 14,
    padding: "10px 10px 9px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left",
    boxShadow: "0 1px 6px rgba(15,23,42,.03)",
  },
  filterPillActive: {
    background: "#f0fdfa",
    borderColor: "#99f6e4",
    boxShadow: "0 8px 18px rgba(20,184,166,.08)",
  },
  filterPillTop: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    minWidth: 0,
  },
  filterItem: {
    width: "100%",
    border: "1px solid transparent",
    background: "transparent",
    borderRadius: 10,
    padding: "9px 10px",
    display: "flex",
    alignItems: "center",
    gap: 8,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left",
  },
  filterItemActive: {
    background: "#e8faf4",
    borderColor: "#a7f3d0",
  },
  filterDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    flexShrink: 0,
  },
  filterLabel: {
    flex: 1,
    fontSize: 12,
    fontWeight: 600,
    color: "#334155",
  },
  filterCount: {
    fontSize: 11,
    fontWeight: 700,
    color: "#64748b",
    background: "rgba(148,163,184,.12)",
    borderRadius: 999,
    padding: "2px 8px",
  },
  miniCalendar: {
    paddingTop: 4,
  },
  miniCalendarHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  miniCalendarNav: {
    border: "none",
    background: "transparent",
    color: "#94a3b8",
    fontSize: 16,
    cursor: "pointer",
    padding: "2px 6px",
  },
  miniCalendarTitle: {
    fontSize: 11,
    fontWeight: 700,
    color: "#334155",
  },
  miniCalendarWeekdays: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    marginBottom: 4,
  },
  miniCalendarWeekday: {
    textAlign: "center",
    fontSize: 9,
    fontWeight: 800,
    color: "#94a3b8",
    padding: "2px 0",
  },
  miniCalendarGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: 2,
  },
  miniCalendarDay: {
    border: "none",
    background: "transparent",
    borderRadius: 8,
    padding: "5px 0",
    fontSize: 11,
    color: "#334155",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  miniCalendarDaySelected: {
    background: "#0dc991",
    color: "#fff",
    fontWeight: 800,
  },
  miniCalendarDayToday: {
    background: "#e8faf4",
    color: "#0aaf7a",
    fontWeight: 700,
  },
  miniCalendarFooter: {
    marginTop: 10,
    display: "flex",
    justifyContent: "center",
  },
  miniCalendarTodayButton: {
    border: "none",
    background: "transparent",
    color: "#0f766e",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  agentCard: {
    background: "#e8faf4",
    borderColor: "#a7f3d0",
  },
  agentTitle: {
    fontSize: 13,
    fontWeight: 800,
    color: "#0aaf7a",
  },
  agentText: {
    marginTop: 6,
    fontSize: 12,
    lineHeight: 1.5,
    color: "#475569",
  },
  agentStatusRow: {
    marginTop: 10,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 999,
    padding: "6px 10px",
    background: "rgba(255,255,255,.72)",
    border: "1px solid rgba(16,185,129,.2)",
    width: "fit-content",
  },
  agentStatusDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "#10b981",
    boxShadow: "0 0 0 4px rgba(16,185,129,.12)",
  },
  agentStatusText: {
    fontSize: 11,
    fontWeight: 800,
    color: "#047857",
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
  activeFilterBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    borderRadius: 14,
    border: "1px solid #fef3c7",
    background: "#fffbeb",
    padding: "10px 12px",
  },
  activeFilterText: {
    fontSize: 12,
    color: "#92400e",
    fontWeight: 700,
  },
  clearFilterButton: {
    border: "none",
    background: "transparent",
    color: "#92400e",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
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
  dayHourNow: {
    background: "#fff5f5",
    color: "#dc2626",
    boxShadow: "inset -2px 0 0 #fecaca",
  },
  dayCell: {
    padding: 10,
    background: "#fff",
    position: "relative",
  },
  dayCellNow: {
    background: "linear-gradient(180deg, #fffefe 0%, #fff7f7 100%)",
  },
  dragHintBar: {
    borderRadius: 12,
    border: "1px solid #bfdbfe",
    background: "#eff6ff",
    color: "#1d4ed8",
    padding: "12px 14px",
    fontSize: 13,
    fontWeight: 700,
  },
  dayEmptyCell: {
    height: "100%",
    minHeight: 42,
    borderRadius: 12,
    background: "#ffffff",
  },
  dayHalfLine: {
    position: "absolute",
    left: 0,
    right: 0,
    top: "50%",
    borderTop: "1px dashed #edf2f7",
    pointerEvents: "none",
  },
  dayAppointmentCard: {
    width: "100%",
    border: "1px solid",
    borderRadius: 14,
    background: "#fff",
    padding: "10px 12px 9px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 8px 22px rgba(15,23,42,.06)",
    borderLeftWidth: 4,
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
  weekDayHeaderToday: {
    background: "linear-gradient(180deg, #eff6ff 0%, #f8fbff 100%)",
    boxShadow: "inset 0 -3px 0 #3b82f6",
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
  todayPill: {
    marginTop: 4,
    borderRadius: 999,
    padding: "2px 8px",
    background: "#dbeafe",
    color: "#1d4ed8",
    fontSize: 9,
    fontWeight: 900,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
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
    position: "relative",
  },
  timeHourLabel: {
    position: "absolute",
    top: -8,
    right: 10,
    fontSize: 12,
    fontWeight: 700,
    color: "#64748b",
    background: "#fff",
    paddingLeft: 4,
    lineHeight: 1,
  },
  timeHalfLabel: {
    position: "absolute",
    top: "50%",
    right: 12,
    fontSize: 10,
    fontWeight: 500,
    color: "#94a3b8",
    transform: "translateY(-50%)",
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
    position: "relative",
  },
  weekCellActive: {
    background: "#fcfffe",
  },
  weekCellToday: {
    background: "#fbfffe",
  },
  weekCellNow: {
    background: "linear-gradient(180deg, #fffefe 0%, #fff7f7 100%)",
  },
  dropCellActive: {
    background: "linear-gradient(180deg, #ecfeff 0%, #f0fdfa 100%)",
    boxShadow: "inset 0 0 0 2px #2dd4bf",
  },
  weekHalfLine: {
    position: "absolute",
    left: 0,
    right: 0,
    top: "50%",
    borderTop: "1px dashed #edf2f7",
    pointerEvents: "none",
  },
  weekAppointmentCard: {
    width: "100%",
    border: "1px solid",
    borderRadius: 12,
    background: "#fff",
    padding: "8px 9px 8px",
    display: "flex",
    flexDirection: "column",
    gap: 5,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 8px 18px rgba(15,23,42,.05)",
    borderLeftWidth: 4,
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
  appointmentIdentityRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    minWidth: 0,
  },
  appointmentTime: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.02em",
    marginBottom: 2,
    textTransform: "uppercase",
  },
  aiInlineBadge: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minWidth: 26,
    height: 18,
    padding: "0 6px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 9,
    fontWeight: 900,
    letterSpacing: "0.05em",
    flexShrink: 0,
  },
  weekAppointmentType: {
    fontSize: 11,
    color: "#4b5563",
    lineHeight: 1.25,
  },
  appointmentRange: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.02em",
  },
  weekAppointmentPills: {
    display: "flex",
    flexWrap: "wrap",
    gap: 5,
  },
  sourceBadge: {
    display: "inline-flex",
    alignItems: "center",
    border: "1px solid",
    borderRadius: 999,
    padding: "3px 8px",
    fontSize: 9,
    fontWeight: 800,
    letterSpacing: "0.01em",
  },
  weekAppointmentMeta: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
    fontSize: 10,
    fontWeight: 600,
    color: "#6b7280",
  },
  nowLine: {
    position: "absolute",
    left: 0,
    right: 0,
    height: 0,
    borderTop: "2px solid #ef4444",
    zIndex: 4,
    pointerEvents: "none",
  },
  nowDot: {
    position: "absolute",
    left: -1,
    top: -5,
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: "#ef4444",
    boxShadow: "0 0 0 4px rgba(239,68,68,.14)",
  },
  nowLabel: {
    position: "absolute",
    right: 8,
    top: -13,
    borderRadius: 999,
    padding: "3px 8px",
    background: "#ef4444",
    color: "#fff",
    fontSize: 10,
    fontWeight: 800,
    letterSpacing: "0.03em",
    boxShadow: "0 8px 18px rgba(239,68,68,.18)",
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
  monthCellDropActive: {
    background: "linear-gradient(180deg, #ecfeff 0%, #f0fdfa 100%)",
    boxShadow: "inset 0 0 0 2px #2dd4bf",
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
  actionToast: {
    borderRadius: 12,
    border: "1px solid #a7f3d0",
    background: "#ecfdf5",
    color: "#047857",
    padding: "12px 14px",
    fontSize: 13,
    fontWeight: 700,
    boxShadow: "0 8px 18px rgba(16,185,129,.08)",
  },
  draggingAppointmentCard: {
    opacity: 0.48,
    transform: "scale(.985)",
    boxShadow: "0 16px 30px rgba(15,23,42,.14)",
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
  @keyframes agenda-card-enter {
    from {
      opacity: 0;
      transform: translateY(6px) scale(0.985);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .agenda-week-appointment,
  .agenda-day-appointment {
    animation: agenda-card-enter 180ms cubic-bezier(0.22, 1, 0.36, 1) both;
    transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease, opacity 180ms ease;
    will-change: transform, box-shadow, opacity;
    transform-origin: top left;
  }

  .agenda-week-appointment:hover,
  .agenda-day-appointment:hover {
    transform: translateY(-2px) scale(1.01);
    box-shadow: 0 16px 30px rgba(15, 23, 42, 0.14) !important;
    filter: saturate(1.03);
  }

  .agenda-week-appointment[draggable="true"],
  .agenda-day-appointment[draggable="true"] {
    cursor: grab;
  }

  .agenda-week-appointment[draggable="true"]:active,
  .agenda-day-appointment[draggable="true"]:active {
    cursor: grabbing;
  }

  @media (prefers-reduced-motion: reduce) {
    .agenda-week-appointment,
    .agenda-day-appointment {
      animation: none !important;
      transition: none !important;
    }
  }

  @media (max-width: 1180px) {
    .agenda-layout-grid {
      grid-template-columns: 1fr !important;
    }
  }

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
