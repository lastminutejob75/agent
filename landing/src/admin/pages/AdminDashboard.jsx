/**
 * Cockpit pilotage plateforme — route /admin
 * Cf. CdC : 7 KPI, leads, actions prioritaires, watchlist, panneau contexte.
 * Style inline + tokens theme (pas Tailwind).
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Users,
  UserPlus,
  Phone,
  Globe,
  Calendar,
  Clock,
  Euro,
  AlertTriangle,
  Sparkles,
  ChevronRight,
  Plus,
} from "lucide-react";
import { getAdminDashboardBundle } from "../../lib/adminApi.js";
import { T, radius, shadow, font, keyframes } from "../theme.js";

const NAVY = "#071A33";
const CDC_BG = "#F4F8FA";
const CDC_BORDER = "#DCE8EC";

function formatIntlNumber(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("fr-FR");
}

function formatEuro2(n, currency = "EUR") {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const cur = (currency || "EUR").toUpperCase();
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: cur === "USD" ? "USD" : "EUR", maximumFractionDigits: 2 }).format(Number(n));
}

/** Tri leads cockpit : plus récents en haut (dernière activité / création). */
function sortLeadsNewestFirst(leads) {
  if (!Array.isArray(leads) || leads.length < 2) return leads || [];
  return [...leads].sort((a, b) => {
    const ta = new Date(a?.created_at || 0).getTime();
    const tb = new Date(b?.created_at || 0).getTime();
    if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
    if (Number.isNaN(ta)) return 1;
    if (Number.isNaN(tb)) return -1;
    return tb - ta;
  });
}

/** Libellé d'arrivée du lead : jour + heure (backend envoie created_display_fr en heure Paris). */
function formatLeadProspectCreation(lead) {
  if (!lead) return "";
  if (lead.created_display_fr) return String(lead.created_display_fr);
  const raw = lead.created_at;
  if (!raw) return "";
  try {
    const d = new Date(String(raw));
    if (Number.isNaN(d.getTime())) return "";
    return (
      new Intl.DateTimeFormat("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Europe/Paris",
      }).format(d) + " (heure de Paris)"
    );
  } catch {
    return "";
  }
}

function deltaMonthText(v) {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  if (n === 0) return "Stable ce mois-ci";
  return n > 0 ? `+${formatIntlNumber(n)} ce mois-ci` : `${formatIntlNumber(n)} ce mois-ci`;
}

function deltaPercentDetail(p, fallback = "") {
  if (p === null || p === undefined || p === "") return fallback;
  const n = Number(p);
  if (!Number.isFinite(n)) return fallback;
  const sign = n > 0 ? "+" : "";
  return `${sign}${formatIntlNumber(n)}% vs période précédente`;
}

function pickKpisPayload(raw) {
  if (!raw) return {};
  if (raw.kpis && typeof raw.kpis === "object") return raw.kpis;
  return raw;
}

function pickLeadsBlock(summary, standalone) {
  if (summary?.leads && typeof summary.leads === "object") return summary.leads;
  if (!standalone) return {};
  if (standalone.leads && typeof standalone.leads === "object") return standalone.leads;
  if (Array.isArray(standalone.latest)) return { latest: standalone.latest };
  if (Array.isArray(standalone.latest_leads)) return { latest: standalone.latest_leads };
  if (standalone.new_leads_count != null || standalone.latest_leads || standalone.latest) return standalone;
  return {};
}

function normalizeActionItems(payload) {
  const arr = Array.isArray(payload) ? payload : payload?.items ?? payload?.action_items ?? [];
  return arr.map((row, idx) => ({
    id: row.id != null ? String(row.id) : `ai-${idx}-${row.title || ""}`,
    severity: row.severity || "info",
    tenant_id: row.tenant_id,
    tenant_name: row.tenant_name || row.tenant || "—",
    lead_id: row.lead_id,
    title: row.title || "Sans titre",
    description: row.description || row.meta || "",
    target_label: row.target_label || row.target || "",
    primary_action_label: row.primary_action_label || "Ouvrir",
    primary_action_url: row.primary_action_url || "",
    secondary_action_label: row.secondary_action_label || "",
    secondary_action_url: row.secondary_action_url || "",
    created_at: row.created_at,
  }));
}

function normalizeWatchlist(payload) {
  const arr = Array.isArray(payload) ? payload : payload?.items ?? payload?.watchlist ?? [];
  return arr.map((row, idx) => ({
    tenant_id: row.tenant_id,
    tenant_name: row.tenant_name || row.name || row.tenant || "—",
    label: row.label || row.signal_type || "Signal",
    value: row.value != null ? String(row.value) : "—",
    trend: row.trend || "",
    severity: row.severity || "info",
    target_url:
      row.target_url ||
      (row.tenant_id != null ? `/admin/tenants/${row.tenant_id}` : ""),
    key: row.tenant_id != null ? `wl-${row.tenant_id}-${idx}` : `wl-${idx}`,
  }));
}

const PERIOD_UI = [
  ["24h", "24h"],
  ["7j", "7d"],
  ["30j", "30d"],
  ["mois", "month"],
];

/** Bandeau « volume » leads : titre aligné sur le sélecteur de période du cockpit. */
function leadsVolumeHeading(apiPeriod) {
  switch (apiPeriod) {
    case "24h":
      return "24 dernières heures";
    case "7d":
      return "7 derniers jours";
    case "30d":
      return "30 derniers jours";
    case "month":
      return "Mois en cours (UTC)";
    default:
      return "Période sélectionnée";
  }
}

