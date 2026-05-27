import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { getBillingOverview, getBillingPlans } from "../../lib/adminApi";
import {
  T,
  font,
  radius,
  keyframes,
  formatNumber,
  formatEuro,
  formatUsd,
} from "../theme.js";
import { Button } from "../components/ui/Button.jsx";
import { MiniStat } from "../components/ui/MiniStat.jsx";

const AdminBillingSection = lazy(() => import("../components/AdminBillingSection"));
const BillingSearchBar = lazy(() =>
  import("../components/AdminBillingSection").then((m) => ({ default: m.BillingSearchBar })),
);

/**
 * Page /admin/billing — vue facturation (refonte CdC light mode).
 */
export default function AdminBilling() {
  const [overview, setOverview] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));

  const [search, setSearch] = useState("");
  const [filterPlan, setFilterPlan] = useState("all");
  const [filterStripe, setFilterStripe] = useState("all");

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

  // ---- Stats résumé --------------------------------------------------------
  const stats = useMemo(() => {
    const summary = overview?.summary || {};
    const tenants = overview?.tenants || [];
    return {
      total: tenants.length,
      mrr: Number(summary.mrr_eur_total ?? 0),
      vapiCost: Number(summary.cost_usd_month_total ?? 0),
      pastDue: Number(summary.tenants_past_due_count ?? 0),
    };
  }, [overview]);

  return (
    <div style={{ padding: 32, background: T.bgPage, minHeight: "100vh" }}>
      <style>{keyframes}</style>

      {/* Breadcrumb */}
      <nav
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
          color: T.textMuted,
          fontFamily: font.body,
          marginBottom: 12,
        }}
      >
        <Link
          to="/admin"
          style={{
            color: T.textSecondary,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 2,
            fontWeight: 500,
          }}
        >
          <ChevronLeft size={14} strokeWidth={2.4} />
          Dashboard
        </Link>
        <span>/</span>
        <span style={{ color: T.text, fontWeight: 600 }}>Billing</span>
      </nav>

      {/* En-tête */}
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 20,
        }}
      >
        <div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: T.text,
              fontFamily: font.display,
              margin: 0,
              letterSpacing: "-0.02em",
            }}
          >
            Billing & Abonnements
          </h1>
          <p
            style={{
              margin: "4px 0 0",
              color: T.textSecondary,
              fontSize: 14,
              fontFamily: font.body,
            }}
          >
            Plans, statuts Stripe, MRR et consommation Vapi par cabinet.
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <MonthInput value={month} onChange={setMonth} />
          <Button
            variant="ghost"
            iconLeft={<RefreshCw size={14} strokeWidth={2.4} />}
            onClick={load}
            disabled={loading}
          >
            Rafraîchir
          </Button>
        </div>
      </header>

      {/* Mini-stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <MiniStat
          label="Clients facturés"
          value={formatNumber(stats.total)}
          onClick={() => {
            setFilterPlan("all");
            setFilterStripe("all");
            setSearch("");
          }}
          active={filterPlan === "all" && filterStripe === "all" && !search}
          title="Réinitialiser les filtres"
        />
        <MiniStat
          label="MRR"
          value={formatEuro(stats.mrr)}
          tone={T.teal}
          onClick={() => setFilterStripe("active")}
          active={filterStripe === "active"}
          title="Voir uniquement les abonnements actifs"
        />
        <MiniStat
          label="Coût Vapi (mois)"
          value={formatUsd(stats.vapiCost)}
          tone={T.orange}
        />
        <MiniStat
          label="Past due"
          value={formatNumber(stats.pastDue)}
          tone={stats.pastDue > 0 ? T.red : T.textSecondary}
          onClick={() => setFilterStripe("past_due")}
          active={filterStripe === "past_due"}
          title="Filtrer sur les abonnements past due"
        />
      </div>

      {/* Barre de filtres */}
      <Suspense fallback={<div style={{ height: 64 }} />}>
        <BillingSearchBar
          search={search}
          setSearch={setSearch}
          filterPlan={filterPlan}
          setFilterPlan={setFilterPlan}
          filterStripe={filterStripe}
          setFilterStripe={setFilterStripe}
        />
      </Suspense>

      {/* Section principale */}
      <Suspense
        fallback={
          <div
            style={{
              padding: 48,
              textAlign: "center",
              color: T.textSecondary,
              fontFamily: font.body,
            }}
          >
            Chargement billing…
          </div>
        }
      >
        <AdminBillingSection
          overview={overview}
          plans={plans}
          loading={loading}
          error={error}
          search={search}
          filterPlan={filterPlan}
          filterStripe={filterStripe}
          reloadBilling={load}
        />
      </Suspense>
    </div>
  );
}

// ---- MonthInput --------------------------------------------------------------

function MonthInput({ value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          fontFamily: font.body,
        }}
      >
        Mois
      </span>
      <input
        type="month"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          background: T.bgCard,
          border: `1px solid ${T.border}`,
          borderRadius: radius.md,
          color: T.text,
          padding: "7px 12px",
          fontSize: 13,
          fontFamily: font.body,
          fontWeight: 500,
          outline: "none",
          cursor: "pointer",
        }}
        onFocus={(e) => (e.currentTarget.style.borderColor = T.teal)}
        onBlur={(e) => (e.currentTarget.style.borderColor = T.border)}
      />
    </div>
  );
}
