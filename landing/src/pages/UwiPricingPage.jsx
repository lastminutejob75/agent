import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 99,
    includedMinutes: 400,
    overagePrice: 0.19,
    description: 'Pour un cabinet qui démarre ou teste UWi.',
    tagline: '≈ 100 appels patients traités automatiquement',
    features: [
      { label: 'Réponse téléphonique 24/7', included: true },
      { label: 'Prise de rendez-vous automatique', included: true },
      { label: 'Rappels SMS patients', included: true },
      { label: 'Intégration Doctolib', included: true },
      { label: 'Triage urgences avancé', included: false },
      { label: "Renouvellements d'ordonnances", included: false },
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    price: 149,
    includedMinutes: 800,
    overagePrice: 0.17,
    description: 'Le meilleur choix pour 80% des cabinets.',
    tagline: '≈ 200 appels patients traités automatiquement',
    popular: true,
    badge: 'Le choix de 80% des cabinets',
    features: [
      { label: 'Tout le plan Starter', included: true },
      { label: 'Triage des urgences médicales', included: true },
      { label: "Renouvellements d'ordonnances", included: true },
      { label: 'Rapports hebdomadaires', included: true },
      { label: 'WhatsApp Business', included: false },
      { label: 'Support prioritaire 7j/7', included: false },
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 199,
    includedMinutes: 1200,
    overagePrice: 0.15,
    description: 'Pour les cabinets chargés qui veulent tout déléguer.',
    tagline: '≈ 300 appels patients traités automatiquement',
    features: [
      { label: 'Tout le plan Growth', included: true },
      { label: 'WhatsApp Business inclus', included: true },
      { label: 'Support prioritaire 7j/7', included: true },
      { label: 'Onboarding personnalisé', included: true },
      { label: 'Rapport mensuel détaillé', included: true },
    ],
  },
];

const SIGNUP_PATH = '/creer-assistante?new=1';

// Panier moyen estimé par RDV récupéré (consultation médicale type)
const AVG_REVENUE_PER_CALL = 25;
// Hypothèse : 30% des appels seraient perdus sans répondeur intelligent
const RECOVERED_RATE = 0.3;

// Calcule le VRAI meilleur plan (forfait + dépassement) pour un volume donné.
function getBestPlan(minutes) {
  return PLANS.map((plan) => {
    const overage = Math.max(0, minutes - plan.includedMinutes);
    const overageCost = overage * plan.overagePrice;
    return {
      plan,
      overageMinutes: overage,
      overageCost,
      total: plan.price + overageCost,
    };
  }).sort((a, b) => a.total - b.total)[0];
}

function calculateTotal(minutes) {
  return getBestPlan(minutes);
}

