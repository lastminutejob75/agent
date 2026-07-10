import { describe, expect, it } from "vitest";
import {
  canCancelAgendaSlot,
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

  it("allows reschedule for a Google UWI slot even without local mirror", () => {
    const slot = { source: "UWI", event_id: "google_evt_1" };
    expect(canRescheduleAgendaSlot(slot)).toBe(true);
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

describe("agendaAppointmentActions past appointments are not actionable", () => {
  const now = new Date("2026-05-29T19:00:00").getTime();

  it("blocks cancel for a past appointment (start known)", () => {
    const slot = { appointment_id: 12, source: "UWI", start_iso: "2026-05-29T11:15:00" };
    expect(canCancelAgendaSlot(slot, now)).toBe(false);
    expect(canRescheduleAgendaSlot(slot, now)).toBe(false);
  });

  it("allows cancel for a future appointment", () => {
    const slot = { appointment_id: 12, slot_id: 34, source: "UWI", start_iso: "2026-05-29T21:30:00" };
    expect(canCancelAgendaSlot(slot, now)).toBe(true);
    expect(canRescheduleAgendaSlot(slot, now)).toBe(true);
  });

  it("blocks past appointment even with backend can_cancel flag", () => {
    const slot = { can_cancel: true, source: "UWI", date: "2026-05-29", hour: "11:15" };
    expect(canCancelAgendaSlot(slot, now)).toBe(false);
  });

  it("does not block when start is unknown (historical behavior)", () => {
    const slot = { appointment_id: 12, source: "UWI" };
    expect(canCancelAgendaSlot(slot, now)).toBe(true);
  });
});
