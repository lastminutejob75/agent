const TESTIMONIALS = [
  {
    quote:
      "Je récupère 1h30 par jour. Mes patients sont mieux pris en charge à 19h qu'à 9h, et mon agenda se remplit tout seul. C'est devenu indispensable.",
    name: 'Dr. Sophie Vasseur',
    role: 'Médecin généraliste',
    location: 'Lyon · Cabinet de 3 praticiens',
    initials: 'SV',
    accent: '#009CA4',
    metric: { value: '+27%', label: 'RDV captés / mois' },
  },
  {
    quote:
      "Avant, je perdais des nouveaux patients chaque semaine parce qu'on ne pouvait pas décrocher. Depuis UWi, zéro appel manqué — et zéro double réservation.",
    name: 'Dr. Karim Benali',
    role: 'Dentiste',
    location: 'Marseille · Cabinet libéral',
    initials: 'KB',
    accent: '#F5C842',
    featured: true,
    metric: { value: '0', label: 'appels manqués' },
  },
  {
    quote:
      "L'installation a pris une demi-journée. Aucune technique de mon côté. Trois mois après, je ne reviendrais plus en arrière — mes secrétaires non plus.",
    name: 'Dr. Élodie Marchand',
    role: 'Kinésithérapeute',
    location: 'Bordeaux · Cabinet de groupe',
    initials: 'EM',
    accent: '#5dd9e0',
    metric: { value: '−40%', label: 'no-shows' },
  },
];

function StarRow() {
  return (
    <div
      style={{
        display: 'inline-flex',
        gap: '2px',
        color: '#F5C842',
        fontSize: '14px',
        letterSpacing: '1px',
      }}
      aria-label="5 étoiles sur 5"
    >
      <span>★</span>
      <span>★</span>
      <span>★</span>
      <span>★</span>
      <span>★</span>
    </div>
  );
}

function TestimonialCard({ t }) {
  const isFeatured = t.featured;
  return (
    <article
      style={{
        position: 'relative',
        padding: '32px 28px 28px',
        background: isFeatured
          ? 'linear-gradient(160deg, #0A1F24 0%, #0d2a30 100%)'
          : '#FFFFFF',
        color: isFeatured ? '#FFFFFF' : '#0A1F24',
        borderRadius: '20px',
        border: isFeatured ? 'none' : '1.5px solid rgba(10,31,36,0.08)',
        boxShadow: isFeatured
          ? '0 24px 60px -16px rgba(10,31,36,0.45)'
          : '0 10px 32px -12px rgba(10,31,36,0.1)',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        overflow: 'hidden',
        transition: 'transform 0.3s ease, box-shadow 0.3s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
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
            : `linear-gradient(90deg, transparent, ${t.accent}, transparent)`,
        }}
      />

      {/* Quote mark décoratif */}
      <div
        style={{
          position: 'absolute',
          top: '20px',
          right: '24px',
          fontFamily: "'Syne', sans-serif",
          fontSize: '64px',
          fontWeight: 800,
          lineHeight: 1,
          color: isFeatured ? 'rgba(245,200,66,0.25)' : `${t.accent}25`,
          pointerEvents: 'none',
        }}
        aria-hidden="true"
      >
        “
      </div>

      <StarRow />

      <p
        style={{
          margin: 0,
          fontSize: '15.5px',
          lineHeight: 1.6,
          color: isFeatured ? 'rgba(255,255,255,0.92)' : 'rgba(10,31,36,0.85)',
          fontWeight: 400,
          position: 'relative',
          zIndex: 1,
          flex: 1,
        }}
      >
        « {t.quote} »
      </p>

      {/* Metric */}
      {t.metric && (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'baseline',
            gap: '8px',
            paddingTop: '14px',
            borderTop: isFeatured
              ? '1px solid rgba(255,255,255,0.12)'
              : '1px dashed rgba(10,31,36,0.12)',
          }}
        >
          <span
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: '24px',
              letterSpacing: '-0.02em',
              color: isFeatured ? '#F5C842' : t.accent,
              lineHeight: 1,
            }}
          >
            {t.metric.value}
          </span>
          <span
            style={{
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '11px',
              fontWeight: 600,
              color: isFeatured ? 'rgba(255,255,255,0.6)' : 'rgba(10,31,36,0.55)',
              letterSpacing: '0.5px',
            }}
          >
            {t.metric.label}
          </span>
        </div>
      )}

      {/* Author */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          paddingTop: '16px',
          borderTop: isFeatured
            ? '1px solid rgba(255,255,255,0.12)'
            : '1px solid rgba(10,31,36,0.08)',
        }}
      >
        <div
          style={{
            width: '46px',
            height: '46px',
            borderRadius: '50%',
            background: isFeatured
              ? 'linear-gradient(135deg, #F5C842 0%, #d4a82d 100%)'
              : `linear-gradient(135deg, ${t.accent} 0%, ${t.accent}cc 100%)`,
            display: 'grid',
            placeItems: 'center',
            color: isFeatured ? '#0A1F24' : '#FFFFFF',
            fontFamily: "'Syne', sans-serif",
            fontWeight: 800,
            fontSize: '15px',
            letterSpacing: '-0.01em',
            flexShrink: 0,
            boxShadow: isFeatured
              ? '0 4px 14px rgba(245,200,66,0.4)'
              : `0 4px 14px ${t.accent}40`,
          }}
        >
          {t.initials}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 700,
              fontSize: '15px',
              color: isFeatured ? '#FFFFFF' : '#0A1F24',
              letterSpacing: '-0.01em',
              marginBottom: '2px',
            }}
          >
            {t.name}
          </div>
          <div
            style={{
              fontSize: '12px',
              color: isFeatured ? 'rgba(255,255,255,0.6)' : 'rgba(10,31,36,0.55)',
              lineHeight: 1.4,
            }}
          >
            {t.role} · {t.location}
          </div>
        </div>
      </div>
    </article>
  );
}

