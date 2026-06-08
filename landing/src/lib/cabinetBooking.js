import { validatePatientPhone } from "./contactValidation.js";

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function formatTimeChoiceFR(value) {
  const raw = String(value || "").trim();
  const [hRaw, mRaw] = raw.split(":").concat("0");
  const hh = Number.parseInt(String(hRaw), 10);
  const mm = Number.parseInt(String(mRaw), 10);
  if (Number.isNaN(hh) || Number.isNaN(mm)) return raw;
  return `${hh}h${String(mm).padStart(2, "0")}`;
}

/** Date longue en français (ex. « lundi 8 juin 2026 »). */
export function formatLongDateFR(dateStr) {
  const raw = String(dateStr || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const d = new Date(`${raw}T12:00:00`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Créneaux entre deux heures d’ouverture (cabinet). */
export function buildCabinetTimeChoices(loH, hiH, stepMinutes = 15) {
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

export function pickDefaultCabinetTime(slots, preferredHour = 9) {
  if (!slots?.length) return "09:00";
  const want = `${String(preferredHour).padStart(2, "0")}:00`;
  if (slots.includes(want)) return want;
  const after = slots.find((s) => s >= want);
  return after || slots[0];
}

/** ISO local (heure murale) pour l'API agenda. */
export function buildCabinetBookingStartIso(bookingDate, bookingTime) {
  const date = String(bookingDate || "").trim();
  const time = String(bookingTime || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return "";
  return `${date}T${time}:00`;
}

export function validateCabinetBookingPhone(raw) {
  return validatePatientPhone(raw);
}

export function cabinetTimeChoicesFromHoraires(horaires) {
  const duration = Number(horaires?.booking_duration_minutes || 30);
  const cfgStart = Number.isFinite(Number(horaires?.booking_start_hour))
    ? Number(horaires.booking_start_hour)
    : 7;
  const cfgEnd = Number.isFinite(Number(horaires?.booking_end_hour))
    ? Number(horaires.booking_end_hour)
    : 21;
  const step =
    duration >= 15 && duration <= 60 && duration % 5 === 0 ? duration : 15;
  return buildCabinetTimeChoices(cfgStart, cfgEnd, step);
}
