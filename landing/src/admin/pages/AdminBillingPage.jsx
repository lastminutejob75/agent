import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { enrichTenant, mapFilterToApi, mapSortToApi } from "./adminBilling.utils.js";

const BRAND = {
  teal: "#009CA4",
  tealDark: "#007C84",
  navy: "#071A33",
  ink: "#0A1628",
  yellow: "#F5C842",
  bg: "#F4F8FA",
  border: "#DCE8EC",
  muted: "#667085",
  red: "#D92D20",
  orange: "#F79009",
  blue: "#2563EB",
  green: "#039855",
  purple: "#7C3AED",
  softTeal: "#E7F7F7",
};


function tone(kind, filled = false) {
  const map = {
    teal: [BRAND.teal, BRAND.softTeal],
    navy: [BRAND.navy, "#EAF0F6"],
    blue: [BRAND.blue, "#EAF1FF"],
    green: [BRAND.green, "#EAF8F0"],
    orange: [BRAND.orange, "#FFF4E5"],
    red: [BRAND.red, "#FEECEC"],
    purple: [BRAND.purple, "#F3E8FF"],
    yellow: ["#B7791F", "#FFF8D8"],
    gray: [BRAND.muted, "#F2F4F7"],
  };
  const [solid, soft] = map[kind] || map.gray;
  return filled
    ? { background: solid, color: "#fff", borderColor: solid }
    : { background: soft, color: solid, borderColor: `${solid}33` };
}

function eur(value) {
  return `${Number(value || 0).toLocaleString("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 2 })} €`;
}

function statusTone(status) {
  if (status === "active") return "green";
  if (status === "trialing") return "blue";
  if (status === "incomplete") return "orange";
  if (status === "past_due" || status === "unpaid" || status === "canceled") return "red";
  return "gray";
}

function isSessionExpiredError(err) {
  const msg = String(err || "").toLowerCase();
  return msg.includes("credential")
    || msg.includes("unauthorized")
    || msg.includes("forbidden")
    || msg.includes("401")
    || msg.includes("403")
    || msg.includes("session");
}

function KpiCard({ label, value, detail, variant = "gray" }) {
  return (
    <div style={{ borderRadius: 22, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 14 }}>
      <div style={{ marginBottom: 6, display: "inline-flex", alignItems: "center", borderRadius: 12, border: "1px solid", ...tone(variant), padding: "4px 8px", fontSize: 11, fontWeight: 800 }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 900, lineHeight: 1, letterSpacing: "-0.04em", color: BRAND.navy }}>{value}</div>
      <div style={{ marginTop: 4, fontSize: 12, fontWeight: 700, color: BRAND.muted }}>{detail}</div>
    </div>
  );
}

function Pill({ children, variant = "gray" }) {
  return (
    <span style={{ ...tone(variant), display: "inline-flex", alignItems: "center", borderRadius: 999, border: "1px solid", padding: "3px 9px", fontSize: 11, fontWeight: 800 }}>
      {children}
    </span>
  );
}