export default function UwiTestimonials() {
  return (
    <section
      id="temoignages"
      style={{
        background: '#F5F9FA',
        padding: '120px 24px',
        position: 'relative',
        overflow: 'hidden',
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      {/* Décor */}
      <div
        style={{
          position: 'absolute',
          top: '10%',
          right: '-8%',
          width: '480px',
          height: '480px',
          background: 'radial-gradient(circle, rgba(0,156,164,0.10) 0%, transparent 65%)',
          pointerEvents: 'none',
          filter: 'blur(40px)',
        }}
      />

      <div style={{ maxWidth: '1180px', margin: '0 auto', position: 'relative' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '60px', maxWidth: '720px', margin: '0 auto 60px' }}>
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
              marginBottom: '24px',
            }}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="#F5C842"
              stroke="#F5C842"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 15 8.5 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 9 8.5 12 2" />
            </svg>
            Ils utilisent UWi au quotidien
          </div>

          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(32px, 4.5vw, 52px)',
              lineHeight: 1.05,
              margin: '0 0 18px',
              letterSpacing: '-0.03em',
              color: '#0A1F24',
            }}
          >
            Des médecins qui ont retrouvé{' '}
            <span style={{ color: '#009CA4' }}>leur temps.</span>
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: '17px',
              color: 'rgba(10,31,36,0.65)',
              lineHeight: 1.6,
            }}
          >
            +200 cabinets nous font confiance — généralistes, spécialistes, dentistes, kinés.
            Voici ce qu'ils en disent.
          </p>
        </div>

        {/* Grid */}
        <div
          className="uwi-testimonials-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '22px',
            alignItems: 'stretch',
          }}
        >
          {TESTIMONIALS.map((t, idx) => (
            <TestimonialCard key={idx} t={t} />
          ))}
        </div>

        {/* Trust strip */}
        <div
          className="uwi-testimonials-trust"
          style={{
            marginTop: '56px',
            padding: '24px 32px',
            background: '#FFFFFF',
            border: '1.5px solid rgba(10,31,36,0.08)',
            borderRadius: '16px',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '32px 48px',
            boxShadow: '0 8px 24px -12px rgba(10,31,36,0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <StarRow />
            <span style={{ fontWeight: 700, fontSize: '15px', color: '#0A1F24' }}>4.9 / 5</span>
            <span style={{ fontSize: '13px', color: 'rgba(10,31,36,0.55)' }}>· 200+ cabinets</span>
          </div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13px',
              color: 'rgba(10,31,36,0.7)',
              fontWeight: 500,
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#009CA4"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 22s-8-4.5-8-11.8A5.5 5.5 0 0 1 12 5a5.5 5.5 0 0 1 8 5.2C20 17.5 12 22 12 22z" />
            </svg>
            Hébergement HDS · Données chiffrées
          </div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13px',
              color: 'rgba(10,31,36,0.7)',
              fontWeight: 500,
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#009CA4"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            Conforme RGPD · 100% France
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .uwi-testimonials-grid {
            grid-template-columns: 1fr !important;
          }
        }
        @media (max-width: 640px) {
          #temoignages {
            padding: 80px 16px !important;
          }
          .uwi-testimonials-trust {
            padding: 20px 18px !important;
            gap: 18px 24px !important;
          }
        }
      `}</style>
    </section>
  );
}
