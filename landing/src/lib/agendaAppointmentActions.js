/** Identifiant API pour annuler / déplacer un RDV agenda. */

export function appointmentActionId(slot) {
  const localId = appointmentLocalId(slot);
  if (localId) return String(localId);
  const evtId = slot?.event_id;
  if (evtId != null && String(evtId).trim()) return String(evtId).trim();
  return "";
}

/** Id numérique local (appointments.id) requis pour déplacer un RDV. */
export function appointmentLocalId(slot) {
  const apptId = Number(slot?.appointment_id);
  if (Number.isFinite(apptId) && apptId > 0) return apptId;
  return null;
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
  const apptId = appointmentLocalId(slot);
  const slotId = Number(slot?.slot_id);
  return apptId != null && Number.isFinite(slotId) && slotId > 0;
}

export function isAgendaSlotPast(startDate, now = Date.now()) {
  return startDate.getTime() < now;
}

/** Ouvre le flux « déplacer » (calendrier) depuis la fiche patient. */
export function canOpenReschedulePatientAppt(slot, startDate, now = Date.now()) {
  if (isAgendaSlotPast(startDate, now)) return false;
  if (canRescheduleAgendaSlot(slot)) return true;
  const src = String(slot?.source || "").toUpperCase();
  return src === "UWI" && Boolean(appointmentActionId(slot));
}

export function buildAgendaViewUrl({ date, phone, slot, action }) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (phone) params.set("phone", phone);
  const focus = appointmentActionId(slot);
  if (focus) params.set("focus", focus);
  if (action) params.set("action", action);
  return `/app/agenda?${params.toString()}`;
}
