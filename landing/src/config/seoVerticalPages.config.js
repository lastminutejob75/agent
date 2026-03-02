/**
 * Config des pages SEO verticales — UWi Medical.
 * Positionnement : UWi = la secrétaire médicale augmentée INDISPENSABLE pour les cabinets libéraux.
 * Angle : stress organisationnel + expérience patient. Pas finance, pas techno, pas gadget.
 * SEO : mélanger émotion ET termes explicites (appels manqués cabinet médical, gestion appels,
 * secrétariat médical débordé, prise de rendez-vous cabinet libéral, continuité téléphonique).
 *
 * Phrase pilier : continuité téléphonique.
 * Positionnement émotionnel : réduire le stress organisationnel + garantir une expérience patient fluide.
 * Ton : charge mentale, fluidité du cabinet, qualité perçue par les patients.
 * Jamais : hôpital, clinique. YMYL-safe (aucun conseil médical).
 */

/** Phrase pilier à réutiliser partout. */
export const PHRASE_PILIER =
  "UWi est la secrétaire médicale augmentée indispensable pour assurer la continuité téléphonique de votre cabinet libéral.";

/** Positionnement émotionnel (stress + expérience patient). */
export const POSITIONNEMENT_EMOTIONNEL =
  "UWi est la secrétaire médicale augmentée indispensable pour réduire le stress organisationnel du cabinet et garantir une expérience patient fluide.";

/** Micro-copy accueil (remplace tout "Optimisez votre standard téléphonique"). */
export const MICROCOPY_ACCUEIL =
  "Ne laissez plus la pression téléphonique désorganiser votre cabinet.";

export const PILLAR_PATH = "/secretaire-medicale-augmentee";

/** Ordre prioritaire France : pilier, médecin, dentiste, kiné, orthophoniste, sage-femme, dermatologue, standard. */
export const SEO_VERTICAL_PATHS = [
  PILLAR_PATH,
  "/secretaire-medicale-augmentee-medecin",
  "/assistant-telephone-ia-dentiste",
  "/assistant-telephone-ia-kine",
  "/assistant-telephone-ia-orthophoniste",
  "/assistant-telephone-ia-sage-femme",
  "/assistant-telephone-ia-dermatologue",
  "/standard-telephonique-cabinet-medical",
];

/** Libellés courts pour le maillage interne. */
export const SEO_VERTICAL_LABELS = {
  [PILLAR_PATH]: "Secrétaire médicale augmentée",
  "/secretaire-medicale-augmentee-medecin": "Médecin généraliste",
  "/assistant-telephone-ia-dentiste": "Dentiste",
  "/assistant-telephone-ia-kine": "Kinésithérapeute",
  "/assistant-telephone-ia-orthophoniste": "Orthophoniste",
  "/assistant-telephone-ia-sage-femme": "Sage-femme",
  "/assistant-telephone-ia-dermatologue": "Dermatologue",
  "/standard-telephonique-cabinet-medical": "Standard téléphonique",
};

