// UWi Medical — Landing nouvelle maquette (navy, teal, mobile-first)
// Route / — CTAs vers /creer-assistante?new=1
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import "./UwiLandingNew.css";
const PricingSimulator = lazy(() => import("./PricingSimulator"));
const AgentsMarquee = lazy(() => import("./AgentsMarquee"));
const AgentsSpotlight = lazy(() => import("./AgentsSpotlight"));

const TYPEWRITER_LINES = [
  "Cabinet du Dr. Martin, bonjour ! Je suis UWi, comment puis-je vous aider ?",
  "Je vérifie les disponibilités… Mardi à 10h ou jeudi à 14h30, lequel vous convient ?",
  "Parfait. Mardi 25 à 10h, c'est noté. Une confirmation SMS vous sera envoyée.",
  "Pour un renouvellement, je transmets votre demande au Dr. Martin. Délai : 24h.",
];

function LogoStethoscope() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 6.5a4 4 0 0 0 8 0V4a.5.5 0 0 0-1 0v2.5a3 3 0 0 1-6 0V4a.5.5 0 0 0-1 0v2.5z" />
      <path d="M8.5 10.5V14a5.5 5.5 0 0 0 11 0v-1.5" />
      <circle cx="19.5" cy="12" r="1.5" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.22 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-.72a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}

function PhoneOutlineIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.22 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-.72a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}

const FAQ_ITEMS = [
  { q: "En combien de temps puis-je démarrer ?", a: "Environ 15 minutes : connexion à votre agenda, configuration des créneaux et de la voix. Votre assistant IA est opérationnel le jour même." },
  { q: "L'IA comprend-elle vraiment les demandes des patients ?", a: "Oui. UWi qualifie le motif (consultation, urgence, renouvellement), propose des créneaux en temps réel et gère les rappels. Elle s'améliore avec le temps." },
  { q: "Mes données sont-elles sécurisées ?", a: "Oui. Hébergement HDS, données en France, conformité RGPD. Nous ne réutilisons pas les conversations à des fins commerciales." },
  { q: "Puis-je annuler à tout moment ?", a: "Oui. Sans engagement : vous pouvez arrêter le service à tout moment. Aucun frais caché, résiliation en un clic." },
  { q: "Quels agendas sont compatibles ?", a: "Google Calendar, et bientôt d'autres logiciels de planification. La synchronisation est en temps réel pour éviter les doubles réservations." },
];

const PRICING_PLANS = [
  {
    name: "STARTER",
    price: "99 €/mois",
    description: "Pour un cabinet qui démarre ou teste UWi.",
    minutes: "400 minutes / mois",
    minutesSub: "≈ 100 appels patients - durée moyenne 4 min",
    overUsage: "Au-delà : 0,19€ / min — bascule auto vers Growth si plus avantageux",
    features: [
      { label: "Réponse téléphonique 24/7", included: true },
      { label: "Prise de RDV automatique", included: true },
      { label: "Rappels SMS patients", included: true },
      { label: "Intégration Doctolib / Maiia", included: true },
      { label: "Triage urgences avancé", included: false },
      { label: "Renouvellements ordonnances", included: false },
    ],
    cta: "Essai gratuit 1 mois",
    featured: false,
  },
  {
    name: "GROWTH",
    price: "149 €/mois",
    description: "Pour un cabinet actif avec flux régulier.",
    minutes: "800 minutes / mois",
    minutesSub: "≈ 200 appels patients - durée moyenne 4 min",
    overUsage: "Au-delà : 0,17€ / min — bascule auto vers Pro si plus avantageux",
    features: [
      { label: "Tout le plan Starter", included: true },
      { label: "Triage des urgences médicales", included: true },
      { label: "Renouvellements d'ordonnances", included: true },
      { label: "Rapports hebdomadaires", included: true },
      { label: "WhatsApp Business", included: false },
      { label: "Support prioritaire 7j/7", included: false },
    ],
    cta: "Essai gratuit 1 mois",
    featured: true,
    badge: "LE PLUS POPULAIRE",
  },
  {
    name: "PRO",
    price: "199 €/mois",
    description: "Pour les cabinets chargés qui veulent tout déléguer.",
    minutes: "1200 minutes / mois",
    minutesSub: "≈ 300 appels patients - durée moyenne 4 min",
    overUsage: "Au-delà : 0,15€ / min — tarif le plus bas",
    features: [
      { label: "Tout le plan Growth", included: true },
      { label: "WhatsApp Business inclus", included: true },
      { label: "Support prioritaire 7j/7", included: true },
      { label: "Onboarding personnalisé", included: true },
      { label: "Rapport mensuel détaillé", included: true },
    ],
    cta: "Essai gratuit 1 mois",
    featured: false,
  },
];

