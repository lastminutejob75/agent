/**
 * Reformulations locales des motifs patients (niveau A — zéro latence).
 */

import { normalizeMedicalString } from "./medicalContext.js";

export const MOTIF_MAP = [
  { keywords: ["mal au ventre", "douleur ventre", "mal de ventre", "ventre", "maux de ventre"], suggestions: ["Douleurs abdominales à explorer", "Épigastralgies — à caractériser"] },
  { keywords: ["mal a la tete", "mal de tete", "migraine", "cephalee", "maux de tete"], suggestions: ["Céphalées à caractériser", "Migraine — évaluation clinique"] },
  { keywords: ["fatigue", "fatiguee", "fatigue", "epuise", "epuisement"], suggestions: ["Asthénie à explorer", "Asthénie persistante — à caractériser"] },
  { keywords: ["mal au dos", "dos bloque", "dos bloqué", "lumbago", "mal de dos"], suggestions: ["Lombalgie aiguë", "Rachialgies à évaluer"] },
  { keywords: ["toux", "je tousse", "tousse"], suggestions: ["Toux — à caractériser", "Syndrome respiratoire à évaluer"] },
  { keywords: ["fievre", "fièvre", "temperature", "température", "frisson"], suggestions: ["Syndrome fébrile à explorer"] },
  { keywords: ["renouvellement", "ordonnance", "medicament", "médicament"], suggestions: ["Renouvellement de traitement", "Suivi de traitement chronique"] },
  { keywords: ["certificat", "sport", "aptitude"], suggestions: ["Certificat médical — aptitude", "Visite d'aptitude"] },
  { keywords: ["resultat", "résultat", "analyse", "prise de sang", "bilan sanguin", "bilan"], suggestions: ["Remise et interprétation de résultats biologiques"] },
  { keywords: ["vaccin", "vaccination", "rappel vaccin"], suggestions: ["Vaccination — mise à jour du calendrier vaccinal"] },
  { keywords: ["gorge", "angine", "mal a la gorge", "mal de gorge"], suggestions: ["Odynophagie à évaluer", "Symptomatologie ORL à explorer"] },
  { keywords: ["oreille", "otite", "mal oreille", "mal aux oreilles"], suggestions: ["Otalgie à évaluer", "Suspicion d'atteinte ORL"] },
  { keywords: ["nez", "rhume", "sinusite", "nez bouche", "nez qui coule"], suggestions: ["Rhinopharyngite à évaluer", "Symptomatologie ORL à caractériser"] },
  { keywords: ["bouton", "eruption", "éruption", "plaque", "demangeaison", "démangeaison", "ca gratte"], suggestions: ["Éruption cutanée à explorer", "Lésion dermatologique à évaluer"] },
  { keywords: ["eczema", "eczéma", "psoriasis"], suggestions: ["Dermatose chronique — suivi", "Lésion cutanée à réévaluer"] },
  { keywords: ["anxiete", "anxiété", "stress", "angoisse", "anxieux"], suggestions: ["Symptômes anxieux à évaluer", "Anxiété — retentissement à caractériser"] },
  { keywords: ["sommeil", "insomnie", "dort mal", "dors mal"], suggestions: ["Troubles du sommeil à explorer", "Insomnie — évaluation clinique"] },
  { keywords: ["vertige", "tete qui tourne", "tête qui tourne", "etourdissement"], suggestions: ["Vertiges à caractériser", "Sensation vertigineuse à évaluer"] },
  { keywords: ["nausee", "nausée", "vomissement", "vomit", "gastro"], suggestions: ["Nausées/vomissements à explorer", "Troubles digestifs à évaluer"] },
  { keywords: ["diarrhee", "diarrhée"], suggestions: ["Diarrhée aiguë à évaluer", "Troubles du transit à explorer"] },
  { keywords: ["constipation", "constipe"], suggestions: ["Constipation à explorer", "Troubles du transit à évaluer"] },
  { keywords: ["brulure urinaire", "brûlure urinaire", "infection urinaire", "urine", "cystite"], suggestions: ["Signes urinaires à explorer", "Suspicion d'infection urinaire à évaluer"] },
  { keywords: ["regles", "règles", "douleur regles", "contraception", "pilule"], suggestions: ["Motif gynécologique courant à préciser", "Douleurs pelviennes à évaluer"] },
  { keywords: ["tension", "hypertension", "hta"], suggestions: ["Suivi tensionnel", "Hypertension artérielle — suivi"] },
  { keywords: ["diabete", "diabète", "glycemie", "glycémie"], suggestions: ["Suivi diabétique", "Équilibre glycémique à évaluer"] },
  { keywords: ["enfant fievre", "enfant fièvre", "mon enfant a de la fievre", "bebe fievre"], suggestions: ["Syndrome fébrile chez l'enfant à évaluer"] },
  { keywords: ["douleur thoracique", "mal poitrine", "poitrine", "mal a la poitrine", "douleur poitrine"], suggestions: ["Douleur thoracique à évaluer rapidement"] },
  { keywords: ["essoufflement", "souffle court", "dyspnee", "dyspnée", "essouffle", "respire mal"], suggestions: ["Dyspnée à évaluer rapidement"] },
  { keywords: ["malaise", "perte de connaissance"], suggestions: ["Malaise à caractériser"] },
  { keywords: ["fourmillement", "paralysie", "trouble parole", "visage deforme", "engourdissement"], suggestions: ["Symptômes neurologiques à évaluer rapidement"] },
  { keywords: ["douleur abdominale intense"], suggestions: ["Douleur abdominale aiguë à évaluer"] },
  { keywords: ["palpitation", "coeur qui bat"], suggestions: ["Palpitations à explorer"] },
  { keywords: ["mal au cou", "torticolis", "cervicale"], suggestions: ["Cervicalgies à évaluer"] },
  { keywords: ["perte de poids", "maigri"], suggestions: ["Amaigrissement à explorer"] },
  { keywords: ["deprime", "moral", "triste"], suggestions: ["Trouble de l'humeur à évaluer"] },
];

export const SENSITIVE_MOTIF_KEYWORDS = [
  "douleur thoracique",
  "mal poitrine",
  "mal a la poitrine",
  "douleur poitrine",
  "poitrine",
  "essoufflement",
  "souffle court",
  "dyspnee",
  "dyspnée",
  "essouffle",
  "malaise",
  "perte de connaissance",
  "paralysie",
  "trouble parole",
  "visage deforme",
  "douleur abdominale intense",
  "enfant fievre",
  "enfant fièvre",
  "mon enfant a de la fievre",
];

export const GENERIC_SUGGESTION = "Consultation de médecine générale — motif à préciser";

export function getMotifSuggestions(rawMotif) {
  const normalized = normalizeMedicalString(rawMotif);
  if (!normalized) return [GENERIC_SUGGESTION];

  const out = [];
  for (const entry of MOTIF_MAP) {
    if (entry.keywords.some((k) => normalized.includes(normalizeMedicalString(k)))) {
      for (const s of entry.suggestions) {
        if (!out.includes(s)) out.push(s);
      }
    }
    if (out.length >= 3) break;
  }
  return out.length ? out.slice(0, 3) : [GENERIC_SUGGESTION];
}

export function isSensitiveMotif(rawMotif) {
  const normalized = normalizeMedicalString(rawMotif);
  if (!normalized) return false;
  return SENSITIVE_MOTIF_KEYWORDS.some((k) => normalized.includes(normalizeMedicalString(k)));
}
