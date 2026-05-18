import { Link } from "react-router-dom";
import "./UwiMaquetteHeroBlock.css";
import { Play, Users, Star, Phone } from "lucide-react";

/**
 * Bloc d’accueil aligné sur la maquette fournie : hero + stats + témoignage + confiance.
 */
export default function UwiMaquetteHeroBlock({ onTrack }) {
  const track = (name) => onTrack?.(name);

  return (
    <section className="uwi-mfz" aria-label="Présentation UWi">
      <div className="uwi-mfz-hero">
        <div className="uwi-mfz-hero-inner">
          <div className="uwi-mfz-hero-copy">
            <span className="uwi-mfz-badge">
              <span className="uwi-mfz-badge-ico" aria-hidden>
                ✨
              </span>
              Assistant IA pour cabinets médicaux
            </span>
            <h1 className="uwi-mfz-title">
              <span className="uwi-mfz-title-line">UWi accueille</span>
              <span className="uwi-mfz-title-line">
                vos{" "}
                <span className="uwi-mfz-title-highlight">
                  patients
                  <svg className="uwi-mfz-title-underline" viewBox="0 0 280 24" fill="none" aria-hidden>
                    <path
                      d="M4 18C48 8 92 4 140 6c48 2 92 10 136 12"
                      stroke="url(#uwiMfzU2)"
                      strokeWidth="5"
                      strokeLinecap="round"
                    />
                    <defs>
                      <linearGradient id="uwiMfzU2" x1="0" y1="0" x2="280" y2="0" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#0d9488" />
                        <stop offset="1" stopColor="#14b8a6" />
                      </linearGradient>
                    </defs>
                  </svg>
                </span>
              </span>
              <span className="uwi-mfz-title-line">et gère votre</span>
              <span className="uwi-mfz-title-patient-wrap">
                <span className="uwi-mfz-title-patient">agenda</span>
                <svg className="uwi-mfz-title-underline" viewBox="0 0 280 24" fill="none" aria-hidden>
                  <path
                    d="M4 18C48 8 92 4 140 6c48 2 92 10 136 12"
                    stroke="url(#uwiMfzU)"
                    strokeWidth="5"
                    strokeLinecap="round"
                  />
                  <defs>
                    <linearGradient id="uwiMfzU" x1="0" y1="0" x2="280" y2="0" gradientUnits="userSpaceOnUse">
                      <stop stopColor="#0d9488" />
                      <stop offset="1" stopColor="#14b8a6" />
                    </linearGradient>
                  </defs>
                </svg>
              </span>
            </h1>
            <p className="uwi-mfz-kicker">
              Dès 99€/mois · Installation offerte · Essai gratuit 30 jours
            </p>
            <div className="uwi-mfz-ctas">
              <Link
                to="/creer-assistante?new=1"
                className="uwi-mfz-btn uwi-mfz-btn--primary"
                onClick={() => track("mfz_hero_demo_click")}
              >
                Demander une démo <span aria-hidden>→</span>
              </Link>
              <a href="#demo" className="uwi-mfz-btn uwi-mfz-btn--ghost" onClick={() => track("mfz_hero_how_click")}>
                <span className="uwi-mfz-play-ring" aria-hidden>
                  <Play size={14} fill="currentColor" strokeWidth={0} className="uwi-mfz-play-ico" />
                </span>
                Voir comment ça marche
              </a>
            </div>
          </div>
          <div className="uwi-mfz-hero-visual">
            <img
              src="/images/after-hero-right-exact.png"
              width={854}
              height={1024}
              alt="Standard médical augmenté : appel entrant, qualification vocale UWi et prise de rendez-vous confirmée"
              loading="eager"
              decoding="async"
              fetchpriority="high"
              className="uwi-mfz-hero-img"
            />
          </div>
        </div>
      </div>

      <div className="uwi-mfz-stats">
        <div className="uwi-mfz-stat-card">
          <span className="uwi-mfz-stat-ico" aria-hidden>
            <Users size={22} strokeWidth={2} />
          </span>
          <div>
            <div className="uwi-mfz-stat-val">
              +200 <span className="uwi-mfz-stat-lbl">cabinets équipés</span>
            </div>
            <p className="uwi-mfz-stat-sub">Partout en France</p>
          </div>
        </div>
        <div className="uwi-mfz-stat-card">
          <span className="uwi-mfz-stat-ico" aria-hidden>
            <Star size={22} strokeWidth={2} />
          </span>
          <div>
            <div className="uwi-mfz-stat-val">
              4,9/5 <span className="uwi-mfz-stat-lbl">satisfaction client</span>
            </div>
            <p className="uwi-mfz-stat-sub">Basé sur +150 avis</p>
          </div>
        </div>
        <div className="uwi-mfz-stat-card">
          <span className="uwi-mfz-stat-ico" aria-hidden>
            <Phone size={22} strokeWidth={2} />
          </span>
          <div>
            <div className="uwi-mfz-stat-val">
              0 <span className="uwi-mfz-stat-lbl">appel manqué</span>
            </div>
            <p className="uwi-mfz-stat-sub">Jamais un patient ne tombe sur la messagerie</p>
          </div>
        </div>
      </div>

      <div className="uwi-mfz-quote-wrap">
        <blockquote className="uwi-mfz-quote">
          <span className="uwi-mfz-quote-mark" aria-hidden>
            “
          </span>
          <p className="uwi-mfz-quote-txt">
            Avant UWi, on ratait énormément d&apos;appels aux heures de pointe. Aujourd&apos;hui, tout est géré
            automatiquement. On a gagné en confort et en chiffre d&apos;affaires.
          </p>
          <div className="uwi-mfz-quote-foot">
            <div className="uwi-mfz-quote-author">
              <span className="uwi-mfz-quote-av" aria-hidden>
                DM
              </span>
              <div>
                <strong>Dr Martin</strong>, Médecin généraliste
              </div>
            </div>
            <div className="uwi-mfz-quote-stars" aria-label="5 sur 5">
              {"★★★★★"}
            </div>
          </div>
        </blockquote>
      </div>

      <div className="uwi-mfz-trust">
        <div className="uwi-mfz-trust-item">
          <span className="uwi-mfz-trust-ico" aria-hidden>
            🛡️
          </span>
          <div>
            <strong>HDS</strong> <span className="uwi-mfz-trust-muted">Hébergeur de Données de Santé</span>
          </div>
        </div>
        <div className="uwi-mfz-trust-item">
          <span className="uwi-mfz-trust-ico" aria-hidden>
            🇪🇺
          </span>
          <div>
            <strong>RGPD</strong> <span className="uwi-mfz-trust-muted">Conformité européenne</span>
          </div>
        </div>
        <div className="uwi-mfz-trust-item">
          <span className="uwi-mfz-trust-ico" aria-hidden>
            🇫🇷
          </span>
          <div>
            <strong>Données hébergées en France</strong>{" "}
            <span className="uwi-mfz-trust-muted">Sécurité et souveraineté</span>
          </div>
        </div>
      </div>

      <div className="uwi-mfz-divider">
        <span>Démo vocale</span>
      </div>
    </section>
  );
}
