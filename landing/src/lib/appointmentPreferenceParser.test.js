import { describe, expect, it } from "vitest";
import {
  parseAppointmentPreferences,
  buildPreferenceAck,
  normalizeFrText,
} from "./appointmentPreferenceParser.ts";

describe("parseAppointmentPreferences", () => {
  it("exclut le matin (restriction forte)", () => {
    const p = parseAppointmentPreferences("Je ne suis pas dispo le matin");
    expect(p.excluded_time_windows.some((w) => w.label === "matin" && w.strength === "hard")).toBe(true);
    expect(p.excluded_time_windows.find((w) => w.label === "matin")?.start).toBe("08:00");
    expect(p.excluded_time_windows.find((w) => w.label === "matin")?.end).toBe("12:00");
  });

  it("préfère fin de journée (souple)", () => {
    const p = parseAppointmentPreferences("Plutôt en fin de journée");
    const w = p.preferred_time_windows.find((x) => x.label === "fin_de_journee");
    expect(w).toBeDefined();
    expect(w.strength).toBe("soft");
    expect(w.start).toBe("17:00");
    expect(w.end).toBe("19:30");
  });

  it("pas avant 17h → earliest_time", () => {
    const p = parseAppointmentPreferences("Pas avant 17h");
    expect(p.earliest_time).toBe("17:00");
  });

  it("pause déjeuner", () => {
    const p = parseAppointmentPreferences("Je peux pendant ma pause déjeuner");
    expect(p.preferred_time_windows.some((w) => w.label === "pause_dejeuner")).toBe(true);
  });

  it("pas le mercredi", () => {
    const p = parseAppointmentPreferences("Pas le mercredi");
    expect(p.excluded_days).toContain("mercredi");
  });

  it("flexible", () => {
    const p = parseAppointmentPreferences("Je suis flexible");
    expect(p.flexibility).toBe("high");
  });

  it("premier disponible", () => {
    const p = parseAppointmentPreferences("Je prends le premier disponible");
    expect(p.flexibility).toBe("high");
    expect(p.sorting).toBe("earliest_available");
  });

  it("urgence médicale → safety", () => {
    const p = parseAppointmentPreferences("C'est urgent, j'ai une douleur thoracique");
    expect(p.safety_required).toBe(true);
    expect(p.safety_message).toMatch(/15/);
  });

  it("phrase combinée + ack humain", () => {
    const text =
      "Je voudrais un rendez-vous, plutôt en fin de journée, je ne suis pas dispo le matin.";
    const p = parseAppointmentPreferences(text);
    const ack = buildPreferenceAck(p);
    expect(p.preferred_time_windows.some((w) => w.label === "fin_de_journee")).toBe(true);
    expect(p.excluded_time_windows.some((w) => w.label === "matin")).toBe(true);
    expect(ack).toMatch(/matin/);
    expect(ack).toMatch(/fin de journée/i);
  });
});

describe("normalizeFrText", () => {
  it("retire les accents", () => {
    expect(normalizeFrText("Plutôt après-midi")).toBe("plutot apres-midi");
  });
});
