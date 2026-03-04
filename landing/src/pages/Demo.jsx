// Page standalone /demo — Parlez à Clara, assistante vocale IA
// Pas de navbar ni footer global. 100% autonome.
// ?ref=email : démo envoyée par l'admin à un lead → message personnalisé + pré-remplissage wizard
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import "./Demo.css";

const REF_STORAGE_KEY = "uwi_demo_ref";

// Icônes inline (pas de dépendance lucide pour cette page standalone)
function PhoneIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.22 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-.72a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}

function UsersIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}

function CheckIcon({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Demo() {
  const [refEmail, setRefEmail] = useState("");
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = (params.get("ref") || "").trim();
    if (ref) {
      setRefEmail(ref);
      try {
        sessionStorage.setItem(REF_STORAGE_KEY, ref);
      } catch (_) {}
    }
  }, []);

  return (
    <div className="demo-page">
      <Helmet>
        <title>UWi — Parlez à Clara, votre assistante IA</title>
        <meta
          name="description"
          content="Testez Clara, l'assistante vocale IA pour cabinets médicaux. Elle répond, filtre et prend les rendez-vous automatiquement."
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Outfit:wght@300;400;500;600&display=swap"
        />
      </Helmet>

      {/* 1. HEADER */}
      <header className="demo-header demo-fade-down">
        <span className="demo-logo">
          UW<span className="demo-logo-i">i</span>
        </span>
        <div className="demo-status-badge">
          <span className="demo-status-dot" aria-hidden />
          <span>Clara disponible</span>
        </div>
      </header>

      {/* 2. HERO */}
      <main className="demo-main">
        <p className="demo-eyebrow demo-fade-up" style={{ animationDelay: "0.3s" }}>
          {refEmail ? (
            <>
              Démo personnalisée pour vous
              {refEmail.includes("@") && (
                <span className="demo-ref-email" style={{ opacity: 0.85, fontWeight: 500 }}>
                  {" "}({refEmail})
                </span>
              )}
            </>
          ) : (
            "Démo live · Sans inscription"
          )}
        </p>

        <div className="demo-stat-choc demo-fade-up" style={{ animationDelay: "0.35s" }}>
          <span className="demo-stat-number">30%</span>
          <div>
            <p>des appels de cabinet restent sans réponse.</p>
            <p>Chaque appel manqué, c'est un patient perdu.</p>
          </div>
        </div>

        <h1 className="demo-h1 demo-fade-up" style={{ animationDelay: "0.45s" }}>
          Concentrez-vous sur
          <br />
          vos <em>patients.</em>
        </h1>

        <p className="demo-subtitle demo-fade-up" style={{ animationDelay: "0.6s" }}>
          Clara répond, filtre et prend les rendez-vous —
          <br className="demo-br-mobile" />
          pour que vous ne manquiez plus jamais un appel.
        </p>

        {/* 3. CALL CARD */}
        <div className="demo-card demo-scale-in" style={{ animationDelay: "0.8s" }}>
          {/* A. Portrait Clara */}
          <div className="demo-portrait-wrap">
            <div className="demo-portrait-ring" aria-hidden />
            <img
              src="/images/clara.png"
              alt="Clara, assistante vocale IA UWi"
              className="demo-portrait-img"
              onError={(e) => {
                e.target.style.display = "none";
                e.target.nextElementSibling?.classList.remove("demo-portrait-placeholder-hidden");
              }}
            />
            <div className="demo-portrait-placeholder demo-portrait-placeholder-hidden">
              <span>Clara</span>
            </div>
            <div className="demo-portrait-overlay">
              <span className="demo-portrait-name">Clara</span>
              <span className="demo-portrait-role">Assistante vocale IA · UWi</span>
            </div>
            <span className="demo-badge-ia">IA</span>
          </div>

          <div className="demo-divider" />

          {/* C. CTA Principal */}
          <a href="tel:+33939240575" className="demo-cta-clara">
            <span className="demo-cta-icon-wrap">
              <PhoneIcon className="demo-cta-phone-icon" />
            </span>
            <span className="demo-cta-text">
              <strong>Appeler Clara maintenant</strong>
              <span className="demo-cta-sub">09 39 24 05 75 · Réponse en &lt; 2 sec</span>
            </span>
          </a>

          {/* D. Friction killer */}
          <p className="demo-friction">
            <CheckIcon className="demo-check-icon" />
            Aucune inscription · Appel standard gratuit
          </p>

          {/* E. Séparateur ou */}
          <div className="demo-or-sep">
            <span>ou</span>
          </div>

          {/* F. Bouton Expert */}
          <a href="tel:+33652398414" className="demo-cta-expert">
            <span className="demo-cta-icon-wrap demo-cta-icon-outline">
              <UsersIcon className="demo-cta-users-icon" />
            </span>
            <span className="demo-cta-text">
              <strong>Parler à un expert</strong>
              <span className="demo-cta-sub">06 52 39 84 14</span>
            </span>
          </a>

          {/* G. Tags */}
          <div className="demo-tags">
            <span>Répond en &lt; 2 sec</span>
            <span>Français naturel</span>
            <span>Vérifie les dispos</span>
            <span>Prend les RDV</span>
          </div>

          {/* H. CTA Créer assistante (si ref = lien admin → lead) */}
          {refEmail && (
            <div className="demo-or-sep" style={{ marginTop: 16 }}>
              <span>ou</span>
            </div>
          )}
          {refEmail && (
            <Link
              to={`/creer-assistante?ref=${encodeURIComponent(refEmail)}`}
              className="demo-cta-expert"
              style={{ textDecoration: "none", display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}
            >
              <span className="demo-cta-text">
                <strong>Créer mon assistante personnalisée</strong>
                <span className="demo-cta-sub">Email pré-rempli · En 2 min</span>
              </span>
            </Link>
          )}
        </div>

        {/* 4. SECTION STEPS */}
        <section className="demo-steps demo-fade-up" style={{ animationDelay: "1.1s" }}>
          <h2 className="demo-steps-title">Ce qui se passe quand vous appelez</h2>
          <div className="demo-steps-grid">
            <div className="demo-step-card">
              <span className="demo-step-num">01</span>
              <p>Clara décroche immédiatement et se présente comme l'assistante du cabinet</p>
            </div>
            <div className="demo-step-card">
              <span className="demo-step-num">02</span>
              <p>Elle comprend votre demande, filtre les urgences et consulte l'agenda</p>
            </div>
            <div className="demo-step-card">
              <span className="demo-step-num">03</span>
              <p>Elle confirme le rendez-vous en moins de 90 secondes</p>
            </div>
          </div>
        </section>
      </main>

      {/* 5. FOOTER */}
      <footer className="demo-footer demo-fade-up" style={{ animationDelay: "1.4s" }}>
        <span className="demo-logo demo-logo-muted">UWi</span>
        <span className="demo-footer-text">Assistante IA pour cabinets médicaux · uwiapp.com</span>
      </footer>
    </div>
  );
}
