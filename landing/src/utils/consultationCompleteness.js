/**
 * Score de complétude relatif au mode actif (rapide / complet).
 */

import { isEmptyOrGeneric } from "./medicalContext.js";

export const COMPLETUDE_REFERENTIELS = {
  rapide: {
    required: ["motif"],
    scored: [
      { field: "motif", weight: 40 },
      { field: "impression", weight: 40 },
      { field: "prescription_ou_examens", weight: 20 },
    ],
  },
  complet: {
    required: ["motif"],
    scored: [
      { field: "motif", weight: 15 },
      { field: "anamnese", weight: 15 },
      { field: "etat_general", weight: 10 },
      { field: "constantes", weight: 15 },
      { field: "impression", weight: 20 },
      { field: "prescription_ou_examens", weight: 15 },
      { field: "suivi", weight: 10 },
    ],
  },
};

const CONSTANTE_KEYS = ["fc", "pas", "pad", "temp", "spo2", "fr", "poids", "taille"];

export function hasPrescriptionOrExamens(formState) {
  if (!formState) return false;
  return !isEmptyOrGeneric(formState.prescription) || (formState.examens?.length ?? 0) > 0;
}

export function countFilledConstantes(formState) {
  if (!formState) return 0;
  return CONSTANTE_KEYS.filter((key) => !isEmptyOrGeneric(formState[key])).length;
}

function completudeFieldRatio(field, formState, hasExistingNextAppointment) {
  switch (field) {
    case "motif":
      return isEmptyOrGeneric(formState.motif) ? 0 : 1;
    case "anamnese":
      return isEmptyOrGeneric(formState.anamnese) ? 0 : 1;
    case "etat_general":
      return isEmptyOrGeneric(formState.etatGeneral) ? 0 : 1;
    case "impression":
      return isEmptyOrGeneric(formState.impression) ? 0 : 1;
    case "prescription_ou_examens":
      return hasPrescriptionOrExamens(formState) ? 1 : 0;
    case "constantes": {
      const filled = countFilledConstantes(formState);
      return filled >= 2 ? 1 : filled === 1 ? 0.5 : 0;
    }
    case "suivi":
      return !isEmptyOrGeneric(formState.suiviConsignes)
        || !isEmptyOrGeneric(formState.suiviRdv)
        || hasExistingNextAppointment
        ? 1
        : 0;
    default:
      return 0;
  }
}

export function computeConsultationCompleteness(formState, mode, hasExistingNextAppointment = false) {
  const ref = COMPLETUDE_REFERENTIELS[mode === "complete" ? "complet" : "rapide"];
  const score = ref.scored.reduce(
    (sum, { field, weight }) => sum + weight * completudeFieldRatio(field, formState, hasExistingNextAppointment),
    0,
  );
  return Math.round(score);
}

/** @deprecated alias — préférer computeConsultationCompleteness */
export const computeCompletude = computeConsultationCompleteness;