function toneSurface(tone) {
  switch (tone) {
    case "teal":
      return { fg: T.teal, bg: T.tealLight, border: `${T.teal}33` };
    case "navy":
      return { fg: NAVY, bg: "#EAF0F6", border: `${NAVY}22` };
    case "blue":
      return { fg: "#2563EB", bg: "#EAF1FF", border: "#2563EB22" };
    case "green":
      return { fg: "#039855", bg: "#EAF8F0", border: "#03985533" };
    case "orange":
      return { fg: T.orange, bg: T.orangeLight, border: `${T.orange}44` };
    case "red":
      return { fg: T.red, bg: T.redLight, border: `${T.red}44` };
    default:
      return { fg: T.textMuted, bg: T.neutralLight, border: T.border };
  }
}

function SeverityBadge({ severity }) {
  const label =
    severity === "critical" ? "Critique" : severity === "warning" ? "À surveiller" : "Info";
  const tone = severity === "critical" ? "red" : severity === "warning" ? "orange" : "blue";
  const s = toneSurface(tone);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 9px",
        borderRadius: radius.pill,
        fontSize: 11,
        fontWeight: 800,
        color: s.fg,
        background: s.bg,
        border: `1px solid ${s.border}`,
      }}
    >
      {label}
    </span>
  );
}

const SAMPLE_SUMMARY = {
  period: "30d",
  kpis: {
    active_tenants_count: 18,
    active_tenants_delta_month: 3,
    calls_handled_count: 1248,
    calls_delta_percent: 18,
    web_requests_count: 186,
    web_requests_delta_percent: 11,
    appointments_created_count: 342,
    appointments_created_delta_percent: 14,
    voice_minutes_used: 4820,
    included_minutes_total: 7100,
    usage_percent: 68,
    vapi_cost_current_period: 864.42,
    vapi_cost_currency: "EUR",
    vapi_cost_is_estimate: true,
    critical_alerts_count: 3,
  },
  leads: {
    new_leads_count: 5,
    to_qualify_today_count: 2,
    latest: [
      {
        id: "s1",
        name: "Dr Martin",
        source: "landing_cta",
        source_label: "Formulaire landing",
        status: "Nouveau",
        note: "Intéressé par essai gratuit",
        created_at: new Date().toISOString(),
        created_display_fr: "mardi 19 mai 2026 à 09:41 (heure de Paris)",
      },
      {
        id: "s2",
        name: "Cabinet Dentaire Lille",
        source: "landing_create_assistant",
        source_label: "Créer mon assistant",
        status: "À rappeler",
        note: "Landing praticien",
        created_display_fr: "lundi 18 mai 2026 à 17:05 (heure de Paris)",
      },
      {
        id: "s3",
        name: "Dr Bernard",
        source: "reseau",
        source_label: "Réseau",
        status: "Démo",
        note: "Attend créneau présentation",
        created_display_fr: "dimanche 17 mai 2026 à 11:22 (heure de Paris)",
      },
    ],
  },
};

const SAMPLE_ACTIONS = [
  {
    id: "demo-1",
    severity: "critical",
    tenant_id: 2001,
    tenant_name: "Cabinet Durand",
    title: "Agenda Google déconnecté",
    description: "12 tentatives de booking bloquées depuis ce matin",
    target_label: "Agenda",
    primary_action_label: "Voir fiche",
    primary_action_url: "/admin/tenants/2001",
    secondary_action_label: "Reconnecter",
    secondary_action_url: "/admin/tenants/2001",
  },
  {
    id: "demo-2",
    severity: "critical",
    tenant_id: 2002,
    tenant_name: "Cabinet Martin",
    title: "Paiement en échec depuis 5 jours",
    description: "Abonnement Growth · relance Stripe échouée",
    target_label: "Billing",
    primary_action_label: "Voir billing",
    primary_action_url: "/admin/tenants/2002",
    secondary_action_label: "Contacter",
    secondary_action_url: "/admin/leads",
  },
  {
    id: "demo-3",
    severity: "warning",
    tenant_id: 2003,
    tenant_name: "Cabinet Lopez",
    title: "12 demandes patients non traitées",
    description: "Issues de la page publique praticien",
    target_label: "Demandes patients",
    primary_action_label: "Voir fiche",
    primary_action_url: "/admin/tenants/2003",
    secondary_action_label: "Notifier",
    secondary_action_url: "/admin/tenants/2003",
  },
  {
    id: "demo-4",
    severity: "warning",
    tenant_id: 2004,
    tenant_name: "Cabinet Petit",
    title: "Quota minutes à 87%",
    description: "Starter · dépassement probable sous 4 jours",
    target_label: "Usage",
    primary_action_label: "Voir consommation",
    primary_action_url: "/admin/billing?tenant=2004&sort=usage_desc",
    secondary_action_label: "Proposer Growth",
    secondary_action_url: "/admin/tenants/2004",
  },
  {
    id: "demo-5",
    severity: "info",
    tenant_id: null,
    tenant_name: "Dr Bernard",
    lead_id: "s3",
    title: "Nouveau lead à qualifier",
    description: "Demande d'essai gratuit reçue hier soir",
    target_label: "Leads",
    primary_action_label: "Voir lead",
    primary_action_url: "/admin/leads/s3",
    secondary_action_label: "Planifier relance",
    secondary_action_url: "/admin/leads",
  },
];

