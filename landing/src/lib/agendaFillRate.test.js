import { describe, expect, it } from "vitest";
import { computeUpcomingFillRate, monthsCoveringHorizon } from "./agendaFillRate.js";

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
});
