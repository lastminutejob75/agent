import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams, useOutletContext } from "react-router-dom";
import CreatePatientFromCallModal from "../components/calls/CreatePatientFromCallModal.jsx";
import AppAgendaMiniCalendar from "../components/AppAgendaMiniCalendar.jsx";
import PatientDuplicateBanner from "../components/patients/PatientDuplicateBanner.jsx";
import {
  validatePatientPhone,
  validateContactEmail,
  validatePatientBirthDate,
  validateRequiredText,
  isValidContactEmail,
} from "../lib/contactValidation.js";
import {
  checkPatientDuplicates,
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  parsePatientDuplicateError,
} from "../lib/patientDuplicateCheck.js";
import { bookingOriginLabel } from "../lib/agendaPatientMeta.js";
import {
  agendaCancelPayload,
  agendaReschedulePayload,
  appointmentGoogleEventId,
  appointmentLocalId,
  canCancelAgendaSlot,
  canRescheduleAgendaSlot,
} from "../lib/agendaAppointmentActions.js";
import { normalizeFrenchPhone } from "../lib/transferConfig.js";
import { api, isTenantUnauthorized } from "../lib/api.js";

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

function isSameAgendaSlotForCancel(slot, appt, date, index) {
  const targetAppointmentId = String(appt?.appointment_id || "");
  const targetEventId = String(appt?.event_id || "");
  const targetActionId = String(appt?.actionId || "");
  const targetSyntheticId = String(appt?.id || "");

  const slotAppointmentId = String(slot?.appointment_id || "");
  const slotEventId = String(slot?.event_id || "");
  const slotActionId = String(slot?.appointment_id || slot?.event_id || "");
  const slotSyntheticId = `${date}-${slot?.event_id || slot?.appointment_id || index}`;

  if (targetAppointmentId && slotAppointmentId === targetAppointmentId) return true;
  if (targetEventId && slotEventId === targetEventId) return true;
  if (targetActionId && slotActionId === targetActionId) return true;
  return Boolean(targetSyntheticId && slotSyntheticId === targetSyntheticId);
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
  if (/^\d{1,2}h\d{2}$/.test(v)) {
    const m = v.match(/^(\d{1,2})h(\d{2})$/);
    if (m) return `${m[1].padStart(2, "0")}:${m[2]}`;
  }
  if (/^\d{1,2}h$/.test(v)) return `${v.replace("h", "").padStart(2, "0")}:00`;
  return v.replace("h", ":");
}

/** Clé grille horaire : un RDV à 09h15 s'affiche sur la ligne 09:00. */
function agendaGridHourKey(displayTime) {
  const normalized = formatTimeLabel(displayTime);
  const match = normalized.match(/^(\d{2}):(\d{2})$/);
  if (!match) return normalized;
  return `${match[1]}:00`;
}

function agendaSlotMergeKey(slot) {
  return String(
    slot?.event_id || slot?.public_booking_id || slot?.appointment_id || `${slot?.start_iso || ""}|${slot?.patient || ""}`,
  );
}

function mergeAgendaDayPayload(existing, incoming) {
  if (!incoming) return existing;
  const prevSlots = existing?.slots || [];
  const nextSlots = incoming?.slots || [];
  if (!nextSlots.length) return prevSlots.length ? existing : incoming;
  const map = new Map();
  prevSlots.forEach((s) => map.set(agendaSlotMergeKey(s), s));
  nextSlots.forEach((s) => map.set(agendaSlotMergeKey(s), s));
  return { ...incoming, date: incoming.date || existing?.date, slots: [...map.values()] };
}

function mergeAgendaBulkIntoState(prev, dates, bulkRes) {
  if (!bulkRes?.dates) return prev;
  const next = { ...(prev || {}) };
  (dates || []).forEach((d) => {
    const incoming = bulkRes.dates[d] || { slots: [], date: d };
    next[d] = mergeAgendaDayPayload(next[d], incoming);
  });
  return next;
}

function addMinutes(timeLabel, mins) {
  const m = String(timeLabel || "").match(/^(\d{2}):(\d{2})$/);
  if (!m) return "—";
  const total = Number(m[1]) * 60 + Number(m[2]) + Number(mins || 0);
  const norm = ((total % 1440) + 1440) % 1440;
  return `${String(Math.floor(norm / 60)).padStart(2, "0")}:${String(norm % 60).padStart(2, "0")}`;
}

/** Affichage local type « 9h30 » dans le sélecteur d’heure. */
function formatTimeChoiceFR(value) {
  const raw = String(value || "").trim();
  const [hRaw, mRaw] = raw.split(":").concat("0");
  const hh = Number.parseInt(String(hRaw), 10);
  const mm = Number.parseInt(String(mRaw), 10);
  if (Number.isNaN(hh) || Number.isNaN(mm)) return raw;
  return `${hh}h${String(mm).padStart(2, "0")}`;
}

/** Créneaux entre deux heures d’ouverture (cabinet), pas configurables en minute arbitraire. */
function buildCabinetTimeChoices(loH, hiH, stepMinutes = 15) {
  let step = Math.round(Number(stepMinutes));
  if (!Number.isFinite(step) || step < 5 || step > 60) step = 15;
  let lo = Math.floor(Number(loH));
  if (!Number.isFinite(lo)) lo = 8;
  lo = Math.max(6, Math.min(22, lo));
  let hi = Math.floor(Number(hiH));
  if (!Number.isFinite(hi)) hi = 19;
  hi = Math.max(lo, Math.min(22, hi));

  const out = [];
  const lastMinute = hi * 60 + 45;
  for (let total = lo * 60; total <= lastMinute; total += step) {
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h > hi) break;
    if (h === hi && m > 45) continue;
    out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  }
  return out.length ? out : ["09:00", "10:00", "11:00", "14:00", "15:00"];
}

function pickDefaultCabinetTime(slots, preferredHour = 9) {
  if (!slots?.length) return "09:00";
  const want = `${String(preferredHour).padStart(2, "0")}:00`;
  if (slots.includes(want)) return want;
  const after = slots.find((s) => s >= want);
  return after || slots[0];
}