const SAMPLE_WATCH = [
  {
    tenant_id: 2003,
    tenant_name: "Cabinet Lopez",
    label: "Demandes web",
    value: "42",
    trend: "+31%",
    severity: "info",
    target_url: "/admin/tenants/2003",
    key: "w1",
  },
  {
    tenant_id: 2004,
    tenant_name: "Cabinet Petit",
    label: "Minutes",
    value: "684",
    trend: "87% quota",
    severity: "warning",
    target_url: "/admin/tenants/2004",
    key: "w2",
  },
  {
    tenant_id: 2001,
    tenant_name: "Cabinet Durand",
    label: "Erreurs booking",
    value: "12",
    trend: "critique",
    severity: "critical",
    target_url: "/admin/tenants/2001",
    key: "w3",
  },
  {
    tenant_id: 2005,
    tenant_name: "Cabinet Moreau",
    label: "RDV créés",
    value: "58",
    trend: "+22%",
    severity: "info",
    target_url: "/admin/tenants/2005",
    key: "w4",
  },
];

export default function AdminDashboard() {
  const navigate = useNavigate();
  const isDev = import.meta.env.DEV;

  const [periodUi, setPeriodUi] = useState("30j");
  const [summary, setSummary] = useState(null);
  const [actions, setActions] = useState([]);
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [isSampleMode, setIsSampleMode] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [selection, setSelection] = useState({ kind: "kpi", id: "alerts" });
  const todayLabel = useMemo(
    () => new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" }).format(new Date()),
    [],
  );

  const apiPeriod = useMemo(() => PERIOD_UI.find(([u]) => u === periodUi)?.[1] || "30d", [periodUi]);
  const leadsVolTitle = leadsVolumeHeading(apiPeriod);
  const leadsEmptyMessage = `Aucun nouveau lead sur ${leadsVolTitle.toLowerCase()}.`;

  const load = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    let usedSample = false;
    let nextSummary = null;
    let nextActions = [];
    let nextWatch = [];
    let errMsg = null;

    try {
      const bundleRes = await getAdminDashboardBundle({ period: apiPeriod, severity: "all" });

      if (bundleRes && bundleRes.kpis) {
        nextSummary = {
          period: bundleRes.period,
          kpis: bundleRes.kpis,
          tenant_totals_hint: bundleRes.tenant_totals_hint,
          leads: bundleRes.leads,
          hints: bundleRes.hints,
        };
        nextActions = normalizeActionItems(bundleRes.actions);
        nextWatch = normalizeWatchlist(bundleRes.watchlist);
      } else if (isDev) {
        nextSummary = SAMPLE_SUMMARY;
        nextActions = SAMPLE_ACTIONS;
        nextWatch = SAMPLE_WATCH;
        usedSample = true;
      } else {
        errMsg = "Réponse cockpit vide.";
      }

      if (!nextSummary?.leads && isDev && nextSummary) {
        nextSummary = { ...nextSummary, leads: SAMPLE_SUMMARY.leads };
        usedSample = true;
      }
    } catch (e) {
      errMsg = e?.message || "Erreur réseau";
      if (isDev) {
        nextSummary = SAMPLE_SUMMARY;
        nextActions = SAMPLE_ACTIONS;
        nextWatch = SAMPLE_WATCH;
        usedSample = true;
      }
    }

    setSummary(nextSummary);
    setActions(nextActions);
    setWatchlist(nextWatch);
    setIsSampleMode(usedSample);
    setFetchError(errMsg);
    setLoading(false);
  }, [apiPeriod, isDev]);

  useEffect(() => {
    load();
  }, [load]);

  const kpis = pickKpisPayload(summary);

  const kpiCards = useMemo(() => {
    const k = kpis;
    const vapiLabel = k.vapi_cost_is_estimate ? "estimation période" : "réel période";
    const vapiExtra = k.vapi_cost_estimation_label || vapiLabel;

    return [
      {
        id: "clients",
        label: "Cabinets actifs",
        value: formatIntlNumber(k.active_tenants_count),
        detail: deltaMonthText(k.active_tenants_delta_month),
        route: "/admin/tenants?status=active",
        description: "Parc client réellement en service, tous canaux confondus.",
        tone: "teal",
        Icon: Building2,
      },
      {
        id: "calls",
        label: "Appels traités",
        value: formatIntlNumber(k.calls_handled_count),
        detail: deltaPercentDetail(k.calls_delta_percent, "Volume vocal sur la période"),
        route: "/admin/tenants?sort=calls_desc",
        description: "Volume vocal global traité par UWi sur la période.",
        tone: "navy",
        Icon: Phone,
      },
      {
        id: "web",
        label: "Demandes web",
        value: formatIntlNumber(k.web_requests_count),
        detail: deltaPercentDetail(k.web_requests_delta_percent, "via pages publiques praticiens"),
        route: "/admin/tenants?sort=web_requests_desc",
        description: "Demandes de RDV et contacts issus des pages publiques praticiens.",
        tone: "blue",
        Icon: Globe,
      },
      {
        id: "appointments",
        label: "RDV créés",
        value: formatIntlNumber(k.appointments_created_count),
        detail: deltaPercentDetail(k.appointments_created_delta_percent, "téléphone + web"),
        route: "/admin/tenants?sort=appointments_desc",
        description: "Rendez-vous créés ou confirmés dans les agendas.",
        tone: "green",
        Icon: Calendar,
      },
      {
        id: "minutes",
        label: "Minutes consommées",
        value: formatIntlNumber(k.voice_minutes_used),
        detail:
          k.usage_percent != null
            ? `${formatIntlNumber(k.usage_percent)}% du volume inclus`
            : k.included_minutes_total
              ? `sur ${formatIntlNumber(k.included_minutes_total)} min incluses`
              : "",
        route: "/admin/billing?sort=usage_desc",
        description: "Usage vocal et risque de dépassement par cabinet.",
        tone: "orange",
        Icon: Clock,
      },
      {
        id: "vapiCost",
        label: "Coût Vapi en cours",
        value: formatEuro2(k.vapi_cost_current_period, k.vapi_cost_currency),
        detail: vapiExtra,
        route: "/admin/billing?vendor=vapi",
        description:
          "Coût Vapi sur la période (estimation si l’API fournisseur n’est pas disponible). Pilotage marge plateforme.",
        tone: "orange",
        Icon: Euro,
      },
      {
        id: "alerts",
        label: "Alertes critiques",
        value: formatIntlNumber(k.critical_alerts_count),
        detail: "à traiter maintenant",
        route: "/admin/operations?severity=critical",
        description: "Incidents bloquants : agenda, paiement, assistant, routage, booking, webhooks…",
        tone: "red",
        Icon: AlertTriangle,
      },
    ].filter((card) => ["clients", "calls", "minutes", "alerts"].includes(card.id));
  }, [kpis]);

  const leadsBlock = pickLeadsBlock(summary, null);
  const newLeadsCount =
    leadsBlock.new_leads_count ?? leadsBlock.new_leads ?? leadsBlock.count ?? (leadsBlock.latest?.length || 0);
  const qualifyToday =
    leadsBlock.to_qualify_today_count ?? leadsBlock.leads_to_qualify_today_count ?? 0;
  const latestLeads = useMemo(() => {
    const raw = leadsBlock.latest ?? leadsBlock.latest_leads ?? [];
    return sortLeadsNewestFirst(raw);
  }, [leadsBlock.latest, leadsBlock.latest_leads]);

  const filteredActions = useMemo(() => {
    if (severityFilter === "all") return actions;
    if (severityFilter === "critical") return actions.filter((a) => a.severity === "critical");
    return actions.filter((a) => a.severity === "warning" || a.severity === "info");
  }, [actions, severityFilter]);

  const selectedKpi = kpiCards.find((c) => c.id === selection.id);

  const detail = useMemo(() => {
    if (selection.kind === "kpi" && selectedKpi) {
      return {
        title: selectedKpi.label,
        body: selectedKpi.description,
        primaryLabel: "Ouvrir",
        primaryTo: selectedKpi.route,
        secondaryLabel: "Créer un client",
        secondaryTo: "/admin/tenants/new",
        onSecondary: null,
      };
    }
    if (selection.kind === "task" && selection.task) {
      const t = selection.task;
      return {
        title: t.tenant_name,
        body: `${t.title} · ${t.description}`,
        primaryLabel: t.primary_action_label || "Ouvrir",
        primaryTo: t.primary_action_url || (t.tenant_id != null ? `/admin/tenants/${t.tenant_id}` : "/admin/operations"),
        secondaryLabel: t.secondary_action_label || "",
        secondaryTo: t.secondary_action_url || "",
        onSecondary: null,
      };
    }
    if (selection.kind === "watch" && selection.watch) {
      const w = selection.watch;
      return {
        title: w.tenant_name,
        body: `${w.label} · ${w.value} · ${w.trend}`,
        primaryLabel: "Ouvrir le cabinet",
        primaryTo: w.target_url || (w.tenant_id != null ? `/admin/tenants/${w.tenant_id}` : "/admin/tenants"),
        secondaryLabel: "",
        secondaryTo: "",
        onSecondary: null,
      };
    }
    return {
      title: "Sélection",
      body: "Clique sur une carte pour afficher le contexte et les actions.",
      primaryLabel: "Clients",
      primaryTo: "/admin/tenants",
      secondaryLabel: "",
      secondaryTo: "",
      onSecondary: null,
    };
  }, [selection, selectedKpi]);

  return (
    <>
      <style>{`
        ${keyframes}
        * { box-sizing: border-box; }
        @media (max-width: 900px) {
          .uwi-admin-quick-actions { grid-template-columns: repeat(2,minmax(0,1fr)) !important; }
          .uwi-admin-lead-row { grid-template-columns: minmax(0,1fr) auto !important; }
          .uwi-admin-lead-source { display: none !important; }
        }
        @media (max-width: 600px) {
          .uwi-admin-home { padding: 12px 10px 28px !important; }
          .uwi-admin-quick-actions { grid-template-columns: 1fr !important; }
          .uwi-admin-leads-summary { grid-template-columns: 1fr 1fr !important; }
          .uwi-admin-leads-summary > button { grid-column: 1 / -1; width: 100% !important; }
          .uwi-admin-lead-date { display: none !important; }
        }
      `}</style>

      <div className="uwi-admin-home" style={{ padding: "18px 20px 40px", minWidth: 0, maxWidth: 1500, margin: "0 auto", background: CDC_BG, fontFamily: font.body, color: T.text }}>
        <header
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 12,
            padding: "18px 20px",
            borderRadius: 20,
            border: `1px solid ${T.border}`,
            background: T.bgCard,
            boxShadow: "0 12px 32px rgba(7,26,51,.055)",
            animation: "uwi-fadein 0.35s ease both",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 800,
                color: T.teal,
                marginBottom: 4,
                textTransform: "capitalize",
              }}
            >
              {todayLabel}
            </div>
            <h1 style={{ fontSize: 25, fontWeight: 800, color: NAVY, letterSpacing: "-.03em", margin: 0, lineHeight: 1.1 }}>
              Bonjour Admin
            </h1>
            <p style={{ margin: "6px 0 0", fontSize: 13, color: T.textSecondary, maxWidth: 640, lineHeight: 1.5 }}>
              Voici ce qui demande votre attention aujourd&apos;hui.
            </p>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 4,
                padding: 4,
                borderRadius: radius.xxl,
                border: `1px solid ${CDC_BORDER}`,
                background: T.bgCard,
                boxShadow: shadow.card,
              }}
            >
              {PERIOD_UI.map(([label, key]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPeriodUi(label)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: radius.lg,
                    border: "none",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    fontSize: 13,
                    fontWeight: 800,
                    background: periodUi === label ? NAVY : "transparent",
                    color: periodUi === label ? "#fff" : T.textMuted,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </header>

        <section
          style={{
            marginBottom: 12,
            padding: "14px 16px",
            borderRadius: 16,
            border: `1px solid ${T.green}55`,
            background: T.greenLight,
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 34, height: 34, borderRadius: 11, display: "grid", placeItems: "center", color: T.green, background: "#fff" }}>
              <Sparkles size={17} />
            </span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: NAVY }}>Pilotage UWi en direct</div>
              <div style={{ marginTop: 2, fontSize: 12, fontWeight: 600, color: T.textSecondary }}>
                {Number(kpis.critical_alerts_count || 0) > 0
                  ? `${formatIntlNumber(kpis.critical_alerts_count)} alerte(s) critique(s) nécessitent une vérification.`
                  : "Aucune alerte critique. Les services principaux sont opérationnels."}
              </div>
            </div>
          </div>
          <button type="button" onClick={() => navigate("/admin/operations")} style={adminHomeDarkButton()}>
            Voir les opérations
          </button>
        </section>

        <section
          style={{
            marginBottom: 14,
            padding: "10px 12px 12px",
            borderRadius: 20,
            border: `1px solid ${T.border}`,
            background: T.bgCard,
            boxShadow: "0 10px 28px rgba(7,26,51,.055)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "0 2px 9px" }}>
            <strong style={{ fontSize: 14, color: NAVY }}>Actions rapides</strong>
            <button type="button" onClick={load} disabled={loading} style={{ border: 0, background: "transparent", color: T.textMuted, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
              {loading ? "Actualisation…" : "Actualiser"}
            </button>
          </div>
          <div className="uwi-admin-quick-actions" style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 9 }}>
            <button type="button" onClick={() => navigate("/admin/leads")} style={adminQuickAction(NAVY, "#fff", NAVY)}>
              <UserPlus size={16} /> Prospects
            </button>
            <button type="button" onClick={() => navigate("/admin/tenants")} style={adminQuickAction("#fff", NAVY, T.border)}>
              <Users size={16} /> Clients
            </button>
            <button type="button" onClick={() => navigate("/admin/tenants/new")} style={adminQuickAction(T.teal, "#fff", T.teal)}>
              <Plus size={16} /> Créer un client
            </button>
            <button type="button" onClick={() => navigate("/admin/billing")} style={adminQuickAction("#fff", T.green, `${T.green}55`)}>
              <Euro size={16} /> Facturation
            </button>
          </div>
        </section>

        {fetchError ? (
          <div
            style={{
              background: T.redLight,
              border: `1px solid ${T.red}40`,
              borderRadius: radius.xl,
              padding: "12px 16px",
              marginBottom: 16,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 13, color: T.red, fontWeight: 600 }}>{fetchError}</span>
            <button
              type="button"
              onClick={load}
              style={{ border: "none", background: "transparent", color: T.red, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" }}
            >
              Réessayer
            </button>
          </div>
        ) : null}

        {isSampleMode ? (
          <div
            style={{
              background: T.yellowLight,
              border: `1px solid ${T.yellow}55`,
              borderRadius: radius.xl,
              padding: "10px 16px",
              marginBottom: 16,
              fontSize: 13,
              color: T.yellowText,
              fontWeight: 600,
            }}
          >
            Mode démonstration (données fictives) : les endpoints{" "}
            <code style={{ fontSize: 12 }}>/api/admin/dashboard/*</code> ne sont pas disponibles ou vides.
          </div>
        ) : null}

        {/* Indicateurs essentiels */}
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(min(150px, 100%), 1fr))",
            gap: 10,
            marginBottom: 22,
          }}
        >
          {loading
            ? Array.from({ length: 4 }).map((_, i) => <KpiSkeleton key={i} />)
            : kpiCards.map((card) => {
                const active = selection.kind === "kpi" && selection.id === card.id;
                const s = toneSurface(card.tone);
                const Icon = card.Icon;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => navigate(card.route)}
                    style={{
                      textAlign: "left",
                      padding: 16,
                      borderRadius: 22,
                      border: `1px solid ${active ? s.fg : CDC_BORDER}`,
                      background: T.bgCard,
                      boxShadow: active ? shadow.cardHover : shadow.card,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "transform 0.12s, box-shadow 0.12s",
                      transform: active ? "translateY(-1px)" : "none",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                      <span
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 16,
                          display: "grid",
                          placeItems: "center",
                          border: `1px solid ${s.border}`,
                          background: s.bg,
                          color: s.fg,
                        }}
                      >
                        <Icon size={20} />
                      </span>
                      <ChevronRight size={18} style={{ opacity: active ? 0.9 : 0.35, color: active ? T.teal : T.textMuted }} />
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 800, color: T.textMuted, marginBottom: 4 }}>{card.label}</div>
                    <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: -0.03, color: NAVY }}>{card.value}</div>
                    <div style={{ marginTop: 6, fontSize: 11, fontWeight: 700, color: T.textMuted, lineHeight: 1.35 }}>{card.detail}</div>
                  </button>
                );
              })}
        </section>

        <LeadsOverview
          loading={loading}
          leads={latestLeads}
          newLeadsCount={newLeadsCount}
          qualifyToday={qualifyToday}
          periodLabel={leadsVolTitle}
          emptyMessage={leadsEmptyMessage}
          onOpenLead={(lead) =>
            navigate(lead?.id ? `/admin/leads?lead=${encodeURIComponent(lead.id)}` : "/admin/leads")
          }
          onOpenAll={() => navigate("/admin/leads")}
        />

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: 18 }}>
          {/* Actions */}
          <section
            style={{
              background: T.bgCard,
              border: `1px solid ${CDC_BORDER}`,
              borderRadius: 28,
              padding: 22,
              boxShadow: shadow.card,
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: NAVY }}>À traiter maintenant</h2>
                <p style={{ margin: "6px 0 0", fontSize: 13, color: T.textMuted, maxWidth: 520 }}>
                  Actions concrètes avant les statistiques détaillées — liens vers fiches tenants ou leads.
                </p>
              </div>
              <div style={{ display: "flex", gap: 4, padding: 4, borderRadius: radius.lg, border: `1px solid ${CDC_BORDER}`, background: T.bgSubtle }}>
                {[
                  ["all", "Tout"],
                  ["critical", "Critique"],
                  ["warning", "À surveiller"],
                ].map(([id, lbl]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setSeverityFilter(id)}
                    style={{
                      padding: "7px 12px",
                      borderRadius: 10,
                      border: "none",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      fontSize: 11,
                      fontWeight: 800,
                      background: severityFilter === id ? NAVY : "transparent",
                      color: severityFilter === id ? "#fff" : T.textMuted,
                    }}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <ColumnSkeleton rows={5} />
            ) : filteredActions.length === 0 ? (
              <div style={{ fontSize: 14, color: T.textMuted, padding: "12px 4px" }}>Aucun élément dans ce filtre.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {filteredActions.map((t, idx) => (
                  <div
                    key={t.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelection({ kind: "task", task: t })}
                    onKeyDown={(e) => e.key === "Enter" && setSelection({ kind: "task", task: t })}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr auto",
                      gap: 14,
                      alignItems: "center",
                      padding: 14,
                      borderRadius: 22,
                      border: `1px solid #E4ECEF`,
                      background: "#FBFDFD",
                      cursor: "pointer",
                      transition: "border-color 0.12s",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 16,
                          display: "grid",
                          placeItems: "center",
                          fontWeight: 900,
                          fontSize: 14,
                          color: toneSurface(t.severity === "critical" ? "red" : t.severity === "warning" ? "orange" : "blue").fg,
                          background: toneSurface(t.severity === "critical" ? "red" : t.severity === "warning" ? "orange" : "blue").bg,
                        }}
                      >
                        {idx + 1}
                      </span>
                      <SeverityBadge severity={t.severity} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 4 }}>
                        <span style={{ fontWeight: 800, color: NAVY }}>{t.tenant_name}</span>
                        {t.target_label ? (
                          <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: radius.pill, background: T.neutralLight, color: T.textMuted }}>
                            {t.target_label}
                          </span>
                        ) : null}
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 800 }}>{t.title}</div>
                      <div style={{ fontSize: 13, color: T.textMuted, marginTop: 2 }}>{t.description}</div>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "flex-end" }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(t.primary_action_url || (t.tenant_id != null ? `/admin/tenants/${t.tenant_id}` : "/admin/leads"));
                        }}
                        style={btnPrimarySmall()}
                      >
                        {t.primary_action_label}
                      </button>
                      {t.secondary_action_label ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(t.secondary_action_url || "/admin/tenants");
                          }}
                          style={btnGhostSmall()}
                        >
                          {t.secondary_action_label}
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Panneau détail */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <section
              style={{
                background: NAVY,
                borderRadius: 28,
                padding: 20,
                color: "#fff",
                boxShadow: shadow.card,
                flex: 1,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 14 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>Panneau détail</h2>
                  <p style={{ margin: "6px 0 0", fontSize: 13, color: "rgba(255,255,255,0.65)", maxWidth: 320 }}>
                    Contexte pour la carte sélectionnée.
                  </p>
                </div>
              </div>
              <div style={{ borderRadius: 22, border: "1px solid rgba(255,255,255,0.12)", padding: 16, background: "rgba(255,255,255,0.06)" }}>
                <div style={{ fontSize: 10, fontWeight: 900, letterSpacing: "0.16em", color: T.yellow, marginBottom: 6 }}>SÉLECTION</div>
                <div style={{ fontSize: 22, fontWeight: 900, marginBottom: 8, lineHeight: 1.2 }}>{detail.title}</div>
                <p style={{ margin: 0, fontSize: 14, color: "rgba(255,255,255,0.76)", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
                  {detail.body}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 14 }}>
                  <button type="button" onClick={() => navigate(detail.primaryTo)} style={ctaYellow()}>
                    {detail.primaryLabel}
                  </button>
                  {detail.secondaryLabel ? (
                    <button
                      type="button"
                      onClick={() => {
                        if (detail.onSecondary) detail.onSecondary();
                        else navigate(detail.secondaryTo);
                      }}
                      style={ctaGhost()}
                    >
                      {detail.secondaryLabel}
                    </button>
                  ) : null}
                </div>
              </div>
            </section>
          </aside>
        </div>

        {/* Watchlist */}
        <section
          style={{
            marginTop: 20,
            background: T.bgCard,
            border: `1px solid ${CDC_BORDER}`,
            borderRadius: 28,
            padding: 22,
            boxShadow: shadow.card,
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "space-between", marginBottom: 14 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: NAVY }}>Top cabinets à surveiller</h2>
              <p style={{ margin: "6px 0 0", fontSize: 13, color: T.textMuted }}>
                Signaux agrégés (pas la liste brute des appels) — ouvrir le tenant pour creuser.
              </p>
            </div>
          </div>
          {loading ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} style={{ height: 120, borderRadius: 22, ...shimmerBlock() }} />
              ))}
            </div>
          ) : watchlist.length === 0 ? (
            <div style={{ fontSize: 13, color: T.textMuted }}>Aucun cabinet sorti sur cette période.</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10 }}>
              {watchlist.map((w) => {
                const sev = w.severity === "critical" ? "red" : w.severity === "warning" ? "orange" : "teal";
                const s = toneSurface(sev);
                return (
                  <button
                    key={w.key}
                    type="button"
                    onClick={() => setSelection({ kind: "watch", watch: w })}
                    style={{
                      textAlign: "left",
                      padding: 16,
                      borderRadius: 22,
                      border: `1px solid #E4ECEF`,
                      background: "#FBFDFD",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "box-shadow 0.12s",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 900,
                          padding: "3px 8px",
                          borderRadius: radius.pill,
                          background: s.bg,
                          color: s.fg,
                          border: `1px solid ${s.border}`,
                        }}
                      >
                        {w.label}
                      </span>
                      <ChevronRight size={16} style={{ opacity: 0.4 }} />
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: NAVY }}>{w.tenant_name}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginTop: 8, gap: 8 }}>
                      <span style={{ fontSize: 26, fontWeight: 900, color: NAVY }}>{w.value}</span>
                      <span style={{ fontSize: 11, fontWeight: 800, color: T.textMuted, paddingBottom: 4 }}>{w.trend}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      </div>

    </>
  );
}

