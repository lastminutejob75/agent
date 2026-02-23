import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";

const stripeApiUrl = import.meta.env.VITE_STRIPE_API_URL || "http://localhost:4242";

export default function CheckoutReturn() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState(null);
  const [customerEmail, setCustomerEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      setError("Paramètre session_id manquant");
      return;
    }
    fetch(`${stripeApiUrl}/session-status?session_id=${encodeURIComponent(sessionId)}`)
      .then((res) => res.json())
      .then((data) => {
        setStatus(data.status);
        setCustomerEmail(data.customer_email || "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const style = {
    minHeight: "100vh",
    background: "#0D1120",
    color: "#e2e8f0",
    padding: 24,
    textAlign: "center",
  };
  const linkStyle = { color: "#00F0B5", marginTop: 24, display: "inline-block" };

  if (loading) {
    return (
      <div style={style}>
        <p>Vérification du paiement...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={style}>
        <p style={{ color: "#f87171" }}>{error}</p>
        <Link to="/" style={linkStyle}>← Retour à l'accueil</Link>
      </div>
    );
  }

  if (status === "open") {
    return (
      <div style={style}>
        <p>Paiement en cours. Vous pouvez retourner au checkout.</p>
        <Link to="/checkout" style={linkStyle}>Retour au paiement</Link>
      </div>
    );
  }

  if (status === "complete") {
    return (
      <div style={style}>
        <h1 style={{ color: "#00F0B5", marginBottom: 16 }}>Merci pour votre achat</h1>
        <p>Un email de confirmation a été envoyé à {customerEmail || "votre adresse"}.</p>
        <p style={{ marginTop: 8, opacity: 0.8 }}>Pour toute question, contactez-nous via la page Contact.</p>
        <Link to="/" style={linkStyle}>← Retour à l'accueil</Link>
      </div>
    );
  }

  return (
    <div style={style}>
      <p>Statut : {status || "inconnu"}</p>
      <Link to="/" style={linkStyle}>← Retour à l'accueil</Link>
    </div>
  );
}
