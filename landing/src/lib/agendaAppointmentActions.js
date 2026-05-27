/** Identifiant API pour annuler / déplacer un RDV agenda. */

export function appointmentActionId(slot) {
  const apptId = slot?.appointment_id;
  if (apptId != null && String(apptId) !== "" && String(apptId) !== "0") {
    return String(apptId);
  }
  const evtId = slot?.event_id;
  if (evtId != null && String(evtId).trim()) return String(evtId).trim();
  return "";
}

/** Id Google Calendar si connu (ignore les ids numériques locaux). */
export function appointmentGoogleEventId(slot) {
  const evtId = String(slot?.event_id || "").trim();
  if (!evtId) return "";
  if (/^\d+$/.test(evtId)) return "";
  return evtId;
}

export function agendaCancelPayload(slot) {
  return {
    source: String(slot?.source || "UWI"),
    external_event_id: appointmentGoogleEventId(slot),
  };
}

export function agendaReschedulePayload(slot, newSlotId) {
  return {
    new_slot_id: newSlotId,
    external_event_id: appointmentGoogleEventId(slot),
  };
}

export function canCancelAgendaSlot(slot) {
  if (slot?.can_cancel === true) return true;
  const src = String(slot?.source || "").toUpperCase();
  if (src !== "UWI") return false;
  return Boolean(appointmentActionId(slot));
}

export function canRescheduleAgendaSlot(slot) {
  if (slot?.can_reschedule === true) return true;
  const apptId = Number(slot?.appointment_id);
  return Number.isFinite(apptId) && apptId > 0;
}

export function buildAgendaViewUrl({ date, phone, slot }) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (phone) params.set("phone", phone);
  const focus = appointmentActionId(slot);
  if (focus) params.set("focus", focus);
  return `/app/agenda?${params.toString()}`;
}
