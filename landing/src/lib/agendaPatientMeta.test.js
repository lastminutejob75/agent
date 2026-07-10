import { describe, expect, it } from "vitest";
import { agendaOriginLabel, bookingOriginLabel } from "./agendaPatientMeta.js";

describe("agendaOriginLabel", () => {
  it("harmonise les trois origines métier", () => {
    expect(bookingOriginLabel("voice")).toBe("Agent vocal");
    expect(bookingOriginLabel("public_page")).toBe("Page publique");
    expect(bookingOriginLabel("praticien")).toBe("Praticien");
  });

  it("utilise la source en repli", () => {
    expect(agendaOriginLabel({ source: "PAGE_PUBLIQUE" })).toBe("Page publique");
    expect(agendaOriginLabel({ source: "UWI" })).toBe("Agent vocal");
    expect(agendaOriginLabel({ source: "CABINET" })).toBe("Praticien");
  });
});
