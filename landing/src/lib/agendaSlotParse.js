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

function normalizeDedupeToken(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}

/** Clé stable pour fusionner doublons agenda (Google + miroir local). */
export function agendaSlotDedupeKey(slot, start = null) {
  const s = slot || {};
  const eventId = String(s.event_id || "").trim();
  if (eventId) return `event:${eventId}`;
  const startIso = start instanceof Date && !Number.isNaN(start.getTime())
    ? start.toISOString()
    : String(s.start_iso || "").trim();
  const phone = String(s.patient_phone || s.phone || "").replace(/\D/g, "");
  const name = normalizeDedupeToken(s.patient || s.patient_name);
  return `slot:${startIso}|${phone}|${name}`;
}

function agendaSlotRichnessScore(slot) {
  const s = slot || {};
  let score = 0;
  if (Number(s.appointment_id || 0) > 0) score += 4;
  if (String(s.event_id || "").trim()) score += 3;
  if (String(s.patient_phone || s.phone || "").trim()) score += 2;
  if (String(s.patient || s.patient_name || "").trim()) score += 1;
  return score;
}

/** Supprime les créneaux en double (même événement Google ou même horaire + patient). */
export function dedupeAgendaSlots(slots) {
  if (!Array.isArray(slots) || !slots.length) return [];
  const byKey = new Map();
  for (const slot of slots) {
    const start = parseAgendaSlotStart(slot);
    const key = agendaSlotDedupeKey(slot, start);
    const prev = byKey.get(key);
    if (!prev || agendaSlotRichnessScore(slot) > agendaSlotRichnessScore(prev)) {
      byKey.set(key, slot);
    }
  }
  return [...byKey.values()];
}

export function isSameAgendaSlotEntry(entryA, entryB) {
  if (!entryA?.slot || !entryB?.slot) return false;
  return agendaSlotDedupeKey(entryA.slot, entryA.start) === agendaSlotDedupeKey(entryB.slot, entryB.start);
}
