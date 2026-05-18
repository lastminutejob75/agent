import { describe, expect, it } from "vitest";
import { enrichTenant, mapFilterToApi, mapSortToApi } from "./adminBilling.utils.js";

describe("adminBilling.utils", () => {
  it("mappe les filtres UI vers API", () => {
    expect(mapFilterToApi("Tous")).toBe("all");
    expect(mapFilterToApi("Quota élevé")).toBe("quota_high");
    expect(mapFilterToApi("Stripe incomplet")).toBe("stripe_incomplete");
    expect(mapFilterToApi("inconnu")).toBe("all");
  });

  it("mappe les tris UI vers API", () => {
    expect(mapSortToApi("mrr")).toBe("mrr_desc");
    expect(mapSortToApi("vapi")).toBe("vapi_cost_desc");
    expect(mapSortToApi("invoice")).toBe("next_invoice_asc");
    expect(mapSortToApi("unknown")).toBe("margin_low");
  });

  it("enrichit un tenant billing avec marge/usage/alertes", () => {
    const tenant = enrichTenant({
      tenant_id: 11,
      name: "Cabinet Test",
      plan_key: "starter",
      stripe_status: "active",
      mrr_eur: 99,
      usage: { minutes: 430, cost_usd: 120 },
      quota: { included: 400, used: 430 },
      stripe_customer_id: "",
      stripe_subscription_id: "sub_123",
    });

    expect(tenant.tenantId).toBe(11);
    expect(tenant.planLabel).toBe("Starter");
    expect(tenant.overMinutes).toBe(30);
    expect(tenant.overageAmount).toBeGreaterThan(0);
    expect(tenant.margin).toBeLessThan(0);
    expect(tenant.alerts.join(" ")).toContain("Stripe customer manquant");
  });
});
