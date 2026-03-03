import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  getDashboardPayload,
  getRecentCalls,
  getCallDetail,
  getBillingOverview,
  getBillingPlans,
  changeTenantPlan,
  cancelTenantSubscription,
  resumeTenantSubscription,
  getStripePortalLink,
} from "../../lib/adminApi";
import CreateTenantModal from "../components/CreateTenantModal";

const C = {
  card: "#ffffff",
  border: "#e2e8f0",
  accent: "#6366f1",
  blue: "#3b82f6",
  warning: "#f59e0b",
  danger: "#ef4444",
  muted: "#64748b",
  text: "#0f172a",
  textMuted: "#64748b",
};

function useDashboard(period) {
  const days = period === "7j" ? 7 : period === "90j" ? 90 : 30;
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
      setCalls(callsRes.items || []);
    } catch (e) {
      setError(e?.message || "Erreur chargement");
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
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [overview, setOverview] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, pls] = await Promise.all([getBillingOverview(month), getBillingPlans()]);
      setOverview(ov);
      setPlans(pls?.items || pls || []);
    } catch (e) {
      setError(e?.message || "Erreur chargement");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { month, setMonth, overview, plans, loading, error, reload };
}

function PlanBadge({ plan }) {
  const map = {
    free: { label: "Free", color: "#6B90A8", bg: "rgba(107,144,168,0.12)" },
    starter: { label: "Starter", color: "#5BA8FF", bg: "rgba(91,168,255,0.12)" },
    growth: { label: "Growth", color: "#FFB347", bg: "rgba(255,179,71,0.12)" },
    pro: { label: "Pro", color: "#00E5A0", bg: "rgba(0,229,160,0.12)" },
    business: { label: "Business", color: "#00E5A0", bg: "rgba(0,229,160,0.12)" },
    custom: { label: "Custom", color: "#6B90A8", bg: "rgba(107,144,168,0.12)" },
  };
  const s = map[(plan || "").toLowerCase()] || map.free;
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
        letterSpacing: 0.5,
      }}
    >
      {s.label}
    </span>
  );
}

function StripeBadge({ status }) {
  const map = {
    active: { label: "Actif", color: "#00E5A0" },
    past_due: { label: "Past due", color: "#FF6B6B" },
    unpaid: { label: "Impayé", color: "#FF6B6B" },
    canceled: { label: "Annulé", color: "#6B90A8" },
    trialing: { label: "Essai", color: "#FFB347" },
    null: { label: "Non config", color: "#6B90A8" },
  };
  const s = map[status] || map.null;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: s.color, fontWeight: 600 }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, display: "inline-block" }} />
      {s.label}
    </span>
  );
}

