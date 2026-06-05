import { describe, expect, it } from "vitest";
import {
  computeDashboardFillRate,
  computeFillRateFromOpeningHours,
  computeUpcomingFillRate,
  mergeBookedEntryStarts,
  monthsCoveringHorizon,
  openingRowOpenMinutes,
} from "./agendaFillRate.js";

describe("agendaFillRate", () => {
  it("monthsCoveringHorizon inclut le mois suivant si la fenêtre le chevauche", () => {
    const today = new Date(2026, 4, 31, 12, 0, 0);
    expect(monthsCoveringHorizon(today, 7)).toEqual(["2026-05", "2026-06"]);
  });

  it("ignore les jours sans créneau et calcule sur 7 jours à venir", () => {
    const today = new Date(2026, 4, 31, 12, 0, 0);
    const bookedEntries = [
      { start: new Date(2026, 5, 1, 9, 15, 0) },
      { start: new Date(2026, 5, 1, 9, 30, 0) },
      { start: new Date(2026, 5, 3, 9, 30, 0) },
    ];
    const freeSlotsByDate = {
      "2026-06-01": 2,
      "2026-06-02": 4,
      "2026-06-03": 1,
    };
    const out = computeUpcomingFillRate({ today, bookedEntries, freeSlotsByDate, horizonDays: 7 });
    expect(out.totalBooked).toBe(3);
    expect(out.totalCapacity).toBe(10);
    expect(out.fillRate).toBe(30);
  });

  it("retourne 0% si aucun créneau ouvert sur la période", () => {
    const today = new Date(2026, 4, 31, 12, 0, 0);
    const out = computeUpcomingFillRate({ today, bookedEntries: [], freeSlotsByDate: {}, horizonDays: 7 });
    expect(out.fillRate).toBe(0);
    expect(out.totalCapacity).toBe(0);
  });

  it("calcule l'amplitude horaire matin + après-midi", () => {
    const minutes = openingRowOpenMinutes({
      is_open: true,
      morning_start: "08:30",
      morning_end: "12:30",
      afternoon_start: "14:00",
      afternoon_end: "18:00",
    });
    expect(minutes).toBe(8 * 60);
  });

  it("calcule le taux depuis les horaires cabinet", () => {
    const today = new Date(2026, 5, 2, 10, 0, 0); // mardi
    const openingHours = [
      { day: "monday", is_open: true, morning_start: "09:00", morning_end: "12:00", afternoon_start: "", afternoon_end: "" },
      { day: "tuesday", is_open: true, morning_start: "09:00", morning_end: "12:00", afternoon_start: "", afternoon_end: "" },
      { day: "wednesday", is_open: false, morning_start: "", morning_end: "", afternoon_start: "", afternoon_end: "" },
      { day: "thursday", is_open: true, morning_start: "09:00", morning_end: "12:00", afternoon_start: "", afternoon_end: "" },
      { day: "friday", is_open: true, morning_start: "09:00", morning_end: "12:00", afternoon_start: "", afternoon_end: "" },
      { day: "saturday", is_open: false, morning_start: "", morning_end: "", afternoon_start: "", afternoon_end: "" },
      { day: "sunday", is_open: false, morning_start: "", morning_end: "", afternoon_start: "", afternoon_end: "" },
    ];
    const bookedEntries = [
      { start: new Date(2026, 5, 2, 9, 0, 0) },
      { start: new Date(2026, 5, 2, 9, 30, 0) },
      { start: new Date(2026, 5, 4, 10, 0, 0) },
    ];
    const out = computeFillRateFromOpeningHours({
      today,
      bookedEntries,
      openingHours,
      slotDurationMinutes: 30,
      horizonDays: 7,
    });
    expect(out.totalBooked).toBe(3);
    expect(out.totalCapacity).toBeGreaterThan(0);
    expect(out.fillRate).toBeGreaterThan(0);
    expect(out.source).toBe("opening_hours");
  });

  it("mergeBookedEntryStarts fusionne agenda et stats-fast sans doublon", () => {
    const d1 = new Date(2026, 5, 2, 9, 0, 0);
    const merged = mergeBookedEntryStarts(
      [{ start: d1 }],
      [d1.toISOString(), "2026-06-04T10:00:00+02:00"],
    );
    expect(merged).toHaveLength(2);
  });

  it("préfère les horaires cabinet au repli créneaux libres", () => {
    const today = new Date(2026, 5, 2, 10, 0, 0);
    const out = computeDashboardFillRate({
      today,
      bookedEntries: [{ start: new Date(2026, 5, 2, 9, 0, 0) }],
      openingHours: [{
        day: "tuesday",
        is_open: true,
        morning_start: "09:00",
        morning_end: "12:00",
        afternoon_start: "",
        afternoon_end: "",
      }],
      slotDurationMinutes: 30,
      freeSlotsByDate: {},
      horizonDays: 7,
    });
    expect(out.source).toBe("opening_hours");
    expect(out.totalCapacity).toBeGreaterThan(0);
  });
});
