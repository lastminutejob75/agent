/**
 * Cache mémoire court (45s) pour calls / handoffs / callbacks tenant.
 * Évite les requêtes dupliquées entre Dashboard, Demandes et fiche patient.
 */

const TTL_MS = 45_000;

function createSlot() {
  return { data: null, ts: 0, inflight: null, query: null };
}

const slots = {
  calls: createSlot(),
  handoffs: createSlot(),
  callbacks: createSlot(),
};

function isFresh(slot, query) {
  return Boolean(slot.data && slot.query === query && Date.now() - slot.ts < TTL_MS);
}

async function loadSlot(slot, query, fetcher) {
  if (isFresh(slot, query)) return slot.data;
  if (slot.inflight && slot.query === query) return slot.inflight;
  slot.query = query;
  slot.inflight = fetcher()
    .then((data) => {
      slot.data = data;
      slot.ts = Date.now();
      slot.inflight = null;
      return data;
    })
    .catch((err) => {
      slot.inflight = null;
      throw err;
    });
  return slot.inflight;
}

export function invalidateTenantRequestsCache() {
  Object.values(slots).forEach((slot) => {
    slot.data = null;
    slot.ts = 0;
    slot.inflight = null;
    slot.query = null;
  });
}

export async function fetchTenantCallsCached(apiClient, query = "?limit=50&days=30&compact=1") {
  return loadSlot(slots.calls, query, () => apiClient.tenantGetCalls(query));
}

export async function fetchTenantHandoffsCached(apiClient, query = "?limit=50") {
  return loadSlot(slots.handoffs, query, () => apiClient.tenantGetHandoffs(query));
}

export async function fetchTenantCallbacksCached(apiClient, query = "?limit=50") {
  return loadSlot(slots.callbacks, query, () => apiClient.tenantGetCallbackRequests(query));
}

/** Bundle parallèle avec cache partagé (clés = query strings). */
export async function fetchTenantRequestsBundleCached(
  apiClient,
  {
    callsQuery = "?limit=50&days=30&compact=1",
    handoffsQuery = "?limit=50",
    callbacksQuery = "?limit=50",
  } = {},
) {
  const [callsRes, handoffsRes, callbacksRes] = await Promise.all([
    fetchTenantCallsCached(apiClient, callsQuery).catch(() => ({ calls: [] })),
    fetchTenantHandoffsCached(apiClient, handoffsQuery).catch(() => ({ items: [] })),
    fetchTenantCallbacksCached(apiClient, callbacksQuery).catch(() => ({ items: [] })),
  ]);
  return { callsRes, handoffsRes, callbacksRes };
}

if (typeof window !== "undefined") {
  window.addEventListener("uwi:request-status-updated", invalidateTenantRequestsCache);
}