function LeadsOverview({
  loading,
  leads,
  newLeadsCount,
  qualifyToday,
  periodLabel,
  emptyMessage,
  onOpenLead,
  onOpenAll,
}) {
  const visibleLeads = leads.slice(0, 5);

  return (
    <section
      style={{
        marginBottom: 18,
        borderRadius: 20,
        border: `1px solid ${CDC_BORDER}`,
        background: T.bgCard,
        boxShadow: "0 12px 32px rgba(7,26,51,.055)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "18px 20px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          borderBottom: `1px solid ${T.border}`,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <span style={{ width: 34, height: 34, borderRadius: 11, display: "grid", placeItems: "center", color: T.teal, background: T.tealLight }}>
              <UserPlus size={17} />
            </span>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: NAVY }}>Prospects à suivre</h2>
              <p style={{ margin: "3px 0 0", fontSize: 12, color: T.textMuted }}>
                Les derniers contacts, classés du plus récent au plus ancien.
              </p>
            </div>
          </div>
        </div>

        <div
          className="uwi-admin-leads-summary"
          style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(120px,auto)) auto", gap: 8 }}
        >
          <div style={leadSummaryCard()}>
            <span style={{ fontSize: 11, fontWeight: 700, color: T.textMuted }}>Nouveaux · {periodLabel}</span>
            <strong style={{ fontSize: 22, color: NAVY }}>{loading ? "…" : formatIntlNumber(newLeadsCount)}</strong>
          </div>
          <div style={leadSummaryCard(qualifyToday > 0)}>
            <span style={{ fontSize: 11, fontWeight: 700, color: T.textMuted }}>À qualifier</span>
            <strong style={{ fontSize: 22, color: qualifyToday > 0 ? T.orange : NAVY }}>
              {loading ? "…" : formatIntlNumber(qualifyToday)}
            </strong>
          </div>
          <button type="button" onClick={onOpenAll} style={adminHomeDarkButton()}>
            Ouvrir le pipeline
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 20 }}><ColumnSkeleton rows={3} /></div>
      ) : visibleLeads.length === 0 ? (
        <div style={{ padding: "26px 20px", textAlign: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: NAVY }}>{emptyMessage}</div>
          <p style={{ margin: "5px 0 0", fontSize: 12, color: T.textMuted }}>Les nouveaux prospects apparaîtront automatiquement ici.</p>
        </div>
      ) : (
        <div>
          {visibleLeads.map((lead) => {
            const status = leadStatusMeta(lead.status);
            const source = lead.source_label || lead.source || "Source inconnue";
            const contact = lead.email || lead.phone || "Coordonnées à compléter";
            return (
              <button
                key={lead.id || `${lead.name}-${lead.created_at}`}
                type="button"
                className="uwi-admin-lead-row"
                onClick={() => onOpenLead(lead)}
                style={{
                  width: "100%",
                  display: "grid",
                  gridTemplateColumns: "minmax(230px,1.5fr) minmax(130px,.65fr) minmax(150px,.7fr) auto",
                  alignItems: "center",
                  gap: 14,
                  padding: "13px 20px",
                  border: "none",
                  borderBottom: `1px solid ${T.border}`,
                  background: "#fff",
                  color: T.text,
                  textAlign: "left",
                  fontFamily: "inherit",
                  cursor: "pointer",
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
                  <span style={{ width: 38, height: 38, flexShrink: 0, borderRadius: 12, display: "grid", placeItems: "center", background: T.tealLight, color: T.tealDark, fontSize: 12, fontWeight: 900 }}>
                    {leadInitials(lead.name)}
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 14, fontWeight: 800, color: NAVY, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {lead.name || "Prospect sans nom"}
                    </span>
                    <span style={{ display: "block", marginTop: 3, fontSize: 12, color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {contact}
                    </span>
                  </span>
                </span>
                <span className="uwi-admin-lead-source" style={{ minWidth: 0 }}>
                  <span style={{ display: "block", fontSize: 10, fontWeight: 700, color: T.textMuted, marginBottom: 4 }}>Origine</span>
                  <span style={{ fontSize: 12, fontWeight: 800, color: T.textSecondary }}>{source}</span>
                </span>
                <span className="uwi-admin-lead-date">
                  <span style={{ display: "block", fontSize: 10, fontWeight: 700, color: T.textMuted, marginBottom: 4 }}>Reçu</span>
                  <span style={{ fontSize: 12, fontWeight: 800, color: T.textSecondary }}>{formatLeadProspectCreation(lead) || "Date inconnue"}</span>
                </span>
                <span style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 10 }}>
                  <span style={{ padding: "5px 9px", borderRadius: radius.pill, background: status.bg, color: status.color, fontSize: 10, fontWeight: 900 }}>
                    {status.label}
                  </span>
                  <ChevronRight size={18} color={T.teal} />
                </span>
              </button>
            );
          })}
          {leads.length > visibleLeads.length ? (
            <button type="button" onClick={onOpenAll} style={{ width: "100%", padding: 12, border: 0, background: T.bgSubtle, color: T.tealDark, fontFamily: "inherit", fontSize: 12, fontWeight: 800, cursor: "pointer" }}>
              Voir les {formatIntlNumber(leads.length - visibleLeads.length)} autre(s) prospect(s)
            </button>
          ) : null}
        </div>
      )}
    </section>
  );
}

