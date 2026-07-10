import { describe, expect, it } from "vitest";
import { buildTenantRequestRows, requestSourceLabel } from "./requestUiStatus.js";

describe("buildTenantRequestRows", () => {
  it("construit les lignes partagées avec statuts et origines harmonisés", () => {
    const rows = buildTenantRequestRows(
      [{
        call_id: "call-1",
        patient_name: "Alice Martin",
        customer_number: "0612345678",
        followup_state: "callback",
        started_at: "2026-07-10T10:00:00Z",
      }],
      [{
        id: 7,
        display_name: "Bob Durand",
        patient_phone: "0698765432",
        status: "processed",
        created_at: "2026-07-10T09:00:00Z",
      }],
      [{
        id: 9,
        name: "Chloé Petit",
        phone: "0600000000",
        source: "public_page",
        status: "new",
        created_at: "2026-07-10T11:00:00Z",
      }],
    );

    expect(rows.find((row) => row.id === "call-call-1")).toMatchObject({
      status: "À traiter",
      source: "Agent vocal",
    });
    expect(rows.find((row) => row.id === "req-007")).toMatchObject({
      status: "Traitées",
      source: "Agent vocal",
    });
    expect(rows.find((row) => row.id === "callback-9")).toMatchObject({
      status: "À traiter",
      source: "Page publique",
    });
  });

  it("applique les surcharges de statut au même endroit", () => {
    const rows = buildTenantRequestRows(
      [],
      [],
      [{ id: 3, name: "Patient", source: "public_page", status: "new" }],
      { "callback-3": { status_raw: "cancelled" } },
    );
    expect(rows[0]).toMatchObject({ status_raw: "cancelled", status: "Traitées" });
  });
});

describe("requestSourceLabel", () => {
  it("normalise Page publique, Agent vocal et Praticien", () => {
    expect(requestSourceLabel("public_page")).toBe("Page publique");
    expect(requestSourceLabel("vocal_agent")).toBe("Agent vocal");
    expect(requestSourceLabel("cabinet")).toBe("Praticien");
  });
});
