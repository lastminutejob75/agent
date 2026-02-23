import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { loadStripe } from "@stripe/stripe-js";
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from "@stripe/react-stripe-js";
import { Link } from "react-router-dom";

const stripePk = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || "";
const stripeApiUrl = import.meta.env.VITE_STRIPE_API_URL || "http://localhost:4242";
const stripePromise = stripePk ? loadStripe(stripePk) : null;

export default function Checkout() {
  const [searchParams] = useSearchParams();
  const priceId = searchParams.get("price_id") || searchParams.get("price");

  const fetchClientSecret = useCallback(async () => {
    const res = await fetch(`${stripeApiUrl}/create-checkout-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity: 1, ...(priceId && { price_id: priceId }) }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Impossible de créer la session de paiement");
    }
    const data = await res.json();
    return data.clientSecret;
  }, [priceId]);

  if (!stripePk) {
    return (
      <div style={{ minHeight: "100vh", background: "#0D1120", color: "#e2e8f0", padding: 24, textAlign: "center" }}>
        <p>Clé Stripe (VITE_STRIPE_PUBLISHABLE_KEY) non configurée.</p>
        <p style={{ fontSize: 14, color: "rgba(255,255,255,0.6)", marginTop: 8 }}>
          Ajoute-la dans <code>landing/.env</code> puis redémarre le serveur.
        </p>
        <Link to="/" style={{ color: "#00F0B5", marginTop: 16, display: "inline-block" }}>← Retour à l'accueil</Link>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0D1120", padding: "24px 16px" }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <Link to="/" style={{ color: "#00F0B5", fontSize: 14, textDecoration: "none", marginBottom: 16, display: "inline-block" }}>
          ← Retour à l'accueil
        </Link>
        <h1 style={{ color: "#fff", fontSize: 24, marginBottom: 24 }}>Paiement sécurisé</h1>
        <EmbeddedCheckoutProvider stripe={stripePromise} options={{ fetchClientSecret }}>
          <EmbeddedCheckout />
        </EmbeddedCheckoutProvider>
      </div>
    </div>
  );
}
