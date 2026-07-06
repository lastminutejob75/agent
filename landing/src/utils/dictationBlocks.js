/**
 * Dictée ambiante — logique pure des blocs (contrat partagé avec le backend).
 *
 * Un bloc : { id, field, dest, label, text, sourceSpans, provenance,
 *            critical, danger, confirmed, status, extra?, structured?, synthetic? }
 */

import { hasContextFieldSignal, normalizeMedicalString } from "./medicalContext.js";

export const DAY_FIELDS = ["motif", "elements", "examen", "impression", "decision"];
export const DOSSIER_FIELDS_ORDER = ["mesures", "allergies", "traitements", "antecedents", "contexte"];

export const FIELD_LABELS = {
  motif: "Motif",
  elements: "Éléments",
  examen: "Examen",
  impression: "Impression",
  decision: "Conduite",
  allergies: "Allergies",
  antecedents: "Antécédents",
  traitements: "Traitements",
  mesures: "Mesures",
  contexte: "Contexte",
};

export const NR_TEXT = "Non renseigné lors de cette consultation.";

export const DECISION_TAGS = [
  "Prescription",
  "Conseils",
  "Surveillance",
  "Examen demandé",
  "Orientation",
  "Certificat",
];

/**
 * Trace « Non renseigné (interrogé le …) » écrite par le backend quand le
 * praticien a marqué un champ non renseigné lors d'une consultation. La
 * question reste ouverte : le champ n'est PAS connu, mais elle a déjà été
 * posée (donc plus de surlignage priorité ni de blocage Allergies).
 */
export function isNonRenseigneTrace(value) {
  const v = normalizeMedicalString(value);
  return v.length > 0 && v.startsWith("non renseigne");
}

/** Champ durable réellement connu : contenu ou négation documentée — pas une trace « non renseigné ». */
export function isDossierFieldKnown(value) {
  return hasContextFieldSignal(value) && !isNonRenseigneTrace(value);
}

/**
 * Checklist de recueil = champs durables inconnus du dossier patient (jamais
 * renseignés OU marqués « non renseigné » lors d'une consultation précédente),
 * quel que soit le rang de la consultation. Un champ marqué « non renseigné »
 * réapparaît, mais sans le surlignage priorité (la question a déjà été posée).
 * Poids/taille vivent dans les constantes : `mesuresConnues` vient du backend.
 */
export function buildChecklist(patient, { mesuresConnues = false } = {}) {
  const items = [];
  const push = (key, label, priorityWhenNew) => {
    items.push({ key, label, priority: priorityWhenNew, captured: false });
  };
  if (!isDossierFieldKnown(patient?.allergies)) {
    push("allergies", "Allergies", !isNonRenseigneTrace(patient?.allergies));
  }
  if (
    !isDossierFieldKnown(patient?.antecedents_medicaux)
    && !isDossierFieldKnown(patient?.antecedents_chirurgicaux)
  ) {
    push("antecedents", "Antécédents", false);
  }
  if (!isDossierFieldKnown(patient?.traitements)) {
    push("traitements", "Traitements", !isNonRenseigneTrace(patient?.traitements));
  }
  if (!mesuresConnues) {
    push("mesures", "Poids · taille", false);
  }
  return items;
}

export function markChecklistCaptured(checklist, blocks) {
  const captured = new Set((blocks || []).map((b) => b.field));
  return (checklist || []).map((item) => ({ ...item, captured: captured.has(item.key) }));
}

export function computeImcFrontend(poidsKg, tailleCm) {
  const kg = Number(String(poidsKg ?? "").replace(",", "."));
  const cm = Number(String(tailleCm ?? "").replace(",", "."));
  if (!Number.isFinite(kg) || !Number.isFinite(cm) || kg <= 0 || cm <= 0) return null;
  const m = cm / 100;
  return Math.round((kg / (m * m)) * 10) / 10;
}

/**
 * Prépare les blocs reçus de /structure-dictation pour la relecture.
 *
 * - `firstConsultation:true` (v7) : complète les blocs dossier manquants de la
 *   checklist en tuiles synthétiques « à renseigner » — le socle entier est visible.
 * - Mode classique (v4) : la grille n'apparaît que si la dictée du jour a produit
 *   des blocs dossier. Seule exception (invariant 3) : Allergies sans AUCUN état
 *   au dossier (`allergiesAsked:false`) → tuile synthétique bloquante. Un « non
 *   renseigné » tracé lors d'une consultation précédente est un état documenté :
 *   pas de tuile, la question ne revit que via la chip de checklist et la dictée.
 */
export function prepareReviewBlocks(
  apiBlocks,
  { checklist = [], degraded = false, firstConsultation = false, allergiesAsked = false } = {},
) {
  const blocks = (Array.isArray(apiBlocks) ? apiBlocks : []).map((b) => ({ ...b, synthetic: false }));
  if (degraded) {
    // Mode dégradé : impression/conduite ne bloquent pas, la dictée est conservée telle quelle.
    return blocks.map((b) => ({ ...b, confirmed: true }));
  }
  const present = new Set(blocks.map((b) => b.field));
  for (const item of checklist) {
    if (present.has(item.key)) continue;
    const blocking = item.key === "allergies" && !allergiesAsked;
    if (!firstConsultation && !blocking) continue;
    blocks.push({
      id: `${item.key}-synthetic`,
      field: item.key,
      dest: "dossier",
      label: FIELD_LABELS[item.key] || item.label,
      text: "",
      sourceSpans: [],
      provenance: "non_renseigne",
      critical: blocking,
      danger: blocking,
      confirmed: !blocking,
      status: "propose",
      synthetic: true,
    });
  }
  return blocks;
}

