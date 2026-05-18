import { describe, expect, it } from "vitest";
import { applySearchParamsUpdates, kpiQueryUpdates } from "./adminLeadsFilters.js";

describe("adminLeadsFilters", () => {
  it("applique les updates KPI sur les query params", () => {
    const base = new URLSearchParams("status=all&page=3");
    const next = applySearchParamsUpdates(base, kpiQueryUpdates("demo"));
    expect(next.get("status")).toBe("demo");
    expect(next.get("page")).toBe("1");
  });

  it("réinitialise les filtres KPI", () => {
    const base = new URLSearchParams("status=trial&search=dentaire&follow_up=today&page=2");
    const next = applySearchParamsUpdates(base, kpiQueryUpdates("reset"));
    expect(next.get("status")).toBeNull();
    expect(next.get("search")).toBeNull();
    expect(next.get("follow_up")).toBeNull();
    expect(next.get("page")).toBe("1");
  });
});
