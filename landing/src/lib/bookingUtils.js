const DAY_MAP = {
  monday: 0,
  tuesday: 1,
  wednesday: 2,
  thursday: 3,
  friday: 4,
  saturday: 5,
  sunday: 6,
};

const DAY_LABELS = {
  0: "Lun",
  1: "Mar",
  2: "Mer",
  3: "Jeu",
  4: "Ven",
  5: "Sam",
  6: "Dim",
};

export function normalizeBookingRules(rules = {}) {
  const rawDays = Array.isArray(rules.booking_days) ? rules.booking_days : [0, 1, 2, 3, 4];
  const bookingDays = [...new Set(rawDays.map((d) => parseInt(d, 10)).filter((d) => Number.isInteger(d) && d >= 0 && d <= 6))].sort(
    (a, b) => a - b,
  );
  return {
    booking_days: bookingDays.length ? bookingDays : [0, 1, 2, 3, 4],
    booking_start_hour: parseInt(rules.booking_start_hour, 10) || 9,
    booking_end_hour: parseInt(rules.booking_end_hour, 10) || 18,
    booking_duration_minutes: parseInt(rules.booking_duration_minutes, 10) || 15,
    booking_buffer_minutes: parseInt(rules.booking_buffer_minutes, 10) || 0,
  };
}

export function convertOpeningHours(openingHours) {
  const days = [];
  const starts = [];
  const ends = [];
  for (const [day, value] of Object.entries(openingHours || {})) {
    const dayIndex = DAY_MAP[String(day).toLowerCase()];
    if (dayIndex === undefined || !value || value.closed) continue;
    days.push(dayIndex);
    if (value.open) starts.push(parseInt(String(value.open).split(":")[0], 10));
    if (value.close) ends.push(parseInt(String(value.close).split(":")[0], 10));
  }
  return normalizeBookingRules({
    booking_days: days,
    booking_start_hour: starts.length ? Math.min(...starts) : 9,
    booking_end_hour: ends.length ? Math.max(...ends) : 18,
  });
}

export function deriveHorairesText(rules = {}) {
  const normalized = normalizeBookingRules(rules);
  const days = normalized.booking_days.map((day) => DAY_LABELS[day]).filter(Boolean).join(", ");
  return `${days} · ${normalized.booking_start_hour}h–${normalized.booking_end_hour}h`;
}