function leadSummaryCard(highlight = false) {
  return {
    minHeight: 54,
    padding: "8px 11px",
    borderRadius: 12,
    border: `1px solid ${highlight ? `${T.orange}55` : T.border}`,
    background: highlight ? T.orangeLight : T.bgSubtle,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    gap: 2,
  };
}

function leadInitials(name) {
  const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
}

function leadStatusMeta(status) {
  const normalized = String(status || "new").toLowerCase();
  if (["qualified", "qualifie", "qualifié"].includes(normalized)) return { label: "QUALIFIÉ", color: T.green, bg: T.greenLight };
  if (["converted", "converti", "client"].includes(normalized)) return { label: "CONVERTI", color: T.tealDark, bg: T.tealLight };
  if (["lost", "perdu", "rejected"].includes(normalized)) return { label: "CLOS", color: T.textMuted, bg: T.neutralLight };
  if (["contacted", "contacte", "contacté"].includes(normalized)) return { label: "CONTACTÉ", color: "#2563EB", bg: "#EFF6FF" };
  return { label: "À TRAITER", color: T.orange, bg: T.orangeLight };
}

function btnPrimarySmall() {
  return {
    padding: "8px 12px",
    borderRadius: 14,
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 11,
    fontWeight: 800,
    background: `linear-gradient(135deg,${T.teal},${T.tealDark})`,
    color: "#fff",
  };
}

