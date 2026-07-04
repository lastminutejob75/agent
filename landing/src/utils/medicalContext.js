/**
 * Helpers contexte patient — signal uniquement, sans bruit visuel.
 */

export const GENERIC_VALUES = [
  "consultation",
  "à compléter",
  "a completer",
  "non renseigné",
  "non renseignée",
  "non renseignés",
  "non renseignées",
  "non precise",
  "non précisé",
  "—",
  "-",
  "",
  "néant",
  "neant",
  "ras",
  "r.a.s.",
];

export const KNOWN_NEGATIVE_VALUES = [
  "aucune allergie connue",
  "pas d'allergie connue",
  "aucun traitement en cours",
  "pas de traitement en cours",
  "aucun antecedent connu",
  "pas d'antecedent connu",
  "aucun antecedent medical majeur connu",
  "aucun antecedent medical connu",
];

export const DOSSIER_FIELDS = [
  { key: "allergies", label: "Allergies", tone: "alert" },
  { key: "traitements", label: "Traitements en cours", tone: "teal" },
  { key: "points_attention", label: "Points d'attention", tone: "amber" },
  { key: "facteurs_risque", label: "Facteurs de risque", tone: "amber" },
  { key: "antecedents_medicaux", label: "Antécédents médicaux", tone: "neutral" },
  { key: "antecedents_chirurgicaux", label: "Antécédents chirurgicaux", tone: "neutral" },
];

export function normalizeMedicalString(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[’']/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

const GENERIC_NORMALIZED = new Set(GENERIC_VALUES.map(normalizeMedicalString));
const KNOWN_NEGATIVE_NORMALIZED = new Set(KNOWN_NEGATIVE_VALUES.map(normalizeMedicalString));

export function isEmptyOrGeneric(value) {
  if (value == null) return true;
  const v = normalizeMedicalString(value);
  return v.length === 0 || GENERIC_NORMALIZED.has(v);
}

export function isKnownNegative(value) {
  if (value == null) return false;
  return KNOWN_NEGATIVE_NORMALIZED.has(normalizeMedicalString(value));
}

/** Champ dossier avec signal affichable (contenu réel ou négation documentée). */
export function hasContextFieldSignal(value) {
  if (isEmptyOrGeneric(value)) return false;
  return true;
}

/**
 * Synthèse / dernier contexte : vide si motif ET impression sont génériques.
 * Accepte une chaîne structurée ou un objet { motif, impression }.
 */
export function isGenericConsultationSummary(summary) {
  if (summary == null) return true;
  if (typeof summary === "object") {
    const motif = summary.motif || summary.reason || "";
    const impression = summary.impression || "";
    return isEmptyOrGeneric(motif) && isEmptyOrGeneric(impression);
  }

  const text = String(summary);
  if (isEmptyOrGeneric(text)) return true;

  const motifMatch = text.match(/motif\s*:\s*([^|]*)/i);
  const impressionMatch = text.match(/impression\s*:\s*([^|]*)/i);
  if (motifMatch || impressionMatch) {
    const motifGeneric = motifMatch ? isEmptyOrGeneric(motifMatch[1]) : true;
    const impressionGeneric = impressionMatch ? isEmptyOrGeneric(impressionMatch[1]) : true;
    return motifGeneric && impressionGeneric;
  }

  return isEmptyOrGeneric(text);
}

export function hasSummarySignal(summary) {
  return !isGenericConsultationSummary(summary);
}

export function hasMedicalSignal(patientContext) {
  if (!patientContext || typeof patientContext !== "object") return false;
  if (DOSSIER_FIELDS.some((f) => hasContextFieldSignal(patientContext[f.key]))) return true;
  if (hasSummarySignal(patientContext.synthese_medicale)) return true;
  if (hasSummarySignal(patientContext.dernier_contexte_consultation)) return true;
  return false;
}

export function dossierHasContent(patient) {
  return hasMedicalSignal(patient);
}

/** Tuiles visibles pour la carte « À relire avant examen » — allergies en premier. */
export function getVisibleContextTiles(patientContext) {
  if (!patientContext || typeof patientContext !== "object") return [];

  const tiles = [];

  if (hasContextFieldSignal(patientContext.allergies)) {
    tiles.push({
      label: "Allergies",
      value: patientContext.allergies,
      tone: isKnownNegative(patientContext.allergies) ? "muted" : "alert",
      wide: false,
      sortOrder: 0,
    });
  }

  if (hasContextFieldSignal(patientContext.traitements)) {
    tiles.push({
      label: "Traitements",
      value: patientContext.traitements,
      tone: isKnownNegative(patientContext.traitements) ? "muted" : "teal",
      wide: false,
      sortOrder: 1,
    });
  }

  const attention = hasContextFieldSignal(patientContext.points_attention)
    ? patientContext.points_attention
    : hasContextFieldSignal(patientContext.facteurs_risque)
      ? patientContext.facteurs_risque
      : null;
  if (attention) {
    tiles.push({
      label: "Attention",
      value: attention,
      tone: "amber",
      wide: false,
      sortOrder: 2,
    });
  }

  if (hasSummarySignal(patientContext.synthese_medicale)) {
    tiles.push({
      label: "Synthèse médicale",
      value: patientContext.synthese_medicale,
      tone: "teal",
      wide: true,
      sortOrder: 3,
    });
  }

  return tiles.sort((a, b) => a.sortOrder - b.sortOrder);
}

export function getEmptyDossierFieldLabels(patient) {
  return DOSSIER_FIELDS
    .filter((f) => !hasContextFieldSignal(patient?.[f.key]))
    .map((f) => f.label.toLowerCase());
}

export function dedupeSummaries(summaryA, summaryB) {
  const a = hasSummarySignal(summaryA) ? summaryA : null;
  let b = hasSummarySignal(summaryB) ? summaryB : null;
  if (a && b && normalizeMedicalString(a) === normalizeMedicalString(b)) {
    b = null;
  }
  return { synthese: a, dernierContexte: b };
}

/** Signal critique (allergie réelle, traitement, points d'attention) — pas les seules négations documentées. */
export function hasCriticalMedicalSignal(patientContext) {
  if (!patientContext) return false;
  if (hasContextFieldSignal(patientContext.allergies) && !isKnownNegative(patientContext.allergies)) {
    return true;
  }
  if (hasContextFieldSignal(patientContext.traitements) && !isKnownNegative(patientContext.traitements)) {
    return true;
  }
  if (hasContextFieldSignal(patientContext.points_attention)) return true;
  if (hasContextFieldSignal(patientContext.facteurs_risque)) return true;
  return false;
}
