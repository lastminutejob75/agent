/**
 * Parse début réel d'un créneau agenda (réponse `/api/tenant/agenda`).
 * Priorité à `start_iso` (léger décalage fuseau évité côté backend quand présent).
 */
export function parseAgendaSlotStart(slot) {
  const startIso = String(slot?.start_iso || "").trim();
  if (startIso) {
    const d = new Date(startIso);
    if (!Number.isNaN(d.getTime())) return d;
  }
  const date = String(slot?.date || "").trim();
  const hour = String(slot?.hour || "").trim();
  if (date && hour) {
    const hhmm = /^\d{2}:\d{2}$/.test(hour) ? hour : `${hour.replace("h", "").padStart(2, "0")}:00`;
    const d = new Date(`${date}T${hhmm}:00`);
    if (!Number.isNaN(d.getTime())) return d;
  }
  return null;
}

export function formatAgendaSlotHour(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return "—";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Motif libellé (API mélange `motif`, `type`, résumés). */
export function agendaSlotMotif(slot) {
  const s = slot || {};
  return String(s.motif || s.reason || s.summary || s.type || "").trim();
}
