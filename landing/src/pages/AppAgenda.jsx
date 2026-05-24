import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import CreatePatientFromCallModal from "../components/calls/CreatePatientFromCallModal.jsx";
import { api } from "../lib/api.js";

const NAVY = "#111827";
const TEAL = "#0DC991";
const TEAL_DARK = "#0AAF7A";
const BLUE = "#2563EB";
const BORDER = "#e5e7eb";
const MUTED = "#6b7280";

function todayISO() { return new Date().toISOString().slice(0, 10); }

function shiftDate(dateStr, diff) {
  const d = new Date(`${dateStr}T12:00:00`);
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

function shiftMonth(dateStr, diff) {
  const d = new Date(`${dateStr}T12:00:00`);
  d.setMonth(d.getMonth() + diff);
  return d.toISOString().slice(0, 10);
}

function formatLongDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(`${dateStr}T12:00:00`);
  const t = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function formatMonthLabel(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`);
  const t = d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function formatShortDay(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`);
  return { wd: d.toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "").toUpperCase(), num: d.getDate() };
}

function startOfWeek(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`);
  const diff = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - diff);
  return d.toISOString().slice(0, 10);
}

function buildWeekDates(dateStr) {
  const s = new Date(`${startOfWeek(dateStr)}T12:00:00`);
  return Array.from({ length: 7 }, (_, i) => { const n = new Date(s); n.setDate(s.getDate() + i); return n.toISOString().slice(0, 10); });
}

function buildMonthGrid(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`);
  const first = new Date(d.getFullYear(), d.getMonth(), 1, 12);
  const offsetToMonday = (first.getDay() + 6) % 7;
  const gridStart = new Date(first);
  gridStart.setDate(gridStart.getDate() - offsetToMonday);
  return Array.from({ length: 42 }, (_, i) => {
    const n = new Date(gridStart);
    n.setDate(gridStart.getDate() + i);
    return n.toISOString().slice(0, 10);
  });
}

function getMonthFromDate(dateStr) {
  return dateStr.slice(0, 7);
}

function formatTimeLabel(hour) {
  const v = String(hour || "").trim();
  if (/^\d{2}:\d{2}$/.test(v)) return v;
  if (/^\d{1,2}h$/.test(v)) return `${v.replace("h", "").padStart(2, "0")}:00`;
  return v.replace("h", ":");
}

function addMinutes(timeLabel, mins) {
  const m = String(timeLabel || "").match(/^(\d{2}):(\d{2})$/);
  if (!m) return "—";
  const total = Number(m[1]) * 60 + Number(m[2]) + Number(mins || 0);
  const norm = ((total % 1440) + 1440) % 1440;
  return `${String(Math.floor(norm / 60)).padStart(2, "0")}:${String(norm % 60).padStart(2, "0")}`;
}

function typeIcon(type) {
  const v = String(type || "").toLowerCase();
  if (v.includes("ordonnance")) return "💊";
  if (v.includes("bilan")) return "📋";
  if (v.includes("vaccin")) return "💉";
  if (v.includes("suivi")) return "🔄";
  if (v.includes("prem")) return "👋";
  return "🩺";
}

function toneForAppointment(appt) {
  const text = `${appt?.patient || ""} ${appt?.type || ""}`.toLowerCase();
  if (text.includes("urgent") || text.includes("prioritaire") || text.includes("douleur")) return "red";
  if (text.includes("document demand") || text.includes("pièce demand") || text.includes("piece demand")) return "blue";
  if (text.includes("ordonnance") || text.includes("renouvellement")) return "indigo";
  if (text.includes("récup") || text.includes("recup") || text.includes("repris") || text.includes("sauvé") || text.includes("sauve")) return "purple";
  if (text.includes("libéré") || text.includes("libere") || text.includes("réattrib") || text.includes("reattrib") || text.includes("confirmer")) return "orange";
  if (text.includes("pause") || text.includes("indisponible") || text.includes("ouvert") || text.includes("disponible")) return "gray";
  if (appt?.isUWI) return "green";
  return "teal";
}

function semanticLabelForAppointment(appt) {
  const tone = toneForAppointment(appt);
  if (tone === "red") return "Urgence";
  if (tone === "blue") return "Documents";
  if (tone === "indigo") return "Ordonnance";
  if (tone === "orange") return "À confirmer";
  if (tone === "purple") return "Récupéré";
  if (tone === "green") return "Confirmé";
  if (tone === "gray") return "Indispo";
  return "Consultation";
}

const APPT_TONE = {
  green: { bg: "#ECFDF5", border: "#34D399", time: "#047857", text: "#065F46" },
  orange: { bg: "#FFF7ED", border: "#F59E0B", time: "#C2410C", text: "#9A3412" },
  blue: { bg: "#EFF6FF", border: "#3B82F6", time: "#1D4ED8", text: "#1E3A8A" },
  indigo: { bg: "#EEF2FF", border: "#6366F1", time: "#4338CA", text: "#3730A3" },
  purple: { bg: "#F5F3FF", border: "#8B5CF6", time: "#6D28D9", text: "#5B21B6" },
  red: { bg: "#FEF2F2", border: "#EF4444", time: "#B91C1C", text: "#991B1B" },
  gray: { bg: "#F8FAFC", border: "#CBD5E1", time: "#64748B", text: "#475569" },
  teal: { bg: "#E8F7F7", border: "#14B8A6", time: "#0F766E", text: "#0F766E" },
};

function normalizePhone(raw) {
  const c = String(raw || "").replace(/[^\d+]/g, "");
  if (!c || c.length < 6) return "";
  return c.startsWith("00") ? `+${c.slice(2)}` : c;
}

function formatPhone(raw) {
  const c = normalizePhone(raw);
  if (!c) return "";
  if (c.startsWith("+33") && c.length === 12) {
    return `0${c.slice(3, 4)} ${c.slice(4, 6)} ${c.slice(6, 8)} ${c.slice(8, 10)} ${c.slice(10)}`;
  }
  return c;
}

function splitAgendaPatientName(value) {
  const full = String(value || "").trim();
  if (!full) return { firstName: "", lastName: "" };
  const parts = full.split(/\s+/);
  if (parts.length === 1) return { firstName: "", lastName: parts[0] };
  return { firstName: parts.slice(0, -1).join(" "), lastName: parts.slice(-1)[0] };
}

function composeAgendaPatientName({ firstName, lastName }) {
  return [String(firstName || "").trim(), String(lastName || "").trim()].filter(Boolean).join(" ").trim();
}