/** ISO local (heure murale) pour l'API agenda — évite le décalage UTC sur les créneaux. */
function buildCabinetBookingStartIso(bookingDate, bookingTime) {
  const date = String(bookingDate || "").trim();
  const time = String(bookingTime || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return "";
  return `${date}T${time}:00`;
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

function isAgendaCancelledSlot(slot) {
  const text = `${slot?.status || ""} ${slot?.booking_status || ""}`.toLowerCase();
  return text.includes("cancel") || text.includes("annul");
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

const WEEKDAY_LABELS = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"];

/** Stale-while-revalidate : affichage immédiat au retour sur l’agenda (session). */
const AGENDA_BULK_CACHE_PREFIX = "uwi_agenda_bulk_v4:";
const AGENDA_BULK_CACHE_MS = 120000;
const AGENDA_GOOGLE_ENRICH_COOLDOWN_MS = 45000;
const AGENDA_HORAIRES_REFRESH_MS = 120000;

function agendaBulkStorageKey(dates) {
  return AGENDA_BULK_CACHE_PREFIX + (dates || []).join(",");
}

function agendaDatesKey(dates) {
  return [...new Set((dates || []).filter(Boolean))].sort().join(",");
}

function countBulkSlots(bulkRes, dates) {
  return (dates || []).reduce(
    (sum, d) => sum + ((bulkRes?.dates?.[d]?.slots || []).length),
    0,
  );
}

function readAgendaBulkStale(dates) {
  if (typeof sessionStorage === "undefined" || !dates?.length) return null;
  try {
    const raw = sessionStorage.getItem(agendaBulkStorageKey(dates));
    if (!raw) return null;
    const rec = JSON.parse(raw);
    if (!rec || typeof rec.ts !== "number" || !rec.payload?.dates) return null;
    if (Date.now() - rec.ts > AGENDA_BULK_CACHE_MS) {
      sessionStorage.removeItem(agendaBulkStorageKey(dates));
      return null;
    }
    if (countBulkSlots(rec.payload, dates) === 0) {
      sessionStorage.removeItem(agendaBulkStorageKey(dates));
      return null;
    }
    return rec.payload;
  } catch {
    return null;
  }
}

function writeAgendaBulkStale(dates, bulkRes) {
  if (typeof sessionStorage === "undefined" || !dates?.length || !bulkRes?.dates) return;
  if (countBulkSlots(bulkRes, dates) === 0) return;
  try {
    sessionStorage.setItem(
      agendaBulkStorageKey(dates),
      JSON.stringify({ ts: Date.now(), payload: bulkRes }),
    );
  } catch {
    // quota / mode privé
  }
}

/** Après mutation (annulation, déplacement…), éviter d’afficher un mois figé ~35 s. */
function invalidateAgendaBulkCache() {
  if (typeof sessionStorage === "undefined") return;
  try {
    const toRemove = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith(AGENDA_BULK_CACHE_PREFIX)) toRemove.push(k);
    }
    toRemove.forEach((k) => sessionStorage.removeItem(k));
  } catch {
    /* ignore */
  }
}

function normalizePhone(raw) {
  return normalizeFrenchPhone(raw);
}

/** Téléphone facultatif (création RDV cabinet) ; si renseigné → format E.164 strict. */
function validateCabinetBookingPhone(raw) {
  return validatePatientPhone(raw);
}

/** E-mail facultatif ; si renseigné → format contact strict. */
function isCabinetBookingEmailValid(raw) {
  return isValidContactEmail(raw);
}

/** Une fiche est considérée "créée" pour l'agenda quand l'identité est validée (`validated_name` >= 2). */
function dashboardPatientHasValidatedIdentity(profile) {
  if (!profile || typeof profile !== "object") return false;
  return String(profile.validated_name || "").trim().length >= 2;
}

function agendaAppointmentHasValidatedIdentity(appt) {
  if (!appt || typeof appt !== "object") return false;
  if (typeof appt.patient_identity_validated === "boolean") {
    return appt.patient_identity_validated;
  }
  return dashboardPatientHasValidatedIdentity(appt.patient || appt);
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

  const [datesError, setDatesError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoadingDates(true);
    setDatesError("");
    api.tenantGetAgendaAvailableDates(calMonth).then((res) => {
      if (!cancelled) setAvailDates(res?.dates || {});
    }).catch((e) => {
      if (!cancelled) {
        setAvailDates({});
        setDatesError(e?.message || "Impossible de charger les disponibilités.");
      }
    }).finally(() => { if (!cancelled) setLoadingDates(false); });
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
          {!loadingDates && !Object.values(availDates).some((n) => Number(n) > 0) ? (
            <div style={S.reschedulePanelEmpty}>
              {datesError
                ? datesError
                : `Aucune disponibilité en ${monthLabel.toLowerCase()}.`}
              <div style={{ marginTop: 8 }}>
                <button type="button" onClick={nextMonth} style={S.calBackBtn}>
                  Voir le mois suivant ›
                </button>
              </div>
            </div>
          ) : null}
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
  onViewPatientFile,
  onCreatePatientFile,
  onCreateConsultation,
  variant = "inline",
}) {
  const aPhone = normalizePhone(a.patient_phone || a.phone || "");
  const aPhoneFmt = formatPhone(aPhone);
  const hasPatientFile = agendaAppointmentHasValidatedIdentity(a);
  const shellStyle = variant === "modal" ? S.inlineDetailModal : S.inlineDetail;
  return (
    <div style={shellStyle}>
      <div style={S.inlineGrid}>
        <div style={S.inlineItem}><span style={S.inlineIcon}>🕐</span><span>{a.displayTime} – {a.endTime}</span></div>
        <div style={S.inlineItem}><span style={S.inlineIcon}>📅</span><span>{formatLongDate(a.date)}</span></div>
        <div style={S.inlineItem}><span style={S.inlineIcon}>📍</span><span>Origine du RDV : {bookingOriginLabel(a.booking_origin)}</span></div>
        <div style={S.inlineItem}><span style={S.inlineIcon}>{a.isUWI ? "🤖" : "📆"}</span><span>{a.isUWI ? "Via assistant IA" : "Agenda externe"}</span></div>
        {aPhoneFmt && <div style={S.inlineItem}><span style={S.inlineIcon}>📞</span><span>{aPhoneFmt}</span></div>}
      </div>
      <div style={S.inlineActions}>
        {aPhone ? <a href={`tel:${aPhone}`} style={S.inlineCallBtn}>📞 Appeler</a> : null}
        {aPhone && hasPatientFile ? (
          <button
            type="button"
            onClick={() => onViewPatientFile?.()}
            style={S.inlineSecBtn}
          >
            👤 Consulter la fiche patient
          </button>
        ) : null}
        {aPhone && !hasPatientFile ? (
          <button
            type="button"
            onClick={() => onCreatePatientFile?.()}
            style={S.inlineSecBtn}
          >
            👤 Créer la fiche patient
          </button>
        ) : null}
        {aPhone ? (
          <button
            type="button"
            onClick={() => onCreateConsultation?.()}
            style={S.inlineSecBtn}
          >
            🩺 Créer fiche consultation
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
        {a.canReschedule && !confirmCancel && !rescheduleMode && (
          <button type="button" onClick={onStartReschedule} style={S.inlineRescheduleBtn}>🔄 Déplacer RDV</button>
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

function sortApptsByTime(appts) {
  return [...appts].sort((a, b) => String(a.displayTime || "").localeCompare(String(b.displayTime || "")));
}

function AgendaWeekMobileList({
  weekDates,
  appointments,
  today,
  selectedDate,
  onSelectDay,
  onOpenDayView,
  onToggleAppt,
  selectedAppt,
  semanticCounts,
  styles: S,
}) {
  const dayApptsByDate = useMemo(() => {
    const map = {};
    weekDates.forEach((d) => {
      map[d] = sortApptsByTime(appointments.filter((a) => a.date === d));
    });
    return map;
  }, [weekDates, appointments]);

  return (
    <div className="agenda-week-mobile">
      <div className="agenda-week-mobile-strip" style={S.weekMobileStrip}>
        {weekDates.map((d) => {
          const { wd, num } = formatShortDay(d);
          const isToday = d === today;
          const isSelected = d === selectedDate;
          const count = dayApptsByDate[d]?.length || 0;
          return (
            <button
              key={d}
              type="button"
              onClick={() => onSelectDay(d)}
              style={{
                ...S.weekMobileDayChip,
                ...(isToday ? S.weekMobileDayChipToday : {}),
                ...(isSelected ? S.weekMobileDayChipSelected : {}),
              }}
            >
              <span style={S.weekMobileDayChipWd}>{wd}</span>
              <span style={S.weekMobileDayChipNum}>{num}</span>
              {count > 0 ? <span style={S.weekMobileDayChipCount}>{count}</span> : null}
            </button>
          );
        })}
      </div>

      <div style={S.weekMobileBadges}>
        <span style={S.weekHeadBadgeRed}>Prioritaire {semanticCounts.red}</span>
        <span style={S.weekHeadBadgeOrange}>À confirmer {semanticCounts.orange}</span>
        <span style={S.weekHeadBadgePurple}>Récupéré {semanticCounts.purple}</span>
      </div>

      {weekDates.map((d) => {
        const dayAppts = dayApptsByDate[d] || [];
        const { wd, num } = formatShortDay(d);
        const isToday = d === today;
        const isSelected = d === selectedDate;
        return (
          <section
            key={d}
            id={`agenda-week-day-${d}`}
            style={{
              ...S.weekMobileDaySection,
              ...(isSelected ? S.weekMobileDaySectionSelected : {}),
            }}
          >
            <div style={S.weekMobileDayHeader}>
              <button type="button" onClick={() => onSelectDay(d)} style={S.weekMobileDayHeaderMain}>
                <div style={S.weekMobileDayTitle}>
                  {wd} {num}
                  {isToday ? <span style={S.weekMobileTodayBadge}>Aujourd&apos;hui</span> : null}
                </div>
                <div style={S.weekMobileDaySub}>{formatLongDate(d)}</div>
              </button>
              <div style={S.weekMobileDayMeta}>
                <span>{dayAppts.length} RDV</span>
                <button type="button" onClick={() => onOpenDayView(d)} style={S.weekMobileOpenDayBtn}>
                  Jour ›
                </button>
              </div>
            </div>
            {dayAppts.length === 0 ? (
              <div style={S.weekMobileEmpty}>Aucun rendez-vous</div>
            ) : (
              <div style={S.weekMobileApptList}>
                {dayAppts.map((a) => {
                  const tone = APPT_TONE[toneForAppointment(a)] || APPT_TONE.teal;
                  const isOpen = selectedAppt?.id === a.id;
                  return (
                    <button
                      key={a.id}
                      type="button"
                      className="agenda-appt-chip"
                      onClick={() => onToggleAppt(a)}
                      style={{
                        ...S.weekMobileApptCard,
                        background: tone.bg,
                        borderLeftColor: tone.border,
                        ...(isOpen ? { boxShadow: `0 0 0 2px ${tone.border}40` } : {}),
                      }}
                    >
                      <div style={S.weekMobileApptTop}>
                        <span style={{ ...S.weekMobileApptTime, color: tone.time }}>{a.displayTime}</span>
                        <span style={{ ...S.weekMobileApptTag, color: tone.time }}>{semanticLabelForAppointment(a)}</span>
                      </div>
                      <div style={{ ...S.weekMobileApptName, color: tone.text }}>{a.patient || "Patient"}</div>
                      <div style={S.weekMobileApptType}>{a.typeIcon} {a.type || "Consultation"}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function AgendaMonthMobileView({
  monthGrid,
  currentMonth,
  appointmentsByDate,
  selectedDate,
  today,
  onSelectDate,
  onOpenDayView,
  onToggleAppt,
  selectedAppt,
  monthCounts,
  styles: S,
}) {
  const selectedDayAppts = appointmentsByDate[selectedDate] || [];

  return (
    <div className="agenda-month-mobile">
      <div style={S.monthMobileSummary}>
        <div style={S.monthMobileSummaryItem}>
          <strong>{monthCounts.total}</strong>
          <span>RDV</span>
        </div>
        <div style={S.monthMobileSummaryItem}>
          <strong>{monthCounts.pending}</strong>
          <span>à confirmer</span>
        </div>
        <div style={S.monthMobileSummaryItem}>
          <strong>{monthCounts.recovered}</strong>
          <span>récupérés</span>
        </div>
      </div>

      <div style={S.monthMobileGrid}>
        {WEEKDAY_LABELS.map((wd) => (
          <div key={wd} style={S.monthMobileWd}>{wd.charAt(0)}</div>
        ))}
        {monthGrid.map((d) => {
          const isCurrentMonth = getMonthFromDate(d) === currentMonth;
          const isToday = d === today;
          const isSelected = d === selectedDate;
          const dayNum = new Date(`${d}T12:00:00`).getDate();
          const dayAppts = appointmentsByDate[d] || [];
          const toneDots = dayAppts.slice(0, 3).map((a) => a.tone || toneForAppointment(a));
          return (
            <button
              key={d}
              type="button"
              onClick={() => onSelectDate(d)}
              style={{
                ...S.monthMobileCell,
                opacity: isCurrentMonth ? 1 : 0.35,
                ...(isToday ? S.monthMobileCellToday : {}),
                ...(isSelected ? S.monthMobileCellSelected : {}),
              }}
            >
              <span style={{ ...S.monthMobileCellNum, ...(isToday && isSelected ? S.monthDayNumToday : {}) }}>
                {dayNum}
              </span>
              {dayAppts.length > 0 ? (
                <div style={S.monthMobileDots}>
                  {toneDots.map((toneKey, idx) => {
                    const tone = APPT_TONE[toneKey] || APPT_TONE.teal;
                    return <span key={`${d}-dot-${idx}`} style={{ ...S.monthMobileDot, background: tone.border }} />;
                  })}
                  {dayAppts.length > 3 ? <span style={S.monthMobileDotMore}>+</span> : null}
                </div>
              ) : null}
            </button>
          );
        })}
      </div>

      <div style={S.monthMobileDayPanel}>
        <div style={S.monthMobileDayPanelHead}>
          <div>
            <div style={S.monthMobileDayPanelTitle}>{formatLongDate(selectedDate)}</div>
            <div style={S.monthMobileDayPanelSub}>{selectedDayAppts.length} rendez-vous</div>
          </div>
          <button type="button" onClick={() => onOpenDayView(selectedDate)} style={S.weekMobileOpenDayBtn}>
            Vue jour ›
          </button>
        </div>
        {selectedDayAppts.length === 0 ? (
          <div style={S.weekMobileEmpty}>Aucun rendez-vous ce jour.</div>
        ) : (
          <div style={S.weekMobileApptList}>
            {selectedDayAppts.map((a) => {
              const tone = APPT_TONE[toneForAppointment(a)] || APPT_TONE.teal;
              const isOpen = selectedAppt?.id === a.id;
              return (
                <button
                  key={a.id}
                  type="button"
                  className="agenda-appt-chip"
                  onClick={() => onToggleAppt(a)}
                  style={{
                    ...S.weekMobileApptCard,
                    background: tone.bg,
                    borderLeftColor: tone.border,
                    ...(isOpen ? { boxShadow: `0 0 0 2px ${tone.border}40` } : {}),
                  }}
                >
                  <div style={S.weekMobileApptTop}>
                    <span style={{ ...S.weekMobileApptTime, color: tone.time }}>{a.displayTime}</span>
                    <span style={{ ...S.weekMobileApptTag, color: tone.time }}>{semanticLabelForAppointment(a)}</span>
                  </div>
                  <div style={{ ...S.weekMobileApptName, color: tone.text }}>{a.patient || "Patient"}</div>
                  <div style={S.weekMobileApptType}>{a.typeIcon} {a.type || "Consultation"}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function AgendaDateNavPanel({
  selectedDate,
  viewMode,
  apptCountByDate,
  onSelectDate,
  onViewMode,
  onGoToday,
  onShift,
  styles: panelStyles,
}) {
  const navHint = viewMode === "month"
    ? "Mois précédent / suivant"
    : viewMode === "week"
      ? "Semaine précédente / suivante"
      : "Jour précédent / suivant";
  return (
    <div style={panelStyles.dateNavPanel}>
      <AppAgendaMiniCalendar
        selectedDate={selectedDate}
        onSelect={onSelectDate}
        apptCountByDate={apptCountByDate}
      />
      <label style={panelStyles.dateJumpLabel}>
        Aller à une date
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => {
            const next = e.target.value;
            if (next && /^\d{4}-\d{2}-\d{2}$/.test(next)) onSelectDate(next);
          }}
          style={panelStyles.dateJumpInput}
        />
      </label>
      <div style={panelStyles.dateNavQuickRow}>
        <button type="button" onClick={() => onShift(-1)} style={panelStyles.dateNavQuickBtn}>‹ {viewMode === "month" ? "Mois" : viewMode === "week" ? "Sem." : "Jour"}</button>
        <button type="button" onClick={onGoToday} style={panelStyles.dateNavTodayBtn}>Aujourd&apos;hui</button>
        <button type="button" onClick={() => onShift(1)} style={panelStyles.dateNavQuickBtn}>{viewMode === "month" ? "Mois" : viewMode === "week" ? "Sem." : "Jour"} ›</button>
      </div>
      <div style={panelStyles.dateNavViewRow}>
        {["day", "week", "month"].map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => onViewMode(mode)}
            style={viewMode === mode ? panelStyles.dateNavViewBtnActive : panelStyles.dateNavViewBtn}
          >
            {mode === "day" ? "Jour" : mode === "week" ? "Semaine" : "Mois"}
          </button>
        ))}
      </div>
      <p style={panelStyles.dateNavHint}>{navHint}</p>
    </div>
  );
}

export default function AppAgenda() {
  const navigate = useNavigate();
  const { me } = useOutletContext() || {};
  const [searchParams] = useSearchParams();
  const urlDate = searchParams.get("date");
  const urlView = searchParams.get("view");
  const urlPhone = searchParams.get("phone");
  const urlFocus = searchParams.get("focus");
  const urlAction = searchParams.get("action");
  const isSpecialDashboardFocus =
    urlFocus === "annulations" || urlFocus === "creneaux-recuperes" || urlFocus === "prises-jour";
  const [selectedDate, setSelectedDate] = useState(urlDate || todayISO());
  const [pendingFocusPhone, setPendingFocusPhone] = useState(urlPhone || null);
  const [pendingFocusApptId, setPendingFocusApptId] = useState(
    urlFocus && !isSpecialDashboardFocus ? urlFocus : null,
  );
  const [pendingAgendaAction, setPendingAgendaAction] = useState(
    urlAction === "cancel" || urlAction === "reschedule" ? urlAction : null,
  );
  const [viewMode, setViewMode] = useState("day");
  const [isMobileAgenda, setIsMobileAgenda] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 760 : false,
  );

  useEffect(() => {
    const onResize = () => setIsMobileAgenda(window.innerWidth <= 760);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (urlDate && urlDate !== selectedDate) {
      setSelectedDate(urlDate);
    }
    if (urlView === "day" || urlView === "week" || urlView === "month") {
      setViewMode(urlView);
    }
    if (urlPhone) setPendingFocusPhone(urlPhone);
    if (urlFocus && urlFocus !== "annulations" && urlFocus !== "creneaux-recuperes" && urlFocus !== "prises-jour") {
      setPendingFocusApptId(urlFocus);
    }
    if (urlAction === "cancel" || urlAction === "reschedule") {
      setPendingAgendaAction(urlAction);
    }
  }, [urlDate, urlView, urlPhone, urlFocus, urlAction, selectedDate]);

  /* Liens depuis le dashboard : focus=annulations → jour ; creneaux-recuperes → semaine */
  useEffect(() => {
    if (urlFocus !== "annulations" && urlFocus !== "creneaux-recuperes") return;
    const d = urlDate && /^\d{4}-\d{2}-\d{2}$/.test(urlDate) ? urlDate : todayISO();
    setSelectedDate(d);
    setViewMode(urlFocus === "creneaux-recuperes" ? "week" : "day");
  }, [urlFocus, urlDate]);

  /* Prises de RDV aujourd'hui (dashboard) → semaine + panneau confirmations */
  useEffect(() => {
    if (urlFocus !== "prises-jour") return;
    setViewMode("week");
    const d = urlDate && /^\d{4}-\d{2}-\d{2}$/.test(urlDate) ? urlDate : todayISO();
    setSelectedDate(d);
  }, [urlFocus, urlDate]);

  useEffect(() => {
    if (urlFocus !== "prises-jour") return undefined;
    let cancelled = false;
    setBookingsTodayPanel((prev) => ({ ...prev, loading: true }));
    api.tenantBookingsToday()
      .then((data) => {
        if (cancelled) return;
        setBookingsTodayPanel({
          loading: false,
          date: String(data?.date || ""),
          items: Array.isArray(data?.bookings) ? data.bookings : [],
        });
      })
      .catch(() => {
        if (cancelled) return;
        setBookingsTodayPanel({ loading: false, date: "", items: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [urlFocus]);
  const [agendaByDate, setAgendaByDate] = useState({});
  const [horaires, setHoraires] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [error, setError] = useState("");
  const agendaLoadSeqRef = useRef(0);
  const [selectedAppt, setSelectedAppt] = useState(null);
  /** Une seule fenêtre RDV : détail ou création fiche (jamais deux modales empilées). */
  const [apptPanel, setApptPanel] = useState("detail");
  const [actionMsg, setActionMsg] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [rescheduleMode, setRescheduleMode] = useState(false);
  const [patientCreateLoading, setPatientCreateLoading] = useState(false);
  const [patientCreateSummary, setPatientCreateSummary] = useState("");
  const [patientCreateForm, setPatientCreateForm] = useState({
    firstName: "",
    lastName: "",
    phone: "",
    email: "",
    birthDate: "",
    treatingPhysicianName: "",
    treatingPhysicianCity: "",
    initialNote: "",
    agendaMotif: "",
    rawCalendarName: "",
    callId: "",
  });
  /** Conflits détectés si une fiche existe déjà pour le numéro / email saisi. */
  const [patientCreateConflicts, setPatientCreateConflicts] = useState([]);
  const [createBookingConflicts, setCreateBookingConflicts] = useState([]);

  const [createBookingOpen, setCreateBookingOpen] = useState(false);
  const [createBookingLoading, setCreateBookingLoading] = useState(false);
  const [createBookingError, setCreateBookingError] = useState("");
  /** Après création réussie : détail pour la modale de confirmation verte */
  const [createBookingConfirm, setCreateBookingConfirm] = useState(null);
  /** Après annulation réussie : message de confirmation visuelle */
  const [cancelBookingConfirm, setCancelBookingConfirm] = useState(null);
  const [createBookingSuggestions, setCreateBookingSuggestions] = useState([]);
  const [createBookingSuggestLoading, setCreateBookingSuggestLoading] = useState(false);
  const [createBookingForm, setCreateBookingForm] = useState({
    patient_name: "",
    patient_phone: "",
    patient_email: "",
    motif: "Consultation",
    booking_date: "",
    booking_time: "",
  });
  const [bookingsTodayPanel, setBookingsTodayPanel] = useState({ loading: false, items: [], date: "" });
  const horairesRef = useRef(horaires);
  const horairesFetchedAtRef = useRef(0);
  const googleEnrichInFlightRef = useRef(new Set());
  const googleEnrichLastAtRef = useRef(new Map());

  useEffect(() => {
    horairesRef.current = horaires;
  }, [horaires]);

  const weekDates = useMemo(() => buildWeekDates(selectedDate), [selectedDate]);
  const monthGrid = useMemo(() => buildMonthGrid(selectedDate), [selectedDate]);
  const currentMonth = getMonthFromDate(selectedDate);
  const today = todayISO();

  const visibleDates = useMemo(() => {
    if (viewMode === "month") return [...new Set(monthGrid)];
    if (viewMode === "week") return weekDates;
    return [selectedDate];
  }, [viewMode, weekDates, monthGrid, selectedDate]);

  /** Plage réellement chargée : semaine entière en vue jour (évite un refetch à chaque clic). */
  const fetchDates = useMemo(() => {
    if (viewMode === "month") return [...new Set(monthGrid)];
    return weekDates;
  }, [viewMode, monthGrid, weekDates]);

  const agendaByDateRef = useRef(agendaByDate);
  useEffect(() => {
    agendaByDateRef.current = agendaByDate;
  }, [agendaByDate]);

  const hasLoadedAgendaForDates = useCallback((dates) => {
    if (!Array.isArray(dates) || dates.length === 0) return false;
    return dates.every((dateValue) => Array.isArray(agendaByDateRef.current?.[dateValue]?.slots));
  }, []);

  const resetAgendaRuntimeCaches = useCallback(() => {
    googleEnrichInFlightRef.current.clear();
    googleEnrichLastAtRef.current.clear();
    horairesFetchedAtRef.current = 0;
  }, []);

  const loadAgenda = useCallback(async () => {
    const loadId = ++agendaLoadSeqRef.current;
    const isStaleLoad = () => loadId !== agendaLoadSeqRef.current;
    const AGENDA_TIMEOUT_MS = 10000;
    const AGENDA_BULK_TIMEOUT_MS = 12000;
    const requiredDates = viewMode === "day" ? [selectedDate] : fetchDates;
    const hasVisibleCache = hasLoadedAgendaForDates(requiredDates);

    setError("");
    setCalendarLoading(!hasVisibleCache);
    const shouldRefreshHoraires =
      !horairesRef.current || (Date.now() - horairesFetchedAtRef.current > AGENDA_HORAIRES_REFRESH_MS);
    if (shouldRefreshHoraires) {
      api.tenantGetHoraires().catch(() => null).then((nextHoraires) => {
        if (!isStaleLoad() && nextHoraires) {
          setHoraires(nextHoraires);
          horairesFetchedAtRef.current = Date.now();
        }
      });
    }

    const handleAgendaAuthError = (e) => {
      if (isTenantUnauthorized(e) || e?.status === 401 || e?.status === 403) {
        setError("Votre session a expiré. Veuillez vous reconnecter.");
        return true;
      }
      return false;
    };

    const loadBulk = async (dates, { timeoutMs = AGENDA_BULK_TIMEOUT_MS, skipGoogle = false } = {}) => {
      const bulkRes = await api.tenantGetAgendaBulk(dates, { lightweight: true, timeoutMs, skipGoogle });
      if (isStaleLoad()) return null;
      setAgendaByDate((prev) => mergeAgendaBulkIntoState(prev, dates, bulkRes));
      if (bulkRes && countBulkSlots(bulkRes, dates) > 0) writeAgendaBulkStale(dates, bulkRes);
      return bulkRes;
    };

    const enrichWithGoogle = (dates) => {
      if (!dates?.length) return;
      const key = agendaDatesKey(dates);
      if (!key) return;
      if (googleEnrichInFlightRef.current.has(key)) return;
      const lastAt = Number(googleEnrichLastAtRef.current.get(key) || 0);
      if (Date.now() - lastAt < AGENDA_GOOGLE_ENRICH_COOLDOWN_MS) return;
      googleEnrichLastAtRef.current.set(key, Date.now());
      googleEnrichInFlightRef.current.add(key);
      loadBulk(dates, { timeoutMs: 15000, skipGoogle: false })
        .catch((e) => {
          if (!isStaleLoad() && handleAgendaAuthError(e)) return;
        })
        .finally(() => {
          googleEnrichInFlightRef.current.delete(key);
        });
    };

    try {
      if (fetchDates.length) {
        const cachedBulk = readAgendaBulkStale(fetchDates);
        if (cachedBulk) {
          setAgendaByDate((prev) => mergeAgendaBulkIntoState(prev, fetchDates, cachedBulk));
        }
      }

      if (viewMode === "day") {
        const dayFast = await api.tenantGetAgenda(`?date=${selectedDate}`, {
          lightweight: true,
          skipGoogle: true,
          timeoutMs: AGENDA_TIMEOUT_MS,
        });
        if (isStaleLoad()) return;
        setAgendaByDate((prev) => ({
          ...(prev || {}),
          [selectedDate]: dayFast || { slots: [], date: selectedDate },
        }));
        setCalendarLoading(false);
        if (fetchDates.length > 1) {
          enrichWithGoogle(fetchDates);
        } else {
          api
            .tenantGetAgenda(`?date=${selectedDate}`, { lightweight: true, timeoutMs: 15000 })
            .then((dayFull) => {
              if (isStaleLoad()) return;
              setAgendaByDate((prev) => ({
                ...(prev || {}),
                [selectedDate]: mergeAgendaDayPayload(prev?.[selectedDate], dayFull),
              }));
            })
            .catch((e) => {
              if (!isStaleLoad() && handleAgendaAuthError(e)) return;
            });
        }
        return;
      }

      await loadBulk(fetchDates, { timeoutMs: AGENDA_BULK_TIMEOUT_MS, skipGoogle: true });
      if (isStaleLoad()) return;
      setCalendarLoading(false);
      enrichWithGoogle(fetchDates);
      return;
    } catch (e) {
      if (!isStaleLoad()) {
        if (!handleAgendaAuthError(e)) {
          const hasFallback = hasLoadedAgendaForDates(requiredDates);
          if (!hasFallback) setError(e?.message || "Impossible de charger l'agenda.");
        }
      }
    } finally {
      if (!isStaleLoad()) setCalendarLoading(false);
    }
  }, [fetchDates, hasLoadedAgendaForDates, selectedDate, viewMode]);

  useEffect(() => { loadAgenda(); }, [loadAgenda]);

  useEffect(() => {
    if (!calendarLoading) return undefined;
    const safetyTimer = window.setTimeout(() => {
      setCalendarLoading(false);
    }, 12000);
    return () => window.clearTimeout(safetyTimer);
  }, [calendarLoading]);

  const patientCreatePhoneError = useMemo(() => {
    const raw = String(patientCreateForm.phone || "").trim();
    if (!raw) return "Indiquez un numéro de téléphone.";
    const check = validatePatientPhone(raw, { required: true });
    return check.ok ? "" : (check.message || "Numéro invalide.");
  }, [patientCreateForm.phone]);

  const patientCreateEmailError = useMemo(() => {
    const check = validateContactEmail(patientCreateForm.email || "", { required: true });
    return check.ok ? "" : (check.message || "Email invalide.");
  }, [patientCreateForm.email]);

  const patientCreateBirthDateError = useMemo(() => {
    const check = validatePatientBirthDate(patientCreateForm.birthDate || "", { required: true });
    return check.ok ? "" : (check.message || "Date de naissance invalide.");
  }, [patientCreateForm.birthDate]);

  const patientCreatePhysicianNameError = useMemo(() => {
    const check = validateRequiredText(patientCreateForm.treatingPhysicianName || "", {
      required: true,
      label: "le médecin traitant",
      maxLength: 200,
    });
    return check.ok ? "" : (check.message || "Médecin traitant requis.");
  }, [patientCreateForm.treatingPhysicianName]);

  const patientCreatePhysicianCityError = useMemo(() => {
    const check = validateRequiredText(patientCreateForm.treatingPhysicianCity || "", {
      required: true,
      label: "la ville du médecin traitant",
      maxLength: 120,
    });
    return check.ok ? "" : (check.message || "Ville requise.");
  }, [patientCreateForm.treatingPhysicianCity]);

  const patientCreateSubmitBlocked = useMemo(
    () =>
      Boolean(patientCreatePhoneError)
      || Boolean(patientCreateEmailError)
      || Boolean(patientCreateBirthDateError)
      || Boolean(patientCreatePhysicianNameError)
      || Boolean(patientCreatePhysicianCityError)
      || hasBlockingPatientDuplicate(patientCreateConflicts),
    [
      patientCreatePhoneError,
      patientCreateEmailError,
      patientCreateBirthDateError,
      patientCreatePhysicianNameError,
      patientCreatePhysicianCityError,
      patientCreateConflicts,
    ],
  );

  useEffect(() => {
    if (apptPanel !== "create-patient" || !selectedAppt) {
      setPatientCreateConflicts([]);
      return undefined;
    }
    const phoneRaw = String(patientCreateForm.phone || "").trim();
    const emailRaw = String(patientCreateForm.email || "").trim();
    const phoneCheck = validatePatientPhone(phoneRaw, { required: true });
    if (!phoneCheck.ok && !emailRaw) {
      setPatientCreateConflicts([]);
      return undefined;
    }
    if (!phoneCheck.ok && emailRaw) {
      const emailCheck = validateContactEmail(emailRaw);
      if (!emailCheck.ok) {
        setPatientCreateConflicts([]);
        return undefined;
      }
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({
        phone: phoneCheck.ok ? phoneRaw : "",
        email: emailRaw,
        signal: ctrl.signal,
      })
        .then((res) => {
          if (!cancelled) {
            setPatientCreateConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) setPatientCreateConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [apptPanel, selectedAppt, patientCreateForm.phone, patientCreateForm.email]);

  useEffect(() => {
    if (!createBookingOpen) {
      setCreateBookingConflicts([]);
      return;
    }
    const phone = normalizePhone(createBookingForm.patient_phone);
    const email = (createBookingForm.patient_email || "").trim();
    if (!phone && !email) {
      setCreateBookingConflicts([]);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({ phone, email, signal: ctrl.signal })
        .then((res) => {
          if (!cancelled) {
            setCreateBookingConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) setCreateBookingConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [createBookingOpen, createBookingForm.patient_phone, createBookingForm.patient_email]);

  /** Suggestions patient (nom / téléphone / email) pour la création de RDV cabinet */
  useEffect(() => {
    if (!createBookingOpen) {
      setCreateBookingSuggestions([]);
      setCreateBookingSuggestLoading(false);
      return;
    }
    const composed = [
      createBookingForm.patient_name,
      createBookingForm.patient_phone,
      createBookingForm.patient_email,
    ]
      .map((s) => (s || "").trim())
      .filter(Boolean)
      .join(" ")
      .trim();
    if (composed.length < 2) {
      setCreateBookingSuggestions([]);
      setCreateBookingSuggestLoading(false);
      return;
    }
    const ctrl = new AbortController();
    const tid = window.setTimeout(async () => {
      setCreateBookingSuggestLoading(true);
      try {
        const res = await api.tenantGetPatients(`?q=${encodeURIComponent(composed)}&limit=15`, {
          signal: ctrl.signal,
        });
        if (!ctrl.signal.aborted) {
          setCreateBookingSuggestions(Array.isArray(res?.items) ? res.items : []);
        }
      } catch (e) {
        if (!ctrl.signal.aborted && String(e?.name || "") !== "AbortError") {
          setCreateBookingSuggestions([]);
        }
      } finally {
        if (!ctrl.signal.aborted) {
          setCreateBookingSuggestLoading(false);
        }
      }
    }, 320);
    return () => {
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [
    createBookingOpen,
    createBookingForm.patient_name,
    createBookingForm.patient_phone,
    createBookingForm.patient_email,
  ]);

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

  const cabinetBookingTimeChoices = useMemo(() => {
    const step =
      duration >= 15 && duration <= 60 && duration % 5 === 0 ? duration : 15;
    return buildCabinetTimeChoices(cfgStart, cfgEnd, step);
  }, [cfgStart, cfgEnd, duration]);

  useEffect(() => {
    if (!createBookingOpen || !cabinetBookingTimeChoices.length) return;
    setCreateBookingForm((p) =>
      cabinetBookingTimeChoices.includes(p.booking_time)
        ? p
        : { ...p, booking_time: pickDefaultCabinetTime(cabinetBookingTimeChoices) },
    );
  }, [createBookingOpen, cabinetBookingTimeChoices]);

  /** Bloque « Enregistrer » tant que téléphone ou e-mail (si remplis) ne sont pas valides. */
  const cabinetBookingFormValid = useMemo(() => {
    const name = (createBookingForm.patient_name || "").trim();
    if (!name || name.length < 2) return false;
    if (!validateCabinetBookingPhone(createBookingForm.patient_phone).ok) return false;
    const emailTrim = (createBookingForm.patient_email || "").trim();
    if (emailTrim && !isCabinetBookingEmailValid(emailTrim)) return false;
    const { booking_date, booking_time } = createBookingForm;
    if (!booking_date || !/^\d{4}-\d{2}-\d{2}$/.test(booking_date.trim())) return false;
    if (!booking_time || !/^\d{2}:\d{2}$/.test(booking_time.trim())) return false;
    const dt = new Date(`${booking_date.trim()}T${booking_time.trim()}:00`);
    return !Number.isNaN(dt.getTime());
  }, [createBookingForm]);

  const createBookingPhoneError = useMemo(() => {
    const raw = String(createBookingForm.patient_phone || "").trim();
    if (!raw) return "";
    const check = validateCabinetBookingPhone(createBookingForm.patient_phone);
    return check.ok ? "" : (check.message || "Numéro invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78).");
  }, [createBookingForm.patient_phone]);

  const createBookingEmailError = useMemo(() => {
    const raw = String(createBookingForm.patient_email || "").trim();
    if (!raw) return "";
    const check = validateContactEmail(raw);
    return check.ok ? "" : (check.message || "Email invalide (format attendu : prenom@domaine.fr).");
  }, [createBookingForm.patient_email]);

  const createBookingSubmitHint = useMemo(() => {
    if (cabinetBookingFormValid) return "";
    const parts = [];
    const name = (createBookingForm.patient_name || "").trim();
    if (!name || name.length < 2) {
      parts.push("Indiquez le nom du patient (au moins 2 caractères).");
    }
    if (createBookingPhoneError) parts.push(createBookingPhoneError);
    if (createBookingEmailError) parts.push(createBookingEmailError);
    if (hasBlockingPatientDuplicate(createBookingConflicts)) {
      parts.push("Ce numéro ou cet e-mail est déjà utilisé par une autre fiche patient.");
    }
    const { booking_date, booking_time } = createBookingForm;
    const dateOk = booking_date && /^\d{4}-\d{2}-\d{2}$/.test(String(booking_date).trim());
    const timeOk = booking_time && /^\d{2}:\d{2}$/.test(String(booking_time).trim());
    if (!dateOk || !timeOk) {
      parts.push("Choisissez une date et une heure valides.");
    }
    if (!parts.length) {
      return "Complétez les champs obligatoires pour enregistrer le rendez-vous.";
    }
    return parts.join(" ");
  }, [
    cabinetBookingFormValid,
    createBookingForm,
    createBookingPhoneError,
    createBookingEmailError,
    createBookingConflicts,
  ]);

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

  const appointments = useMemo(
    () => visibleDates.flatMap((date) =>
      (agendaByDate[date]?.slots || [])
        .filter((s) => !isAgendaCancelledSlot(s))
        .map((s, i) => {
          const appt = {
            ...s,
            id: `${date}-${s.event_id || s.appointment_id || i}`,
            date,
            displayTime: formatTimeLabel(s.hour),
            endTime: addMinutes(formatTimeLabel(s.hour), duration),
            typeIcon: typeIcon(s.type),
            isUWI: s.source === "UWI",
            canCancel: canCancelAgendaSlot(s),
            canReschedule: canRescheduleAgendaSlot(s),
            actionId: s.source === "PAGE_PUBLIQUE"
              ? (s.public_booking_id || s.event_id || "")
              : (s.appointment_id || s.event_id || ""),
          };
          return { ...appt, tone: toneForAppointment(appt) };
        })),
    [agendaByDate, visibleDates, duration],
  );

  const appointmentsByDate = useMemo(() => {
    const map = {};
    appointments.forEach((a) => {
      if (!map[a.date]) map[a.date] = [];
      map[a.date].push(a);
    });
    Object.keys(map).forEach((d) => {
      map[d] = sortApptsByTime(map[d]);
    });
    return map;
  }, [appointments]);

  const appointmentsByDateHour = useMemo(() => {
    const map = {};
    appointments.forEach((a) => {
      const key = `${a.date}|${agendaGridHourKey(a.displayTime)}`;
      if (!map[key]) map[key] = [];
      map[key].push(a);
    });
    return map;
  }, [appointments]);

  /** RDV au statut annulé dans la période affichée (aligné logique dashboard). */
  const cancelledInVisible = useMemo(
    () => appointments.filter((a) => String(a?.status || "").toLowerCase().includes("cancel")).length,
    [appointments],
  );

  /** Deep link depuis le dashboard : scroll vers la pastille Annulations / Créneau récupéré */
  useEffect(() => {
    if (calendarLoading) return undefined;
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
  }, [calendarLoading, urlFocus, viewMode, selectedDate, appointments.length]);

  const apptCountByDate = useMemo(() => {
    const map = {};
    appointments.forEach((a) => { map[a.date] = (map[a.date] || 0) + 1; });
    return map;
  }, [appointments]);

  useEffect(() => {
    if (!pendingFocusApptId) return;
    if (!appointments.length) return;
    const focus = String(pendingFocusApptId);
    const match = appointments.find((a) => {
      const apptId = String(a.appointment_id || "");
      const evtId = String(a.event_id || "");
      const actionId = String(a.actionId || "");
      return apptId === focus || evtId === focus || actionId === focus || String(a.id) === focus;
    });
    if (match) {
      setSelectedAppt(match);
      if (pendingAgendaAction === "cancel") {
        setConfirmCancel(true);
        setRescheduleMode(false);
      } else if (pendingAgendaAction === "reschedule") {
        setRescheduleMode(true);
        setConfirmCancel(false);
      } else {
        setConfirmCancel(false);
        setRescheduleMode(false);
      }
      setPendingFocusApptId(null);
      setPendingAgendaAction(null);
    }
  }, [appointments, pendingFocusApptId, pendingAgendaAction]);

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
    const apptToCancel = selectedAppt;
    setActionLoading(true);
    try {
      await api.tenantCancelAgendaAppointment(
        apptToCancel.actionId || apptToCancel.appointment_id || apptToCancel.event_id || apptToCancel.id,
        agendaCancelPayload(apptToCancel),
      );
      const cancelledWhen = `${formatLongDate(apptToCancel.date)} à ${apptToCancel.displayTime || formatTimeLabel(apptToCancel.hour) || "—"}`;
      setCancelBookingConfirm({
        patientName: String(apptToCancel.patient || "Patient").trim() || "Patient",
        whenLine: cancelledWhen,
      });
      setActionMsg({ text: "Rendez-vous annulé.", type: "success" });
      setAgendaByDate((prev) => {
        const date = String(apptToCancel?.date || "");
        if (!date || !prev?.[date]?.slots) return prev;
        const slots = Array.isArray(prev[date].slots) ? prev[date].slots : [];
        const filtered = slots.filter((slot, idx) => !isSameAgendaSlotForCancel(slot, apptToCancel, date, idx));
        if (filtered.length === slots.length) return prev;
        return {
          ...(prev || {}),
          [date]: {
            ...(prev[date] || {}),
            slots: filtered,
          },
        };
      });
      closeAppointmentDetail();
      resetAgendaRuntimeCaches();
      invalidateAgendaBulkCache();
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

  function closeAppointmentDetail() {
    setSelectedAppt(null);
    setApptPanel("detail");
    setConfirmCancel(false);
    resetReschedule();
  }

  const syncAgendaUrl = useCallback((nextDate, nextView, extra = {}) => {
    const params = new URLSearchParams();
    params.set("view", nextView || viewMode);
    params.set("date", nextDate || selectedDate);
    if (extra.focus) params.set("focus", String(extra.focus));
    if (extra.action) params.set("action", String(extra.action));
    navigate(`/app/agenda?${params.toString()}`, { replace: true });
  }, [navigate, selectedDate, viewMode]);

  function applyAgendaDate(dateStr, opts = {}) {
    if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return;
    setSelectedDate(dateStr);
    const nextView = opts.view || viewMode;
    if (opts.view) setViewMode(opts.view);
    syncAgendaUrl(dateStr, nextView, opts);
    if (isMobileAgenda && nextView === "week") {
      window.requestAnimationFrame(() => {
        document.getElementById(`agenda-week-day-${dateStr}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  function applyViewMode(mode) {
    if (mode !== "day" && mode !== "week" && mode !== "month") return;
    setViewMode(mode);
    syncAgendaUrl(selectedDate, mode);
  }

  function toggleAppt(a) {
    if (selectedAppt?.id === a.id) {
      closeAppointmentDetail();
    } else {
      setSelectedAppt(a);
      setApptPanel("detail");
      setConfirmCancel(false);
      resetReschedule();
    }
  }

  function viewPatientFileFromSelectedAppt() {
    const phone = normalizePhone(selectedAppt?.patient_phone || selectedAppt?.phone || "");
    if (!phone) return;
    closeAppointmentDetail();
    navigate(`/app/patient-dashboard?phone=${encodeURIComponent(phone)}`);
  }

  function openCreatePatientFormFromAppt(appt) {
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
      email: String(appt?.patient_email || appt?.email || "").trim(),
      birthDate: "",
      treatingPhysicianName: "",
      treatingPhysicianCity: "",
      initialNote,
      agendaMotif: motif,
      rawCalendarName: String(appt?.patient || "").trim(),
      callId: "",
    });
    setPatientCreateConflicts([]);
    setPatientCreateSummary(
      `${formatLongDate(appt?.date)} · ${appt?.displayTime || "—"}${motif ? ` · ${motif}` : ""}`,
    );
    setSelectedAppt(appt);
    setApptPanel("create-patient");
    setConfirmCancel(false);
    resetReschedule();
  }

  function openConsultationSheetFromSelectedAppt(appt) {
    const phone = normalizePhone(appt?.patient_phone || appt?.phone || "");
    if (!phone) {
      setActionMsg({
        type: "error",
        text: "Numéro patient requis pour créer une fiche de consultation.",
      });
      return;
    }
    const params = new URLSearchParams();
    params.set("phone", phone);
    params.set("consultation", "1");
    const dateIso = String(appt?.date || "").trim();
    if (dateIso) params.set("consultationDate", dateIso);
    const motif = String(appt?.type || "").trim();
    if (motif) params.set("consultationMotif", motif);
    const apptId = appointmentLocalId(appt)
      ? String(appointmentLocalId(appt))
      : (appointmentGoogleEventId(appt) || String(appt?.event_id || "").trim());
    if (apptId) params.set("consultationAppointmentId", apptId);
    closeAppointmentDetail();
    navigate(`/app/patient-dashboard?${params.toString()}`);
  }

  useEffect(() => {
    if (!selectedAppt) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") closeAppointmentDetail();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedAppt]);

  function handleStartReschedule(action) {
    if (action === "close") { resetReschedule(); return; }
    setRescheduleMode(true);
    setConfirmCancel(false);
  }

  async function handleReschedule(slot) {
    if (!selectedAppt) return;
    const apptId = appointmentLocalId(selectedAppt);
    const actionId = apptId
      ? String(apptId)
      : (appointmentGoogleEventId(selectedAppt) || String(selectedAppt.event_id || "").trim());
    if (!actionId) {
      setActionMsg({ text: "Déplacement impossible : rendez-vous introuvable.", type: "error" });
      return;
    }
    setActionLoading(true);
    try {
      const res = await api.tenantRescheduleAgendaAppointment(
        actionId,
        agendaReschedulePayload(selectedAppt, slot.slot_id),
      );
      const fmtDate = new Date(`${slot.date}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
      const syncedGoogle = res?.provider === "google+local" || res?.google_synced === true;
      setActionMsg({
        text: syncedGoogle
          ? `RDV déplacé sur UWi et Google Calendar au ${fmtDate} à ${slot.time}`
          : `RDV déplacé au ${fmtDate} à ${slot.time}`,
        type: "success",
      });
      closeAppointmentDetail();
      resetAgendaRuntimeCaches();
      invalidateAgendaBulkCache();
      await loadAgenda();
    } catch (e) {
      setActionMsg({ text: e?.message || "Impossible de déplacer le RDV.", type: "error" });
    } finally {
      setActionLoading(false);
    }
  }

  function openCreateCabinetBooking() {
    setCreateBookingError("");
    setCreateBookingForm({
      patient_name: "",
      patient_phone: "",
      patient_email: "",
      motif: "Consultation",
      booking_date: selectedDate >= today ? selectedDate : today,
      booking_time: pickDefaultCabinetTime(cabinetBookingTimeChoices),
    });
    setCreateBookingSuggestions([]);
    setCreateBookingOpen(true);
  }

  function applyCreateBookingPatient(p) {
    if (!p) return;
    const display = (p.display_name || p.validated_name || p.raw_name || "").trim();
    setCreateBookingForm((prev) => ({
      ...prev,
      patient_name: display || prev.patient_name,
      patient_phone: (p.phone || "").trim(),
      patient_email: ((p.email || "").trim()) || prev.patient_email,
    }));
    setCreateBookingSuggestions([]);
  }

  async function handleCreateCabinetBookingSubmit() {
    const name = (createBookingForm.patient_name || "").trim();
    if (!name || name.length < 2) {
      setActionMsg({ type: "error", text: "Indiquez le nom du patient (au moins 2 caractères)." });
      return;
    }
    const { booking_date, booking_time } = createBookingForm;
    if (!booking_date || !/^\d{4}-\d{2}-\d{2}$/.test(booking_date.trim())) {
      setActionMsg({ type: "error", text: "Choisissez une date pour le RDV." });
      return;
    }
    if (!booking_time || !/^\d{2}:\d{2}$/.test(booking_time.trim())) {
      setActionMsg({ type: "error", text: "Choisissez une heure pour le RDV." });
      return;
    }
    const startIso = buildCabinetBookingStartIso(booking_date, booking_time);
    if (!startIso) {
      setCreateBookingError("Choisissez une date et une heure valides pour le RDV.");
      return;
    }
    const phoneCheck = validateCabinetBookingPhone(createBookingForm.patient_phone);
    if (!phoneCheck.ok) {
      setCreateBookingError(phoneCheck.message || "Numéro de téléphone invalide.");
      return;
    }
    const emailTrim = (createBookingForm.patient_email || "").trim();
    if (emailTrim && !isCabinetBookingEmailValid(emailTrim)) {
      setCreateBookingError("L’adresse e-mail n’est pas valide (exemple : prenom@gmail.com).");
      return;
    }
    if (hasBlockingPatientDuplicate(createBookingConflicts)) {
      setCreateBookingError(
        "Cet e-mail ou ce numéro est déjà utilisé par une autre fiche patient. Corrigez avant de créer le RDV.",
      );
      return;
    }
    setCreateBookingLoading(true);
    setCreateBookingError("");
    try {
      await api.tenantCreateAgendaBooking({
        patient_name: name,
        patient_phone: normalizePhone(createBookingForm.patient_phone || ""),
        patient_email: (createBookingForm.patient_email || "").trim(),
        motif: (createBookingForm.motif || "Consultation").trim(),
        start_iso: startIso,
      });
      const dIso = booking_date.trim();
      const timeHm = createBookingForm.booking_time.trim();
      const timeStr = formatTimeChoiceFR(timeHm);
      const phoneNorm = normalizePhone(createBookingForm.patient_phone || "");
      let needsPatientFile = false;
      if (phoneNorm) {
        try {
          const prof = await api.tenantGetPatient(phoneNorm, { lightweight: true });
          needsPatientFile = !prof?.patient;
        } catch (e) {
          needsPatientFile = e?.status === 404;
        }
      }

      setCreateBookingConfirm({
        patientName: name,
        whenLine: `${formatLongDate(dIso)}, ${timeStr}`,
        motif: (createBookingForm.motif || "Consultation").trim(),
        dateIso: dIso,
        timeHHMM: timeHm,
        patientPhone: phoneNorm,
        patientEmail: emailTrim,
        needsPatientFile: Boolean(phoneNorm && needsPatientFile),
      });
      setCreateBookingOpen(false);
      setCreateBookingError("");
      resetAgendaRuntimeCaches();
      invalidateAgendaBulkCache();
      await loadAgenda();
      setActionMsg({ type: "success", text: "Rendez-vous créé avec succès." });
    } catch (e) {
      const msg = e?.message || "Impossible de créer ce rendez-vous.";
      setCreateBookingError(msg);
      setActionMsg({ type: "error", text: msg });
    } finally {
      setCreateBookingLoading(false);
    }
  }

  function handleViewBookingInAgenda(confirmPayload) {
    if (!confirmPayload?.dateIso) return;
    setCreateBookingConfirm(null);
    const qs = new URLSearchParams({ date: confirmPayload.dateIso, view: "day" });
    if (confirmPayload.patientPhone) qs.set("phone", confirmPayload.patientPhone);
    navigate(`/app/agenda?${qs.toString()}`);
  }

  function handleCreatePatientFromBookingConfirm(confirmPayload) {
    if (!confirmPayload?.dateIso || !confirmPayload?.patientPhone) return;
    const fakeAppt = {
      id: `cabinet-after-booking-${confirmPayload.dateIso}-${confirmPayload.timeHHMM || ""}`,
      date: confirmPayload.dateIso,
      displayTime: confirmPayload.timeHHMM || "",
      endTime: confirmPayload.timeHHMM || "",
      patient: confirmPayload.patientName,
      patient_phone: confirmPayload.patientPhone,
      patient_email: confirmPayload.patientEmail || "",
      patient_has_file: false,
      patient_identity_validated: false,
      type: confirmPayload.motif || "Consultation",
      typeIcon: "📋",
      isUWI: false,
      canCancel: false,
      source: "UWI",
    };
    setCreateBookingConfirm(null);
    openPatientCreateFromAppointment(fakeAppt);
  }

  function openPatientCreateFromAppointment(appt) {
    if (agendaAppointmentHasValidatedIdentity(appt)) {
      const phone = normalizePhone(appt?.patient_phone || "");
      if (phone) {
        closeAppointmentDetail();
        navigate(`/app/patient-dashboard?phone=${encodeURIComponent(phone)}`);
        return;
      }
    }
    openCreatePatientFormFromAppt(appt);
  }

  async function handlePatientCreateFromAgendaSubmit() {
    const phoneRaw = String(patientCreateForm.phone || "").trim();
    const emailRaw = String(patientCreateForm.email || "").trim();
    const name = composeAgendaPatientName(patientCreateForm);
    const phoneCheck = validatePatientPhone(phoneRaw, { required: true });
    if (!phoneCheck.ok) {
      setActionMsg({ type: "error", text: phoneCheck.message || "Numéro de téléphone invalide." });
      return;
    }
    const emailCheck = validateContactEmail(emailRaw, { required: true });
    if (!emailCheck.ok) {
      setActionMsg({ type: "error", text: emailCheck.message || "Email invalide." });
      return;
    }
    const birthDateRaw = String(patientCreateForm.birthDate || "").trim();
    const birthCheck = validatePatientBirthDate(birthDateRaw, { required: true });
    if (!birthCheck.ok) {
      setActionMsg({ type: "error", text: birthCheck.message || "Date de naissance invalide." });
      return;
    }
    const physicianName = String(patientCreateForm.treatingPhysicianName || "").trim();
    const physicianCity = String(patientCreateForm.treatingPhysicianCity || "").trim();
    const physicianNameCheck = validateRequiredText(physicianName, {
      required: true,
      label: "le médecin traitant",
      maxLength: 200,
    });
    if (!physicianNameCheck.ok) {
      setActionMsg({ type: "error", text: physicianNameCheck.message || "Médecin traitant requis." });
      return;
    }
    const physicianCityCheck = validateRequiredText(physicianCity, {
      required: true,
      label: "la ville du médecin traitant",
      maxLength: 120,
    });
    if (!physicianCityCheck.ok) {
      setActionMsg({ type: "error", text: physicianCityCheck.message || "Ville du médecin requise." });
      return;
    }
    const phone = normalizePhone(phoneRaw);
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
    let conflicts = patientCreateConflicts;
    try {
      const dupRes = await checkPatientDuplicates({ phone: phoneRaw, email: emailRaw });
      conflicts = Array.isArray(dupRes?.conflicts) ? dupRes.conflicts : [];
      setPatientCreateConflicts(conflicts);
    } catch {
      /* garde les conflits déjà affichés */
    }
    if (hasBlockingPatientDuplicate(conflicts)) {
      const first = conflicts[0];
      setActionMsg({
        type: "error",
        text: formatPatientDuplicateConflict(first) || "Ce numéro ou cet email appartient déjà à une autre fiche.",
      });
      return;
    }
    setPatientCreateLoading(true);
    try {
      const res = await api.tenantRegisterPatient({
        patient_phone: phone,
        validated_name: name,
        raw_name: (patientCreateForm.rawCalendarName || "").trim() || name,
        first_name: String(patientCreateForm.firstName || "").trim() || undefined,
        last_name: String(patientCreateForm.lastName || "").trim() || undefined,
        agenda_motif: (patientCreateForm.agendaMotif || "").trim() || undefined,
        initial_note: (patientCreateForm.initialNote || "").trim() || undefined,
        patient_email: emailRaw ? emailRaw.toLowerCase() : emailRaw,
        birth_date: birthDateRaw,
        treating_physician_name: physicianName,
        treating_physician_city: physicianCity,
      });
      const mode = res?.register_mode;
      const okText =
        mode === "created"
          ? "Fiche patient créée."
          : mode === "completed"
            ? "Fiche patient complétée (numéro déjà connu, nom renseigné)."
            : mode === "updated"
              ? "Fiche patient mise à jour pour ce numéro (éléments ajoutés sur une fiche existante)."
              : "Fiche patient enregistrée.";
      setPatientCreateConflicts([]);
      setActionMsg({ type: "success", text: okText });
      resetAgendaRuntimeCaches();
      invalidateAgendaBulkCache();
      closeAppointmentDetail();
      const profile = res?.patient;
      const displayName = String(
        profile?.display_name || profile?.validated_name || name,
      ).trim() || name;
      navigate(`/app/patient-dashboard?phone=${encodeURIComponent(phone)}`, {
        state: {
          bootstrapPatient: {
            name: displayName,
            phone,
            email: emailRaw,
            birth_date: birthDateRaw,
            treating_physician_name: physicianName,
            treating_physician_city: physicianCity,
          },
        },
      });
      void loadAgenda();
    } catch (e) {
      const dup = parsePatientDuplicateError(e);
      setActionMsg({
        type: "error",
        text: dup.message || e?.message || "Impossible de créer la fiche patient.",
      });
    } finally {
      setPatientCreateLoading(false);
    }
  }

  function navPrev() {
    const nextDate = viewMode === "month"
      ? shiftMonth(selectedDate, -1)
      : shiftDate(selectedDate, viewMode === "week" ? -7 : -1);
    applyAgendaDate(nextDate);
  }
  function navNext() {
    const nextDate = viewMode === "month"
      ? shiftMonth(selectedDate, 1)
      : shiftDate(selectedDate, viewMode === "week" ? 7 : 1);
    applyAgendaDate(nextDate);
  }
  function goToday() {
    applyAgendaDate(todayISO(), { view: viewMode });
  }

  function selectAgendaDay(dateStr) {
    applyAgendaDate(dateStr);
  }

  function openDayView(dateStr) {
    applyAgendaDate(dateStr, { view: "day" });
  }

  function shiftAgendaPeriod(diff) {
    const nextDate = viewMode === "month"
      ? shiftMonth(selectedDate, diff)
      : shiftDate(selectedDate, viewMode === "week" ? diff * 7 : diff);
    applyAgendaDate(nextDate);
  }

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

  const navLabel = viewMode === "month"
    ? formatMonthLabel(selectedDate)
    : viewMode === "week"
      ? `Semaine du ${formatLongDate(weekDates[0])}`
      : formatLongDate(selectedDate);

  return (
    <div className="agenda-page" style={S.page}>
      <style>{CSS}</style>

      {error ? (
        <div style={S.errorBox}>
          {error}
          {" "}
          <button type="button" onClick={loadAgenda} style={S.errorRetryBtn}>
            Réessayer
          </button>
        </div>
      ) : null}
      {actionMsg ? <div style={actionMsg.type === "error" ? S.toastError : S.toast}>
        {actionMsg.type === "error" ? "⚠️ " : "✅ "}{actionMsg.text || actionMsg}
      </div> : null}

      {/* ─── BARRE UNIQUE : navigation + vues + stats ─── */}
      <div className="agenda-toolbar" style={S.toolbar}>
        <div className="agenda-toolbar-left" style={S.toolbarLeft}>
          <button type="button" onClick={navPrev} style={S.navBtn} title={viewMode === "month" ? "Mois précédent" : viewMode === "week" ? "Semaine précédente" : "Jour précédent"}>‹</button>
          <label style={S.toolbarDateJump}>
            <span className="agenda-nav-label" style={S.navDate}>{navLabel}</span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => applyAgendaDate(e.target.value)}
              style={S.toolbarDateInput}
              aria-label="Choisir une date"
            />
          </label>
          <button type="button" onClick={navNext} style={S.navBtn} title={viewMode === "month" ? "Mois suivant" : viewMode === "week" ? "Semaine suivante" : "Jour suivant"}>›</button>
          {selectedDate !== today && <button type="button" onClick={goToday} style={S.todayBtn}>Aujourd&apos;hui</button>}
          <button
            type="button"
            onClick={openCreateCabinetBooking}
            className="agenda-create-btn"
            style={S.createRdvBtn}
            title="Créer un rendez-vous depuis l'espace cabinet"
          >
            + Créer un rendez-vous
          </button>
        </div>
        <div className="agenda-toolbar-right" style={S.toolbarRight}>
          <span style={S.stats}>
            {subtitleMap[viewMode]}
            {uwiCount > 0 ? ` · ${uwiCount} via IA` : ""}
            {isConnected ? " · 🟢" : ""}
          </span>
          <div className="agenda-view-switch" style={S.viewSwitch}>
            {["day", "week", "month"].map((m) => (
              <button key={m} type="button" onClick={() => applyViewMode(m)} style={viewMode === m ? S.viewBtnActive : S.viewBtn}>
                {m === "day" ? "Jour" : m === "week" ? "Semaine" : "Mois"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {urlFocus === "prises-jour" ? (
        <div
          id="agenda-focus-prises-jour"
          style={{
            marginBottom: 16,
            padding: "14px 16px",
            borderRadius: 14,
            border: `1px solid ${TEAL}44`,
            background: "#ecfdf5",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div>
              <strong style={{ color: TEAL_DARK, fontSize: 15 }}>
                Prises de RDV aujourd&apos;hui
              </strong>
              <p style={{ margin: "6px 0 0", color: MUTED, fontSize: 13 }}>
                Confirmations enregistrées aujourd&apos;hui (Clara, page publique, cabinet). Les créneaux réservés apparaissent dans la semaine ci-dessous.
              </p>
            </div>
            <span style={{ fontWeight: 800, color: TEAL_DARK, fontSize: 22 }}>
              {bookingsTodayPanel.loading ? "…" : bookingsTodayPanel.items.length}
            </span>
          </div>
          {!bookingsTodayPanel.loading && bookingsTodayPanel.items.length > 0 ? (
            <ul style={{ listStyle: "none", margin: "12px 0 0", padding: 0, display: "grid", gap: 8 }}>
              {bookingsTodayPanel.items.slice(0, 8).map((item) => {
                const when = String(item.created_at || "");
                const timeLabel = when
                  ? new Date(when).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
                  : "";
                const sourceLabel =
                  String(item.source || "").toLowerCase() === "clara"
                    ? "Clara"
                    : String(item.source || "").toLowerCase().includes("public")
                      ? "Page publique"
                      : "Cabinet";
                return (
                  <li
                    key={String(item.id)}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 10,
                      padding: "10px 12px",
                      borderRadius: 10,
                      background: "#fff",
                      border: `1px solid ${BORDER}`,
                      fontSize: 13,
                    }}
                  >
                    <span>
                      <strong>{item.patient_name || "Patient"}</strong>
                      {item.slot_label ? ` · ${item.slot_label}` : ""}
                      {item.motif ? ` · ${item.motif}` : ""}
                    </span>
                    <span style={{ color: MUTED, whiteSpace: "nowrap" }}>
                      {timeLabel ? `${timeLabel} · ` : ""}{sourceLabel}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {!bookingsTodayPanel.loading && bookingsTodayPanel.items.length === 0 ? (
            <p style={{ margin: "12px 0 0", color: MUTED, fontSize: 13 }}>Aucune confirmation enregistrée aujourd&apos;hui.</p>
          ) : null}
        </div>
      ) : null}
      <div className="agenda-legend-row" style={S.legendRow}>
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
      <div style={{ ...S.calendarCol, position: "relative" }}>
        {calendarLoading ? (
          <div style={S.calendarLoadingOverlay} aria-busy="true">
            <div style={S.loadingBox}>Chargement de l&apos;agenda…</div>
          </div>
        ) : null}

        {/* ═══ MONTH VIEW ═══ */}
        {viewMode === "month" && (
          <div className="agenda-month-layout" style={S.monthLayout}>
            <div className="agenda-month-card" style={S.card}>
              {isMobileAgenda ? (
                <AgendaMonthMobileView
                  monthGrid={monthGrid}
                  currentMonth={currentMonth}
                  appointmentsByDate={appointmentsByDate}
                  selectedDate={selectedDate}
                  today={today}
                  onSelectDate={selectAgendaDay}
                  onOpenDayView={openDayView}
                  onToggleAppt={toggleAppt}
                  selectedAppt={selectedAppt}
                  monthCounts={monthCounts}
                  styles={S}
                />
              ) : (
              <div className="agenda-month-grid-wrap" style={S.monthGridWrap}>
              {WEEKDAY_LABELS.map((wd) => (
                <div key={wd} style={S.monthWdHeader}>{wd}</div>
              ))}
              {monthGrid.map((d, idx) => {
                const isCurrentMonth = getMonthFromDate(d) === currentMonth;
                const isToday = d === today;
                const dayAppts = appointmentsByDate[d] || [];
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
                      onClick={() => openDayView(d)}
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
                        <button type="button" onClick={() => openDayView(d)} style={S.monthOverflow}>
                          +{overflow} autre{overflow > 1 ? "s" : ""}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
              </div>
              )}
            </div>
            {!isMobileAgenda ? (
            <div style={S.monthSide}>
              <AgendaDateNavPanel
                selectedDate={selectedDate}
                viewMode={viewMode}
                apptCountByDate={apptCountByDate}
                onSelectDate={applyAgendaDate}
                onViewMode={applyViewMode}
                onGoToday={goToday}
                onShift={shiftAgendaPeriod}
                styles={S}
              />
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Mois en cours</div>
                <div className="agenda-side-head-title" style={S.sideHeadTitle}>Synthèse du mois</div>
                <div style={S.sideHeadSub}>Vue globale des performances et priorités du mois en cours.</div>
                <div style={S.sideList}>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.green.border }} /><div><div style={S.sideRowTitle}>{monthCounts.confirmed} confirmés</div><div style={S.sideRowSub}>Patients confirmés sur le mois</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.orange.border }} /><div><div style={S.sideRowTitle}>{monthCounts.pending} à confirmer</div><div style={S.sideRowSub}>Relances Clara à finaliser</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.red.border }} /><div><div style={S.sideRowTitle}>{monthCounts.urgent} urgences</div><div style={S.sideRowSub}>Demandes prioritaires détectées</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.purple.border }} /><div><div style={S.sideRowTitle}>{monthCounts.recovered} créneaux récupérés</div><div style={S.sideRowSub}>Slots sauvés par Clara</div></div></div>
                </div>
              </div>
              <div style={S.sideCard}>
                <div className="agenda-side-card-title" style={S.sideCardTitle}>Actions du mois</div>
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
            ) : (
              <div style={S.mobileSideCompact}>
                <div style={S.sideCard}>
                  <div style={S.mobileSideTitle}>Jours les plus chargés</div>
                  <div style={S.loadList}>
                    {monthTopDays.slice(0, 4).map((row) => (
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
            )}
          </div>
        )}

        {/* ═══ WEEK VIEW ═══ */}
        {viewMode === "week" && (
          <div className="agenda-week-layout" style={S.weekLayout}>
            <div style={S.card}>
              {isMobileAgenda ? (
                <AgendaWeekMobileList
                  weekDates={weekDates}
                  appointments={appointments}
                  today={today}
                  selectedDate={selectedDate}
                  onSelectDay={selectAgendaDay}
                  onOpenDayView={openDayView}
                  onToggleAppt={toggleAppt}
                  selectedAppt={selectedAppt}
                  semanticCounts={semanticCounts}
                  styles={S}
                />
              ) : (
              <>
              <div style={S.weekHead}>
                <div>
                  <div className="agenda-week-head-title" style={S.weekHeadTitle}>Vue semaine — vraie grille de rendez-vous</div>
                  <div style={S.weekHeadSub}>Clique colonne : affiche les créneaux, patients, alertes et actions Clara.</div>
                </div>
                <div style={S.weekHeadBadges}>
                  <span style={S.weekHeadBadgeRed}>Prioritaire {semanticCounts.red}</span>
                  <span style={S.weekHeadBadgeOrange}>À confirmer {semanticCounts.orange}</span>
                  <span style={S.weekHeadBadgePurple}>Récupéré {semanticCounts.purple}</span>
                </div>
              </div>
              <div className="agenda-week-scroll" style={S.weekScroll}>
                <div className="agenda-week-scroll-hint">Glissez pour parcourir la semaine →</div>
                <div className="agenda-week-grid" style={{ ...S.weekGrid, gridTemplateColumns: `54px repeat(${weekDates.length}, minmax(116px, 1fr))` }}>
                  <div className="agenda-week-time-sticky" style={S.weekCorner} />
                  {weekDates.map((d) => {
                    const { wd, num } = formatShortDay(d);
                    const isToday = d === today;
                    const isSelected = d === selectedDate;
                    return (
                      <button key={d} type="button" onClick={() => openDayView(d)} style={{ ...S.weekDayHeader, ...(isToday ? S.weekDayToday : isSelected ? S.weekDaySelected : {}) }}>
                        <span style={S.weekDayLabel}>{wd}</span>
                        <span style={{ ...S.weekDayNum, ...(isToday ? { color: BLUE } : {}) }}>{num}</span>
                        {isToday && <span style={S.todayDot} />}
                      </button>
                    );
                  })}
                  {hours.map((hour) => (
                    <Fragment key={hour}>
                      <div className="agenda-week-time-sticky" style={S.weekTimeCell}><span style={S.weekTimeLabel}>{hour}</span></div>
                      {weekDates.map((d, dayIdx) => {
                        const cellAppts = appointmentsByDateHour[`${d}|${hour}`] || [];
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
              </>
              )}
            </div>
            {!isMobileAgenda ? (
            <div style={S.weekSide}>
              <AgendaDateNavPanel
                selectedDate={selectedDate}
                viewMode={viewMode}
                apptCountByDate={apptCountByDate}
                onSelectDate={applyAgendaDate}
                onViewMode={applyViewMode}
                onGoToday={goToday}
                onShift={shiftAgendaPeriod}
                styles={S}
              />
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Semaine en cours</div>
                <div className="agenda-side-head-title" style={S.sideHeadTitle}>6 actions qui comptent</div>
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
                <div className="agenda-side-card-title" style={S.sideCardTitle}>Charge réelle</div>
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
            ) : (
              <div style={S.mobileSideCompact}>
                <div style={S.sideCard}>
                  <div style={S.mobileSideTitle}>Charge de la semaine</div>
                  <div style={S.loadList}>
                    {weekLoadRows.slice(0, 5).map((row) => (
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
            )}
          </div>
        )}

        {/* ═══ DAY VIEW ═══ */}
        {viewMode === "day" && (
          <div className="agenda-day-layout" style={S.dayLayout}>
            <div style={S.card}>
              <div style={S.dayTimeline}>
                {hours.map((hour) => {
                  const hourAppts = appointmentsByDateHour[`${selectedDate}|${hour}`] || [];
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
                                <button
                                  type="button"
                                  className="agenda-appt-card"
                                  onClick={() => toggleAppt(a)}
                                  style={{
                                    ...S.dayCard,
                                    background: tone.bg,
                                    borderLeftColor: tone.border,
                                    ...(isOpen ? { boxShadow: `0 0 0 2px ${tone.border}55`, zIndex: 1 } : {}),
                                  }}
                                >
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
              {!isMobileAgenda ? (
                <AgendaDateNavPanel
                  selectedDate={selectedDate}
                  viewMode={viewMode}
                  apptCountByDate={apptCountByDate}
                  onSelectDate={applyAgendaDate}
                  onViewMode={applyViewMode}
                  onGoToday={goToday}
                  onShift={shiftAgendaPeriod}
                  styles={S}
                />
              ) : null}
              <div style={S.sideCardPrimary}>
                <div style={S.sideHeadLabel}>Journée en cours</div>
                <div className="agenda-side-head-title" style={S.sideHeadTitle}>Résumé de la journée</div>
                <div style={S.sideHeadSub}>Synthèse rapide des rendez-vous du jour et priorités à traiter.</div>
                <div style={S.sideList}>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.green.border }} /><div><div style={S.sideRowTitle}>{dayCounts.confirmed} confirmés</div><div style={S.sideRowSub}>Patients confirmés aujourd'hui</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.orange.border }} /><div><div style={S.sideRowTitle}>{dayCounts.pending} à confirmer</div><div style={S.sideRowSub}>Relances Clara en attente</div></div></div>
                  <div style={S.sideRow}><span style={{ ...S.sideDot, background: APPT_TONE.red.border }} /><div><div style={S.sideRowTitle}>{dayCounts.urgent} urgences</div><div style={S.sideRowSub}>Demandes prioritaires du jour</div></div></div>
                </div>
              </div>
              <div style={S.sideCard}>
                <div className="agenda-side-card-title" style={S.sideCardTitle}>Détail du jour</div>
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

      {selectedAppt ? (
        <div
          style={S.apptDetailOverlay}
          role="presentation"
          onClick={closeAppointmentDetail}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={apptPanel === "create-patient" ? "create-patient-from-call-heading" : "appt-detail-heading"}
            style={S.apptDetailCard}
            onClick={(e) => e.stopPropagation()}
          >
            {apptPanel === "create-patient" ? (
              <CreatePatientFromCallModal
                embedded
                open
                showEmail
                emailRequired
                extendedProfile
                loading={patientCreateLoading}
                form={patientCreateForm}
                phoneError={patientCreatePhoneError}
                emailError={patientCreateEmailError}
                birthDateError={patientCreateBirthDateError}
                physicianNameError={patientCreatePhysicianNameError}
                physicianCityError={patientCreatePhysicianCityError}
                submitDisabled={patientCreateSubmitBlocked}
                onChange={(field, value) => setPatientCreateForm((prev) => ({ ...prev, [field]: value }))}
                onClose={closeAppointmentDetail}
                onBack={() => setApptPanel("detail")}
                onSubmit={handlePatientCreateFromAgendaSubmit}
                subtitleLine={
                  <>
                    {patientCreateConflicts.length ? (
                      <PatientDuplicateBanner conflicts={patientCreateConflicts} className="mb-3" />
                    ) : null}
                    <span className="text-[#64748B]">
                      Source : <strong>rendez-vous agenda</strong>
                      {patientCreateSummary ? (
                        <>
                          {" "}
                          · <span>{patientCreateSummary}</span>
                        </>
                      ) : null}
                    </span>
                  </>
                }
              />
            ) : (
              <>
                <div style={S.apptDetailHeader}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flex: 1 }}>
                    <span style={{ fontSize: 22, lineHeight: 1 }}>{selectedAppt.typeIcon}</span>
                    <div>
                      <div id="appt-detail-heading" style={{ fontSize: 17, fontWeight: 800, color: NAVY }}>
                        {selectedAppt.patient || "Patient"}
                      </div>
                      <div style={{ fontSize: 13, color: MUTED, marginTop: 2 }}>
                        {selectedAppt.type || "Consultation"}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={closeAppointmentDetail}
                    style={S.weekDetailClose}
                    aria-label="Fermer la fiche rendez-vous"
                  >
                    ✕
                  </button>
                </div>
                <InlineDetail
                  variant="modal"
                  a={selectedAppt}
                  navigate={navigate}
                  confirmCancel={confirmCancel}
                  setConfirmCancel={setConfirmCancel}
                  handleCancel={handleCancel}
                  actionLoading={actionLoading}
                  rescheduleMode={rescheduleMode}
                  onStartReschedule={handleStartReschedule}
                  onReschedule={handleReschedule}
                  onViewPatientFile={viewPatientFileFromSelectedAppt}
                  onCreatePatientFile={() => openCreatePatientFormFromAppt(selectedAppt)}
                  onCreateConsultation={() => openConsultationSheetFromSelectedAppt(selectedAppt)}
                />
              </>
            )}
          </div>
        </div>
      ) : null}

      {createBookingOpen ? (
        <div style={S.modalOverlay} role="dialog" aria-modal="true">
          <div style={S.modalCardWide}>
            <div style={S.modalTitleRow}>
              <span style={{ fontWeight: 800 }}>Créer un rendez-vous</span>
              <button
                type="button"
                style={S.modalClose}
                onClick={() => {
                  setCreateBookingOpen(false);
                  setCreateBookingError("");
                }}
                aria-label="Fermer"
              >
                ✕
              </button>
            </div>
            <p style={{ margin: "0 0 14px", fontSize: 13, color: MUTED, lineHeight: 1.45 }}>
              Ce RDV est enregistré comme créé depuis l&apos;espace cabinet. En saisissant le nom, le numéro ou
              l&apos;email d&apos;un patient déjà en base, une suggestion permet de préremplir la fiche. Avec
              Google&nbsp;Calendar, la durée suit les réglages du cabinet.
            </p>

            {(createBookingSuggestLoading || (createBookingSuggestions && createBookingSuggestions.length > 0)) ? (
              <div style={S.modalSuggestBox}>
                {createBookingSuggestLoading ? (
                  <div style={S.modalSuggestHint}>Recherche des patients correspondants…</div>
                ) : null}
                {!createBookingSuggestLoading && createBookingSuggestions?.length ? (
                  <div style={S.modalSuggestList}>
                    <div style={S.modalSuggestListLabel}>Patients correspondants</div>
                    {createBookingSuggestions.map((p, idx) => {
                      const label = (p.display_name || p.validated_name || p.raw_name || "Patient").trim();
                      const sub = [(p.phone || "").trim(), (p.email || "").trim()].filter(Boolean).join(" · ");
                      const key = (p.phone || label) + (sub || "") + String(idx);
                      return (
                        <button
                          key={key}
                          type="button"
                          style={{
                            ...S.modalSuggestBtn,
                            borderTop: idx === 0 ? "none" : S.modalSuggestBtn.borderTop,
                          }}
                          onMouseDown={(e) => {
                            e.preventDefault();
                            applyCreateBookingPatient(p);
                          }}
                        >
                          <span style={S.modalSuggestMain}>{label}</span>
                          {sub ? <span style={S.modalSuggestMeta}>{sub}</span> : null}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}

            <label style={S.modalLabel}>
              Nom du patient *
              <input
                style={S.modalInput}
                value={createBookingForm.patient_name}
                onChange={(e) => setCreateBookingForm((p) => ({ ...p, patient_name: e.target.value }))}
                autoComplete="name"
              />
            </label>
            <label style={S.modalLabel}>
              Téléphone
              <input
                style={{
                  ...S.modalInput,
                  ...(createBookingPhoneError ? S.modalInputInvalid : {}),
                }}
                value={createBookingForm.patient_phone}
                onChange={(e) => setCreateBookingForm((p) => ({ ...p, patient_phone: e.target.value }))}
                autoComplete="tel"
                inputMode="tel"
                placeholder="ex. 06 12 34 56 78"
                aria-invalid={createBookingPhoneError ? "true" : undefined}
              />
              {createBookingPhoneError ? (
                <span style={S.modalFieldError}>{createBookingPhoneError}</span>
              ) : (
                <span style={S.modalFieldHint}>Format : 06 12 34 56 78 ou +33 6 12 34 56 78</span>
              )}
            </label>
            <label style={S.modalLabel}>
              E-mail (optionnel)
              <input
                type="email"
                style={{
                  ...S.modalInput,
                  ...(createBookingEmailError ? S.modalInputInvalid : {}),
                }}
                value={createBookingForm.patient_email}
                onChange={(e) => setCreateBookingForm((p) => ({ ...p, patient_email: e.target.value }))}
                autoComplete="email"
                placeholder="ex. patient@gmail.com"
                aria-invalid={createBookingEmailError ? "true" : undefined}
              />
              {createBookingEmailError ? (
                <span style={S.modalFieldError}>{createBookingEmailError}</span>
              ) : (
                <span style={S.modalFieldHint}>Si renseigné : prenom@domaine.fr (sans espace)</span>
              )}
            </label>
            {createBookingConflicts.length ? (
              <PatientDuplicateBanner conflicts={createBookingConflicts} className="mb-3" />
            ) : null}
            <label style={S.modalLabel}>
              Motif
              <input
                style={S.modalInput}
                value={createBookingForm.motif}
                onChange={(e) => setCreateBookingForm((p) => ({ ...p, motif: e.target.value }))}
              />
            </label>
            <div style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: "block", marginBottom: 8 }}>
                Date et horaire *
              </span>
              <p style={{ margin: "0 0 10px", fontSize: 12, color: MUTED, lineHeight: 1.4 }}>
                D&apos;abord la date avec le sélecteur de jour du navigateur, puis l&apos;heure dans une liste courte
                (pas sous la forme 24/05/2026 09:00). Les créneaux suivent vos horaires cabinet et la durée des RDV.
              </p>
              <div style={S.modalDatetimeRow}>
                <label style={S.modalDatetimeCol}>
                  <span style={{ display: "block", fontSize: 11, fontWeight: 800, color: MUTED, marginBottom: 6 }}>Jour</span>
                  <input
                    type="date"
                    style={S.modalInput}
                    min={todayISO()}
                    value={createBookingForm.booking_date}
                    onChange={(e) => setCreateBookingForm((p) => ({ ...p, booking_date: e.target.value }))}
                  />
                </label>
                <label style={S.modalDatetimeCol}>
                  <span style={{ display: "block", fontSize: 11, fontWeight: 800, color: MUTED, marginBottom: 6 }}>Heure</span>
                  <select
                    style={{ ...S.modalInput, ...S.modalSelect }}
                    value={
                      cabinetBookingTimeChoices.includes(createBookingForm.booking_time)
                        ? createBookingForm.booking_time
                        : (cabinetBookingTimeChoices[0] || "")
                    }
                    onChange={(e) => setCreateBookingForm((p) => ({ ...p, booking_time: e.target.value }))}
                  >
                    {cabinetBookingTimeChoices.map((t) => (
                      <option key={t} value={t}>{formatTimeChoiceFR(t)}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            {!cabinetBookingFormValid && createBookingSubmitHint ? (
              <p style={S.modalSubmitHint} role="status">
                {createBookingSubmitHint}
              </p>
            ) : null}
            {createBookingError ? (
              <p style={S.modalFieldError} role="alert">
                {createBookingError}
              </p>
            ) : null}
            <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
              <button
                type="button"
                style={{ ...S.createRdvBtn, flex: 1, fontSize: 13, ...(cabinetBookingFormValid ? {} : { opacity: 0.55, cursor: "not-allowed" }) }}
                disabled={createBookingLoading || !cabinetBookingFormValid}
                onClick={handleCreateCabinetBookingSubmit}
              >
                {createBookingLoading ? "…" : "Enregistrer le rendez-vous"}
              </button>
              <button type="button" style={S.todayBtn} onClick={() => setCreateBookingOpen(false)}>
                Annuler
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {cancelBookingConfirm ? (
        <div
          style={S.bookingConfirmOverlay}
          role="dialog"
          aria-modal="true"
          aria-labelledby="cancel-confirm-title"
        >
          <div style={S.bookingConfirmCard}>
            <div style={S.bookingConfirmIcon} aria-hidden>✓</div>
            <div id="cancel-confirm-title" style={S.bookingConfirmTitle}>
              Rendez-vous annulé
            </div>
            <p style={S.bookingConfirmLead}>
              Le rendez-vous du <strong>{cancelBookingConfirm.whenLine}</strong> de{" "}
              <strong>{cancelBookingConfirm.patientName}</strong> a bien été annulé.
            </p>
            <button
              type="button"
              style={S.bookingConfirmBtn}
              onClick={() => setCancelBookingConfirm(null)}
            >
              OK
            </button>
          </div>
        </div>
      ) : null}

      {createBookingConfirm ? (
        <div
          style={S.bookingConfirmOverlay}
          role="dialog"
          aria-modal="true"
          aria-labelledby="booking-confirm-title"
        >
          <div style={S.bookingConfirmCard}>
            <div style={S.bookingConfirmIcon} aria-hidden>✓</div>
            <div id="booking-confirm-title" style={S.bookingConfirmTitle}>
              Rendez-vous enregistré
            </div>
            <p style={S.bookingConfirmLead}>
              Le rendez-vous de <strong>{createBookingConfirm.patientName}</strong> a bien été créé depuis
              l&apos;espace cabinet.
            </p>
            <ul style={S.bookingConfirmMeta}>
              <li style={S.bookingConfirmMetaRow}>
                <span style={S.bookingConfirmMetaLbl}>Date et heure</span>
                <span style={S.bookingConfirmMetaVal}>{createBookingConfirm.whenLine}</span>
              </li>
              <li style={S.bookingConfirmMetaRow}>
                <span style={S.bookingConfirmMetaLbl}>Motif</span>
                <span style={S.bookingConfirmMetaVal}>{createBookingConfirm.motif}</span>
              </li>
            </ul>
            {createBookingConfirm.needsPatientFile ? (
              <div style={S.bookingConfirmNoFileBox}>
                <p style={S.bookingConfirmNoFileLead}>
                  Pas encore de fiche patient pour ce numéro.
                </p>
                <button
                  type="button"
                  style={S.bookingConfirmCtaPatient}
                  onClick={() => handleCreatePatientFromBookingConfirm(createBookingConfirm)}
                >
                  Créer sa fiche patient
                </button>
              </div>
            ) : null}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <button
                type="button"
                style={S.bookingConfirmSecondaryBtn}
                onClick={() => handleViewBookingInAgenda(createBookingConfirm)}
              >
                Voir ce rendez-vous dans l&apos;agenda
              </button>
              <button
                type="button"
                style={S.bookingConfirmBtn}
                onClick={() => setCreateBookingConfirm(null)}
              >
                {createBookingConfirm.needsPatientFile ? "Valider sans créer de fiche" : "OK"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}

const S = {
  page: { minHeight: "100%", background: "#F6F8FB", fontFamily: "'Inter', 'DM Sans', sans-serif", color: NAVY, padding: "18px 24px 36px", maxWidth: 1280, margin: "0 auto" },

  loadingBox: { padding: 40, textAlign: "center", fontSize: 14, color: MUTED },
  calendarLoadingOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 2,
    display: "grid",
    placeItems: "center",
    background: "rgba(246,248,251,.82)",
    backdropFilter: "blur(2px)",
    borderRadius: 16,
    minHeight: 220,
  },
  errorBox: { marginBottom: 14, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 14px", fontSize: 14, fontWeight: 600 },
  errorRetryBtn: { marginLeft: 8, padding: "4px 10px", borderRadius: 8, border: "1px solid #fca5a5", background: "#fff", color: "#b91c1c", fontSize: 13, fontWeight: 700, cursor: "pointer" },
  toast: { marginBottom: 14, borderRadius: 10, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", padding: "12px 16px", fontSize: 14, fontWeight: 700, animation: "toastIn .3s ease" },
  toastError: { marginBottom: 14, borderRadius: 10, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 16px", fontSize: 14, fontWeight: 700, animation: "toastIn .3s ease" },

  bookingConfirmOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(15,23,42,.5)",
    display: "grid",
    placeItems: "center",
    zIndex: 65,
    padding: 16,
  },
  bookingConfirmCard: {
    width: "min(400px, 100%)",
    borderRadius: 18,
    padding: "24px 22px 20px",
    background: "linear-gradient(165deg, #ecfdf5 0%, #d1fae5 45%, #fff 100%)",
    border: "2px solid #10b981",
    boxShadow: "0 24px 48px rgba(16,185,129,.22), 0 8px 24px rgba(15,23,42,.12)",
    textAlign: "center",
  },
  bookingConfirmIcon: {
    width: 52,
    height: 52,
    margin: "0 auto 12px",
    borderRadius: "50%",
    background: "#10b981",
    color: "#fff",
    fontSize: 28,
    fontWeight: 900,
    display: "grid",
    placeItems: "center",
    lineHeight: 1,
    boxShadow: "0 8px 20px rgba(16,185,129,.45)",
  },
  bookingConfirmTitle: { fontSize: 20, fontWeight: 900, color: "#065f46", letterSpacing: "-.02em", marginBottom: 8 },
  bookingConfirmLead: { margin: "0 0 16px", fontSize: 14, color: "#047857", lineHeight: 1.5, textAlign: "left" },
  bookingConfirmMeta: {
    listStyle: "none",
    margin: "0 0 20px",
    padding: 12,
    borderRadius: 12,
    background: "rgba(255,255,255,.75)",
    border: "1px solid #a7f3d0",
    textAlign: "left",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  bookingConfirmMetaRow: { display: "flex", flexDirection: "column", gap: 4 },
  bookingConfirmMetaLbl: { fontSize: 11, fontWeight: 800, color: MUTED, textTransform: "uppercase", letterSpacing: "0.05em" },
  bookingConfirmMetaVal: { fontSize: 15, fontWeight: 700, color: NAVY },
  bookingConfirmBtn: {
    width: "100%",
    padding: "12px 16px",
    borderRadius: 12,
    border: "none",
    background: "#059669",
    color: "#fff",
    fontSize: 15,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 6px 18px rgba(5,150,105,.35)",
  },
  bookingConfirmSecondaryBtn: {
    width: "100%",
    padding: "11px 16px",
    borderRadius: 12,
    border: "2px solid #059669",
    background: "#fff",
    color: "#047857",
    fontSize: 14,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    boxSizing: "border-box",
  },
  bookingConfirmNoFileBox: {
    marginBottom: 14,
    padding: "12px 14px",
    borderRadius: 12,
    background: "rgba(254,243,199,0.95)",
    border: "1px solid #fcd34d",
    textAlign: "left",
  },
  bookingConfirmNoFileLead: {
    margin: "0 0 10px",
    fontSize: 13,
    fontWeight: 700,
    color: "#92400e",
    lineHeight: 1.45,
  },
  bookingConfirmCtaPatient: {
    width: "100%",
    padding: "10px 14px",
    borderRadius: 10,
    border: "2px solid #b45309",
    background: "#fff",
    color: "#92400e",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    boxSizing: "border-box",
  },

  modalOverlay: { position: "fixed", inset: 0, background: "rgba(15,23,42,.45)", display: "grid", placeItems: "center", zIndex: 60, padding: 16 },
  apptDetailOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(15,23,42,.45)",
    display: "grid",
    placeItems: "center",
    zIndex: 62,
    padding: 16,
    boxSizing: "border-box",
  },
  apptDetailCard: {
    width: "min(460px, 100%)",
    maxHeight: "min(88vh, 760px)",
    overflowY: "auto",
    overflowX: "hidden",
    WebkitOverflowScrolling: "touch",
    background: "#fff",
    borderRadius: 18,
    boxShadow: "0 28px 72px rgba(15,23,42,.3)",
    border: `1px solid ${BORDER}`,
  },
  apptDetailHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    padding: "16px 16px 12px",
    position: "sticky",
    top: 0,
    zIndex: 2,
    background: "#fff",
    borderBottom: `1px solid ${BORDER}`,
  },
  modalCard: { width: "min(420px, 100%)", background: "#fff", borderRadius: 16, padding: "20px 22px", boxShadow: "0 24px 60px rgba(15,23,42,.18)", border: `1px solid ${BORDER}` },
  modalCardWide: { width: "min(480px, 100%)", background: "#fff", borderRadius: 16, padding: "20px 22px", boxShadow: "0 24px 60px rgba(15,23,42,.18)", border: `1px solid ${BORDER}` },
  modalTitleRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  modalClose: { border: "none", background: "transparent", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 4, color: MUTED },
  modalLabel: { display: "block", fontSize: 12, fontWeight: 700, color: NAVY, marginBottom: 10 },
  modalInput: { display: "block", width: "100%", marginTop: 6, padding: "10px 11px", borderRadius: 10, border: `1px solid ${BORDER}`, fontSize: 14, boxSizing: "border-box", fontFamily: "inherit" },
  modalInputInvalid: { borderColor: "#F87171", background: "#FEF2F2" },
  modalFieldError: { display: "block", marginTop: 6, fontSize: 11, fontWeight: 700, color: "#DC2626", lineHeight: 1.4 },
  modalFieldHint: { display: "block", marginTop: 6, fontSize: 11, fontWeight: 500, color: MUTED, lineHeight: 1.4 },
  modalSubmitHint: {
    margin: "14px 0 0",
    padding: "10px 12px",
    borderRadius: 10,
    border: "1px solid #FDE68A",
    background: "#FFFBEB",
    fontSize: 12,
    fontWeight: 600,
    color: "#92400E",
    lineHeight: 1.45,
  },
  modalSelect: { cursor: "pointer", backgroundColor: "#fff", WebkitAppearance: "none", appearance: "none", backgroundImage: "linear-gradient(45deg, transparent 50%, #64748b 50%), linear-gradient(135deg, #64748b 50%, transparent 50%)", backgroundPosition: "calc(100% - 18px) 50%, calc(100% - 13px) 50%", backgroundSize: "6px 6px, 6px 6px", backgroundRepeat: "no-repeat", paddingRight: 36 },
  modalDatetimeRow: { display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" },
  modalDatetimeCol: { flex: "1 1 160px", minWidth: 140 },
  modalSuggestBox: { marginBottom: 14 },
  modalSuggestHint: { fontSize: 12, color: TEAL_DARK, fontWeight: 600, marginBottom: 8 },
  modalSuggestList: { borderRadius: 12, border: `1px solid ${BORDER}`, overflow: "hidden", background: "#f8fafc" },
  modalSuggestListLabel: {
    padding: "8px 10px",
    fontSize: 11,
    fontWeight: 800,
    color: MUTED,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    background: "#f1f5f9",
  },
  modalSuggestBtn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
    gap: 2,
    width: "100%",
    textAlign: "left",
    padding: "10px 12px",
    border: "none",
    borderTop: `1px solid ${BORDER}`,
    background: "#fff",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  modalSuggestMain: { fontSize: 14, fontWeight: 700, color: NAVY },
  modalSuggestMeta: { fontSize: 12, fontWeight: 600, color: MUTED },

  header: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 16, flexWrap: "wrap" },
  title: { margin: 0, fontSize: 20, fontWeight: 800, color: NAVY },
  subtitle: { margin: "4px 0 0", fontSize: 13, color: MUTED },
  headerRight: { display: "flex", gap: 8 },
  toolbar: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16, flexWrap: "wrap", padding: "12px 16px", background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 18, boxShadow: "0 8px 26px rgba(15,23,42,.05)" },
  toolbarLeft: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  toolbarRight: { display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" },
  toolbarDateJump: { position: "relative", display: "inline-flex", alignItems: "center", cursor: "pointer" },
  toolbarDateInput: {
    position: "absolute",
    inset: 0,
    opacity: 0,
    width: "100%",
    height: "100%",
    cursor: "pointer",
  },
  dateNavPanel: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
    marginBottom: 4,
  },
  dateJumpLabel: {
    display: "grid",
    gap: 6,
    fontSize: 12,
    fontWeight: 700,
    color: MUTED,
  },
  dateJumpInput: {
    height: 38,
    borderRadius: 10,
    border: `1px solid ${BORDER}`,
    padding: "0 10px",
    fontSize: 13,
    fontWeight: 600,
    color: NAVY,
    fontFamily: "inherit",
  },
  dateNavQuickRow: { display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 8 },
  dateNavQuickBtn: {
    height: 36,
    borderRadius: 10,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: NAVY,
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  dateNavTodayBtn: {
    height: 36,
    borderRadius: 10,
    border: `1px solid ${TEAL}`,
    background: "#ECFDF5",
    color: TEAL_DARK,
    fontSize: 12,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    padding: "0 10px",
  },
  dateNavViewRow: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 6 },
  dateNavViewBtn: {
    height: 34,
    borderRadius: 10,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: MUTED,
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  dateNavViewBtnActive: {
    height: 34,
    borderRadius: 10,
    border: `1px solid ${BLUE}`,
    background: "#EFF6FF",
    color: BLUE,
    fontSize: 12,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  dateNavHint: { margin: 0, fontSize: 11, color: MUTED, lineHeight: 1.4 },
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
  createRdvBtn: {
    padding: "8px 14px",
    borderRadius: 10,
    border: "none",
    background: BLUE,
    color: "#fff",
    fontSize: 12,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "normal",
    textAlign: "center",
    boxShadow: "0 6px 16px rgba(37,99,235,.38)",
    lineHeight: 1.2,
    minHeight: 36,
    maxWidth: 220,
  },

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

  mobileSideCompact: { display: "flex", flexDirection: "column", gap: 12 },
  mobileSideTitle: { fontSize: 16, fontWeight: 900, color: NAVY, marginBottom: 10, letterSpacing: "-.02em" },

  weekMobileStrip: {
    display: "flex",
    gap: 8,
    overflowX: "auto",
    padding: "12px 12px 4px",
    WebkitOverflowScrolling: "touch",
    scrollbarWidth: "none",
  },
  weekMobileDayChip: {
    flex: "0 0 auto",
    minWidth: 58,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#fff",
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  weekMobileDayChipToday: { borderColor: "#93c5fd", background: "#eff6ff" },
  weekMobileDayChipSelected: { borderColor: "#14b8a6", background: "#ecfdf5", boxShadow: "0 0 0 2px rgba(20,184,166,.18)" },
  weekMobileDayChipWd: { fontSize: 10, fontWeight: 800, color: MUTED, letterSpacing: "0.06em" },
  weekMobileDayChipNum: { fontSize: 18, fontWeight: 900, color: NAVY, lineHeight: 1 },
  weekMobileDayChipCount: {
    marginTop: 2,
    fontSize: 10,
    fontWeight: 800,
    color: "#0f766e",
    background: "#ecfdf5",
    borderRadius: 999,
    padding: "1px 6px",
  },
  weekMobileBadges: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
    padding: "8px 12px 12px",
    borderBottom: `1px solid ${BORDER}`,
  },
  weekMobileDaySection: {
    borderBottom: `1px solid ${BORDER}`,
    background: "#fff",
  },
  weekMobileDaySectionSelected: { background: "#f8fffe" },
  weekMobileDayHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    padding: "12px 12px 8px",
  },
  weekMobileDayHeaderMain: {
    border: "none",
    background: "transparent",
    padding: 0,
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    flex: 1,
    minWidth: 0,
  },
  weekMobileDayTitle: { display: "flex", alignItems: "center", gap: 8, fontSize: 16, fontWeight: 900, color: NAVY },
  weekMobileTodayBadge: {
    fontSize: 10,
    fontWeight: 800,
    color: BLUE,
    background: "#eff6ff",
    borderRadius: 999,
    padding: "2px 8px",
  },
  weekMobileDaySub: { marginTop: 2, fontSize: 12, color: MUTED, fontWeight: 600 },
  weekMobileDayMeta: { display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 },
  weekMobileOpenDayBtn: {
    border: `1px solid ${BORDER}`,
    borderRadius: 10,
    background: "#fff",
    color: BLUE,
    fontSize: 11,
    fontWeight: 800,
    padding: "6px 10px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  weekMobileEmpty: { padding: "8px 12px 14px", fontSize: 13, color: MUTED, fontWeight: 600 },
  weekMobileApptList: { display: "flex", flexDirection: "column", gap: 8, padding: "0 12px 14px" },
  weekMobileApptCard: {
    width: "100%",
    textAlign: "left",
    border: "none",
    borderLeft: "3px solid",
    borderRadius: 12,
    padding: "10px 12px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  weekMobileApptTop: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 },
  weekMobileApptTime: { fontSize: 12, fontWeight: 800 },
  weekMobileApptTag: { fontSize: 9, fontWeight: 900, letterSpacing: "0.05em", textTransform: "uppercase" },
  weekMobileApptName: { fontSize: 14, fontWeight: 800, lineHeight: 1.25 },
  weekMobileApptType: { marginTop: 4, fontSize: 12, color: "#475569", fontWeight: 600 },

  monthMobileSummary: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
    padding: 12,
    borderBottom: `1px solid ${BORDER}`,
    background: "#f8fafc",
  },
  monthMobileSummaryItem: {
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    padding: "10px 8px",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  monthMobileGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    gap: 0,
    borderBottom: `1px solid ${BORDER}`,
  },
  monthMobileWd: {
    padding: "8px 0",
    textAlign: "center",
    fontSize: 10,
    fontWeight: 800,
    color: MUTED,
    background: "#f8fafc",
    borderBottom: `1px solid ${BORDER}`,
  },
  monthMobileCell: {
    minHeight: 52,
    border: "none",
    borderRight: `1px solid #f3f4f6`,
    borderBottom: `1px solid #f3f4f6`,
    background: "#fff",
    padding: "4px 2px 6px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  monthMobileCellToday: { background: "#eff6ff" },
  monthMobileCellSelected: { background: "#ecfdf5", boxShadow: "inset 0 0 0 2px rgba(20,184,166,.35)" },
  monthMobileCellNum: { fontSize: 12, fontWeight: 800, color: NAVY, lineHeight: 1 },
  monthMobileDots: { display: "flex", alignItems: "center", justifyContent: "center", gap: 3, minHeight: 8 },
  monthMobileDot: { width: 5, height: 5, borderRadius: "50%", flexShrink: 0 },
  monthMobileDotMore: { fontSize: 8, fontWeight: 900, color: MUTED, lineHeight: 1 },
  monthMobileDayPanel: { padding: "14px 12px 16px" },
  monthMobileDayPanelHead: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 12 },
  monthMobileDayPanelTitle: { fontSize: 16, fontWeight: 900, color: NAVY, letterSpacing: "-.02em" },
  monthMobileDayPanelSub: { marginTop: 2, fontSize: 12, color: MUTED, fontWeight: 600 },

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
  inlineDetailModal: {
    background: "#fff",
    border: "none",
    borderRadius: 0,
    padding: "4px 14px 18px",
    marginBottom: 0,
    boxShadow: "none",
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
  @media (max-width: 1024px) {
    .agenda-kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
    .agenda-week-layout { grid-template-columns: 1fr !important; }
    .agenda-month-layout { grid-template-columns: 1fr !important; }
    .agenda-day-layout { grid-template-columns: 1fr !important; }
    .agenda-week-scroll {
      -webkit-overflow-scrolling: touch;
      scroll-snap-type: x proximity;
    }
    .agenda-week-grid { min-width: 760px !important; }
    .agenda-week-scroll-hint {
      display: block;
      padding: 8px 16px 0;
      font-size: 11px;
      font-weight: 700;
      color: #64748b;
      text-align: center;
    }
    .agenda-week-time-sticky {
      position: sticky;
      left: 0;
      z-index: 2;
      background: #f8fafc !important;
      box-shadow: 8px 0 12px rgba(15, 23, 42, 0.06);
    }
  }
  @media (min-width: 1025px) {
    .agenda-week-scroll-hint { display: none; }
  }
  @media (max-width: 760px) {
    .agenda-page { padding: 12px 10px 24px !important; }
    .agenda-toolbar {
      flex-direction: column !important;
      align-items: stretch !important;
      gap: 10px !important;
    }
    .agenda-toolbar-left,
    .agenda-toolbar-right {
      width: 100% !important;
      display: flex !important;
      flex-wrap: wrap !important;
      gap: 8px !important;
      align-items: center !important;
    }
    .agenda-toolbar-right {
      justify-content: space-between !important;
    }
    .agenda-nav-label {
      flex: 1 1 100% !important;
      text-align: center !important;
      font-size: 14px !important;
      line-height: 1.35 !important;
    }
    .agenda-create-btn {
      flex: 1 1 100% !important;
      justify-content: center !important;
    }
    .agenda-toolbar-left > button,
    .agenda-toolbar-right > button {
      min-height: 38px;
    }
    .agenda-view-switch {
      width: 100% !important;
      display: grid !important;
      grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    }
    .agenda-legend-row {
      flex-wrap: nowrap !important;
      overflow-x: auto !important;
      gap: 8px !important;
      padding-bottom: 2px !important;
    }
    .agenda-legend-row > div {
      flex: 0 0 auto !important;
    }
    .agenda-kpi-row { grid-template-columns: 1fr !important; }
    .agenda-week-head-title {
      font-size: 22px !important;
      line-height: 1.05 !important;
      letter-spacing: -0.02em !important;
    }
    .agenda-side-head-title {
      font-size: 28px !important;
      line-height: 1.02 !important;
      letter-spacing: -0.02em !important;
    }
    .agenda-side-card-title {
      font-size: 24px !important;
      line-height: 1.06 !important;
      letter-spacing: -0.02em !important;
    }
    .agenda-week-layout { grid-template-columns: 1fr !important; }
    .agenda-month-layout { grid-template-columns: 1fr !important; }
    .agenda-day-layout { grid-template-columns: 1fr !important; }
    .agenda-week-mobile-strip::-webkit-scrollbar { display: none; }
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
