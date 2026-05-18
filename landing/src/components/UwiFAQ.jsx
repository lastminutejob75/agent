import { useState } from 'react';

const FAQ_DATA = [
  {
    category: 'Équipe',
    q: "Je ne veux pas remplacer mes assistantes",
    a: {
      lead: "UWi ne remplace pas votre équipe — il s'occupe de ce qui la surcharge.",
      body: "Aujourd'hui, une grande partie des appels sont répétitifs : prise de rendez-vous, horaires, annulations. Résultat : votre standard est saturé… et certains patients n'arrivent jamais à vous joindre.",
      highlight: "Chaque appel manqué est un patient qui va ailleurs.",
      body2: "UWi répond en moins de 2 secondes, 24/7, même pendant les pics (lundi matin, retour de congés). Il absorbe une grande partie des appels et laisse à vos assistantes les demandes à forte valeur humaine.",
      conclusion: "Résultat : moins d'interruptions, moins de stress, et un agenda mieux rempli."
    }
  },
  {
    category: 'Produit',
    q: "Pourquoi UWi est-il différent des autres solutions ?",
    a: {
      lead: "UWi est 100% dédié au secteur médical.",
      body: "Contrairement aux solutions généralistes, tout est pensé pour votre réalité :",
      list: [
        "gestion des urgences",
        "prise de rendez-vous",
        "flux patient",
        "contraintes métier (RGPD, confidentialité, spécialités)"
      ],
      highlight: "Pas de fonctionnalités inutiles. Un outil conçu uniquement pour les praticiens."
    }
  },
  {
    category: 'Produit',
    q: "Combien d'appels je perds aujourd'hui sans le savoir ?",
    a: {
      lead: "La plupart des cabinets sous-estiment fortement ce chiffre.",
      body: "Entre les appels pendant les consultations, les pics d'activité et les horaires de fermeture, une part importante des appels n'aboutit pas.",
      highlight: "Chaque appel non traité est un patient qui ne reviendra pas forcément.",
      conclusion: "UWi capte chaque appel et le transforme en action."
    }
  },
  {
    category: 'Produit',
    q: "Quel gain concret puis-je attendre ?",
    a: {
      lead: "UWi transforme les appels perdus en rendez-vous pris.",
      body: "Les cabinets qui utilisent UWi constatent typiquement :",
      list: [
        "Des appels captés même en dehors des horaires d'ouverture",
        "Moins de temps passé au téléphone par les assistantes",
        "Une meilleure disponibilité pour les patients déjà sur place",
        "Un agenda mieux rempli sur les créneaux creux"
      ],
      highlight: "Quelques rendez-vous récupérés par semaine suffisent à rentabiliser UWi."
    }
  },
  {
    category: 'Produit',
    q: "Est-ce que mes patients vont accepter de parler à une IA ?",
    a: {
      lead: "Votre assistant vocal UWi se présente toujours comme un assistant — jamais de tromperie.",
      body: "Ce que vos patients remarquent surtout :",
      list: ["pas d'attente", "une réponse immédiate", "un échange fluide et rassurant"],
      body2: "Vous pouvez personnaliser son prénom selon votre cabinet (Clara par défaut, ou un prénom qui vous ressemble — Sophie, Julie, Marc…).",
      highlight: "Dans la majorité des cas, l'expérience est perçue comme meilleure qu'un répondeur ou qu'une attente de plusieurs minutes."
    }
  },
  {
    category: 'Produit',
    q: "UWi peut-il gérer les urgences ?",
    a: {
      lead: "UWi ne prend aucune décision médicale.",
      body: "L'assistant applique strictement les règles que vous définissez :",
      list: ["transfert immédiat", "orientation vers le 15", "consignes spécifiques"],
      highlight: "Vous gardez le contrôle total. UWi exécute, il ne diagnostique jamais."
    }
  },
  {
    category: 'Produit',
    q: "Et si UWi ne comprend pas un patient ?",
    a: {
      lead: "UWi reformule et confirme.",
      body: "Si le doute persiste, l'appel est automatiquement transféré vers vous ou votre équipe.",
      highlight: "Aucun patient n'est laissé sans solution."
    }
  },
  {
    category: 'Équipe',
    q: "Que se passe-t-il si je rate un appel aujourd'hui ?",
    a: {
      lead: "Sans UWi : le patient rappelle… ou prend rendez-vous ailleurs.",
      body: "Avec UWi : chaque appel est pris immédiatement, compris, et transformé en action :",
      list: ["rendez-vous pris", "message transmis", "urgence redirigée"],
      highlight: "Vous ne perdez plus d'opportunités sans même vous en rendre compte."
    }
  },
  {
    category: 'Technique',
    q: "Est-ce compliqué à installer ?",
    a: {
      lead: "Vous n'avez rien à faire — on s'occupe de tout.",
      list: ["configuration du numéro", "paramétrage des règles", "connexion à votre agenda"],
      highlight: "Configuration, paramétrage, mise en place : UWi est prêt sans que vous ayez à toucher à quoi que ce soit."
    }
  },
  {
    category: 'Technique',
    q: "Est-ce que ça fonctionne avec Doctolib ?",
    a: {
      lead: "Oui.",
      body: "UWi se connecte à votre agenda et peut, en moins de 2 secondes :",
      list: ["prendre des rendez-vous", "modifier", "annuler"],
      highlight: "Vos disponibilités restent toujours à jour."
    }
  },
  {
    category: 'Technique',
    q: "Mes données sont-elles sécurisées ?",
    a: {
      lead: "Oui — la sécurité est au cœur du produit.",
      list: [
        "Hébergement en Europe",
        "Données chiffrées (transit + stockage)",
        "Conforme RGPD",
        "Partenaires hébergeurs compatibles données de santé",
        "Aucune revente ni utilisation externe"
      ],
      highlight: "Vous restez propriétaire de vos données à tout moment."
    }
  },
  {
    category: 'Technique',
    q: "Que se passe-t-il en cas de problème technique ?",
    a: {
      lead: "En cas d'incident (très rare), les appels sont automatiquement redirigés vers une ligne de secours.",
      highlight: "Vous ne perdez jamais un appel."
    }
  },
  {
    category: 'Offre',
    q: "Combien ça coûte ?",
    a: {
      lead: "Deux formules simples, tout inclus.",
      pricing: [
        { name: 'Starter', price: '99€', period: '/mois', desc: "L'essentiel pour démarrer : prise de RDV, filtrage d'urgence, gestion des annulations." },
        { name: 'Pro', price: '149€', period: '/mois', desc: "Intégration Doctolib complète, règles conversationnelles avancées, statistiques détaillées, support prioritaire." }
      ],
      body: "Un forfait adapté à votre volume d'appels, sans surprise en fin de mois.",
      highlight: "Pas de frais cachés, vous êtes orienté vers le forfait le plus adapté à votre activité."
    }
  },
  {
    category: 'Offre',
    q: "Puis-je arrêter à tout moment ?",
    a: {
      lead: "Oui.",
      body: "Sans engagement, résiliation simple.",
      highlight: "Vous restez uniquement si UWi vous apporte de la valeur."
    }
  },
  {
    category: 'Offre',
    q: "Le support est-il réactif ?",
    a: {
      lead: "Oui — c'est un point clé chez UWi.",
      body: "Notre équipe est disponible pour vous accompagner :",
      list: ["mise en place", "ajustements", "support quotidien"],
      highlight: "Nous répondons en moins de 2 heures."
    }
  },
  {
    category: 'Offre',
    q: "Comment choisir le bon forfait ?",
    a: {
      lead: "Vous n'avez rien à deviner.",
      list: [
        "Nous analysons votre volume d'appels et votre organisation",
        "Nous vous orientons vers le forfait le plus adapté"
      ],
      body: "Et si votre usage évolue, votre formule s'ajuste."
    }
  }
];

