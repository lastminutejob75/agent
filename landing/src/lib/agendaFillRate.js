/** Date civile locale → YYYY-MM-DD */
export function dateToISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
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

  return { fillRate, totalBooked, totalCapacity, horizonDays };
}
