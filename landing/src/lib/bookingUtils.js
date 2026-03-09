const DAY_MAP = {
  0: 0,
  1: 1,
  2: 2,
  3: 3,
  4: 4,
  5: 5,
  6: 6,
  monday: 0,
  tuesday: 1,
  wednesday: 2,
  thursday: 3,
  friday: 4,
  saturday: 5,
  sunday: 6,
  lun: 0,
  mar: 1,
  mer: 2,
  jeu: 3,
  ven: 4,
  sam: 5,
  dim: 6,
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
    const rawDay = String(day).toLowerCase();
    const parsedDay = parseInt(rawDay, 10);
    const dayIndex =
      Number.isInteger(parsedDay) && parsedDay >= 0 && parsedDay <= 6
        ? parsedDay
        : DAY_MAP[rawDay];
    if (dayIndex === undefined || !value || value.closed) continue;
    days.push(dayIndex);
    const startValue = value.start || value.open || "";
    const endValue = value.end || value.close || "";
    if (startValue) starts.push(parseInt(String(startValue).split(":")[0], 10));
    if (endValue) ends.push(parseInt(String(endValue).split(":")[0], 10));
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
