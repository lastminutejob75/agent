import { describe, expect, it } from "vitest";

import { patientDashboardFileHasValidatedIdentity } from "./callsService.js";

describe("patientDashboardFileHasValidatedIdentity", () => {
  it("refuse vide ou trop court", () => {
    expect(patientDashboardFileHasValidatedIdentity(null)).toBe(false);
    expect(patientDashboardFileHasValidatedIdentity({ validated_name: "" })).toBe(false);
    expect(patientDashboardFileHasValidatedIdentity({ validated_name: " A " })).toBe(false);
  });

  it("accepte deux caractères ou plus après trim", () => {
    expect(patientDashboardFileHasValidatedIdentity({ validated_name: "Jean Dupont" })).toBe(true);
  });
});
