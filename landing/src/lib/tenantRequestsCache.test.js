import { describe, expect, it, vi } from "vitest";

import {
  fetchTenantCallsCached,
  fetchTenantHandoffsCached,
  invalidateTenantRequestsCache,
} from "./tenantRequestsCache.js";

describe("tenantRequestsCache", () => {
  it("deduplicates concurrent calls with the same query", async () => {
    invalidateTenantRequestsCache();
    const api = {
      tenantGetCalls: vi.fn().mockResolvedValue({ calls: [{ id: 1 }] }),
    };
    const [a, b] = await Promise.all([
      fetchTenantCallsCached(api, "?limit=10"),
      fetchTenantCallsCached(api, "?limit=10"),
    ]);
    expect(a).toEqual({ calls: [{ id: 1 }] });
    expect(b).toEqual({ calls: [{ id: 1 }] });
    expect(api.tenantGetCalls).toHaveBeenCalledTimes(1);
  });

  it("refetches after invalidation", async () => {
    invalidateTenantRequestsCache();
    const api = {
      tenantGetHandoffs: vi
        .fn()
        .mockResolvedValueOnce({ items: [{ id: "a" }] })
        .mockResolvedValueOnce({ items: [{ id: "b" }] }),
    };
    const first = await fetchTenantHandoffsCached(api, "?limit=5");
    invalidateTenantRequestsCache();
    const second = await fetchTenantHandoffsCached(api, "?limit=5");
    expect(first.items[0].id).toBe("a");
    expect(second.items[0].id).toBe("b");
    expect(api.tenantGetHandoffs).toHaveBeenCalledTimes(2);
  });
});
