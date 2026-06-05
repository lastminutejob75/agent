const WEEKDAY_TO_KEY = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

/** Date civile locale → YYYY-MM-DD */
export function dateToISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseClockToMinutes(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const match = raw.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function isOpeningDayOpen(row) {
  if (!row || typeof row !== "object") return false;
  if (row.is_open === false || row.is_open === 0 || row.is_open === "0") return false;
  if (row.closed === true) return false;
  return row.is_open === true || row.is_open === 1 || row.is_open === "1" || row.is_open === "true" || row.is_open == null;
}

/** Minutes ouvertes sur une journée (matin + après-midi). */
export function openingRowOpenMinutes(row) {
  if (!isOpeningDayOpen(row)) return 0;
  let total = 0;
  for (const [startRaw, endRaw] of [
    [row.morning_start, row.morning_end],
    [row.afternoon_start, row.afternoon_end],
  ]) {
    const startMin = parseClockToMinutes(startRaw);
    const endMin = parseClockToMinutes(endRaw);
    if (startMin != null && endMin != null && endMin > startMin) total += endMin - startMin;
  }
  if (total === 0) {
    const startMin = parseClockToMinutes(row.start);
    const endMin = parseClockToMinutes(row.end);
    if (startMin != null && endMin != null && endMin > startMin) total = endMin - startMin;
  }
  return total;
}

/**
 * Taux de remplissage dynamique :
 * RDV réservés / capacité théorique (amplitude horaire × jours ouverts / durée créneau).
 */
export function computeFillRateFromOpeningHours({
  today,
  bookedEntries = [],
  openingHours = [],
  slotDurationMinutes = 30,
  horizonDays = 7,
}) {
  const slotMinutes = Math.max(5, Number(slotDurationMinutes) || 30);
  const hoursByDay = {};
  (openingHours || []).forEach((row) => {
    const key = String(row?.day || "").trim().toLowerCase();
    if (key) hoursByDay[key] = row;
  });

  const todayStart = new Date(today);
  todayStart.setHours(0, 0, 0, 0);
  const end = new Date(todayStart);
  end.setDate(end.getDate() + Math.max(1, horizonDays) - 1);
  end.setHours(23, 59, 59, 999);

  const bookedByDate = {};
  bookedEntries.forEach(({ start }) => {
    if (!(start instanceof Date) || Number.isNaN(start.getTime())) return;
    if (start < todayStart || start > end) return;
    const key = dateToISO(start);
    bookedByDate[key] = (bookedByDate[key] || 0) + 1;
  });

  let totalBooked = 0;
  let totalCapacity = 0;
  const cursor = new Date(todayStart);
  cursor.setHours(12, 0, 0, 0);
  const endCursor = new Date(end);
  endCursor.setHours(12, 0, 0, 0);

  while (cursor <= endCursor) {
    const key = dateToISO(cursor);
    const dayKey = WEEKDAY_TO_KEY[cursor.getDay()];
    const openMinutes = openingRowOpenMinutes(hoursByDay[dayKey]);
    const capacity = openMinutes > 0 ? Math.max(1, Math.floor(openMinutes / slotMinutes)) : 0;
    const booked = bookedByDate[key] || 0;
    if (capacity > 0) {
      totalCapacity += capacity;
      totalBooked += booked;
    }
    cursor.setDate(cursor.getDate() + 1);
  }

  const fillRate = totalCapacity > 0
    ? Math.min(100, Math.round((totalBooked / totalCapacity) * 100))
    : 0;

  return { fillRate, totalBooked, totalCapacity, horizonDays, source: "opening_hours" };
}

/** Mois YYYY-MM à charger pour couvrir [today, today + horizonDays - 1]. */
export function monthsCoveringHorizon(today, horizonDays = 7) {
  const start = new Date(today);
  start.setHours(12, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + Math.max(1, horizonDays) - 1);
  const months = new Set([dateToISO(start).slice(0, 7), dateToISO(end).slice(0, 7)]);
  return [...months];
}

/**
 * Taux de remplissage = RDV réservés / (réservés + libres) sur les N prochains jours.
 * Les jours sans aucun créneau (cabinet fermé) sont ignorés.
 */
export function computeUpcomingFillRate({
  today,
  bookedEntries = [],
  freeSlotsByDate = {},
  horizonDays = 7,
}) {
  const todayStart = new Date(today);
  todayStart.setHours(0, 0, 0, 0);
  const end = new Date(todayStart);
  end.setDate(end.getDate() + Math.max(1, horizonDays) - 1);

  const bookedByDate = {};
  bookedEntries.forEach(({ start }) => {
    if (!(start instanceof Date) || Number.isNaN(start.getTime())) return;
    if (start < todayStart || start > end) return;
    const key = dateToISO(start);
    bookedByDate[key] = (bookedByDate[key] || 0) + 1;
  });

  let totalBooked = 0;
  let totalCapacity = 0;
  const cursor = new Date(todayStart);
  cursor.setHours(12, 0, 0, 0);
  const endCursor = new Date(end);
  endCursor.setHours(12, 0, 0, 0);

  while (cursor <= endCursor) {
    const key = dateToISO(cursor);
    const booked = bookedByDate[key] || 0;
    const free = Number(freeSlotsByDate[key]) || 0;
    const capacity = booked + free;
    if (capacity > 0) {
      totalBooked += booked;
      totalCapacity += capacity;
    }
    cursor.setDate(cursor.getDate() + 1);
  }

  const fillRate = totalCapacity > 0
    ? Math.min(100, Math.round((totalBooked / totalCapacity) * 100))
    : 0;

  return { fillRate, totalBooked, totalCapacity, horizonDays, source: "free_slots" };
}

/** Fusionne créneaux agenda + starts ISO stats-fast (dédupliqués). */
export function mergeBookedEntryStarts(agendaEntries = [], isoStarts = []) {
  const byKey = new Map();
  const add = (start) => {
    if (!(start instanceof Date) || Number.isNaN(start.getTime())) return;
    byKey.set(start.toISOString(), { start });
  };
  (agendaEntries || []).forEach((entry) => {
    if (entry?.start) add(entry.start);
    else if (entry instanceof Date) add(entry);
  });
  (isoStarts || []).forEach((iso) => {
    const d = new Date(String(iso || "").trim());
    add(d);
  });
  return [...byKey.values()];
}

/** Préfère le calcul horaires cabinet ; repli sur créneaux libres PG si horaires absents. */
export function computeDashboardFillRate({
  today,
  bookedEntries = [],
  openingHours = [],
  slotDurationMinutes = 30,
  freeSlotsByDate = {},
  horizonDays = 7,
}) {
  const fromHours = computeFillRateFromOpeningHours({
    today,
    bookedEntries,
    openingHours,
    slotDurationMinutes,
    horizonDays,
  });
  if (fromHours.totalCapacity > 0) return fromHours;
  return computeUpcomingFillRate({
    today,
    bookedEntries,
    freeSlotsByDate,
    horizonDays,
  });
}
