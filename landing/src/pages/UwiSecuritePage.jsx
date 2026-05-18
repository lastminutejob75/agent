import { useState } from 'react';
import { Link } from 'react-router-dom';

const PILLARS = [
  {
    id: 'securite',
    chapter: '01',
    title: 'Sécurité',
    subtitle: "La sécurité est au cœur de la conception d'UWi.",
    intro:
      "Chaque jour, nos équipes veillent à ce que vos données et celles de vos patients soient protégées à chaque étape — de la transmission au stockage, en passant par le traitement.",
    sections: [
      {
        icon: '🛡️',
        title: 'Infrastructure de sécurité',
        body: "Notre infrastructure intègre plusieurs niveaux de protection. Les communications sont chiffrées via TLS 1.3, les données au repos via AES-256. Nous appliquons le principe de moindre privilège sur tous les accès internes, et suivons les bonnes pratiques de développement logiciel sécurisé.",
      },
      {
        icon: '⚙️',
        title: 'Sécurité opérationnelle',
        body: "Notre équipe met en place en continu des contrôles de sécurité et surveille l'activité de notre infrastructure. Les mises à jour critiques sont appliquées dans les meilleurs délais. Nos employés suivent une politique stricte de confidentialité.",
      },
      {
        icon: '🔐',
        title: 'Sécurité du produit',
        body: "UWi intègre plusieurs mécanismes d'administration pour offrir aux praticiens une visibilité et un contrôle complets sur leurs données : authentification forte, registre d'activité, gestion fine des accès par rôle (praticien, assistant·e, admin).",
      },
    ],
  },
  {
    id: 'confidentialite',
    chapter: '02',
    title: 'Confidentialité',
    subtitle: 'Vos données, vos patients, votre secret médical.',
    intro:
      "Nous avons bâti UWi autour d'un principe simple : vos données vous appartiennent et elles ne sortent jamais du cadre pour lequel vous nous les confiez.",
    sections: [
      {
        icon: '📋',
        title: 'Traitement des données',
        body: "Nous développons et déployons nos processus en conformité avec les exigences du RGPD et de l'Article L.1110-4 du Code de la santé publique. Chaque employé et prestataire intervenant sur UWi signe un accord de confidentialité. Nous demandons à nos sous-traitants (hébergeurs, prestataires IA) de suivre les mêmes standards que nous.",
      },
      {
        icon: '🗂️',
        title: 'Gouvernance des données',
        body: "La gouvernance couvre tout le cycle de vie de vos données : création, collecte, stockage, traitement, suppression. Aucune donnée patient n'est utilisée à des fins commerciales, publicitaires, ou pour entraîner des modèles d'IA externes.",
      },
      {
        icon: '⚖️',
        title: 'RGPD',
        body: "Le Règlement Général sur la Protection des Données est considéré comme la référence mondiale en matière de vie privée. UWi s'y conforme pleinement : vous disposez des droits d'accès, de rectification, d'effacement, de portabilité et de limitation, activables à tout moment.",
      },
      {
        icon: '🤖',
        title: "Gouvernance de l'IA",
        body: "UWi utilise des modèles d'IA pour comprendre les appels et générer les réponses vocales. Nos contrats avec nos sous-traitants IA interdisent explicitement l'utilisation de vos données conversationnelles pour entraîner leurs modèles. Ce que vos patients disent reste entre vous et nous.",
      },
    ],
  },
  {
    id: 'fiabilite',
    chapter: '03',
    title: 'Fiabilité',
    subtitle: 'Une plateforme sur laquelle vous pouvez compter.',
    intro:
      "Votre cabinet ne peut pas se permettre qu'UWi tombe en panne pendant une consultation ou un pic d'appels. Nous concevons notre infrastructure pour être disponible quand vous en avez besoin.",
    sections: [
      {
        icon: '🏗️',
        title: 'Infrastructure',
        body: "Nous construisons UWi sur des infrastructures cloud européennes reconnues. Nos serveurs applicatifs et bases de données sont hébergés en Europe — aucune donnée patient ne transite hors UE.",
      },
      {
        icon: '🔄',
        title: 'Haute disponibilité',
        body: "Nos systèmes sont supervisés en continu. En cas d'incident, un mécanisme de bascule redirige automatiquement les appels vers une ligne de secours configurée par vos soins — aucun appel patient n'est jamais perdu.",
      },
      {
        icon: '📡',
        title: 'Transparence',
        body: "Nous vous informons de la disponibilité d'UWi en toute transparence. En cas de maintenance planifiée, vous êtes prévenus à l'avance. En cas d'incident, notre équipe vous tient informés.",
      },
    ],
  },
];