export function splitBlocks(blocks) {
  const day = (blocks || []).filter((b) => b.dest === "day");
  const dossier = (blocks || []).filter((b) => b.dest === "dossier");
  const orderIndex = (order, field) => {
    const i = order.indexOf(field);
    return i === -1 ? order.length : i;
  };
  day.sort((a, b) => orderIndex(DAY_FIELDS, a.field) - orderIndex(DAY_FIELDS, b.field));
  dossier.sort((a, b) => orderIndex(DOSSIER_FIELDS_ORDER, a.field) - orderIndex(DOSSIER_FIELDS_ORDER, b.field));
  return { day, dossier };
}

/** Blocs critiques encore à confirmer (libellés pour la note au-dessus du CTA). */
export function pendingCriticalLabels(blocks) {
  return (blocks || [])
    .filter((b) => b.critical && !b.confirmed)
    .map((b) => b.label || FIELD_LABELS[b.field] || b.field);
}

/**
 * Tuiles de la grille "Fiche patient" : poids / taille / IMC issus du bloc
 * mesures + une tuile par bloc dossier. L'IMC est purement calculé.
 */
export function buildDossierTiles(blocks) {
  const { dossier } = splitBlocks(blocks);
  const tiles = [];
  const mesures = dossier.find((b) => b.field === "mesures");
  if (mesures) {
    const structured = mesures.structured || {};
    const poidsNr = structured.poids_kg == null;
    const tailleNr = structured.taille_cm == null;
    const imc = computeImcFrontend(structured.poids_kg, structured.taille_cm);
    tiles.push({
      key: "poids",
      blockId: mesures.id,
      label: "Poids",
      value: poidsNr ? NR_TEXT : `${String(structured.poids_kg).replace(".", ",")} kg`,
      status: poidsNr ? "non_renseigne" : mesures.status,
      confirmed: true,
      critical: false,
      danger: false,
      nrable: true,
      calc: false,
    });
    tiles.push({
      key: "taille",
      blockId: mesures.id,
      label: "Taille",
      value: tailleNr ? NR_TEXT : `${String(structured.taille_cm).replace(".", ",")} cm`,
      status: tailleNr ? "non_renseigne" : mesures.status,
      confirmed: true,
      critical: false,
      danger: false,
      nrable: true,
      calc: false,
    });
    tiles.push({
      key: "imc",
      blockId: mesures.id,
      label: "IMC",
      value: imc == null ? "—" : String(imc).replace(".", ","),
      status: "calcule",
      confirmed: true,
      critical: false,
      danger: false,
      nrable: false,
      calc: true,
      missing: imc == null,
    });
  }
  for (const block of dossier) {
    if (block.field === "mesures") continue;
    tiles.push({
      key: block.field,
      blockId: block.id,
      label: block.label || FIELD_LABELS[block.field] || block.field,
      value: block.status === "non_renseigne" || (!block.text && block.synthetic)
        ? (block.status === "non_renseigne" ? NR_TEXT : "À renseigner")
        : block.text,
      status: block.status,
      confirmed: block.confirmed,
      critical: block.critical,
      danger: block.danger,
      nrable: true,
      calc: false,
    });
  }
  return tiles;
}

function findDayText(blocks, field) {
  const block = (blocks || []).find((b) => b.dest === "day" && b.field === field);
  return block ? String(block.text || "").trim() : "";
}

/**
 * Payload d'enregistrement : blocs day -> champs classiques de la fiche,
 * blocs dossier -> dictee.dossier_blocks (upsert fiche patient côté serveur).
 * Le transcript brut n'est JAMAIS inclus.
 */
export function buildConsultationPayloadFromBlocks({
  blocks,
  decisionTags = [],
  date,
  appointmentId = "",
  motifSource = "praticien",
  motifRawPatient = null,
  durationSeconds = null,
  degraded = false,
} = {}) {
  const all = blocks || [];
  const mesures = all.find((b) => b.dest === "dossier" && b.field === "mesures");
  const structured = mesures?.structured || {};
  const imc = computeImcFrontend(structured.poids_kg, structured.taille_cm);

  const dossierBlocks = all
    .filter((b) => b.dest === "dossier")
    // Une tuile synthétique jamais touchée n'est ni une donnée ni une trace.
    .filter((b) => !b.synthetic || b.status === "non_renseigne" || b.status === "modifie")
    .map((b) => ({
      field: b.field,
      text: b.status === "non_renseigne" ? "" : String(b.text || "").trim(),
      status: b.status === "propose" ? "confirme" : b.status,
      structured: b.structured || undefined,
    }));

  return {
    date,
    appointment_id: appointmentId || undefined,
    mode_consultation: "rapide",
    motif: findDayText(all, "motif") || "Consultation",
    motif_source: motifSource,
    motif_raw_patient: motifRawPatient || undefined,
    anamnese: findDayText(all, "elements"),
    examen_clinique: {
      etat_general: "",
      examen_physique: findDayText(all, "examen"),
      constantes: {
        poids_kg: structured.poids_kg ?? null,
        taille_cm: structured.taille_cm ?? null,
        imc,
      },
    },
    impression_clinique: findDayText(all, "impression"),
    conduite_a_tenir: {
      examens_complementaires: [],
      prescription: "",
      orientation: "",
      suivi: { prochain_rdv: null, consignes: findDayText(all, "decision") },
    },
    dictee: {
      consent_patient: true,
      degraded,
      duration_seconds: durationSeconds ?? undefined,
      decision_tags: decisionTags,
      dossier_blocks: dossierBlocks,
    },
  };
}
