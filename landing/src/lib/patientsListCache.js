/**
 * Cache court (90s) pour GET /api/tenant/patients?compact=1 (sidebar patient-dashboard).
 * sessionStorage + mémoire : affichage immédiat puis revalidation en arrière-plan.
 */

const TTL_MS = 90_000;
const STORAGE_KEY = "uwi:tenant-patients-list:v1";
const DEFAULT_QUERY = "?limit=80&compact=1";

const memory = {
  query: null,
  items: null,
  ts: 0,
  inflight: null,
};

function readSession() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (Date.now() - Number(parsed.ts || 0) >= TTL_MS) return null;
    if (!Array.isArray(parsed.items)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeSession(query, items) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ query, items, ts: Date.now() }),
    );
  } catch {
    /* quota / mode privé */
  }
}

function isFresh(query) {
  return Boolean(
    memory.items
    && memory.query === query
    && Date.now() - memory.ts < TTL_MS,
  );
}

export function getCachedTenantPatientsList(query = DEFAULT_QUERY) {
  if (isFresh(query)) {
    return { items: memory.items, query, fromCache: true };
  }
  const session = readSession();
  if (session && session.query === query) {
    memory.query = query;
    memory.items = session.items;
    memory.ts = Number(session.ts || Date.now());
    return { items: session.items, query, fromCache: true };
  }
  return null;
}

export function invalidateTenantPatientsListCache() {
  memory.query = null;
  memory.items = null;
  memory.ts = 0;
  memory.inflight = null;
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}

/**
 * @param {import("./api.js").default} apiClient
 * @param {{ query?: string, force?: boolean }} [opts]
 */
export async function fetchTenantPatientsListCached(
  apiClient,
  { query = DEFAULT_QUERY, force = false } = {},
) {
  if (!force) {
    const cached = getCachedTenantPatientsList(query);
    if (cached) return cached;
  }
  if (memory.inflight && memory.query === query && !force) {
    return memory.inflight;
  }
  memory.query = query;
  memory.inflight = apiClient
    .tenantGetPatients(query)
    .then((res) => {
      const items = Array.isArray(res?.items) ? res.items : [];
      memory.items = items;
      memory.ts = Date.now();
      memory.inflight = null;
      writeSession(query, items);
      return { items, query, fromCache: false };
    })
    .catch((err) => {
      memory.inflight = null;
      throw err;
    });
  return memory.inflight;
}
