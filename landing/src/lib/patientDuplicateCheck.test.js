import { describe, expect, it } from "vitest";
import {
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  parsePatientDuplicateError,
  patientDuplicateDashboardUrl,
} from "./patientDuplicateCheck";

describe("patientDuplicateCheck", () => {
  it("formats phone conflict message", () => {
    expect(
      formatPatientDuplicateConflict({
        field: "phone",
        display_name: "Claire Dupont",
      }),
    ).toContain("Claire Dupont");
  });

  it("detects blocking email conflict", () => {
    expect(
      hasBlockingPatientDuplicate([{ field: "phone" }, { field: "email" }]),
    ).toBe(true);
    expect(hasBlockingPatientDuplicate([{ field: "phone" }])).toBe(false);
  });

  it("parses structured duplicate error", () => {
    const parsed = parsePatientDuplicateError({
      message: "HTTP 409",
      data: {
        detail: {
          message: "Cet email est déjà utilisé par la fiche de Paul Martin.",
          has_conflict: true,
          conflicts: [{ field: "email", phone: "+33611111111" }],
        },
      },
    });
    expect(parsed.message).toContain("Paul Martin");
    expect(parsed.conflicts).toHaveLength(1);
  });

  it("builds dashboard url from conflict phone", () => {
    expect(
      patientDuplicateDashboardUrl({ phone: "+33612345678" }),
    ).toBe("/app/patient-dashboard?phone=%2B33612345678");
  });
});