const CATEGORY_STYLES = {
  Produit: { bg: 'rgba(0,156,164,0.12)', color: '#007F86' },
  Technique: { bg: 'rgba(245,200,66,0.18)', color: '#8B6508' },
  Offre: { bg: 'rgba(10,31,36,0.08)', color: '#0A1F24' },
  Équipe: { bg: 'rgba(0,156,164,0.1)', color: '#007F86' }
};

// Schema.org JSON-LD pour SEO
const faqSchema = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ_DATA.map((item) => {
    // Transforme la réponse structurée en texte plat pour schema.org
    const a = item.a;
    const parts = [];
    if (a.lead) parts.push(a.lead);
    if (a.body) parts.push(a.body);
    if (a.list) parts.push(a.list.join(' — '));
    if (a.body2) parts.push(a.body2);
    if (a.pricing) parts.push(a.pricing.map(p => `${p.name} ${p.price}${p.period} : ${p.desc}`).join(' '));
    if (a.highlight) parts.push(a.highlight);
    if (a.conclusion) parts.push(a.conclusion);
    return {
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: parts.join(' ') }
    };
  })
};

function AnswerContent({ a }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {a.lead && (
        <p style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#0A1F24', lineHeight: 1.6 }}>
          {a.lead}
        </p>
      )}
      {a.body && (
        <p style={{ margin: 0, fontSize: '15px', color: 'rgba(10,31,36,0.72)', lineHeight: 1.7 }}>
          {a.body}
        </p>
      )}
      {a.list && (
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {a.list.map((item, idx) => (
            <li
              key={idx}
              style={{
                fontSize: '15px',
                color: 'rgba(10,31,36,0.78)',
                lineHeight: 1.5,
                paddingLeft: '22px',
                position: 'relative'
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  left: 0,
                  top: '8px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#009CA4'
                }}
              />
              {item}
            </li>
          ))}
        </ul>
      )}
      {a.pricing && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            marginTop: '4px'
          }}
        >
          {a.pricing.map((plan, idx) => (
            <div
              key={idx}
              style={{
                padding: '20px',
                background: idx === 1 ? 'linear-gradient(135deg, rgba(0,156,164,0.08) 0%, rgba(245,200,66,0.08) 100%)' : 'rgba(10,31,36,0.03)',
                border: `1px solid ${idx === 1 ? 'rgba(0,156,164,0.3)' : 'rgba(10,31,36,0.08)'}`,
                borderRadius: '14px',
                position: 'relative'
              }}
            >
              {idx === 1 && (
                <span
                  style={{
                    position: 'absolute',
                    top: '-10px',
                    right: '16px',
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    padding: '3px 10px',
                    background: '#F5C842',
                    color: '#0A1F24',
                    borderRadius: '6px'
                  }}
                >
                  Populaire
                </span>
              )}
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#007F86', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                {plan.name}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginBottom: '10px' }}>
                <span style={{ fontSize: '32px', fontWeight: 800, color: '#0A1F24', fontFamily: "'Syne', sans-serif" }}>
                  {plan.price}
                </span>
                <span style={{ fontSize: '14px', color: 'rgba(10,31,36,0.6)' }}>{plan.period}</span>
              </div>
              <p style={{ margin: 0, fontSize: '13px', color: 'rgba(10,31,36,0.7)', lineHeight: 1.5 }}>
                {plan.desc}
              </p>
            </div>
          ))}
        </div>
      )}
      {a.body2 && (
        <p style={{ margin: 0, fontSize: '15px', color: 'rgba(10,31,36,0.72)', lineHeight: 1.7 }}>
          {a.body2}
        </p>
      )}
      {a.highlight && (
        <div
          style={{
            marginTop: '4px',
            padding: '14px 18px',
            background: 'linear-gradient(135deg, rgba(0,156,164,0.1) 0%, rgba(245,200,66,0.12) 100%)',
            borderLeft: '3px solid #F5C842',
            borderRadius: '0 10px 10px 0',
            fontSize: '15px',
            fontWeight: 600,
            color: '#0A1F24',
            lineHeight: 1.5
          }}
        >
          👉 {a.highlight}
        </div>
      )}
      {a.conclusion && (
        <p
          style={{
            margin: 0,
            fontSize: '15px',
            fontWeight: 600,
            color: '#0A1F24',
            lineHeight: 1.6,
            fontStyle: 'italic'
          }}
        >
          {a.conclusion}
        </p>
      )}
    </div>
  );
}