export const SEO_VERTICAL_PAGES = {
  [PILLAR_PATH]: {
    title: "Secrétaire médicale augmentée indispensable pour cabinet libéral | UWi Medical",
    description:
      "Un cabinet médical libéral ne peut pas se permettre de manquer des appels. UWi assure la continuité téléphonique — moins d'interruptions, moins de stress en fin de journée.",
    h1: "Secrétaire médicale augmentée indispensable pour cabinet médical libéral",
    conversion: true,
    hero: {
      h1: "Un cabinet médical libéral ne peut pas se permettre de manquer des appels.",
      subtitle:
        "UWi est la secrétaire médicale augmentée indispensable pour assurer la continuité téléphonique de votre cabinet libéral.",
      bullets: [
        "Réponse immédiate aux patients",
        "Moins d'interruptions pendant vos consultations",
        "Moins de stress en fin de journée",
      ],
      cta: "Réduire la pression de mon cabinet",
    },
    ctaPrimary: "Réduire la pression de mon cabinet",
    ctaFinal: "Assurer la continuité de mon cabinet",
    sections: [
      {
        h2: "Votre cabinet est sous tension permanente",
        content: "Le médecin doit se reconnaître :",
        listItems: [
          "Le téléphone qui sonne en consultation",
          "Les 18 appels à rappeler à 19h",
          "Les messages mal notés",
          "La secrétaire débordée",
        ],
      },
      {
        h2: "Et si votre cabinet n'avait plus d'appels manqués ?",
        content: "Imaginez :",
        listItems: [
          "Consultations sans interruption",
          "Appels gérés en continu",
          "Patients rassurés",
          "Fin de journée plus légère",
        ],
        subContent: "La sérénité au quotidien.",
      },
      {
        h2: "Aujourd'hui, un cabinet organisé répond toujours.",
        listItems: [
          "La continuité téléphonique n'est plus un confort.",
          "Elle est devenue une exigence des patients.",
          "UWi s'intègre naturellement dans l'organisation d'un cabinet libéral structuré.",
        ],
        subContent:
          "Un cabinet médical ne revient pas en arrière après avoir assuré sa continuité téléphonique.",
        subContentSpaced: true,
      },
      {
        h2: "Comment fonctionne votre secrétaire médicale augmentée",
        content: "3 étapes simples. Court. Clair. Rassurant.",
        listItems: [
          "Elle répond immédiatement",
          "Elle organise les rendez-vous",
          "Elle transmet les urgences",
        ],
      },
      {
        h2: "UWi ne remplace pas votre secrétariat",
        content: "Il le complète. Pas d'erreur, pas de remplacement de l'humain :",
        listItems: [
          "UWi ne remplace pas votre secrétariat — il le complète",
          "Il absorbe les pics",
          "Il transfère les cas sensibles",
          "Il ne donne aucun avis médical",
        ],
      },
    ],
    faq: [
      {
        q: "La secrétaire médicale augmentée remplace-t-elle ma secrétaire ?",
        a: "Non. UWi complète votre secrétariat : elle absorbe les pics, prend les appels et les RDV simples, et transfère à un humain les cas sensibles.",
      },
      {
        q: "UWi donne-t-il des conseils médicaux ?",
        a: "Non. Aucun avis médical, aucun diagnostic. Uniquement accueil téléphonique et organisation des rendez-vous.",
      },
      {
        q: "Les données sont-elles conformes au RGPD ?",
        a: "Oui. UWi est conçu pour respecter le RGPD et la réglementation européenne.",
      },
    ],
  },
  "/secretaire-medicale-augmentee-medecin": {
    title: "Secrétaire médicale augmentée indispensable pour médecin généraliste | UWi Medical",
    description:
      "La secrétaire médicale augmentée indispensable aux médecins libéraux. Continuité téléphonique et organisation des rendez-vous pour votre cabinet.",
    h1: "Secrétaire médicale augmentée indispensable pour médecin généraliste",
    intro: [
      "Pendant que vous consultez, votre cabinet continue de fonctionner.",
      "Sans interruption. Sans appel manqué. Sans surcharge administrative en fin de journée.",
    ],
    ctaPrimary: "Réduire la pression de mon cabinet",
    sections: [
      {
        h2: "Une continuité de votre secrétariat",
        content: "Pendant que vous consultez, votre secrétaire augmentée :",
        listItems: [
          "répond immédiatement aux appels",
          "identifie le motif",
          "propose des créneaux",
          "collecte les informations nécessaires",
        ],
      },
      {
        h2: "Réduction des appels manqués",
        content:
          "Moins d'interruptions. Moins d'appels en attente. Moins de frustration patient.",
      },
      {
        h2: "Filtrage des urgences",
        content: "Elle peut détecter une urgence déclarée, transférer l'appel ou prendre un message prioritaire. Elle ne fournit jamais d'avis médical.",
      },
      {
        h2: "Intégration avec votre organisation actuelle",
        listItems: [
          "Cabinet individuel",
          "Cabinet de groupe",
          "Secrétariat partagé",
          "Agenda en ligne",
        ],
      },
    ],
    faq: [
      {
        q: "La secrétaire médicale augmentée remplace-t-elle ma secrétaire ?",
        a: "Non. UWi complète votre secrétariat : elle gère les appels et les RDV simples, et transfère à un humain les cas complexes.",
      },
      {
        q: "Peut-on gérer les renouvellements par téléphone ?",
        a: "Elle peut qualifier la demande (renouvellement, nouveau RDV, urgence) et orienter selon vos règles. Elle ne donne pas de conseil médical.",
      },
    ],
  },
  "/assistant-telephone-ia-dentiste": {
    title: "Assistant téléphonique IA pour dentiste | UWi Medical",
    description:
      "Standard téléphonique intelligent pour cabinet dentaire. Réponse automatique et prise de rendez-vous.",
    h1: "Assistant téléphonique IA pour dentiste",
    sections: [
      {
        h2: "Répond aux appels pendant vos soins",
        content:
          "L'agent UWi décroche pour votre cabinet dentaire et oriente les patients : prise de rendez-vous, urgence (douleur, traumatisme), ou question. Disponible 24/7 pour ne plus manquer d'appels.",
      },
      {
        h2: "Réduit les appels manqués et améliore l'accueil patient",
        content:
          "Les patients obtiennent une réponse immédiate et un créneau confirmé sans rester en attente. Les rappels de rendez-vous peuvent être automatisés pour limiter les absences.",
      },
      {
        h2: "Filtrage des urgences dentaires",
        content:
          "Douleurs, saignements, traumatismes : l'agent identifie les urgences et les oriente selon votre protocole (créneau dédié, transfert). Les demandes de RDV courants sont gérées automatiquement.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Prise de rendez-vous en direct avec votre outil d'agenda. Créneaux à jour, pas de double réservation. Configuration rapide, sans compétence technique.",
      },
    ],
    faq: [
      {
        q: "L'IA peut-elle remplacer une secrétaire en cabinet dentaire ?",
        a: "Non. UWi automatise les appels simples (RDV, rappels) et transfère à un humain pour les demandes complexes ou les urgences à traiter par l'équipe.",
      },
      {
        q: "Comment sont gérées les urgences dentaires ?",
        a: "L'agent détecte les formulations d'urgence (douleur, traumatisme, etc.) et les oriente selon les règles que vous définissez (créneau dédié, transfert, etc.).",
      },
    ],
  },
  "/assistant-telephone-ia-kine": {
    title: "Assistant téléphonique IA pour kinésithérapeute | UWi Medical",
    description:
      "Agent d'accueil IA pour cabinet de kinésithérapie. Gestion des appels et prise de rendez-vous.",
    h1: "Assistant téléphonique IA pour kinésithérapeute",
    sections: [
      {
        h2: "Répond aux appels pendant vos séances",
        content:
          "L'agent UWi décroche pour votre cabinet de kiné et oriente les patients : première consultation, suivi, renouvellement de série. Plus de ligne occupée pendant les soins.",
      },
      {
        h2: "Réduit les appels manqués et améliore l'accueil patient",
        content:
          "Chaque appel reçoit une réponse immédiate. Prise de rendez-vous en direct avec votre agenda ; les patients obtiennent un créneau confirmé sans attente.",
      },
      {
        h2: "Filtrage des demandes et priorisation",
        content:
          "L'agent qualifie la demande (nouveau patient, suivi, renouvellement) et propose les créneaux adaptés. Les cas particuliers sont transférés à votre secrétariat.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Synchronisation avec votre outil d'agenda. Créneaux à jour, pas de double réservation. Mise en route rapide pour le cabinet.",
      },
    ],
    faq: [
      {
        q: "L'IA peut-elle remplacer une secrétaire en cabinet kiné ?",
        a: "Non. UWi automatise les appels simples (RDV, rappels) et transfère à un humain pour les cas complexes. Outil administratif, pas de remplacement.",
      },
    ],
  },
  "/assistant-telephone-ia-sage-femme": {
    title: "Assistant téléphonique IA pour sage-femme | UWi Medical",
    description:
      "Agent d'accueil IA pour cabinet de sage-femme. Réponse aux appels, prise de rendez-vous et orientation des patientes.",
    h1: "Assistant téléphonique IA pour sage-femme",
    sections: [
      {
        h2: "Répond aux appels pendant vos consultations",
        content:
          "L'agent UWi décroche pour votre cabinet et oriente les patientes : prise de rendez-vous (suivi grossesse, consultation), questions, urgences. Disponible 24/7 pour ne plus manquer d'appels.",
      },
      {
        h2: "Réduit les appels manqués et améliore l'accueil",
        content:
          "Chaque appel reçoit une réponse immédiate. Prise de rendez-vous en direct avec votre agenda ; les patientes obtiennent un créneau confirmé.",
      },
      {
        h2: "Filtrage des demandes et orientation",
        content:
          "L'agent qualifie la demande (premier RDV, suivi, urgence) et oriente selon vos règles. Les cas complexes sont transférés à votre secrétariat.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Synchronisation avec votre outil d'agenda. Créneaux à jour, pas de double réservation. Configuration adaptée au cabinet.",
      },
    ],
    faq: [
      {
        q: "L'IA peut-elle remplacer une secrétaire en cabinet de sage-femme ?",
        a: "Non. UWi automatise les appels simples (RDV, rappels) et transfère à un humain pour les demandes complexes. C'est un outil de secrétariat pour le cabinet.",
      },
    ],
  },
  "/assistant-telephone-ia-orthophoniste": {
    title: "Assistant téléphonique IA pour orthophoniste | UWi Medical",
    description:
      "Agent d'accueil IA pour cabinet d'orthophonie : prise de rendez-vous automatique, gestion des appels, rappels.",
    h1: "Assistant téléphonique IA pour orthophoniste",
    sections: [
      {
        h2: "Répond aux appels 24/7",
        content:
          "L'agent UWi décroche pour votre cabinet d'orthophonie et oriente les patients (prise de RDV, questions).",
      },
      {
        h2: "Prend les rendez-vous automatiquement",
        content:
          "Prise de RDV en direct avec votre agenda. Les familles et patients obtiennent un créneau confirmé sans attente.",
      },
      {
        h2: "Filtre les demandes",
        content:
          "Première consultation, suivi, bilan : l'agent qualifie la demande et propose les créneaux adaptés.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Synchronisation avec votre outil d'agenda. Configuration simple pour le cabinet.",
      },
    ],
    faq: [
      {
        q: "L'IA peut-elle remplacer une secrétaire en cabinet orthophonie ?",
        a: "Non. UWi automatise les appels simples et transfère à un humain pour les demandes complexes. C'est un outil de secrétariat pour le cabinet.",
      },
    ],
  },
  "/assistant-telephone-ia-dermatologue": {
    title: "Assistant téléphonique IA pour dermatologue | UWi Medical",
    description:
      "Agent d'accueil IA pour cabinet de dermatologie. Gestion des appels, prise de rendez-vous et filtrage des demandes pour médecin libéral.",
    h1: "Assistant téléphonique IA pour dermatologue",
    intro: [
      "En cabinet de dermatologie, le volume d'appels est souvent élevé : demandes de rendez-vous, renouvellements, questions sur les délais.",
      "UWi Medical agit comme un assistant téléphonique pour les dermatologues en libéral. Moins d'appels manqués, un accueil professionnel 24/7.",
    ],
    sections: [
      {
        h2: "Répond aux appels pendant vos consultations",
        content:
          "L'agent décroche à la place du cabinet pendant que vous consultez. Prise de RDV, orientation des demandes, message en cas d'urgence — sans interrompre votre exercice.",
      },
      {
        h2: "Réduction des appels manqués",
        content:
          "Moins d'interruptions. Moins d'appels en attente. Les patients obtiennent une réponse immédiate et un créneau confirmé.",
      },
      {
        h2: "Filtrage des demandes",
        content:
          "Première consultation, suivi, renouvellement : l'agent qualifie la demande et propose les créneaux adaptés. Les cas complexes sont transférés à votre secrétariat.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Synchronisation avec votre outil d'agenda. Cabinet individuel ou de groupe, sans infrastructure lourde.",
      },
    ],
    faq: [
      {
        q: "L'IA peut-elle remplacer une secrétaire en cabinet de dermatologie ?",
        a: "Non. UWi automatise les appels simples (RDV, rappels) et transfère à un humain pour les demandes complexes. Outil de secrétariat pour le médecin libéral.",
      },
    ],
  },
  "/standard-telephonique-cabinet-medical": {
    title: "Standard téléphonique cabinet médical — IA 24/7 | UWi Medical",
    description:
      "Standard téléphonique intelligent pour cabinet médical : répondez aux appels 24/7, prenez les RDV automatiquement, filtrez les urgences. Gestion des appels cabinet.",
    h1: "Standard téléphonique intelligent pour cabinet médical",
    sections: [
      {
        h2: "Répond aux appels 24/7",
        content:
          "Plus de ligne occupée ou d'attente interminable. L'agent UWi décroche, informe et oriente les patients en continu.",
      },
      {
        h2: "Prend les rendez-vous automatiquement",
        content:
          "Gestion des appels cabinet médical : prise de RDV en direct avec l'agenda, sans double réservation.",
      },
      {
        h2: "Filtre les urgences",
        content:
          "L'agent identifie les situations urgentes et les signale. Les demandes courantes sont traitées selon vos règles.",
      },
      {
        h2: "Intégration avec votre agenda",
        content:
          "Synchronisation temps réel avec votre outil d'agenda. Secrétariat médical automatisé sans compétence technique.",
      },
    ],
    faq: [
      {
        q: "Qu'est-ce qu'un standard téléphonique IA pour cabinet médical ?",
        a: "C'est un agent vocal qui décroche les appels à la place du cabinet, prend les rendez-vous, filtre les urgences et transfère à un humain quand nécessaire. Outil de gestion des appels, pas de conseil médical.",
      },
      {
        q: "L'IA peut-elle remplacer une secrétaire médicale ?",
        a: "Non. UWi automatise les appels simples et transfère les cas complexes. C'est un outil administratif qui soulage le secrétariat médical.",
      },
    ],
  },
};
