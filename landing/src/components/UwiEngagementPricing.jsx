import { Link } from 'react-router-dom';
import {
  Tag,
  Star,
  Zap,
  TrendingUp,
  Target,
  CheckCircle2,
  ShieldCheck,
  Clock,
  BarChart3,
  ArrowUpRight,
  Check,
} from 'lucide-react';

const PRICING_BILLING_CARD = {
  variant: 'billingMerge',
  imgSrc: '/images/uwi-pricing-facturation-forfait.png',
  alt: "Facturation juste, forfait ajusté : si votre volume augmente, UWi vous oriente vers le forfait le plus avantageux. Précision à la seconde, ajustement avec forfait recommandé.",
};

// =============================================================================
// MAQUETTE HTML/CSS — "Tarification ajustée — Toujours le forfait le plus juste"
// (remplace l'ancien PNG basse résolution /images/uwi-pricing-engagement-usage-reel.png)
// =============================================================================

const MOCK_USAGE = { current: 928, included: 1300 }; // minutes consommées / forfait

function PricingTarificationMockup() {
  const TEAL = '#009CA4';
  const TEAL_DARK = '#007F86';
  const INK = '#0A1F24';
  const MUTED = 'rgba(10,31,36,0.6)';
  const YELLOW = '#F5C842';
  const YELLOW_50 = '#FFF7CD';
  const usagePct = Math.min(100, Math.round((MOCK_USAGE.current / MOCK_USAGE.included) * 100));

  return (
    <div
      role="img"
      aria-label="Maquette tarification ajustée : usage 928 minutes, forfait actuel Starter 99 euros, forfait recommandé Growth 149 euros, garantie de toujours payer le forfait le plus avantageux."
      style={{
        background: '#FFFFFF',
        border: `2px solid ${TEAL_DARK}`,
        borderRadius: 22,
        padding: '24px 22px 22px',
        boxShadow: '0 24px 56px -22px rgba(10,31,36,0.22)',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: INK,
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
      }}
    >
      {/* Header eyebrow */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: YELLOW,
            color: '#5b4500',
            padding: '5px 10px',
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.08em',
          }}
        >
          <span style={{ fontWeight: 900 }}>01</span>
          <Tag size={11} strokeWidth={2.5} />
          TARIFICATION AJUSTÉE
        </span>
      </div>

      {/* Title + body */}
      <div>
        <h3
          style={{
            margin: 0,
            fontFamily: "'Syne', sans-serif",
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            lineHeight: 1.2,
          }}
        >
          Toujours le forfait le plus juste
        </h3>
        <p
          style={{
            margin: '8px 0 0',
            fontSize: 13.5,
            color: MUTED,
            lineHeight: 1.55,
          }}
        >
          Dès que vous dépassez votre forfait, UWi vous oriente vers l&apos;offre la plus
          adaptée à votre volume d&apos;appels.
        </p>
      </div>

      {/* Barre de progression "Usage ce mois-ci" */}
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 8,
            fontSize: 12.5,
          }}
        >
          <span style={{ fontWeight: 600, color: MUTED }}>Usage ce mois-ci</span>
          <span style={{ fontWeight: 800, color: INK }}>
            {MOCK_USAGE.current} min
          </span>
        </div>
        <div
          style={{
            position: 'relative',
            height: 8,
            background: '#EEF3F4',
            borderRadius: 999,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              bottom: 0,
              width: `${usagePct}%`,
              background: `linear-gradient(90deg, ${TEAL} 0%, ${TEAL_DARK} 100%)`,
              borderRadius: 999,
              transition: 'width 0.6s ease',
            }}
          />
        </div>
      </div>

      {/* 2 cartes : Forfait actuel / Forfait recommandé */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
        }}
      >
        {/* Forfait actuel */}
        <div
          style={{
            background: '#F8FAFB',
            border: '1.5px solid rgba(10,31,36,0.08)',
            borderRadius: 14,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <span style={{ fontSize: 10.5, color: MUTED, fontWeight: 600 }}>
            Forfait actuel
          </span>
          <span style={{ fontSize: 16, fontWeight: 800 }}>Starter</span>
          <span
            style={{
              fontSize: 17,
              fontWeight: 800,
              color: TEAL_DARK,
              fontFamily: "'Syne', sans-serif",
            }}
          >
            99 € <span style={{ fontSize: 11, fontWeight: 600, color: MUTED }}>/ mois</span>
          </span>
          <span
            style={{
              marginTop: 4,
              paddingTop: 6,
              borderTop: '1px dashed rgba(10,31,36,0.08)',
              fontSize: 10.5,
              color: MUTED,
            }}
          >
            adapté pour démarrer
          </span>
        </div>
        {/* Forfait recommandé */}
        <div
          style={{
            position: 'relative',
            background: YELLOW_50,
            border: `1.5px solid ${YELLOW}`,
            borderRadius: 14,
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <span
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              borderRadius: '50%',
              background: YELLOW,
              color: '#5b4500',
            }}
          >
            <Star size={12} strokeWidth={2.5} fill="#5b4500" />
          </span>
          <span style={{ fontSize: 10.5, color: '#7a5b00', fontWeight: 700 }}>
            Forfait recommandé
          </span>
          <span style={{ fontSize: 16, fontWeight: 800 }}>Growth</span>
          <span
            style={{
              fontSize: 17,
              fontWeight: 800,
              color: TEAL_DARK,
              fontFamily: "'Syne', sans-serif",
            }}
          >
            149 € <span style={{ fontSize: 11, fontWeight: 600, color: MUTED }}>/ mois</span>
          </span>
          <span
            style={{
              marginTop: 4,
              paddingTop: 6,
              borderTop: '1px dashed rgba(122, 91, 0, 0.18)',
              fontSize: 10.5,
              color: '#7a5b00',
            }}
          >
            plus adapté à ce volume
          </span>
        </div>
      </div>

      {/* Bandeau garantie */}
      <div
        style={{
          background: 'rgba(0,156,164,0.08)',
          border: '1.5px solid rgba(0,156,164,0.25)',
          borderRadius: 12,
          padding: '12px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 12,
          color: INK,
          fontWeight: 600,
          lineHeight: 1.4,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 32,
            height: 32,
            borderRadius: 8,
            background: '#fff',
            color: TEAL_DARK,
            border: '1px solid rgba(0,156,164,0.3)',
            flexShrink: 0,
          }}
        >
          <ShieldCheck size={16} strokeWidth={2.2} />
        </span>
        Vous gardez toujours le forfait le plus avantageux selon votre usage.
      </div>

      {/* 3 mini-features icônes */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 8,
        }}
      >
        {[
          { Ico: TrendingUp, label: 'Usage suivi' },
          { Ico: Target, label: 'Recommandation\u00a0claire' },
          { Ico: CheckCircle2, label: 'Aucun forfait\nsurdimensionné' },
        ].map(({ Ico, label }) => (
          <div
            key={label}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              padding: '10px 6px',
              borderRadius: 10,
              background: '#F8FAFB',
              border: '1px solid rgba(10,31,36,0.06)',
              fontSize: 10.5,
              fontWeight: 600,
              textAlign: 'center',
              color: INK,
              lineHeight: 1.3,
              whiteSpace: 'pre-line',
            }}
          >
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: 8,
                background: 'rgba(0,156,164,0.1)',
                color: TEAL_DARK,
              }}
            >
              <Ico size={14} strokeWidth={2.2} />
            </span>
            {label}
          </div>
        ))}
      </div>

      {/* Footer note discrète */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: 4,
          borderTop: '1px solid rgba(10,31,36,0.06)',
          fontSize: 10,
          color: MUTED,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          fontWeight: 700,
        }}
      >
        <span>Réajustement</span>
        <span style={{ color: TEAL_DARK, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Zap size={11} strokeWidth={2.5} />
          Temps réel
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// MAQUETTE HTML/CSS — "Facturation juste, forfait ajusté"
// (remplace l'ancien PNG /images/uwi-pricing-facturation-forfait.png)
// =============================================================================

function PricingFacturationMockup() {
  const TEAL = '#009CA4';
  const TEAL_DARK = '#007F86';
  const INK = '#0A1F24';
  const MUTED = 'rgba(10,31,36,0.6)';
  const YELLOW = '#F5C842';
  const ORANGE = '#F97316';

  return (
    <div
      role="img"
      aria-label="Maquette facturation juste : si votre volume augmente, UWi vous oriente vers le forfait le plus avantageux. Précision à la seconde, ajustement avec forfait recommandé."
      style={{
        background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FBFB 100%)',
        borderRadius: 18,
        padding: '24px 22px',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: INK,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        textAlign: 'center',
      }}
    >
      {/* Header eyebrow */}
      <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: YELLOW,
            color: '#5b4500',
            padding: '5px 10px',
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.08em',
          }}
        >
          <span style={{ fontWeight: 900 }}>02</span>
          <Tag size={11} strokeWidth={2.5} />
          PRICING
        </span>
      </div>

      {/* Visuel central : horloge + petit badge check + flèche orange */}
      <div
        aria-hidden
        style={{
          position: 'relative',
          margin: '4px auto 0',
          width: 200,
          height: 130,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Grande horloge */}
        <svg width="130" height="130" viewBox="0 0 130 130" fill="none">
          {/* Cercle externe */}
          <circle
            cx="65"
            cy="65"
            r="58"
            fill="#FFFDF5"
            stroke={INK}
            strokeWidth="4.5"
          />
          {/* Marqueurs heures */}
          {[0, 90, 180, 270].map((angle) => {
            const rad = (angle - 90) * (Math.PI / 180);
            const x1 = 65 + Math.cos(rad) * 50;
            const y1 = 65 + Math.sin(rad) * 50;
            const x2 = 65 + Math.cos(rad) * 44;
            const y2 = 65 + Math.sin(rad) * 44;
            return (
              <line
                key={angle}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={INK}
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            );
          })}
          {/* Aiguille des minutes (pointant vers 1, jolie diagonale) */}
          <line
            x1="65"
            y1="65"
            x2="92"
            y2="42"
            stroke={INK}
            strokeWidth="3.5"
            strokeLinecap="round"
          />
          {/* Aiguille des heures */}
          <line
            x1="65"
            y1="65"
            x2="65"
            y2="32"
            stroke={INK}
            strokeWidth="4.5"
            strokeLinecap="round"
          />
          {/* Petit jaune au centre (pivot) */}
          <circle cx="65" cy="65" r="5" fill={YELLOW} stroke={INK} strokeWidth="2" />
        </svg>

        {/* Badge check (petite carte à droite) */}
        <div
          style={{
            position: 'absolute',
            top: 16,
            right: 0,
            background: '#FFFFFF',
            border: `2px solid ${INK}`,
            borderRadius: 10,
            padding: 4,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            width: 56,
            boxShadow: '3px 3px 0 rgba(10,31,36,0.1)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              borderRadius: 6,
              background: TEAL,
              color: '#fff',
              alignSelf: 'flex-end',
            }}
          >
            <Check size={14} strokeWidth={3} />
          </div>
          <div
            style={{
              height: 3,
              background: '#E5EAEB',
              borderRadius: 2,
              width: '90%',
            }}
          />
          <div
            style={{
              height: 3,
              background: '#E5EAEB',
              borderRadius: 2,
              width: '60%',
            }}
          />
        </div>

        {/* Flèche orange ascendante (ajustement) */}
        <div
          style={{
            position: 'absolute',
            bottom: 18,
            left: 70,
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: ORANGE,
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 6px 18px rgba(249,115,22,0.45)',
          }}
        >
          <ArrowUpRight size={20} strokeWidth={2.6} />
        </div>
      </div>

      {/* Title */}
      <div>
        <h3
          style={{
            margin: 0,
            fontFamily: "'Syne', sans-serif",
            fontSize: 24,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            lineHeight: 1.15,
          }}
        >
          Facturation juste,
          <br />
          <span style={{ color: '#7a5b00' }}>forfait ajusté</span>
        </h3>
        <p
          style={{
            margin: '12px auto 0',
            maxWidth: 280,
            fontSize: 14,
            color: MUTED,
            lineHeight: 1.55,
            fontWeight: 600,
          }}
        >
          Si votre volume augmente, UWi vous oriente vers le forfait le plus avantageux.
        </p>
      </div>

      {/* Bottom : 2 mini-cards Précision / Ajustement */}
      <div
        style={{
          background: '#F2F8F8',
          borderRadius: 14,
          padding: 12,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
        }}
      >
        {[
          { Ico: Clock, label: 'Précision', value: 'À la seconde', color: TEAL_DARK },
          {
            Ico: BarChart3,
            label: 'Ajustement',
            value: 'Forfait recommandé',
            color: '#7a5b00',
          },
        ].map(({ Ico, label, value, color }) => (
          <div
            key={label}
            style={{
              background: '#FFFFFF',
              borderRadius: 10,
              padding: '12px 10px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              border: '1px solid rgba(10,31,36,0.05)',
            }}
          >
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 32,
                height: 32,
                borderRadius: 8,
                background: color === TEAL_DARK ? 'rgba(0,156,164,0.1)' : 'rgba(245,200,66,0.18)',
                color,
              }}
            >
              <Ico size={16} strokeWidth={2.2} />
            </span>
            <span style={{ fontSize: 11, color: MUTED, fontWeight: 600 }}>{label}</span>
            <span style={{ fontSize: 13, fontWeight: 800, color, lineHeight: 1.2, textAlign: 'center' }}>
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function trackClick(name) {
  if (typeof window === 'undefined') return;
  const payload = { event: name, source: 'landing_pricing_engagement' };
  window.dataLayer?.push(payload);
  if (typeof window.gtag === 'function') {
    window.gtag('event', name, { source: 'landing_pricing_engagement' });
  }
}

const PILLARS = [
  {
    chapter: '03',
    title: 'Aucune action requise',
    body: 'Tout est optimisé automatiquement, en continu. Vous ne touchez à rien.',
    items: [
      'Forfait recommandé en temps réel selon votre usage',
      'Ajustement à la seconde près, jamais surfacturé',
      'Aucune intervention de votre part — UWi vous prévient',
    ],
    spec: { label: 'Réajustement', value: 'Temps réel' },
    accent: '#4DD8DE',
    featured: false,
    icon: (
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 12a9 9 0 1 1-9-9" />
        <polyline points="21 3 21 9 15 9" />
      </svg>
    ),
  },
];

export default function UwiEngagementPricing() {
  return (
    <section
      id="pricing"
      style={{
        background: 'linear-gradient(180deg, #F5F9FA 0%, #E8F5F6 50%, #F5F9FA 100%)',
        padding: '120px 24px 140px 24px',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: '#0A1F24',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Grille technique en fond */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'linear-gradient(rgba(10,31,36,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(10,31,36,0.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          pointerEvents: 'none',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 40%, #000 30%, transparent 100%)',
          WebkitMaskImage:
            'radial-gradient(ellipse 80% 60% at 50% 40%, #000 30%, transparent 100%)',
        }}
      />

      {/* Orbes lumineuses teal en fond */}
      <div
        style={{
          position: 'absolute',
          top: '5%',
          left: '-12%',
          width: '560px',
          height: '560px',
          background: 'radial-gradient(circle, rgba(0,156,164,0.32) 0%, transparent 60%)',
          pointerEvents: 'none',
          filter: 'blur(50px)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '5%',
          right: '-12%',
          width: '640px',
          height: '640px',
          background: 'radial-gradient(circle, rgba(245,200,66,0.18) 0%, transparent 60%)',
          pointerEvents: 'none',
          filter: 'blur(50px)',
        }}
      />

      <div style={{ maxWidth: '1180px', margin: '0 auto', position: 'relative' }}>
        {/* Header */}
        <div
          style={{
            textAlign: 'center',
            marginBottom: '72px',
            maxWidth: '820px',
            marginLeft: 'auto',
            marginRight: 'auto',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 18px',
              background: 'rgba(0,156,164,0.1)',
              border: '1.5px solid rgba(0,156,164,0.28)',
              borderRadius: '100px',
              fontSize: '12px',
              fontWeight: 700,
              color: '#007F86',
              letterSpacing: '1.6px',
              textTransform: 'uppercase',
              marginBottom: '28px',
            }}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#007F86"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L15 8L22 9L17 14L18 21L12 18L6 21L7 14L2 9L9 8L12 2Z" />
            </svg>
            Notre engagement pricing
          </div>

          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(36px, 4.5vw, 56px)',
              lineHeight: 1.05,
              margin: '0 0 20px 0',
              letterSpacing: '-0.03em',
              color: '#0A1F24',
            }}
          >
            Une tarification qui suit votre{' '}
            <span style={{ color: '#007F86' }}>usage réel.</span>
          </h2>

          <p
            style={{
              margin: 0,
              fontSize: '18px',
              color: 'rgba(10,31,36,0.7)',
              lineHeight: 1.6,
              fontWeight: 500,
            }}
          >
            Vous démarrez avec le forfait adapté à votre volume d&apos;appels. Si votre usage évolue,
            UWi vous aide à choisir l&apos;offre la plus avantageuse.
          </p>
        </div>

        <figure
          className="uwi-pricing-hero-mock"
          style={{
            margin: '0 auto 56px',
            maxWidth: '420px',
            padding: '0 8px',
            position: 'relative',
          }}
        >
          <PricingTarificationMockup />
          <figcaption
            style={{
              marginTop: '12px',
              textAlign: 'center',
              fontSize: '13px',
              fontWeight: 500,
              color: 'rgba(10,31,36,0.55)',
            }}
          >
            Tarification ajustée, forfaits Starter / Growth et suivi d&apos;usage.
          </figcaption>
        </figure>

        {/* Cards */}
        <div
          className="uwi-pricing-cards"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
            gap: '20px',
            marginBottom: '72px',
            alignItems: 'stretch',
          }}
        >
          <div
            key="billing-merge"
            className="uwi-pricing-card uwi-pricing-card--billing-merge"
            style={{
              position: 'relative',
              padding: '32px 24px',
              borderRadius: '20px',
              overflow: 'hidden',
              transition: 'transform 0.3s ease, box-shadow 0.3s ease',
              background: 'linear-gradient(180deg, #f7fbfb 0%, #ffffff 100%)',
              border: '2px solid #0A1F24',
              boxShadow: '8px 8px 0 rgba(10, 31, 36, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-6px)';
              e.currentTarget.style.boxShadow = '12px 12px 0 rgba(0, 156, 164, 0.25)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '8px 8px 0 rgba(10, 31, 36, 0.12)';
            }}
          >
            <div style={{ width: '100%', maxWidth: 380 }}>
              <PricingFacturationMockup />
            </div>
          </div>

          {PILLARS.map((pillar, idx) => {
            const isFeatured = pillar.featured;
            return (
              <div
                key={idx}
                className="uwi-pricing-card"
                style={{
                  position: 'relative',
                  padding: '36px 28px 32px',
                  borderRadius: '20px',
                  overflow: 'hidden',
                  transition: 'transform 0.3s ease, box-shadow 0.3s ease',
                  background: isFeatured
                    ? 'linear-gradient(135deg, #009CA4 0%, #007F86 60%, #005f64 100%)'
                    : '#FFFFFF',
                  color: isFeatured ? '#FFFFFF' : '#0A1F24',
                  border: isFeatured ? 'none' : `1.5px solid rgba(10,31,36,0.08)`,
                  boxShadow: isFeatured
                    ? '0 24px 60px -16px rgba(0,156,164,0.55), 0 8px 20px -8px rgba(10,31,36,0.18), inset 0 1px 0 rgba(255,255,255,0.15)'
                    : '0 10px 32px -12px rgba(10,31,36,0.1)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '18px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-6px)';
                  e.currentTarget.style.boxShadow = isFeatured
                    ? '0 32px 70px -16px rgba(0,156,164,0.65), 0 14px 28px -8px rgba(10,31,36,0.22), inset 0 1px 0 rgba(255,255,255,0.2)'
                    : `0 20px 48px -12px ${pillar.accent}40`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = isFeatured
                    ? '0 24px 60px -16px rgba(0,156,164,0.55), 0 8px 20px -8px rgba(10,31,36,0.18), inset 0 1px 0 rgba(255,255,255,0.15)'
                    : '0 10px 32px -12px rgba(10,31,36,0.1)';
                }}
              >
                {/* Top accent bar */}
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '4px',
                    background: isFeatured
                      ? 'linear-gradient(90deg, #4DFFD4, #F5C842, #4DFFD4)'
                      : `linear-gradient(90deg, transparent, ${pillar.accent}, transparent)`,
                  }}
                />

                {/* Glow décoratif */}
                {isFeatured && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '-30%',
                      right: '-20%',
                      width: '320px',
                      height: '320px',
                      background:
                        'radial-gradient(circle, rgba(255,255,255,0.22) 0%, transparent 60%)',
                      pointerEvents: 'none',
                    }}
                  />
                )}
                {!isFeatured && (
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '-40%',
                      right: '-30%',
                      width: '260px',
                      height: '260px',
                      background: `radial-gradient(circle, ${pillar.accent}14 0%, transparent 65%)`,
                      pointerEvents: 'none',
                    }}
                  />
                )}

                {/* Header row : chapter + badge */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    position: 'relative',
                    zIndex: 1,
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'SF Mono', Menlo, monospace",
                      fontSize: '11px',
                      fontWeight: 700,
                      letterSpacing: '2px',
                      color: isFeatured ? 'rgba(255,255,255,0.7)' : pillar.accent,
                    }}
                  >
                    — {pillar.chapter}
                  </span>

                  {isFeatured && (
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '7px',
                        padding: '5px 11px',
                        background: 'rgba(255,255,255,0.16)',
                        backdropFilter: 'blur(10px)',
                        WebkitBackdropFilter: 'blur(10px)',
                        border: '1px solid rgba(255,255,255,0.28)',
                        borderRadius: '30px',
                        fontFamily: "'SF Mono', Menlo, monospace",
                        fontSize: '9px',
                        fontWeight: 700,
                        color: '#FFFFFF',
                        letterSpacing: '1.6px',
                        textTransform: 'uppercase',
                      }}
                    >
                      <span
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: '#4DFFD4',
                          boxShadow: '0 0 10px rgba(77,255,212,0.95)',
                          animation: 'uwi-pricing-pulse 1.6s ease-in-out infinite',
                        }}
                      />
                      Live
                    </div>
                  )}
                </div>

                {/* Icon */}
                <div
                  style={{
                    position: 'relative',
                    width: '64px',
                    height: '64px',
                    borderRadius: '16px',
                    background: isFeatured
                      ? 'rgba(255,255,255,0.15)'
                      : `linear-gradient(135deg, ${pillar.accent}1a 0%, ${pillar.accent}33 100%)`,
                    backdropFilter: isFeatured ? 'blur(10px)' : 'none',
                    WebkitBackdropFilter: isFeatured ? 'blur(10px)' : 'none',
                    border: isFeatured
                      ? '1.5px solid rgba(255,255,255,0.32)'
                      : `1.5px solid ${pillar.accent}55`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: isFeatured ? '#FFFFFF' : pillar.accent === '#F5C842' ? '#B8860B' : pillar.accent,
                    zIndex: 1,
                    boxShadow: isFeatured
                      ? 'inset 0 0 24px rgba(255,255,255,0.08)'
                      : `0 6px 18px -8px ${pillar.accent}66`,
                  }}
                >
                  {pillar.icon}
                </div>

                {/* Title */}
                <h3
                  style={{
                    fontFamily: "'Syne', sans-serif",
                    fontWeight: 800,
                    fontSize: '22px',
                    margin: 0,
                    letterSpacing: '-0.02em',
                    lineHeight: 1.2,
                    color: isFeatured ? '#FFFFFF' : '#0A1F24',
                    position: 'relative',
                    zIndex: 1,
                  }}
                >
                  {pillar.title}
                </h3>

                {/* Body */}
                <p
                  style={{
                    margin: 0,
                    fontSize: '14.5px',
                    color: isFeatured ? 'rgba(255,255,255,0.88)' : 'rgba(10,31,36,0.72)',
                    lineHeight: 1.6,
                    position: 'relative',
                    zIndex: 1,
                  }}
                >
                  {pillar.body}
                </p>

                {/* Items list */}
                {pillar.items && (
                  <ul
                    style={{
                      listStyle: 'none',
                      padding: 0,
                      margin: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      position: 'relative',
                      zIndex: 1,
                      flex: 1,
                    }}
                  >
                    {pillar.items.map((it) => (
                      <li
                        key={it}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          fontSize: '13.5px',
                          fontWeight: 500,
                          lineHeight: 1.5,
                          color: isFeatured ? 'rgba(255,255,255,0.92)' : '#0A1F24',
                        }}
                      >
                        <span
                          aria-hidden
                          style={{
                            flexShrink: 0,
                            width: '20px',
                            height: '20px',
                            borderRadius: '50%',
                            background: isFeatured
                              ? 'rgba(77,255,212,0.2)'
                              : `${pillar.accent}26`,
                            color: isFeatured ? '#4DFFD4' : '#0A5C62',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginTop: '1px',
                          }}
                        >
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        </span>
                        <span>{it}</span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* Spec line */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '10px',
                    paddingTop: '16px',
                    marginTop: '4px',
                    borderTop: isFeatured
                      ? '1px solid rgba(255,255,255,0.18)'
                      : '1px dashed rgba(10,31,36,0.12)',
                    position: 'relative',
                    zIndex: 1,
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'SF Mono', Menlo, monospace",
                      fontSize: '10px',
                      fontWeight: 700,
                      letterSpacing: '1.4px',
                      textTransform: 'uppercase',
                      color: isFeatured ? 'rgba(255,255,255,0.65)' : 'rgba(10,31,36,0.5)',
                    }}
                  >
                    {pillar.spec.label}
                  </span>
                  <span
                    style={{
                      fontFamily: "'Syne', sans-serif",
                      fontWeight: 800,
                      fontSize: '20px',
                      letterSpacing: '-0.02em',
                      color: isFeatured ? '#4DFFD4' : pillar.accent === '#F5C842' ? '#B8860B' : pillar.accent,
                      lineHeight: 1,
                    }}
                  >
                    {pillar.spec.value}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Tagline + lien vers la page tarifs (CTA création déjà présent ailleurs sur la landing) */}
        <div
          style={{
            textAlign: 'center',
            marginTop: '72px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '16px',
          }}
        >
          <p
            style={{
              margin: 0,
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(24px, 3vw, 32px)',
              color: '#0A1F24',
              letterSpacing: '-0.02em',
              lineHeight: 1.2,
              maxWidth: '680px',
            }}
          >
            Vous payez le bon prix.{' '}
            <span style={{ position: 'relative', display: 'inline-block', color: '#009CA4' }}>
              Automatiquement.
              <svg
                viewBox="0 0 200 10"
                preserveAspectRatio="none"
                style={{
                  position: 'absolute',
                  bottom: '-4px',
                  left: 0,
                  width: '100%',
                  height: '10px',
                  zIndex: -1,
                }}
              >
                <path
                  d="M 0 5 Q 50 0 100 5 T 200 5"
                  stroke="#009CA4"
                  strokeWidth="3"
                  fill="none"
                  opacity="0.4"
                />
              </svg>
            </span>
          </p>

          <Link
            to="/pricing"
            onClick={() => trackClick('pricing_block_link_page_tarifs')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '14px',
              fontWeight: 600,
              color: '#009CA4',
              textDecoration: 'none',
              borderBottom: '1px solid rgba(0, 156, 164, 0.4)',
              paddingBottom: '2px',
              lineHeight: 1.4,
            }}
          >
            Voir la page tarifs complète
            <ArrowUpRight size={15} strokeWidth={2.25} aria-hidden />
          </Link>
        </div>
      </div>

      <style>{`
        @keyframes uwi-pricing-pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.3); opacity: 0.7; }
        }
        @media (max-width: 900px) {
          .uwi-pricing-hero-mock {
            margin-bottom: 40px !important;
          }
          .uwi-pricing-cards {
            grid-template-columns: 1fr !important;
          }
        }
        @media (max-width: 640px) {
          #pricing { padding: 80px 16px 96px 16px !important; }
          .uwi-pricing-card { padding: 28px 22px 26px !important; }
        }
      `}</style>
    </section>
  );
}
