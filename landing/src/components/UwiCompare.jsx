import { Link } from 'react-router-dom';
import {
  Phone,
  Headphones,
  Bot,
  Star,
  DollarSign,
  Clock,
  PhoneCall,
  Calendar,
  RefreshCw,
  AlertTriangle,
  MessageSquare,
  Rocket,
  Unlock,
  Check,
  X,
} from 'lucide-react';

function trackClick(name) {
  if (typeof window === 'undefined') return;
  const payload = { event: name, source: 'landing_compare' };
  window.dataLayer?.push(payload);
  if (typeof window.gtag === 'function') {
    window.gtag('event', name, { source: 'landing_compare' });
  }
}

// Couleurs partagées
const TEAL = '#009CA4';
const TEAL_DARK = '#007F86';
const INK = '#0A1F24';
const MUTED = 'rgba(10,31,36,0.55)';
const ROSE = '#E5484D';
const YELLOW_50 = '#FFF7CD';
const YELLOW_300 = '#F5C842';
const TEAL_50 = '#E6F4F5';

/** Lignes du comparatif. value type : 'yes' | 'no' | string (texte court). */
const ROWS = [
  {
    label: 'Coût mensuel',
    Icon: DollarSign,
    iconBg: YELLOW_300,
    highlight: true,
    values: [
      { type: 'text', label: '0 €' },
      { type: 'text', label: '600 – 1 200 €' },
      { type: 'text', label: '99 – 199 €', strong: true },
    ],
  },
  {
    label: 'Disponible 24/7',
    Icon: Clock,
    values: [{ type: 'no' }, { type: 'no' }, { type: 'yes' }],
  },
  {
    label: 'Zéro appel manqué',
    Icon: PhoneCall,
    values: [{ type: 'no' }, { type: 'text', label: 'partiel', muted: true }, { type: 'yes' }],
  },
  {
    label: 'RDV automatique',
    Icon: Calendar,
    values: [{ type: 'no' }, { type: 'yes' }, { type: 'yes' }],
  },
  {
    label: 'Sync agenda live',
    Icon: RefreshCw,
    values: [{ type: 'no' }, { type: 'no' }, { type: 'yes' }],
  },
  {
    label: 'Triage urgences',
    Icon: AlertTriangle,
    values: [
      { type: 'no' },
      { type: 'text', label: 'manuel', muted: true },
      { type: 'badge', label: 'IA' },
    ],
  },
  {
    label: 'Rappels SMS',
    Icon: MessageSquare,
    values: [
      { type: 'no' },
      { type: 'text', label: 'option', muted: true },
      { type: 'yes' },
    ],
  },
  {
    label: 'Mise en service',
    Icon: Rocket,
    values: [
      { type: 'text', label: 'Immédiat' },
      { type: 'text', label: '2 – 4 sem.', muted: true },
      { type: 'text', label: '24 h', strong: true },
    ],
  },
  {
    label: 'Sans engagement',
    Icon: Unlock,
    values: [{ type: 'yes' }, { type: 'no' }, { type: 'yes' }],
  },
];

const COLS = [
  { label: 'Téléphone', Icon: Phone },
  { label: 'Secrétariat', Icon: Headphones },
  { label: 'UWi', Icon: Bot, featured: true, ribbon: 'LE PLUS COMPLET' },
];

/** Texte alternatif pour lecteurs d'écran (sr-only) */
function buildAltText() {
  const parts = ['Tableau comparatif Téléphone, Secrétariat externalisé, UWi.'];
  ROWS.forEach((r) => {
    const cells = r.values.map((v, i) => {
      const colName = COLS[i].label;
      if (v.type === 'yes') return `${colName} oui`;
      if (v.type === 'no') return `${colName} non`;
      return `${colName} ${v.label}`;
    });
    parts.push(`${r.label} : ${cells.join(' ; ')}.`);
  });
  return parts.join(' ');
}

const COMPARE_ALT = buildAltText();

