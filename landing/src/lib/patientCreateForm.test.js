import { describe, expect, it } from "vitest";
import {
  applyTreatingPhysicianDefaults,
  generalPractitionerPatientDefaults,
  isGeneralPractitionerSpecialty,
} from "./patientCreateForm.js";

describe("general practitioner patient defaults", () => {
  it("recognizes common general-practice labels", () => {
    expect(isGeneralPractitionerSpecialty("Médecin généraliste")).toBe(true);
    expect(isGeneralPractitionerSpecialty("Médecine générale")).toBe(true);
    expect(isGeneralPractitionerSpecialty("Cardiologue")).toBe(false);
  });

  it("uses the practitioner name and city for a general practitioner", () => {
    expect(generalPractitionerPatientDefaults({
      specialty: "Médecin généraliste",
      practitioner_name: "Dr Marie Martin",
      city: "Lyon",
    })).toEqual({
      treatingPhysicianName: "Dr Marie Martin",
      treatingPhysicianCity: "Lyon",
    });
  });

  it("never overwrites a physician entered by the user", () => {
    expect(applyTreatingPhysicianDefaults(
      { treatingPhysicianName: "Dr Durand", treatingPhysicianCity: "Paris" },
      { treatingPhysicianName: "Dr Martin", treatingPhysicianCity: "Lyon" },
    )).toMatchObject({
      treatingPhysicianName: "Dr Durand",
      treatingPhysicianCity: "Paris",
    });
  });
});
