import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  getDashboardPayload,
  getRecentCalls,
  getBillingOverview,
  getBillingPlans,
  changeTenantPlan,
  cancelTenantSubscription,
  resumeTenantSubscription,
  getStripePortalLink,
} from "../../lib/adminApi";
import CreateTenantModal from "../components/CreateTenantModal";

// ── Brand tokens ──────────────────────────────────────────────────────────────
const C = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  blue: "#5BA8FF",
  text: "#FFFFFF",
  muted: "#6B90A8",
  danger: "#FF6B6B",
  warning: "#FFB347",
};

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, trend, color, delay }) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: "20px 22px",
        position: "relative",
        overflow: "hidden",
        animation: `uwi-fadein 0.5s ease ${delay}s both`,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg,${color},transparent)`,
        }}
      />
      <div
        style={{
          fontSize: 11,
          color: C.muted,
          fontWeight: 600,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 32,
          fontWeight: 800,
          color: C.text,
          letterSpacing: -1,
          lineHeight: 1,
          marginBottom: 6,
        }}
      >
        {value}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {trend != null && (
          <span
            style={{
              fontSize: 11,
              color: trend > 0 ? C.accent : C.danger,
              fontWeight: 600,
            }}
          >
            {trend > 0 ? "↑" : "↓"} {Math.abs(trend)}%
          </span>
        )}
        <span style={{ fontSize: 11, color: C.muted }}>{sub}</span>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: -20,
          right: -20,
          width: 80,
          height: 80,
          borderRadius: "50%",
          background: `radial-gradient(circle,${color}18,transparent)`,
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

// ── Status Badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    booking_confirmed: { label: "RDV", color: C.accent },
    transferred_human: { label: "Transfert", color: C.warning },
    transferred: { label: "Transfert", color: C.warning },
    user_abandon: { label: "Abandon", color: C.danger },
    abandon: { label: "Abandon", color: C.danger },
    error: { label: "Erreur", color: C.danger },
    rdv: { label: "RDV", color: C.accent },
    info: { label: "Info", color: C.blue },
    abandon_: { label: "Abandon", color: C.danger },
    transfert: { label: "Transfert", color: C.warning },
  };
  const s = map[status] || { label: "Info", color: C.blue };
  return (
    <span
      style={{
        background: `${s.color}18`,
        color: s.color,
        border: `1px solid ${s.color}40`,
        borderRadius: 6,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 700,
      }}
    >
      {s.label}
    </span>
  );
}

// ── Tooltip chart ─────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "8px 14px",
        fontSize: 12,
        color: C.text,
      }}
    >
      <strong style={{ color: C.accent }}>{payload[0].value}</strong> appels
    </div>
  );
};

// ── Plan Badge ────────────────────────────────────────────────────────────────
function PlanBadge({ plan }) {
  const map = {
    free: { label: "Free", color: C.muted, bg: "rgba(107,144,168,0.12)" },
    starter: { label: "Starter", color: C.blue, bg: "rgba(91,168,255,0.12)" },
    growth: { label: "Growth", color: C.warning, bg: "rgba(255,179,71,0.12)" },
    pro: { label: "Pro", color: C.accent, bg: "rgba(0,229,160,0.12)" },
  };
  const s = map[plan?.toLowerCase()] || map.free;
  return (
    <span
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.color}40`,
        borderRadius: 6,
        padding: "3px 10px",
        fontSize: 11,
        fontWeight: 700,
      }}
    >
      {s.label}
    </span>
  );
}

// ── Stripe Badge ──────────────────────────────────────────────────────────────
function StripeBadge({ status }) {
  const map = {
    active: { label: "Actif", color: C.accent },
    past_due: { label: "Past due", color: C.danger },
    canceled: { label: "Annulé", color: C.muted },
    trialing: { label: "Essai", color: C.warning },
  };
  const s = map[status] || { label: "Non config", color: C.muted };
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: s.color, fontWeight: 600 }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: s.color,
          display: "inline-block",
        }}
      />
      {s.label}
    </span>
  );
}

