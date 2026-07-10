import { describe, expect, it } from "vitest";
import {
  agendaSlotDedupeKey,
  dedupeAgendaSlots,
  isSameAgendaSlotEntry,
  parseAgendaSlotStart,
} from "./agendaSlotParse.js";

describe("dedupeAgendaSlots", () => {
  it("fusionne le même event_id Google", () => {
    const slots = [
      { event_id: "abc", patient: "Walter White", start_iso: "2026-06-03T09:00:00" },
      { event_id: "abc", patient: "Walter White", patient_phone: "+33601020304", start_iso: "2026-06-03T09:00:00" },
    ];
    const out = dedupeAgendaSlots(slots);
    expect(out).toHaveLength(1);
    expect(out[0].patient_phone).toBe("+33601020304");
  });

  it("fusionne un événement Google et son miroir local sans perdre les identifiants d'action", () => {
    const slots = [
      {
        event_id: "google-evt-42",
        patient: "Marie Dupont",
        patient_phone: "+33601020304",
        start_iso: "2026-06-03T09:00:00",
        source: "UWI",
      },
      {
        event_id: "google-evt-42",
        appointment_id: 42,
        slot_id: 84,
        patient: "Marie Dupont",
        start_iso: "2026-06-03T09:00:00",
        source: "UWI",
      },
    ];

    const out = dedupeAgendaSlots(slots);

    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      event_id: "google-evt-42",
      appointment_id: 42,
      slot_id: 84,
      patient_phone: "+33601020304",
    });
  });

  it("fusionne même horaire et même patient sans event_id", () => {
    const slots = [
      { patient: "Georges Wassiuf", start_iso: "2026-06-03T09:15:00" },
      { patient_name: "Georges Wassiuf", start_iso: "2026-06-03T09:15:00", appointment_id: 12 },
    ];
    expect(dedupeAgendaSlots(slots)).toHaveLength(1);
  });

  it("isSameAgendaSlotEntry compare deux entrées parsées", () => {
    const slot = { patient: "A", start_iso: "2026-06-03T10:00:00" };
    const start = parseAgendaSlotStart(slot);
    const a = { slot, start };
    const b = { slot: { ...slot }, start: new Date(start) };
    expect(isSameAgendaSlotEntry(a, b)).toBe(true);
  });
});

describe("agendaSlotDedupeKey", () => {
  it("utilise event_id en priorité", () => {
    const key = agendaSlotDedupeKey({ event_id: "ev-1", start_iso: "2026-06-01T09:00:00" });
    expect(key).toBe("event:ev-1");
  });
});
