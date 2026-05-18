import { useEffect, useMemo, useState } from "react";
import {
  changeTenantPlan,
  cancelTenantSubscription,
  resumeTenantSubscription,
  getStripePortalLink,
} from "../../lib/adminApi";
import { T } from "../theme.js";

function PlanBadge({ plan, theme }) {
  const map = {
    free: { label: "Free", color: theme.muted, bg: T.neutralLight },
    starter: { label: "Starter", color: theme.blue, bg: "#EFF6FF" },
    growth: { label: "Growth", color: theme.warning, bg: T.yellowLight },
    pro: { label: "Pro", color: theme.accent, bg: T.tealLight },
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

function StripeBadge({ status, theme }) {
  const map = {
    active: { label: "Actif", color: theme.accent },
    past_due: { label: "Past due", color: theme.danger },
    canceled: { label: "Annule", color: theme.muted },
    trialing: { label: "Essai", color: theme.warning },
  };
  const s = map[status] || { label: "Non config", color: theme.muted };
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

function QuotaBar({ used, included, theme }) {
  const pct = included > 0 ? Math.min((used / included) * 100, 100) : 0;
  const color = pct > 90 ? theme.danger : pct > 70 ? theme.warning : theme.accent;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: theme.muted, marginBottom: 5 }}>
        <span>{used} min utilisees</span>
        <span>{included} min incluses</span>
      </div>
      <div style={{ height: 5, background: theme.border, borderRadius: 3, overflow: "hidden" }}>
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
      <div style={{ fontSize: 10, color: theme.muted, marginTop: 4, textAlign: "right" }}>
        {Math.max(0, included - used)} min restantes
      </div>
    </div>
  );
}

