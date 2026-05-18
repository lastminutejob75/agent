import { describe, it, expect } from "vitest";
import {
  buildTenantPatientRequestsPath,
  buildTenantsActivityGridPath,
} from "./adminApi.js";

describe("Chemins REST admin (smoke)", () => {
  it("demandes patient : tenant dans le chemin + query optionnelle", () => {
    expect(buildTenantPatientRequestsPath(42)).toBe("/api/admin/tenants/42/patient-requests");
    expect(buildTenantPatientRequestsPath(42, { limit: 200 })).toBe(
      "/api/admin/tenants/42/patient-requests?limit=200",
    );
    expect(buildTenantPatientRequestsPath("12", { limit: 200 })).toBe(
      "/api/admin/tenants/12/patient-requests?limit=200",
    );
    const withStatus = buildTenantPatientRequestsPath(7, { status: "À traiter" });
    expect(withStatus.startsWith("/api/admin/tenants/7/patient-requests?")).toBe(true);
    expect(withStatus).toContain("status=");
  });

  it("activity-grid : window_days dans la query", () => {
    expect(buildTenantsActivityGridPath(14)).toBe("/api/admin/tenants/activity-grid?window_days=14");
    expect(buildTenantsActivityGridPath(90)).toBe("/api/admin/tenants/activity-grid?window_days=90");
  });
});