/** Cellule de valeur (yes / no / text / badge) */
function ValueCell({ value, featured }) {
  const baseStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 56,
    padding: '8px 6px',
    fontSize: 14,
    fontFamily: "'Inter', -apple-system, sans-serif",
  };

  if (value.type === 'yes') {
    return (
      <div style={baseStyle}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: featured ? TEAL : '#E8F5E9',
            color: featured ? '#fff' : '#2E7D32',
          }}
          aria-label="oui"
        >
          <Check size={16} strokeWidth={3} />
        </span>
      </div>
    );
  }
  if (value.type === 'no') {
    return (
      <div style={baseStyle}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: '#FFEBEE',
            color: ROSE,
          }}
          aria-label="non"
        >
          <X size={16} strokeWidth={3} />
        </span>
      </div>
    );
  }
  if (value.type === 'badge') {
    return (
      <div style={baseStyle}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 36,
            height: 28,
            padding: '0 10px',
            borderRadius: 999,
            background: featured ? TEAL : TEAL_50,
            color: featured ? '#fff' : TEAL_DARK,
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.06em',
          }}
        >
          {value.label}
        </span>
      </div>
    );
  }
  // text
  return (
    <div
      style={{
        ...baseStyle,
        color: value.muted ? MUTED : featured ? '#fff' : INK,
        fontWeight: value.strong || featured ? 700 : 500,
        fontStyle: value.muted ? 'italic' : 'normal',
        textAlign: 'center',
        lineHeight: 1.25,
      }}
    >
      {value.label}
    </div>
  );
}