function Simulator() {
  const [minutes, setMinutes] = useState(400);

  const { plan, overageMinutes, overageCost, total } = useMemo(
    () => calculateTotal(minutes),
    [minutes]
  );

  const approxCalls = Math.round(minutes / 4);
  const recoveredCalls = Math.round(approxCalls * RECOVERED_RATE);
  const recoveredRevenue = recoveredCalls * AVG_REVENUE_PER_CALL;
  const roiMultiplier = total > 0 ? Math.max(0, recoveredRevenue / total).toFixed(1) : '0';

  return (
    <div
      style={{
        background: '#FFFFFF',
        border: '1.5px solid rgba(0,156,164,0.15)',
        borderRadius: '24px',
        padding: '40px',
        boxShadow:
          '0 20px 60px -20px rgba(0,156,164,0.2), 0 4px 20px -10px rgba(10,31,36,0.08)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '-100px',
          right: '-100px',
          width: '300px',
          height: '300px',
          background: 'radial-gradient(circle, rgba(0,156,164,0.1) 0%, transparent 60%)',
          pointerEvents: 'none',
        }}
      />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ marginBottom: '28px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 14px',
              background: 'rgba(0,156,164,0.1)',
              border: '1px solid rgba(0,156,164,0.25)',
              borderRadius: '30px',
              fontSize: '11px',
              fontWeight: 700,
              color: '#007F86',
              letterSpacing: '1.8px',
              textTransform: 'uppercase',
              marginBottom: '16px',
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
              <rect x="4" y="2" width="16" height="20" rx="2" />
              <line x1="8" y1="6" x2="16" y2="6" />
              <line x1="8" y1="10" x2="16" y2="10" />
              <line x1="8" y1="14" x2="10" y2="14" />
              <line x1="14" y1="14" x2="16" y2="14" />
            </svg>
            Simulateur
          </div>
          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(24px, 3vw, 32px)',
              color: '#0A1F24',
              margin: '0 0 8px 0',
              letterSpacing: '-0.02em',
              lineHeight: 1.15,
            }}
          >
            Estimez votre facture
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: '15px',
              color: 'rgba(10,31,36,0.65)',
              lineHeight: 1.5,
            }}
          >
            Déplacez le curseur selon votre volume mensuel estimé.
          </p>
        </div>

        <div style={{ marginBottom: '32px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginBottom: '12px',
            }}
          >
            <label
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: 'rgba(10,31,36,0.55)',
                letterSpacing: '1.5px',
                textTransform: 'uppercase',
              }}
            >
              Minutes d'appels / mois
            </label>
            <div
              style={{
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: '18px',
                color: '#009CA4',
                letterSpacing: '-0.01em',
              }}
            >
              {minutes} min
            </div>
          </div>

          <input
            type="range"
            min="100"
            max="2000"
            step="50"
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
            className="uwi-range"
            style={{
              width: '100%',
              height: '6px',
              borderRadius: '3px',
              background: `linear-gradient(to right, #009CA4 0%, #009CA4 ${
                ((minutes - 100) / 1900) * 100
              }%, rgba(10,31,36,0.1) ${
                ((minutes - 100) / 1900) * 100
              }%, rgba(10,31,36,0.1) 100%)`,
              appearance: 'none',
              WebkitAppearance: 'none',
              outline: 'none',
              cursor: 'pointer',
            }}
          />

          <div
            className="uwi-range-ticks"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: '10px',
              fontSize: '11px',
              color: 'rgba(10,31,36,0.5)',
              fontFamily: "'SF Mono', Menlo, monospace",
              letterSpacing: '0.3px',
            }}
          >
            <span>100</span>
            <span>400 · ~100 appels</span>
            <span>800 · ~200 appels</span>
            <span>1200 · ~300 appels</span>
            <span>2000</span>
          </div>
        </div>

        <div
          style={{
            background:
              'linear-gradient(135deg, rgba(0,156,164,0.05) 0%, rgba(77,216,222,0.08) 100%)',
            border: '1.5px solid rgba(0,156,164,0.2)',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '20px',
          }}
        >
          <div
            style={{
              fontSize: '13px',
              color: 'rgba(10,31,36,0.7)',
              marginBottom: '16px',
              lineHeight: 1.5,
            }}
          >
            Plan recommandé :{' '}
            <strong
              style={{
                color: '#009CA4',
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: '15px',
              }}
            >
              {plan.name}
            </strong>{' '}
            — {minutes} min/mois ≈ {approxCalls} appels
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              gap: '16px',
              alignItems: 'center',
              padding: '20px 0',
              borderTop: '1px solid rgba(10,31,36,0.08)',
              borderBottom: '1px solid rgba(10,31,36,0.08)',
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color: 'rgba(10,31,36,0.5)',
                  letterSpacing: '1.5px',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                Forfait
              </div>
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: '28px',
                  color: '#0A1F24',
                  letterSpacing: '-0.02em',
                  lineHeight: 1,
                }}
              >
                {plan.price}€
              </div>
            </div>

            <div
              style={{
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: '24px',
                color: 'rgba(10,31,36,0.4)',
              }}
            >
              {overageMinutes > 0 ? '+' : '='}
            </div>

            {overageMinutes > 0 ? (
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    color: 'rgba(10,31,36,0.5)',
                    letterSpacing: '1.5px',
                    textTransform: 'uppercase',
                    marginBottom: '6px',
                  }}
                >
                  Dépassement
                </div>
                <div
                  style={{
                    fontFamily: "'Syne', sans-serif",
                    fontWeight: 800,
                    fontSize: '28px',
                    color: '#0A1F24',
                    letterSpacing: '-0.02em',
                    lineHeight: 1,
                  }}
                >
                  {overageCost.toFixed(2)}€
                </div>
                <div
                  style={{
                    fontSize: '10px',
                    color: 'rgba(10,31,36,0.5)',
                    marginTop: '4px',
                    fontFamily: "'SF Mono', Menlo, monospace",
                  }}
                >
                  {overageMinutes} min × {plan.overagePrice}€
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    color: 'rgba(10,31,36,0.5)',
                    letterSpacing: '1.5px',
                    textTransform: 'uppercase',
                    marginBottom: '6px',
                  }}
                >
                  Total estimé
                </div>
                <div
                  style={{
                    fontFamily: "'Syne', sans-serif",
                    fontWeight: 800,
                    fontSize: '28px',
                    background: 'linear-gradient(135deg, #009CA4 0%, #4DD8DE 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                    letterSpacing: '-0.02em',
                    lineHeight: 1,
                  }}
                >
                  {total.toFixed(0)}€
                </div>
              </div>
            )}
          </div>

          {overageMinutes > 0 && (
            <div
              style={{
                textAlign: 'center',
                marginTop: '20px',
                paddingTop: '16px',
              }}
            >
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color: 'rgba(10,31,36,0.5)',
                  letterSpacing: '1.5px',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                Total estimé
              </div>
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: 'clamp(36px, 4vw, 48px)',
                  background: 'linear-gradient(135deg, #009CA4 0%, #4DD8DE 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                  letterSpacing: '-0.025em',
                  lineHeight: 1,
                }}
              >
                {total.toFixed(2)}€
              </div>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              marginTop: '20px',
              fontSize: '13px',
              fontWeight: 600,
              color: '#007F86',
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#007F86"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Bascule automatique au meilleur prix appliquée
          </div>
        </div>

        {/* ROI block — combien le médecin récupère grâce à UWi */}
        <div
          style={{
            position: 'relative',
            background: 'linear-gradient(135deg, #0A1F24 0%, #0d2a30 100%)',
            border: '1.5px solid rgba(245,200,66,0.4)',
            borderRadius: '16px',
            padding: '22px 24px',
            marginBottom: '20px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '-50%',
              right: '-10%',
              width: '260px',
              height: '260px',
              background: 'radial-gradient(circle, rgba(245,200,66,0.18) 0%, transparent 65%)',
              pointerEvents: 'none',
            }}
          />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              position: 'relative',
              zIndex: 1,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: "'SF Mono', Menlo, monospace",
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#F5C842',
                  letterSpacing: '1.8px',
                  textTransform: 'uppercase',
                  marginBottom: '8px',
                }}
              >
                💰 Revenu récupéré / mois
              </div>
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: 'clamp(28px, 4vw, 36px)',
                  letterSpacing: '-0.025em',
                  lineHeight: 1,
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: '6px',
                }}
              >
                <span
                  style={{
                    background: 'linear-gradient(135deg, #F5C842 0%, #FFE08A 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  +{recoveredRevenue.toLocaleString('fr-FR')}€
                </span>
              </div>
              <div
                style={{
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.6)',
                  marginTop: '6px',
                  fontFamily: "'SF Mono', Menlo, monospace",
                  letterSpacing: '0.3px',
                }}
              >
                ≈ {recoveredCalls} appels sauvés × {AVG_REVENUE_PER_CALL}€ /consultation
              </div>
            </div>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: '4px',
              }}
            >
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: '32px',
                  color: '#4DFFD4',
                  letterSpacing: '-0.02em',
                  lineHeight: 1,
                }}
              >
                ×{roiMultiplier}
              </div>
              <div
                style={{
                  fontFamily: "'SF Mono', Menlo, monospace",
                  fontSize: '9px',
                  fontWeight: 700,
                  color: 'rgba(255,255,255,0.7)',
                  letterSpacing: '1.5px',
                  textTransform: 'uppercase',
                }}
              >
                Retour sur investissement
              </div>
            </div>
          </div>
        </div>

        <Link
          to={SIGNUP_PATH}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            padding: '18px 24px',
            background: 'linear-gradient(135deg, #009CA4 0%, #007F86 100%)',
            color: '#FFFFFF',
            textDecoration: 'none',
            borderRadius: '14px',
            fontFamily: "'Syne', sans-serif",
            fontWeight: 800,
            fontSize: '16px',
            letterSpacing: '-0.01em',
            transition: 'all 0.25s ease',
            boxShadow: '0 10px 25px -5px rgba(0,156,164,0.4)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 15px 35px -5px rgba(0,156,164,0.5)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(0,156,164,0.4)';
          }}
        >
          Automatiser mon standard
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </Link>

        <div
          style={{
            textAlign: 'center',
            marginTop: '16px',
            fontSize: '12px',
            color: 'rgba(10,31,36,0.55)',
            fontFamily: "'SF Mono', Menlo, monospace",
            letterSpacing: '0.3px',
          }}
        >
          Essai gratuit 1 mois · Sans CB · Sans engagement
        </div>
      </div>
    </div>
  );
}

