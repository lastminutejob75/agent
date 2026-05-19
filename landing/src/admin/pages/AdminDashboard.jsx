/**
 * Cockpit pilotage plateforme — route /admin
 * Cf. CdC : 7 KPI, leads, actions prioritaires, watchlist, panneau contexte.
 * Style inline + tokens theme (pas Tailwind).
 */
import React, { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Phone,
  Globe,
  Calendar,
  Clock,
  Euro,
  AlertTriangle,
  Sparkles,
  ChevronRight,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import {
  adminApi,
  getAdminDashboardBundle,
} from "../../lib/adminApi.js";
import { T, radius, shadow, font, keyframes } from "../theme.js";

const CreateTenantModal = lazy(() => import("../components/CreateTenantModal.jsx"));

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

function leadsVolumeExplanation(apiPeriod) {
  if (apiPeriod === "month") {
    return "Nombre de leads créés depuis le 1er du mois (UTC). Suit le sélecteur de période en haut de page.";
  }
  return `Nombre de leads créés sur ${leadsVolumeHeading(apiPeriod).toLowerCase()} (fenêtre glissante). Suit le sélecteur de période en haut de page.`;
}

const QUALIFY_TOOLTIP =
  "File opérationnelle : compteur métier côté serveur (ex. statut « nouveau » / à traiter). Il ne change pas quand vous passez de 24 h à 7 jours ou au mois — ouvrez la liste leads pour la traiter.";

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
      { id: "s1", name: "Dr Martin", source: "LinkedIn", status: "Nouveau", note: "Intéressé par essai gratuit" },
      { id: "s2", name: "Cabinet Dentaire Lille", source: "Formulaire", status: "À rappeler", note: "Landing praticien" },
      { id: "s3", name: "Dr Bernard", source: "Réseau", status: "Démo", note: "Attend créneau présentation" },
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
  const [showCreate, setShowCreate] = useState(false);
  const [deletingLeadId, setDeletingLeadId] = useState(null);
  const [selection, setSelection] = useState({ kind: "kpi", id: "alerts" });

  const apiPeriod = useMemo(() => PERIOD_UI.find(([u]) => u === periodUi)?.[1] || "30d", [periodUi]);
  const leadsVolTitle = leadsVolumeHeading(apiPeriod);
  const leadsVolCaption = leadsVolumeExplanation(apiPeriod);
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

  const handleDeleteLead = useCallback(
    async (lead) => {
      const id = lead?.id;
      if (!id) return;
      const label = String(lead.name || id || "").slice(0, 120);
      if (
        !window.confirm(
          `Supprimer définitivement ce lead (${label}) ? Cette action est irréversible.`,
        )
      ) {
        return;
      }
      setDeletingLeadId(id);
      try {
        await adminApi.leadDelete(id);
        setSelection((prev) =>
          prev.kind === "lead" && prev.lead?.id === id ? { kind: "kpi", id: "clients" } : prev,
        );
        await load();
      } catch (e) {
        window.alert(e?.message || "Échec de la suppression.");
      } finally {
        setDeletingLeadId(null);
      }
    },
    [load],
  );

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
    ];
  }, [kpis]);

  const leadsBlock = pickLeadsBlock(summary, null);
  const newLeadsCount =
    leadsBlock.new_leads_count ?? leadsBlock.new_leads ?? leadsBlock.count ?? (leadsBlock.latest?.length || 0);
  const qualifyToday =
    leadsBlock.to_qualify_today_count ?? leadsBlock.leads_to_qualify_today_count ?? 0;
  const latestLeads = leadsBlock.latest ?? leadsBlock.latest_leads ?? [];

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
        secondaryTo: null,
        onSecondary: () => setShowCreate(true),
      };
    }
    if (selection.kind === "lead" && selection.lead) {
      const L = selection.lead;
      const id = L.id;
      return {
        title: L.name,
        body: [L.note, L.source && `Source : ${L.source}`, L.status && `Statut : ${L.status}`].filter(Boolean).join(" · "),
        primaryLabel: "Ouvrir le lead",
        primaryTo: id ? `/admin/leads/${id}` : "/admin/leads",
        secondaryLabel: "Tous les leads",
        secondaryTo: "/admin/leads",
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
      `}</style>

      <div style={{ padding: "28px 32px 40px", minWidth: 0, background: CDC_BG, fontFamily: font.body, color: T.text }}>
        <header
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 22,
            animation: "uwi-fadein 0.35s ease both",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 12px",
                borderRadius: radius.pill,
                border: `1px solid #BFE9EC`,
                background: T.bgCard,
                fontSize: 11,
                fontWeight: 800,
                color: T.tealDark,
                marginBottom: 10,
                boxShadow: shadow.card,
              }}
            >
              <Sparkles size={14} /> Accueil admin · aujourd&apos;hui
            </div>
            <h1 style={{ fontSize: 30, fontWeight: 800, color: NAVY, letterSpacing: -1, margin: 0, lineHeight: 1.1 }}>
              Pilotage UWi
            </h1>
            <p style={{ margin: "8px 0 0", fontSize: 14, color: T.textSecondary, maxWidth: 640, lineHeight: 1.5 }}>
              Vue macro : activité, valeur délivrée, coûts, risques et opportunités commerciales — détail dans les fiches
              clients.
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
            <button
              type="button"
              onClick={load}
              disabled={loading}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "9px 14px",
                borderRadius: radius.lg,
                border: `1px solid ${CDC_BORDER}`,
                background: T.bgCard,
                cursor: loading ? "wait" : "pointer",
                fontFamily: "inherit",
                fontWeight: 700,
                fontSize: 13,
                color: T.text,
              }}
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
              Rafraîchir
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "9px 14px",
                borderRadius: radius.lg,
                border: "none",
                cursor: "pointer",
                fontFamily: "inherit",
                fontWeight: 800,
                fontSize: 13,
                color: "#fff",
                background: `linear-gradient(135deg,${T.teal},${T.tealDark})`,
                boxShadow: shadow.card,
              }}
            >
              <Plus size={16} />
              Nouveau client
            </button>
          </div>
        </header>

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

        {/* 7 KPI */}
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(min(150px, 100%), 1fr))",
            gap: 10,
            marginBottom: 22,
          }}
        >
          {loading
            ? Array.from({ length: 7 }).map((_, i) => <KpiSkeleton key={i} />)
            : kpiCards.map((card) => {
                const active = selection.kind === "kpi" && selection.id === card.id;
                const s = toneSurface(card.tone);
                const Icon = card.Icon;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => setSelection({ kind: "kpi", id: card.id })}
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

          {/* Leads + panneau détail */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <section
              style={{
                background: T.bgCard,
                border: `1px solid ${CDC_BORDER}`,
                borderRadius: 28,
                padding: 20,
                boxShadow: shadow.card,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 14 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: NAVY }}>Leads</h2>
                  <p style={{ margin: "6px 0 0", fontSize: 13, color: T.textMuted, maxWidth: 320 }}>
                    Deux indicateurs : volume sur la période (sélecteur en haut) et file à qualifier (règle opérationnelle, indépendante).
                  </p>
                </div>
                <button type="button" onClick={() => navigate("/admin/leads")} style={btnPrimarySmall()}>
                  Voir les leads
                </button>
              </div>
              <div
                style={{
                  borderRadius: 22,
                  border: `1px solid #BFE9EC`,
                  background: T.tealLight,
                  padding: 14,
                  marginBottom: 12,
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 800, color: T.tealDark }}>Volume — {leadsVolTitle}</div>
                <p style={{ margin: "4px 0 0", fontSize: 11, fontWeight: 600, color: T.textMuted, lineHeight: 1.45 }}>
                  {leadsVolCaption}
                </p>
                {loading ? (
                  <div style={{ marginTop: 8, ...shimmerBar(120, 36) }} />
                ) : (
                  <div style={{ fontSize: 32, fontWeight: 900, color: NAVY, marginTop: 8 }}>{formatIntlNumber(newLeadsCount)}</div>
                )}
                <div
                  title={QUALIFY_TOOLTIP}
                  role="note"
                  style={{
                    marginTop: 12,
                    paddingTop: 12,
                    borderTop: `1px dashed rgba(15,118,142,0.35)`,
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 900, color: T.tealDark, letterSpacing: "0.02em" }}>
                    À qualifier · vue live
                  </div>
                  {loading ? (
                    <div style={{ marginTop: 8, ...shimmerBar(180, 14) }} />
                  ) : (
                    <>
                      <div style={{ fontSize: 15, fontWeight: 800, color: NAVY, marginTop: 4 }}>
                        {qualifyToday ? `${formatIntlNumber(qualifyToday)} lead(s)` : "0 lead en file (règles actuelles)"}
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: T.textMuted, marginTop: 4, lineHeight: 1.45 }}>
                        Indépendant du sélecteur de période — survolez cette zone pour le détail.
                      </div>
                    </>
                  )}
                </div>
              </div>
              {loading ? (
                <ColumnSkeleton rows={3} />
              ) : latestLeads.length === 0 ? (
                <div style={{ fontSize: 13, color: T.textMuted }}>{leadsEmptyMessage}</div>
              ) : (
                <>
                  <div style={{ fontSize: 11, fontWeight: 800, color: T.textMuted, marginBottom: 6 }}>
                    Leads ({leadsVolTitle.toLowerCase()}) — jusqu’à 80 · suppression définitive
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      maxHeight: 440,
                      overflowY: "auto",
                      paddingRight: 4,
                    }}
                  >
                    {latestLeads.map((lead) => (
                      <div
                        key={lead.id || lead.name}
                        style={{
                          display: "flex",
                          gap: 8,
                          alignItems: "stretch",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setSelection({ kind: "lead", lead })}
                          style={{
                            flex: 1,
                            minWidth: 0,
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: 8,
                            textAlign: "left",
                            padding: 12,
                            borderRadius: 16,
                            border: `1px solid #E4ECEF`,
                            background: "#FBFDFD",
                            cursor: "pointer",
                            fontFamily: "inherit",
                          }}
                        >
                          <span style={{ minWidth: 0 }}>
                            <span style={{ display: "block", fontSize: 14, fontWeight: 800, color: NAVY }}>{lead.name}</span>
                            <span
                              style={{
                                display: "block",
                                fontSize: 11,
                                fontWeight: 700,
                                color: T.textMuted,
                                marginTop: 2,
                              }}
                            >
                              {lead.source} · {lead.status}
                            </span>
                          </span>
                          <ChevronRight size={18} color={T.teal} style={{ flexShrink: 0 }} />
                        </button>
                        <button
                          type="button"
                          title="Supprimer définitivement ce lead"
                          aria-label={`Supprimer le lead ${lead.name || lead.id || ""}`}
                          disabled={deletingLeadId === lead.id}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            handleDeleteLead(lead);
                          }}
                          style={{
                            flexShrink: 0,
                            width: 46,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            borderRadius: 16,
                            border: "1px solid #F5C6CB",
                            background: deletingLeadId === lead.id ? "#F3F4F6" : "#FFF5F5",
                            cursor: deletingLeadId === lead.id ? "wait" : "pointer",
                            color: "#B71C1C",
                            fontFamily: "inherit",
                          }}
                        >
                          <Trash2 size={18} strokeWidth={2} />
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>

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
                <p style={{ margin: 0, fontSize: 14, color: "rgba(255,255,255,0.76)", lineHeight: 1.55 }}>{detail.body}</p>
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

      {showCreate ? (
        <Suspense fallback={null}>
          <CreateTenantModal
            onClose={() => setShowCreate(false)}
            onCreated={() => {
              setShowCreate(false);
              load();
            }}
          />
        </Suspense>
      ) : null}
    </>
  );
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

function shimmerBar(w, h) {
  return {
    width: w,
    height: h,
    borderRadius: 10,
    ...shimmerBlock(),
  };
}