/** Tableau comparatif en CSS Grid : libellé(1.4fr) + 3 colonnes(1fr) */
function CompareTable() {
  return (
    <div
      role="table"
      aria-label="Comparatif Téléphone, Secrétariat externalisé, UWi"
      style={{
        position: 'relative',
        background: '#FFFFFF',
        border: `2px solid ${TEAL_DARK}`,
        borderRadius: 22,
        padding: '22px 18px 18px',
        boxShadow: '0 24px 56px -22px rgba(10,31,36,0.25)',
        overflow: 'visible',
      }}
    >
      {/* Ribbon featured (au-dessus de la colonne UWi) */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: -14,
          right: 'calc(18px + (100% - 36px) / 4.4 * 0.5 - 70px)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '5px 11px',
          background: '#FFFFFF',
          border: `1.5px solid ${YELLOW_300}`,
          borderRadius: 999,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: '0.1em',
          color: '#8a6b00',
          boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
        }}
      >
        <Star size={11} strokeWidth={2.5} fill={YELLOW_300} color={YELLOW_300} />
        {COLS[2].ribbon}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 1fr 1fr 1fr',
          gap: 0,
          rowGap: 2,
        }}
      >
        {/* HEADER ROW */}
        <div role="rowheader" />
        {COLS.map((col, idx) => {
          const Icon = col.Icon;
          const featured = !!col.featured;
          return (
            <div
              key={col.label}
              role="columnheader"
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
                padding: '6px 4px 14px',
                background: featured ? TEAL_DARK : 'transparent',
                color: featured ? '#fff' : INK,
                borderRadius: featured ? '14px 14px 0 0' : 0,
                position: 'relative',
                zIndex: 1,
              }}
            >
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: featured ? 'rgba(255,255,255,0.15)' : '#F4F7F8',
                  color: featured ? '#fff' : MUTED,
                }}
              >
                <Icon size={18} strokeWidth={2} />
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: featured ? '#fff' : MUTED,
                }}
              >
                {col.label}
              </span>
            </div>
          );
        })}

        {/* DATA ROWS */}
        {ROWS.map((row, rIdx) => {
          const RowIcon = row.Icon;
          const isLast = rIdx === ROWS.length - 1;
          const baseRowStyle = {
            display: 'contents',
          };
          return (
            <div key={row.label} role="row" style={baseRowStyle}>
              {/* Cellule libellé */}
              <div
                role="rowheader"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 8px 10px 4px',
                  background: row.highlight ? YELLOW_50 : 'transparent',
                  borderTopLeftRadius: row.highlight ? 10 : 0,
                  borderBottomLeftRadius: row.highlight ? 10 : 0,
                  borderTop: rIdx === 0 ? 'none' : '1px solid rgba(10,31,36,0.06)',
                  fontSize: 13.5,
                  fontWeight: 700,
                  color: INK,
                  lineHeight: 1.2,
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 26,
                    height: 26,
                    borderRadius: 8,
                    background: row.iconBg || '#F4F7F8',
                    color: row.iconBg ? '#8a6b00' : MUTED,
                    flexShrink: 0,
                  }}
                >
                  <RowIcon size={14} strokeWidth={2.2} />
                </span>
                {row.label}
              </div>

              {/* 3 cellules de valeur */}
              {row.values.map((v, cIdx) => {
                const featured = COLS[cIdx].featured;
                const isHighlightTeal = featured;
                return (
                  <div
                    key={cIdx}
                    role="cell"
                    style={{
                      background: row.highlight
                        ? featured
                          ? TEAL_DARK
                          : YELLOW_50
                        : featured
                        ? 'rgba(0,156,164,0.06)'
                        : 'transparent',
                      borderTop: rIdx === 0 ? 'none' : '1px solid rgba(10,31,36,0.06)',
                      borderTopRightRadius:
                        cIdx === row.values.length - 1 && row.highlight ? 10 : 0,
                      borderBottomRightRadius:
                        cIdx === row.values.length - 1 && row.highlight ? 10 : 0,
                      // bord arrondi inférieur de la colonne UWi (dernière ligne)
                      ...(featured && isLast
                        ? { borderRadius: '0 0 14px 14px' }
                        : {}),
                    }}
                  >
                    <ValueCell value={v} featured={isHighlightTeal && row.highlight} />
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function UwiCompare() {
  return (
    <section
      id="compare"
      style={{
        background: '#FFFFFF',
        padding: '120px 24px',
        position: 'relative',
        overflow: 'hidden',
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '-10%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '720px',
          height: '480px',
          background: 'radial-gradient(circle, rgba(0,156,164,0.08) 0%, transparent 65%)',
          pointerEvents: 'none',
          filter: 'blur(40px)',
        }}
      />

      <div style={{ maxWidth: '960px', margin: '0 auto', position: 'relative' }}>
        <div
          style={{
            textAlign: 'center',
            marginBottom: '40px',
            maxWidth: '720px',
            margin: '0 auto 40px',
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
              marginBottom: '24px',
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
              <line x1="9" y1="3" x2="9" y2="21" />
              <line x1="15" y1="3" x2="15" y2="21" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="3" y1="15" x2="21" y2="15" />
            </svg>
            # COMPARATIF
          </div>

          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(32px, 4.5vw, 50px)',
              lineHeight: 1.05,
              margin: '0 0 18px',
              letterSpacing: '-0.03em',
              color: '#0A1F24',
            }}
          >
            Pourquoi UWi plutôt qu&apos;une{' '}
            <span style={{ color: '#009CA4' }}>secrétaire externalisée ?</span>
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: '17px',
              color: 'rgba(10,31,36,0.65)',
              lineHeight: 1.6,
            }}
          >
            Un accueil plus complet, disponible 24h/24, pour un coût bien plus léger.
          </p>
        </div>

        {/* Maquette HTML/CSS native (remplace l'image PNG basse résolution) */}
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <CompareTable />
          <span className="uwi-sr-only">{COMPARE_ALT}</span>
        </div>

        <div
          style={{
            marginTop: '32px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: '13px',
              color: 'rgba(10,31,36,0.5)',
              fontFamily: "'SF Mono', Menlo, monospace",
              letterSpacing: '0.3px',
            }}
          >
            * Tarifs externalisés moyens constatés en France pour 200 appels/mois.
          </p>
          <Link
            to="/creer-assistante?new=1"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '14px 26px',
              background: '#0A1F24',
              color: '#FFFFFF',
              textDecoration: 'none',
              borderRadius: '12px',
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: '14px',
              letterSpacing: '-0.01em',
              boxShadow: '0 10px 24px -6px rgba(10,31,36,0.3)',
              transition: 'all 0.25s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.background = '#009CA4';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.background = '#0A1F24';
            }}
            onClick={() => trackClick('compare_create_assistant_click')}
          >
            Créer mon assistant
            <svg
              width="14"
              height="14"
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

      <style>{`
        .uwi-sr-only {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0,0,0,0);
          white-space: nowrap;
          border: 0;
        }
        @media (max-width: 640px) {
          #compare {
            padding: 80px 16px !important;
          }
        }
        @media (max-width: 520px) {
          #compare [role="table"] {
            padding: 18px 10px 14px !important;
          }
          #compare [role="columnheader"] span:last-child {
            font-size: 9.5px !important;
            letter-spacing: 0.06em !important;
          }
          #compare [role="rowheader"] {
            font-size: 12px !important;
            gap: 6px !important;
          }
        }
      `}</style>
    </section>
  );
}
