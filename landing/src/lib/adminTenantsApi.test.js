import { describe, it, expect } from "vitest";
import { buildTenantsListQuery } from "./adminTenantsApi.js";

describe("buildTenantsListQuery", () => {
  it("encode include_inactive, pagination serveur et filtre suspendus", () => {
    const qs = buildTenantsListQuery({
      includeInactive: true,
      search: "",
      status: "suspended",
      page: 2,
      limit: 50,
    });
    expect(qs).toContain("include_inactive=true");
    expect(qs).toContain("status=suspended");
    expect(qs).toContain("page=2");
    expect(qs).toContain("limit=50");
  });

  it("encode status_in onboarding", () => {
    expect(buildTenantsListQuery({ statusIn: "pending_payment,inactive" })).toContain(
      "status_in=pending_payment%2Cinactive",
    );
  });
});