function adminHomeDarkButton() {
  return {
    minHeight: 40,
    padding: "0 16px",
    borderRadius: 11,
    border: "none",
    background: NAVY,
    color: "#fff",
    fontFamily: "inherit",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
  };
}

function adminQuickAction(background, color, borderColor) {
  return {
    minHeight: 42,
    padding: "0 14px",
    borderRadius: 11,
    border: `1px solid ${borderColor}`,
    background,
    color,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    fontFamily: "inherit",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
  };
}

function btnGhostSmall() {
  return {
    padding: "8px 12px",
    borderRadius: 14,
    border: `1px solid ${CDC_BORDER}`,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 11,
    fontWeight: 800,
    background: T.bgCard,
    color: T.text,
  };
}

function ctaYellow() {
  return {
    padding: "10px 16px",
    borderRadius: 14,
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 13,
    fontWeight: 900,
    background: "#F5C842",
    color: NAVY,
  };
}

function ctaGhost() {
  return {
    padding: "10px 16px",
    borderRadius: 14,
    border: "1px solid rgba(255,255,255,0.22)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 13,
    fontWeight: 800,
    background: "transparent",
    color: "rgba(255,255,255,0.9)",
  };
}

function KpiSkeleton() {
  return (
    <div style={{ padding: 16, borderRadius: 22, border: `1px solid ${CDC_BORDER}`, background: T.bgCard }}>
      <div style={{ ...shimmerBlock(), height: 40, width: 40, borderRadius: 14, marginBottom: 10 }} />
      <div style={{ ...shimmerBlock(), height: 12, width: "55%", marginBottom: 8 }} />
      <div style={{ ...shimmerBlock(), height: 28, width: "40%" }} />
    </div>
  );
}

function ColumnSkeleton({ rows }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ height: 88, borderRadius: 20, ...shimmerBlock() }} />
      ))}
    </div>
  );
}

function shimmerBlock() {
  return {
    background: `linear-gradient(90deg, ${T.border} 25%, ${T.bgSubtle} 50%, ${T.border} 75%)`,
    backgroundSize: "200% 100%",
    animation: "uwi-shimmer 1.4s ease infinite",
  };
}