function PlanCard({ plan }) {
  const isPopular = plan.popular;

  return (
    <div
      style={{
        position: 'relative',
        padding: isPopular ? '40px 32px 32px 32px' : '32px',
        background: isPopular
          ? 'linear-gradient(135deg, #009CA4 0%, #007F86 100%)'
          : '#FFFFFF',
        color: isPopular ? '#FFFFFF' : '#0A1F24',
        borderRadius: '24px',
        border: isPopular ? 'none' : '1.5px solid rgba(0,156,164,0.15)',
        boxShadow: isPopular
          ? '0 25px 60px -15px rgba(0,156,164,0.45), 0 10px 25px -8px rgba(10,31,36,0.15)'
          : '0 8px 30px -12px rgba(10,31,36,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        overflow: 'hidden',
        transition: 'all 0.3s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {isPopular && (
        <div
          style={{
            position: 'absolute',
            top: '-20%',
            right: '-20%',
            width: '400px',
            height: '400px',
            background: 'radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 60%)',
            pointerEvents: 'none',
          }}
        />
      )}

      {isPopular && (
        <div
          style={{
            position: 'absolute',
            top: '-12px',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '6px 16px',
            background: '#FFFFFF',
            color: '#007F86',
            fontSize: '10px',
            fontWeight: 800,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            borderRadius: '30px',
            boxShadow: '0 4px 12px rgba(0,156,164,0.25)',
            whiteSpace: 'nowrap',
            zIndex: 2,
          }}
        >
          ★ {plan.badge || 'Le plus populaire'}
        </div>
      )}

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div
          style={{
            fontFamily: "'SF Mono', Menlo, monospace",
            fontSize: '12px',
            fontWeight: 700,
            color: isPopular ? 'rgba(255,255,255,0.85)' : '#007F86',
            letterSpacing: '2.5px',
            textTransform: 'uppercase',
            marginBottom: '16px',
          }}
        >
          {plan.name}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '6px',
            marginBottom: '12px',
          }}
        >
          <span
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(44px, 5vw, 56px)',
              color: isPopular ? '#FFFFFF' : '#0A1F24',
              letterSpacing: '-0.03em',
              lineHeight: 1,
            }}
          >
            {plan.price}€
          </span>
          <span
            style={{
              fontSize: '14px',
              fontWeight: 600,
              color: isPopular ? 'rgba(255,255,255,0.75)' : 'rgba(10,31,36,0.55)',
            }}
          >
            / mois
          </span>
        </div>

        <p
          style={{
            margin: '0 0 20px 0',
            fontSize: '14px',
            color: isPopular ? 'rgba(255,255,255,0.85)' : 'rgba(10,31,36,0.65)',
            lineHeight: 1.5,
          }}
        >
          {plan.description}
        </p>

        <div
          style={{
            padding: '16px 18px',
            background: isPopular ? 'rgba(255,255,255,0.12)' : 'rgba(0,156,164,0.06)',
            backdropFilter: isPopular ? 'blur(10px)' : 'none',
            WebkitBackdropFilter: isPopular ? 'blur(10px)' : 'none',
            border: isPopular ? '1px solid rgba(255,255,255,0.2)' : '1px solid rgba(0,156,164,0.15)',
            borderRadius: '12px',
            marginBottom: '16px',
          }}
        >
          <div
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: '18px',
              color: isPopular ? '#FFFFFF' : '#0A1F24',
              letterSpacing: '-0.01em',
              marginBottom: '4px',
            }}
          >
            {plan.includedMinutes} minutes / mois
          </div>
          <div
            style={{
              fontSize: '12px',
              color: isPopular ? 'rgba(255,255,255,0.75)' : 'rgba(10,31,36,0.6)',
              lineHeight: 1.4,
            }}
          >
            {plan.tagline}
          </div>
        </div>

        <div
          style={{
            fontSize: '12px',
            color: isPopular ? 'rgba(255,255,255,0.8)' : 'rgba(10,31,36,0.65)',
            lineHeight: 1.5,
            marginBottom: '24px',
            fontFamily: "'SF Mono', Menlo, monospace",
          }}
        >
          Au-delà : {plan.overagePrice}€ / min
          {plan.id !== 'pro' && ' — bascule auto si plus avantageux'}
          {plan.id === 'pro' && ' — tarif le plus bas'}
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            marginBottom: '28px',
          }}
        >
          {plan.features.map((feature, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                fontSize: '14px',
                color: feature.included
                  ? isPopular
                    ? 'rgba(255,255,255,0.95)'
                    : '#0A1F24'
                  : isPopular
                  ? 'rgba(255,255,255,0.4)'
                  : 'rgba(10,31,36,0.35)',
                lineHeight: 1.4,
              }}
            >
              {feature.included ? (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={isPopular ? '#FFFFFF' : '#009CA4'}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ flexShrink: 0, marginTop: '2px' }}
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={isPopular ? 'rgba(255,255,255,0.4)' : 'rgba(10,31,36,0.35)'}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ flexShrink: 0, marginTop: '2px' }}
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              )}
              <span>{feature.label}</span>
            </div>
          ))}
        </div>

        <Link
          to={SIGNUP_PATH}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            padding: '16px 24px',
            background: isPopular ? '#FFFFFF' : 'transparent',
            color: isPopular ? '#007F86' : '#009CA4',
            textDecoration: 'none',
            borderRadius: '12px',
            fontFamily: "'Syne', sans-serif",
            fontWeight: 800,
            fontSize: '14px',
            letterSpacing: '-0.01em',
            border: isPopular ? 'none' : '2px solid #009CA4',
            transition: 'all 0.25s ease',
            boxShadow: isPopular ? '0 8px 20px -5px rgba(10,31,36,0.15)' : 'none',
          }}
          onMouseEnter={(e) => {
            if (isPopular) {
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 12px 25px -5px rgba(10,31,36,0.25)';
            } else {
              e.currentTarget.style.background = '#009CA4';
              e.currentTarget.style.color = '#FFFFFF';
            }
          }}
          onMouseLeave={(e) => {
            if (isPopular) {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 8px 20px -5px rgba(10,31,36,0.15)';
            } else {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#009CA4';
            }
          }}
        >
          Automatiser mon standard
        </Link>
      </div>
    </div>
  );
}

