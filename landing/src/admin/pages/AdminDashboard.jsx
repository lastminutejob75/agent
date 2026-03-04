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

const NAV_ITEMS = [
  { icon: "⬛", label: "Dashboard" },
  { icon: "👥", label: "Clients" },
  { icon: "🎯", label: "Leads" },
  { icon: "📞", label: "Appels" },
  { icon: "📡", label: "Monitoring" },
  { icon: "⚙️", label: "Operations" },
  { icon: "⭐", label: "Quality" },
  { icon: "📋", label: "Audit log" },
];

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar({ active, onNavigate }) {
  return (
    <aside
      style={{
        width: 200,
        flexShrink: 0,
        background: C.surface,
        borderRight: `1px solid ${C.border}`,
        display: "flex",
        flexDirection: "column",
        padding: "20px 0",
        position: "sticky",
        top: 0,
        height: "100vh",
      }}
    >
      <div style={{ padding: "0 20px 24px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
              fontWeight: 800,
              color: C.bg,
            }}
          >
            UWi
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>UWi Admin</div>
            <div style={{ fontSize: 10, color: C.muted }}>Pilotage & facturation</div>
          </div>
        </div>
      </div>
      <nav style={{ padding: "16px 10px", flex: 1 }}>
        <div
          style={{
            fontSize: 9,
            color: C.muted,
            fontWeight: 700,
            letterSpacing: 1.5,
            textTransform: "uppercase",
            padding: "0 10px",
            marginBottom: 10,
          }}
        >
          Navigation
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.label;
          return (
            <div
              key={item.label}
              onClick={() => onNavigate(item.label)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 10px",
                borderRadius: 10,
                marginBottom: 2,
                cursor: "pointer",
                background: isActive ? "rgba(0,229,160,0.1)" : "transparent",
                border: `1px solid ${isActive ? "rgba(0,229,160,0.2)" : "transparent"}`,
                transition: "all 0.15s",
              }}
            >
              <span style={{ fontSize: 14, opacity: isActive ? 1 : 0.6 }}>{item.icon}</span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? C.accent : C.muted,
                }}
              >
                {item.label}
              </span>
              {isActive && (
                <div
                  style={{
                    marginLeft: "auto",
                    width: 4,
                    height: 4,
                    borderRadius: "50%",
                    background: C.accent,
                  }}
                />
              )}
            </div>
          );
        })}
      </nav>
      <div style={{ padding: "16px 20px", borderTop: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: C.muted }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: C.accent,
              animation: "uwi-pulse 2s ease infinite",
            }}
          />
          Système opérationnel
        </div>
      </div>
    </aside>
  );
}

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
  const [navActive, setNavActive] = useState("Dashboard");
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

  const handleNav = (label) => {
    setNavActive(label);
    const routes = {
      Clients: "/admin/tenants",
      Appels: "/admin/calls",
      Leads: "/admin/leads",
      Monitoring: "/admin/monitoring",
      Operations: "/admin/operations",
      Quality: "/admin/quality",
      "Audit log": "/admin/audit",
    };
    if (routes[label]) navigate(routes[label]);
  };

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
  }));

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: C.bg, fontFamily: "'DM Sans', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
        * { box-sizing:border-box; margin:0; padding:0; }
        @keyframes uwi-fadein  { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        @keyframes uwi-pulse   { 0%,100%{opacity:1} 50%{opacity:.4} }
        @keyframes uwi-shimmer { 0%,100%{opacity:.4} 50%{opacity:.8} }
        ::-webkit-scrollbar{width:4px} ::-webkit-scrollbar-thumb{background:${C.border};border-radius:2px}
      `}</style>

      <Sidebar active={navActive} onNavigate={handleNav} />

      <main style={{ flex: 1, padding: "32px", overflowY: "auto", minWidth: 0 }}>
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

        {/* ── KPI Grid ── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 24 }}>
          {loading
            ? Array(4)
                .fill(0)
                .map((_, i) => <SkeletonCard key={i} />)
            : kpis.map((kpi) => (
                <KpiCard key={kpi.label} {...kpi} />
              ))}
        </div>

        {/* ── Sub-stats ── */}
        <div style={{ display: "flex", gap: 10, marginBottom: 24, animation: "uwi-fadein 0.5s ease 0.25s both" }}>
          {subStats.map(([l, v, c]) => (
            <div
              key={l}
              style={{
                background: C.card,
                border: `1px solid ${C.border}`,
                borderRadius: 12,
                padding: "10px 18px",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: c }} />
              <span style={{ fontSize: 12, color: C.muted }}>{l}</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: c }}>{v}</span>
            </div>
          ))}
        </div>

        {/* ── Charts row ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
          {/* Activity chart */}
          <div
            style={{
              gridColumn: "1/3",
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 16,
              padding: 22,
              animation: "uwi-fadein 0.5s ease 0.3s both",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 2 }}>
                  Activité — appels/jour
                </div>
                <div style={{ fontSize: 12, color: C.muted }}>{period} derniers jours</div>
              </div>
            </div>
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
          </div>

          {/* Billing snapshot */}
          <div
            style={{
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 16,
              padding: 22,
              animation: "uwi-fadein 0.5s ease 0.35s both",
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 4 }}>Billing</div>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 20 }}>Mois en cours (UTC)</div>
            <div style={{ fontSize: 36, fontWeight: 800, color: C.accent, letterSpacing: -1, marginBottom: 4 }}>
              ${(data?.billing?.cost_usd_this_month ?? 0).toFixed(2)}
            </div>
            <div
              style={{
                fontSize: 11,
                color: (data?.billing?.tenants_past_due_count ?? 0) > 0 ? C.danger : C.muted,
                marginBottom: 20,
              }}
            >
              {(data?.billing?.tenants_past_due_count ?? 0) > 0
                ? `⚠️ ${data.billing.tenants_past_due_count} past due`
                : "✓ Aucun past due"}
            </div>
          </div>
        </div>

        {/* ── Bottom row ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 14 }}>
          {/* Top clients */}
          <div
            style={{
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 16,
              padding: 22,
              animation: "uwi-fadein 0.5s ease 0.4s both",
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 4 }}>Top clients</div>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 16 }}>Par volume d'appels</div>
            {topClients.map((c, i) => (
              <div
                key={c.id}
                onClick={() => navigate(`/admin/tenants/${c.id}`)}
                style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, cursor: "pointer" }}
              >
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 6,
                    background: i === 0 ? "rgba(0,229,160,0.15)" : C.surface,
                    border: `1px solid ${i === 0 ? C.accent : C.border}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 10,
                    fontWeight: 700,
                    color: i === 0 ? C.accent : C.muted,
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: C.text,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {c.name}
                  </div>
                  <div style={{ fontSize: 10, color: C.muted }}>{c.appels} appels</div>
                </div>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.accent }}>${c.cost}</div>
              </div>
            ))}
          </div>

          {/* Appels récents */}
          <div
            style={{
              gridColumn: "2/4",
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 16,
              padding: 22,
              animation: "uwi-fadein 0.5s ease 0.45s both",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 2 }}>Appels récents</div>
                <div style={{ fontSize: 11, color: C.muted }}>Aujourd'hui</div>
              </div>
              <button
                onClick={() => navigate("/admin/calls")}
                style={{
                  fontSize: 12,
                  color: C.accent,
                  background: "transparent",
                  border: `1px solid rgba(0,229,160,0.3)`,
                  borderRadius: 8,
                  padding: "5px 12px",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontWeight: 600,
                }}
              >
                Voir tout →
              </button>
            </div>
            {recentCalls.length === 0 ? (
              <div style={{ fontSize: 13, color: C.muted }}>Aucun appel aujourd'hui</div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr auto auto auto",
                  gap: "8px 14px",
                  alignItems: "center",
                }}
              >
                {["Heure", "Client", "Durée", "Statut", "ID"].map((h) => (
                  <div
                    key={h}
                    style={{
                      fontSize: 10,
                      color: C.muted,
                      fontWeight: 600,
                      letterSpacing: 0.8,
                      textTransform: "uppercase",
                      paddingBottom: 8,
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    {h}
                  </div>
                ))}
                {recentCalls.map((call, i) => (
                  <React.Fragment key={i}>
                    <div style={{ fontSize: 12, color: C.muted }}>{call.time}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{call.client}</div>
                    <div style={{ fontSize: 12, color: C.muted }}>{call.dur}</div>
                    <div>
                      <StatusBadge status={call.status} />
                    </div>
                    <div style={{ fontSize: 11, color: C.muted, fontFamily: "monospace" }}>{call.num}</div>
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Quick actions ── */}
        <div style={{ display: "flex", gap: 10, marginBottom: 24, animation: "uwi-fadein 0.5s ease 0.5s both" }}>
          <button
            onClick={() => navigate("/admin/tenants")}
            style={{
              flex: 1,
              padding: 13,
              borderRadius: 12,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              border: "none",
              color: C.bg,
              fontSize: 13,
              fontWeight: 800,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Voir tous les clients →
          </button>
          <button
            onClick={() => navigate("/admin/calls")}
            style={{
              flex: 1,
              padding: 13,
              borderRadius: 12,
              background: C.surface,
              border: `1px solid ${C.border}`,
              color: C.text,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Voir tous les appels →
          </button>
        </div>

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
      </main>

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
    </div>
  );
}