function MiniStatCard({ label, value, hint, tone = C.text }) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 14,
        padding: "16px 18px",
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: C.muted,
          fontWeight: 700,
          letterSpacing: 0.8,
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 800, color: tone, letterSpacing: -0.8, lineHeight: 1 }}>
        {value}
      </div>
      {hint ? <div style={{ fontSize: 11, color: C.muted, marginTop: 6 }}>{hint}</div> : null}
    </div>
  );
}

function PanelCard({ title, subtitle, action = null, children }) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: 22,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 2 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, color: C.muted }}>{subtitle}</div> : null}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

const ACTIVATION_STEP_LABELS = {
  account: "email client",
  assistant: "assistant",
  phone: "numéro vocal",
  calendar: "agenda",
  horaires: "horaires",
  faq: "FAQ",
  first_visit_done: "1re visite",
};

const ACTIVATION_PRIORITY_UI = {
  blocking_before_launch: { label: "Bloquant", color: C.danger },
  setup_pending: { label: "Configuration", color: C.warning },
  first_visit_pending: { label: "1re visite", color: C.blue },
  fragile_active: { label: "Fragile", color: "#f59e0b" },
  billing_risk: { label: "Billing", color: "#fb7185" },
  ready: { label: "Prêt", color: C.accent },
};

// ── Quota Bar ─────────────────────────────────────────────────────────────────
function QuotaBar({ used, included }) {
  const pct = included > 0 ? Math.min((used / included) * 100, 100) : 0;
  const color = pct > 90 ? C.danger : pct > 70 ? C.warning : C.accent;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted, marginBottom: 5 }}>
        <span>{used} min utilisées</span>
        <span>{included} min incluses</span>
      </div>
      <div style={{ height: 5, background: C.border, borderRadius: 3, overflow: "hidden" }}>
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 3,
            transition: "width 0.6s ease",
          }}
        />
      </div>
      <div style={{ fontSize: 10, color: C.muted, marginTop: 4, textAlign: "right" }}>
        {Math.max(0, included - used)} min restantes
      </div>
    </div>
  );
}

