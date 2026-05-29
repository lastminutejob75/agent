import { describe, expect, it } from "vitest";
import {
  canOpenReschedulePatientAppt,
  canRescheduleAgendaSlot,
  isAgendaSlotPast,
} from "./agendaAppointmentActions.js";

describe("agendaAppointmentActions reschedule", () => {
  const future = new Date("2030-06-01T10:00:00");
  const past = new Date("2020-06-01T10:00:00");
  const now = new Date("2026-05-29T12:00:00").getTime();

  it("detects past appointments", () => {
    expect(isAgendaSlotPast(past, now)).toBe(true);
    expect(isAgendaSlotPast(future, now)).toBe(false);
  });

  it("allows reschedule when local mirror ids are present", () => {
    const slot = { appointment_id: 12, slot_id: 34, source: "UWI" };
    expect(canRescheduleAgendaSlot(slot)).toBe(true);
    expect(canOpenReschedulePatientAppt(slot, future, now)).toBe(true);
  });

  it("allows opening modal for UWI slot with event id even without mirror", () => {
    const slot = { source: "UWI", event_id: "google_evt_1" };
    expect(canRescheduleAgendaSlot(slot)).toBe(false);
    expect(canOpenReschedulePatientAppt(slot, future, now)).toBe(true);
  });

  it("blocks external calendar events without UWI linkage", () => {
    const slot = { source: "EXTERNAL", event_id: "google_evt_2" };
    expect(canOpenReschedulePatientAppt(slot, future, now)).toBe(false);
  });

  it("respects backend can_reschedule flag", () => {
    const slot = { can_reschedule: true, source: "EXTERNAL" };
    expect(canRescheduleAgendaSlot(slot)).toBe(true);
    expect(canOpenReschedulePatientAppt(slot, future, now)).toBe(true);
  });
});