function QuotaBar({ used, included }) {
  const pct = included > 0 ? Math.min((used / included) * 100, 100) : 0;
  const color = pct > 90 ? "#FF6B6B" : pct > 70 ? "#FFB347" : "#00E5A0";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#6B90A8", marginBottom: 5 }}>
        <span>{Math.round(used)} min utilisées</span>
        <span>{included} min incluses</span>
      </div>
      <div style={{ height: 5, background: "#1E3D56", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.6s ease" }} />
      </div>
      <div style={{ fontSize: 10, color: "#6B90A8", marginTop: 4, textAlign: "right" }}>
        {Math.max(0, Math.round(included - used))} min restantes
      </div>
    </div>
  );
}

function TenantBillingCard({ item, plans, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);
  const planKey = item.plan_key || "free";
  const stripeStatus = item.stripe_status;
  const tenantId = item.tenant_id;
  const tenantName = item.name;

  const handlePortal = async () => {
    try {
      const { url } = await getStripePortalLink(tenantId);
      window.open(url, "_blank");
    } catch (e) {
      setActionMsg("Portail indisponible : " + (e?.message || "Erreur"));
    }
  };

  const handleCancel = async () => {
    if (!confirm(`Annuler l'abonnement de ${tenantName} ?`)) return;
    try {
      await cancelTenantSubscription(tenantId);
      setActionMsg("Abonnement annulé.");
      onAction?.();
    } catch (e) {
      setActionMsg("Erreur : " + (e?.message || "Erreur"));
    }
  };

  const handleResume = async () => {
    try {
      await resumeTenantSubscription(tenantId);
      setActionMsg("Abonnement réactivé.");
      onAction?.();
    } catch (e) {
      setActionMsg("Erreur : " + (e?.message || "Erreur"));
    }
  };

  const isCanceled = stripeStatus === "canceled";

  const periodEndStr = item.current_period_end
    ? new Date(item.current_period_end * 1000).toLocaleDateString("fr-FR")
    : "—";

  const usage = item.usage || {};
  const quota = item.quota || {};

  return (
    <div
      style={{
        background: "#132840",
        border: "1px solid #1E3D56",
        borderRadius: 16,
        overflow: "hidden",
        transition: "box-shadow 0.2s",
      }}
    >
      <div
        onClick={() => setExpanded((e) => !e)}
        style={{ padding: "18px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 12 }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <Link
            to={`/admin/tenants/${tenantId}`}
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 14, fontWeight: 700, color: "#FFFFFF", marginBottom: 5, textDecoration: "none" }}
          >
            {tenantName}
          </Link>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <PlanBadge plan={planKey} />
            <StripeBadge status={stripeStatus} />
          </div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: "#00E5A0", letterSpacing: -0.5 }}>
            ${(usage.cost_usd ?? 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.5 }}>ce mois</div>
        </div>
        <div style={{ color: "#6B90A8", fontSize: 12, transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▼</div>
      </div>

      {expanded && (
        <div style={{ padding: "0 20px 20px", borderTop: "1px solid #1E3D56" }}>
          {(quota.included != null || quota.used != null) && (
            <div style={{ marginTop: 16, marginBottom: 16 }}>
              <QuotaBar used={quota.used ?? 0} included={quota.included ?? 0} />
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              ["Customer ID", item.stripe_customer_id || "—"],
              ["Subscription", item.stripe_subscription_id || "—"],
              ["Prochain débit", periodEndStr],
              ["MRR", item.mrr_eur ? `${item.mrr_eur}€` : "—"],
            ].map(([l, v]) => (
              <div key={l} style={{ background: "#0F2236", borderRadius: 8, padding: "8px 12px" }}>
                <div style={{ fontSize: 10, color: "#6B90A8", marginBottom: 3, textTransform: "uppercase", letterSpacing: 0.5 }}>{l}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#FFFFFF", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v}</div>
              </div>
            ))}
          </div>

          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, color: "#6B90A8", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Changer de plan</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {(plans || [])
                .filter((p) => ["starter", "growth", "pro"].includes((p.plan_key || "").toLowerCase()))
                .map((p) => (
                  <button
                    key={p.plan_key}
                    type="button"
                    onClick={async () => {
                      if (!confirm(`Passer ${tenantName} au plan ${p.plan_key} ?`)) return;
                      try {
                        await changeTenantPlan(tenantId, p.plan_key);
                        setActionMsg(`Plan changé → ${p.plan_key}`);
                        onAction?.();
                      } catch (e) {
                        setActionMsg("Erreur : " + (e?.message || "Erreur"));
                      }
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      background: planKey === (p.plan_key || "").toLowerCase() ? "rgba(0,229,160,0.15)" : "#0F2236",
                      border: `1px solid ${planKey === (p.plan_key || "").toLowerCase() ? "#00E5A0" : "#1E3D56"}`,
                      color: planKey === (p.plan_key || "").toLowerCase() ? "#00E5A0" : "#6B90A8",
                    }}
                  >
                    {p.plan_key}
                  </button>
                ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
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
                color: "#5BA8FF",
              }}
            >
              ↗ Portail Stripe
            </button>
            {isCanceled ? (
              <button
                type="button"
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
                  color: "#00E5A0",
                }}
              >
                ↺ Réactiver
              </button>
            ) : (
              <button
                type="button"
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
                  color: "#FF6B6B",
                }}
              >
                ✕ Annuler
              </button>
            )}
          </div>

          {actionMsg && (
            <div style={{ marginTop: 10, fontSize: 12, color: "#00E5A0", padding: "8px 12px", background: "rgba(0,229,160,0.08)", borderRadius: 8 }}>
              {actionMsg}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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

function KpiCard({ label, value, sub, color, delay = 0 }) {
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: "20px 22px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: color || C.text }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: C.textMuted, marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

const RESULT_MAP = {
  booking_confirmed: "rdv",
  transferred_human: "transfert",
  transferred: "transfert",
  user_abandon: "abandon",
  abandon: "abandon",
  error: "abandon",
};

const STATUS_COLORS = {
  rdv: "#22c55e",
  transfert: "#3b82f6",
  abandon: "#f59e0b",
  info: "#64748b",
};

export default function UWIDashboard({ title = "Dashboard", showCreateButton = true }) {
  const [period, setPeriod] = useState("30j");
  const { data, calls, loading, error, refresh } = useDashboard(period);
  const billingOv = useBillingOverview();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedCall, setSelectedCall] = useState(null);
  const [callDetail, setCallDetail] = useState(null);
  const [callDetailLoading, setCallDetailLoading] = useState(false);
  const [callDetailError, setCallDetailError] = useState(null);

  const days = period === "7j" ? 7 : period === "90j" ? 90 : 30;

  const kpis = data?.global
    ? [
        {
          label: "Appels",
          value: data.global.calls_total ?? 0,
          sub: `${data.global.errors_total ?? 0} erreurs`,
          color: C.accent,
        },
        {
          label: "RDV confirmés",
          value: data.global.appointments_total ?? 0,
          sub: "ce mois",
          color: C.blue,
        },
        {
          label: "Coût 30j",
          value: `$${(data.global.cost_usd_total ?? 0).toFixed(2)}`,
          sub: "via Vapi",
          color: C.warning,
        },
        {
          label: "Clients actifs",
          value: data.global.tenants_active ?? 0,
          sub: `/${data.global.tenants_total ?? 0} total`,
          color: C.muted,
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
        name: item.name,
        appels: item.value,
        cost: (costItem?.value ?? 0).toFixed(2),
        tenant_id: item.tenant_id,
      };
    }) ?? [];

  const billing = data?.billing ?? null;

  const subStats = data?.global
    ? [
        ["Transferts", data.global.transfers_total ?? 0, C.blue],
        ["Minutes", data.global.minutes_total ?? 0, C.accent],
        ["Erreurs", data.global.errors_total ?? 0, C.danger],
      ]
    : [];

  const recentCalls = calls.map((c) => ({
    time: new Date(c.started_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    client: c.tenant_name ?? `Client #${c.tenant_id}` ?? "—",
    dur: c.duration_min != null ? `${c.duration_min}m` : "—",
    status: RESULT_MAP[c.result] ?? "info",
    num: c.call_id?.slice(0, 16) ?? "—",
    call_id: c.call_id,
    tenant_id: c.tenant_id,
  }));

  const billingLines = billing
    ? [
        ["Coût ce mois", `$${billing.cost_usd_this_month?.toFixed(2) ?? "0.00"}`],
        [
          "Past due",
          billing.tenants_past_due_count > 0
            ? `⚠️ ${billing.tenants_past_due_count} tenant(s)`
            : "✓ Aucun",
        ],
      ]
    : [];

  async function openCallDetail(row) {
    if (!row?.tenant_id || !row?.call_id) return;
    setSelectedCall({ tenant_id: row.tenant_id, call_id: row.call_id });
    setCallDetail(null);
    setCallDetailError(null);
    setCallDetailLoading(true);
    try {
      const d = await getCallDetail(row.tenant_id, row.call_id);
      setCallDetail(d);
    } catch (e) {
      setCallDetailError(e?.message || "Erreur");
    } finally {
      setCallDetailLoading(false);
    }
  }

  function closeCallDetail() {
    setSelectedCall(null);
    setCallDetail(null);
    setCallDetailError(null);
  }

  useEffect(() => {
    if (!selectedCall) return;
    const onEsc = (e) => {
      if (e.key === "Escape") closeCallDetail();
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [selectedCall]);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif" }}>
      <style>{`
        @keyframes uwi-shimmer { 0%,100%{opacity:.4} 50%{opacity:.8} }
        @keyframes uwi-fadein { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* Error banner */}
      {error && (
        <div
          style={{
            background: "rgba(255,107,107,0.1)",
            border: "1px solid rgba(255,107,107,0.3)",
            borderRadius: 12,
            padding: "12px 20px",
            marginBottom: 20,
            fontSize: 13,
            color: "#FF6B6B",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>⚠️ {error}</span>
          <button
            type="button"
            onClick={refresh}
            style={{
              background: "transparent",
              border: "none",
              color: "#FF6B6B",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: C.text, margin: 0 }}>{title}</h1>
          <p style={{ fontSize: 14, color: C.textMuted, marginTop: 4 }}>
            Vue d'ensemble sur les {days} derniers jours
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {showCreateButton && (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              style={{
                padding: "7px 16px",
                borderRadius: 10,
                background: C.accent,
                border: "none",
                color: "#fff",
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
          )}
          <div style={{ display: "flex", gap: 4 }}>
            {["7j", "30j", "90j"].map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  border: `1px solid ${period === p ? C.accent : C.border}`,
                  background: period === p ? `${C.accent}15` : C.card,
                  color: period === p ? C.accent : C.textMuted,
                  fontWeight: period === p ? 600 : 400,
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: `1px solid ${C.border}`,
              background: C.card,
              color: C.accent,
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: 13,
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "…" : "↺ Rafraîchir"}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
        {loading
          ? Array(4)
              .fill(0)
              .map((_, i) => <SkeletonCard key={i} />)
          : kpis.map((kpi) => (
              <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} sub={kpi.sub} color={kpi.color} />
            ))}
      </div>

      {/* Sub-stats bar */}
      {!loading && subStats.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 24 }}>
          {subStats.map(([label, value, color]) => (
            <div
              key={label}
              style={{
                background: "#f8fafc",
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 16px",
                fontSize: 13,
              }}
            >
              <span style={{ color: C.textMuted }}>{label}</span>
              <span style={{ marginLeft: 8, fontWeight: 600, color }}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
        {/* Activity chart */}
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: 20,
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h2 style={{ fontSize: 16, fontWeight: 600, color: C.text, margin: "0 0 16px 0" }}>
            Activité ({days} j) — appels/jour
          </h2>
          {loading ? (
            <div style={{ height: 120, display: "flex", alignItems: "flex-end", gap: 4 }}>
              {Array(14)
                .fill(0)
                .map((_, i) => (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      minWidth: 8,
                      height: 40 + Math.random() * 60,
                      background: C.border,
                      borderRadius: 4,
                      animation: "uwi-shimmer 1.5s ease infinite",
                    }}
                  />
                ))}
            </div>
          ) : activityData.length > 0 ? (
            <div style={{ display: "flex", gap: 4, alignItems: "flex-end", minHeight: 100 }}>
              {activityData.map((p, i) => {
                const maxVal = Math.max(1, ...activityData.map((x) => x.appels));
                return (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      minWidth: 8,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                    }}
                    title={`${p.day}: ${p.appels}`}
                  >
                    <div
                      style={{
                        width: "100%",
                        maxWidth: 14,
                        height: Math.max(6, (p.appels / maxVal) * 80),
                        background: C.accent,
                        borderRadius: "4px 4px 0 0",
                      }}
                    />
                    <span style={{ fontSize: 10, color: C.textMuted, marginTop: 4 }}>{p.day}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ color: C.textMuted, fontSize: 13 }}>Aucune donnée sur la période.</p>
          )}
        </div>

        {/* Top clients */}
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: 20,
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h2 style={{ fontSize: 16, fontWeight: 600, color: C.text, margin: "0 0 16px 0" }}>
            Top clients
          </h2>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[1, 2, 3, 4].map((i) => (
                <div key={i} style={{ height: 24, background: C.border, borderRadius: 4, animation: "uwi-shimmer 1.5s ease infinite" }} />
              ))}
            </div>
          ) : topClients.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {topClients.map((t) => (
                <li key={t.tenant_id} style={{ padding: "8px 0", borderBottom: `1px solid ${C.border}` }}>
                  <Link
                    to={`/admin/tenants/${t.tenant_id}`}
                    style={{ color: C.accent, fontWeight: 500, textDecoration: "none" }}
                  >
                    {t.name}
                  </Link>
                  <div style={{ fontSize: 12, color: C.textMuted, marginTop: 2 }}>
                    {t.appels} appels · ${t.cost}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: C.textMuted, fontSize: 13 }}>Aucune donnée.</p>
          )}
        </div>

        {/* Billing */}
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: 20,
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h2 style={{ fontSize: 16, fontWeight: 600, color: C.text, margin: "0 0 16px 0" }}>
            Billing (mois UTC)
          </h2>
          {loading ? (
            <div style={{ height: 60, background: C.border, borderRadius: 4, animation: "uwi-shimmer 1.5s ease infinite" }} />
          ) : billingLines.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {billingLines.map(([label, value]) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span style={{ color: C.textMuted }}>{label}</span>
                  <span style={{ fontWeight: 600, color: C.text }}>{value}</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: C.textMuted, fontSize: 13 }}>Aucun coût ce mois.</p>
          )}
        </div>

        {/* Recent calls */}
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: 20,
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: C.text, margin: 0 }}>Appels récents</h2>
            <Link to="/admin/calls" style={{ fontSize: 13, color: C.accent, fontWeight: 500, textDecoration: "none" }}>
              Voir tout →
            </Link>
          </div>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} style={{ height: 36, background: C.border, borderRadius: 4, animation: "uwi-shimmer 1.5s ease infinite" }} />
              ))}
            </div>
          ) : recentCalls.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {recentCalls.map((row, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => openCallDetail(row)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 12px",
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    background: "transparent",
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%",
                    fontSize: 13,
                  }}
                >
                  <span style={{ color: C.textMuted, minWidth: 40 }}>{row.time}</span>
                  <span style={{ flex: 1, fontWeight: 500, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {row.client}
                  </span>
                  <span style={{ color: C.textMuted }}>{row.dur}</span>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: `${STATUS_COLORS[row.status] || C.muted}20`,
                      color: STATUS_COLORS[row.status] || C.muted,
                    }}
                  >
                    {row.status}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p style={{ color: C.textMuted, fontSize: 13 }}>Aucun appel récent.</p>
          )}
        </div>
      </div>

      {/* Billing & Abonnements */}
      <section style={{ marginTop: 24, animation: "uwi-fadein 0.5s ease 0.55s both" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, letterSpacing: -0.5, marginBottom: 2 }}>
              Billing & Abonnements
            </div>
            <div style={{ fontSize: 12, color: "#6B90A8" }}>
              Plans, statuts Stripe et usage Vapi
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {/* Sélecteur de mois */}
            <input
              type="month"
              value={billingOv.month}
              onChange={(e) => billingOv.setMonth(e.target.value)}
              style={{
                background: "#132840",
                border: "1px solid #1E3D56",
                borderRadius: 9,
                color: "#FFFFFF",
                padding: "6px 12px",
                fontSize: 13,
                fontFamily: "inherit",
                cursor: "pointer",
              }}
            />

            {/* MRR global */}
            <div
              style={{
                background: "#132840",
                border: "1px solid #1E3D56",
                borderRadius: 10,
                padding: "8px 16px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }}>MRR</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#00E5A0" }}>
                {(billingOv.overview?.summary?.mrr_eur_total ?? 0).toFixed(0)}€
              </div>
            </div>

            {/* Coût Vapi mois */}
            <div
              style={{
                background: "#132840",
                border: "1px solid #1E3D56",
                borderRadius: 10,
                padding: "8px 16px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }}>Vapi</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#FFB347" }}>
                ${(billingOv.overview?.summary?.cost_usd_month_total ?? 0).toFixed(2)}
              </div>
            </div>

            {/* Past due alert */}
            {(billingOv.overview?.summary?.tenants_past_due_count ?? 0) > 0 && (
              <div
                style={{
                  background: "rgba(255,107,107,0.1)",
                  border: "1px solid rgba(255,107,107,0.3)",
                  borderRadius: 10,
                  padding: "8px 16px",
                }}
              >
                <div style={{ fontSize: 12, color: "#FF6B6B", fontWeight: 700 }}>
                  ⚠️ {billingOv.overview.summary.tenants_past_due_count} past due
                </div>
              </div>
            )}

            {/* Refresh */}
            <button
              type="button"
              onClick={billingOv.reload}
              disabled={billingOv.loading}
              style={{
                padding: "7px 14px",
                borderRadius: 9,
                fontSize: 12,
                fontWeight: 700,
                background: "transparent",
                border: "1px solid #1E3D56",
                color: "#6B90A8",
                cursor: billingOv.loading ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                opacity: billingOv.loading ? 0.6 : 1,
              }}
            >
              {billingOv.loading ? "…" : "↺"}
            </button>
          </div>
        </div>

        {billingOv.error && (
          <div
            style={{
              background: "rgba(255,107,107,0.1)",
              border: "1px solid rgba(255,107,107,0.3)",
              borderRadius: 12,
              padding: "12px 20px",
              marginBottom: 14,
              fontSize: 13,
              color: "#FF6B6B",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>⚠️ {billingOv.error}</span>
            <button
              type="button"
              onClick={billingOv.reload}
              style={{ background: "transparent", border: "none", color: "#FF6B6B", cursor: "pointer", fontWeight: 800 }}
            >
              Réessayer
            </button>
          </div>
        )}

        {billingOv.loading ? (
          <div style={{ color: "#6B90A8", fontSize: 13, padding: "20px 0" }}>Chargement billing…</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {(billingOv.overview?.tenants ?? []).map((item) => (
              <TenantBillingCard key={item.tenant_id} item={item} plans={billingOv.plans} onAction={billingOv.reload} />
            ))}
          </div>
        )}
      </section>

      {/* Call detail modal */}
      {selectedCall && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 50,
            padding: 24,
          }}
          onClick={closeCallDetail}
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
        >
          <div
            style={{
              background: C.card,
              borderRadius: 16,
              padding: 24,
              maxWidth: 480,
              width: "100%",
              maxHeight: "80vh",
              overflow: "auto",
              boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ fontSize: 18, fontWeight: 600, color: C.text, margin: 0 }}>Détail appel</h3>
              <button
                type="button"
                onClick={closeCallDetail}
                style={{
                  background: "transparent",
                  border: "none",
                  fontSize: 20,
                  color: C.textMuted,
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                ×
              </button>
            </div>
            {callDetailLoading && <p style={{ color: C.textMuted }}>Chargement…</p>}
            {callDetailError && (
              <p style={{ color: C.danger }}>⚠️ {callDetailError}</p>
            )}
            {callDetail && !callDetailLoading && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 13 }}>
                  <div>
                    <span style={{ color: C.textMuted }}>Durée</span>
                    <div style={{ fontWeight: 600 }}>{callDetail.duration_min ?? "—"} min</div>
                  </div>
                  <div>
                    <span style={{ color: C.textMuted }}>Résultat</span>
                    <div style={{ fontWeight: 600 }}>{callDetail.result ?? "—"}</div>
                  </div>
                  <div>
                    <span style={{ color: C.textMuted }}>Début</span>
                    <div style={{ fontWeight: 500, fontSize: 12 }}>{callDetail.started_at ?? "—"}</div>
                  </div>
                  <div>
                    <span style={{ color: C.textMuted }}>Fin</span>
                    <div style={{ fontWeight: 500, fontSize: 12 }}>{callDetail.last_event_at ?? "—"}</div>
                  </div>
                </div>
                {callDetail.events?.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: 14, fontWeight: 600, color: C.text, marginBottom: 8 }}>Timeline</h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                      {callDetail.events.map((ev, i) => (
                        <div
                          key={i}
                          style={{
                            padding: "8px 12px",
                            background: "#f8fafc",
                            borderRadius: 8,
                            fontSize: 12,
                            borderLeft: `3px solid ${C.accent}`,
                          }}
                        >
                          <span style={{ color: C.textMuted }}>{ev.created_at}</span>
                          <span style={{ marginLeft: 8, fontWeight: 600, color: C.text }}>{ev.event}</span>
                          {ev.meta && (
                            <div style={{ marginTop: 4, color: C.textMuted, fontSize: 11 }}>
                              {JSON.stringify(ev.meta)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <CreateTenantModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            refresh();
            billingOv.reload?.();
          }}
        />
      )}
    </div>
  );
}