const SECURITY_ITEMS = [
  { icon: "🛡️", title: "Hébergement HDS", desc: "Données de santé hébergées chez un acteur certifié HDS." },
  { icon: "🔒", title: "RGPD", desc: "Conformité totale, pas de revente de données." },
  { icon: "🇫🇷", title: "Hébergé en France", desc: "Serveurs en France, souveraineté des données." },
  { icon: "⚡", title: "Disponibilité", desc: "Service conçu pour une disponibilité maximale." },
];

const STEPS = [
  { num: "1", title: "Connexion agenda", desc: "Connectez votre Google Calendar (ou autre). Les créneaux sont synchronisés en temps réel." },
  { num: "2", title: "Paramétrage", desc: "Définissez vos horaires, la voix de l'assistant et les règles (urgences, renouvellements)." },
  { num: "3", title: "En production", desc: "UWi décroche, prend les RDV et envoie les rappels. Vous restez concentré sur vos patients." },
];

function DeferredSectionFallback({ minHeight = 320 }) {
  return <div style={{ minHeight }} aria-hidden="true" />;
}

export default function UwiLanding() {
  const navigate = useNavigate();
  const bgRef = useRef(null);
  const waveRef = useRef(null);
  const waveRefDemo = useRef(null);
  const [typedLine, setTypedLine] = useState(0);
  const [typedChar, setTypedChar] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const [openFaq, setOpenFaq] = useState(-1);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const close = (e) => {
      if (!e.target.closest(".burger-btn") && !e.target.closest(".mobile-dropdown")) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  // BG Aurora canvas
  useEffect(() => {
    const c = bgRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    const resize = () => {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);
    const blobs = [
      { x: 0.5, y: 0, r: 0.65, col: "rgba(0,240,181,0.08)", sp: 0.00022, ph: 0 },
      { x: 0.85, y: 0.78, r: 0.5, col: "rgba(0,163,163,0.06)", sp: 0.00028, ph: 1.3 },
      { x: 0.1, y: 0.6, r: 0.44, col: "rgba(0,230,204,0.05)", sp: 0.00018, ph: 2.6 },
    ];
    const dots = Array.from({ length: 26 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 0.9 + 0.25,
      vx: (Math.random() - 0.5) * 9e-5,
      vy: (Math.random() - 0.5) * 9e-5,
      a: Math.random() * 0.28 + 0.06,
    }));
    let t = 0;
    const loop = () => {
      const W = c.width;
      const H = c.height;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#0D1120";
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "rgba(100,160,200,0.12)";
      ctx.lineWidth = 1;
      for (let x = 0; x < W; x += 44) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
      }
      for (let y = 0; y < H; y += 44) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }
      blobs.forEach((b) => {
        const bx = (b.x + Math.sin(t * b.sp * 1000 + b.ph) * 0.07) * W;
        const by = (b.y + Math.cos(t * b.sp * 1000 + b.ph * 1.4) * 0.055) * H;
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, b.r * Math.min(W, H));
        g.addColorStop(0, b.col);
        g.addColorStop(1, "transparent");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
      });
      dots.forEach((d) => {
        d.x += d.vx;
        d.y += d.vy;
        if (d.x < 0) d.x = 1;
        if (d.x > 1) d.x = 0;
        if (d.y < 0) d.y = 1;
        if (d.y > 1) d.y = 0;
        ctx.beginPath();
        ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,240,181,${d.a})`;
        ctx.fill();
      });
      t++;
      requestAnimationFrame(loop);
    };
    loop();
    return () => window.removeEventListener("resize", resize);
  }, []);

  // Waveform canvas (hero + section démo)
  const setupWave = (canvasRef) => {
    const c = canvasRef.current;
    if (!c) return () => {};
    const ctx = c.getContext("2d");
    let W = 0;
    let H = 0;
    const sz = () => {
      W = c.offsetWidth * (window.devicePixelRatio || 1);
      H = c.offsetHeight * (window.devicePixelRatio || 1);
      c.width = W;
      c.height = H;
    };
    sz();
    window.addEventListener("resize", sz);
    const N = 44;
    const ph = Array.from({ length: N }, () => Math.random() * Math.PI * 2);
    const sp = Array.from({ length: N }, () => 0.035 + Math.random() * 0.04);
    let t = 0;
    const loop = () => {
      ctx.clearRect(0, 0, W, H);
      const bw = W / N;
      const cy = H / 2;
      for (let i = 0; i < N; i++) {
        const amp =
          Math.sin(t * sp[i] + ph[i]) * 0.4 +
          Math.sin(t * sp[i] * 1.9 + ph[i] * 0.55) * 0.3 +
          Math.sin(t * 0.017 + i * 0.23) * 0.3;
        const bh = Math.max(3, Math.abs(amp) * cy * 0.78 + 4);
        const x = i * bw + bw * 0.2;
        const w = bw * 0.52;
        const a = 0.28 + Math.abs(amp) * 0.62;
        const g = ctx.createLinearGradient(0, cy - bh, 0, cy + bh);
        g.addColorStop(0, `rgba(0,240,181,${a * 0.25})`);
        g.addColorStop(0.5, `rgba(0,240,181,${a})`);
        g.addColorStop(1, `rgba(0,240,181,${a * 0.25})`);
        ctx.fillStyle = g;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, cy - bh, w, bh * 2, w / 2);
        else ctx.rect(x, cy - bh, w, bh * 2);
        ctx.fill();
      }
      t++;
      requestAnimationFrame(loop);
    };
    loop();
    return () => window.removeEventListener("resize", sz);
  };
  useEffect(() => {
    return setupWave(waveRef);
  }, []);
  useEffect(() => {
    return setupWave(waveRefDemo);
  }, []);

  // Typewriter
  useEffect(() => {
    const line = TYPEWRITER_LINES[typedLine];
    if (!line) return;
    if (!deleting && typedChar === line.length) {
      const id = setTimeout(() => setDeleting(true), 2600);
      return () => clearTimeout(id);
    }
    const delay = deleting ? 15 : 34;
    const id = setTimeout(() => {
      if (!deleting) {
        if (typedChar < line.length) setTypedChar((c) => c + 1);
      } else {
        if (typedChar > 0) {
          setTypedChar((c) => c - 1);
        } else {
          setDeleting(false);
          setTypedLine((li) => (li + 1) % TYPEWRITER_LINES.length);
        }
      }
    }, delay);
    return () => clearTimeout(id);
  }, [typedLine, typedChar, deleting]);

  // Scroll reveal (sections .reveal)
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    const run = () => document.querySelectorAll(".uwi-landing-new .reveal").forEach((el) => io.observe(el));
    run();
    return () => io.disconnect();
  }, []);

  // Smooth scroll pour ancres (nav)
  useEffect(() => {
    const root = document.querySelector(".uwi-landing-new");
    if (!root) return;
    const handleClick = (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a || !a.getAttribute("href") || a.getAttribute("href") === "#") return;
      const id = a.getAttribute("href").slice(1);
      const el = document.getElementById(id);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };
    root.addEventListener("click", handleClick);
    return () => root.removeEventListener("click", handleClick);
  }, []);

  const line = TYPEWRITER_LINES[typedLine] || "";
  const displayed = line.slice(0, typedChar);

  const faqLdJson = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  };

  return (
    <div className="uwi-landing-new">
      <Helmet>
        <script type="application/ld+json">{JSON.stringify(faqLdJson)}</script>
      </Helmet>
      <canvas id="bg" ref={bgRef} aria-hidden />
      <div className="wrap">
        <nav className="landing-nav">
          <Link to="/" className="logo header-logo">
            <div className="logo-mark header-logo-icon">
              <LogoStethoscope />
            </div>
            <div className="logo-copy">
              <span className="logo-name header-logo-name">UWi Medical</span>
              <span className="logo-tag header-logo-subtitle">IA Secrétariat</span>
            </div>
          </Link>
          <div className="nav-links">
            <a href="#assistants">Assistants</a>
            <a href="#metiers">Spécialités</a>
            <a href="#fonctionnalites">Fonctionnalités</a>
            <a href="#comment">Comment ça marche</a>
            <a href="#pricing">Tarifs</a>
            <a href="#securite">Sécurité</a>
            <a href="#faq">FAQ</a>
          </div>
          <div className="nav-actions header-right">
            <Link to="/login" className="nav-btn nav-btn--secondary header-link-connexion">Connexion</Link>
            <Link to="/creer-assistante?new=1" className="nav-btn header-cta">
              Créer mon assistant
            </Link>
            <button
              type="button"
              className={`burger-btn ${menuOpen ? "open" : ""}`}
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Menu"
              aria-expanded={menuOpen}
            >
              <span /><span /><span />
            </button>
          </div>
        </nav>

        {menuOpen && (
          <div className="mobile-dropdown">
            <Link to="/login" className="dd-item" onClick={() => setMenuOpen(false)}>
              <span className="dd-icon">👤</span>
              <div>
                <div className="dd-label">Connexion</div>
                <div className="dd-sub">Accéder à mon espace</div>
              </div>
            </Link>
            <a href="#pricing" className="dd-item" onClick={() => setMenuOpen(false)}>
              <span className="dd-icon">💳</span>
              <div>
                <div className="dd-label">Tarifs</div>
                <div className="dd-sub">À partir de 99€/mois</div>
              </div>
            </a>
            <a href="#fonctionnalites" className="dd-item" onClick={() => setMenuOpen(false)}>
              <span className="dd-icon">⚡</span>
              <div>
                <div className="dd-label">Fonctionnalités</div>
                <div className="dd-sub">Agenda, triage, RDV 24/7</div>
              </div>
            </a>
            <a href="#metiers" className="dd-item" onClick={() => setMenuOpen(false)}>
              <span className="dd-icon">🏥</span>
              <div>
                <div className="dd-label">Pour les médecins</div>
                <div className="dd-sub">Certifié HDS, RGPD</div>
              </div>
            </a>
            <div className="dd-sep" />
            <Link to="/creer-assistante?new=1" className="dd-cta" onClick={() => setMenuOpen(false)}>
              Créer mon assistant — gratuit 1 mois →
            </Link>
          </div>
        )}

        <section className="hero">
          <div className="hero-inner">
            <div className="hero-content">
              <div className="pill">
                <div className="pill-avs">
                  <div className="pav pav-1">👨‍⚕️</div>
                  <div className="pav pav-2">👩‍⚕️</div>
                  <div className="pav pav-3">🧑‍⚕️</div>
                </div>
                <span className="pill-lbl">500+ praticiens nous font confiance</span>
              </div>

              <h1 className="hero-h1">
                <span className="h1-w">Votre</span>
                <span className="h1-w">assistant IA</span>
                <span className="h1-t">répond et</span>
                <span className="h1-line-4"><span className="h1-t">prend</span><span className="h1-w"> vos RDV</span></span>
              </h1>

              <Link to="/creer-assistante?new=1" className="hero-cta-mobile">
                Créer mon assistant →
              </Link>

              <p className="subtitle">
                Pendant que vous soignez, UWi <strong>décroche, oriente vos patients et remplit votre agenda</strong> — sans aucune interruption de votre part.
              </p>

              <div className="stats">
                <div className="stat">
                  <span className="stat-v">HDS</span>
                  <span className="stat-l">Certifié santé</span>
                </div>
                <div className="stat">
                  <span className="stat-v">15min</span>
                  <span className="stat-l">Pour démarrer</span>
                </div>
                <div className="stat">
                  <span className="stat-v">24/7</span>
                  <span className="stat-l">Disponible</span>
                </div>
              </div>

              <div className="feats">
                <div className="feat">
                  <div className="feat-ico ico-teal">📅</div>
                  <span className="feat-name">Agenda en direct</span>
                </div>
                <div className="feat">
                  <div className="feat-ico ico-orange">🚨</div>
                  <span className="feat-name">Triage urgences</span>
                </div>
                <div className="feat">
                  <div className="feat-ico ico-blue">💊</div>
                  <span className="feat-name">Renouvellements</span>
                </div>
                <div className="feat">
                  <div className="feat-ico ico-violet">🔔</div>
                  <span className="feat-name">Rappels SMS</span>
                </div>
              </div>

              <div className="ctas">
                <Link to="/creer-assistante?new=1" className="btn-primary">
                  Essai gratuit 1 mois
                  <span className="btn-badge">Sans CB</span>
                </Link>
<a href="tel:+33652398414" className="btn-secondary">
              <PhoneOutlineIcon />
              Parler à un expert
            </a>
              </div>

              <div className="trust">
                <div className="trust-item">
                  <span className="trust-check">✓</span> Sans engagement
                </div>
                <div className="trust-dot" />
                <div className="trust-item">
                  <span className="trust-check">✓</span> RGPD · HDS
                </div>
                <div className="trust-dot" />
                <div className="trust-item">
                  <span className="trust-check">✓</span> Hébergé en France 🇫🇷
                </div>
              </div>
            </div>
            <div className="hero-visual">
              <div className="hero-demo">
                <p className="eyebrow">Testez en 60 secondes</p>
                <h2 className="hero-demo-title">Écoutez UWi<br />répondre à votre place</h2>
                <p className="demo-sub">
                  Appelez ce numéro et vivez l'expérience d'un de vos patients. <strong>Une conversation suffit</strong> pour comprendre ce que ça change.
                </p>

                <div className="demo-card">
                  <div className="live">
                    <span className="live-dot" />
                    IA disponible maintenant
                  </div>

                  <div className="wave-wrap">
                    <canvas id="wave" ref={waveRef} aria-hidden />
                  </div>

                  <div className="agent-row">
                    <div className="agent-av">UWi</div>
                    <div className="agent-info">
                      <span className="agent-name">Secrétaire IA — Cabinet Dr. Martin</span>
                      <span className="agent-status">Répond en moins de 2 secondes</span>
                    </div>
                    <div className="agent-online" />
                  </div>

                  <div className="bubble">
                    <span>{displayed}</span>
                    <span className="cursor" />
                  </div>

                  <div className="phone-block">
                    <p className="ph-label">Numéro de démonstration</p>
                    <p className="ph-number">09 39 24 05 75</p>
                    <p className="ph-sub">Gratuit · Appel public · Sans engagement</p>
                  </div>

                  <a href="tel:0939240575" className="btn-call">
                    <PhoneIcon />
                    Appeler la démo maintenant
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="section-divider">
          <span className="divider-label">Démo vocale</span>
        </div>

        <section className="demo reveal demo-section">
          <div className="demo-inner">
            <p className="eyebrow">Testez en 60 secondes</p>
            <h2>Écoutez UWi<br />répondre à votre place</h2>
            <p className="demo-sub">
              Appelez ce numéro et vivez l'expérience d'un de vos patients. <strong>Une conversation suffit</strong> pour comprendre ce que ça change.
            </p>

            <div className="demo-card">
              <div className="live">
                <span className="live-dot" />
                IA disponible maintenant
              </div>

              <div className="wave-wrap">
                <canvas id="wave-demo" ref={waveRefDemo} aria-hidden />
              </div>

              <div className="agent-row">
                <div className="agent-av">UWi</div>
                <div className="agent-info">
                  <span className="agent-name">Secrétaire IA — Cabinet Dr. Martin</span>
                  <span className="agent-status">Répond en moins de 2 secondes</span>
                </div>
                <div className="agent-online" />
              </div>

              <div className="bubble">
                <span>{displayed}</span>
                <span className="cursor" />
              </div>

              <div className="phone-block">
                <p className="ph-label">Numéro de démonstration</p>
                <p className="ph-number">09 39 24 05 75</p>
                <p className="ph-sub">Gratuit · Appel public · Sans engagement</p>
              </div>

              <a href="tel:0939240575" className="btn-call">
                <PhoneIcon />
                Appeler la démo maintenant
              </a>
            </div>
          </div>
        </section>

        <section id="metiers" className="landing-section reveal">
          <p className="section-eyebrow">Spécialités</p>
          <h2>Pour tous les cabinets</h2>
          <p className="section-sub">
            Médecins généralistes, kinés, dentistes, centres médicaux… <strong>UWi s'adapte à votre activité</strong> et à vos horaires.
          </p>
          <div className="landing-cards">
            <div className="landing-card">
              <h3>Médecine générale</h3>
              <p>RDV, renouvellements, triage des urgences. L'IA gère les appels pendant vos consultations.</p>
            </div>
            <div className="landing-card">
              <h3>Kinésithérapie & spécialistes</h3>
              <p>Prise de rendez-vous selon vos créneaux, rappels de présence, orientation des patients.</p>
            </div>
            <div className="landing-card">
              <h3>Centres & cliniques</h3>
              <p>Volume élevé, plusieurs praticiens. UWi qualifie et répartit sans saturer votre standard.</p>
            </div>
          </div>
        </section>

        <section id="fonctionnalites" className="landing-section reveal">
          <p className="section-eyebrow">Fonctionnalités</p>
          <h2>Un secrétariat IA complet</h2>
          <p className="section-sub">
            Prise de RDV en direct, gestion des urgences, renouvellements, rappels patients. <strong>Disponible 24/7</strong>.
          </p>
          <div className="landing-cards">
            <div className="landing-card">
              <h3>Agenda synchronisé</h3>
              <p>Créneaux en temps réel, plus de double réservation. Intégration avec votre outil actuel.</p>
            </div>
            <div className="landing-card">
              <h3>Triage & urgences</h3>
              <p>L'IA identifie les cas urgents et les signale. Les autres demandes sont planifiées proprement.</p>
            </div>
            <div className="landing-card">
              <h3>Rappels & confirmation</h3>
              <p>SMS de rappel pour limiter les absences. Confirmation des RDV à la prise.</p>
            </div>
          </div>
        </section>

        <section id="comment" className="landing-section reveal">
          <p className="section-eyebrow">Comment ça marche</p>
          <h2>En 3 étapes</h2>
          <p className="section-sub">
            Mise en route en quelques minutes. Aucune compétence technique requise.
          </p>
          <div className="steps-row">
            {STEPS.map((step, i) => (
              <div key={i} className="step-card">
                <div className="step-num">{step.num}</div>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Spotlight — hors wrap pour pleine largeur */}
      <div className="uwi-fullwidth-section">
        <Suspense fallback={<DeferredSectionFallback minHeight={720} />}>
          <AgentsSpotlight onSelectAgent={(a) => navigate("/creer-assistante?new=1", { state: a })} />
        </Suspense>
      </div>

      <div className="wrap">
        <section id="pricing" className="landing-section reveal pricing-section">
          <p className="section-eyebrow">Tarifs</p>
          <h2>Simple et prévisible</h2>
          <p className="pricing-intro">
            Un forfait fixe couvre votre usage courant. Au-delà, vous payez uniquement les minutes consommées — jamais plus que nécessaire.
          </p>
          <div className="pricing-grid">
            {PRICING_PLANS.map((plan, i) => (
              <div key={i} className={`pricing-card ${plan.featured ? "featured" : ""}`}>
                {plan.badge && (
                  <div className="pricing-card-badge">{plan.badge}</div>
                )}
                <h3>{plan.name}</h3>
                <div className="price">{plan.price}</div>
                <p className="pricing-card-desc">{plan.description}</p>
                <div className="pricing-minutes">
                  <span className="pricing-minutes-value">{plan.minutes}</span>
                  <span className="pricing-minutes-sub">{plan.minutesSub}</span>
                </div>
                <p className="pricing-over-usage">{plan.overUsage}</p>
                <ul className="pricing-features">
                  {plan.features.map((f, j) => (
                    <li key={j} className={f.included ? "included" : "excluded"}>
                      {f.included ? "✔" : "✘"} {f.label}
                    </li>
                  ))}
                </ul>
                <div className="pricing-cta">
                  <Link to="/creer-assistante?new=1" className="btn-primary">
                    {plan.cta}
                  </Link>
                </div>
              </div>
            ))}
          </div>
          <Suspense fallback={<DeferredSectionFallback minHeight={260} />}>
            <PricingSimulator />
          </Suspense>
          <div className="pricing-guarantee">
            <span className="pricing-guarantee-icon" aria-hidden>🛡️</span>
            <div>
              <strong>Meilleur prix garanti automatiquement</strong>
              <p>Si votre usage rend le forfait supérieur plus avantageux, nous vous basculons automatiquement. Vous ne payez jamais plus que nécessaire. Facturation à la seconde, sans arrondi.</p>
            </div>
          </div>
          <div className="pricing-usage-stats">
            <span className="pricing-usage-stats-icon" aria-hidden>💡</span>
            <div>
              <strong>La plupart des cabinets utilisent entre 350 et 900 minutes par mois.</strong>
              <p>Contrairement aux solutions facturées uniquement à la minute, notre forfait vous protège des mois chargés.</p>
            </div>
          </div>
        </section>

        <section id="securite" className="landing-section reveal">
          <p className="section-eyebrow">Sécurité & conformité</p>
          <h2>Vos données protégées</h2>
          <p className="section-sub">
            Hébergement santé, conformité RGPD et données en France. Nous prenons la confiance au sérieux.
          </p>
          <div className="security-grid">
            {SECURITY_ITEMS.map((item, i) => (
              <div key={i} className="security-card">
                <div className="sec-icon">{item.icon}</div>
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="faq" className="landing-section reveal">
          <p className="section-eyebrow">FAQ</p>
          <h2>Questions fréquentes</h2>
          <div className="landing-faq">
            {FAQ_ITEMS.map((item, i) => (
              <div key={i} className={`faq-item ${openFaq === i ? "open" : ""}`}>
                <button type="button" onClick={() => setOpenFaq(openFaq === i ? -1 : i)}>
                  {item.q}
                  <span className="faq-chevron">▼</span>
                </button>
                {openFaq === i && <p className="faq-answer">{item.a}</p>}
              </div>
            ))}
          </div>
        </section>

        <section className="landing-section reveal">
          <div className="landing-cta-block">
            <h2>Prêt à ne plus rater un appel ?</h2>
            <p>Créez votre assistant IA en quelques minutes. Essai gratuit, sans carte bancaire.</p>
            <Link to="/creer-assistante?new=1" className="btn-primary" style={{ display: "inline-flex", width: "auto", padding: "16px 28px" }}>
              Créer mon assistant
            </Link>
          </div>
        </section>
      </div>

      {/* Marquee — hors wrap pour pleine largeur */}
      <div className="uwi-fullwidth-section">
        <Suspense fallback={<DeferredSectionFallback minHeight={520} />}>
          <AgentsMarquee onSelectAgent={() => navigate("/creer-assistante?new=1")} />
        </Suspense>
      </div>

      <div className="wrap">
        {/* Sticky CTA — mobile uniquement */}
        <div className="sticky-cta">
          <Link to="/creer-assistante?new=1" className="sticky-cta-btn">
            Créer mon assistant — gratuit 1 mois →
          </Link>
        </div>

        <footer className="landing-footer">
          <Link to="/creer-assistante?new=1">Créer mon assistant</Link>
          <Link to="/checkout">Paiement</Link>
          <Link to="/contact">Contact</Link>
          <a href="tel:0939240575">09 39 24 05 75</a>
          <Link to="/cgv">CGV</Link>
          <Link to="/cgu">CGU</Link>
          <Link to="/mentions-legales">Mentions légales</Link>
          <span>© UWi Medical</span>
        </footer>
      </div>
    </div>
  );
}