function RescheduleCalendar({ onClose, onReschedule, actionLoading }) {
  const [calMonth, setCalMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [availDates, setAvailDates] = useState({});
  const [loadingDates, setLoadingDates] = useState(false);
  const [pickedDate, setPickedDate] = useState(null);
  const [daySlots, setDaySlots] = useState([]);
  const [loadingDay, setLoadingDay] = useState(false);
  const [confirmSlot, setConfirmSlot] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingDates(true);
    api.tenantGetAgendaAvailableDates(calMonth).then((res) => {
      if (!cancelled) setAvailDates(res?.dates || {});
    }).catch(() => {}).finally(() => { if (!cancelled) setLoadingDates(false); });
    return () => { cancelled = true; };
  }, [calMonth]);

  function loadDay(dateStr) {
    setPickedDate(dateStr);
    setConfirmSlot(null);
    setLoadingDay(true);
    api.tenantGetAgendaAvailableSlots(`?date=${dateStr}`).then((res) => {
      setDaySlots(res?.slots || []);
    }).catch(() => { setDaySlots([]); }).finally(() => setLoadingDay(false));
  }

  const year = Number(calMonth.slice(0, 4));
  const month = Number(calMonth.slice(5, 7)) - 1;
  const firstDay = new Date(year, month, 1);
  const startDow = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const todayStr = new Date().toISOString().slice(0, 10);
  const monthLabel = firstDay.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }).replace(/^./, (c) => c.toUpperCase());

  function fmtMonth(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; }
  function prevMonth() { setCalMonth(fmtMonth(new Date(year, month - 1, 1))); setPickedDate(null); setConfirmSlot(null); }
  function nextMonth() { setCalMonth(fmtMonth(new Date(year, month + 1, 1))); setPickedDate(null); setConfirmSlot(null); }

  const fmtDay = (d) => { const dt = new Date(`${d}T12:00:00`); return dt.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }).replace(/^./, (c) => c.toUpperCase()); };

  if (confirmSlot) {
    return (
      <div style={S.reschedulePanel}>
        <div style={S.reschedulePanelHeader}>
          <span style={S.reschedulePanelTitle}>Confirmer le déplacement</span>
          <button type="button" onClick={onClose} style={S.rescheduleCloseBtn}>✕</button>
        </div>
        <div style={S.rescheduleConfirm}>
          <p style={S.rescheduleConfirmText}>Déplacer ce RDV au <strong>{fmtDay(confirmSlot.date)}</strong> à <strong>{confirmSlot.time}</strong> ?</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={() => onReschedule(confirmSlot)} disabled={actionLoading} style={S.rescheduleConfirmBtn}>{actionLoading ? "…" : "Confirmer"}</button>
            <button type="button" onClick={() => setConfirmSlot(null)} style={S.confirmBackBtn}>Retour</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.reschedulePanel}>
      <div style={S.reschedulePanelHeader}>
        <span style={S.reschedulePanelTitle}>{pickedDate ? fmtDay(pickedDate) : "Choisir une date"}</span>
        <button type="button" onClick={onClose} style={S.rescheduleCloseBtn}>✕</button>
      </div>

      {pickedDate ? (
        <div>
          <button type="button" onClick={() => { setPickedDate(null); setDaySlots([]); }} style={S.calBackBtn}>← Calendrier</button>
          {loadingDay ? (
            <div style={S.reschedulePanelEmpty}>Chargement…</div>
          ) : daySlots.length === 0 ? (
            <div style={S.reschedulePanelEmpty}>Aucun créneau libre ce jour.</div>
          ) : (
            <div style={S.slotTimeRow}>
              {daySlots.map((slot) => (
                <button key={slot.slot_id} type="button" className="slot-time-btn" onClick={() => setConfirmSlot(slot)} style={S.slotTimeBtn}>
                  {slot.time}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          <div style={S.calNav}>
            <button type="button" onClick={prevMonth} style={S.calNavBtn}>‹</button>
            <span style={S.calNavLabel}>{loadingDates ? "…" : monthLabel}</span>
            <button type="button" onClick={nextMonth} style={S.calNavBtn}>›</button>
          </div>
          <div style={S.calGrid}>
            {["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"].map((d) => <div key={d} style={S.calDow}>{d}</div>)}
            {cells.map((day, i) => {
              if (day === null) return <div key={`e${i}`} style={S.calCell} />;
              const dateStr = `${calMonth}-${String(day).padStart(2, "0")}`;
              const free = availDates[dateStr] || 0;
              const isPast = dateStr < todayStr;
              const hasSlots = free > 0 && !isPast;
              return (
                <div key={dateStr} className={hasSlots ? "cal-day-avail" : ""} onClick={hasSlots ? () => loadDay(dateStr) : undefined} style={{ ...S.calCell, ...(dateStr === todayStr ? S.calCellToday : {}), ...(hasSlots ? S.calCellAvail : {}), ...(isPast || !hasSlots ? S.calCellDisabled : {}), cursor: hasSlots ? "pointer" : "default" }}>
                  <span>{day}</span>
                  {hasSlots && <span style={S.calCellDot}>{free}</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function InlineDetail({
  a,
  navigate,
  confirmCancel,
  setConfirmCancel,
  handleCancel,
  actionLoading,
  rescheduleMode,
  onStartReschedule,
  onReschedule,
  onCreatePatientFromAgenda,
}) {
  const aPhone = normalizePhone(a.patient_phone || a.phone || "");
  const aPhoneFmt = formatPhone(aPhone);
  const hasPatientFile = Boolean(a.patient_has_file);
  return (
    <div style={S.inlineDetail}>
      <div style={S.inlineGrid}>
        <div style={S.inlineItem}><span style={S.inlineIcon}>🕐</span><span>{a.displayTime} – {a.endTime}</span></div>
        <div style={S.inlineItem}><span style={S.inlineIcon}>📅</span><span>{formatLongDate(a.date)}</span></div>
        <div style={S.inlineItem}><span style={S.inlineIcon}>{a.isUWI ? "🤖" : "📆"}</span><span>{a.isUWI ? "Via assistant IA" : "Agenda externe"}</span></div>
        {aPhoneFmt && <div style={S.inlineItem}><span style={S.inlineIcon}>📞</span><span>{aPhoneFmt}</span></div>}
      </div>
      <div style={S.inlineActions}>
        {aPhone ? <a href={`tel:${aPhone}`} style={S.inlineCallBtn}>📞 Appeler</a> : null}
        {aPhone && hasPatientFile ? (
          <button
            type="button"
            onClick={() => navigate(`/app/patient-dashboard?phone=${encodeURIComponent(aPhone)}`)}
            style={S.inlineSecBtn}
          >
            👤 Fiche patient
          </button>
        ) : null}
        {aPhone && !hasPatientFile ? (
          <button
            type="button"
            onClick={() => onCreatePatientFromAgenda?.(a)}
            style={S.inlineSecBtn}
          >
            👤 Créer fiche patient
          </button>
        ) : null}
        {!aPhone ? (
          <button
            type="button"
            onClick={() => navigate("/app/patient-dashboard")}
            style={S.inlineSecBtn}
          >
            👤 Patients
          </button>
        ) : null}
        {a.canCancel && !confirmCancel && !rescheduleMode && (
          <button type="button" onClick={onStartReschedule} style={S.inlineRescheduleBtn}>🔄 Déplacer</button>
        )}
        {a.canCancel && !confirmCancel && !rescheduleMode && (
          <button type="button" onClick={() => setConfirmCancel(true)} style={S.inlineDangerBtn}>Annuler RDV</button>
        )}
      </div>

      {rescheduleMode && (
        <RescheduleCalendar onClose={() => onStartReschedule("close")} onReschedule={onReschedule} actionLoading={actionLoading} />
      )}

      {a.canCancel && confirmCancel && (
        <div style={S.inlineConfirm}>
          <p style={S.inlineConfirmText}>Annuler ce RDV ? Un SMS sera envoye au patient.</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={handleCancel} disabled={actionLoading} style={S.confirmCancelBtn}>{actionLoading ? "…" : "Confirmer"}</button>
            <button type="button" onClick={() => setConfirmCancel(false)} style={S.confirmBackBtn}>Retour</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AppAgenda() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlDate = searchParams.get("date");
  const urlView = searchParams.get("view");
  const urlPhone = searchParams.get("phone");
  const urlFocus = searchParams.get("focus");
  const [selectedDate, setSelectedDate] = useState(urlDate || todayISO());
  const [pendingFocusPhone, setPendingFocusPhone] = useState(urlPhone || null);
  const [viewMode, setViewMode] = useState("day");

  useEffect(() => {
    if (urlDate && urlDate !== selectedDate) {
      setSelectedDate(urlDate);
      setViewMode("day");
    }
    if (urlView === "day" || urlView === "week" || urlView === "month") {
      setViewMode(urlView);
    }
    if (urlPhone) setPendingFocusPhone(urlPhone);
  }, [urlDate, urlView, urlPhone, selectedDate]);

  /* Liens depuis le dashboard : focus=annulations | creneaux-recuperes → jour + date explicite */
  useEffect(() => {
    if (urlFocus !== "annulations" && urlFocus !== "creneaux-recuperes") return;
    setViewMode("day");
    const d = urlDate && /^\d{4}-\d{2}-\d{2}$/.test(urlDate) ? urlDate : todayISO();
    setSelectedDate(d);
  }, [urlFocus, urlDate]);
  const [agendaByDate, setAgendaByDate] = useState({});
  const [horaires, setHoraires] = useState(null);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedAppt, setSelectedAppt] = useState(null);
  const [actionMsg, setActionMsg] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [rescheduleMode, setRescheduleMode] = useState(false);
  const [patientCreateOpen, setPatientCreateOpen] = useState(false);
  const [patientCreateLoading, setPatientCreateLoading] = useState(false);
  const [patientCreateSummary, setPatientCreateSummary] = useState("");
  const [patientCreateForm, setPatientCreateForm] = useState({
    firstName: "",
    lastName: "",
    phone: "",
    initialNote: "",
    agendaMotif: "",
    rawCalendarName: "",
    callId: "",
  });

  const weekDates = useMemo(() => buildWeekDates(selectedDate), [selectedDate]);
  const monthGrid = useMemo(() => buildMonthGrid(selectedDate), [selectedDate]);
  const currentMonth = getMonthFromDate(selectedDate);
  const today = todayISO();

  const visibleDates = useMemo(() => {
    if (viewMode === "month") return [...new Set(monthGrid)];
    if (viewMode === "week") return weekDates;
    return [selectedDate];
  }, [viewMode, weekDates, monthGrid, selectedDate]);

  const loadAgenda = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextMe, nextHoraires, bulkRes] = await Promise.all([
        api.tenantMe(),
        api.tenantGetHoraires(),
        api.tenantGetAgendaBulk(visibleDates).catch(() => null),
      ]);
      setMe(nextMe);
      setHoraires(nextHoraires);
      const byDate = {};
      if (bulkRes?.dates) {
        visibleDates.forEach((d) => { byDate[d] = bulkRes.dates[d] || { slots: [], date: d }; });
      } else {
        const results = await Promise.all(visibleDates.map((d) => api.tenantGetAgenda(`?date=${d}`).catch(() => ({ slots: [], date: d }))));
        visibleDates.forEach((d, i) => { byDate[d] = results[i]; });
      }
      setAgendaByDate(byDate);
    } catch (e) {
      setError(e?.message || "Impossible de charger l'agenda.");
    } finally {
      setLoading(false);
    }
  }, [visibleDates]);

  useEffect(() => { loadAgenda(); }, [loadAgenda]);

  useEffect(() => {
    if (!actionMsg) return undefined;
    const t = window.setTimeout(() => setActionMsg(""), 4000);
    return () => window.clearTimeout(t);
  }, [actionMsg]);

  const duration = Number(horaires?.booking_duration_minutes || 30);
  // Grille horaire généreuse : 7h-21h par défaut, étendue si le cabinet
  // ouvre plus tôt/finit plus tard ou si un RDV existe en dehors.
  const MIN_GRID_START = 7;
  const MIN_GRID_END = 21;
  const cfgStart = Number.isFinite(Number(horaires?.booking_start_hour)) ? Number(horaires.booking_start_hour) : MIN_GRID_START;
  const cfgEnd = Number.isFinite(Number(horaires?.booking_end_hour)) ? Number(horaires.booking_end_hour) : MIN_GRID_END;
  const startHour = Math.min(MIN_GRID_START, cfgStart);
  const endHour = Math.max(MIN_GRID_END, cfgEnd);
  const apptHourBounds = useMemo(() => {
    let min = null, max = null;
    visibleDates.forEach((date) => {
      (agendaByDate[date]?.slots || []).forEach((s) => {
        const t = formatTimeLabel(s.hour);
        const h = Number(String(t).slice(0, 2));
        if (!Number.isNaN(h)) {
          if (min === null || h < min) min = h;
          if (max === null || h > max) max = h;
        }
      });
    });
    return { min, max };
  }, [agendaByDate, visibleDates]);

  const hours = useMemo(() => {
    const lo = Math.min(startHour, apptHourBounds.min ?? startHour);
    const hi = Math.max(endHour, (apptHourBounds.max ?? endHour - 1) + 1);
    const h = [];
    for (let i = lo; i < hi; i++) h.push(`${String(i).padStart(2, "0")}:00`);
    return h;
  }, [startHour, endHour, apptHourBounds]);

  const appointments = useMemo(() =>
    visibleDates.flatMap((date) =>
      (agendaByDate[date]?.slots || []).map((s, i) => ({
        ...s,
        id: `${date}-${s.event_id || s.appointment_id || i}`,
        date,
        displayTime: formatTimeLabel(s.hour),
        endTime: addMinutes(formatTimeLabel(s.hour), duration),
        typeIcon: typeIcon(s.type),
        isUWI: s.source === "UWI",
        canCancel: !!s.can_cancel,
        actionId: s.appointment_id || s.event_id || "",
      })),
    ),
    [agendaByDate, visibleDates, duration],
  );

  /** RDV au statut annulé dans la période affichée (aligné logique dashboard). */
  const cancelledInVisible = useMemo(
    () => appointments.filter((a) => String(a?.status || "").toLowerCase().includes("cancel")).length,
    [appointments],
  );

  /** Deep link depuis le dashboard : scroll vers la pastille Annulations / Créneau récupéré */
  useEffect(() => {
    if (loading) return undefined;
    if (urlFocus !== "annulations" && urlFocus !== "creneaux-recuperes") return undefined;
    const id = urlFocus === "annulations" ? "agenda-focus-annulations" : "agenda-focus-creneaux-recuperes";
    const run = () => {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
    run();
    const raf = window.requestAnimationFrame(run);
    const t = window.setTimeout(run, 160);
    return () => {
      window.cancelAnimationFrame(raf);
      window.clearTimeout(t);
    };
  }, [loading, urlFocus, viewMode, selectedDate, appointments.length]);

  const apptCountByDate = useMemo(() => {
    const map = {};
    appointments.forEach((a) => { map[a.date] = (map[a.date] || 0) + 1; });
    return map;
  }, [appointments]);

  useEffect(() => {
    if (!pendingFocusPhone) return;
    if (!appointments.length) return;
    const norm = (p) => String(p || "").replace(/[\s().-]/g, "");
    const target = norm(pendingFocusPhone);
    const match = appointments.find((a) => a.date === selectedDate && norm(a.patient_phone) === target);
    if (match) {
      setSelectedAppt(match);
      setConfirmCancel(false);
      setRescheduleMode(false);
      setPendingFocusPhone(null);
    }
  }, [appointments, selectedDate, pendingFocusPhone]);

  const todayCount = appointments.filter((a) => a.date === selectedDate).length;
  const uwiCount = appointments.filter((a) => a.isUWI).length;
  const isConnected = me?.calendar_provider === "google" && me?.calendar_id;

  async function handleCancel() {
    if (!selectedAppt?.canCancel) return;
    setActionLoading(true);
    try {
      await api.tenantCancelAgendaAppointment(selectedAppt.actionId || selectedAppt.appointment_id || selectedAppt.event_id || selectedAppt.id, {
        source: selectedAppt.source,
        external_event_id: selectedAppt.event_id || "",
      });
      setActionMsg({ text: "Rendez-vous annulé. Le patient a été notifié par SMS.", type: "success" });
      setSelectedAppt(null);
      setConfirmCancel(false);
      await loadAgenda();
    } catch (e) {
      setActionMsg({ text: e?.message || "Impossible d'annuler.", type: "error" });
      setConfirmCancel(false);
    } finally {
      setActionLoading(false);
    }
  }

  function resetReschedule() {
    setRescheduleMode(false);
  }

  function toggleAppt(a) {
    if (selectedAppt?.id === a.id) {
      setSelectedAppt(null);
      setConfirmCancel(false);
      resetReschedule();
    } else {
      setSelectedAppt(a);
      setConfirmCancel(false);
      resetReschedule();
    }
  }

  function handleStartReschedule(action) {
    if (action === "close") { resetReschedule(); return; }
    setRescheduleMode(true);
    setConfirmCancel(false);
  }

  async function handleReschedule(slot) {
    if (!selectedAppt) return;
    setActionLoading(true);
    try {
      await api.tenantRescheduleAgendaAppointment(
        selectedAppt.actionId || selectedAppt.appointment_id || selectedAppt.id,
        { new_slot_id: slot.slot_id, external_event_id: selectedAppt.event_id || "" },
      );
      const fmtDate = new Date(`${slot.date}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
      setActionMsg({ text: `RDV déplacé au ${fmtDate} à ${slot.time}`, type: "success" });
      setSelectedAppt(null);
      resetReschedule();
      await loadAgenda();
    } catch (e) {
      setActionMsg({ text: e?.message || "Impossible de déplacer le RDV.", type: "error" });
    } finally {
      setActionLoading(false);
    }
  }

  function openPatientCreateFromAppointment(appt) {
    const fromName = splitAgendaPatientName(appt?.patient);
    const motif = String(appt?.type || "").trim();
    const initialNote = [
      `Rendez-vous : ${formatLongDate(appt?.date)} · ${appt?.displayTime || ""}`,
      motif ? `Motif : ${motif}` : null,
    ]
      .filter(Boolean)
      .join("\n");
    setPatientCreateForm({
      firstName: fromName.firstName,
      lastName: fromName.lastName,
      phone: normalizePhone(appt?.patient_phone || ""),
      initialNote,
      agendaMotif: motif,
      rawCalendarName: String(appt?.patient || "").trim(),
      callId: "",
    });
    setPatientCreateSummary(
      `${formatLongDate(appt?.date)} · ${appt?.displayTime || "—"}${motif ? ` · ${motif}` : ""}`,
    );
    setPatientCreateOpen(true);
  }

  async function handlePatientCreateFromAgendaSubmit() {
    const phone = normalizePhone(patientCreateForm.phone);
    const name = composeAgendaPatientName(patientCreateForm);
    if (!phone) {
      setActionMsg({ type: "error", text: "Le téléphone est requis pour créer une fiche patient." });
      return;
    }
    if ((name || "").trim().length < 2) {
      setActionMsg({
        type: "error",
        text: "Indiquez au moins le nom ou le prénom (au moins 2 caractères au total).",
      });
      return;
    }
    setPatientCreateLoading(true);
    try {
      await api.tenantRegisterPatient({
        patient_phone: phone,
        validated_name: name,
        raw_name: (patientCreateForm.rawCalendarName || "").trim() || name,
        agenda_motif: (patientCreateForm.agendaMotif || "").trim() || undefined,
        initial_note: (patientCreateForm.initialNote || "").trim() || undefined,
      });
      setPatientCreateOpen(false);
      setActionMsg({ type: "success", text: "Fiche patient enregistrée." });
      await loadAgenda();
      navigate(`/app/patient-dashboard?phone=${encodeURIComponent(phone)}`);
    } catch (e) {
      setActionMsg({ type: "error", text: e?.message || "Impossible de créer la fiche patient." });
    } finally {
      setPatientCreateLoading(false);
    }
  }

  function navPrev() {
    setSelectedDate((v) => viewMode === "month" ? shiftMonth(v, -1) : shiftDate(v, viewMode === "week" ? -7 : -1));
  }
  function navNext() {
    setSelectedDate((v) => viewMode === "month" ? shiftMonth(v, 1) : shiftDate(v, viewMode === "week" ? 7 : 1));
  }
  function goToday() { setSelectedDate(todayISO()); }

  const subtitleMap = {
    day: `${todayCount} RDV aujourd'hui`,
    week: `${appointments.length} RDV cette semaine`,
    month: `${appointments.length} RDV ce mois`,
  };
  const semanticCounts = useMemo(() => {
    const base = { green: 0, orange: 0, purple: 0, red: 0, blue: 0, indigo: 0, gray: 0, teal: 0 };
    appointments.forEach((a) => {
      const tone = toneForAppointment(a);
      base[tone] = (base[tone] || 0) + 1;
    });
    return base;
  }, [appointments]);
  const kpiCards = [
    { tone: "teal", value: appointments.length, label: viewMode === "month" ? "rendez-vous" : "rendez-vous" },
    { tone: "orange", value: semanticCounts.orange, label: "à confirmer" },
    { tone: "purple", value: semanticCounts.purple, label: "créneaux récupérés" },
    { tone: "green", value: Math.max(semanticCounts.green, uwiCount), label: "rappels envoyés" },
  ];
  const weekActionItems = useMemo(() => {
    const weekAppts = appointments.filter((a) => weekDates.includes(a.date));
    const firstByTone = (tone) => weekAppts.find((a) => toneForAppointment(a) === tone);
    const urgent = firstByTone("red");
    const pending = firstByTone("orange");
    const recovered = firstByTone("purple");
    return [
      {
        tone: "red",
        title: urgent?.patient || "Aucune urgence",
        subtitle: urgent ? `${formatLongDate(urgent.date)} · ${urgent.displayTime}` : "Alerte prioritaire cette semaine",
      },
      {
        tone: "orange",
        title: pending?.patient || "À confirmer",
        subtitle: pending ? `${formatLongDate(pending.date)} · ${pending.displayTime}` : "Relances à lancer",
      },
      {
        tone: "purple",
        title: recovered ? "Créneau sauvé" : "Créneaux récupérés",
        subtitle: `${semanticCounts.purple} rendez-vous récupérés`,
      },
      {
        tone: "green",
        title: "Confirmations",
        subtitle: `${semanticCounts.green} patients confirmés`,
      },
    ];
  }, [appointments, weekDates, semanticCounts.purple, semanticCounts.green]);
  const weekLoadRows = useMemo(() => {
    return weekDates.map((d) => {
      const { wd, num } = formatShortDay(d);
      return { key: d, label: `${wd} ${num}`, count: appointments.filter((a) => a.date === d).length };
    });
  }, [weekDates, appointments]);
  const dayAppointments = useMemo(
    () => appointments.filter((a) => a.date === selectedDate),
    [appointments, selectedDate],
  );
  const dayCounts = useMemo(() => {
    const counts = { total: dayAppointments.length, confirmed: 0, pending: 0, urgent: 0, recovered: 0 };
    dayAppointments.forEach((a) => {
      const t = toneForAppointment(a);
      if (t === "green") counts.confirmed += 1;
      if (t === "orange") counts.pending += 1;
      if (t === "red") counts.urgent += 1;
      if (t === "purple") counts.recovered += 1;
    });
    return counts;
  }, [dayAppointments]);
  const dayRange = useMemo(() => {
    if (!dayAppointments.length) return "Aucun RDV aujourd'hui";
    const sorted = [...dayAppointments].sort((a, b) => String(a.displayTime).localeCompare(String(b.displayTime)));
    const first = sorted[0]?.displayTime || "--:--";
    const last = sorted[sorted.length - 1]?.endTime || "--:--";
    return `${first} - ${last}`;
  }, [dayAppointments]);
  const monthAppointments = useMemo(
    () => appointments.filter((a) => getMonthFromDate(a.date) === currentMonth),
    [appointments, currentMonth],
  );
  const monthCounts = useMemo(() => {
    const counts = { total: monthAppointments.length, confirmed: 0, pending: 0, urgent: 0, docs: 0, ordonnance: 0, recovered: 0 };
    monthAppointments.forEach((a) => {
      const t = toneForAppointment(a);
      if (t === "green") counts.confirmed += 1;
      if (t === "orange") counts.pending += 1;
      if (t === "red") counts.urgent += 1;
      if (t === "blue") counts.docs += 1;
      if (t === "indigo") counts.ordonnance += 1;
      if (t === "purple") counts.recovered += 1;
    });
    return counts;
  }, [monthAppointments]);
  const monthTopDays = useMemo(() => {
    const byDate = {};
    monthAppointments.forEach((a) => { byDate[a.date] = (byDate[a.date] || 0) + 1; });
    return Object.entries(byDate)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([date, count]) => ({ date, count, label: formatLongDate(date) }));
  }, [monthAppointments]);
  const semanticLegend = [
    { tone: "red", label: "Urgence / prioritaire" },
    { tone: "blue", label: "Documents demandés" },
    { tone: "indigo", label: "Ordonnance / renouvellement" },
    { tone: "orange", label: "À confirmer / à réattribuer" },
    { tone: "purple", label: "Créneau récupéré" },
    { tone: "green", label: "Confirmé" },
    { tone: "gray", label: "Indisponible / libre" },
  ];

  if (loading) {
    return <div style={S.page}><style>{CSS}</style><div style={S.loadingBox}>Chargement de l&apos;agenda…</div></div>;
  }

  const navLabel = viewMode === "month"
    ? formatMonthLabel(selectedDate)
    : viewMode === "week"
      ? `Semaine du ${formatLongDate(weekDates[0])}`
      : formatLongDate(selectedDate);

  const WEEKDAY_LABELS = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"];

  return (
    <div style={S.page}>
      <style>{CSS}</style>

      {error ? <div style={S.errorBox}>{error}</div> : null}
      {actionMsg ? <div style={actionMsg.type === "error" ? S.toastError : S.toast}>
        {actionMsg.type === "error" ? "⚠️ " : "✅ "}{actionMsg.text || actionMsg}
      </div> : null}

      {/* ─── BARRE UNIQUE : navigation + vues + stats ─── */}
      <div style={S.toolbar}>
        <div style={S.toolbarLeft}>
          <button type="button" onClick={navPrev} style={S.navBtn}>‹</button>
          <span style={S.navDate}>{navLabel}</span>
          <button type="button" onClick={navNext} style={S.navBtn}>›</button>
          {selectedDate !== today && <button type="button" onClick={goToday} style={S.todayBtn}>Aujourd&apos;hui</button>}
        </div>
        <div style={S.toolbarRight}>
          <span style={S.stats}>
            {subtitleMap[viewMode]}
            {uwiCount > 0 ? ` · ${uwiCount} via IA` : ""}
            {isConnected ? " · 🟢" : ""}
          </span>
          <div style={S.viewSwitch}>
            {["day", "week", "month"].map((m) => (
              <button key={m} type="button" onClick={() => setViewMode(m)} style={viewMode === m ? S.viewBtnActive : S.viewBtn}>
                {m === "day" ? "Jour" : m === "week" ? "Semaine" : "Mois"}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div style={S.legendRow}>
        {semanticLegend.map((item) => {
          const tone = APPT_TONE[item.tone] || APPT_TONE.teal;
          const anchorId =
            item.tone === "purple"
              ? "agenda-focus-creneaux-recuperes"
              : undefined;
          return (
            <div
              key={item.label}
              id={anchorId}
              style={{ ...S.legendItem, background: tone.bg, borderColor: `${tone.border}55` }}
            >
              <span style={{ ...S.legendDot, background: tone.border }} />
              <span style={{ ...S.legendText, color: tone.text }}>{item.label}</span>
            </div>
          );
        })}
        <div
          id="agenda-focus-annulations"
          style={{
            ...S.legendItem,
            background: APPT_TONE.orange.bg,
            borderColor: `${APPT_TONE.orange.border}55`,
          }}
          title="Rendez-vous au statut annulé dans la période affichée"
        >
          <span style={{ ...S.legendDot, background: APPT_TONE.orange.border }} />
          <span style={{ ...S.legendText, color: APPT_TONE.orange.text }}>
            Annulations ({cancelledInVisible})
          </span>
        </div>
      </div>
      <div className="agenda-kpi-row" style={S.kpiRow}>
        {kpiCards.map((card) => {
          const tone = APPT_TONE[card.tone] || APPT_TONE.teal;
          return (
            <div key={`${card.label}-${card.tone}`} style={{ ...S.kpiCard, borderColor: `${tone.border}30` }}>
              <div style={{ ...S.kpiDot, background: tone.bg, color: tone.time }}>◉</div>
              <div>
                <div style={S.kpiValue}>{card.value}</div>
                <div style={S.kpiLabel}>{card.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ─── CALENDAR ─── */}
      <div style={S.calendarCol}>

        {/* ═══ MONTH VIEW ═══ */}
        {viewMode === "month" && (
          <div className="agenda-month-layout" style={S.monthLayout}>
            <div style={S.card}>
            {/* Détail du RDV sélectionné (au-dessus de la grille mois) */}
            {selectedAppt && (
              <div style={S.topDetailWrap}>
                <div style={S.topDetailHeader}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                    <span style={{ fontSize: 18 }}>{selectedAppt.typeIcon}</span>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 800, color: NAVY }}>{selectedAppt.patient || "Patient"}</div>
                      <div style={{ fontSize: 12, color: MUTED }}>{selectedAppt.type || "Consultation"}</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => { setSelectedAppt(null); setConfirmCancel(false); }} style={S.weekDetailClose}>✕</button>
                </div>
                <InlineDetail
                  a={selectedAppt}
                  navigate={navigate}
                  confirmCancel={confirmCancel}
                  setConfirmCancel={setConfirmCancel}
                  handleCancel={handleCancel}
                  actionLoading={actionLoading}
                  rescheduleMode={rescheduleMode}
                  onStartReschedule={handleStartReschedule}
                  onReschedule={handleReschedule}
                  onCreatePatientFromAgenda={openPatientCreateFromAppointment}
                />
              </div>
            )}
              <div style={S.monthGridWrap}>
              {WEEKDAY_LABELS.map((wd) => (
                <div key={wd} style={S.monthWdHeader}>{wd}</div>
              ))}
              {monthGrid.map((d, idx) => {
                const isCurrentMonth = getMonthFromDate(d) === currentMonth;
                const isToday = d === today;
                const dayAppts = appointments.filter((a) => a.date === d);
                const dayNum = new Date(`${d}T12:00:00`).getDate();
                const maxVisible = 3;
                const overflow = dayAppts.length - maxVisible;
                return (
                  <div
                    key={d}
                    className="month-day-cell"
                    style={{
                      ...S.monthCell,
                      opacity: isCurrentMonth ? 1 : 0.3,
                      ...(isCurrentMonth && idx % 2 === 0 ? S.monthCellAlt : {}),
                      ...(isToday ? S.monthCellToday : {}),
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => { setSelectedDate(d); setViewMode("day"); }}
                      style={{ ...S.monthDayNumBtn, ...(isToday ? S.monthDayNumToday : {}) }}
                    >
                      {dayNum}
                    </button>
                    <div style={S.monthApptList}>
                      {dayAppts.slice(0, maxVisible).map((a) => {
                        const tone = APPT_TONE[toneForAppointment(a)] || APPT_TONE.teal;
                        return (
                        <button
                          key={a.id}
                          type="button"
                          className="month-appt-pill"
                          onClick={() => toggleAppt(a)}
                          style={{
                            ...S.monthApptPill,
                            background: tone.bg,
                            borderLeftColor: tone.border,
                            ...(selectedAppt?.id === a.id ? { boxShadow: `0 0 0 2px ${tone.border}50` } : {}),
                          }}
                        >
                          <span style={{ ...S.monthApptTime, color: tone.time }}>{a.displayTime}</span>
                          <span style={{ ...S.monthApptName, color: tone.text }}>{a.patient || "Patient"}</span>
                        </button>
                      );})}
                      {overflow > 0 && (
                        <button type="button" onClick={() => { setSelectedDate(d); setViewMode("day"); }} style={S.monthOverflow}>
                          +{overflow} autre{overflow > 1 ? "s" : ""}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
              </div>
            </div>
            <div style={S.monthSide}>
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Mois en cours</div>
                <div style={S.sideHeadTitle}>Synthèse du mois</div>
                <div style={S.sideHeadSub}>Vue globale des performances et priorités du mois en cours.</div>
                <div style={S.sideList}>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.green.border }} /><div><div style={S.sideRowTitle}>{monthCounts.confirmed} confirmés</div><div style={S.sideRowSub}>Patients confirmés sur le mois</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.orange.border }} /><div><div style={S.sideRowTitle}>{monthCounts.pending} à confirmer</div><div style={S.sideRowSub}>Relances Clara à finaliser</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.red.border }} /><div><div style={S.sideRowTitle}>{monthCounts.urgent} urgences</div><div style={S.sideRowSub}>Demandes prioritaires détectées</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.purple.border }} /><div><div style={S.sideRowTitle}>{monthCounts.recovered} créneaux récupérés</div><div style={S.sideRowSub}>Slots sauvés par Clara</div></div></div>
                </div>
              </div>
              <div style={S.sideCard}>
                <div style={S.sideCardTitle}>Actions du mois</div>
                <div style={S.loadList}>
                  <div style={S.loadRowHead}><span>Total RDV</span><span>{monthCounts.total}</span></div>
                  <div style={S.loadRowHead}><span>Documents demandés</span><span>{monthCounts.docs}</span></div>
                  <div style={S.loadRowHead}><span>Ordonnances</span><span>{monthCounts.ordonnance}</span></div>
                  {monthTopDays.map((row) => (
                    <div key={row.date}>
                      <div style={S.loadRowHead}><span>{row.label}</span><span>{row.count} RDV</span></div>
                      <div style={S.loadTrack}>
                        <div style={{ ...S.loadFill, width: `${Math.min(100, row.count * 14)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══ WEEK VIEW ═══ */}
        {viewMode === "week" && (
          <div className="agenda-week-layout" style={S.weekLayout}>
            <div style={S.card}>
              <div style={S.weekHead}>
                <div>
                  <div style={S.weekHeadTitle}>Vue semaine — vraie grille de rendez-vous</div>
                  <div style={S.weekHeadSub}>Clique colonne : affiche les créneaux, patients, alertes et actions Clara.</div>
                </div>
                <div style={S.weekHeadBadges}>
                  <span style={S.weekHeadBadgeRed}>Prioritaire {semanticCounts.red}</span>
                  <span style={S.weekHeadBadgeOrange}>À confirmer {semanticCounts.orange}</span>
                  <span style={S.weekHeadBadgePurple}>Récupéré {semanticCounts.purple}</span>
                </div>
              </div>
              {/* Détail du RDV sélectionné (au-dessus de la grille semaine) */}
              {selectedAppt && (
                <div style={S.topDetailWrap}>
                  <div style={S.topDetailHeader}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                      <span style={{ fontSize: 18 }}>{selectedAppt.typeIcon}</span>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 800, color: NAVY }}>{selectedAppt.patient || "Patient"}</div>
                        <div style={{ fontSize: 12, color: MUTED }}>{selectedAppt.type || "Consultation"}</div>
                      </div>
                    </div>
                    <button type="button" onClick={() => { setSelectedAppt(null); setConfirmCancel(false); }} style={S.weekDetailClose}>✕</button>
                  </div>
                  <InlineDetail
                    a={selectedAppt}
                    navigate={navigate}
                    confirmCancel={confirmCancel}
                    setConfirmCancel={setConfirmCancel}
                    handleCancel={handleCancel}
                    actionLoading={actionLoading}
                    rescheduleMode={rescheduleMode}
                    onStartReschedule={handleStartReschedule}
                    onReschedule={handleReschedule}
                    onCreatePatientFromAgenda={openPatientCreateFromAppointment}
                  />
                </div>
              )}
              <div className="agenda-week-scroll" style={S.weekScroll}>
                <div className="agenda-week-grid" style={{ ...S.weekGrid, gridTemplateColumns: `54px repeat(${weekDates.length}, minmax(116px, 1fr))` }}>
                  <div style={S.weekCorner} />
                  {weekDates.map((d) => {
                    const { wd, num } = formatShortDay(d);
                    const isToday = d === today;
                    const isSelected = d === selectedDate;
                    return (
                      <button key={d} type="button" onClick={() => { setSelectedDate(d); setViewMode("day"); }} style={{ ...S.weekDayHeader, ...(isToday ? S.weekDayToday : isSelected ? S.weekDaySelected : {}) }}>
                        <span style={S.weekDayLabel}>{wd}</span>
                        <span style={{ ...S.weekDayNum, ...(isToday ? { color: BLUE } : {}) }}>{num}</span>
                        {isToday && <span style={S.todayDot} />}
                      </button>
                    );
                  })}
                  {hours.map((hour) => (
                    <Fragment key={hour}>
                      <div style={S.weekTimeCell}><span style={S.weekTimeLabel}>{hour}</span></div>
                      {weekDates.map((d, dayIdx) => {
                        const cellAppts = appointments.filter((a) => a.date === d && a.displayTime === hour);
                        return (
                          <div key={`${d}-${hour}`} style={{ ...S.weekCell, ...(dayIdx % 2 === 0 ? S.weekCellAlt : {}) }}>
                            {cellAppts.map((a) => {
                              const tone = APPT_TONE[toneForAppointment(a)] || APPT_TONE.teal;
                              return (
                                <button key={a.id} type="button" className="agenda-appt-chip" onClick={(e) => { e.stopPropagation(); toggleAppt(a); }} style={{ ...S.weekChip, background: tone.bg, borderLeftColor: tone.border, ...(selectedAppt?.id === a.id ? { boxShadow: `0 0 0 2px ${tone.border}40` } : {}) }}>
                                  <div style={S.chipTop}>
                                    <span style={{ ...S.chipTime, color: tone.time }}>{a.displayTime}</span>
                                    <span style={{ ...S.chipTag, color: tone.time }}>{semanticLabelForAppointment(a)}</span>
                                  </div>
                                  <span style={{ ...S.chipName, color: tone.text }}>{a.patient || "Patient"}</span>
                                </button>
                              );
                            })}
                          </div>
                        );
                      })}
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
            <div style={S.weekSide}>
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Semaine en cours</div>
                <div style={S.sideHeadTitle}>6 actions qui comptent</div>
                <div style={S.sideHeadSub}>Vue métier claire pour prioriser rapidement.</div>
                <div style={S.sideList}>
                  {weekActionItems.map((item) => {
                    const tone = APPT_TONE[item.tone] || APPT_TONE.teal;
                    return (
                      <div key={`${item.title}-${item.subtitle}`} style={S.sideRow}>
                        <span style={{ ...S.sideDot, background: tone.border }} />
                        <div>
                          <div style={S.sideRowTitle}>{item.title}</div>
                          <div style={S.sideRowSub}>{item.subtitle}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div style={S.sideCard}>
                <div style={S.sideCardTitle}>Charge réelle</div>
                <div style={S.loadList}>
                  {weekLoadRows.map((row) => (
                    <div key={row.key}>
                      <div style={S.loadRowHead}>
                        <span>{row.label}</span>
                        <span>{row.count} RDV</span>
                      </div>
                      <div style={S.loadTrack}>
                        <div style={{ ...S.loadFill, width: `${Math.min(100, row.count * 12)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══ DAY VIEW ═══ */}
        {viewMode === "day" && (
          <div className="agenda-day-layout" style={S.dayLayout}>
            <div style={S.card}>
              <div style={S.dayTimeline}>
                {hours.map((hour) => {
                  const hourAppts = appointments.filter((a) => a.date === selectedDate && a.displayTime === hour);
                  const isNow = selectedDate === today && hour === `${String(new Date().getHours()).padStart(2, "0")}:00`;
                  return (
                    <div key={hour} style={{ ...S.dayRow, ...(isNow ? S.dayRowNow : {}) }}>
                      <div style={S.dayHour}>{hour}</div>
                      <div style={S.daySlots}>
                        {hourAppts.length === 0 ? (
                          <div style={S.dayEmpty} />
                        ) : (
                          hourAppts.map((a) => {
                            const tone = APPT_TONE[toneForAppointment(a)] || APPT_TONE.teal;
                            const isOpen = selectedAppt?.id === a.id;
                            return (
                              <div key={a.id}>
                                <button type="button" className="agenda-appt-card" onClick={() => toggleAppt(a)} style={{ ...S.dayCard, background: tone.bg, borderLeftColor: tone.border, ...(isOpen ? { borderBottomLeftRadius: 0, borderBottomRightRadius: 0 } : {}) }}>
                                  <div style={S.dayCardTop}>
                                    <div style={{ ...S.dayCardTime, color: tone.time }}>{a.displayTime} – {a.endTime}</div>
                                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                      <span style={{ ...S.dayTag, color: tone.time, borderColor: `${tone.border}66` }}>{semanticLabelForAppointment(a)}</span>
                                      {a.isUWI && <span style={S.aiBadge}>IA</span>}
                                    </div>
                                  </div>
                                  <div style={{ ...S.dayCardName, color: tone.text }}>{a.patient || "Patient"}</div>
                                  <div style={S.dayCardType}>{a.typeIcon} {a.type || "Consultation"}</div>
                                </button>
                                {isOpen && (
                                  <InlineDetail
                                    a={a}
                                    navigate={navigate}
                                    confirmCancel={confirmCancel}
                                    setConfirmCancel={setConfirmCancel}
                                    handleCancel={handleCancel}
                                    actionLoading={actionLoading}
                                    rescheduleMode={rescheduleMode}
                                    onStartReschedule={handleStartReschedule}
                                    onReschedule={handleReschedule}
                                    onCreatePatientFromAgenda={openPatientCreateFromAppointment}
                                  />
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
                {dayAppointments.length === 0 && (
                  <div style={S.emptyDay}>
                    <div style={{ fontSize: 28 }}>📅</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: NAVY, marginTop: 8 }}>Aucun rendez-vous</div>
                    <div style={{ fontSize: 13, color: MUTED, marginTop: 4 }}>Pas de rendez-vous prévu ce jour.</div>
                  </div>
                )}
              </div>
            </div>
            <div style={S.daySide}>
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Journée en cours</div>
                <div style={S.sideHeadTitle}>Résumé de la journée</div>
                <div style={S.sideHeadSub}>Synthèse rapide des rendez-vous du jour et priorités à traiter.</div>
                <div style={S.sideList}>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.green.border }} /><div><div style={S.sideRowTitle}>{dayCounts.confirmed} confirmés</div><div style={S.sideRowSub}>Patients confirmés aujourd'hui</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.orange.border }} /><div><div style={S.sideRowTitle}>{dayCounts.pending} à confirmer</div><div style={S.sideRowSub}>Relances Clara en attente</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.red.border }} /><div><div style={S.sideRowTitle}>{dayCounts.urgent} urgences</div><div style={S.sideRowSub}>Demandes prioritaires du jour</div></div></div>
                </div>
              </div>
              <div style={S.sideCard}>
                <div style={S.sideCardTitle}>Détail du jour</div>
                <div style={S.loadList}>
                  <div style={S.loadRowHead}><span>Amplitude</span><span>{dayRange}</span></div>
                  <div style={S.loadRowHead}><span>Total RDV</span><span>{dayCounts.total}</span></div>
                  <div style={S.loadRowHead}><span>Creneaux recuperes</span><span>{dayCounts.recovered}</span></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <CreatePatientFromCallModal
        open={patientCreateOpen}
        loading={patientCreateLoading}
        form={patientCreateForm}
        onChange={(field, value) => setPatientCreateForm((prev) => ({ ...prev, [field]: value }))}
        onClose={() => setPatientCreateOpen(false)}
        onSubmit={handlePatientCreateFromAgendaSubmit}
        subtitleLine={
          <>
            Source : <strong>rendez-vous agenda</strong>
            {patientCreateSummary ? (
              <>
                {" "}
                · <span>{patientCreateSummary}</span>
              </>
            ) : null}
          </>
        }
      />
    </div>
  );
}

const S = {
  page: { minHeight: "100%", background: "#F6F8FB", fontFamily: "'Inter', 'DM Sans', sans-serif", color: NAVY, padding: "18px 24px 36px", maxWidth: 1280, margin: "0 auto" },

  loadingBox: { padding: 40, textAlign: "center", fontSize: 14, color: MUTED },
  errorBox: { marginBottom: 14, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 14px", fontSize: 14, fontWeight: 600 },
  toast: { marginBottom: 14, borderRadius: 10, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", padding: "12px 16px", fontSize: 14, fontWeight: 700, animation: "toastIn .3s ease" },
  toastError: { marginBottom: 14, borderRadius: 10, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 16px", fontSize: 14, fontWeight: 700, animation: "toastIn .3s ease" },

  header: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 16, flexWrap: "wrap" },
  title: { margin: 0, fontSize: 20, fontWeight: 800, color: NAVY },
  subtitle: { margin: "4px 0 0", fontSize: 13, color: MUTED },
  headerRight: { display: "flex", gap: 8 },
  toolbar: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16, flexWrap: "wrap", padding: "12px 16px", background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 18, boxShadow: "0 8px 26px rgba(15,23,42,.05)" },
  toolbarLeft: { display: "flex", alignItems: "center", gap: 10 },
  toolbarRight: { display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" },
  stats: { fontSize: 12, color: MUTED, fontWeight: 600 },
  viewSwitch: { display: "flex", borderRadius: 12, border: `1px solid ${BORDER}`, overflow: "hidden", background: "#f8fafc" },
  viewBtn: { padding: "8px 18px", border: "none", background: "transparent", color: MUTED, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  viewBtnActive: { padding: "8px 18px", border: "none", background: "#009CA4", color: "#fff", fontSize: 12, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  legendRow: { marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 8 },
  legendItem: { display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid", borderRadius: 999, padding: "4px 10px" },
  legendDot: { width: 8, height: 8, borderRadius: "50%" },
  legendText: { fontSize: 11, fontWeight: 700 },
  kpiRow: { marginBottom: 16, display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12 },
  kpiCard: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 18, padding: "16px 18px", minHeight: 90, display: "flex", alignItems: "center", gap: 12, boxShadow: "0 8px 20px rgba(15,23,42,.04)" },
  kpiDot: { width: 30, height: 30, borderRadius: 10, display: "grid", placeItems: "center", fontSize: 10, fontWeight: 900 },
  kpiValue: { fontSize: 36, lineHeight: 1, fontWeight: 900, color: NAVY, letterSpacing: "-.045em" },
  kpiLabel: { fontSize: 13, color: "#475569", fontWeight: 700, marginTop: 4 },

  navBar: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 },
  navBtn: { width: 36, height: 36, borderRadius: 10, border: `1px solid ${BORDER}`, background: "#fff", color: NAVY, fontSize: 18, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" },
  navCenter: { display: "flex", alignItems: "center", gap: 10, flex: 1 },
  navDate: { fontSize: 18, fontWeight: 900, color: NAVY, letterSpacing: "-.02em" },
  todayBtn: { padding: "6px 12px", borderRadius: 10, border: `1px solid ${BORDER}`, background: "#fff", color: "#009CA4", fontSize: 11, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },

  calendarCol: { flex: 1, minWidth: 0 },
  card: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 22, overflow: "hidden", boxShadow: "0 16px 40px rgba(15,23,42,.06)" },
  monthLayout: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) 368px", gap: 16, alignItems: "start" },
  monthSide: { display: "flex", flexDirection: "column", gap: 12 },

  // ── Day view ──
  dayLayout: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) 368px", gap: 16, alignItems: "start" },
  daySide: { display: "flex", flexDirection: "column", gap: 12 },
  dayTimeline: { display: "flex", flexDirection: "column" },
  dayRow: { display: "grid", gridTemplateColumns: "72px 1fr", minHeight: 72, borderBottom: "1px solid #f1f5f9" },
  dayRowNow: { background: "#f8fbff" },
  dayHour: { padding: "13px 8px", fontSize: 12, fontWeight: 800, color: "#64748b", borderRight: "1px solid #f1f5f9", display: "flex", alignItems: "flex-start", justifyContent: "center" },
  daySlots: { padding: "7px 12px", display: "flex", flexDirection: "column", gap: 7 },
  dayEmpty: { minHeight: 20 },
  dayCard: { width: "100%", textAlign: "left", border: "1px solid #e2e8f0", borderLeft: "4px solid", borderRadius: 14, background: "#FCFEFF", padding: "11px 13px", cursor: "pointer", fontFamily: "inherit", boxShadow: "0 4px 14px rgba(15,23,42,.05)" },
  dayCardTop: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 },
  dayCardTime: { fontSize: 12, fontWeight: 800, color: "#007C84" },
  dayCardName: { fontSize: 14, fontWeight: 700, color: NAVY, marginTop: 4 },
  dayCardType: { fontSize: 12, color: "#475569", marginTop: 2 },
  dayTag: { fontSize: 9, fontWeight: 800, letterSpacing: ".04em", textTransform: "uppercase", border: "1px solid", borderRadius: 999, padding: "2px 6px", background: "rgba(255,255,255,.75)" },
  aiBadge: { padding: "2px 6px", borderRadius: 999, background: "#ede9fe", color: "#7c3aed", fontSize: 9, fontWeight: 900, letterSpacing: "0.05em" },
  emptyDay: { padding: "40px 20px", textAlign: "center" },

  // ── Week view ──
  weekScroll: { overflowX: "auto" },
  weekHead: { borderBottom: `1px solid ${BORDER}`, padding: "14px 18px 12px", background: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" },
  weekHeadTitle: { fontSize: 38, lineHeight: 1, fontWeight: 900, color: NAVY, letterSpacing: "-.038em" },
  weekHeadSub: { fontSize: 13, color: "#64748b", marginTop: 5, fontWeight: 500 },
  weekHeadBadges: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  weekHeadBadgeRed: { fontSize: 11, fontWeight: 900, color: "#991B1B", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 999, padding: "4px 9px", letterSpacing: ".01em" },
  weekHeadBadgeOrange: { fontSize: 11, fontWeight: 900, color: "#9A3412", background: "#FFF7ED", border: "1px solid #FED7AA", borderRadius: 999, padding: "4px 9px", letterSpacing: ".01em" },
  weekHeadBadgePurple: { fontSize: 11, fontWeight: 900, color: "#5B21B6", background: "#F5F3FF", border: "1px solid #DDD6FE", borderRadius: 999, padding: "4px 9px", letterSpacing: ".01em" },
  weekGrid: { display: "grid", minWidth: 980, borderTop: `1px solid ${BORDER}`, borderLeft: `1px solid ${BORDER}` },
  weekLayout: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) 368px", gap: 16, alignItems: "start" },
  weekSide: { display: "flex", flexDirection: "column", gap: 12 },
  sideCardPrimary: { border: "1px solid #0c4a6e22", borderRadius: 20, background: "linear-gradient(180deg, #052D3E 0%, #0A4A5E 60%, #0B5A67 100%)", color: "#fff", padding: 16, boxShadow: "0 14px 34px rgba(2, 44, 54, .32)" },
  sideHeadLabel: { fontSize: 12, fontWeight: 800, opacity: 0.85, letterSpacing: ".01em" },
  sideHeadTitle: { fontSize: 42, lineHeight: 1, fontWeight: 900, marginTop: 4, letterSpacing: "-.04em" },
  sideHeadSub: { fontSize: 13, opacity: 0.85, marginTop: 5, marginBottom: 13, lineHeight: 1.35 },
  sideList: { display: "flex", flexDirection: "column", gap: 8 },
  sideRow: { background: "rgba(255,255,255,.95)", borderRadius: 12, border: "1px solid #e2e8f0", padding: "11px 10px", display: "flex", gap: 8, alignItems: "flex-start", color: NAVY },
  sideDot: { width: 8, height: 8, borderRadius: "50%", marginTop: 6, flexShrink: 0 },
  sideRowTitle: { fontSize: 14, fontWeight: 900, color: NAVY, letterSpacing: "-.01em" },
  sideRowSub: { fontSize: 11, color: "#334155", marginTop: 2, lineHeight: 1.45, fontWeight: 500 },
  sideCard: { border: `1px solid ${BORDER}`, borderRadius: 18, background: "#fff", padding: 16, boxShadow: "0 10px 28px rgba(15,23,42,.07)" },
  sideCardTitle: { fontSize: 36, lineHeight: 1, fontWeight: 900, color: NAVY, marginBottom: 12, letterSpacing: "-.035em" },
  loadList: { display: "flex", flexDirection: "column", gap: 10 },
  loadRowHead: { display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 4 },
  loadTrack: { width: "100%", height: 8, borderRadius: 999, background: "#e2e8f0", overflow: "hidden" },
  loadFill: { height: "100%", borderRadius: 999, background: "#0ea5a6" },
  weekCorner: { borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, background: "#f8fafc", minHeight: 52 },
  weekDayHeader: { borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, background: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "12px 6px", cursor: "pointer", border: "none", fontFamily: "inherit", borderRightStyle: "solid", borderRightWidth: 1, borderRightColor: BORDER, borderBottomStyle: "solid", borderBottomWidth: 1, borderBottomColor: BORDER },
  weekDayToday: { background: "#E8F7F7" },
  weekDaySelected: { background: "#f0fdf4" },
  weekDayLabel: { fontSize: 10, fontWeight: 800, color: MUTED, letterSpacing: "0.07em" },
  weekDayNum: { fontSize: 28, fontWeight: 900, color: NAVY, lineHeight: 1, letterSpacing: "-.02em" },
  todayDot: { width: 5, height: 5, borderRadius: "50%", background: BLUE, marginTop: 2 },
  weekTimeCell: { borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, padding: "10px 4px", display: "flex", alignItems: "flex-start", justifyContent: "center", background: "#f8fafc", minHeight: 82 },
  weekTimeLabel: { fontSize: 10, fontWeight: 800, color: "#94a3b8", letterSpacing: ".02em" },
  weekCell: { borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, padding: 7, background: "#fff", display: "flex", flexDirection: "column", gap: 5, minHeight: 82 },
  weekCellAlt: { background: "#fcfdff" },
  weekChip: { width: "100%", textAlign: "left", border: "none", borderLeft: "3px solid", borderRadius: 12, background: "#f8fafc", padding: "7px 8px", cursor: "pointer", fontFamily: "inherit", boxShadow: "0 1px 0 rgba(15,23,42,.03)" },
  chipTop: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, marginBottom: 2 },
  chipTime: { fontSize: 11, fontWeight: 800, color: "#0f766e", display: "block", letterSpacing: ".01em" },
  chipTag: { fontSize: 9, fontWeight: 900, letterSpacing: ".05em", textTransform: "uppercase", background: "rgba(255,255,255,.8)", borderRadius: 999, padding: "1px 5px" },
  chipName: { fontSize: 12, fontWeight: 700, color: NAVY, display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", letterSpacing: "-.01em" },

  topDetailWrap: { borderBottom: `1px solid ${BORDER}`, padding: "0", background: "#f8fbfc" },
  topDetailHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 16px 0",
  },
  weekDetailClose: {
    width: 28,
    height: 28,
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: MUTED,
    fontSize: 13,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "inherit",
    flexShrink: 0,
  },

  // ── Month view ──
  monthGridWrap: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: 0,
  },
  monthWdHeader: {
    padding: "12px 4px",
    textAlign: "center",
    fontSize: 11,
    fontWeight: 800,
    color: MUTED,
    letterSpacing: "0.04em",
    borderBottom: `1px solid ${BORDER}`,
    background: "#f8fafc",
  },
  monthCell: {
    minHeight: 128,
    padding: "6px",
    borderBottom: `1px solid #f3f4f6`,
    borderRight: `1px solid #f3f4f6`,
    background: "#fff",
    fontFamily: "inherit",
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  monthCellToday: { background: "#E8F7F7" },
  monthCellAlt: { background: "#FCFDFF" },
  monthDayNumBtn: {
    border: "none",
    background: "transparent",
    fontSize: 13,
    fontWeight: 700,
    color: NAVY,
    width: 26,
    height: 26,
    borderRadius: "50%",
    cursor: "pointer",
    fontFamily: "inherit",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
    alignSelf: "flex-start",
  },
  monthDayNumToday: {
    background: BLUE,
    color: "#fff",
  },
  monthApptList: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    flex: 1,
    overflow: "hidden",
  },
  monthApptPill: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "4px 7px",
    borderRadius: 8,
    border: "none",
    borderLeft: "3px solid",
    background: "#f8fafc",
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left",
    width: "100%",
    overflow: "hidden",
  },
  monthApptTime: { fontSize: 10, fontWeight: 800, color: "#007C84", flexShrink: 0 },
  monthApptName: {
    fontSize: 10,
    fontWeight: 600,
    color: NAVY,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  monthOverflow: {
    border: "none",
    background: "transparent",
    color: BLUE,
    fontSize: 10,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    padding: "2px 4px",
    textAlign: "left",
  },

  // ── Inline detail panel ──
  inlineDetail: {
    background: "#fff",
    border: `1px solid ${BORDER}`,
    borderTop: "none",
    borderRadius: "0 0 12px 12px",
    padding: "14px 16px 16px",
    marginBottom: 6,
    boxShadow: "0 4px 16px rgba(15,23,42,.07)",
  },
  inlineGrid: {
    display: "flex",
    flexWrap: "wrap",
    gap: 10,
    marginBottom: 12,
  },
  inlineItem: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 13,
    color: MUTED,
    fontWeight: 500,
  },
  inlineIcon: {
    fontSize: 14,
  },
  inlineActions: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  inlineCallBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    border: "none",
    background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`,
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    textDecoration: "none",
  },
  inlineSecBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: NAVY,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  inlineDangerBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid #fecaca",
    background: "#fff",
    color: "#dc2626",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  inlineConfirm: {
    marginTop: 10,
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 10,
    padding: 12,
  },
  inlineConfirmText: {
    margin: "0 0 10px",
    fontSize: 13,
    color: "#7f1d1d",
    lineHeight: 1.5,
  },
  confirmCancelBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "none",
    background: "#dc2626",
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  confirmBackBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: MUTED,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  inlineRescheduleBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid #bfdbfe",
    background: "#fff",
    color: "#2563eb",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  reschedulePanel: {
    marginTop: 10,
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    padding: "14px 16px",
  },
  reschedulePanelHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  reschedulePanelTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  rescheduleCloseBtn: {
    width: 28,
    height: 28,
    borderRadius: 6,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: MUTED,
    fontSize: 13,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "inherit",
  },
  reschedulePanelEmpty: {
    fontSize: 13,
    color: MUTED,
    textAlign: "center",
    padding: "16px 0",
  },
  calNav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  calNavBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    fontSize: 18,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "inherit",
    color: NAVY,
  },
  calNavLabel: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  calGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: 2,
  },
  calDow: {
    textAlign: "center",
    fontSize: 11,
    fontWeight: 700,
    color: MUTED,
    padding: "4px 0",
  },
  calCell: {
    textAlign: "center",
    padding: "6px 2px",
    borderRadius: 8,
    fontSize: 13,
    minHeight: 36,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  calCellToday: {
    fontWeight: 800,
    color: BLUE,
  },
  calCellAvail: {
    background: "#f0fdf4",
    color: NAVY,
    fontWeight: 600,
    border: "1px solid #bbf7d0",
  },
  calCellDisabled: {
    color: "#d1d5db",
    background: "transparent",
    border: "1px solid transparent",
  },
  calCellDot: {
    fontSize: 9,
    color: TEAL,
    fontWeight: 700,
    lineHeight: 1,
  },
  calBackBtn: {
    background: "none",
    border: "none",
    color: BLUE,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    padding: "0 0 10px",
    fontFamily: "inherit",
  },
  slotTimeRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 6,
  },
  slotTimeBtn: {
    padding: "8px 16px",
    borderRadius: 8,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: NAVY,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "background .1s, border-color .1s",
  },
  rescheduleConfirm: {
    background: "#fff",
    border: "1px solid #bfdbfe",
    borderRadius: 10,
    padding: 14,
  },
  rescheduleConfirmText: {
    margin: "0 0 12px",
    fontSize: 14,
    color: NAVY,
    lineHeight: 1.5,
  },
  rescheduleConfirmBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "none",
    background: "#2563eb",
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
};

const CSS = `
  .agenda-appt-card { transition: transform .08s ease, box-shadow .08s ease; }
  .agenda-appt-card:hover { transform: translateY(-1px); box-shadow: 0 10px 26px rgba(15,23,42,.1) !important; }
  .agenda-appt-chip { transition: background .08s ease, box-shadow .08s ease; }
  .agenda-appt-chip:hover { box-shadow: 0 0 0 1px rgba(148,163,184,.45) inset !important; }
  .month-day-cell { transition: background .08s ease; }
  .month-day-cell:hover { background: #f0f9ff !important; }
  .month-appt-pill { transition: background .08s ease, box-shadow .08s ease; }
  .month-appt-pill:hover { box-shadow: 0 0 0 1px rgba(148,163,184,.45) inset !important; }
  .slot-time-btn:hover { background: #eff6ff !important; border-color: #93c5fd !important; }
  .cal-day-avail:hover { background: #dcfce7 !important; border-color: #86efac !important; }
  @media (max-width: 768px) {
    .agenda-week-grid { min-width: 600px !important; }
    .agenda-week-layout { grid-template-columns: 1fr !important; }
    .agenda-month-layout { grid-template-columns: 1fr !important; }
    .agenda-day-layout { grid-template-columns: 1fr !important; }
    .agenda-kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
  }
  @media (max-width: 1100px) {
    .agenda-week-layout { grid-template-columns: 1fr !important; }
    .agenda-month-layout { grid-template-columns: 1fr !important; }
    .agenda-day-layout { grid-template-columns: 1fr !important; }
  }
  @keyframes toastIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .agenda-appt-card, .agenda-appt-chip, .month-day-cell { animation: none !important; transition: none !important; }
  }
`;