function TrustLine() {
  const items = [
    'Installation complète incluse',
    'Support réactif 7j/7',
    'Essai gratuit 1 mois',
    'Sans CB requise',
    'Sans engagement',
    'Bascule auto meilleur prix',
  ];

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '24px',
        padding: '20px 24px',
        fontSize: '13px',
        color: 'rgba(10,31,36,0.65)',
        fontWeight: 500,
      }}
    >
      {items.map((item, idx) => (
        <div
          key={idx}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#009CA4"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

function TopNav() {
  const navLinks = [
    { to: '/pricing', label: 'Tarifs', active: true },
    { to: '/securite', label: 'Sécurité' },
    { to: '/#faq', label: 'FAQ' },
    { to: '/login', label: 'Connexion' },
  ];

  return (
    <nav
      className="uwi-pricing-nav"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '24px',
        padding: '14px 32px',
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
        borderBottom: '1px solid rgba(10,31,36,0.08)',
        boxShadow: '0 4px 20px -10px rgba(10,31,36,0.08)',
      }}
    >
      <Link
        to="/"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '10px',
          textDecoration: 'none',
          color: '#0A1F24',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'linear-gradient(145deg, #009CA4 0%, #007F86 100%)',
            display: 'grid',
            placeItems: 'center',
            boxShadow: '0 4px 14px rgba(0,156,164,0.35)',
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#fff"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4.5 6.5a4 4 0 0 0 8 0V4a.5.5 0 0 0-1 0v2.5a3 3 0 0 1-6 0V4a.5.5 0 0 0-1 0v2.5z" />
            <path d="M8.5 10.5V14a5.5 5.5 0 0 0 11 0v-1.5" />
            <circle cx="19.5" cy="12" r="1.5" />
          </svg>
        </span>
        <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: '16px',
              letterSpacing: '-0.02em',
            }}
          >
            UWi Medical
          </span>
          <span
            style={{
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '9px',
              fontWeight: 700,
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              opacity: 0.55,
              marginTop: '2px',
            }}
          >
            Standard intelligent
          </span>
        </span>
      </Link>

      {/* Liens desktop centraux */}
      <ul
        className="uwi-pricing-nav-links"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {navLinks.map((link) => (
          <li key={link.to}>
            <Link
              to={link.to}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '8px 14px',
                fontFamily: "'Inter', sans-serif",
                fontSize: '14px',
                fontWeight: link.active ? 700 : 600,
                color: link.active ? '#009CA4' : '#0A1F24',
                textDecoration: 'none',
                borderRadius: '8px',
                background: link.active ? 'rgba(0,156,164,0.10)' : 'transparent',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (!link.active) {
                  e.currentTarget.style.background = 'rgba(10,31,36,0.05)';
                  e.currentTarget.style.color = '#009CA4';
                }
              }}
              onMouseLeave={(e) => {
                if (!link.active) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#0A1F24';
                }
              }}
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          flexShrink: 0,
        }}
      >
        <Link
          to={SIGNUP_PATH}
          className="uwi-pricing-nav-cta"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '11px 20px',
            fontFamily: "'Syne', sans-serif",
            fontSize: '13px',
            fontWeight: 800,
            letterSpacing: '-0.01em',
            color: '#FFFFFF',
            textDecoration: 'none',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #009CA4 0%, #007F86 100%)',
            boxShadow: '0 6px 18px -4px rgba(0,156,164,0.45)',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 10px 22px -4px rgba(0,156,164,0.55)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 6px 18px -4px rgba(0,156,164,0.45)';
          }}
        >
          Créer mon assistant →
        </Link>
      </div>
    </nav>
  );
}

