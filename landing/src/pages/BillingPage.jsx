import { useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";

/**
 * Page /billing : retours Stripe Checkout (success/cancel) + UI Billing minimale.
 * URLs configurées côté Stripe :
 *   STRIPE_CHECKOUT_SUCCESS_URL=https://uwiapp.com/billing?checkout=success
 *   STRIPE_CHECKOUT_CANCEL_URL=https://uwiapp.com/billing?checkout=cancel
 *
 * TODO: Récupération des données billing — aucun endpoint tenant-scoped pour l’instant.
 * Backend : GET /api/admin/tenants/{tenant_id}/billing existe (admin uniquement).
 * Si un GET /api/app/billing ou équivalent (tenant_id depuis session) est ajouté,
 * brancher ici : fetch au mount, afficher plan_key, billing_status, current_period_end.
 */
export default function BillingPage() {
  const [searchParams] = useSearchParams();
  const checkoutStatus = searchParams.get("checkout"); // "success" | "cancel" | null

  // Nettoyer le param après affichage pour éviter de revoir le bandeau au refresh/partage d’URL
  useEffect(() => {
    if (checkoutStatus === "success" || checkoutStatus === "cancel") {
      const url = new URL(window.location.href);
      url.searchParams.delete("checkout");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }, [checkoutStatus]);

  const wrapperStyle = {
    minHeight: "100vh",
    background: "#0D1120",
    color: "#e2e8f0",
    padding: "24px 16px",
    maxWidth: 560,
    margin: "0 auto",
  };

  const titleStyle = {
    fontSize: "1.5rem",
    fontWeight: 700,
    color: "#e2e8f0",
    marginBottom: 24,
  };

  const bandeauSuccess = {
    background: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.4)",
    color: "#34d399",
    padding: "12px 16px",
    borderRadius: 10,
    marginBottom: 24,
    fontSize: "0.9375rem",
  };

  const bandeauCancel = {
    background: "rgba(248, 113, 113, 0.12)",
    border: "1px solid rgba(248, 113, 113, 0.35)",
    color: "#f87171",
    padding: "12px 16px",
    borderRadius: 10,
    marginBottom: 24,
    fontSize: "0.9375rem",
  };

  const cardStyle = {
    background: "rgba(255, 255, 255, 0.06)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: 12,
    padding: 22,
    marginBottom: 24,
  };

  const labelStyle = {
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    color: "rgba(255, 255, 255, 0.5)",
    marginBottom: 8,
  };

  const valueStyle = {
    fontSize: "0.9375rem",
    color: "#e2e8f0",
    marginBottom: 12,
  };

  const linkStyle = {
    color: "#00F0B5",
    marginTop: 24,
    display: "inline-block",
    fontSize: "0.9375rem",
  };

  const buttonStyle = {
    padding: "12px 20px",
    borderRadius: 10,
    border: "1px solid rgba(0, 240, 181, 0.4)",
    background: "rgba(0, 240, 181, 0.1)",
    color: "#00F0B5",
    fontWeight: 600,
    fontSize: "0.9375rem",
    cursor: "pointer",
  };

  return (
    <div style={wrapperStyle}>
      <h1 style={titleStyle}>Facturation</h1>

      {checkoutStatus === "success" && (
        <div style={bandeauSuccess} role="alert">
          ✅ Abonnement activé avec succès.
        </div>
      )}
      {checkoutStatus === "cancel" && (
        <div style={bandeauCancel} role="alert">
          ❌ Paiement annulé.
        </div>
      )}

      <div style={cardStyle}>
        <div style={labelStyle}>Plan actuel</div>
        <div style={valueStyle}>
          <strong>Plan :</strong> —
        </div>
        <div style={valueStyle}>
          <strong>Statut :</strong> —
        </div>
        <div style={{ ...valueStyle, marginBottom: 0 }}>
          <strong>Prochaine échéance :</strong> —
        </div>
      </div>

      <button
        type="button"
        style={buttonStyle}
        onClick={() => {}}
        aria-label="Changer de plan (à venir)"
      >
        Changer de plan
      </button>
      <p style={{ marginTop: 32 }}>
        <Link to="/" style={linkStyle}>← Retour à l'accueil</Link>
        {" · "}
        <Link to="/app/facturation" style={linkStyle}>Facturation détaillée</Link>
      </p>
    </div>
  );
}
