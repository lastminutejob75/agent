import { describe, expect, it } from "vitest";
import {
  computePatientAgeYears,
  formatBirthDateWithAge,
  formatPhysicianWithCity,
} from "./patientProfileMeta.js";

describe("patientProfileMeta", () => {
  it("calcule l'âge à partir de la date du jour", () => {
    const today = new Date("2026-05-27T12:00:00");
    expect(computePatientAgeYears("1990-05-12", today)).toBe(36);
    expect(computePatientAgeYears("1990-05-28", today)).toBe(35);
  });

  it("affiche la date de naissance avec l'âge", () => {
    const today = new Date("2026-05-27T12:00:00");
    const label = formatBirthDateWithAge(
      "1990-05-12",
      (value) => String(value),
      today,
    );
    expect(label).toContain("36 ans");
  });

  it("affiche médecin et ville", () => {
    expect(formatPhysicianWithCity("Dr Martin", "Lyon")).toBe("Dr Martin · Lyon");
    expect(formatPhysicianWithCity("", "Lyon")).toBe("Lyon");
    expect(formatPhysicianWithCity("", "")).toBe("Non renseigné");
  });
});
