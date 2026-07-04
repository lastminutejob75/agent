// Reformulations locales des motifs patients (niveau A — zéro latence).
// Motif déclaré en langage courant -> propositions de motif médical.
// Jamais de diagnostic affirmé : toujours "à explorer / à caractériser / à évaluer".

export const MOTIF_MAP = [
  // Digestif
  { keywords: ["mal au ventre", "douleur ventre", "mal de ventre", "maux de ventre", "douleur abdominale"], suggestions: ["Douleurs abdominales à explorer", "Épigastralgies"] },
  { keywords: ["diarrhee", "gastro", "vomissement", "nausee"], suggestions: ["Troubles digestifs aigus à caractériser", "Gastro-entérite — évaluation"] },
  { keywords: ["constipation", "constipe"], suggestions: ["Constipation à explorer", "Troubles du transit à évaluer"] },
  { keywords: ["brulure estomac", "reflux", "remontee acide"], suggestions: ["Pyrosis / reflux gastro-œsophagien à évaluer", "Épigastralgies"] },

  // Céphalées / neuro
  { keywords: ["mal a la tete", "mal de tete", "migraine", "maux de tete"], suggestions: ["Céphalées à caractériser", "Migraine — évaluation"] },
  { keywords: ["vertige", "tete qui tourne", "etourdissement"], suggestions: ["Vertiges à explorer", "Sensations vertigineuses à caractériser"] },
  { keywords: ["fourmillement", "engourdissement"], suggestions: ["Paresthésies à explorer"] },

  // Général
  { keywords: ["fatigue", "epuise", "epuisement", "plus d'energie"], suggestions: ["Asthénie à explorer", "Asthénie persistante"] },
  { keywords: ["fievre", "temperature", "frisson"], suggestions: ["Syndrome fébrile à explorer"] },
  { keywords: ["perte de poids", "maigri"], suggestions: ["Amaigrissement à explorer"] },

  // Ostéo-articulaire
  { keywords: ["mal au dos", "dos bloque", "lumbago", "mal de dos"], suggestions: ["Lombalgie aiguë", "Rachialgies à évaluer"] },
  { keywords: ["mal au cou", "torticolis", "cervicale"], suggestions: ["Cervicalgies à évaluer"] },
  { keywords: ["genou", "epaule", "articulation", "entorse"], suggestions: ["Douleur articulaire à caractériser", "Traumatisme ostéo-articulaire à évaluer"] },

  // Respiratoire / ORL
  { keywords: ["toux", "je tousse"], suggestions: ["Toux — à caractériser (durée, productivité)", "Syndrome respiratoire"] },
  { keywords: ["essouffle", "souffle court", "respire mal"], suggestions: ["Dyspnée à explorer", "Dyspnée d'effort à caractériser"] },
  { keywords: ["mal a la gorge", "gorge", "angine"], suggestions: ["Odynophagie à évaluer", "Syndrome pharyngé"] },
  { keywords: ["nez bouche", "rhume", "sinusite", "nez qui coule"], suggestions: ["Syndrome rhinopharyngé", "Rhinite — évaluation"] },
  { keywords: ["oreille", "otite", "mal aux oreilles"], suggestions: ["Otalgie à évaluer"] },

  // Cardio
  { keywords: ["douleur poitrine", "douleur thoracique", "mal a la poitrine", "oppression"], suggestions: ["Douleur thoracique à explorer", "Précordialgies à caractériser"] },
  { keywords: ["palpitation", "coeur qui bat"], suggestions: ["Palpitations à explorer"] },
  { keywords: ["tension", "hypertension", "hta"], suggestions: ["Suivi d'hypertension artérielle", "Contrôle tensionnel"] },

  // Dermato
  { keywords: ["bouton", "plaque", "eruption", "demangeaison", "ca gratte"], suggestions: ["Lésions cutanées à caractériser", "Prurit à explorer"] },
  { keywords: ["grain de beaute", "tache peau"], suggestions: ["Lésion pigmentée — évaluation dermatologique"] },

  // Uro / gynéco courant
  { keywords: ["brulure urinaire", "envie d'uriner", "cystite", "infection urinaire"], suggestions: ["Signes fonctionnels urinaires à explorer", "Suspicion d'infection urinaire — à évaluer"] },
  { keywords: ["regle", "regles douloureuses", "cycle"], suggestions: ["Troubles du cycle à évaluer", "Dysménorrhées à caractériser"] },
  { keywords: ["contraception", "pilule"], suggestions: ["Consultation de contraception"] },

  // Psy / sommeil
  { keywords: ["stress", "anxieux", "anxiete", "angoisse"], suggestions: ["Symptomatologie anxieuse à évaluer"] },
  { keywords: ["dors mal", "insomnie", "sommeil"], suggestions: ["Troubles du sommeil à caractériser"] },
  { keywords: ["deprime", "moral", "triste"], suggestions: ["Trouble de l'humeur à évaluer"] },

  // Administratif / suivi
  { keywords: ["renouvellement", "ordonnance"], suggestions: ["Renouvellement de traitement", "Suivi de traitement chronique"] },
  { keywords: ["certificat", "sport", "aptitude"], suggestions: ["Certificat médical — aptitude", "Visite d'aptitude"] },
  { keywords: ["resultat", "analyse", "prise de sang", "bilan"], suggestions: ["Remise et interprétation de résultats biologiques"] },
  { keywords: ["vaccin", "rappel vaccin"], suggestions: ["Vaccination — mise à jour calendrier vaccinal"] },
  { keywords: ["diabete", "glycemie"], suggestions: ["Suivi de diabète", "Contrôle glycémique — évaluation"] },

  // Pédiatrie courante
  { keywords: ["enfant fievre", "bebe fievre", "mon fils a de la fievre", "ma fille a de la fievre"], suggestions: ["Syndrome fébrile de l'enfant à explorer"] },
];

export const GENERIC_SUGGESTION = "Consultation de médecine générale — motif à préciser";

// lowercase + sans accents, pour un matching tolérant.
export function normalizeMotif(text) {
  return String(text ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Retourne 2 à 3 suggestions médicales pour un motif patient brut.
// Aucun match -> une seule chip générique (le champ reste éditable).
export function getMotifSuggestions(rawMotif) {
  const normalized = normalizeMotif(rawMotif);
  if (!normalized) return [GENERIC_SUGGESTION];

  const out = [];
  for (const entry of MOTIF_MAP) {
    if (entry.keywords.some((k) => normalized.includes(normalizeMotif(k)))) {
      for (const s of entry.suggestions) {
        if (!out.includes(s)) out.push(s);
      }
    }
    if (out.length >= 3) break;
  }
  return out.length ? out.slice(0, 3) : [GENERIC_SUGGESTION];
}
