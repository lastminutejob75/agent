import { useMemo, useState, useEffect, useCallback, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi, getBillingOverview } from "../../lib/adminApi.js";
import { buildTenantsListQuery } from "../../lib/adminTenantsApi.js";
import { T } from "../theme.js";

const C = {
  bg: T.bgPage,
  card: T.bgCard,
  border: T.border,
  accent: T.teal,
  text: T.text,
  muted: T.textMuted,
  danger: T.red,
  navy: "#071A33",
};

const SORT_METRICS = {
  calls_desc: "calls",
  appointments_desc: "appointments",
  web_requests_desc: "web_handoffs",
};

/** Pagination API : réduit la charge réseau / JSON (le serveur agrège encore tout le parc). */
const DEFAULT_TENANTS_PAGE_SIZE = 50;

/** Évite un POST liste à chaque frappe dans la recherche. */
const SEARCH_DEBOUNCE_MS = 400;

/** Palette alignée maquette Cabinets clients */
const BRAND = {
  teal: "#009CA4",
  tealDark: "#007C84",
  navy: "#071A33",
  bg: "#F4F8FA",
  border: "#DCE8EC",
  muted: "#667085",
  red: "#D92D20",
  orange: "#F79009",
  blue: "#2563EB",
  green: "#039855",
  softTeal: "#E7F7F7",
};

function parseWindowDays(raw) {
  const n = Number(raw);
  if (Number.isFinite(n) && n >= 1 && n <= 90) return Math.floor(n);
  return 30;
}

function parseSummaryPeriod(raw) {
  const n = Number(raw);
  if (Number.isFinite(n) && n >= 1 && n <= 90) return Math.floor(n);
  return 30;
}

function parsePageParam(raw) {
  const n = Number(raw || 1);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.floor(n);
}

/** @returns {number | "all" | null} — null = défaut rapide (DEFAULT_TENANTS_PAGE_SIZE), "all" = liste complète */
function parseLimitParam(raw) {
  if (raw == null || raw === "") return null;
  const s = String(raw).trim().toLowerCase();
  if (s === "all") return "all";
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1 || n > 500) return null;
  return Math.floor(n);
}

function usagePct(used, included) {
  const u = Number(used);
  const i = Number(included);
  if (!Number.isFinite(u) || !Number.isFinite(i) || i <= 0) return null;
  return Math.min(100, Math.round((u / i) * 100));
}

function usageBarColor(pct) {
  if (pct == null) return BRAND.teal;
  if (pct >= 90) return BRAND.red;
  if (pct >= 75) return BRAND.orange;
  return BRAND.teal;
}

/** Cabinets fictifs pour prévisualiser la liste (scroll dense + filtres). */
const SAMPLE_SEEDS = [
  {
    name: "Cabinet Durand",
    practitioner: "Dr Karim Durand",
    profession: "Cardiologue",
    city: "Paris 15e",
    status: "inactive",
    email: "contact@durand-cardio.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 226,
    cockpitAlert: true,
    calls: 142,
    rdv: 89,
    web: 34,
  },
  {
    name: "Centre Vital Bastille",
    practitioner: "Dr Marion Weiss",
    profession: "Médecine générale",
    city: "Paris 11e",
    status: "active",
    email: "accueil@vital-bastille.fr",
    plan: "pro",
    stripe: "active",
    included: 600,
    used: 312,
    calls: 208,
    rdv: 121,
    web: 52,
  },
  {
    name: "Kiné Seine Ouest",
    practitioner: "Julie Renaud",
    profession: "Kinésithérapeute",
    city: "Boulogne-Billancourt",
    status: "active",
    email: "cabinet@kine-seine-ouest.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 368,
    cockpitAlert: false,
    calls: 96,
    rdv: 64,
    web: 18,
  },
  {
    name: "Dentaire Soleil",
    practitioner: "Dr Ahmed Benali",
    profession: "Chirurgien-dentiste",
    city: "Marseille 8e",
    status: "pending_payment",
    email: "secretariat@dentaire-soleil.fr",
    plan: "starter",
    stripe: "incomplete",
    included: 400,
    used: 0,
    cockpitAlert: true,
    calls: 0,
    rdv: 2,
    web: 1,
  },
  {
    name: "Ophta Horizon",
    practitioner: "Dr Claire Mercier",
    profession: "Ophtalmologue",
    city: "Toulouse",
    status: "active",
    email: "rdv@ophta-horizon.fr",
    plan: "growth",
    stripe: "active",
    included: 800,
    used: 214,
    calls: 178,
    rdv: 95,
    web: 41,
  },
  {
    name: "ORL Forum",
    practitioner: "Dr Lucas Petit",
    profession: "ORL",
    city: "Lille",
    status: "suspended",
    email: "contact@orl-forum.fr",
    plan: "pro",
    stripe: "active",
    included: 600,
    used: 88,
    calls: 44,
    rdv: 31,
    web: 12,
  },
  {
    name: "Maison santé Voltaire",
    practitioner: "Dr Fatoumata Diallo",
    profession: "Médecine générale",
    city: "Lyon 7e",
    status: "active",
    email: "accueil@ms-voltaire.fr",
    plan: "trial",
    stripe: "trialing",
    included: 250,
    used: 112,
    calls: 124,
    rdv: 71,
    web: 28,
  },
  {
    name: "Imagerie Wilson",
    practitioner: "Dr Geoffroy Marin",
    profession: "Radiologue",
    city: "Strasbourg",
    status: "inactive",
    email: "planning@imagerie-wilson.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 54,
    cockpitAlert: false,
    calls: 62,
    rdv: 48,
    web: 22,
  },
  {
    name: "Pédiatrie des Lilas",
    practitioner: "Dr Sofia Martins",
    profession: "Pédiatre",
    city: "Les Lilas",
    status: "active",
    email: "rdv@pediatrie-lilas.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 156,
    calls: 186,
    rdv: 102,
    web: 37,
  },
  {
    name: "Sage-femme Bel Air",
    practitioner: "Camille Leroy",
    profession: "Sage-femme",
    city: "Bordeaux",
    status: "active",
    email: "contact@belair-naissance.fr",
    plan: "pro",
    stripe: "past_due",
    included: 600,
    used: 518,
    cockpitAlert: true,
    calls: 151,
    rdv: 88,
    web: 29,
  },
  {
    name: "Laboratoire Nova Bio",
    practitioner: "Biologie médicale · plate-forme",
    profession: "Laboratoire",
    city: "Montpellier",
    status: "active",
    email: "operations@nova-bio.fr",
    plan: "growth",
    stripe: "active",
    included: 800,
    used: 706,
    calls: 412,
    rdv: 198,
    web: 76,
  },
  {
    name: "Dermatologie Alpha",
    practitioner: "Dr Nora Saïd",
    profession: "Dermatologue",
    city: "Nice",
    status: "active",
    email: "cabinet@dermato-alpha.fr",
    plan: "pro",
    stripe: "active",
    included: 600,
    used: 578,
    calls: 167,
    rdv: 93,
    web: 44,
  },
  {
    name: "Cardio Horizon",
    practitioner: "Dr Étienne Roche",
    profession: "Cardiologue",
    city: "Rennes",
    status: "active",
    email: "secretariat@cardio-horizon.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 392,
    cockpitAlert: false,
    calls: 131,
    rdv: 76,
    web: 31,
  },
  {
    name: "Centre Orthopédie Maine",
    practitioner: "Dr Yasmine El Mansouri",
    profession: "Chirurgien orthopédiste",
    city: "Angers",
    status: "active",
    email: "accueil@ortho-maine.fr",
    plan: "pro",
    stripe: "active",
    included: 600,
    used: 241,
    calls: 98,
    rdv: 56,
    web: 19,
  },
  {
    name: "Psychologie Plaza",
    practitioner: "Laura Nguyen",
    profession: "Psychologue",
    city: "Nantes",
    status: "pending_payment",
    email: "contact@psy-plaza.fr",
    plan: "starter",
    stripe: "incomplete",
    included: 400,
    used: 12,
    calls: 18,
    rdv: 9,
    web: 6,
  },
  {
    name: "Centre acupuncture Jade",
    practitioner: "Mei Zhang",
    profession: "Acupunctrice",
    city: "Paris 10e",
    status: "active",
    email: "rdv@acu-jade.fr",
    plan: "trial",
    stripe: "trialing",
    included: 250,
    used: 61,
    calls: 72,
    rdv: 41,
    web: 15,
  },
  {
    name: "Pôle santé Montcalm",
    practitioner: "Dr Hugo Bernard",
    profession: "Médecine générale",
    city: "Grenoble",
    status: "active",
    email: "info@pole-montcalm.fr",
    plan: "growth",
    stripe: "active",
    included: 800,
    used: 421,
    calls: 265,
    rdv: 154,
    web: 61,
  },
  {
    name: "Cabinet ostéo Rivoli",
    practitioner: "Thomas Girard",
    profession: "Ostéopathe",
    city: "Paris 1er",
    status: "inactive",
    email: "contact@osteo-rivoli.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 38,
    cockpitAlert: true,
    calls: 54,
    rdv: 38,
    web: 21,
  },
  {
    name: "Nutrition Santé Plus",
    practitioner: "Élodie Marchand",
    profession: "Diététicienne",
    city: "Clermont-Ferrand",
    status: "active",
    email: "hello@nutrition-sp.fr",
    plan: "starter",
    stripe: "active",
    included: 400,
    used: 134,
    calls: 87,
    rdv: 52,
    web: 24,
  },
  {
    name: "Urgences dentaires Nord",
    practitioner: "Dr Inès Khaldi",
    profession: "Chirurgien-dentiste",
    city: "Roubaix",
    status: "active",
    email: "urgences@dentaire-nord.fr",
    plan: "pro",
    stripe: "unpaid",
    included: 600,
    used: 604,
    cockpitAlert: true,
    calls: 312,
    rdv: 140,
    web: 58,
  },
];

