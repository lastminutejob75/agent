import { describe, expect, it } from "vitest";
import {
  isValidContactEmail,
  isValidPatientPhone,
  validateContactEmail,
  validatePatientPhone,
} from "./contactValidation.js";

describe("contactValidation", () => {
  it("accepte les numéros FR valides", () => {
    expect(isValidPatientPhone("06 12 34 56 78")).toBe(true);
    expect(isValidPatientPhone("+33612345678")).toBe(true);
  });

  it("rejette les numéros fantaisistes", () => {
    expect(isValidPatientPhone("06968547855555555")).toBe(false);
    expect(isValidPatientPhone("061234")).toBe(false);
    expect(validatePatientPhone("abc").ok).toBe(false);
  });

  it("accepte les e-mails valides", () => {
    expect(isValidContactEmail("prenom@gmail.com")).toBe(true);
    expect(validateContactEmail("").ok).toBe(true);
  });

  it("rejette les e-mails fantaisistes", () => {
    expect(isValidContactEmail("pas-un-email")).toBe(false);
    expect(isValidContactEmail("a@b")).toBe(false);
    expect(isValidContactEmail("a @b.com")).toBe(false);
    expect(validateContactEmail("foo", { required: true }).ok).toBe(false);
  });
});