const INFRASTRUCTURE_CATEGORIES = [
  {
    category: 'Hébergement applicatif',
    location: 'Europe',
    detail:
      'Serveurs et bases de données hébergés sur une infrastructure cloud européenne reconnue.',
  },
  {
    category: 'Moteur conversationnel IA',
    location: 'Clauses strictes',
    detail:
      'Nos sous-traitants IA sont liés contractuellement à la non-exploitation de vos données conversationnelles pour entraîner leurs modèles.',
  },
  {
    category: 'Téléphonie & numéros',
    location: 'Standards européens',
    detail:
      'Opérateur télécom conforme aux réglementations européennes des communications électroniques.',
  },
  {
    category: 'Distribution de la landing',
    location: 'Sans données patient',
    detail:
      "Les pages publiques de notre site sont distribuées via un CDN global, mais aucune donnée patient n'y transite.",
  },
];

function SideNav({ activeId }) {
  return (
    <nav
      style={{
        position: 'sticky',
        top: '40px',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px',
      }}
    >
      <div
        style={{
          fontFamily: "'SF Mono', Menlo, monospace",
          fontSize: '10px',
          fontWeight: 700,
          color: '#0A1F24',
          letterSpacing: '2px',
          textTransform: 'uppercase',
          opacity: 0.5,
          marginBottom: '16px',
          paddingLeft: '14px',
        }}
      >
        Sommaire
      </div>
      {PILLARS.map((pillar) => (
        <a
          key={pillar.id}
          href={`#${pillar.id}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 14px',
            textDecoration: 'none',
            borderRadius: '8px',
            transition: 'background 0.2s ease',
            borderLeft:
              activeId === pillar.id ? '3px solid #009CA4' : '3px solid transparent',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(10,31,36,0.04)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <span
            style={{
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '11px',
              fontWeight: 700,
              color: '#009CA4',
              letterSpacing: '1px',
            }}
          >
            {pillar.chapter}
          </span>
          <span
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 700,
              fontSize: '14px',
              color: '#0A1F24',
              letterSpacing: '-0.01em',
            }}
          >
            {pillar.title}
          </span>
        </a>
      ))}
    </nav>
  );
}

function PillarSection({ pillar }) {
  return (
    <section
      id={pillar.id}
      style={{
        paddingTop: '80px',
        paddingBottom: '40px',
        borderBottom: '2px solid #0A1F24',
        marginBottom: '40px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontFamily: "'SF Mono', Menlo, monospace",
          fontSize: '10px',
          fontWeight: 700,
          color: '#0A1F24',
          letterSpacing: '2px',
          textTransform: 'uppercase',
          marginBottom: '20px',
          opacity: 0.7,
        }}
      >
        <span style={{ width: '32px', height: '2px', background: '#009CA4' }} />
        Chapitre {pillar.chapter}
      </div>

      <h2
        style={{
          fontFamily: "'Syne', sans-serif",
          fontWeight: 800,
          fontSize: 'clamp(36px, 4vw, 52px)',
          lineHeight: 1.05,
          margin: '0 0 16px 0',
          letterSpacing: '-0.025em',
          color: '#0A1F24',
        }}
      >
        {pillar.title}
      </h2>
      <p
        style={{
          fontFamily: "'Syne', sans-serif",
          fontWeight: 700,
          fontSize: '22px',
          color: '#009CA4',
          margin: '0 0 24px 0',
          lineHeight: 1.3,
          letterSpacing: '-0.01em',
        }}
      >
        {pillar.subtitle}
      </p>
      <p
        style={{
          fontSize: '17px',
          color: '#0A1F24',
          lineHeight: 1.7,
          margin: '0 0 48px 0',
          opacity: 0.8,
          maxWidth: '680px',
        }}
      >
        {pillar.intro}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {pillar.sections.map((section, idx) => (
          <div
            key={idx}
            style={{
              padding: '28px 32px',
              background: '#FFFFFF',
              border: '2px solid #0A1F24',
              borderRadius: '12px',
              boxShadow: '4px 4px 0 #0A1F24',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translate(-2px, -2px)';
              e.currentTarget.style.boxShadow = '6px 6px 0 #009CA4';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translate(0, 0)';
              e.currentTarget.style.boxShadow = '4px 4px 0 #0A1F24';
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                marginBottom: '14px',
              }}
            >
              <span
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '10px',
                  background: 'rgba(0,156,164,0.1)',
                  border: '1.5px solid #0A1F24',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  flexShrink: 0,
                }}
              >
                {section.icon}
              </span>
              <h3
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: '20px',
                  color: '#0A1F24',
                  margin: 0,
                  letterSpacing: '-0.01em',
                  lineHeight: 1.2,
                }}
              >
                {section.title}
              </h3>
            </div>
            <p
              style={{
                margin: 0,
                fontSize: '15px',
                color: '#0A1F24',
                lineHeight: 1.7,
                opacity: 0.75,
              }}
            >
              {section.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function InfrastructureSection() {
  return (
    <section style={{ paddingTop: '80px', paddingBottom: '40px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontFamily: "'SF Mono', Menlo, monospace",
          fontSize: '10px',
          fontWeight: 700,
          color: '#0A1F24',
          letterSpacing: '2px',
          textTransform: 'uppercase',
          marginBottom: '20px',
          opacity: 0.7,
        }}
      >
        <span style={{ width: '32px', height: '2px', background: '#009CA4' }} />
        Annexe — Notre infrastructure
      </div>

      <h2
        style={{
          fontFamily: "'Syne', sans-serif",
          fontWeight: 800,
          fontSize: 'clamp(32px, 3.5vw, 42px)',
          lineHeight: 1.1,
          margin: '0 0 16px 0',
          letterSpacing: '-0.02em',
          color: '#0A1F24',
        }}
      >
        Une architecture pensée pour la confiance.
      </h2>
      <p
        style={{
          fontSize: '16px',
          color: '#0A1F24',
          lineHeight: 1.7,
          margin: '0 0 24px 0',
          opacity: 0.75,
          maxWidth: '680px',
        }}
      >
        Nous sélectionnons nos partenaires d'infrastructure selon des critères stricts :
        localisation européenne quand c'est possible, standards de sécurité reconnus, et clauses
        contractuelles de non-exploitation de vos données.
      </p>

      <div
        style={{
          padding: '14px 18px',
          background: 'rgba(0,156,164,0.06)',
          border: '1.5px dashed #009CA4',
          borderRadius: '8px',
          fontSize: '13px',
          color: '#0A1F24',
          lineHeight: 1.6,
          marginBottom: '40px',
          maxWidth: '680px',
        }}
      >
        <strong style={{ color: '#007F86' }}>Pour nos clients :</strong> la liste nominative
        complète de nos sous-traitants ainsi que notre contrat de traitement des données (DPA)
        sont disponibles sur demande à l'adresse{' '}
        <a
          href="mailto:contact@uwiapp.com"
          style={{ color: '#007F86', fontWeight: 700, textDecoration: 'none' }}
        >
          contact@uwiapp.com
        </a>
        .
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '12px',
        }}
      >
        {INFRASTRUCTURE_CATEGORIES.map((item, idx) => (
          <div
            key={idx}
            style={{
              padding: '22px 24px',
              background: '#FFFFFF',
              border: '1.5px solid #0A1F24',
              borderRadius: '10px',
              boxShadow: '3px 3px 0 #0A1F24',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                marginBottom: '14px',
                gap: '12px',
              }}
            >
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: '15px',
                  color: '#0A1F24',
                  letterSpacing: '-0.01em',
                  lineHeight: 1.3,
                }}
              >
                {item.category}
              </div>
              <div
                style={{
                  fontFamily: "'SF Mono', Menlo, monospace",
                  fontSize: '9px',
                  fontWeight: 700,
                  padding: '3px 8px',
                  background: '#0A1F24',
                  color: '#FFFFFF',
                  borderRadius: '4px',
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {item.location}
              </div>
            </div>
            <div
              style={{
                fontSize: '13px',
                color: '#0A1F24',
                opacity: 0.7,
                lineHeight: 1.6,
              }}
            >
              {item.detail}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function UwiSecuritePage() {
  const [activeId] = useState('securite');

  return (
    <main
      style={{
        background: '#F5F9FA',
        minHeight: '100vh',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: '#0A1F24',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'fixed',
          inset: 0,
          backgroundImage:
            'linear-gradient(rgba(10,31,36,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(10,31,36,0.03) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* Top nav */}
      <nav
        className="uwi-securite-nav"
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          padding: '14px 32px',
          background: 'rgba(245,249,250,0.92)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '2px solid #0A1F24',
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
          }}
        >
          <span
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'linear-gradient(145deg, #009CA4 0%, #007F86 100%)',
              display: 'grid',
              placeItems: 'center',
              border: '1.5px solid #0A1F24',
              boxShadow: '2px 2px 0 #0A1F24',
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
                fontSize: '15px',
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
              Trust Center
            </span>
          </span>
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Link
            to="/"
            className="uwi-securite-nav-back"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              color: '#0A1F24',
              textDecoration: 'none',
              border: '1.5px solid #0A1F24',
              borderRadius: '8px',
              background: '#FFFFFF',
              boxShadow: '2px 2px 0 #0A1F24',
              transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translate(-1px, -1px)';
              e.currentTarget.style.boxShadow = '3px 3px 0 #009CA4';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translate(0, 0)';
              e.currentTarget.style.boxShadow = '2px 2px 0 #0A1F24';
            }}
          >
            ← Retour
          </Link>
          <Link
            to="/creer-assistante?new=1"
            className="uwi-securite-nav-cta"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '11px 18px',
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              color: '#FFFFFF',
              textDecoration: 'none',
              border: '1.5px solid #0A1F24',
              borderRadius: '8px',
              background: '#0A1F24',
              boxShadow: '2px 2px 0 #009CA4',
              transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translate(-1px, -1px)';
              e.currentTarget.style.boxShadow = '3px 3px 0 #009CA4';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translate(0, 0)';
              e.currentTarget.style.boxShadow = '2px 2px 0 #009CA4';
            }}
          >
            Créer mon assistant →
          </Link>
        </div>
      </nav>

      <div
        className="uwi-securite-container"
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '56px 32px 120px 32px',
        }}
      >
        <div
          style={{
            fontFamily: "'SF Mono', Menlo, monospace",
            fontSize: '11px',
            fontWeight: 600,
            color: '#0A1F24',
            opacity: 0.55,
            marginBottom: '40px',
            letterSpacing: '1px',
            textTransform: 'uppercase',
          }}
        >
          <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
            UWi
          </Link>
          <span style={{ margin: '0 10px', opacity: 0.5 }}>/</span>
          <span>Sécurité</span>
        </div>

        <div style={{ marginBottom: '80px', maxWidth: '820px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 14px',
              background: '#0A1F24',
              color: '#FFFFFF',
              borderRadius: '6px',
              fontFamily: "'SF Mono', Menlo, monospace",
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              marginBottom: '32px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#009CA4',
                boxShadow: '0 0 8px #009CA4',
              }}
            />
            Trust Center
          </div>

          <h1
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(48px, 6vw, 80px)',
              lineHeight: 1,
              margin: '0 0 32px 0',
              letterSpacing: '-0.035em',
              color: '#0A1F24',
            }}
          >
            Sécurité &<br />
            <span
              style={{
                textDecoration: 'underline',
                textDecorationColor: '#009CA4',
                textDecorationThickness: '6px',
                textUnderlineOffset: '12px',
              }}
            >
              confidentialité.
            </span>
          </h1>

          <p
            style={{
              fontSize: '20px',
              color: '#0A1F24',
              lineHeight: 1.6,
              margin: '0 0 24px 0',
              opacity: 0.8,
              maxWidth: '680px',
            }}
          >
            Votre sécurité et votre confidentialité sont notre priorité absolue. Nous développons
            UWi en conséquence, chaque jour.
          </p>

          <p
            style={{
              fontSize: '15px',
              color: '#0A1F24',
              lineHeight: 1.7,
              margin: 0,
              opacity: 0.65,
              maxWidth: '680px',
            }}
          >
            Cette page détaille notre approche de la sécurité, de la confidentialité et de la
            fiabilité pour les cabinets médicaux qui nous font confiance. Elle est mise à jour
            régulièrement au fur et à mesure que nos pratiques évoluent.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '240px 1fr',
            gap: '64px',
            alignItems: 'start',
          }}
          className="uwi-securite-layout"
        >
          <aside>
            <SideNav activeId={activeId} />
          </aside>

          <div>
            {PILLARS.map((pillar) => (
              <PillarSection key={pillar.id} pillar={pillar} />
            ))}

            <InfrastructureSection />

            <div
              style={{
                marginTop: '80px',
                padding: '40px 36px',
                background: '#0A1F24',
                color: '#FFFFFF',
                border: '2px solid #0A1F24',
                borderRadius: '12px',
                boxShadow: '6px 6px 0 #009CA4',
              }}
            >
              <div
                style={{
                  fontFamily: "'SF Mono', Menlo, monospace",
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#009CA4',
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                  marginBottom: '16px',
                }}
              >
                — Contact —
              </div>
              <h3
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontWeight: 800,
                  fontSize: 'clamp(24px, 3vw, 32px)',
                  margin: '0 0 16px 0',
                  letterSpacing: '-0.02em',
                  lineHeight: 1.2,
                }}
              >
                Une question sur la sécurité<br />ou vos droits ?
              </h3>
              <p
                style={{
                  fontSize: '15px',
                  color: 'rgba(255,255,255,0.75)',
                  lineHeight: 1.7,
                  margin: '0 0 28px 0',
                  maxWidth: '560px',
                }}
              >
                Nous traitons chaque demande liée à la protection des données dans les meilleurs
                délais, conformément au RGPD. Demandes d'accès, de rectification, de portabilité ou
                d'effacement — nous sommes là pour vous répondre.
              </p>
              <a
                href="mailto:contact@uwiapp.com"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '14px 24px',
                  background: '#FFFFFF',
                  color: '#0A1F24',
                  textDecoration: 'none',
                  border: '2px solid #FFFFFF',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '14px',
                  fontFamily: "'SF Mono', Menlo, monospace",
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                  transition: 'all 0.2s ease',
                  boxShadow: '4px 4px 0 #009CA4',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translate(-2px, -2px)';
                  e.currentTarget.style.boxShadow = '6px 6px 0 #009CA4';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translate(0, 0)';
                  e.currentTarget.style.boxShadow = '4px 4px 0 #009CA4';
                }}
              >
                contact@uwiapp.com →
              </a>
            </div>

            <div
              style={{
                marginTop: '40px',
                fontFamily: "'SF Mono', Menlo, monospace",
                fontSize: '11px',
                color: '#0A1F24',
                opacity: 0.5,
                letterSpacing: '0.5px',
                textAlign: 'center',
              }}
            >
              Dernière mise à jour : Avril 2026 · UWi
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .uwi-securite-layout {
            grid-template-columns: 1fr !important;
            gap: 32px !important;
          }
          .uwi-securite-layout aside nav {
            position: static !important;
          }
        }
        @media (max-width: 640px) {
          .uwi-securite-nav {
            padding: 10px 16px !important;
            gap: 8px !important;
          }
          .uwi-securite-nav-back {
            display: none !important;
          }
          .uwi-securite-nav-cta {
            padding: 9px 12px !important;
            font-size: 11px !important;
          }
          .uwi-securite-container {
            padding: 36px 16px 80px 16px !important;
          }
        }
      `}</style>
    </main>
  );
}