function jitterDemoUsed(baseUsed, included, index) {
  const delta = ((index * 17) % 43) - 21;
  let u = Math.round(Number(baseUsed) + delta);
  if (!included || included <= 0) return 0;
  if (!Number.isFinite(u)) u = 0;
  return Math.max(0, Math.min(u, Math.floor(included * 0.96)));
}

function expandSampleSeeds(seeds, totalCount) {
  return Array.from({ length: totalCount }, (_, index) => {
    const s = seeds[index % seeds.length];
    const wave = Math.floor(index / seeds.length);
    const id = 1001 + index;
    const emailParts = String(s.email || "demo@cabinet.fr").split("@");
    const emailLocal = emailParts[0];
    const emailDomain = emailParts[1] || "cabinet-demo.fr";
    const included = Number(s.included) || 400;
    const used = jitterDemoUsed(s.used, included, index);
    const waveSuffix = wave > 0 ? ` · ${wave + 1}` : "";
    const calls = Number(s.calls ?? 40 + (index % 55));
    const rdv = Number(s.rdv ?? 22 + (index % 38));
    const web = Number(s.web ?? 9 + (index % 21));
    return {
      tenant_id: id,
      name: `${s.name}${waveSuffix}`,
      primary_practitioner_name: s.practitioner,
      profession: s.profession,
      city: s.city,
      contact_email: `${emailLocal}+d${id}@${emailDomain}`,
      status: s.status,
      plan_key_params: s.plan,
      __sample: true,
      __demo_cockpit_alert: Boolean(s.cockpitAlert && wave === 0),
      __sampleBilling: {
        plan_key: s.plan,
        stripe_status: s.stripe,
        included,
        used,
      },
      __sample_activity: { calls, rdv, web },
    };
  });
}

function buildSampleBillingMap(rows) {
  const m = {};
  for (const t of rows) {
    const id = Number(t.tenant_id ?? t.id);
    const sb = t.__sampleBilling;
    if (!sb) continue;
    m[id] = {
      tenant_id: id,
      plan_key: sb.plan_key,
      stripe_status: sb.stripe_status,
      quota: { used: sb.used, included: sb.included },
      usage: { minutes: sb.used, cost_usd: Number(((sb.used || 0) * 0.014).toFixed(2)) },
    };
  }
  return m;
}

function buildDemoSummary(tenants, billingMap) {
  let active = 0;
  let onboarding = 0;
  let suspended = 0;
  const alertIds = new Set();
  let totalMins = 0;

  for (const t of tenants) {
    const id = Number(t.tenant_id ?? t.id);
    const st = String(t.status || "active").toLowerCase();
    if (st === "active") active += 1;
    else if (st === "pending_payment" || st === "inactive") onboarding += 1;
    else if (st === "suspended") suspended += 1;

    const b = billingMap[id];
    const used = Number(b?.quota?.used ?? 0);
    const incl = Number(b?.quota?.included ?? 0);
    totalMins += used;
    const pct = usagePct(used, incl);
    const stripe = String(b?.stripe_status || "").toLowerCase();

    if (["pending_payment", "inactive", "suspended"].includes(st)) alertIds.add(id);
    if (pct != null && pct >= 85) alertIds.add(id);
    if (stripe === "past_due" || stripe === "unpaid") alertIds.add(id);
    if (t.__demo_cockpit_alert) alertIds.add(id);
  }

  return {
    period_days: 30,
    active_tenants_count: active,
    onboarding_tenants_count: onboarding,
    suspended_tenants_count: suspended,
    alerts_count: alertIds.size,
    alert_tenant_ids: [...alertIds].sort((a, b) => a - b).slice(0, 500),
    total_voice_minutes_current_period: Math.round(totalMins),
  };
}

const SAMPLE_TENANTS_EXTENDED = expandSampleSeeds(SAMPLE_SEEDS, 96);

/** Ligne jeu de données « Cabinets clients » (?demo=1 sur la liste ou la fiche). */
export function getDemoCabinetRowByTenantId(rawId) {
  const n = Number(rawId);
  if (!Number.isFinite(n) || n < 1) return null;
  const row = SAMPLE_TENANTS_EXTENDED.find((t) => Number(t.tenant_id ?? t.id) === n);
  return row && row.__sample ? row : null;
}

function practitionerInitial(practitionerName, cabinetName) {
  const p = String(practitionerName || "").trim();
  if (p) {
    const parts = p.split(/\s+/).filter(Boolean);
    const last = parts[parts.length - 1];
    return String(last[0] || "?").toUpperCase();
  }
  const n = String(cabinetName || "").trim();
  return (n.slice(0, 1) || "?").toUpperCase();
}