export default function UwiPricingPage() {
  return (
    <main
      style={{
        background: 'linear-gradient(180deg, #F5F9FA 0%, #E8F5F6 30%, #F5F9FA 70%, #F5F9FA 100%)',
        minHeight: '100vh',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: '#0A1F24',
        position: 'relative',
      }}
    >
      <TopNav />

      <div
        style={{
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: '5%',
            left: '-10%',
            width: '600px',
            height: '600px',
            background: 'radial-gradient(circle, rgba(0,156,164,0.2) 0%, transparent 60%)',
            pointerEvents: 'none',
            filter: 'blur(40px)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: '40%',
            right: '-10%',
            width: '500px',
            height: '500px',
            background: 'radial-gradient(circle, rgba(77,216,222,0.18) 0%, transparent 60%)',
            pointerEvents: 'none',
            filter: 'blur(40px)',
          }}
        />

      <div
        className="uwi-pricing-container"
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '56px 24px 120px 24px',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div
          style={{
            fontFamily: "'SF Mono', Menlo, monospace",
            fontSize: '11px',
            fontWeight: 600,
            color: 'rgba(10,31,36,0.55)',
            marginBottom: '32px',
            letterSpacing: '1px',
            textTransform: 'uppercase',
          }}
        >
          <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
            UWi
          </Link>
          <span style={{ margin: '0 10px', opacity: 0.5 }}>/</span>
          <span>Tarifs</span>
        </div>

        <div
          style={{
            textAlign: 'center',
            maxWidth: '780px',
            margin: '0 auto 56px auto',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 18px',
              background: 'rgba(0,156,164,0.12)',
              border: '1.5px solid rgba(0,156,164,0.3)',
              borderRadius: '30px',
              fontSize: '12px',
              fontWeight: 700,
              color: '#007F86',
              letterSpacing: '1.8px',
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
            Tarifs
          </div>

          <h1
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(40px, 5.5vw, 64px)',
              lineHeight: 1.02,
              margin: '0 0 20px 0',
              letterSpacing: '-0.03em',
              color: '#0A1F24',
            }}
          >
            Ne perdez plus aucun{' '}
            <span style={{ position: 'relative', display: 'inline-block', color: '#009CA4' }}>
              patient au téléphone.
              <svg
                viewBox="0 0 300 12"
                preserveAspectRatio="none"
                style={{
                  position: 'absolute',
                  bottom: '-6px',
                  left: 0,
                  width: '100%',
                  height: '12px',
                  zIndex: -1,
                }}
              >
                <path
                  d="M 0 6 Q 75 0 150 6 T 300 6"
                  stroke="#009CA4"
                  strokeWidth="3"
                  fill="none"
                  opacity="0.5"
                />
              </svg>
            </span>
          </h1>

          <p
            style={{
              margin: 0,
              fontSize: '18px',
              color: 'rgba(10,31,36,0.7)',
              lineHeight: 1.6,
              fontWeight: 500,
            }}
          >
            UWi répond, filtre et remplit votre agenda automatiquement. Un forfait fixe couvre votre
            usage, et vous ne payez jamais plus que nécessaire.
          </p>
        </div>

        <div
          style={{
            maxWidth: '720px',
            margin: '0 auto 80px auto',
          }}
        >
          <Simulator />
        </div>

        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '16px',
              marginBottom: '24px',
            }}
          >
            <div style={{ width: '60px', height: '1px', background: 'rgba(10,31,36,0.15)' }} />
            <div
              style={{
                fontFamily: "'SF Mono', Menlo, monospace",
                fontSize: '11px',
                fontWeight: 700,
                color: 'rgba(10,31,36,0.6)',
                letterSpacing: '2px',
                textTransform: 'uppercase',
              }}
            >
              Les forfaits en détail
            </div>
            <div style={{ width: '60px', height: '1px', background: 'rgba(10,31,36,0.15)' }} />
          </div>

          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(28px, 3.5vw, 40px)',
              color: '#0A1F24',
              margin: 0,
              letterSpacing: '-0.025em',
              lineHeight: 1.1,
            }}
          >
            Trois forfaits. <span style={{ color: '#009CA4' }}>Aucun compromis.</span>
          </h2>
        </div>

        <div
          className="uwi-plans-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '24px',
            marginBottom: '40px',
          }}
        >
          {PLANS.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </div>

        <TrustLine />

        <div
          style={{
            marginTop: '80px',
            padding: '40px',
            background: 'linear-gradient(135deg, #009CA4 0%, #007F86 100%)',
            color: '#FFFFFF',
            borderRadius: '24px',
            boxShadow: '0 20px 60px -20px rgba(0,156,164,0.4)',
            textAlign: 'center',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '-50%',
              right: '-10%',
              width: '500px',
              height: '500px',
              background: 'radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 60%)',
              pointerEvents: 'none',
            }}
          />
          <div style={{ position: 'relative', zIndex: 1 }}>
            <h3
              style={{
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: 'clamp(24px, 3vw, 36px)',
                margin: '0 0 16px 0',
                letterSpacing: '-0.02em',
                lineHeight: 1.2,
                color: '#FFFFFF',
              }}
            >
              Chaque appel manqué = un patient perdu.{' '}
              <span style={{ opacity: 0.85 }}>UWi vous les rend.</span>
            </h3>
            <p
              style={{
                margin: '0 auto 28px auto',
                fontSize: '16px',
                color: 'rgba(255,255,255,0.88)',
                lineHeight: 1.65,
                maxWidth: '580px',
              }}
            >
              Installation complète prise en charge par notre équipe. Vous êtes opérationnel en 24h,
              sans rien faire — et vous payez le bon prix, automatiquement.
            </p>
            <Link
              to={SIGNUP_PATH}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '10px',
                padding: '16px 32px',
                background: '#FFFFFF',
                color: '#007F86',
                textDecoration: 'none',
                borderRadius: '12px',
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: '15px',
                letterSpacing: '-0.01em',
                transition: 'all 0.25s ease',
                boxShadow: '0 10px 25px -5px rgba(10,31,36,0.2)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 15px 35px -5px rgba(10,31,36,0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 10px 25px -5px rgba(10,31,36,0.2)';
              }}
            >
              Automatiser mon standard
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </Link>
          </div>
        </div>
      </div>
      </div>

      <style>{`
        .uwi-range::-webkit-slider-thumb {
          appearance: none;
          -webkit-appearance: none;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: #FFFFFF;
          border: 3px solid #009CA4;
          cursor: pointer;
          box-shadow: 0 4px 10px rgba(0,156,164,0.3);
          transition: all 0.2s ease;
        }
        .uwi-range::-webkit-slider-thumb:hover {
          transform: scale(1.15);
          box-shadow: 0 6px 15px rgba(0,156,164,0.4);
        }
        .uwi-range::-moz-range-thumb {
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: #FFFFFF;
          border: 3px solid #009CA4;
          cursor: pointer;
          box-shadow: 0 4px 10px rgba(0,156,164,0.3);
        }
        @media (max-width: 900px) {
          .uwi-plans-grid {
            grid-template-columns: 1fr !important;
          }
        }
        @media (max-width: 900px) {
          .uwi-pricing-nav-links {
            display: none !important;
          }
        }
        @media (max-width: 640px) {
          .uwi-pricing-nav {
            padding: 10px 16px !important;
            gap: 12px !important;
          }
          .uwi-pricing-nav-cta {
            padding: 9px 14px !important;
            font-size: 12px !important;
          }
          .uwi-pricing-container {
            padding: 36px 16px 80px 16px !important;
          }
          .uwi-range-ticks {
            display: none !important;
          }
        }
      `}</style>
    </main>
  );
}