function TenantBillingCard({ item, plans, onAction, navigate, theme, isNarrow = false }) {
  const [expanded, setExpanded] = useState(false);
  const [actionMsg, setActionMsg] = useState(null);

  const handlePortal = async () => {
    try {
      const { url } = await getStripePortalLink(item.tenant_id);
      window.open(url, "_blank");
    } catch (e) {
      setActionMsg(`Portail indisponible : ${e.message}`);
    }
  };

  const handleCancel = async () => {
    if (!confirm(`Annuler l'abonnement de ${item.name} ?`)) return;
    try {
      await cancelTenantSubscription(item.tenant_id);
      setActionMsg("Abonnement annule.");
      onAction();
    } catch (e) {
      setActionMsg(`Erreur : ${e.message}`);
    }
  };

  const handleResume = async () => {
    try {
      await resumeTenantSubscription(item.tenant_id);
      setActionMsg("Abonnement reactive.");
      onAction();
    } catch (e) {
      setActionMsg(`Erreur : ${e.message}`);
    }
  };

  const isCanceled = item.stripe_status === "canceled";

  return (
    <div style={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: isNarrow ? 12 : 16, overflow: "hidden" }}>
      <div
        onClick={() => setExpanded((current) => !current)}
        style={{
          padding: isNarrow ? "12px 12px" : "18px 20px",
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
              color: theme.text,
              marginBottom: 5,
              cursor: "pointer",
              textDecoration: "underline",
              textDecorationColor: "transparent",
            }}
            onMouseEnter={(e) => (e.target.style.color = theme.accent)}
            onMouseLeave={(e) => (e.target.style.color = theme.text)}
          >
            {item.name}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <PlanBadge plan={item.plan_key} theme={theme} />
            <StripeBadge status={item.stripe_status} theme={theme} />
          </div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: theme.accent, letterSpacing: -0.5 }}>
            ${(item.usage?.cost_usd ?? 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 10, color: theme.muted, textTransform: "uppercase", letterSpacing: 0.5 }}>
            ce mois
          </div>
        </div>
        <div
          style={{
            color: theme.muted,
            fontSize: 12,
            transform: expanded ? "rotate(180deg)" : "none",
            transition: "transform 0.2s",
          }}
        >
          ▼
        </div>
      </div>

      {expanded ? (
        <div style={{ padding: isNarrow ? "0 12px 12px" : "0 20px 20px", borderTop: `1px solid ${theme.border}` }}>
          {item.quota ? (
            <div style={{ marginTop: 16, marginBottom: 16 }}>
              <QuotaBar used={item.quota.used ?? 0} included={item.quota.included ?? 0} theme={theme} />
            </div>
          ) : null}
          <div style={{ display: "grid", gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              ["Customer ID", item.stripe_customer_id || "—"],
              ["Subscription", item.stripe_subscription_id || "—"],
              [
                "Prochain debit",
                item.current_period_end ? new Date(item.current_period_end * 1000).toLocaleDateString("fr-FR") : "—",
              ],
              ["MRR", item.mrr_eur ? `${item.mrr_eur}€` : "—"],
            ].map(([label, value]) => (
              <div key={label} style={{ background: theme.surface, borderRadius: 8, padding: "8px 12px" }}>
                <div
                  style={{
                    fontSize: 10,
                    color: theme.muted,
                    marginBottom: 3,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {label}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: theme.text,
                    fontFamily: "monospace",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                fontSize: 11,
                color: theme.muted,
                marginBottom: 8,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}
            >
              Changer de plan
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {(plans || []).map((plan) => (
                <button
                  key={plan.id}
                  onClick={async () => {
                    if (!confirm(`Passer ${item.name} au plan ${plan.name} ?`)) return;
                    try {
                      await changeTenantPlan(item.tenant_id, plan.id || plan.plan_key);
                      setActionMsg(`Plan → ${plan.name}`);
                      onAction();
                    } catch (e) {
                      setActionMsg(`Erreur : ${e.message}`);
                    }
                  }}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    background: item.plan_key === (plan.id || plan.plan_key) ? T.tealLight : theme.surface,
                    border: `1px solid ${item.plan_key === (plan.id || plan.plan_key) ? theme.accent : theme.border}`,
                    color: item.plan_key === (plan.id || plan.plan_key) ? theme.accent : theme.muted,
                  }}
                >
                  {plan.name}
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
                background: "#EFF6FF",
                border: `1px solid ${theme.blue}40`,
                color: theme.blue,
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
                  background: T.tealLight,
                  border: `1px solid ${T.teal}40`,
                  color: theme.accent,
                }}
              >
                ↺ Reactiver
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
                  background: T.redLight,
                  border: `1px solid ${T.red}40`,
                  color: theme.danger,
                }}
              >
                ✕ Annuler
              </button>
            )}
          </div>
          {actionMsg ? (
            <div
              style={{
                marginTop: 10,
                fontSize: 12,
                color: theme.accent,
                padding: "8px 12px",
                background: T.tealLight,
                borderRadius: 8,
              }}
            >
              {actionMsg}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function AdminBillingSection({
  theme,
  overview,
  plans,
  loading,
  error,
  month,
  setMonth,
  reloadBilling,
  navigate,
}) {
  const C = theme;
  const [isNarrow, setIsNarrow] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth <= 900 : false,
  );
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortMode, setSortMode] = useState("cost_desc");

  useEffect(() => {
    function onResize() {
      setIsNarrow(window.innerWidth <= 900);
    }
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const tenants = overview?.tenants ?? [];
  const filteredTenants = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = [...tenants];
    if (q) {
      rows = rows.filter((item) => {
        const haystack = `${item.name || ""} ${item.plan_key || ""} ${item.stripe_status || ""} ${item.tenant_id || ""}`.toLowerCase();
        return haystack.includes(q);
      });
    }
    if (statusFilter !== "all") {
      rows = rows.filter((item) => (item.stripe_status || "none") === statusFilter);
    }
    rows.sort((a, b) => {
      if (sortMode === "name_asc") return String(a.name || "").localeCompare(String(b.name || ""), "fr");
      if (sortMode === "name_desc") return String(b.name || "").localeCompare(String(a.name || ""), "fr");
      if (sortMode === "mrr_desc") return Number(b.mrr_eur || 0) - Number(a.mrr_eur || 0);
      if (sortMode === "mrr_asc") return Number(a.mrr_eur || 0) - Number(b.mrr_eur || 0);
      if (sortMode === "cost_asc") return Number(a.usage?.cost_usd || 0) - Number(b.usage?.cost_usd || 0);
      return Number(b.usage?.cost_usd || 0) - Number(a.usage?.cost_usd || 0);
    });
    return rows;
  }, [tenants, query, statusFilter, sortMode]);

  return (
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
            <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }}>MRR</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: C.accent }}>{overview?.summary?.mrr_eur_total ?? 0}€</div>
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
            <div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }}>Vapi</div>
            <div style={{ fontSize: 16, fontWeight: 800, color: C.warning }}>
              ${overview?.summary?.cost_usd_month_total?.toFixed(2) ?? "0.00"}
            </div>
          </div>
          {(overview?.summary?.tenants_past_due_count ?? 0) > 0 ? (
            <div
              style={{
                background: T.redLight,
                border: `1px solid ${T.red}40`,
                borderRadius: 10,
                padding: "8px 16px",
              }}
            >
              <div style={{ fontSize: 12, color: C.danger, fontWeight: 700 }}>
                ⚠️ {overview.summary.tenants_past_due_count} past due
              </div>
            </div>
          ) : null}
          <button
            onClick={reloadBilling}
            disabled={loading}
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
            {loading ? "…" : "↺"}
          </button>
        </div>
      </div>

      <div
        style={{
          marginBottom: 12,
          display: "grid",
          gap: 8,
          gridTemplateColumns: isNarrow ? "1fr" : "minmax(200px,1fr) auto auto auto",
          alignItems: "center",
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher un client (nom, plan, statut, ID)..."
          style={{
            width: "100%",
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            background: C.card,
            color: C.text,
            padding: "8px 10px",
            fontSize: 12,
            fontFamily: "inherit",
          }}
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ border: `1px solid ${C.border}`, borderRadius: 9, background: C.card, color: C.text, padding: "8px 10px", fontSize: 12, fontFamily: "inherit" }}
        >
          <option value="all">Tous statuts</option>
          <option value="active">Actif</option>
          <option value="trialing">Essai</option>
          <option value="past_due">Past due</option>
          <option value="canceled">Annulé</option>
          <option value="none">Non config</option>
        </select>
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value)}
          style={{ border: `1px solid ${C.border}`, borderRadius: 9, background: C.card, color: C.text, padding: "8px 10px", fontSize: 12, fontFamily: "inherit" }}
        >
          <option value="cost_desc">Coût Vapi ↓</option>
          <option value="cost_asc">Coût Vapi ↑</option>
          <option value="mrr_desc">MRR ↓</option>
          <option value="mrr_asc">MRR ↑</option>
          <option value="name_asc">Nom A-Z</option>
          <option value="name_desc">Nom Z-A</option>
        </select>
        <button
          type="button"
          onClick={() => {
            setQuery("");
            setStatusFilter("all");
            setSortMode("cost_desc");
          }}
          style={{ borderRadius: 9, border: `1px solid ${C.border}`, background: C.card, color: C.muted, padding: "8px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
        >
          Reset
        </button>
      </div>

      {error ? (
        <div
          style={{
            background: T.redLight,
            border: `1px solid ${T.red}40`,
            borderRadius: 12,
            padding: "12px 20px",
            marginBottom: 16,
            fontSize: 13,
            color: C.danger,
          }}
        >
          ⚠️ {error}
        </div>
      ) : null}

      {loading && !overview ? (
        <div style={{ color: C.muted, fontSize: 13, padding: "20px 0" }}>Chargement billing…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 700 }}>
            {filteredTenants.length} résultat(s) sur {tenants.length}
          </div>
          {filteredTenants.map((item) => (
            <TenantBillingCard
              key={item.tenant_id}
              item={item}
              plans={plans}
              onAction={reloadBilling}
              navigate={navigate}
              theme={theme}
              isNarrow={isNarrow}
            />
          ))}
          {!filteredTenants.length ? (
            <div style={{ borderRadius: 12, border: `1px dashed ${C.border}`, background: C.card, color: C.muted, fontSize: 13, fontWeight: 700, padding: "16px 14px", textAlign: "center" }}>
              Aucun client ne correspond aux filtres.
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