// ── Tenant Billing Card ───────────────────────────────────────────────────────
function TenantBillingCard({ item, plans, onAction, navigate }) {
  const [expanded, setExpanded] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);

  const handlePortal = async () => {
    try {
      const { url } = await getStripePortalLink(item.tenant_id);
      window.open(url, "_blank");
    } catch (e) {
      setActionMsg("Portail indisponible : " + e.message);
    }
  };

  const handleCancel = async () => {
    if (!confirm(`Annuler l'abonnement de ${item.name} ?`)) return;
    try {
      await cancelTenantSubscription(item.tenant_id);
      setActionMsg("Abonnement annulé.");
      onAction();
    } catch (e) {
      setActionMsg("Erreur : " + e.message);
    }
  };

  const handleResume = async () => {
    try {
      await resumeTenantSubscription(item.tenant_id);
      setActionMsg("Abonnement réactivé.");
      onAction();
    } catch (e) {
      setActionMsg("Erreur : " + e.message);
    }
  };

  const isCanceled = item.stripe_status === "canceled";

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, overflow: "hidden" }}>
      <div
        onClick={() => setExpanded((e) => !e)}
        style={{
          padding: "18px 20px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/admin/tenants/${item.tenant_id}`);
            }}
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: C.text,
              marginBottom: 5,
              cursor: "pointer",
              textDecoration: "underline",
              textDecorationColor: "transparent",
            }}
            onMouseEnter={(e) => (e.target.style.color = C.accent)}
            onMouseLeave={(e) => (e.target.style.color = C.text)}
          >
            {item.name}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <PlanBadge plan={item.plan_key} />
            <StripeBadge status={item.stripe_status} />
          </div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: C.accent, letterSpacing: -0.5 }}>
            ${(item.usage?.cost_usd ?? 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>
            ce mois
          </div>
        </div>
        <div
          style={{
            color: C.muted,
            fontSize: 12,
            transform: expanded ? "rotate(180deg)" : "none",
            transition: "transform 0.2s",
          }}
        >
          ▼
        </div>
      </div>

      {expanded && (
        <div style={{ padding: "0 20px 20px", borderTop: `1px solid ${C.border}` }}>
          {item.quota && (
            <div style={{ marginTop: 16, marginBottom: 16 }}>
              <QuotaBar used={item.quota.used ?? 0} included={item.quota.included ?? 0} />
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              ["Customer ID", item.stripe_customer_id || "—"],
              ["Subscription", item.stripe_subscription_id || "—"],
              [
                "Prochain débit",
                item.current_period_end ? new Date(item.current_period_end * 1000).toLocaleDateString("fr-FR") : "—",
              ],
              ["MRR", item.mrr_eur ? `${item.mrr_eur}€` : "—"],
            ].map(([l, v]) => (
              <div key={l} style={{ background: C.surface, borderRadius: 8, padding: "8px 12px" }}>
                <div
                  style={{
                    fontSize: 10,
                    color: C.muted,
                    marginBottom: 3,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {l}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: C.text,
                    fontFamily: "monospace",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {v}
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                fontSize: 11,
                color: C.muted,
                marginBottom: 8,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}
            >
              Changer de plan
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {(plans || []).map((p) => (
                <button
                  key={p.id}
                  onClick={async () => {
                    if (!confirm(`Passer ${item.name} au plan ${p.name} ?`)) return;
                    try {
                      await changeTenantPlan(item.tenant_id, p.id || p.plan_key);
                      setActionMsg(`Plan → ${p.name}`);
                      onAction();
                    } catch (e) {
                      setActionMsg("Erreur : " + e.message);
                    }
                  }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    background: item.plan_key === (p.id || p.plan_key) ? "rgba(0,229,160,0.15)" : C.surface,
                    border: `1px solid ${item.plan_key === (p.id || p.plan_key) ? C.accent : C.border}`,
                    color: item.plan_key === (p.id || p.plan_key) ? C.accent : C.muted,
                  }}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              onClick={handlePortal}
              style={{
                padding: "8px 14px",
                borderRadius: 9,
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
                background: "rgba(91,168,255,0.1)",
                border: "1px solid rgba(91,168,255,0.3)",
                color: C.blue,
              }}
            >
              ↗ Portail Stripe
            </button>
            {isCanceled ? (
              <button
                onClick={handleResume}
                style={{
                  padding: "8px 14px",
                  borderRadius: 9,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  background: "rgba(0,229,160,0.1)",
                  border: "1px solid rgba(0,229,160,0.3)",
                  color: C.accent,
                }}
              >
                ↺ Réactiver
              </button>
            ) : (
              <button
                onClick={handleCancel}
                style={{
                  padding: "8px 14px",
                  borderRadius: 9,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  background: "rgba(255,107,107,0.1)",
                  border: "1px solid rgba(255,107,107,0.3)",
                  color: C.danger,
                }}
              >
                ✕ Annuler
              </button>
            )}
          </div>
          {actionMsg && (
            <div
              style={{
                marginTop: 10,
                fontSize: 12,
                color: C.accent,
                padding: "8px 12px",
                background: "rgba(0,229,160,0.08)",
                borderRadius: 8,
              }}
            >
              {actionMsg}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Hooks ─────────────────────────────────────────────────────────────────────
function useDashboard(days) {
  const [data, setData] = useState(null);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [payload, callsRes] = await Promise.all([
        getDashboardPayload(days),
        getRecentCalls(1, 5),
      ]);
      setData(payload);
      setCalls(callsRes?.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    refresh();
  }, [refresh]);
  return { data, calls, loading, error, refresh };
}

function useBillingOverview() {
  const [overview, setOverview] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, pl] = await Promise.all([getBillingOverview(month), getBillingPlans()]);
      setOverview(ov);
      setPlans(pl?.items ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    load();
  }, [load]);
  return { overview, plans, loading, error, month, setMonth, reload: load };
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: "20px 22px",
        height: 100,
      }}
    >
      <div
        style={{
          width: 60,
          height: 10,
          borderRadius: 4,
          background: C.border,
          marginBottom: 12,
          animation: "uwi-shimmer 1.5s ease infinite",
        }}
      />
      <div
        style={{
          width: 80,
          height: 28,
          borderRadius: 6,
          background: C.border,
          animation: "uwi-shimmer 1.5s ease 0.1s infinite",
        }}
      />
    </div>
  );
}

// ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
export default function AdminDashboard() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState("30j");
  const [showCreate, setShowCreate] = useState(false);

  const days = period === "7j" ? 7 : period === "90j" ? 90 : 30;
  const { data, calls, loading, error, refresh } = useDashboard(days);
  const {
    overview,
    plans,
    loading: billingLoading,
    error: billingError,
    month,
    setMonth,
    reload: reloadBilling,
  } = useBillingOverview();

  // ── Mapping données API → UI ──
  const RESULT_MAP = {
    booking_confirmed: "rdv",
    transferred_human: "transfert",
    transferred: "transfert",
    user_abandon: "abandon",
    abandon: "abandon",
    error: "abandon",
  };

  const kpis = data
    ? [
        {
          label: "Appels",
          value: data.global?.calls_total ?? 0,
          sub: `${data.global?.errors_total ?? 0} erreurs`,
          trend: null,
          color: C.accent,
          delay: 0.05,
        },
        {
          label: "RDV confirmés",
          value: data.global?.appointments_total ?? 0,
          sub: "ce mois",
          trend: null,
          color: C.blue,
          delay: 0.1,
        },
        {
          label: `Coût ${period}`,
          value: `$${(data.global?.cost_usd_total ?? 0).toFixed(2)}`,
          sub: "via Vapi",
          trend: null,
          color: C.warning,
          delay: 0.15,
        },
        {
          label: "Clients actifs",
          value: data.global?.tenants_active ?? 0,
          sub: `/${data.global?.tenants_total ?? 0} total`,
          trend: null,
          color: C.muted,
          delay: 0.2,
        },
      ]
    : [];

  const activityData =
    data?.timeseries?.points?.map((p) => ({
      day: new Date(p.date).toLocaleDateString("fr-FR", { weekday: "short" }).slice(0, 1).toUpperCase(),
      appels: p.value,
    })) ?? [];

  const topClients =
    data?.topTenantsCalls?.items?.slice(0, 4).map((item) => {
      const costItem = data.topTenantsCost?.items?.find((c) => c.tenant_id === item.tenant_id);
      return {
        id: item.tenant_id,
        name: item.name ?? `Tenant #${item.tenant_id}`,
        appels: item.value,
        cost: (costItem?.value ?? 0).toFixed(2),
      };
    }) ?? [];

  const subStats = data
    ? [
        ["Transferts", data.global?.transfers_total ?? 0, C.blue],
        ["Minutes", data.global?.minutes_total ?? 0, C.accent],
        ["Erreurs", data.global?.errors_total ?? 0, C.danger],
      ]
    : [];

  const recentCalls = calls.map((c) => ({
    time: new Date(c.started_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    client: c.tenant_name ?? "—",
    dur: c.duration_min != null ? `${c.duration_min}m` : "—",
    status: RESULT_MAP[c.result] ?? "info",
    num: c.call_id?.slice(0, 16) ?? "—",
    tenantId: c.tenant_id,
    callId: c.call_id,
  }));

  const tenants = overview?.tenants ?? [];
  const urgentBillingItems = tenants
    .filter((item) => ["past_due", "canceled"].includes((item?.stripe_status || "").toLowerCase()))
    .slice(0, 4)
    .map((item) => ({
      id: `billing-${item.tenant_id}`,
      tenantId: item.tenant_id,
      title: item.name || `Tenant #${item.tenant_id}`,
      reason: item.stripe_status === "past_due" ? "Facturation en retard" : "Abonnement annulé",
      detail:
        item.stripe_status === "past_due"
          ? "Relancer le client ou ouvrir le portail Stripe."
          : "Vérifier si le cabinet doit être réactivé.",
      tone: item.stripe_status === "past_due" ? C.danger : C.warning,
      cta: item.stripe_status === "past_due" ? "Ouvrir la fiche" : "Vérifier le dossier",
    }));

  const quotaAlerts = tenants
    .filter((item) => {
      const included = item?.quota?.included ?? 0;
      const used = item?.quota?.used ?? 0;
      return included > 0 && used / included >= 0.85;
    })
    .slice(0, 4)
    .map((item) => ({
      id: `quota-${item.tenant_id}`,
      tenantId: item.tenant_id,
      title: item.name || `Tenant #${item.tenant_id}`,
      reason: "Quota presque atteint",
      detail: `${item?.quota?.used ?? 0}/${item?.quota?.included ?? 0} min utilisées.`,
      tone: C.warning,
      cta: "Ajuster le plan",
    }));

  const topActionItems = [...urgentBillingItems, ...quotaAlerts].slice(0, 6);

  const operatorQueue = recentCalls
    .filter((call) => ["transfert", "abandon"].includes(call.status))
    .slice(0, 5)
    .map((call) => ({
      id: `call-${call.callId}`,
      tenantId: call.tenantId,
      title: call.client,
      reason: call.status === "transfert" ? "Appel transféré" : "Abandon / friction",
      detail: `${call.time} · ${call.dur} · ${call.num}`,
      tone: call.status === "transfert" ? C.warning : C.danger,
      cta: "Voir le tenant",
    }));

  const actionQueue = [...operatorQueue, ...topActionItems].slice(0, 6);

  const healthSignals = [
    {
      label: "Past due",
      value: overview?.summary?.tenants_past_due_count ?? 0,
      hint: "clients à relancer",
      tone: (overview?.summary?.tenants_past_due_count ?? 0) > 0 ? C.danger : C.accent,
    },
    {
      label: "Appels transférés",
      value: data?.global?.transfers_total ?? 0,
      hint: `${days} derniers jours`,
      tone: (data?.global?.transfers_total ?? 0) > 0 ? C.warning : C.text,
    },
    {
      label: "Erreurs",
      value: data?.global?.errors_total ?? 0,
      hint: "anti-loop / incidents",
      tone: (data?.global?.errors_total ?? 0) > 0 ? C.danger : C.text,
    },
    {
      label: "Dernière activité",
      value: data?.global?.last_activity_at
        ? new Date(data.global.last_activity_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
        : "—",
      hint: "trace la plus récente",
      tone: C.blue,
    },
  ];

  const activationQueue = data?.activationQueue?.items ?? [];
  const activationSummary = data?.activationQueue?.summary ?? {};

  return (
    <>
      <style>{`
        @keyframes uwi-fadein  { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        @keyframes uwi-pulse   { 0%,100%{opacity:1} 50%{opacity:.4} }
        @keyframes uwi-shimmer { 0%,100%{opacity:.4} 50%{opacity:.8} }
      `}</style>

      <div style={{ padding: "32px", minWidth: 0 }}>
        {/* ── Header ── */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            marginBottom: 32,
            animation: "uwi-fadein 0.4s ease both",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: C.text, letterSpacing: -1, marginBottom: 4 }}>
              Dashboard
            </h1>
            <div style={{ fontSize: 13, color: C.muted }}>
              Vue d'ensemble ·{" "}
              <span style={{ color: C.accent }}>
                Mis à jour à {new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {["7j", "30j", "90j"].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                style={{
                  padding: "7px 16px",
                  borderRadius: 10,
                  border: `1px solid ${period === p ? C.accent : C.border}`,
                  background: period === p ? "rgba(0,229,160,0.1)" : "transparent",
                  color: period === p ? C.accent : C.muted,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.15s",
                }}
              >
                {p}
              </button>
            ))}
            <button
              onClick={refresh}
              disabled={loading}
              style={{
                padding: "7px 16px",
                borderRadius: 10,
                background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                border: "none",
                color: C.bg,
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {loading ? "…" : "↺ Rafraîchir"}
            </button>
            <button
              onClick={() => setShowCreate(true)}
              style={{
                padding: "7px 16px",
                borderRadius: 10,
                background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                border: "none",
                color: C.bg,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              + Nouveau client
            </button>
          </div>
        </div>

        {/* ── Erreur globale ── */}
        {error && (
          <div
            style={{
              background: "rgba(255,107,107,0.1)",
              border: "1px solid rgba(255,107,107,0.3)",
              borderRadius: 12,
              padding: "12px 20px",
              marginBottom: 20,
              fontSize: 13,
              color: C.danger,
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>⚠️ {error}</span>
            <button
              onClick={refresh}
              style={{ background: "transparent", border: "none", color: C.danger, cursor: "pointer", fontWeight: 700 }}
            >
              Réessayer
            </button>
          </div>
        )}

        {/* ── Control strip ── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14, marginBottom: 24 }}>
          {loading
            ? Array(4)
                .fill(0)
                .map((_, i) => <SkeletonCard key={i} />)
            : [
                {
                  label: "Clients actifs",
                  value: data?.global?.tenants_active ?? 0,
                  hint: `${data?.global?.tenants_total ?? 0} clients au total`,
                  tone: C.text,
                },
                {
                  label: "Past due",
                  value: overview?.summary?.tenants_past_due_count ?? 0,
                  hint: "à traiter maintenant",
                  tone: (overview?.summary?.tenants_past_due_count ?? 0) > 0 ? C.danger : C.accent,
                },
                {
                  label: "MRR",
                  value: `${overview?.summary?.mrr_eur_total ?? 0}€`,
                  hint: month,
                  tone: C.accent,
                },
                {
                  label: `Coût ${period}`,
                  value: `$${(data?.global?.cost_usd_total ?? 0).toFixed(2)}`,
                  hint: "usage Vapi",
                  tone: C.warning,
                },
              ].map((item) => <MiniStatCard key={item.label} {...item} />)}
        </div>

        {/* ── Action panels ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 14, marginBottom: 24 }}>
          <PanelCard
            title="À traiter maintenant"
            subtitle="Relances billing, saturation quota, appels transférés ou abandonnés."
            action={
              <button
                onClick={() => navigate("/admin/tenants")}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.muted,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Voir clients →
              </button>
            }
          >
            {actionQueue.length === 0 ? (
              <div style={{ fontSize: 13, color: C.muted }}>Aucune alerte prioritaire détectée.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {actionQueue.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "12px 14px",
                      borderRadius: 12,
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                    }}
                  >
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: item.tone, flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 3 }}>{item.title}</div>
                      <div style={{ fontSize: 11, color: item.tone, marginBottom: 3 }}>{item.reason}</div>
                      <div style={{ fontSize: 11, color: C.muted }}>{item.detail}</div>
                    </div>
                    <button
                      onClick={() => navigate(`/admin/tenants/${item.tenantId}`)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 9,
                        background: `${item.tone}18`,
                        border: `1px solid ${item.tone}40`,
                        color: item.tone,
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: "pointer",
                        fontFamily: "inherit",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.cta}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </PanelCard>

          <PanelCard
            title="Signaux d'exploitation"
            subtitle="État court pour savoir si la journée dérive."
            action={
              <button
                onClick={() => navigate("/admin/operations")}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.muted,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Operations →
              </button>
            }
          >
            <div style={{ display: "grid", gap: 10 }}>
              {healthSignals.map((signal) => (
                <div
                  key={signal.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, color: C.muted, marginBottom: 4 }}>{signal.label}</div>
                    <div style={{ fontSize: 11, color: C.muted }}>{signal.hint}</div>
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: signal.tone, letterSpacing: -0.7 }}>
                    {signal.value}
                  </div>
                </div>
              ))}
            </div>
          </PanelCard>
        </div>

        <PanelCard
          title="Cabinets à activer"
          subtitle="Priorisés par blocage réel, configuration, première visite, fragilité technique et risque billing."
          action={
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {[
                ["Bloquants", activationSummary.blocking_before_launch ?? 0, C.danger],
                ["Configuration", activationSummary.setup_pending ?? 0, C.warning],
                ["1re visite", activationSummary.first_visit_pending ?? 0, C.blue],
                ["Fragiles", activationSummary.fragile_active ?? 0, "#f59e0b"],
                ["Billing", activationSummary.billing_risk ?? 0, "#fb7185"],
              ].map(([label, value, color]) => (
                <div
                  key={label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 10px",
                    borderRadius: 999,
                    background: `${color}18`,
                    border: `1px solid ${color}30`,
                    color,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  <span>{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          }
        >
          {activationQueue.length === 0 ? (
            <div style={{ fontSize: 13, color: C.muted }}>Tous les cabinets actifs semblent prêts.</div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {activationQueue.map((item) => (
                <div
                  key={item.tenant_id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1.2fr auto auto",
                    gap: 12,
                    alignItems: "center",
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3, flexWrap: "wrap" }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{item.tenant_name}</div>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          borderRadius: 999,
                          padding: "3px 8px",
                          background: `${(ACTIVATION_PRIORITY_UI[item.priority_key] || ACTIVATION_PRIORITY_UI.ready).color}18`,
                          border: `1px solid ${(ACTIVATION_PRIORITY_UI[item.priority_key] || ACTIVATION_PRIORITY_UI.ready).color}30`,
                          color: (ACTIVATION_PRIORITY_UI[item.priority_key] || ACTIVATION_PRIORITY_UI.ready).color,
                        }}
                      >
                        {(ACTIVATION_PRIORITY_UI[item.priority_key] || ACTIVATION_PRIORITY_UI.ready).label}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: (ACTIVATION_PRIORITY_UI[item.priority_key] || ACTIVATION_PRIORITY_UI.ready).color,
                        marginBottom: 4,
                      }}
                    >
                      {item.primary_reason}
                      {item.missing_count > 0
                        ? ` · ${item.missing_count} point${item.missing_count > 1 ? "s" : ""} à compléter`
                        : " · suivi prioritaire"}
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {(item.missing_steps || []).slice(0, 5).map((step) => (
                        <span
                          key={step}
                          style={{
                            fontSize: 10,
                            color: C.muted,
                            border: `1px solid ${C.border}`,
                            borderRadius: 999,
                            padding: "3px 8px",
                          }}
                        >
                          {ACTIVATION_STEP_LABELS[step] || step}
                        </span>
                      ))}
                      {item.call_lock_timeout_alert ? (
                        <span
                          style={{
                            fontSize: 10,
                            color: "#f59e0b",
                            border: "1px solid rgba(245,158,11,0.3)",
                            borderRadius: 999,
                            padding: "3px 8px",
                          }}
                        >
                          lock timeout
                        </span>
                      ) : null}
                      {item.stripe_status ? (
                        <span
                          style={{
                            fontSize: 10,
                            color: "#fb7185",
                            border: "1px solid rgba(251,113,133,0.28)",
                            borderRadius: 999,
                            padding: "3px 8px",
                          }}
                        >
                          Stripe {item.stripe_status}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>Plan</div>
                    <PlanBadge plan={item.plan_key} />
                  </div>
                  <button
                    onClick={() => navigate(`/admin/tenants/${item.tenant_id}`)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: 9,
                      background: "rgba(0,229,160,0.1)",
                      border: "1px solid rgba(0,229,160,0.28)",
                      color: C.accent,
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Ouvrir le cabinet
                  </button>
                </div>
              ))}
            </div>
          )}
        </PanelCard>

        {/* ── Operational rows ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.4fr", gap: 14, marginBottom: 24 }}>
          <PanelCard
            title="Top clients"
            subtitle="Cabinets les plus actifs sur la fenêtre."
            action={
              <button
                onClick={() => navigate("/admin/tenants")}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.muted,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Tous les clients →
              </button>
            }
          >
            {topClients.length === 0 ? (
              <div style={{ fontSize: 13, color: C.muted }}>Aucune donnée client sur la fenêtre.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {topClients.map((c, i) => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/admin/tenants/${c.id}`)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 12px",
                      borderRadius: 12,
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      cursor: "pointer",
                    }}
                  >
                    <div
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 7,
                        background: i === 0 ? "rgba(0,229,160,0.15)" : C.card,
                        border: `1px solid ${i === 0 ? C.accent : C.border}`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 10,
                        fontWeight: 800,
                        color: i === 0 ? C.accent : C.muted,
                        flexShrink: 0,
                      }}
                    >
                      {i + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: 11, color: C.muted }}>{c.appels} appels</div>
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: C.accent }}>${c.cost}</div>
                  </div>
                ))}
              </div>
            )}
          </PanelCard>

          <PanelCard
            title="Appels récents"
            subtitle="Transferts, abandons et trafic du jour."
            action={
              <button
                onClick={() => navigate("/admin/calls")}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.muted,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Voir tout →
              </button>
            }
          >
            {recentCalls.length === 0 ? (
              <div style={{ fontSize: 13, color: C.muted }}>Aucun appel aujourd'hui</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {recentCalls.map((call, i) => (
                  <div
                    key={`${call.callId || i}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr auto auto",
                      alignItems: "center",
                      gap: 12,
                      padding: "10px 12px",
                      borderRadius: 12,
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                    }}
                  >
                    <div style={{ fontSize: 12, color: C.muted }}>{call.time}</div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{call.client}</div>
                      <div style={{ fontSize: 11, color: C.muted }}>{call.dur} · {call.num}</div>
                    </div>
                    <StatusBadge status={call.status} />
                    <button
                      onClick={() => navigate(call.tenantId ? `/admin/tenants/${call.tenantId}` : "/admin/calls")}
                      style={{
                        padding: "7px 10px",
                        borderRadius: 8,
                        background: "rgba(0,229,160,0.1)",
                        border: "1px solid rgba(0,229,160,0.28)",
                        color: C.accent,
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: "pointer",
                        fontFamily: "inherit",
                        whiteSpace: "nowrap",
                      }}
                    >
                      Ouvrir
                    </button>
                  </div>
                ))}
              </div>
            )}
          </PanelCard>
        </div>

        {/* ── Activity chart ── */}
        <PanelCard
          title="Volume d'appels"
          subtitle={`${period} derniers jours`}
          action={
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {subStats.map(([l, v, c]) => (
                <div key={l} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: C.muted }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: c }} />
                  <span>{l}</span>
                  <span style={{ color: c, fontWeight: 700 }}>{v}</span>
                </div>
              ))}
            </div>
          }
        >
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={activityData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id="accentGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C.accent} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.muted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="appels" stroke={C.accent} strokeWidth={2} fill="url(#accentGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </PanelCard>

        {/* ── Section Billing ── */}
        <section style={{ animation: "uwi-fadein 0.5s ease 0.55s both" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 800,
                  color: C.text,
                  letterSpacing: -0.5,
                  marginBottom: 2,
                }}
              >
                Billing & Abonnements
              </div>
              <div style={{ fontSize: 12, color: C.muted }}>Plans, statuts Stripe et usage Vapi</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="month"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                style={{
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 9,
                  color: C.text,
                  padding: "6px 12px",
                  fontSize: 13,
                  fontFamily: "inherit",
                }}
              />
              <div
                style={{
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 10,
                  padding: "8px 16px",
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: C.muted,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    marginBottom: 2,
                  }}
                >
                  MRR
                </div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.accent }}>
                  {overview?.summary?.mrr_eur_total ?? 0}€
                </div>
              </div>
              <div
                style={{
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 10,
                  padding: "8px 16px",
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: C.muted,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    marginBottom: 2,
                  }}
                >
                  Vapi
                </div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.warning }}>
                  ${overview?.summary?.cost_usd_month_total?.toFixed(2) ?? "0.00"}
                </div>
              </div>
              {(overview?.summary?.tenants_past_due_count ?? 0) > 0 && (
                <div
                  style={{
                    background: "rgba(255,107,107,0.1)",
                    border: "1px solid rgba(255,107,107,0.3)",
                    borderRadius: 10,
                    padding: "8px 16px",
                  }}
                >
                  <div style={{ fontSize: 12, color: C.danger, fontWeight: 700 }}>
                    ⚠️ {overview.summary.tenants_past_due_count} past due
                  </div>
                </div>
              )}
              <button
                onClick={reloadBilling}
                disabled={billingLoading}
                style={{
                  padding: "7px 14px",
                  borderRadius: 9,
                  fontSize: 12,
                  fontWeight: 700,
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.muted,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                {billingLoading ? "…" : "↺"}
              </button>
            </div>
          </div>

          {billingError && (
            <div
              style={{
                background: "rgba(255,107,107,0.1)",
                border: "1px solid rgba(255,107,107,0.3)",
                borderRadius: 12,
                padding: "12px 20px",
                marginBottom: 16,
                fontSize: 13,
                color: C.danger,
              }}
            >
              ⚠️ {billingError}
            </div>
          )}

          {billingLoading && !overview ? (
            <div style={{ color: C.muted, fontSize: 13, padding: "20px 0" }}>Chargement billing…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {(overview?.tenants ?? []).map((item) => (
                <TenantBillingCard
                  key={item.tenant_id}
                  item={item}
                  plans={plans}
                  onAction={reloadBilling}
                  navigate={navigate}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      {/* ── Modal création tenant ── */}
      {showCreate && (
        <CreateTenantModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            refresh();
            reloadBilling();
          }}
        />
      )}
    </>
  );
}