function displayCabinetStatus(status, stripeStatus) {
  const s = String(status || "active").toLowerCase();
  const stripe = String(stripeStatus || "").toLowerCase();
  if (s === "pending_payment" || s === "inactive") return "À configurer";
  if (s === "active" && stripe === "trialing") return "Essai gratuit";
  if (s === "active") return "Actif";
  if (s === "suspended") return "Suspendu";
  return status || "—";
}

function healthFromRow(inAlerts, pct, stripeStatus) {
  const past = stripeStatus === "past_due" || stripeStatus === "unpaid";
  if (past || (pct != null && pct >= 90) || inAlerts) return { label: "Risque", tone: "red" };
  if (pct != null && pct >= 75) return { label: "À surveiller", tone: "yellow" };
  return { label: "Bonne", tone: "green" };
}

function pillToneStyle(tone, filled = false) {
  const map = {
    green: { solid: BRAND.green, soft: "#EAF8F0" },
    orange: { solid: BRAND.orange, soft: "#FFF4E5" },
    yellow: { solid: "#CA8504", soft: "#FFFBEB" },
    red: { solid: BRAND.red, soft: "#FEECEC" },
    blue: { solid: BRAND.blue, soft: "#EAF1FF" },
    navy: { solid: BRAND.navy, soft: "#EAF0F6" },
    gray: { solid: BRAND.muted, soft: "#F2F4F7" },
  };
  const { solid, soft } = map[tone] || map.gray;
  if (filled) return { background: solid, color: "#fff", borderColor: solid };
  return { background: soft, color: solid, borderColor: `${solid}44` };
}

function Pill({ children, tone = "gray", filled = false }) {
  const ps = pillToneStyle(tone, filled);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 10px",
        borderRadius: 999,
        border: `1px solid ${ps.borderColor}`,
        background: ps.background,
        color: ps.color,
        fontSize: 11,
        fontWeight: 900,
      }}
    >
      {children}
    </span>
  );
}

function cabinetAlertPills(inAlerts, pct, stripeStatus, pendingConfigure, backendHints = []) {
  const fromBackend = Array.isArray(backendHints) ? backendHints.map((x) => String(x).trim()).filter(Boolean) : [];
  const pills = [];
  if (pendingConfigure) pills.push("À finaliser");
  if (stripeStatus === "past_due" || stripeStatus === "unpaid") pills.push("Paiement échoué");
  if (pct != null && pct >= 85) pills.push(`Quota à ${pct}%`);
  if (inAlerts) pills.push("Alerte cockpit");
  const seen = new Set();
  const merged = [];
  for (const label of [...fromBackend, ...pills]) {
    if (!label || seen.has(label)) continue;
    seen.add(label);
    merged.push(label);
    if (merged.length >= 3) break;
  }
  return merged.slice(0, 3);
}

function alertRowPillTone(label) {
  if (label.includes("Quota")) return "orange";
  if (label === "À finaliser") return "orange";
  if (/demande/i.test(label)) return "orange";
  if (/Assistant/i.test(label)) return "navy";
  if (/Agenda/i.test(label)) return "blue";
  return "red";
}

function statusPillTone(label) {
  if (label === "Actif") return "green";
  if (label === "À configurer") return "orange";
  if (label === "Essai gratuit") return "blue";
  if (label === "Suspendu") return "red";
  return "gray";
}