function UsageBar({ percent }) {
  const color = percent >= 100 ? BRAND.red : percent >= 85 ? BRAND.orange : BRAND.teal;
  return (
    <div>
      <div style={{ marginBottom: 4, display: "flex", justifyContent: "space-between", fontSize: 10, fontWeight: 800, color: BRAND.muted }}>
        <span>Usage</span>
        <span>{percent}%</span>
      </div>
      <div style={{ height: 8, borderRadius: 999, background: "#EAF0F6", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(100, percent)}%`, height: "100%", borderRadius: 999, background: color }} />
      </div>
    </div>
  );
}

export default function AdminBillingPage() {
  const navigate = useNavigate();
  const { tenantId: routeTenantId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [summary, setSummary] = useState(null);
  const [actionItems, setActionItems] = useState([]);
  const [tenantRows, setTenantRows] = useState([]);
  const [tenantOverview, setTenantOverview] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [month, setMonth] = useState(() => searchParams.get("month") || new Date().toISOString().slice(0, 7));
  const [filter, setFilter] = useState(searchParams.get("filter") || "Tous");
  const [sort, setSort] = useState(searchParams.get("sort") || "margin_low");
  const [query, setQuery] = useState(searchParams.get("search") || "");
  const [selectedId, setSelectedId] = useState(routeTenantId || searchParams.get("tenant") || "");
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [tab, setTab] = useState("overview");
  const [tenantBilling, setTenantBilling] = useState(null);
  const [tenantQuota, setTenantQuota] = useState(null);
  const [tenantInvoices, setTenantInvoices] = useState([]);
  const [isNarrow, setIsNarrow] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < 1100;
  });

  const isCabinetView = Boolean(routeTenantId);

  useEffect(() => {
    function onResize() {
      setIsNarrow(window.innerWidth < 1100);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const loadMeta = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [sumRes, actionsRes, plansRes] = await Promise.all([
        adminApi.getBillingSummary(month),
        adminApi.getBillingActionItems(month),
        adminApi.getBillingPlans(),
      ]);
      setSummary(sumRes || null);
      setActionItems(actionsRes?.items || []);
      setPlans(plansRes?.items || []);
    } catch (e) {
      setError(e?.message || "Impossible de charger le billing.");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const loadTenants = useCallback(async () => {
    try {
      const res = await adminApi.listBillingTenants({
        period: month,
        filter: mapFilterToApi(filter),
        sort: mapSortToApi(sort),
        search: query.trim(),
        page: 1,
        limit: 300,
      });
      setTenantRows(res?.items || []);
    } catch (e) {
      setError(e?.message || "Impossible de charger les tenants billing.");
      setTenantRows([]);
    }
  }, [month, filter, sort, query]);

  useEffect(() => {
    if (isCabinetView) return;
    loadTenants();
  }, [loadTenants, isCabinetView]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    next.set("month", month);
    if (filter === "Tous") next.delete("filter"); else next.set("filter", filter);
    if (sort === "margin_low") next.delete("sort"); else next.set("sort", sort);
    if (query.trim()) next.set("search", query.trim()); else next.delete("search");
    if (!isCabinetView && selectedId) next.set("tenant", selectedId); else next.delete("tenant");
    setSearchParams(next, { replace: true });
  }, [month, filter, sort, query, selectedId, setSearchParams, isCabinetView]); // eslint-disable-line react-hooks/exhaustive-deps

  const tenants = useMemo(() => (tenantRows || []).map(enrichTenant), [tenantRows]);

  useEffect(() => {
    if (!selectedId && tenants.length) setSelectedId(String(tenants[0].tenantId));
  }, [selectedId, tenants]);

  useEffect(() => {
    if (!isCabinetView) return;
    setSelectedId(String(routeTenantId));
  }, [isCabinetView, routeTenantId]);

  useEffect(() => {
    async function loadCabinet() {
      if (!isCabinetView || !routeTenantId) return;
      try {
        const [overviewRes, stripeRes, quotaRes, invoicesRes] = await Promise.all([
          adminApi.getBillingTenantOverview(routeTenantId, month).catch(() => null),
          adminApi.getBillingTenantStripe(routeTenantId).catch(() => null),
          adminApi.getBillingTenantUsage(routeTenantId, month).catch(() => null),
          adminApi.getBillingTenantInvoices(routeTenantId, 20).catch(() => ({ items: [] })),
        ]);
        setTenantOverview(overviewRes?.tenant ? enrichTenant(overviewRes.tenant) : null);
        setTenantBilling(stripeRes || null);
        setTenantQuota(quotaRes || null);
        setTenantInvoices(invoicesRes?.items || []);
      } catch (e) {
        setError(e?.message || "Impossible de charger le cabinet billing.");
      }
    }
    loadCabinet();
  }, [isCabinetView, routeTenantId, month]);

  const selected = useMemo(() => {
    if (isCabinetView) return tenantOverview;
    return tenants.find((t) => String(t.tenantId) === String(selectedId)) || tenants[0] || null;
  }, [tenants, selectedId, isCabinetView, tenantOverview]);

  useEffect(() => {
    if (isCabinetView) return;
    async function loadTenantPanels() {
      if (!selected?.tenantId) return;
      try {
        const [billingRes, quotaRes, invoicesRes] = await Promise.all([
          adminApi.getBillingTenantStripe(selected.tenantId).catch(() => null),
          adminApi.getBillingTenantUsage(selected.tenantId, month).catch(() => null),
          adminApi.getBillingTenantInvoices(selected.tenantId, 20).catch(() => ({ items: [] })),
        ]);
        setTenantBilling(billingRes || null);
        setTenantQuota(quotaRes || null);
        setTenantInvoices(invoicesRes?.items || []);
      } catch {
        setTenantBilling(null);
        setTenantQuota(null);
        setTenantInvoices([]);
      }
    }
    loadTenantPanels();
  }, [selected?.tenantId, month, isCabinetView]);

  const totals = useMemo(() => {
    const mrr = Number(summary?.mrr || 0);
    const revenue = Number(summary?.estimated_revenue || 0);
    const vapi = Number(summary?.vapi_cost_estimate || 0);
    const minutes = Number(summary?.voice_minutes_used || 0);
    const overage = Number(summary?.estimated_overage_amount || 0);
    const alerts = Number(summary?.billing_alerts_count || 0);
    const margin = Number(summary?.estimated_margin ?? revenue - vapi);
    const marginRate = Math.round(Number(summary?.estimated_margin_rate || 0) * 100);
    return { mrr, revenue, vapi, minutes, overage, alerts, margin, marginRate };
  }, [summary, tenants]);

  const rows = tenants;

  async function runAction(action) {
    if (!selected?.tenantId) return;
    const tenantId = selected.tenantId;
    try {
      setBusy(action);
      setToast("");
      if (action === "checkout") {
        await adminApi.createStripeCheckout(tenantId, { plan_key: selected.planKey === "free" ? "starter" : selected.planKey });
        setToast("Checkout Stripe créé.");
      } else if (action === "portal") {
        const res = await adminApi.getStripePortalLink(tenantId);
        if (res?.url) window.open(res.url, "_blank", "noopener,noreferrer");
        setToast("Portail Stripe ouvert.");
      } else if (action === "plan_growth") {
        await adminApi.patchBillingTenantPlan(tenantId, "growth");
        setToast("Plan changé vers Growth.");
      } else if (action === "cancel") {
        await adminApi.cancelTenantSubscription(tenantId);
        setToast("Abonnement annulé en fin de période.");
      } else if (action === "resume") {
        await adminApi.resumeTenantSubscription(tenantId);
        setToast("Abonnement réactivé.");
      } else if (action === "usage") {
        await adminApi.pushUsageBillingTenant(tenantId);
        setToast("Usage poussé vers Stripe.");
      }
      await Promise.all([loadMeta(), !isCabinetView ? loadTenants() : Promise.resolve()]);
    } catch (e) {
      setError(e?.message || "Action billing impossible.");
    } finally {
      setBusy("");
    }
  }

  async function handleSyncStripe() {
    try {
      setError("");
      await adminApi.syncStripeBilling(month);
      await Promise.all([loadMeta(), !isCabinetView ? loadTenants() : Promise.resolve()]);
      setToast("Synchronisation Stripe terminée.");
    } catch (e) {
      setError(e?.message || "Sync Stripe impossible.");
    }
  }

  function topActions(item) {
    return (
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr" }}>
        <button type="button" onClick={() => navigate(`/admin/tenants/${item.tenantId}`)} style={{ ...btn("yellow"), color: BRAND.navy }}>Ouvrir la page cabinet</button>
        <button type="button" onClick={() => runAction("checkout")} disabled={busy === "checkout"} style={btn("dark")}>Créer checkout</button>
        <button type="button" onClick={() => runAction("usage")} style={btn("dark")}>Pousser usage</button>
        <button type="button" onClick={() => runAction("plan_growth")} disabled={busy === "plan_growth"} style={btn("dark")}>Changer plan</button>
      </div>
    );
  }

  if (loading && !summary && !selected) {
    return <div style={{ padding: 24, color: BRAND.muted, fontWeight: 700 }}>Chargement billing...</div>;
  }

  return (
    <div style={{ minHeight: "100%", background: BRAND.bg, color: BRAND.ink, fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif", padding: isNarrow ? "10px 8px 16px" : "14px 12px 20px" }}>
      <header style={{ marginBottom: 14, display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ marginBottom: 6, display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid #BFE9EC", borderRadius: 999, background: "#fff", padding: "4px 10px", fontSize: 11, fontWeight: 800, color: BRAND.tealDark }}>
            Admin · Billing plateforme
          </div>
          <h1 style={{ margin: 0, fontSize: isNarrow ? 30 : 38, lineHeight: 1.05, letterSpacing: "-0.05em", fontWeight: 900, color: BRAND.navy }}>Billing plateforme</h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, fontWeight: 600, color: BRAND.muted }}>
            Revenus, abonnements Stripe, consommation Vapi et marge par cabinet.
          </p>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ borderRadius: 14, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "10px 12px", fontWeight: 800, color: BRAND.navy }} />
          <button type="button" style={btn("light")}>Export CSV</button>
          <button type="button" onClick={handleSyncStripe} style={btn("light")}>Sync Stripe</button>
          <button type="button" onClick={() => Promise.all([loadMeta(), !isCabinetView ? loadTenants() : Promise.resolve()])} style={btn("teal")}>Rafraîchir</button>
        </div>
      </header>

      {error ? (
        <div style={{ marginBottom: 10, borderRadius: 12, border: `1px solid ${BRAND.red}55`, background: "#FEECEC", color: BRAND.red, padding: "10px 12px", fontSize: 13, fontWeight: 700 }}>
          {isSessionExpiredError(error) ? "Session admin expirée. Reconnecte-toi pour accéder au billing." : error}
        </div>
      ) : null}
      {toast ? (
        <div style={{ marginBottom: 10, borderRadius: 12, border: `1px solid ${BRAND.teal}55`, background: BRAND.softTeal, color: BRAND.tealDark, padding: "10px 12px", fontSize: 13, fontWeight: 700 }}>
          {toast}
        </div>
      ) : null}

      {!isCabinetView ? (
        <>
          <section style={{ marginBottom: 12, display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
            <KpiCard label="MRR" value={eur(totals.mrr)} detail="subscriptions actives" variant="teal" />
            <KpiCard label="Revenus estimés" value={eur(totals.revenue)} detail="base + dépassements" variant="green" />
            <KpiCard label="Coût Vapi" value={eur(totals.vapi)} detail="estimation 30j" variant="orange" />
            <KpiCard label="Marge estimée" value={eur(totals.margin)} detail={`${totals.marginRate}%`} variant={totals.margin < 0 ? "red" : "navy"} />
            <KpiCard label="Minutes" value={Math.round(totals.minutes).toLocaleString("fr-FR")} detail="consommées" variant="blue" />
            <KpiCard label="Dépassements" value={eur(totals.overage)} detail="à facturer" variant="yellow" />
            <KpiCard label="Alertes billing" value={String(totals.alerts)} detail="à traiter" variant="red" />
          </section>

          <div style={{ display: "grid", gap: 12, gridTemplateColumns: isNarrow ? "1fr" : "minmax(0,1.4fr) minmax(320px,0.8fr)" }}>
            <section style={{ display: "grid", gap: 12 }}>
              <div style={{ borderRadius: 22, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
                <div style={{ marginBottom: 8, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 22, fontWeight: 900, letterSpacing: "-0.03em", color: BRAND.navy }}>À traiter billing</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: BRAND.muted }}>Paiements, essais, quotas, dépassements et marge faible.</div>
                  </div>
                  <Pill variant="red">{actionItems.length} actions</Pill>
                </div>
                <div style={{ display: "grid", gap: 8 }}>
                  {actionItems.map((a, index) => (
                    <div key={`${a.tenant_id}-${a.title}`} style={{ borderRadius: 14, border: `1px solid ${BRAND.border}`, background: "#FBFDFD", padding: 10, display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "42px minmax(0,1fr) auto", alignItems: "center" }}>
                      <div style={{ ...tone(a.severity === "critical" ? "red" : "orange"), border: "1px solid", borderRadius: 12, width: 36, height: 36, display: "grid", placeItems: "center", fontWeight: 900 }}>{index + 1}</div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 900, color: BRAND.navy }}>{a.tenant_name}</div>
                        <div style={{ marginTop: 1, fontSize: 13, fontWeight: 800, color: BRAND.ink }}>{a.title}</div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: BRAND.muted }}>{a.description}</div>
                      </div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        <button type="button" onClick={() => setSelectedId(String(a.tenant_id))} style={{ ...btn("teal"), padding: "8px 10px", fontSize: 12 }}>Voir</button>
                        <button type="button" onClick={() => navigate(`/admin/tenants/${a.tenant_id}`)} style={{ ...btn("light"), padding: "8px 10px", fontSize: 12 }}>Fiche</button>
                      </div>
                    </div>
                  ))}
                  {!actionItems.length ? (
                    <div style={{ borderRadius: 12, border: "1px dashed #BFD3DA", background: "#FBFDFD", color: BRAND.muted, fontWeight: 700, fontSize: 13, textAlign: "center", padding: "12px 10px" }}>
                      Aucune action critique pour le moment.
                    </div>
                  ) : null}
                </div>
              </div>

              <div style={{ borderRadius: 22, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
                <div style={{ marginBottom: 10, display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "space-between" }}>
                  <div>
                    <div style={{ fontSize: 22, fontWeight: 900, letterSpacing: "-0.03em", color: BRAND.navy }}>Cabinets billing</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: BRAND.muted }}>MRR, usage, coût Vapi, dépassements, marge et statut Stripe.</div>
                  </div>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rechercher cabinet..." style={{ minWidth: isNarrow ? "100%" : 200, width: isNarrow ? "100%" : "auto", borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "8px 10px", fontWeight: 700, color: BRAND.navy }} />
                </div>
                <div style={{ marginBottom: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {["Tous", "Actifs", "Essais", "Quota élevé", "Dépassement", "Marge faible", "Stripe incomplet", "Alertes"].map((f) => (
                    <button key={f} type="button" onClick={() => setFilter(f)} style={{ borderRadius: 999, border: "1px solid transparent", padding: "6px 10px", fontSize: 11, fontWeight: 800, cursor: "pointer", ...(filter === f ? tone("navy", true) : { background: "#F2F4F7", color: BRAND.muted, borderColor: "transparent" }) }}>
                      {f}
                    </button>
                  ))}
                  <select value={sort} onChange={(e) => setSort(e.target.value)} style={{ marginLeft: "auto", borderRadius: 10, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "6px 8px", fontWeight: 800, color: BRAND.navy }}>
                    <option value="margin_low">Marge faible</option>
                    <option value="mrr">MRR décroissant</option>
                    <option value="vapi">Coût Vapi</option>
                    <option value="usage">Quota élevé</option>
                    <option value="name">Nom A-Z</option>
                    <option value="invoice">Prochaine facture</option>
                  </select>
                </div>

                <div style={{ borderRadius: 14, border: `1px solid #E4ECEF`, overflowX: "auto" }}>
                  <div style={{ minWidth: 860, display: "grid", gap: 8, gridTemplateColumns: "1.4fr .75fr .9fr .75fr .9fr .9fr .9fr .7fr", background: "#FBFDFD", borderBottom: "1px solid #E4ECEF", padding: "10px", fontSize: 10, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    <div>Cabinet</div><div>Plan</div><div>Stripe</div><div>MRR</div><div>Usage</div><div>Coût Vapi</div><div>Marge</div><div>Action</div>
                  </div>
                  {rows.map((r) => (
                    <div
                      key={r.tenantId}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedId(String(r.tenantId))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedId(String(r.tenantId));
                        }
                      }}
                      style={{ minWidth: 860, border: "none", borderBottom: "1px solid #E4ECEF", textAlign: "left", background: String(selectedId) === String(r.tenantId) ? "#F8FBFC" : "#fff", padding: "10px", display: "grid", gap: 8, gridTemplateColumns: "1.4fr .75fr .9fr .75fr .9fr .9fr .9fr .7fr", alignItems: "center", cursor: "pointer" }}
                    >
                      <div>
                        <div style={{ fontWeight: 900, color: BRAND.navy }}>{r.name}</div>
                        <div style={{ marginTop: 2, fontSize: 11, fontWeight: 700, color: BRAND.muted }}>
                          {r.periodEndTs ? `Facture ${new Date(r.periodEndTs * 1000).toLocaleDateString("fr-FR")}` : "Facture —"}
                        </div>
                      </div>
                      <div><div style={{ fontWeight: 900, color: BRAND.navy }}>{r.planLabel}</div><div style={{ fontSize: 11, fontWeight: 700, color: BRAND.muted }}>{r.includedMinutes} min</div></div>
                      <div><Pill variant={statusTone(r.stripeStatus)}>{r.stripeStatus || "none"}</Pill></div>
                      <div style={{ fontWeight: 900, color: BRAND.navy }}>{eur(r.mrr)}</div>
                      <UsageBar percent={r.usagePercent} />
                      <div style={{ fontWeight: 900, color: BRAND.navy }}>{eur(r.vapiCost)}</div>
                      <div><div style={{ fontWeight: 900, color: r.margin < 0 ? BRAND.red : BRAND.green }}>{eur(r.margin)}</div><div style={{ fontSize: 11, fontWeight: 700, color: BRAND.muted }}>{r.marginRate}%</div></div>
                      <div>
                        <button type="button" onClick={(e) => { e.stopPropagation(); navigate(`/admin/billing/${r.tenantId}`); }} style={{ ...btn("light"), fontSize: 12, padding: "7px 10px" }}>
                          Ouvrir
                        </button>
                      </div>
                    </div>
                  ))}
                  {!rows.length ? (
                    <div style={{ padding: 14, textAlign: "center", fontWeight: 700, color: BRAND.muted }}>Aucun cabinet ne correspond au filtre.</div>
                  ) : null}
                </div>
              </div>
            </section>

            {selected ? (
              <aside style={{ position: isNarrow ? "static" : "sticky", top: 10, alignSelf: "start", display: "grid", gap: 10 }}>
                <section style={{ overflow: "hidden", borderRadius: 24, border: `1px solid ${BRAND.border}`, background: "#fff" }}>
                  <div style={{ background: BRAND.navy, color: "#fff", padding: 12 }}>
                    <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                      <Pill variant={statusTone(selected.stripeStatus)}>{selected.stripeStatus || "none"}</Pill>
                      <Pill variant="blue">{selected.planLabel}</Pill>
                    </div>
                    <div style={{ fontSize: 30, fontWeight: 900, letterSpacing: "-0.04em" }}>{selected.name}</div>
                    <div style={{ marginTop: 2, fontSize: 13, fontWeight: 700, opacity: 0.8 }}>Cabinet sélectionné</div>
                    <div style={{ marginTop: 10 }}>{topActions(selected)}</div>
                  </div>
                  <div style={{ padding: 10, display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr" }}>
                    <Metric label="MRR" value={eur(selected.mrr)} />
                    <Metric label="Revenu estimé" value={eur(selected.expectedRevenue)} />
                    <Metric label="Coût Vapi" value={eur(selected.vapiCost)} />
                    <Metric label="Marge" value={`${eur(selected.margin)} · ${selected.marginRate}%`} danger={selected.margin < 0} />
                    <div style={{ gridColumn: "1 / -1", borderRadius: 12, border: "1px solid #E4ECEF", background: "#FBFDFD", padding: 10 }}>
                      <div style={{ marginBottom: 5, fontSize: 10, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase" }}>Usage vocal</div>
                      <UsageBar percent={selected.usagePercent} />
                      <div style={{ marginTop: 8, display: "grid", gap: 6, gridTemplateColumns: isNarrow ? "1fr" : "repeat(3,1fr)" }}>
                        <Small label="Inclus" value={`${selected.includedMinutes} min`} />
                        <Small label="Utilisé" value={`${Math.round(selected.usedMinutes)} min`} />
                        <Small label="Dépassement" value={`${Math.round(selected.overMinutes)} min`} />
                      </div>
                    </div>
                  </div>
                </section>

                <section style={{ borderRadius: 20, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
                  <div style={{ marginBottom: 8, fontSize: 18, fontWeight: 900, color: BRAND.navy }}>Alertes cabinet</div>
                  {selected.alerts.length ? (
                    <div style={{ display: "grid", gap: 6 }}>
                      {selected.alerts.map((a) => (
                        <div key={a} style={{ borderRadius: 10, border: `1px solid ${BRAND.red}44`, background: "#FEECEC", padding: "8px 10px", color: BRAND.red, fontSize: 12, fontWeight: 800 }}>{a}</div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ borderRadius: 10, border: `1px solid ${BRAND.green}44`, background: "#EAF8F0", padding: "8px 10px", color: BRAND.green, fontSize: 12, fontWeight: 800 }}>
                      Aucune alerte billing active.
                    </div>
                  )}
                </section>
              </aside>
            ) : null}
          </div>
        </>
      ) : selected ? (
        <div>
          <button type="button" onClick={() => navigate("/admin/billing")} style={{ ...btn("light"), marginBottom: 10 }}>← Retour billing plateforme</button>
          <section style={{ borderRadius: 24, border: `1px solid ${BRAND.border}`, overflow: "hidden", background: "#fff", marginBottom: 10 }}>
            <div style={{ background: BRAND.navy, color: "#fff", padding: 14 }}>
              <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                <Pill variant={statusTone(selected.stripeStatus)}>{selected.stripeStatus || "none"}</Pill>
                <Pill variant="blue">{selected.planLabel}</Pill>
                <Pill variant={selected.alerts.length ? "red" : "green"}>{selected.alerts.length ? `${selected.alerts.length} alerte(s)` : "Billing OK"}</Pill>
              </div>
              <h2 style={{ margin: 0, fontSize: 36, fontWeight: 900, letterSpacing: "-0.05em" }}>{selected.name}</h2>
              <p style={{ margin: "4px 0 0", fontSize: 13, fontWeight: 700, opacity: 0.75 }}>Page billing cabinet</p>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 8 }}>
                <button type="button" onClick={() => runAction("portal")} style={btn("dark")}>Ouvrir Stripe</button>
                <button type="button" onClick={() => runAction("checkout")} style={btn("dark")}>Créer checkout</button>
                <button type="button" onClick={() => runAction("usage")} style={btn("dark")}>Pousser usage</button>
                <button type="button" onClick={() => runAction("plan_growth")} style={{ ...btn("yellow"), color: BRAND.navy }}>Changer plan</button>
              </div>
            </div>
            <div style={{ padding: 10, display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
              <KpiCard label="MRR" value={eur(selected.mrr)} detail={`${selected.includedMinutes} min incluses`} variant="teal" />
              <KpiCard label="Usage" value={`${Math.round(selected.usedMinutes)} min`} detail={`${Math.max(0, selected.includedMinutes - selected.usedMinutes)} min restantes`} variant="blue" />
              <KpiCard label="Dépassement" value={`${Math.round(selected.overMinutes)} min`} detail={eur(selected.overageAmount)} variant={selected.overMinutes ? "orange" : "green"} />
              <KpiCard label="Coût Vapi" value={eur(selected.vapiCost)} detail="estimation" variant="orange" />
              <KpiCard label="Marge" value={eur(selected.margin)} detail={`${selected.marginRate}%`} variant={selected.margin < 0 ? "red" : "green"} />
              <KpiCard label="Prochaine facture" value={selected.periodEndTs ? new Date(selected.periodEndTs * 1000).toLocaleDateString("fr-FR") : "—"} detail="Stripe" variant="navy" />
            </div>
          </section>

          <section style={{ marginBottom: 10, borderRadius: 16, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {[
              ["overview", "Vue billing"],
              ["usage", "Usage & marge"],
              ["stripe", "Stripe"],
              ["invoices", "Factures"],
              ["actions", "Actions"],
            ].map(([id, label]) => (
              <button key={id} type="button" onClick={() => setTab(id)} style={{ borderRadius: 12, border: "1px solid transparent", padding: "9px 12px", fontWeight: 800, cursor: "pointer", ...(tab === id ? tone("navy", true) : { background: "transparent", color: BRAND.muted, borderColor: "transparent" }) }}>
                {label}
              </button>
            ))}
          </section>

          <section style={{ borderRadius: 20, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
            {tab === "overview" ? (
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))" }}>
                <Metric label="Plan actuel" value={`${selected.planLabel} · ${eur(selected.mrr)}/mois`} />
                <Metric label="Usage actuel" value={`${Math.round(selected.usedMinutes)} / ${selected.includedMinutes} min`} />
                <Metric label="Revenu estimé" value={eur(selected.expectedRevenue)} />
                <Metric label="Coût fournisseur Vapi" value={eur(selected.vapiCost)} />
                <Metric label="Marge estimée" value={`${eur(selected.margin)} · ${selected.marginRate}%`} danger={selected.margin < 0} />
                <Metric label="Synchronisation" value={tenantBilling?.updated_at || "—"} />
              </div>
            ) : null}

            {tab === "usage" ? (
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
                <Metric label="Appels vocaux" value={`${Math.round(selected.usedMinutes)} min`} />
                <Metric label="Minutes incluses" value={`${selected.includedMinutes} min`} />
                <Metric label="Dépassement actuel" value={`${Math.round(selected.overMinutes)} min · ${eur(selected.overageAmount)}`} />
                <Metric label="Projection fin de mois" value={`${Math.round(selected.usedMinutes * 1.18)} min`} />
                <Metric label="Quota API" value={tenantQuota ? `${Math.round((Number(tenantQuota.voice_minutes_used || 0) / Math.max(1, Number(tenantQuota.included_minutes || 1))) * 100)}%` : `${selected.usagePercent}%`} />
              </div>
            ) : null}

            {tab === "stripe" ? (
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))" }}>
                <Metric label="Customer ID" value={selected.stripeCustomerId || "—"} />
                <Metric label="Subscription ID" value={selected.stripeSubscriptionId || "—"} />
                <Metric label="Metered item ID" value={tenantBilling?.stripe_metered_item_id || "—"} />
                <Metric label="Statut Stripe" value={selected.stripeStatus || "—"} />
                <Metric label="Prochaine facture" value={selected.periodEndTs ? new Date(selected.periodEndTs * 1000).toLocaleDateString("fr-FR") : "—"} />
              </div>
            ) : null}

            {tab === "invoices" ? (
              <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid #E4ECEF" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, background: "#FBFDFD", borderBottom: "1px solid #E4ECEF", padding: "10px", fontSize: 11, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  <div>Période</div><div>Montant</div><div>Statut</div><div>Détail</div>
                </div>
                {(tenantInvoices || []).map((inv) => (
                  <div key={inv.id} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, borderBottom: "1px solid #E4ECEF", padding: "10px", fontSize: 13, fontWeight: 700, color: BRAND.navy }}>
                    <div>{inv.created ? new Date(inv.created * 1000).toLocaleDateString("fr-FR") : "—"}</div>
                    <div>{eur(inv.amount_due || 0)}</div>
                    <div>{inv.status || "—"}</div>
                    <div>{inv.number || inv.id || "—"}</div>
                  </div>
                ))}
                {!tenantInvoices.length ? <div style={{ padding: 12, color: BRAND.muted, fontWeight: 700 }}>Aucune facture disponible.</div> : null}
              </div>
            ) : null}

            {tab === "actions" ? (
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
                <ActionCard title="Créer / ouvrir checkout Stripe" onClick={() => runAction("checkout")} />
                <ActionCard title="Changer plan vers Growth" onClick={() => runAction("plan_growth")} />
                <ActionCard title="Pousser usage Stripe" onClick={() => runAction("usage")} />
                <ActionCard title="Relancer paiement / portail" onClick={() => runAction("portal")} />
                <ActionCard title="Suspendre abonnement" onClick={() => runAction("cancel")} />
                <ActionCard title="Réactiver abonnement" onClick={() => runAction("resume")} />
              </div>
            ) : null}
          </section>
        </div>
      ) : (
        <div style={{ padding: 20, color: BRAND.muted, fontWeight: 700 }}>Cabinet introuvable.</div>
      )}
    </div>
  );
}

function btn(kind) {
  if (kind === "teal") return { borderRadius: 12, border: "none", background: BRAND.teal, color: "#fff", padding: "10px 12px", fontWeight: 900, cursor: "pointer" };
  if (kind === "yellow") return { borderRadius: 12, border: "none", background: BRAND.yellow, color: BRAND.navy, padding: "10px 12px", fontWeight: 900, cursor: "pointer" };
  if (kind === "dark") return { borderRadius: 12, border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.08)", color: "#fff", padding: "10px 12px", fontWeight: 900, cursor: "pointer" };
  return { borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#fff", color: BRAND.ink, padding: "10px 12px", fontWeight: 800, cursor: "pointer" };
}

function Metric({ label, value, danger = false }) {
  return (
    <div style={{ borderRadius: 12, border: "1px solid #E4ECEF", background: "#FBFDFD", padding: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</div>
      <div style={{ marginTop: 4, fontSize: 14, fontWeight: 900, color: danger ? BRAND.red : BRAND.navy }}>{value}</div>
    </div>
  );
}

function Small({ label, value }) {
  return (
    <div style={{ borderRadius: 8, background: "#fff", padding: "6px 8px", textAlign: "center" }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase" }}>{label}</div>
      <div style={{ marginTop: 2, fontSize: 11, fontWeight: 900, color: BRAND.navy }}>{value}</div>
    </div>
  );
}

function ActionCard({ title, onClick }) {
  return (
    <button type="button" onClick={onClick} style={{ borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#FBFDFD", padding: "12px 10px", textAlign: "left", cursor: "pointer" }}>
      <div style={{ fontSize: 14, fontWeight: 900, color: BRAND.navy }}>{title}</div>
      <div style={{ marginTop: 3, fontSize: 11, fontWeight: 700, color: BRAND.muted }}>Action admin protégée + audit log recommandé.</div>
    </button>
  );
}