// Bloc de preuve sociale (témoignage) inséré après la Q2 "Pourquoi UWi différent"
function SocialProofCard() {
  return (
    <div
      style={{
        padding: '28px 32px',
        background: 'linear-gradient(135deg, #FFFFFF 0%, rgba(0,156,164,0.04) 100%)',
        border: '1px solid rgba(0,156,164,0.2)',
        borderRadius: '16px',
        boxShadow: '0 4px 16px rgba(0,156,164,0.08)',
        display: 'flex',
        gap: '20px',
        alignItems: 'flex-start'
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #009CA4 0%, #4DD8DE 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 700,
          fontSize: '18px',
          fontFamily: "'Syne', sans-serif"
        }}
      >
        💬
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: '11px',
            fontWeight: 700,
            color: '#007F86',
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            marginBottom: '10px'
          }}
        >
          ✨ Retour terrain
        </div>
        <p
          style={{
            margin: 0,
            fontSize: '16px',
            color: '#0A1F24',
            lineHeight: 1.6,
            fontWeight: 500,
            fontStyle: 'italic'
          }}
        >
          « Nos assistantes ne sont plus débordées le lundi matin. UWi prend les appels répétitifs, et on se concentre enfin sur les patients présents au cabinet. »
        </p>
        <div
          style={{
            marginTop: '12px',
            fontSize: '13px',
            color: 'rgba(10,31,36,0.6)',
            fontWeight: 600
          }}
        >
          — Cabinet médical pilote, Hauts-de-France
        </div>
      </div>
    </div>
  );
}

