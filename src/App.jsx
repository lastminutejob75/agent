// App racine : affiche la nouvelle landing UWi (synchro avec landing/)
import { BrowserRouter, Routes, Route } from "react-router-dom";
import UwiLanding from "./components/UwiLanding";
import CGV from "./pages/CGV";
import CGU from "./pages/CGU";
import MentionsLegales from "./pages/MentionsLegales";
import Contact from "./pages/Contact";

const legalStyle = {
  minHeight: "100vh",
  background: "#0D1120",
  color: "#e2e8f0",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
  textAlign: "center",
};
const codeStyle = { background: "rgba(0,212,170,0.15)", padding: "2px 8px", borderRadius: 4 };

function CreerAssistantePlaceholder() {
  return (
    <div style={legalStyle}>
      <div>
        <p style={{ marginBottom: 16, fontSize: 18 }}>
          Pour le wizard complet (création d'assistant), lancez l'app depuis le dossier <code style={codeStyle}>landing/</code>.
        </p>
        <p style={{ marginBottom: 24, color: "#94a3b8" }}>
          <code>cd landing && npm run dev</code>
        </p>
        <a href="/" style={{ color: "#00d4aa", textDecoration: "underline" }}>← Retour à l'accueil</a>
      </div>
    </div>
  );
}

function LoginPlaceholder() {
  return (
    <div style={legalStyle}>
      <div>
        <p style={{ marginBottom: 16, fontSize: 18 }}>
          Pour vous connecter, lancez l'app depuis le dossier <code style={codeStyle}>landing/</code>.
        </p>
        <p style={{ marginBottom: 24, color: "#94a3b8" }}>
          <code>cd landing && npm run dev</code>
        </p>
        <a href="/" style={{ color: "#00d4aa", textDecoration: "underline" }}>← Retour à l'accueil</a>
      </div>
    </div>
  );
}

function CheckoutPlaceholder() {
  return (
    <div style={legalStyle}>
      <div>
        <p style={{ marginBottom: 16, fontSize: 18 }}>
          Pour le paiement Stripe, lancez l'app depuis le dossier <code style={codeStyle}>landing/</code>.
        </p>
        <p style={{ marginBottom: 24, color: "#94a3b8" }}>
          <code>cd landing && npm run dev</code>
        </p>
        <a href="/" style={{ color: "#00d4aa", textDecoration: "underline" }}>← Retour à l'accueil</a>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UwiLanding />} />
        <Route path="/login" element={<LoginPlaceholder />} />
        <Route path="/creer-assistante" element={<CreerAssistantePlaceholder />} />
        <Route path="/cgv" element={<CGV />} />
        <Route path="/cgu" element={<CGU />} />
        <Route path="/mentions-legales" element={<MentionsLegales />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/checkout" element={<CheckoutPlaceholder />} />
        <Route path="/checkout/return" element={<CheckoutPlaceholder />} />
      </Routes>
    </BrowserRouter>
  );
}