function MiniMetric({ value, label }) {
  return (
    <div className="uwi-mini-metric" style={{ borderRadius: 14, background: BRAND.bg, padding: "8px 10px", textAlign: "center", minWidth: 56 }}>
      <div className="uwi-mini-metric-value" style={{ fontSize: 14, fontWeight: 900, color: BRAND.navy }}>{value}</div>
      <div className="uwi-mini-metric-label" style={{ fontSize: 10, fontWeight: 700, color: BRAND.muted, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function capitalizePlan(pk) {
  const p = String(pk || "").trim();
  if (!p || p === "—") return "—";
  return p.charAt(0).toUpperCase() + p.slice(1).toLowerCase();
}

function StatKpiCard({ icon, label, value, detail, tone = "neutral", periodBadge = "30j" }) {
  const tones = {
    neutral: { border: BRAND.border, bg: "#fff", accent: BRAND.muted },
    teal: { border: `${BRAND.teal}44`, bg: "#fff", accent: BRAND.teal },
    green: { border: `${BRAND.green}44`, bg: "#fff", accent: BRAND.green },
    orange: { border: `${BRAND.orange}44`, bg: "#fff", accent: BRAND.orange },
    red: { border: `${BRAND.red}44`, bg: "#fff", accent: BRAND.red },
  };
  const tk = tones[tone] || tones.neutral;
  return (
    <div
      style={{
        borderRadius: 28,
        border: `1px solid ${tk.border}`,
        background: tk.bg,
        padding: "18px 20px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <span style={{ fontSize: 22, lineHeight: 1 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 900, color: BRAND.muted }}>{periodBadge}</span>
      </div>
      <div style={{ fontSize: 13, fontWeight: 900, color: BRAND.muted }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 900, color: BRAND.navy, marginTop: 6, letterSpacing: "-0.05em" }}>{value}</div>
      {detail ? (
        <div style={{ fontSize: 12, fontWeight: 600, color: BRAND.muted, marginTop: 6 }}>{detail}</div>
      ) : null}
    </div>
  );
}

export default function AdminTenantsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const fetchGenRef = useRef(0);
  const [tenants, setTenants] = useState([]);
  const [billingMap, setBillingMap] = useState({});
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [errStatus, setErrStatus] = useState(null);
  const [isSampleMode, setIsSampleMode] = useState(false);
  const [listTotal, setListTotal] = useState(null);
  const [activityByTenant, setActivityByTenant] = useState({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  const legacyStatus = (searchParams.get("status") || "").toLowerCase();
  const filterParam = (searchParams.get("filter") || "").toLowerCase();
  const effectiveFilter =
    filterParam ||
    (legacyStatus === "active" ? "active" : legacyStatus === "suspended" ? "suspended" : "") ||
    "all";

  const sortParam = (searchParams.get("sort") || "").trim();
  const windowDays = parseWindowDays(searchParams.get("window_days"));
  const summaryPeriod = parseSummaryPeriod(searchParams.get("summary_period"));
  const qParam = (searchParams.get("q") || "").trim();

  const qFromUrl = searchParams.get("q") ?? "";
  const [searchDraft, setSearchDraft] = useState(qFromUrl);

  useEffect(() => {
    setSearchDraft(qFromUrl);
  }, [qFromUrl]);

  const demoExamplesRaw = String(searchParams.get("demo") ?? "").trim().toLowerCase();
  const forcedDemoExamples = ["1", "true", "oui", "yes", "exemple", "exemples", "examples", "demo"].includes(demoExamplesRaw);

  const explicitLimit = parseLimitParam(searchParams.get("limit"));
  const wantsFullTenantList = explicitLimit === "all";
  const parsedPage = parsePageParam(searchParams.get("page"));

  const filterBlocksPagination =
    effectiveFilter === "alerts" ||
    effectiveFilter === "quota_high" ||
    effectiveFilter === "trial" ||
    sortParam === "alerts_first" ||
    sortParam === "minutes_desc" ||
    sortParam === "plan_asc" ||
    Boolean(SORT_METRICS[sortParam]);

  const paginationAllowed =
    !filterBlocksPagination && ["all", "active", "onboarding", "suspended"].includes(effectiveFilter);

  const serverPagingActive = paginationAllowed && !wantsFullTenantList;

  const apiPageLimit =
    typeof explicitLimit === "number" ? explicitLimit : DEFAULT_TENANTS_PAGE_SIZE;

  const effectivePageSize = serverPagingActive ? apiPageLimit : null;

  const alertIdSet = useMemo(() => {
    const xs = summary?.alert_tenant_ids || [];
    return new Set((Array.isArray(xs) ? xs : []).map(Number));
  }, [summary]);

  const setQuery = useCallback(
    (updates) => {
      const p = new URLSearchParams(searchParams);
      Object.entries(updates).forEach(([k, v]) => {
        if (v === null || v === undefined || v === "") p.delete(k);
        else p.set(k, String(v));
      });
      setSearchParams(p);
    },
    [searchParams, setSearchParams]
  );

  useEffect(() => {
    const trimmed = searchDraft.trim();
    const urlTrimmed = qParam.trim();
    if (trimmed === urlTrimmed) return undefined;
    const t = setTimeout(() => {
      setQuery({ q: trimmed || null, page: "1" });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchDraft, qParam, setQuery]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setErr(null);

      if (forcedDemoExamples) {
        const demoRows = SAMPLE_TENANTS_EXTENDED;
        const demoBilling = buildSampleBillingMap(demoRows);
        const demoSummary = buildDemoSummary(demoRows, demoBilling);
        if (cancelled) return;
        setActivityByTenant({});
        setListTotal(null);
        setTenants(demoRows);
        setIsSampleMode(true);
        setBillingMap(demoBilling);
        setSummary(demoSummary);
        setLoading(false);
        return;
      }

      try {
        const gen = ++fetchGenRef.current;
        const summaryPromise = adminApi.tenantsSummary(summaryPeriod).catch(() => null);

        const needBilling =
          Boolean(
            sortParam === "minutes_desc" ||
              effectiveFilter === "quota_high" ||
              sortParam === "plan_asc" ||
              effectiveFilter === "trial",
          );
        const overviewPromise = needBilling ? getBillingOverview().catch(() => null) : Promise.resolve(null);

        const tenantQs = buildTenantsListQuery({
          includeInactive: true,
          search: qParam.trim() || undefined,
          page: serverPagingActive ? parsedPage : undefined,
          limit: serverPagingActive ? apiPageLimit : undefined,
          status:
            serverPagingActive && effectiveFilter === "active"
              ? "active"
              : serverPagingActive && effectiveFilter === "suspended"
                ? "suspended"
                : undefined,
          statusIn:
            serverPagingActive && effectiveFilter === "onboarding"
              ? "pending_payment,inactive"
              : undefined,
        });

        const listRes = await adminApi.listTenants(tenantQs);
        const overviewRes = needBilling ? await overviewPromise : null;

        const raw = listRes?.tenants ?? listRes;
        let next = Array.isArray(raw) ? raw : [];

        const bMap = {};
        if (overviewRes?.tenants && Array.isArray(overviewRes.tenants)) {
          for (const row of overviewRes.tenants) {
            const tid = row.tenant_id;
            if (tid != null) bMap[Number(tid)] = row;
          }
        }

        const metric = SORT_METRICS[sortParam];
        if (next.length > 0 && metric && !next[0]?.__sample) {
          try {
            const top = await adminApi.statsTopTenants(metric, windowDays, Math.min(500, next.length + 100));
            const rank = {};
            (top.items || []).forEach((row, idx) => {
              if (row.tenant_id != null) rank[row.tenant_id] = idx;
            });
            next = [...next].sort((a, b) => {
              const ida = a.tenant_id ?? a.id;
              const idb = b.tenant_id ?? b.id;
              const ra = rank[ida];
              const rb = rank[idb];
              if (ra != null && rb != null) return ra - rb;
              if (ra != null) return -1;
              if (rb != null) return 1;
              return String(a.name || "").localeCompare(String(b.name || ""), "fr");
            });
          } catch (_) {
            /* ignore */
          }
        }

        if (next.length > 0 && sortParam === "minutes_desc" && !next[0]?.__sample) {
          next = [...next].sort((a, b) => {
            const ida = Number(a.tenant_id ?? a.id);
            const idb = Number(b.tenant_id ?? b.id);
            const ua = bMap[ida]?.quota?.used ?? bMap[ida]?.usage?.minutes ?? 0;
            const ub = bMap[idb]?.quota?.used ?? bMap[idb]?.usage?.minutes ?? 0;
            return Number(ub) - Number(ua);
          });
        }

        if (next.length > 0 && sortParam === "plan_asc" && !next[0]?.__sample) {
          next = [...next].sort((a, b) => {
            const ida = Number(a.tenant_id ?? a.id);
            const idb = Number(b.tenant_id ?? b.id);
            const pa = (bMap[ida]?.plan_key || "zzz").toLowerCase();
            const pb = (bMap[idb]?.plan_key || "zzz").toLowerCase();
            const c = pa.localeCompare(pb, "fr");
            if (c !== 0) return c;
            return String(a.name || "").localeCompare(String(b.name || ""), "fr");
          });
        }

        if (next.length > 0 && sortParam === "created_desc" && !next[0]?.__sample) {
          next = [...next].sort((a, b) => Number(b.tenant_id ?? b.id ?? 0) - Number(a.tenant_id ?? a.id ?? 0));
        }

        if (next.length > 0 && sortParam === "name_asc" && !next[0]?.__sample) {
          next = [...next].sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "fr"));
        }

        if (cancelled) return;
        setListTotal(serverPagingActive && typeof listRes?.total === "number" ? listRes.total : null);
        setBillingMap(bMap);
        setActivityByTenant({});

        if (next.length > 0) {
          setTenants(next);
          setIsSampleMode(false);
          summaryPromise.then((sumRes) => {
            if (cancelled || fetchGenRef.current !== gen) return;
            setSummary(sumRes && typeof sumRes === "object" ? sumRes : null);
          });
          if (!next[0]?.__sample) {
            adminApi
              .tenantsActivityGrid(windowDays)
              .then((grid) => {
                if (cancelled || fetchGenRef.current !== gen) return;
                setActivityByTenant(grid?.by_tenant_id ?? {});
              })
              .catch(() => {
                if (cancelled) return;
                /* grille activité optionnelle si le backend refuse ou est indisponible */
              });
          }
        } else {
          setTenants([]);
          setIsSampleMode(false);
          setBillingMap({});
          setSummary(null);
          setActivityByTenant({});
        }
      } catch (e) {
        if (cancelled) return;
        setErr(e?.message ?? e?.data?.detail ?? String(e) ?? "Erreur de chargement");
        setErrStatus(e?.status);
        setTenants([]);
        setIsSampleMode(false);
        setListTotal(null);
        setBillingMap({});
        setSummary(null);
        setActivityByTenant({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sortParam, windowDays, summaryPeriod, effectiveFilter, qParam, explicitLimit, wantsFullTenantList, serverPagingActive, parsedPage, apiPageLimit, forcedDemoExamples]);

  const filtered = useMemo(() => {
    const q = searchDraft.trim().toLowerCase();

    return tenants.filter((t) => {
      const id = Number(t.tenant_id ?? t.id);
      const st = String(t.status || "active").toLowerCase();
      const b = billingMap[id];
      const used = Number(b?.quota?.used ?? b?.usage?.minutes ?? 0);
      const incl = Number(b?.quota?.included ?? 0);
      const pct = usagePct(used, incl);

      if (!serverPagingActive) {
        switch (effectiveFilter) {
          case "active":
            if (st !== "active") return false;
            break;
          case "onboarding":
            if (!["pending_payment", "inactive"].includes(st)) return false;
            break;
          case "suspended":
            if (st !== "suspended") return false;
            break;
          case "alerts":
            if (alertIdSet.size > 0) {
              if (!alertIdSet.has(id)) return false;
            } else if (!["pending_payment", "inactive", "suspended"].includes(st)) {
              return false;
            }
            break;
          case "quota_high": {
            if (!b || incl <= 0) return false;
            if (!(pct != null && pct >= 85) && !(used / incl >= 0.85)) return false;
            break;
          }
          case "trial": {
            const bs = String(b?.stripe_status || "").toLowerCase();
            const pk = String(b?.plan_key || t.plan_key_params || "").toLowerCase();
            if (bs !== "trialing" && !pk.includes("trial")) return false;
            break;
          }
          default:
            break;
        }
      }

      if (!q) return true;
      const name = (t.name || "").toLowerCase();
      const email = (t.contact_email || t.params?.contact_email || "").toLowerCase();
      const plan = `${b?.plan_key || ""} ${t.params?.plan_key || ""} ${t.plan_key_params || ""}`.toLowerCase();
      const profession = (t.profession || t.params?.profession || "").toLowerCase();
      const city = (t.city || t.params?.city || "").toLowerCase();
      const pract = (t.primary_practitioner_name || t.params?.primary_practitioner_name || t.params?.practitioner_name || "").toLowerCase();
      return (
        name.includes(q) ||
        email.includes(q) ||
        plan.includes(q) ||
        profession.includes(q) ||
        city.includes(q) ||
        pract.includes(q) ||
        String(t.tenant_id ?? t.id).includes(q)
      );
    });
  }, [tenants, searchDraft, effectiveFilter, billingMap, alertIdSet, serverPagingActive]);

  if (loading) {
    return (
      <div style={{ padding: "32px", color: C.muted }}>Chargement des clients…</div>
    );
  }

  return (
    <div className="uwi-tenants-page" style={{ padding: "32px", background: BRAND.bg, minHeight: "100vh", fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      <style>{`
        input.admin-search-input::placeholder { color: ${BRAND.muted}; }
        .uwi-tenant-head { display: none; }
        .uwi-tenant-li { margin: 0; padding: 0; list-style: none; border-bottom: 1px solid ${BRAND.border}; }
        .uwi-tenant-row { display: grid; gap: 16px; align-items: start; }
        .uwi-cell::before { display: none; }
        @media (max-width: 1279px) {
          .uwi-tenants-page {
            padding: 18px 14px 24px !important;
          }
          .uwi-tenants-top {
            gap: 10px !important;
          }
          .uwi-header-cta {
            width: 100%;
            justify-content: center;
          }
          .uwi-tenant-table-shell {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
          }
          .uwi-controls-shell {
            border-radius: 22px !important;
            padding: 12px !important;
          }
          .uwi-controls-row {
            gap: 10px !important;
          }
          .uwi-filter-pills {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            width: 100%;
          }
          .uwi-filter-pills > button {
            width: 100%;
            justify-content: center;
          }
          .uwi-tenant-li {
            border-bottom: none;
            padding: 0 0 14px 0;
          }
          .uwi-tenant-li:last-child {
            padding-bottom: 0;
          }
          .uwi-tenant-row {
            border: 1px solid ${BRAND.border};
            border-radius: 22px;
            background: #fff;
            padding: 14px 14px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            gap: 14px;
          }
          .uwi-cell::before {
            display: block;
            font-size: 10px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: ${BRAND.muted};
            margin-bottom: 8px;
          }
          .uwi-cell {
            width: 100%;
            justify-self: stretch;
            text-align: left;
          }
          .uwi-cell--identity::before { content: "Cabinet"; }
          .uwi-cell--prof::before { content: "Profession · ville"; }
          .uwi-cell--status::before { content: "Statut"; }
          .uwi-cell--plan::before { content: "Abonnement"; }
          .uwi-cell--usage::before { content: "Usage"; }
          .uwi-cell--activity::before { content: "Activité (${windowDays} j)"; }
          .uwi-cell--alerts::before { content: "Alertes"; }
          .uwi-cell--usage::before,
          .uwi-cell--activity::before,
          .uwi-cell--alerts::before {
            margin-bottom: 10px;
          }
          .uwi-cell--status::before,
          .uwi-cell--alerts::before {
            flex-basis: 100%;
          }
          .uwi-cell--activity::before {
            grid-column: 1 / -1;
            margin-bottom: 0;
          }
          .uwi-cell--identity {
            align-items: flex-start !important;
          }
          .uwi-cell--status,
          .uwi-cell--alerts {
            justify-content: flex-start !important;
          }
          .uwi-cell--activity {
            display: grid !important;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px !important;
            align-items: stretch;
          }
          .uwi-mini-metric {
            min-width: 0 !important;
            width: 100%;
            padding: 10px 6px !important;
            min-height: 72px;
            display: flex !important;
            flex-direction: column;
            justify-content: center;
            align-items: center;
          }
          .uwi-cell--alerts {
            display: flex;
            flex-wrap: wrap;
            row-gap: 8px;
            column-gap: 8px;
            align-content: flex-start;
          }
          .uwi-cell--alerts > span {
            min-height: 24px;
          }
          .uwi-cell--chevron {
            display: none !important;
          }
        }
        @media (max-width: 767px) {
          .uwi-filter-pills {
            grid-template-columns: 1fr;
          }
        }
        @media (max-width: 390px) {
          .uwi-tenants-page {
            padding: 14px 10px 20px !important;
          }
          .uwi-head-badge {
            font-size: 10px !important;
            padding: 3px 10px !important;
          }
          .uwi-head-title {
            font-size: 24px !important;
            letter-spacing: -0.03em !important;
          }
          .uwi-head-subtitle {
            margin-top: 6px !important;
            font-size: 13px !important;
            line-height: 1.45 !important;
          }
          .uwi-demo-hint {
            display: none;
          }
          .uwi-controls-shell {
            margin-top: 14px !important;
            border-radius: 18px !important;
            padding: 10px !important;
          }
          .uwi-search-box {
            padding: 8px 12px !important;
          }
          .uwi-sort-select {
            width: 100%;
          }
          .uwi-small-control {
            width: 100%;
            justify-content: space-between;
            background: #f8fbfc;
            border: 1px solid ${BRAND.border};
            border-radius: 12px;
            padding: 7px 10px;
          }
          .uwi-small-control-select {
            max-width: 55%;
          }
          .uwi-filter-pills > button {
            padding: 8px 12px !important;
            font-size: 11px !important;
          }
          .uwi-tenant-row {
            border-radius: 18px;
            padding: 12px 12px !important;
          }
          .uwi-identity-avatar {
            width: 40px !important;
            height: 40px !important;
            font-size: 15px !important;
          }
          .uwi-cabinet-name {
            font-size: 14px !important;
          }
          .uwi-cabinet-sub {
            font-size: 12px !important;
          }
          .uwi-cell--alerts > span {
            max-width: 100%;
            white-space: normal;
            text-align: left;
            line-height: 1.2;
          }
          .uwi-mini-metric {
            padding: 7px 4px !important;
          }
          .uwi-mini-metric-value {
            font-size: 12px !important;
          }
          .uwi-mini-metric-label {
            font-size: 9px !important;
          }
        }
        @media (min-width: 1280px) {
          .uwi-tenant-head {
            display: grid;
            grid-template-columns: 1.65fr 1fr 0.88fr 0.92fr 1.05fr 1fr 0.82fr 28px;
            gap: 16px;
            padding: 12px 22px;
            font-size: 11px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: ${BRAND.muted};
            background: #FBFDFD;
            border-bottom: 1px solid ${BRAND.border};
          }
          .uwi-tenant-row {
            grid-template-columns: 1.65fr 1fr 0.88fr 0.92fr 1.05fr 1fr 0.82fr 28px;
            align-items: center;
          }
          .uwi-cell--chevron {
            margin-top: 0;
          }
        }
      `}</style>

      <div className="uwi-tenants-top" style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div
            className="uwi-head-badge"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 8,
              padding: "4px 12px",
              borderRadius: 999,
              border: `1px solid #BFE9EC`,
              background: "#fff",
              fontSize: 11,
              fontWeight: 700,
              color: T.tealDark,
            }}
          >
            <span>◎</span> Admin · Clients
          </div>
          <h1 className="uwi-head-title" style={{ fontSize: 30, fontWeight: 900, color: BRAND.navy, letterSpacing: "-0.04em", margin: 0 }}>
            Clients
          </h1>
          <p className="uwi-head-subtitle" style={{ marginTop: 10, maxWidth: 720, fontSize: 15, fontWeight: 500, color: BRAND.muted, lineHeight: 1.55 }}>
            Retrouvez rapidement un client, son statut, son activité et les actions à mener.
          </p>
          <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            {!forcedDemoExamples ? (
              <>
                <button
                  type="button"
                  onClick={() => setQuery({ demo: "1" })}
                  style={{
                    padding: "9px 16px",
                    borderRadius: 14,
                    border: `1px solid ${BRAND.teal}`,
                    background: BRAND.softTeal,
                    color: BRAND.tealDark,
                    fontWeight: 800,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  Voir des données d’exemple
                </button>
                <span className="uwi-demo-hint" style={{ fontSize: 12, fontWeight: 600, color: BRAND.muted }}>
                  Ou ajoutez <span style={{ fontWeight: 800, color: BRAND.navy }}>?demo=1</span> dans l’URL.
                </span>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setQuery({ demo: null })}
                style={{
                  padding: "9px 16px",
                  borderRadius: 14,
                  border: `1px solid ${BRAND.border}`,
                  background: "#fff",
                  color: BRAND.navy,
                  fontWeight: 800,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Charger les données réelles
              </button>
            )}
          </div>
        </div>
        <Link
          to="/admin/tenants/new"
          className="uwi-header-cta"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "12px 22px",
            background: BRAND.teal,
            color: "#FFFFFF",
            fontWeight: 800,
            borderRadius: 16,
            textDecoration: "none",
          }}
        >
          <span style={{ fontSize: 18, lineHeight: 1 }}>+</span> Créer un client
        </Link>
      </div>

      {summary && (
        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 14 }}>
          <StatKpiCard
            tone="green"
            icon="✓"
            label="Cabinets actifs"
            value={Number(summary.active_tenants_count ?? 0).toLocaleString("fr-FR")}
            detail="clients en service"
            periodBadge={`${summaryPeriod}j`}
          />
          <StatKpiCard
            tone="orange"
            icon="◷"
            label="En onboarding"
            value={Number(summary.onboarding_tenants_count ?? 0).toLocaleString("fr-FR")}
            detail="à finaliser"
            periodBadge={`${summaryPeriod}j`}
          />
          <StatKpiCard
            tone="red"
            icon="!"
            label="Alertes"
            value={Number(summary.alerts_count ?? 0).toLocaleString("fr-FR")}
            detail="à vérifier"
            periodBadge={`${summaryPeriod}j`}
          />
          <StatKpiCard
            tone="teal"
            icon="☎"
            label="Minutes"
            value={Number(summary.total_voice_minutes_current_period ?? 0).toLocaleString("fr-FR")}
            detail="période en cours"
            periodBadge={`${summaryPeriod}j`}
          />
        </div>
      )}

      {err && (
        <div
          style={{
            marginTop: 16,
            padding: "12px 14px",
            background: T.redLight,
            border: `1px solid ${T.red}40`,
            borderRadius: 12,
            color: C.danger,
            fontSize: 13,
          }}
        >
          {err}
          {errStatus === 401 && (
            <Link to="/admin/login" style={{ marginLeft: 8, color: C.accent, fontWeight: 600 }}>
              Revenir à la connexion
            </Link>
          )}
        </div>
      )}

      {isSampleMode && (
        <div
          style={{
            marginTop: 16,
            padding: "12px 14px",
            background: T.yellowLight,
            border: `1px solid ${T.yellow}66`,
            borderRadius: 12,
            color: T.yellowText,
            fontSize: 13,
          }}
        >
          {forcedDemoExamples
            ? "Mode démo activé : liste et KPI sont remplis avec des exemples (~96 cabinets fictifs). Utilisez « Charger les données réelles » ou retirez ?demo= de l’URL."
            : "Mode exemple ou erreur réseau : données et KPI fictifs pour prévisualiser la liste (aucune donnée réelle provenant de votre environnement)."}
        </div>
      )}

      <div
        className="uwi-controls-shell"
        style={{
          marginTop: 20,
          padding: "16px 18px",
          borderRadius: 30,
          border: `1px solid ${BRAND.border}`,
          background: "#fff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        <div className="uwi-controls-row" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <div
            className="uwi-search-box"
            style={{
              flex: "1 1 280px",
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 16px",
              borderRadius: 16,
              border: `1px solid ${BRAND.border}`,
              background: "#F8FBFC",
            }}
          >
            <span style={{ color: "#98A2B3", fontSize: 18 }}>⌕</span>
            <input
              className="admin-search-input"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              placeholder="Rechercher cabinet, praticien, ville, profession…"
              style={{ flex: 1, border: "none", background: "transparent", fontSize: 14, fontWeight: 700, color: BRAND.navy, outline: "none" }}
            />
          </div>

          <div className="uwi-filter-pills" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {[
              ["Tous", "all"],
              ["Actif", "active"],
              ["À configurer", "onboarding"],
              ["Alertes", "alerts"],
            ].map(([label, key]) => {
              const on = effectiveFilter === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    const clearsLimit = key === "alerts" || key === "quota_high" || key === "trial";
                    setQuery({
                      filter: key === "all" ? null : key,
                      status: null,
                      page: "1",
                      ...(clearsLimit ? { limit: null } : {}),
                    });
                  }}
                  style={{
                    padding: "9px 14px",
                    borderRadius: 16,
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                    border: `1px solid ${on ? BRAND.navy : BRAND.border}`,
                    background: on ? BRAND.navy : "#F2F4F7",
                    color: on ? "#fff" : BRAND.muted,
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced((value) => !value)}
            aria-expanded={showAdvanced}
            style={{
              padding: "9px 14px",
              borderRadius: 16,
              border: `1px solid ${BRAND.border}`,
              background: showAdvanced ? BRAND.softTeal : "#fff",
              color: showAdvanced ? BRAND.tealDark : BRAND.navy,
              fontSize: 12,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            {showAdvanced ? "Masquer les options" : "Options avancées"}
          </button>

          {showAdvanced ? (
            <>
              <div className="uwi-filter-pills" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {[
                  ["Suspendus", "suspended"],
                  ["Essai gratuit", "trial"],
                  ["Quota élevé", "quota_high"],
                ].map(([label, key]) => {
                  const on = effectiveFilter === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setQuery({ filter: key, status: null, page: "1", limit: null })}
                      style={{
                        padding: "9px 14px",
                        borderRadius: 16,
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: "pointer",
                        border: `1px solid ${on ? BRAND.navy : BRAND.border}`,
                        background: on ? BRAND.navy : "#F2F4F7",
                        color: on ? "#fff" : BRAND.muted,
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>

          <select
            className="uwi-sort-select"
            value={sortParam || "default"}
            onChange={(e) => {
              const v = e.target.value;
              setQuery({ sort: v === "default" ? null : v, page: "1" });
            }}
            style={{
              padding: "9px 14px",
              borderRadius: 16,
              border: `1px solid ${BRAND.border}`,
              fontSize: 13,
              fontWeight: 800,
              background: "#fff",
              color: BRAND.navy,
            }}
          >
            <option value="default">Tri par défaut</option>
            <option value="alerts_first">Alertes d&apos;abord</option>
            <option value="minutes_desc">Plus de minutes</option>
            <option value="calls_desc">Plus d&apos;appels</option>
            <option value="appointments_desc">Plus de RDV</option>
            <option value="web_requests_desc">Plus de demandes web</option>
            <option value="name_asc">Nom A → Z</option>
            <option value="created_desc">Créés récemment</option>
            <option value="plan_asc">Plan A → Z</option>
          </select>

          <label className="uwi-small-control" style={{ fontSize: 12, fontWeight: 600, color: C.muted, display: "inline-flex", alignItems: "center", gap: 6 }}>
            Stats j
            <select
              className="uwi-small-control-select"
              value={String(windowDays)}
              onChange={(e) => setQuery({ window_days: e.target.value })}
              disabled={forcedDemoExamples}
              title="Fenêtre pour le tri (appels, RDV, web) et les chiffres d’activité affichés par ligne."
              style={{
                padding: "6px 10px",
                borderRadius: 10,
                border: `1px solid ${C.border}`,
                opacity: forcedDemoExamples ? 0.45 : 1,
              }}
            >
              {[7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>
                  {d} j
                </option>
              ))}
            </select>
          </label>

          <label className="uwi-small-control" style={{ fontSize: 12, fontWeight: 600, color: C.muted, display: "inline-flex", alignItems: "center", gap: 6 }}>
            KPI j
            <select
              className="uwi-small-control-select"
              value={String(summaryPeriod)}
              onChange={(e) => setQuery({ summary_period: e.target.value })}
              style={{ padding: "6px 10px", borderRadius: 10, border: `1px solid ${C.border}` }}
            >
              {[7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>
                  {d} j (minutes parc)
                </option>
              ))}
            </select>
          </label>

          <label className="uwi-small-control" style={{ fontSize: 12, fontWeight: 600, color: C.muted, display: "inline-flex", alignItems: "center", gap: 6 }}>
            Page serveur
            <select
              className="uwi-small-control-select"
              value={wantsFullTenantList ? "all" : typeof explicitLimit === "number" ? String(explicitLimit) : "50"}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "50") setQuery({ limit: null, page: "1" });
                else setQuery({ limit: v, page: "1" });
              }}
              style={{ padding: "6px 10px", borderRadius: 10, border: `1px solid ${C.border}` }}
            >
              <option value="50">50 lignes (défaut)</option>
              <option value="25">25 lignes</option>
              <option value="100">100 lignes</option>
              <option value="all">Tout charger (peut être lent)</option>
            </select>
          </label>
            </>
          ) : null}
        </div>
        {typeof explicitLimit === "number" && !paginationAllowed ? (
          <div style={{ marginTop: 12, fontSize: 12, fontWeight: 600, color: T.orange }}>
            Avec ce filtre ou ce tri, la liste complète est chargée (pagination serveur désactivée).
          </div>
        ) : null}
      </div>

      <div
        className="uwi-tenant-table-shell"
        style={{
          marginTop: 18,
          background: "#fff",
          borderRadius: 32,
          border: `1px solid ${BRAND.border}`,
          overflow: "hidden",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        {filtered.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: BRAND.muted }}>
            {tenants.length === 0 ? "Aucun client. Utilisez « Ajouter un cabinet »." : "Aucune ligne avec ces filtres."}
          </div>
        ) : (
          <>
            <div className="uwi-tenant-head">
              <div>Cabinet / praticien</div>
              <div>Profession / ville</div>
              <div>Statut</div>
              <div>Abonnement</div>
              <div>Usage</div>
              <div>Activité ({windowDays}&nbsp;j)</div>
              <div>Alertes</div>
              <div aria-hidden />
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {(() => {
                let rows = [...filtered];
                if (sortParam === "alerts_first") {
                  rows.sort((a, b) => {
                    const ia = alertIdSet.has(Number(a.tenant_id ?? a.id)) ? 0 : 1;
                    const ib = alertIdSet.has(Number(b.tenant_id ?? b.id)) ? 0 : 1;
                    if (ia !== ib) return ia - ib;
                    const sa = ["suspended", "pending_payment"].includes(String(a.status || "").toLowerCase()) ? 0 : 1;
                    const sb = ["suspended", "pending_payment"].includes(String(b.status || "").toLowerCase()) ? 0 : 1;
                    if (sa !== sb) return sa - sb;
                    return String(a.name || "").localeCompare(String(b.name || ""), "fr");
                  });
                }
                return rows;
              })().map((t, index) => {
                const id = t.tenant_id ?? t.id;
                const nid = Number(id);
                const name = t.name || "Sans nom";
                const status = t.status || "active";
                const isSample = Boolean(t.__sample);
                const b = billingMap[nid];
                const used = Number(b?.quota?.used ?? b?.usage?.minutes ?? 0);
                const incl = Number(b?.quota?.included ?? 0);
                const pct = usagePct(used, incl);
                const bar = usageBarColor(pct);
                const inAlerts = summary && alertIdSet.has(nid);
                const stripeStatus = String(b?.stripe_status || "").toLowerCase();
                const statusLabel = displayCabinetStatus(status, stripeStatus);
                const health = healthFromRow(inAlerts, pct, stripeStatus);
                const params = t.params && typeof t.params === "object" ? t.params : {};
                const email = t.contact_email || params.contact_email || "";
                const practitioner =
                  t.primary_practitioner_name ||
                  params.primary_practitioner_name ||
                  params.practitioner_name ||
                  "";
                const profession = t.profession || params.profession || "";
                const city = t.city || params.city || "";
                const planKeyRaw = (b?.plan_key || t.plan_key_params || params.plan_key || "").trim();
                const planTitle = planKeyRaw.length > 0 ? capitalizePlan(planKeyRaw) : "Non défini";
                const includedMin = incl > 0 ? incl : null;
                const pendingConfigure = ["pending_payment", "inactive"].includes(String(status).toLowerCase());
                const sig =
                  activityByTenant[String(nid)] != null ? activityByTenant[String(nid)] : activityByTenant[nid];
                const hasActivityGrid =
                  typeof sig === "object" &&
                  sig != null &&
                  !isSample &&
                  (Object.prototype.hasOwnProperty.call(sig, "calls") ||
                    Object.prototype.hasOwnProperty.call(sig, "appointments") ||
                    Object.prototype.hasOwnProperty.call(sig, "web_handoffs"));
                const backendHints = Array.isArray(sig?.hints) ? sig.hints : [];
                const alertsList = cabinetAlertPills(inAlerts, pct, stripeStatus, pendingConfigure, backendHints);
                const detailHref =
                  id != null && String(id).trim() !== ""
                    ? `/admin/tenants/${encodeURIComponent(String(id).trim())}${isSample ? "?demo=1" : ""}`
                    : null;

                return (
                  <li key={id != null ? id : `row-${index}`} className="uwi-tenant-li">
                    <Link
                      to={detailHref || "#"}
                      onClick={(e) => {
                        if (!detailHref) e.preventDefault();
                      }}
                      className="uwi-tenant-row"
                      style={{
                        padding: "20px 22px",
                        textDecoration: "none",
                        color: "inherit",
                      }}
                    >
                      <div className="uwi-cell uwi-cell--identity" style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
                        <div
                          className="uwi-identity-avatar"
                          style={{
                            width: 48,
                            height: 48,
                            borderRadius: 999,
                            background: BRAND.navy,
                            color: "#fff",
                            display: "grid",
                            placeItems: "center",
                            fontWeight: 900,
                            fontSize: 18,
                            flexShrink: 0,
                          }}
                        >
                          {practitionerInitial(practitioner, name)}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div className="uwi-cabinet-name" style={{ fontWeight: 900, fontSize: 15, color: BRAND.navy, lineHeight: 1.25 }}>{name}</div>
                          <div className="uwi-cabinet-sub" style={{ marginTop: 4, fontSize: 13, fontWeight: 600, color: BRAND.muted }}>
                            {practitioner || email || "—"}
                          </div>
                        </div>
                      </div>

                      <div className="uwi-cell uwi-cell--prof" style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 900, fontSize: 14, color: BRAND.navy }}>
                          {profession || "Non renseigné"}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 13, fontWeight: 600, color: BRAND.muted }}>
                          {city || "Ville non renseignée"}
                        </div>
                      </div>

                      <div className="uwi-cell uwi-cell--status" style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                        <Pill tone={statusPillTone(statusLabel)}>{statusLabel}</Pill>
                        <Pill tone={health.tone}>{health.label}</Pill>
                      </div>

                      <div className="uwi-cell uwi-cell--plan" style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 900, fontSize: 14, color: BRAND.navy }}>{planTitle}</div>
                        <div style={{ marginTop: 4, fontSize: 11, fontWeight: 700, color: BRAND.muted }}>
                          {includedMin
                            ? `${includedMin} min incluses`
                            : planKeyRaw
                              ? "Quota détaillé sur la fiche"
                              : "Billing non disponible"}
                        </div>
                      </div>

                      <div className="uwi-cell uwi-cell--usage" style={{ minWidth: 0 }}>
                        {includedMin ? (
                          <>
                            <div style={{ fontSize: 11, fontWeight: 800, color: BRAND.muted }}>
                              {Math.round(used)} / {includedMin} min
                              {pct != null ? (
                                <span style={{ marginLeft: 8, fontVariantNumeric: "tabular-nums", color: BRAND.navy }}>
                                  {pct}%
                                </span>
                              ) : null}
                            </div>
                            <div
                              style={{
                                height: 8,
                                borderRadius: 999,
                                background: "#EAF0F6",
                                overflow: "hidden",
                                marginTop: 8,
                              }}
                            >
                              <div
                                style={{
                                  height: "100%",
                                  width: `${pct == null ? 0 : pct}%`,
                                  background: bar,
                                  borderRadius: 999,
                                  transition: "width 0.25s ease",
                                }}
                              />
                            </div>
                          </>
                        ) : (
                          <span style={{ fontSize: 12, fontWeight: 600, color: BRAND.muted }}>
                            Non disponible · ouvrir la fiche cabinet
                          </span>
                        )}
                      </div>

                      <div className="uwi-cell uwi-cell--activity" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <MiniMetric
                          value={
                            isSample && t.__sample_activity
                              ? Number(t.__sample_activity.calls).toLocaleString("fr-FR")
                              : hasActivityGrid
                                ? Number(sig.calls ?? 0).toLocaleString("fr-FR")
                                : "—"
                          }
                          label="appels"
                        />
                        <MiniMetric
                          value={
                            isSample && t.__sample_activity
                              ? Number(t.__sample_activity.rdv).toLocaleString("fr-FR")
                              : hasActivityGrid
                                ? Number(sig.appointments ?? 0).toLocaleString("fr-FR")
                                : "—"
                          }
                          label="RDV"
                        />
                        <MiniMetric
                          value={
                            isSample && t.__sample_activity
                              ? Number(t.__sample_activity.web).toLocaleString("fr-FR")
                              : hasActivityGrid
                                ? Number(sig.web_handoffs ?? 0).toLocaleString("fr-FR")
                                : "—"
                          }
                          label="web"
                        />
                      </div>

                      <div className="uwi-cell uwi-cell--alerts" style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                        {isSample ? (
                          <span style={{ fontSize: 12, fontWeight: 700, color: BRAND.muted }}>Exemple</span>
                        ) : alertsList.length ? (
                          alertsList.map((label) => (
                            <Pill key={label} tone={alertRowPillTone(label)}>
                              {label}
                            </Pill>
                          ))
                        ) : (
                          <Pill tone="green">OK</Pill>
                        )}
                      </div>

                      <div className="uwi-cell uwi-cell--chevron" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
                        <span style={{ fontSize: 22, fontWeight: 300, color: "#98A2B3", lineHeight: 1 }} aria-hidden>
                          ›
                        </span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </>
        )}
        {serverPagingActive && listTotal != null && effectivePageSize != null ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              padding: "14px 22px",
              borderTop: `1px solid ${C.border}`,
              background: T.bgSubtle,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>
              Page {parsedPage} · {listTotal.toLocaleString("fr-FR")} cabinets (serveur)
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                disabled={parsedPage <= 1}
                onClick={() => setQuery({ page: String(Math.max(1, parsedPage - 1)) })}
                style={{
                  padding: "8px 14px",
                  borderRadius: 12,
                  border: `1px solid ${C.border}`,
                  background: C.card,
                  fontWeight: 700,
                  cursor: parsedPage <= 1 ? "default" : "pointer",
                  opacity: parsedPage <= 1 ? 0.45 : 1,
                }}
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={parsedPage * effectivePageSize >= listTotal}
                onClick={() => setQuery({ page: String(parsedPage + 1) })}
                style={{
                  padding: "8px 14px",
                  borderRadius: 12,
                  border: `1px solid ${C.border}`,
                  background: C.card,
                  fontWeight: 700,
                  cursor: parsedPage * effectivePageSize >= listTotal ? "default" : "pointer",
                  opacity: parsedPage * effectivePageSize >= listTotal ? 0.45 : 1,
                }}
              >
                Suivant
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