export default function UwiFAQ() {
  const [openIndex, setOpenIndex] = useState(2);

  const toggle = (i) => setOpenIndex(openIndex === i ? -1 : i);

  return (
    <section
      id="faq"
      style={{
        background: '#F5F9FA',
        padding: '120px 24px',
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: '#0A1F24',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* JSON-LD pour SEO */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      {/* Overrides mobile (n'impacte pas le desktop) */}
      <style dangerouslySetInnerHTML={{ __html: `
        @media (max-width: 640px) {
          #faq { padding: 72px 16px !important; }
          .uwi-faq-q-btn {
            padding: 16px 16px !important;
            gap: 12px !important;
            align-items: flex-start !important;
            font-size: 15px !important;
          }
          .uwi-faq-q-row {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 8px !important;
          }
          .uwi-faq-q-cat {
            font-size: 9px !important;
            padding: 3px 8px !important;
            letter-spacing: 1px !important;
          }
          .uwi-faq-q-text {
            font-size: 15px !important;
            line-height: 1.35 !important;
            font-weight: 600 !important;
          }
          .uwi-faq-q-toggle {
            width: 28px !important;
            height: 28px !important;
            margin-top: 2px !important;
          }
        }
        @media (max-width: 420px) {
          #faq { padding: 56px 12px !important; }
          .uwi-faq-q-btn { padding: 14px 14px !important; }
          .uwi-faq-q-text { font-size: 14.5px !important; }
        }
      `}} />

      {/* Glows d'ambiance */}
      <div
        style={{
          position: 'absolute',
          top: '-200px',
          right: '-200px',
          width: '600px',
          height: '600px',
          background: 'radial-gradient(circle, rgba(0,156,164,0.12) 0%, transparent 70%)',
          pointerEvents: 'none'
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-150px',
          left: '-150px',
          width: '500px',
          height: '500px',
          background: 'radial-gradient(circle, rgba(245,200,66,0.15) 0%, transparent 70%)',
          pointerEvents: 'none'
        }}
      />

      <div style={{ maxWidth: '880px', margin: '0 auto', position: 'relative' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <div
            style={{
              display: 'inline-block',
              padding: '6px 14px',
              background: 'rgba(245,200,66,0.2)',
              border: '1px solid rgba(184,134,11,0.3)',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 700,
              color: '#8B6508',
              letterSpacing: '1px',
              textTransform: 'uppercase',
              marginBottom: '24px'
            }}
          >
            FAQ
          </div>
          <h2
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 800,
              fontSize: 'clamp(36px, 5vw, 56px)',
              lineHeight: 1.05,
              margin: 0,
              letterSpacing: '-0.02em',
              color: '#0A1F24'
            }}
          >
            Tout ce que vous voulez<br />
            savoir sur <span style={{ color: '#009CA4' }}>UWi</span>
          </h2>
          <p
            style={{
              marginTop: '20px',
              fontSize: '17px',
              color: 'rgba(10,31,36,0.6)',
              lineHeight: 1.6
            }}
          >
            Si votre question n'est pas ici, écrivez-nous — on répond en moins de 2h.
          </p>
        </div>

        {/* Barre de trust indicators */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '24px',
            flexWrap: 'wrap',
            marginBottom: '56px',
            padding: '16px 24px',
            background: 'rgba(255,255,255,0.6)',
            borderRadius: '14px',
            border: '1px solid rgba(10,31,36,0.06)'
          }}
        >
          {[
            { icon: '🇫🇷', label: 'Solution française' },
            { icon: '🔒', label: 'RGPD & données santé' },
            { icon: '⚡', label: 'Réponse support < 2h' },
            { icon: '🎯', label: '100% médical' }
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '13px',
                fontWeight: 600,
                color: 'rgba(10,31,36,0.75)'
              }}
            >
              <span style={{ fontSize: '16px' }}>{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        {/* FAQ List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {FAQ_DATA.map((item, i) => {
            const isOpen = openIndex === i;
            const catStyle = CATEGORY_STYLES[item.category] || CATEGORY_STYLES.Offre;
            return (
              <div key={i}>
                <div
                  style={{
                    background: isOpen ? '#FFFFFF' : 'rgba(255,255,255,0.7)',
                    border: `1px solid ${isOpen ? 'rgba(0,156,164,0.35)' : 'rgba(10,31,36,0.08)'}`,
                    borderRadius: '16px',
                    overflow: 'hidden',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: isOpen ? '0 8px 32px rgba(0,156,164,0.12)' : '0 2px 8px rgba(10,31,36,0.04)'
                  }}
                >
                  <button
                    onClick={() => toggle(i)}
                    className="uwi-faq-q-btn"
                    style={{
                      width: '100%',
                      padding: '24px 28px',
                      background: 'transparent',
                      border: 'none',
                      color: '#0A1F24',
                      fontSize: '17px',
                      fontWeight: 600,
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '20px',
                      fontFamily: 'inherit',
                      lineHeight: 1.4
                    }}
                  >
                    <span className="uwi-faq-q-row" style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1, minWidth: 0 }}>
                      <span
                        className="uwi-faq-q-cat"
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          letterSpacing: '1.5px',
                          textTransform: 'uppercase',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: catStyle.bg,
                          color: catStyle.color,
                          flexShrink: 0
                        }}
                      >
                        {item.category}
                      </span>
                      <span className="uwi-faq-q-text">{item.q}</span>
                    </span>
                    <span
                      className="uwi-faq-q-toggle"
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: isOpen ? '#009CA4' : 'rgba(10,31,36,0.06)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        transition: 'all 0.3s ease',
                        transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)'
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path
                          d="M7 1V13M1 7H13"
                          stroke={isOpen ? '#fff' : '#0A1F24'}
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                      </svg>
                    </span>
                  </button>

                  <div
                    style={{
                      maxHeight: isOpen ? '1000px' : '0px',
                      opacity: isOpen ? 1 : 0,
                      overflow: 'hidden',
                      transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease'
                    }}
                  >
                    <div style={{ padding: '0 28px 28px 28px' }}>
                      <AnswerContent a={item.a} />
                    </div>
                  </div>
                </div>

                {/* Témoignage inséré après la Q2 (différentiateur UWi) */}
                {i === 1 && (
                  <div style={{ marginTop: '12px', marginBottom: '0' }}>
                    <SocialProofCard />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Bloc résumé final */}
        <div
          style={{
            marginTop: '80px',
            padding: '48px 40px',
            background: 'linear-gradient(135deg, #0A1F24 0%, #134148 100%)',
            borderRadius: '24px',
            position: 'relative',
            overflow: 'hidden',
            boxShadow: '0 20px 60px rgba(10,31,36,0.25)'
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '-100px',
              right: '-100px',
              width: '300px',
              height: '300px',
              background: 'radial-gradient(circle, rgba(245,200,66,0.18) 0%, transparent 70%)',
              pointerEvents: 'none'
            }}
          />
          <div
            style={{
              position: 'absolute',
              bottom: '-80px',
              left: '-80px',
              width: '250px',
              height: '250px',
              background: 'radial-gradient(circle, rgba(0,156,164,0.2) 0%, transparent 70%)',
              pointerEvents: 'none'
            }}
          />
          <div style={{ position: 'relative', textAlign: 'center', color: '#fff' }}>
            <div style={{ display: 'inline-block', fontSize: '28px', marginBottom: '16px' }}>🎯</div>
            <h3
              style={{
                fontFamily: "'Syne', sans-serif",
                fontWeight: 800,
                fontSize: 'clamp(28px, 3.5vw, 40px)',
                margin: '0 0 24px 0',
                letterSpacing: '-0.01em',
                lineHeight: 1.1,
                color: '#fff'
              }}
            >
              En résumé
            </h3>
            <p
              style={{
                fontSize: '18px',
                color: 'rgba(255,255,255,0.85)',
                margin: '0 0 32px 0',
                fontWeight: 600,
                lineHeight: 1.5
              }}
            >
              Aujourd'hui, vous perdez des patients sans le voir.
            </p>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                maxWidth: '460px',
                margin: '0 auto 36px auto',
                textAlign: 'left'
              }}
            >
              {[
                'chaque appel est traité',
                'chaque demande est qualifiée',
                'votre cabinet gagne en efficacité sans complexité'
              ].map((point, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    padding: '14px 20px',
                    background: 'rgba(255,255,255,0.07)',
                    borderRadius: '12px',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}
                >
                  <span style={{ fontSize: '18px', flexShrink: 0 }}>👉</span>
                  <span style={{ fontSize: '15px', color: '#fff', fontWeight: 500 }}>
                    Avec UWi, {point}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
              <a
                href="tel:0939240575"
                style={{
                  display: 'inline-block',
                  padding: '16px 32px',
                  background: '#F5C842',
                  color: '#0A1F24',
                  textDecoration: 'none',
                  borderRadius: '12px',
                  fontWeight: 700,
                  fontSize: '15px',
                  transition: 'transform 0.2s ease'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
                onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
              >
                📞 Tester UWi maintenant
              </a>
              <a
                href="mailto:contact@uwiapp.com"
                style={{
                  display: 'inline-block',
                  padding: '16px 32px',
                  background: 'transparent',
                  color: '#fff',
                  textDecoration: 'none',
                  borderRadius: '12px',
                  fontWeight: 600,
                  fontSize: '15px',
                  border: '1px solid rgba(255,255,255,0.25)',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.5)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)';
                }}
              >
                Nous écrire
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
