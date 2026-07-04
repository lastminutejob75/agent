import { useEffect, useMemo, useRef, useState } from "react";
import {
  Stethoscope, Activity, FlaskConical, Sparkles,
  Save, Plus, X, User, Calendar, Heart, Thermometer, Wind, Loader2,
  Scale, AlertTriangle, FileText, ChevronDown, ChevronUp, Search,
  Check, Lock, Mic, Square, Wand2, Phone, ClipboardCheck, LayoutTemplate,
  Bell, MessageSquare, Info,
} from "lucide-react";

import { getMotifSuggestions } from "./motifReformulations.js";

/**
 * Fiche de consultation UWI — avec dictée vocale structurée
 * ==========================================================================
 * La dictée NE REMPLIT JAMAIS directement : elle PROPOSE. Chaque champ extrait
 * arrive en "draft" (panneau de relecture + anneau teal sur le champ concerné),
 * le praticien accepte/refuse au champ ou en bloc. Rien n'atterrit sans validation.
 *
 * Props :
 *  - patient                  : GET /api/tenant/patients/:id
 *  - onSave(payload)          : POST /api/tenant/patients/:id/consultations
 *  - onGenerateSummary(draft) : POST /api/tenant/consultations/summary
 *  - onTranscribe(audioBlob)  : POST /api/tenant/consultations/transcribe
 *                               -> { transcription, extraction, champs_confiance, avertissements }
 *                               (absent => mode démo avec extraction simulée)
 *  - onReformulateMotif({ raw_motif, patient_age?, signal? })
 *                               : POST /api/tenant/consultations/reformulate-motif (niveau B, optionnel)
 */

const C = {
  teal: "#009CA4", tealDark: "#007A80", tealSoft: "#E9F7F7", tealGhost: "#F4FBFB",
  navy: "#0A1628", navy2: "#102240", ink: "#1F2A37", muted: "#69727E", faint: "#98A1AC",
  line: "#E8ECEF", bg: "#F5F7F8", card: "#FFFFFF",
  amber: "#B45309", amberSoft: "#FEF4E4", amberLine: "#F3C98B",
  red: "#B42318", redSoft: "#FEF3F2",
  voice: "#6941C6", voiceDark: "#5B34B0", voiceSoft: "#F4F3FF", voiceLine: "#D9D6FE",
  headerGrad: "linear-gradient(135deg, #0A1628 0%, #102240 55%, #0E3A44 100%)",
  shadow: "0 1px 2px rgba(10,22,40,0.04), 0 4px 16px rgba(10,22,40,0.05)",
  shadowHeader: "0 8px 28px rgba(10,22,40,0.22)",
  focusRing: "0 0 0 3px rgba(0,156,164,0.14)",
};

// ---- Détection de contenu "vide ou générique" (chantier contexte) ----
// Un champ qui ne contient que ces valeurs n'apporte aucun signal clinique.
const GENERIC_VALUES = [
  "consultation", "à compléter", "a completer",
  "non renseigné", "non renseignée", "non renseignés", "non renseignées",
  "aucun", "aucune", "—", "-", "",
  "aucune allergie connue", "aucun traitement en cours",
  "aucun antécédent médical majeur connu", "aucun antecedent medical majeur connu",
  "néant", "neant", "ras", "r.a.s.",
];

export function isEmptyOrGeneric(value) {
  if (value == null) return true;
  const v = String(value).trim().toLowerCase();
  return v.length === 0 || GENERIC_VALUES.includes(v);
}

// Une synthèse type "Dernière consultation: ... | Motif: Consultation | Impression: À compléter"
// est vide si son motif ET son impression sont génériques.
export function isEmptyOrGenericSynthese(value) {
  if (isEmptyOrGeneric(value)) return true;
  const text = String(value);
  const motifMatch = text.match(/motif\s*:\s*([^|]*)/i);
  const impressionMatch = text.match(/impression\s*:\s*([^|]*)/i);
  if (motifMatch || impressionMatch) {
    const motifGeneric = motifMatch ? isEmptyOrGeneric(motifMatch[1]) : true;
    const impressionGeneric = impressionMatch ? isEmptyOrGeneric(impressionMatch[1]) : true;
    return motifGeneric && impressionGeneric;
  }
  return false;
}

const normalizedText = (v) => String(v ?? "").trim().toLowerCase().replace(/\s+/g, " ");

// Champs structurés du bloc "Dossier patient" (hors synthèses, gérées à part)
const DOSSIER_FIELDS = [
  { key: "allergies", label: "Allergies", tone: "alert" },
  { key: "traitements", label: "Traitements en cours", tone: "teal" },
  { key: "points_attention", label: "Points d'attention", tone: "amber" },
  { key: "facteurs_risque", label: "Facteurs de risque", tone: "amber" },
  { key: "antecedents_medicaux", label: "Antécédents médicaux", tone: "neutral" },
  { key: "antecedents_chirurgicaux", label: "Antécédents chirurgicaux", tone: "neutral" },
];

function dossierHasContent(patient) {
  return (
    DOSSIER_FIELDS.some((f) => !isEmptyOrGeneric(patient?.[f.key])) ||
    !isEmptyOrGenericSynthese(patient?.synthese_medicale) ||
    !isEmptyOrGenericSynthese(patient?.dernier_contexte_consultation)
  );
}

const PATIENT_MOCK = {
  id: "pat_001", nom: "M. X", age: 32, sexe: "H",
  antecedents_medicaux: "Aucun antécédent médical majeur connu",
  antecedents_chirurgicaux: "—",
  allergies: "Aucune allergie connue",
  traitements: "Aucun traitement en cours",
};

const EXAMENS_PRESETS = [
  "NFS", "Hémoglobine", "Ferritine sérique", "Fer sérique", "CRP", "Réticulocytes",
  "Frottis sanguin", "Ionogramme", "Créatinine", "Glycémie à jeun", "TSH",
  "Bilan hépatique", "ECG", "Radiographie thoracique",
];

const EMPTY = {
  motif: "", anamnese: "", etatGeneral: "", examenPhysique: "",
  fc: "", pas: "", pad: "", temp: "", spo2: "", fr: "", poids: "", taille: "",
  impression: "", cim10: "", examens: [],
  prescription: "", orientation: "", suiviRdv: "", suiviConsignes: "",
  notePraticien: "", resumeIa: "", contexteIa: "",
};

function toInputString(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function normalizeInitialExamens(items) {
  if (!Array.isArray(items)) return [];
  const seen = new Set();
  return items
    .map((item) => String(item || "").trim())
    .filter((item) => {
      if (!item) return false;
      const key = item.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function buildInitialConsultationState(initialDraft = {}) {
  const prefill = initialDraft?.prefill && typeof initialDraft.prefill === "object"
    ? initialDraft.prefill
    : {};
  const constantes = prefill?.constantes && typeof prefill.constantes === "object"
    ? prefill.constantes
    : {};
  return {
    ...EMPTY,
    motif: toInputString(initialDraft?.motif || prefill?.motif).trim(),
    anamnese: toInputString(prefill?.anamnese),
    etatGeneral: toInputString(prefill?.etat_general),
    examenPhysique: toInputString(prefill?.examen_physique),
    fc: toInputString(constantes?.fc_bpm),
    pas: toInputString(constantes?.pa_systolique),
    pad: toInputString(constantes?.pa_diastolique),
    temp: toInputString(constantes?.temperature_c),
    spo2: toInputString(constantes?.spo2_pct),
    fr: toInputString(constantes?.fr_min),
    poids: toInputString(constantes?.poids_kg),
    taille: toInputString(constantes?.taille_cm),
    impression: toInputString(prefill?.impression_clinique),
    cim10: toInputString(prefill?.cim10),
    examens: normalizeInitialExamens(prefill?.examens_complementaires),
    prescription: toInputString(prefill?.prescription),
    orientation: toInputString(prefill?.orientation),
    suiviRdv: "",
    suiviConsignes: toInputString(prefill?.suivi_consignes),
    notePraticien: toInputString(prefill?.note_praticien),
    resumeIa: toInputString(prefill?.ia_resume),
    contexteIa: toInputString(prefill?.ia_contexte_patient),
  };
}

function buildDictationAccessError(err) {
  const name = String(err?.name || "");
  const message = String(err?.message || "");
  const hasMediaApi = typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  const secureContext = typeof window === "undefined" ? true : Boolean(window.isSecureContext);
  const protocol = typeof window === "undefined" ? "" : String(window.location?.protocol || "");
  let inIframe = false;
  if (typeof window !== "undefined") {
    try {
      inIframe = window.self !== window.top;
    } catch {
      inIframe = true;
    }
  }

  if (!hasMediaApi) {
    return "Micro indisponible dans ce navigateur/contexte. Ouvrez la fiche sur un navigateur récent en HTTPS.";
  }
  if (!secureContext || protocol === "http:") {
    return "Le micro est bloqué car la page n'est pas en HTTPS. Ouvrez l'application en https:// (ou localhost en dev).";
  }
  if (name === "NotAllowedError" || name === "SecurityError") {
    if (inIframe) {
      return "Le micro est bloqué dans cette iframe/preview. Ouvrez la page dans un onglet direct puis autorisez le micro.";
    }
    return "Accès micro refusé.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "Aucun micro détecté. Branchez/activez un micro puis réessayez.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "Le micro est déjà utilisé par une autre application. Fermez les apps audio/visioconf puis réessayez.";
  }
  if (name === "OverconstrainedError") {
    return "Le périphérique micro sélectionné n'est pas disponible. Choisissez un autre micro.";
  }
  if (message) {
    return `Accès micro impossible (${name || "erreur navigateur"}). Vérifiez HTTPS et permissions micro.`;
  }
  return "Accès micro impossible. Vérifiez HTTPS, permissions micro et périphérique audio.";
}

// Métadonnées d'affichage des champs proposés par la dictée (clés plates = state)
const FIELD_LABELS = {
  motif:          { label: "Motif", section: "Motif & anamnèse" },
  anamnese:       { label: "Anamnèse", section: "Motif & anamnèse" },
  etatGeneral:    { label: "État général", section: "Examen clinique" },
  examenPhysique: { label: "Examen physique", section: "Examen clinique" },
  fc:             { label: "FC", section: "Constantes", unit: "bpm" },
  pas:            { label: "PA systolique", section: "Constantes", unit: "mmHg" },
  pad:            { label: "PA diastolique", section: "Constantes", unit: "mmHg" },
  temp:           { label: "Température", section: "Constantes", unit: "°C" },
  spo2:           { label: "SpO₂", section: "Constantes", unit: "%" },
  fr:             { label: "FR", section: "Constantes", unit: "/min" },
  poids:          { label: "Poids", section: "Constantes", unit: "kg" },
  taille:         { label: "Taille", section: "Constantes", unit: "cm" },
  impression:     { label: "Impression clinique", section: "Impression" },
  prescription:   { label: "Prescription", section: "Conduite à tenir" },
  orientation:    { label: "Orientation", section: "Conduite à tenir" },
  suiviConsignes: { label: "Consignes de suivi", section: "Conduite à tenir" },
  examens:        { label: "Examens demandés", section: "Conduite à tenir" },
};

// Chemins dottés (sortie LLM) -> clés plates du state
const PATH_TO_FLAT = {
  "motif": "motif",
  "anamnese": "anamnese",
  "examen_clinique.etat_general": "etatGeneral",
  "examen_clinique.examen_physique": "examenPhysique",
  "examen_clinique.constantes.fc_bpm": "fc",
  "examen_clinique.constantes.pa_systolique": "pas",
  "examen_clinique.constantes.pa_diastolique": "pad",
  "examen_clinique.constantes.temperature_c": "temp",
  "examen_clinique.constantes.spo2_pct": "spo2",
  "examen_clinique.constantes.fr_min": "fr",
  "examen_clinique.constantes.poids_kg": "poids",
  "examen_clinique.constantes.taille_cm": "taille",
  "impression_clinique": "impression",
  "conduite_a_tenir.prescription": "prescription",
  "conduite_a_tenir.orientation": "orientation",
  "conduite_a_tenir.suivi.consignes": "suiviConsignes",
};

// Extraction simulée (mode démo, sans backend) — cas anémie de la fiche source
const DEMO_EXTRACTION = {
  transcription:
    "Alors le patient vient pour une fatigue importante depuis trois semaines, " +
    "il décrit aussi un essoufflement à l'effort et des vertiges au lever. " +
    "À l'examen il est pâle, conjonctives pâles, le cœur est à 102, tension 11/7. " +
    "Je pars sur un syndrome anémique à explorer, je demande une NFS, une ferritine et une CRP. " +
    "Je lui dis de reconsulter si ça s'aggrave.",
  extraction: {
    motif: "Fatigue importante depuis 3 semaines",
    anamnese: "Essoufflement à l'effort et vertiges au lever depuis 3 semaines.",
    examen_clinique: {
      examen_physique: "Pâleur cutanée, conjonctives pâles.",
      constantes: { fc_bpm: 102, pa_systolique: 110, pa_diastolique: 70 },
    },
    impression_clinique: "Syndrome anémique à explorer",
    conduite_a_tenir: {
      examens_complementaires: ["NFS", "Ferritine sérique", "CRP"],
      suivi: { consignes: "Reconsulter si aggravation." },
    },
  },
  champs_confiance: [
    { champ: "motif", niveau: 0.95 },
    { champ: "anamnese", niveau: 0.9 },
    { champ: "examen_clinique.examen_physique", niveau: 0.85 },
    { champ: "examen_clinique.constantes.fc_bpm", niveau: 0.92 },
    { champ: "examen_clinique.constantes.pa_systolique", niveau: 0.7 },
    { champ: "examen_clinique.constantes.pa_diastolique", niveau: 0.7 },
    { champ: "impression_clinique", niveau: 0.8 },
  ],
  avertissements: [],
};

// Modèles rapides — SQUELETTE D'ANAMNÈSE UNIQUEMENT, jamais d'impression.
// Un modèle structure ce qu'il faut explorer ; il ne conclut pas à la place du médecin.
const TEMPLATES = {
  fatigue: {
    label: "Fatigue / asthénie", motif: "Asthénie",
    anamnese: "À explorer : ancienneté et mode d'installation, sommeil, perte de poids, fièvre, dyspnée, pâleur, saignements, contexte psychologique, traitements récents.",
  },
  renouvellement: {
    label: "Renouvellement", motif: "Renouvellement d'ordonnance",
    anamnese: "À vérifier : observance, tolérance, effets indésirables, constantes de suivi, besoin d'adaptation posologique.",
  },
  hta: {
    label: "Suivi HTA", motif: "Suivi d'hypertension artérielle",
    anamnese: "À vérifier : automesures tensionnelles, observance, effets secondaires, hygiène de vie, autres facteurs de risque cardiovasculaire.",
  },
  orl: {
    label: "Infection ORL", motif: "Symptômes ORL",
    anamnese: "À explorer : fièvre, douleur, durée, toux, dysphagie, écoulement, contage, terrain à risque.",
  },
  douleur: {
    label: "Douleur aiguë", motif: "Douleur aiguë",
    anamnese: "À caractériser : localisation, type, intensité (EVA), irradiation, facteurs déclenchants et calmants, signes associés.",
  },
};

// Préparation démo : ce que renverrait GET /context-pack + résumé appel Clara à l'ouverture.
// Le motif est étiqueté "déclaré par le patient" -> proposition, jamais motif médical faisant autorité.
const DEMO_PREFILL = {
  source: "clara",
  resume_appel: "« Je suis très fatigué depuis plusieurs semaines, et je suis essoufflé quand je monte les escaliers. »",
  derniere_consultation: "Aucune consultation récente dans le dossier.",
  documents: "Aucun résultat biologique intégré.",
  extraction: {
    motif: "Fatigue depuis 3 semaines avec essoufflement à l'effort (déclaré à la prise de RDV)",
    anamnese: "Motif déclaré lors de la prise de rendez-vous : fatigue persistante et essoufflement à l'effort à la montée des escaliers.",
  },
  champs_confiance: [],
  avertissements: [],
};

// Sources de proposition draft -> badge affiché dans le panneau de relecture
const SOURCE_META = {
  voice:    { label: "Dictée",        color: "#6941C6", soft: "#F4F3FF" },
  clara:    { label: "Appel Clara",   color: "#175CD3", soft: "#EFF8FF" },
  context:  { label: "Dossier",       color: "#027A48", soft: "#ECFDF3" },
  template: { label: "Modèle",        color: "#B45309", soft: "#FEF4E4" },
};

// ---- Complétude relative au mode (rapide / complet) ----
const COMPLETUDE_REFERENTIELS = {
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

// Ratio de remplissage d'un champ scoré : 0, 0.5 (constantes partielles) ou 1.
function completudeFieldRatio(field, c, hasExistingNextAppointment) {
  switch (field) {
    case "motif":
      return isEmptyOrGeneric(c.motif) ? 0 : 1;
    case "anamnese":
      return isEmptyOrGeneric(c.anamnese) ? 0 : 1;
    case "etat_general":
      return isEmptyOrGeneric(c.etatGeneral) ? 0 : 1;
    case "impression":
      return isEmptyOrGeneric(c.impression) ? 0 : 1;
    case "prescription_ou_examens":
      return !isEmptyOrGeneric(c.prescription) || (c.examens?.length ?? 0) > 0 ? 1 : 0;
    case "constantes": {
      const filled = [c.fc, c.pas, c.pad, c.temp, c.spo2, c.fr, c.poids, c.taille]
        .filter((v) => !isEmptyOrGeneric(v)).length;
      return filled >= 2 ? 1 : filled === 1 ? 0.5 : 0;
    }
    case "suivi":
      // Un RDV de suivi déjà planifié compte comme suivi assuré.
      return !isEmptyOrGeneric(c.suiviConsignes) || !isEmptyOrGeneric(c.suiviRdv) || hasExistingNextAppointment ? 1 : 0;
    default:
      return 0;
  }
}

export function computeCompletude(c, mode, hasExistingNextAppointment = false) {
  const ref = COMPLETUDE_REFERENTIELS[mode === "complete" ? "complet" : "rapide"];
  const score = ref.scored.reduce(
    (sum, { field, weight }) => sum + weight * completudeFieldRatio(field, c, hasExistingNextAppointment),
    0,
  );
  return Math.round(score);
}

// Vérifications de complétude — non bloquantes, jamais diagnostiques (parle workflow).
function runChecks(c) {
  const checks = [];
  const has = (v) => (v ?? "").toString().trim().length > 0;

  if (has(c.motif)) {
    checks.push({ type: "ok", title: "Motif renseigné", text: "La fiche peut être enregistrée." });
  } else {
    checks.push({ type: "warn", title: "Champ requis manquant", text: "À compléter : motif." });
  }
  if ((c.examens?.length ?? 0) > 0 && !has(c.suiviRdv)) {
    checks.push({ type: "warn", title: "Examens demandés sans rendez-vous de suivi",
      text: "Prévoir un contrôle, ou laisser UWI créer un rappel interne à réception des résultats.", action: "creer_rappel" });
  }
  const fcAbn = c.fc && (Number(c.fc) > 100 || Number(c.fc) < 60);
  const spo2Abn = c.spo2 && Number(c.spo2) < 94;
  const tempAbn = c.temp && (Number(c.temp) >= 38 || Number(c.temp) < 35);
  if ((fcAbn || spo2Abn || tempAbn) && !has(c.impression)) {
    checks.push({ type: "info", title: "Constante(s) hors norme relevée(s)",
      text: "Pensez à renseigner l'impression clinique si nécessaire." });
  }
  if (has(c.suiviConsignes)) {
    checks.push({ type: "info", title: "Consignes patient présentes",
      text: "Elles pourront être envoyées par SMS après validation.", action: "envoyer_sms" });
  }
  if (has(c.prescription) && !has(c.suiviConsignes)) {
    checks.push({ type: "info", title: "Prescription sans consignes de suivi",
      text: "Ajouter des consignes peut sécuriser la prise en charge." });
  }
  return checks;
}

export default function FicheConsultationUWI({
  patient = PATIENT_MOCK,
  onSave,
  saving = false,
  existingNextAppointment = null, // { dateLabel?: string, timeLabel?: string, motif?: string }
  onOpenCreateBooking = null, // même flux que "Créer un RDV" sur la fiche patient
  onGenerateSummary,
  onTranscribe,
  onLoadPrefill,   // (patientId) => { source, extraction, champs_confiance, avertissements, resume_appel, ... }
  onReformulateMotif, // ({ raw_motif, patient_age?, signal? }) => { suggestions: string[] } — niveau B LLM
  initialDraft = {}, // { date?: string, motif?: string, appointment_id?: string, source_consultation_id?: string, prefill?: {...} }
}) {
  const today = new Date().toISOString().slice(0, 10);

  const [mode, setMode] = useState(
    initialDraft?.prefill?.mode_consultation === "complete" ? "complete" : "rapide",
  );
  const [date, setDate] = useState(initialDraft?.date || today);
  const [c, setC] = useState(() => buildInitialConsultationState(initialDraft));
  const set = (k) => (v) => setC((s) => ({ ...s, [k]: v }));

  const [examenInput, setExamenInput] = useState("");
  // Dossier vide -> replié par défaut : pas de mur de cartes "—" à l'ouverture.
  const [showDossier, setShowDossier] = useState(() => dossierHasContent(patient));
  const [savePending, setSavePending] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveNotice, setSaveNotice] = useState("");
  const [createFollowupBooking, setCreateFollowupBooking] = useState(false);
  const [followupBookingTime, setFollowupBookingTime] = useState("09:00");
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState(null);

  // ---- Dictée ----
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [draft, setDraft] = useState({});          // { flatKey: { value, confidence } }
  const [transcription, setTranscription] = useState("");
  const [dictWarnings, setDictWarnings] = useState([]);
  const [dictError, setDictError] = useState(null);
  const [demoMode, setDemoMode] = useState(false);
  const [dictIntent, setDictIntent] = useState("consultation"); // "consultation" | "note_libre"
  const [memoNotice, setMemoNotice] = useState("");

  // ---- Préparation UWi (Clara + dossier), chargée à l'ouverture ----
  const [prefill, setPrefill] = useState(null);     // { source, resume_appel, ... } pour la carte
  const [prefillLoading, setPrefillLoading] = useState(false);
  const [prefillUsed, setPrefillUsed] = useState(false);

  // ---- Reformulation du motif patient (traçabilité clara_patient_signals) ----
  const [motifSource, setMotifSource] = useState("praticien"); // 'uwi_suggestion' | 'praticien'
  const [appliedMotifSuggestion, setAppliedMotifSuggestion] = useState(null);
  const [llmMotifSuggestions, setLlmMotifSuggestions] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const streamRef = useRef(null);
  const saveFeedbackRef = useRef(null);
  const revealSaveFeedback = () => {
    if (!saveFeedbackRef.current) return;
    saveFeedbackRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  useEffect(() => {
    setDate(String(initialDraft?.date || today));
    setMode(initialDraft?.prefill?.mode_consultation === "complete" ? "complete" : "rapide");
    setC(buildInitialConsultationState(initialDraft));
    setCreateFollowupBooking(false);
    setFollowupBookingTime("09:00");
    setSaveError("");
    setSaveNotice("");
    setMotifSource("praticien");
    setAppliedMotifSuggestion(null);
  }, [initialDraft?.date, initialDraft?.motif, initialDraft?.source_consultation_id, today]);

  // Changement de patient : le repli par défaut du dossier suit son contenu.
  useEffect(() => {
    setShowDossier(dossierHasContent(patient));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.id]);

  // Chargement de la préparation à l'ouverture de la fiche
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setPrefillLoading(true);
      try {
        const res = onLoadPrefill
          ? await onLoadPrefill(patient.id)
          : await new Promise((r) => setTimeout(() => r(DEMO_PREFILL), 600));
        if (!cancelled && res) setPrefill(res);
      } catch {
        /* prépa indisponible : la fiche reste utilisable normalement */
      } finally {
        if (!cancelled) setPrefillLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.id]);

  const imc = useMemo(() => {
    const p = num(c.poids);
    const t = num(c.taille) ? Number(c.taille) / 100 : null;
    if (!p || !t) return null;
    return (p / (t * t)).toFixed(1);
  }, [c.poids, c.taille]);

  const canSave = c.motif.trim().length > 0;
  const saveBusy = savePending || saving;
  const hasExistingNextAppointment = Boolean(
    existingNextAppointment && String(existingNextAppointment?.dateLabel || "").trim(),
  );
  const hasExternalBookingFlow = typeof onOpenCreateBooking === "function";

  useEffect(() => {
    if (!c.suiviRdv) setCreateFollowupBooking(false);
  }, [c.suiviRdv]);

  useEffect(() => {
    if (hasExistingNextAppointment) {
      setCreateFollowupBooking(false);
      setC((prev) => ({ ...prev, suiviRdv: "" }));
    }
  }, [hasExistingNextAppointment]);

  useEffect(() => {
    if (!saveError && !saveNotice) return;
    if (!saveFeedbackRef.current) return;
    saveFeedbackRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [saveError, saveNotice]);

  // Score de complétude relatif au mode actif : une fiche rapide bien remplie
  // affiche 100 %, pas 50 % calculés sur le référentiel du mode complet.
  const completion = useMemo(
    () => computeCompletude(c, mode, hasExistingNextAppointment),
    [c, mode, hasExistingNextAppointment],
  );

  const pendingKeys = useMemo(() => new Set(Object.keys(draft)), [draft]);
  const checks = useMemo(() => runChecks(c), [c]);

  // Verbatim patient (prise de RDV) : source des chips de reformulation.
  const motifRawPatient = useMemo(() => {
    const fromPrefill = String(prefill?.extraction?.motif || "").trim();
    if (fromPrefill) return fromPrefill;
    const fromCall = String(prefill?.resume_appel || "").trim().replace(/^«\s*|\s*»$/g, "");
    return fromCall || null;
  }, [prefill]);

  const localMotifSuggestions = useMemo(
    () => (motifRawPatient ? getMotifSuggestions(motifRawPatient) : []),
    [motifRawPatient],
  );

  const motifSuggestions = llmMotifSuggestions ?? localMotifSuggestions;

  // Niveau B : chips locales immédiates, remplacées si le LLM répond (< 2 s).
  useEffect(() => {
    if (!motifRawPatient || typeof onReformulateMotif !== "function") {
      setLlmMotifSuggestions(null);
      return undefined;
    }

    let cancelled = false;
    const controller = new AbortController();
    setLlmMotifSuggestions(null);

    (async () => {
      try {
        const res = await onReformulateMotif({
          raw_motif: motifRawPatient,
          patient_age: patient?.age ?? undefined,
          signal: controller.signal,
        });
        if (cancelled) return;
        const next = Array.isArray(res?.suggestions)
          ? res.suggestions.map((s) => String(s || "").trim()).filter(Boolean).slice(0, 3)
          : [];
        if (next.length) setLlmMotifSuggestions(next);
      } catch {
        /* fallback silencieux sur le niveau A */
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [motifRawPatient, onReformulateMotif, patient?.age]);

  const applyMotifSuggestion = (suggestion) => {
    setC((s) => ({ ...s, motif: suggestion }));
    setMotifSource("uwi_suggestion");
    setAppliedMotifSuggestion(suggestion);
  };

  // Édition manuelle du motif : le champ fait foi, la chip perd son état sélectionné.
  const handleMotifChange = (value) => {
    setC((s) => ({ ...s, motif: value }));
    if (value !== appliedMotifSuggestion) {
      setMotifSource("praticien");
      setAppliedMotifSuggestion(null);
    }
  };

  // Suggérer le mode complet sur une fiche vide est du bruit : la suggestion
  // n'apparaît que si des données "mode complet" sont déjà en cours de saisie.
  const suggestCompleteMode = useMemo(() => {
    if (mode !== "rapide") return false;
    const hasConstante = [c.fc, c.pas, c.pad, c.temp, c.spo2, c.fr, c.poids, c.taille]
      .some((v) => String(v ?? "").trim().length > 0);
    return hasConstante || c.anamnese.trim().length > 80;
  }, [mode, c.fc, c.pas, c.pad, c.temp, c.spo2, c.fr, c.poids, c.taille, c.anamnese]);

  // ---------------- Examens ----------------
  const addExamen = (label) => {
    const v = (label ?? examenInput).trim();
    if (!v || c.examens.includes(v)) return;
    setC((s) => ({ ...s, examens: [...s.examens, v] }));
    setExamenInput("");
  };
  const removeExamen = (v) =>
    setC((s) => ({ ...s, examens: s.examens.filter((x) => x !== v) }));

  // ---------------- Dictée : enregistrement ----------------
  const startRecording = async () => {
    setDictError(null);
    setDemoMode(false);
    setMemoNotice("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        stopStream();
        processAudio(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
      setRecSeconds(0);
      timerRef.current = setInterval(() => setRecSeconds((s) => s + 1), 1000);
    } catch (err) {
      const reason = buildDictationAccessError(err);
      // Pas de repli démo automatique si le micro est bloqué:
      // on garde un message actionnable (permissions/https/appareil).
      setDictError(reason);
      setDemoMode(false);
    }
  };

  const stopStream = () => {
    clearInterval(timerRef.current);
    setRecording(false);
    streamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    else stopStream();
  };

  // ---------------- Dictée : traitement ----------------
  const processAudio = async (blob) => {
    setProcessing(true);
    setDictError(null);
    try {
      let result;
      if (onTranscribe && blob) {
        result = await onTranscribe(blob, { transcriptionOnly: dictIntent === "note_libre" });
        setDemoMode(false);
      } else {
        await new Promise((r) => setTimeout(r, 1400)); // simule la latence STT+LLM
        result = DEMO_EXTRACTION;
        setDemoMode(true);
      }
      if (dictIntent === "note_libre") {
        ingestFreeMemo(result);
      } else {
        ingestExtraction(result);
      }
    } catch (err) {
      const detail = String(err?.message || "").trim();
      setDictError(
        detail
          ? `La dictée n'a pas pu être traitée (${detail}). Réessaie ou saisis manuellement.`
          : "La dictée n'a pas pu être traitée. Réessaie ou saisis manuellement.",
      );
    } finally {
      setProcessing(false);
    }
  };

  // Transforme la sortie API (nichée) en draft à plat, sans rien écraser de force.
  // `source` = origine de la proposition (voice/clara/context/template) pour le badge.
  const ingestExtraction = (result, source = "voice") => {
    setTranscription(result?.transcription || "");
    setDictWarnings(result?.avertissements || []);

    const conf = {};
    for (const cc of result?.champs_confiance || []) {
      const flat = PATH_TO_FLAT[cc.champ];
      if (flat) conf[flat] = cc.niveau;
    }

    const ex = result?.extraction || {};
    const additions = {};
    const put = (path, value) => {
      const flat = PATH_TO_FLAT[path];
      if (!flat) return;
      if (value === null || value === undefined || value === "") return;
      additions[flat] = { value: String(value), confidence: conf[flat] ?? null, source };
    };

    put("motif", ex.motif);
    put("anamnese", ex.anamnese);
    const ecl = ex.examen_clinique || {};
    put("examen_clinique.etat_general", ecl.etat_general);
    put("examen_clinique.examen_physique", ecl.examen_physique);
    const cst = ecl.constantes || {};
    put("examen_clinique.constantes.fc_bpm", cst.fc_bpm);
    put("examen_clinique.constantes.pa_systolique", cst.pa_systolique);
    put("examen_clinique.constantes.pa_diastolique", cst.pa_diastolique);
    put("examen_clinique.constantes.temperature_c", cst.temperature_c);
    put("examen_clinique.constantes.spo2_pct", cst.spo2_pct);
    put("examen_clinique.constantes.fr_min", cst.fr_min);
    put("examen_clinique.constantes.poids_kg", cst.poids_kg);
    put("examen_clinique.constantes.taille_cm", cst.taille_cm);
    put("impression_clinique", ex.impression_clinique);
    const cat = ex.conduite_a_tenir || {};
    put("conduite_a_tenir.prescription", cat.prescription);
    put("conduite_a_tenir.orientation", cat.orientation);
    put("conduite_a_tenir.suivi.consignes", cat.suivi?.consignes);

    const exNew = (cat.examens_complementaires || []).filter((t) => !c.examens.includes(t));
    if (exNew.length) additions.examens = { value: exNew, confidence: null, source };

    // merge avec les propositions déjà en attente (ex. dictée après prépa)
    setDraft((prev) => ({ ...prev, ...additions }));
  };

  // Mémo vocal libre : transcription fidèle rangée dans la note praticien.
  // On ne structure rien et on n'écrase rien — c'est la parole du médecin,
  // éditable avant enregistrement (jamais injectée dans les champs cliniques).
  const ingestFreeMemo = (result) => {
    const text = String(result?.transcription || "").trim();
    if (!text) {
      setDictError("Aucune parole détectée.");
      return;
    }
    setC((s) => ({
      ...s,
      notePraticien: s.notePraticien.trim()
        ? `${s.notePraticien.trim()}\n\n${text}`
        : text,
    }));
    setMemoNotice("Mémo vocal ajouté à la note praticien (en bas de la fiche).");
  };

  // ---------------- Préparation UWi : pousser en draft ----------------
  const usePrefill = () => {
    if (!prefill) return;
    ingestExtraction(prefill, prefill.source || "clara");
    setPrefillUsed(true);
  };

  // ---------------- Modèles rapides : pousser en draft (jamais d'impression) ----------------
  const applyTemplate = (key) => {
    const t = TEMPLATES[key];
    if (!t) return;
    setDraft((prev) => {
      const next = { ...prev };
      if (t.motif) next.motif = { value: t.motif, confidence: null, source: "template" };
      if (t.anamnese) {
        const base = c.anamnese?.trim();
        next.anamnese = {
          value: base ? `${base}\n${t.anamnese}` : t.anamnese,
          confidence: null, source: "template",
        };
      }
      return next;
    });
  };

  // ---------------- Validation du draft ----------------
  const acceptField = (key) => {
    const d = draft[key];
    if (!d) return;
    if (key === "examens") {
      setC((s) => ({ ...s, examens: [...s.examens, ...d.value.filter((t) => !s.examens.includes(t))] }));
    } else {
      setC((s) => ({ ...s, [key]: d.value }));
    }
    setDraft((p) => { const n = { ...p }; delete n[key]; return n; });
  };
  const rejectField = (key) =>
    setDraft((p) => { const n = { ...p }; delete n[key]; return n; });

  const acceptAll = () => {
    setC((s) => {
      const next = { ...s };
      for (const [key, d] of Object.entries(draft)) {
        if (key === "examens") next.examens = [...next.examens, ...d.value.filter((t) => !next.examens.includes(t))];
        else next[key] = d.value;
      }
      return next;
    });
    setDraft({});
  };
  const rejectAll = () => setDraft({});

  // ---------------- IA synthèse ----------------
  const buildDraft = () => ({
    patient_id: patient.id,
    appointment_id: initialDraft?.appointment_id || null,
    date,
    mode_consultation: mode,
    motif: c.motif, anamnese: c.anamnese,
    motif_source: motifSource,
    motif_raw_patient: motifRawPatient,
    examen_clinique: {
      etat_general: c.etatGeneral, examen_physique: c.examenPhysique,
      constantes: {
        fc_bpm: num(c.fc), pa_systolique: num(c.pas), pa_diastolique: num(c.pad),
        temperature_c: num(c.temp), spo2_pct: num(c.spo2), fr_min: num(c.fr),
        poids_kg: num(c.poids), taille_cm: num(c.taille), imc: imc ? Number(imc) : null,
      },
    },
    impression_clinique: c.impression, cim10: c.cim10 || null,
    conduite_a_tenir: {
      examens_complementaires: c.examens, prescription: c.prescription,
      orientation: c.orientation,
      suivi: { prochain_rdv: c.suiviRdv || null, consignes: c.suiviConsignes },
    },
    rdv_suivi_booking:
      !hasExternalBookingFlow && !hasExistingNextAppointment && createFollowupBooking && c.suiviRdv
        ? {
            create: true,
            date: c.suiviRdv,
            time: followupBookingTime,
            motif: c.motif?.trim() || "Consultation de suivi",
          }
        : undefined,
  });

  const handleGenerateSummary = async () => {
    if (!onGenerateSummary) { setIaError("Génération non branchée (prop onGenerateSummary absente)."); return; }
    setIaLoading(true); setIaError(null);
    try {
      const res = await onGenerateSummary(buildDraft());
      setC((s) => ({ ...s, resumeIa: res?.resume ?? s.resumeIa, contexteIa: res?.contexte ?? s.contexteIa }));
    } catch { setIaError("Échec de la génération. Réessaie ou complète manuellement."); }
    finally { setIaLoading(false); }
  };

  const handleSave = async () => {
    if (saveBusy) return;
    if (!canSave) {
      setSaveError("Veuillez renseigner le motif avant d'enregistrer.");
      setSaveNotice("");
      revealSaveFeedback();
      return;
    }
    if (!onSave) {
      setSaveError("Enregistrement indisponible (action non branchée).");
      setSaveNotice("");
      revealSaveFeedback();
      return;
    }
    setSavePending(true);
    setSaveError("");
    setSaveNotice("");
    const payload = {
      ...buildDraft(),
      ia_uwi: c.resumeIa || c.contexteIa
        ? { resume_consultation: c.resumeIa, contexte_patient: c.contexteIa, validated_by_practitioner: true }
        : null,
      note_praticien: c.notePraticien || null,
    };
    try {
      const result = await onSave(payload);
      const bookingCreated = Boolean(result?.followupBookingCreated);
      const bookingSkipped = String(result?.followupBookingSkippedReason || "").trim();
      if (bookingCreated) {
        setSaveNotice("Fiche enregistrée et prochain rendez-vous créé.");
      } else if (bookingSkipped) {
        setSaveNotice(`Fiche enregistrée. Prochain rendez-vous: ${bookingSkipped}`);
      } else {
        setSaveNotice("Fiche consultation enregistrée.");
      }
    } catch (err) {
      const msg = String(err?.message || "").trim() || "Impossible d'enregistrer la fiche consultation.";
      setSaveError(msg);
      revealSaveFeedback();
    } finally {
      setSavePending(false);
    }
  };

  const isComplete = mode === "complete";
  const draftCount = Object.keys(draft).length;
  const hasCriticalContext =
    !isEmptyOrGeneric(patient.allergies) ||
    !isEmptyOrGeneric(patient.traitements) ||
    !isEmptyOrGeneric(patient.points_attention) ||
    !isEmptyOrGeneric(patient.facteurs_risque);

  // Garde-fou : tant que des propositions de dictée ne sont ni acceptées ni
  // refusées, on évite qu'une fermeture/rafraîchissement accidentel les perde.
  useEffect(() => {
    if (draftCount === 0 || typeof window === "undefined") return undefined;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [draftCount]);

  return (
    <div className="min-h-screen w-full px-3 py-4 sm:px-4 sm:py-6" style={{ background: "linear-gradient(180deg, #F4F8FA 0%, #EEF4F6 100%)", color: C.ink }}>
      <div className="mx-auto max-w-5xl">

        {/* ================= En-tête ================= */}
        <header className="sticky top-2 z-20 mb-4 overflow-hidden rounded-3xl sm:top-3 sm:mb-6"
          style={{ background: C.headerGrad, boxShadow: C.shadowHeader }}>
          <div className="pointer-events-none absolute -right-14 -top-20 h-52 w-52 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(0,156,164,0.35) 0%, transparent 70%)" }} />
          <div className="relative flex flex-wrap items-center justify-between gap-4 px-6 py-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
                style={{ background: "rgba(0,156,164,0.18)", border: "1px solid rgba(0,156,164,0.45)" }}>
                <Stethoscope size={21} color="#4FD1D9" />
              </div>
              <div className="min-w-0">
                <p className="text-[9px] font-bold uppercase tracking-[0.22em] sm:text-[10px]" style={{ color: "#5FAEB3" }}>Consultation</p>
                <h1 className="mt-0.5 truncate text-lg font-extrabold tracking-tight text-white sm:text-xl">
                  {patient.nom}
                  <span className="ml-2 text-xs font-medium sm:text-sm" style={{ color: "#8FA3B8" }}>
                    {patient.age} ans{patient.sexe ? ` · ${patient.sexe}` : ""}
                  </span>
                </h1>
              </div>
            </div>
            <div className="flex w-full flex-col gap-2.5 sm:w-auto sm:flex-row sm:items-center">
              {draftCount > 0 ? (
                <span className="flex items-center gap-1.5 self-start rounded-full px-3 py-1.5 text-[11px] font-bold sm:self-auto"
                  style={{ background: "rgba(105,65,198,0.20)", color: "#D9D6FE", border: "1px solid rgba(105,65,198,0.55)" }}
                  title="Propositions de dictée à valider avant enregistrement">
                  <Wand2 size={12} /> {draftCount} à relire
                </span>
              ) : null}
              <label className="hidden items-center gap-2 rounded-xl px-3 py-2 sm:flex"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.10)" }}>
                <Calendar size={14} color="#5FAEB3" />
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                  className="bg-transparent text-sm font-medium text-white outline-none [color-scheme:dark]" />
              </label>
              <label className="flex items-center gap-2 rounded-xl px-3 py-2 sm:hidden"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.10)" }}>
                <Calendar size={14} color="#5FAEB3" />
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                  className="w-full bg-transparent text-sm font-medium text-white outline-none [color-scheme:dark]" />
              </label>
              <button onClick={() => void handleSave()} disabled={saveBusy}
                className="flex w-full items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white transition hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
                style={{ background: C.teal, boxShadow: "0 2px 10px rgba(0,156,164,0.35)" }}>
                {saveBusy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
                {saveBusy ? "Enregistrement..." : "Enregistrer la fiche"}
              </button>
              {saveError ? (
                <p className="m-0 rounded-lg px-2 py-1 text-xs font-semibold sm:max-w-[360px]"
                  style={{ background: "rgba(180,35,24,0.14)", color: "#FFD6D3", border: "1px solid rgba(253,162,155,0.5)" }}>
                  {saveError}
                </p>
              ) : null}
            </div>
          </div>
          <div className="relative h-1 w-full" style={{ background: "rgba(255,255,255,0.08)" }}>
            <div className="h-full transition-all duration-500"
              style={{ width: `${completion}%`, background: "linear-gradient(90deg, #009CA4, #4FD1D9)" }} />
          </div>
        </header>

        {/* ================= Mode + statut ================= */}
        <section className="mb-4 flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex rounded-full p-1" style={{ background: "#EBEFF1", border: `1px solid ${C.line}` }}>
            <ModeBtn active={mode === "rapide"} onClick={() => setMode("rapide")}>Rapide</ModeBtn>
            <ModeBtn active={isComplete} onClick={() => setMode("complete")}>Complet</ModeBtn>
          </div>
          {canSave ? (
            <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: C.tealDark }}>
              <Check size={14} /> Prêt à enregistrer · {completion}% (mode {isComplete ? "complet" : "rapide"})
            </span>
          ) : (
            <span className="text-xs font-medium" style={{ color: C.faint }}>
              Motif requis · {completion}% (mode {isComplete ? "complet" : "rapide"})
            </span>
          )}
        </section>

        <div ref={saveFeedbackRef} className="mb-4 rounded-2xl border border-[#D5E8F8] bg-[#F3FAFF] px-4 py-3 text-sm font-semibold text-[#355D87]">
          Après enregistrement, la fiche est ajoutée dans le bloc <strong>"Dossier consultations"</strong> de la fiche patient
          (avec téléchargement PDF possible).
        </div>

        {saveError ? (
          <div className="mb-4 flex items-start gap-2 rounded-2xl px-4 py-3 text-[13px] font-semibold leading-relaxed sm:text-sm"
            style={{ background: C.redSoft, border: "1px solid #FDA29B", color: C.red }}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <span>{saveError}</span>
          </div>
        ) : null}

        <PatientClinicalSnapshot
          patient={patient}
          hasCriticalContext={hasCriticalContext}
          completion={completion}
          isComplete={isComplete}
          showCompleteSuggestion={suggestCompleteMode}
          onCompleteMode={() => setMode("complete")}
        />

        {/* ================= Barre de dictée ================= */}
        <DictationBar
          recording={recording} processing={processing} recSeconds={recSeconds}
          onStart={startRecording} onStop={stopRecording}
          demoMode={demoMode} error={dictError}
          intent={dictIntent} onIntentChange={setDictIntent} memoNotice={memoNotice}
        />

        {/* ================= Préparation UWi (Clara + dossier) ================= */}
        {prefill && !prefillUsed && (
          <PrepCard
            prefill={prefill}
            loading={prefillLoading}
            onUse={usePrefill}
            motifRaw={motifRawPatient}
            suggestions={motifSuggestions}
            appliedSuggestion={appliedMotifSuggestion}
            onApplySuggestion={applyMotifSuggestion}
          />
        )}

        {/* ================= Relecture des propositions (validation) ================= */}
        {draftCount > 0 && (
          <DictationReview
            draft={draft} transcription={transcription} warnings={dictWarnings}
            onAccept={acceptField} onReject={rejectField}
            onAcceptAll={acceptAll} onRejectAll={rejectAll}
          />
        )}

        {/* ================= Dossier patient ================= */}
        <PatientDossierCard patient={patient} show={showDossier} onToggle={() => setShowDossier((s) => !s)} />

        {/* ================= Motif & anamnèse ================= */}
        <Card icon={<FileText size={15} />} title="Motif & anamnèse">
          <TemplateBar onApply={applyTemplate} />
          <Label required pending={pendingKeys.has("motif")}>Motif de consultation</Label>
          <TextArea rows={2} value={c.motif} onChange={handleMotifChange} pending={pendingKeys.has("motif")}
            placeholder="Ex. Fatigue importante évoluant depuis plusieurs semaines." />
          <div className="mt-4">
            <Label pending={pendingKeys.has("anamnese")}>Anamnèse / histoire de la maladie</Label>
            <TextArea rows={isComplete ? 5 : 3} value={c.anamnese} onChange={set("anamnese")} pending={pendingKeys.has("anamnese")}
              placeholder="Symptômes, chronologie, facteurs associés, retentissement…" />
          </div>
        </Card>

        {/* ================= Examen clinique ================= */}
        <Card icon={<Activity size={15} />} title="Examen clinique">
          <Label pending={pendingKeys.has("etatGeneral")}>État général</Label>
          <TextArea rows={2} value={c.etatGeneral} onChange={set("etatGeneral")} pending={pendingKeys.has("etatGeneral")}
            placeholder="Ex. Altéré, asthénie marquée. Conjonctives pâles…" />

          <div className="mt-5 mb-2.5 flex items-baseline justify-between">
            <Label noMargin>Constantes</Label>
            <span className="text-[10px] font-medium" style={{ color: C.faint }}>hors norme = surligné</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Vital icon={<Heart size={13} />} label="FC" unit="bpm" value={c.fc} onChange={set("fc")}
              hint="60–100" pending={pendingKeys.has("fc")} flag={num(c.fc) != null && (Number(c.fc) > 100 || Number(c.fc) < 60)} />
            <PA pas={c.pas} pad={c.pad} setPas={set("pas")} setPad={set("pad")} pending={pendingKeys.has("pas") || pendingKeys.has("pad")} />
            <Vital icon={<Thermometer size={13} />} label="Temp" unit="°C" step="0.1" value={c.temp} onChange={set("temp")}
              hint="36–37.5" pending={pendingKeys.has("temp")} flag={num(c.temp) != null && (Number(c.temp) >= 38 || Number(c.temp) < 35)} />
            <Vital icon={<Wind size={13} />} label="SpO₂" unit="%" value={c.spo2} onChange={set("spo2")}
              hint="≥ 95" pending={pendingKeys.has("spo2")} flag={num(c.spo2) != null && Number(c.spo2) < 94} />
            {isComplete && (
              <>
                <Vital icon={<Wind size={13} />} label="FR" unit="/min" value={c.fr} onChange={set("fr")} hint="12–20" pending={pendingKeys.has("fr")} />
                <Vital icon={<Scale size={13} />} label="Poids" unit="kg" step="0.1" value={c.poids} onChange={set("poids")} pending={pendingKeys.has("poids")} />
                <Vital icon={<Scale size={13} />} label="Taille" unit="cm" value={c.taille} onChange={set("taille")} pending={pendingKeys.has("taille")} />
                <div className="rounded-2xl px-3.5 py-3" style={{ background: C.tealSoft, border: "1px solid #C9E9EA" }}>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.tealDark }}>IMC auto</p>
                  <p className="mt-1.5 text-2xl font-extrabold tabular-nums" style={{ color: C.navy }}>{imc ?? "—"}</p>
                </div>
              </>
            )}
          </div>

          {isComplete && (
            <div className="mt-5">
              <Label pending={pendingKeys.has("examenPhysique")}>Examen physique</Label>
              <TextArea rows={3} value={c.examenPhysique} onChange={set("examenPhysique")} pending={pendingKeys.has("examenPhysique")}
                placeholder="Par appareil : cardio-pulmonaire, abdominal, neuro…" />
            </div>
          )}
        </Card>

        {/* ================= Impression clinique ================= */}
        <Card icon={<Search size={15} />} title="Impression clinique">
          <Label pending={pendingKeys.has("impression")}>Hypothèse / conclusion</Label>
          <TextArea rows={2} value={c.impression} onChange={set("impression")} pending={pendingKeys.has("impression")}
            placeholder="Ex. Syndrome anémique à explorer." />
          {isComplete && (
            <div className="mt-4 max-w-[200px]">
              <Label>Code CIM-10</Label>
              <Input value={c.cim10} onChange={set("cim10")} placeholder="D64.9" />
            </div>
          )}
        </Card>

        {/* ================= Conduite à tenir ================= */}
        <Card icon={<FlaskConical size={15} />} title="Examens & conduite à tenir">
          <Label pending={pendingKeys.has("examens")}>Examens complémentaires demandés</Label>
          {c.examens.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {c.examens.map((e) => (
                <span key={e} className="group flex items-center gap-1.5 rounded-full py-1 pl-3 pr-1.5 text-[13px] font-semibold text-white" style={{ background: C.teal }}>
                  {e}
                  <button onClick={() => removeExamen(e)} className="flex h-4.5 w-4.5 items-center justify-center rounded-full" style={{ background: "rgba(255,255,255,0.18)" }}>
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input value={examenInput} onChange={(e) => setExamenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addExamen())}
              placeholder="Ajouter un examen…"
              className="min-w-0 flex-1 rounded-xl border px-3.5 py-2.5 text-sm outline-none transition" style={{ borderColor: C.line }}
              onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.boxShadow = "none"; }} />
            <button onClick={() => addExamen()}
              className="flex items-center gap-1 rounded-xl px-3.5 py-2.5 text-sm font-bold text-white transition hover:brightness-110 active:scale-[0.98]" style={{ background: C.navy }}>
              <Plus size={15} />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {EXAMENS_PRESETS.filter((p) => !c.examens.includes(p)).map((p) => (
              <button key={p} onClick={() => addExamen(p)}
                className="rounded-full px-3 py-1 text-xs font-semibold transition hover:-translate-y-px"
                style={{ background: C.tealGhost, color: C.tealDark, border: "1px solid #D6EEEF" }}>{p}</button>
            ))}
          </div>

          <Divider />

          <div className="space-y-4">
            <div>
              <Label pending={pendingKeys.has("prescription")}>Prescription / traitement</Label>
              <TextArea rows={2} value={c.prescription} onChange={set("prescription")} pending={pendingKeys.has("prescription")}
                placeholder="Médicaments, posologie, durée…" />
            </div>
            {isComplete && (
              <div>
                <Label pending={pendingKeys.has("orientation")}>Orientation</Label>
                <Input value={c.orientation} onChange={set("orientation")} pending={pendingKeys.has("orientation")}
                  placeholder="Ex. Avis hématologie si anémie confirmée" />
              </div>
            )}
            <div className="rounded-2xl px-4 py-4" style={{ background: "#F5FAFE", border: "1px solid #DCEAF6" }}>
              <div className="mb-3 flex items-center gap-2">
                <span className="rounded-lg px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em]"
                  style={{ background: "#E6F4FF", color: "#1E5A92" }}>
                  Suivi post-consultation
                </span>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label>Prochain rendez-vous</Label>
                  {hasExistingNextAppointment ? (
                    <div className="rounded-xl px-3 py-3 text-sm font-semibold"
                      style={{ background: "#ECFDF3", border: "1px solid #A6E4BE", color: "#166534" }}>
                      Prochain RDV déjà planifié : {existingNextAppointment?.dateLabel}{existingNextAppointment?.timeLabel ? ` à ${existingNextAppointment.timeLabel}` : ""}
                    </div>
                  ) : (
                    <>
                      {hasExternalBookingFlow ? (
                        <button
                          type="button"
                          onClick={onOpenCreateBooking}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-black transition"
                          style={{
                            borderColor: "#DDE7F1",
                            background: "#FFFFFF",
                            color: "#0A1628",
                          }}
                        >
                          <Calendar size={14} />
                          Créer un rendez-vous
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => setCreateFollowupBooking((v) => !v)}
                            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-black transition"
                            style={
                              createFollowupBooking
                                ? {
                                    borderColor: "#009CA4",
                                    background: "#E9FAFC",
                                    color: "#007E8C",
                                  }
                                : {
                                    borderColor: "#DDE7F1",
                                    background: "#FFFFFF",
                                    color: "#0A1628",
                                  }
                            }
                          >
                            <Calendar size={14} />
                            {createFollowupBooking ? "Création du rendez-vous activée" : "Créer le prochain rendez-vous"}
                          </button>
                          {createFollowupBooking ? (
                            <>
                              <div className="mt-3">
                                <Label>Date du rendez-vous</Label>
                                <Input type="date" value={c.suiviRdv} onChange={set("suiviRdv")} />
                              </div>
                              <div className="mt-2">
                                <Label>Heure du rendez-vous</Label>
                                <Input type="time" value={followupBookingTime} onChange={setFollowupBookingTime} />
                              </div>
                            </>
                          ) : null}
                        </>
                      )}
                    </>
                  )}
                </div>
                <div>
                  <Label pending={pendingKeys.has("suiviConsignes")}>Consignes de suivi</Label>
                  <Input value={c.suiviConsignes} onChange={set("suiviConsignes")} pending={pendingKeys.has("suiviConsignes")}
                    placeholder="Ex. Reconsulter si aggravation" />
                  <p className="mt-1 text-[11px] font-medium" style={{ color: C.faint }}>
                    {hasExistingNextAppointment
                      ? "Un rendez-vous de suivi existe déjà. La fiche peut être enregistrée sans en créer un autre."
                      : hasExternalBookingFlow
                        ? "Le rendez-vous de suivi s'ouvre via le même formulaire que sur la fiche patient."
                        : "Si la création échoue, la fiche consultation reste enregistrée."}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* ================= Vérifications avant sauvegarde ================= */}
        <ChecksCard checks={checks} />

        {/* ================= Synthèse UWI ================= */}
        <section className="mb-4 overflow-hidden rounded-3xl" style={{ background: C.card, border: "1px solid #CDEBEC", boxShadow: C.shadow }}>
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
            style={{ background: "linear-gradient(135deg, #E9F7F7 0%, #F4FBFB 100%)", borderBottom: "1px solid #DFF1F2" }}>
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: C.teal }}>
                <Sparkles size={15} color="#fff" />
              </span>
              <div>
                <h2 className="text-sm font-extrabold" style={{ color: C.navy }}>Synthèse UWI</h2>
                <p className="text-[11px]" style={{ color: C.muted }}>Générée à partir de la fiche · relue et validée par vous</p>
              </div>
            </div>
            <button onClick={handleGenerateSummary} disabled={iaLoading || !c.motif.trim()}
              className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold text-white transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40" style={{ background: C.teal }}>
              {iaLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {c.resumeIa ? "Régénérer" : "Générer"}
            </button>
          </div>
          <div className="px-6 py-5">
            {iaError && <p className="mb-3 rounded-xl px-3 py-2 text-xs font-semibold" style={{ background: C.redSoft, color: C.red }}>{iaError}</p>}
            <Label>Résumé de la consultation</Label>
            <TextArea rows={4} value={c.resumeIa} onChange={set("resumeIa")}
              placeholder="Généré automatiquement à l'enregistrement — ou cliquez sur Générer pour relire avant." />
            <div className="mt-4">
              <Label>Contexte patient à mettre à jour</Label>
              <TextArea rows={2} value={c.contexteIa} onChange={set("contexteIa")}
                placeholder="Éléments à retenir pour les prochains appels et RDV." />
            </div>
            <div className="mt-4">
              <Label icon={<Lock size={10} />}>Note interne praticien</Label>
              <TextArea rows={2} value={c.notePraticien} onChange={set("notePraticien")}
                placeholder="Privée — exclue du contexte Clara et des communications patient." />
            </div>
          </div>
        </section>

        {saveNotice ? (
          <div className="mt-5 flex items-start gap-2 rounded-2xl px-4 py-3 text-[13px] font-semibold leading-relaxed sm:text-sm"
            style={{ background: C.tealSoft, border: "1px solid #BFE9EC", color: C.tealDark }}>
            <Check size={15} className="mt-0.5 shrink-0" />
            <span>{saveNotice}</span>
          </div>
        ) : null}

        <p className="mt-6 pb-4 text-center text-[11px]" style={{ color: C.faint }}>
          UWI · les données de consultation restent dans le dossier du cabinet
        </p>
      </div>
    </div>
  );
}

/* ============================ Dictée : composants ============================ */

const WAVE_BARS = [8, 16, 12, 22, 14, 26, 10, 20, 14, 24, 12, 18, 8, 22, 14];

function IntentBtn({ active, disabled, light, onClick, children }) {
  const bg = active ? (light ? "#FFFFFF" : C.voice) : "transparent";
  const color = active
    ? (light ? C.voiceDark : "#FFFFFF")
    : (light ? "rgba(255,255,255,0.72)" : C.muted);
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className="rounded-full px-3 py-1 text-[11px] font-bold transition disabled:cursor-not-allowed"
      style={{ background: bg, color, boxShadow: active && light ? "0 1px 4px rgba(10,22,40,0.18)" : "none" }}>
      {children}
    </button>
  );
}

function DictationBar({ recording, processing, recSeconds, onStart, onStop, demoMode, error, intent, onIntentChange, memoNotice }) {
  const mmss = `${String(Math.floor(recSeconds / 60)).padStart(2, "0")}:${String(recSeconds % 60).padStart(2, "0")}`;
  const isMemo = intent === "note_libre";
  const busy = recording || processing;
  const title = recording
    ? (isMemo ? "Note vocale en cours…" : "Dictée en cours…")
    : processing
      ? (isMemo ? "UWI transcrit votre note…" : "UWI structure votre dictée…")
      : (isMemo ? "Dicter une note libre" : "Dicter la consultation");
  const sub = recording
    ? `${mmss} · ${isMemo ? "parlez, UWI transcrit fidèlement" : "parlez naturellement, UWI range dans les champs"}`
    : processing
      ? (isMemo ? "Transcription fidèle de votre note" : "Transcription puis répartition dans la fiche")
      : (isMemo ? "Transcrite telle quelle dans la note praticien — vous relisez" : "Parlez, UWI remplit la fiche — vous validez ensuite");
  return (
    <div className="mb-4 overflow-hidden rounded-3xl"
      style={{ background: recording ? "#FFFFFF" : C.navy, border: `1px solid ${recording ? C.voiceLine : "transparent"}`, boxShadow: C.shadow }}>

      {/* Identité "votre voix" + sélecteur d'intention */}
      <div className="flex flex-wrap items-center gap-2 px-5 pt-4">
        <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em]"
          style={{ color: recording ? C.voiceDark : "#B9AEEA" }}>
          <Mic size={11} /> Votre voix
        </span>
        <div className="ml-auto flex rounded-full p-0.5"
          style={{ background: recording ? C.voiceSoft : "rgba(255,255,255,0.08)" }}>
          <IntentBtn active={!isMemo} disabled={busy} light={!recording} onClick={() => onIntentChange("consultation")}>
            Consultation
          </IntentBtn>
          <IntentBtn active={isMemo} disabled={busy} light={!recording} onClick={() => onIntentChange("note_libre")}>
            Note libre
          </IntentBtn>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="flex min-w-0 items-center gap-3">
          {recording ? (
            <span className="relative flex h-10 w-10 shrink-0 items-center justify-center">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full" style={{ background: "rgba(180,35,24,0.25)" }} />
              <span className="relative flex h-10 w-10 items-center justify-center rounded-full" style={{ background: C.red }}>
                <Mic size={18} color="#fff" />
              </span>
            </span>
          ) : (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl"
              style={{ background: "rgba(105,65,198,0.20)", border: "1px solid rgba(105,65,198,0.45)" }}>
              {processing ? <Loader2 size={18} color="#B9AEEA" className="animate-spin" /> : <Wand2 size={18} color="#B9AEEA" />}
            </span>
          )}
          <div className="min-w-0">
            <p className="text-sm font-bold" style={{ color: recording ? C.navy : "#fff" }}>{title}</p>
            <p className="truncate text-[11px]" style={{ color: recording ? C.muted : "#8FA3B8" }}>{sub}</p>
          </div>
        </div>

        {recording ? (
          <button onClick={onStop}
            className="flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold text-white transition hover:brightness-110 active:scale-[0.98]" style={{ background: C.red }}>
            <Square size={14} fill="#fff" /> Arrêter
          </button>
        ) : (
          <button onClick={onStart} disabled={processing}
            className="flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
            style={{ background: C.voice, color: "#fff" }}>
            <Mic size={15} /> {processing ? "…" : "Dicter"}
          </button>
        )}
      </div>

      {recording && (
        <div className="flex items-end gap-1 px-5 pb-4" style={{ height: 30 }}>
          {WAVE_BARS.map((h, i) => (
            <span key={i} className="w-1 rounded-full animate-pulse"
              style={{ background: C.voice, height: h, animationDelay: `${(i % 5) * 110}ms` }} />
          ))}
        </div>
      )}

      {error && (
        <div className="mx-4 mb-4 flex items-start gap-2 rounded-xl px-3 py-2.5"
          style={{ background: C.redSoft, border: "1px solid #FDA29B" }}>
          <AlertTriangle size={14} color={C.red} className="mt-0.5 shrink-0" />
          <p className="text-[12px] font-semibold leading-snug" style={{ color: C.red }}>{error}</p>
        </div>
      )}

      {memoNotice && !error && (
        <div className="mx-4 mb-4 flex items-start gap-2 rounded-xl px-3 py-2.5"
          style={{ background: C.voiceSoft, border: `1px solid ${C.voiceLine}` }}>
          <Check size={14} color={C.voiceDark} className="mt-0.5 shrink-0" />
          <p className="text-[12px] font-semibold leading-snug" style={{ color: C.voiceDark }}>{memoNotice}</p>
        </div>
      )}

      {demoMode && !error && (
        <div className="px-5 pb-3 -mt-1">
          <p className="text-[11px] font-medium" style={{ color: recording ? C.muted : "#8FA3B8" }}>
            Mode démonstration · {isMemo ? "transcription simulée" : "extraction simulée"} (aucun backend connecté)
          </p>
        </div>
      )}
    </div>
  );
}

function DictationReview({ draft, transcription, warnings, onAccept, onReject, onAcceptAll, onRejectAll }) {
  const [showTranscript, setShowTranscript] = useState(false);
  const entries = Object.entries(draft);

  return (
    <div className="mb-4 overflow-hidden rounded-3xl" style={{ background: C.card, border: "1px solid #C9E9EA", boxShadow: C.shadow }}>
      {/* bandeau */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5"
        style={{ background: "linear-gradient(135deg, #E9F7F7 0%, #F4FBFB 100%)", borderBottom: "1px solid #DFF1F2" }}>
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: C.teal }}>
            <Wand2 size={15} color="#fff" />
          </span>
          <div>
            <h2 className="text-sm font-extrabold" style={{ color: C.navy }}>
              {entries.length} champ{entries.length > 1 ? "s" : ""} proposé{entries.length > 1 ? "s" : ""}
            </h2>
            <p className="text-[11px]" style={{ color: C.muted }}>Relisez et validez — rien n'est enregistré sans votre accord</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onRejectAll} className="rounded-xl px-3 py-2 text-xs font-bold transition hover:bg-white" style={{ color: C.muted }}>
            Tout ignorer
          </button>
          <button onClick={onAcceptAll}
            className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold text-white transition hover:brightness-110 active:scale-[0.98]" style={{ background: C.teal }}>
            <Check size={14} /> Tout accepter
          </button>
        </div>
      </div>

      {warnings?.length > 0 && (
        <div className="mx-5 mt-3 flex items-start gap-2 rounded-xl px-3 py-2" style={{ background: C.amberSoft, border: `1px solid ${C.amberLine}` }}>
          <AlertTriangle size={13} color={C.amber} className="mt-0.5 shrink-0" />
          <div className="text-[11px] font-medium" style={{ color: C.amber }}>
            {warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        </div>
      )}

      {/* liste des propositions */}
      <div className="divide-y" style={{ borderColor: C.line }}>
        {entries.map(([key, d]) => {
          const meta = FIELD_LABELS[key] || { label: key };
          const lowConf = d.confidence != null && d.confidence < 0.6;
          const src = SOURCE_META[d.source];
          const displayValue = key === "examens" ? d.value.join(", ") : d.value;
          return (
            <div key={key} className="flex items-start gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.faint }}>
                    {meta.section ? `${meta.section} · ` : ""}{meta.label}
                  </span>
                  {src && (
                    <span className="rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase" style={{ background: src.soft, color: src.color }}>
                      {src.label}
                    </span>
                  )}
                  {lowConf && (
                    <span className="rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase" style={{ background: C.amberSoft, color: C.amber }}>
                      à vérifier
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-sm leading-snug" style={{ color: C.ink }}>
                  {displayValue}{meta.unit ? <span style={{ color: C.faint }}> {meta.unit}</span> : null}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <button onClick={() => onReject(key)}
                  className="flex h-7 w-7 items-center justify-center rounded-lg transition hover:bg-slate-100" style={{ color: C.muted }} title="Ignorer">
                  <X size={15} />
                </button>
                <button onClick={() => onAccept(key)}
                  className="flex h-7 w-7 items-center justify-center rounded-lg text-white transition hover:brightness-110" style={{ background: C.teal }} title="Accepter">
                  <Check size={15} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {transcription && (
        <div style={{ borderTop: `1px solid ${C.line}` }}>
          <button onClick={() => setShowTranscript((s) => !s)}
            className="flex w-full items-center justify-between px-5 py-3 text-[11px] font-bold uppercase tracking-wide" style={{ color: C.faint }}>
            Transcription brute
            {showTranscript ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showTranscript && (
            <p className="px-5 pb-4 text-[13px] italic leading-relaxed" style={{ color: C.muted }}>« {transcription} »</p>
          )}
        </div>
      )}
    </div>
  );
}

/* ============================ Préparation UWi ============================ */

function PrepCard({ prefill, loading, onUse, motifRaw, suggestions = [], appliedSuggestion = null, onApplySuggestion }) {
  const src = SOURCE_META[prefill.source] || SOURCE_META.clara;
  const suggestionApplied = Boolean(appliedSuggestion);
  return (
    <div className="mb-4 overflow-hidden rounded-3xl"
      style={{ background: "radial-gradient(circle at top right, rgba(0,156,164,.08), transparent 34%), linear-gradient(180deg,#FFFFFF 0%,#FBFEFE 100%)", border: "1px solid rgba(0,156,164,0.24)", boxShadow: C.shadow }}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-6 py-4" style={{ borderBottom: "1px solid #DFF1F2" }}>
        <div className="flex items-start gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: C.teal }}>
            <Sparkles size={15} color="#fff" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-extrabold" style={{ color: C.navy }}>Préparation UWI</h2>
              <span className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase" style={{ background: src.soft, color: src.color }}>
                <Phone size={9} /> {src.label}
              </span>
            </div>
            <p className="text-[11px]" style={{ color: C.muted }}>Préparé avant la consultation — proposé, vous validez</p>
          </div>
        </div>
        <button onClick={onUse} disabled={loading}
          className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold transition hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
          style={{ background: C.tealSoft, color: C.tealDark, border: "1px solid rgba(0,156,164,0.16)" }}>
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />} Utiliser dans la fiche
        </button>
      </div>
      <div className="grid grid-cols-1 gap-3 px-6 py-4 sm:grid-cols-[1.3fr_0.7fr]">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.faint }}>Déclaré par le patient à la prise de RDV</p>
          {prefill.resume_appel && (
            <p className="mt-1.5 rounded-xl px-3 py-2 text-[13px] italic leading-relaxed"
              style={{ background: "#F7FAFA", border: "1px dashed #D9E6E7", color: C.muted }}>
              {prefill.resume_appel}
            </p>
          )}
          {!suggestionApplied && (
            <p className="mt-2 text-[11px] font-medium" style={{ color: C.amber }}>
              ⚠ Motif déclaré, non médical — à reformuler par le praticien.
            </p>
          )}
          {motifRaw && (
            <p className="mt-2 text-slate-600 italic text-[13px]">« {motifRaw} »</p>
          )}
          {suggestions.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {suggestions.map((s) => {
                const selected = appliedSuggestion === s;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => onApplySuggestion?.(s)}
                    className={
                      selected
                        ? "rounded-full bg-teal-600 text-white px-3 py-1 text-sm cursor-pointer"
                        : "rounded-full border border-teal-600 text-teal-700 hover:bg-teal-50 px-3 py-1 text-sm cursor-pointer"
                    }
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="space-y-2">
          {prefill.derniere_consultation && <PrepLine n="1" title="Dernière consultation" text={prefill.derniere_consultation} />}
          {prefill.documents && <PrepLine n="2" title="Documents" text={prefill.documents} />}
        </div>
      </div>
    </div>
  );
}

function PrepLine({ n, title, text }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl px-3 py-2" style={{ background: "#F8FBFC", border: "1px solid #E9F1F2" }}>
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-bold" style={{ background: C.tealSoft, color: C.tealDark }}>{n}</span>
      <div>
        <strong className="block text-[12px]" style={{ color: C.navy }}>{title}</strong>
        <span className="block text-[12px] leading-snug" style={{ color: C.muted }}>{text}</span>
      </div>
    </div>
  );
}

/* ============================ Modèles rapides ============================ */

function TemplateBar({ onApply }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4">
      <button onClick={() => setOpen((s) => !s)}
        className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.12em] transition hover:opacity-80" style={{ color: C.tealDark }}>
        <LayoutTemplate size={13} /> Modèles rapides
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>
      {open && (
        <>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {Object.entries(TEMPLATES).map(([key, t]) => (
              <button key={key} onClick={() => onApply(key)}
                className="rounded-full px-3 py-1.5 text-xs font-semibold transition hover:-translate-y-px"
                style={{ background: C.tealGhost, color: C.tealDark, border: "1px solid #D6EEEF" }}>
                {t.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px]" style={{ color: C.faint }}>
            Pré-remplit le motif et la trame d'interrogatoire — jamais l'impression clinique.
          </p>
        </>
      )}
    </div>
  );
}

/* ============================ Vérifications avant save ============================ */

const CHECK_STYLE = {
  ok:   { icon: Check,         color: "#027A48", soft: "#ECFDF3" },
  warn: { icon: AlertTriangle, color: "#B45309", soft: "#FEF4E4" },
  info: { icon: Info,          color: "#175CD3", soft: "#EFF8FF" },
};
const CHECK_ACTION = {
  creer_rappel: { label: "Créer un rappel", icon: Bell },
  envoyer_sms:  { label: "Préparer le SMS", icon: MessageSquare },
};

function ChecksCard({ checks }) {
  if (!checks?.length) return null;
  return (
    <Card icon={<ClipboardCheck size={15} />} title="Vérifications avant sauvegarde"
      subtitle="UWI signale les manques possibles, sans décision médicale"
      right={<span className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide" style={{ background: C.tealSoft, color: C.tealDark }}>Complétude</span>}>
      <div className="space-y-2">
        {checks.map((ck, i) => {
          const st = CHECK_STYLE[ck.type] || CHECK_STYLE.info;
          const Ico = st.icon;
          const act = ck.action ? CHECK_ACTION[ck.action] : null;
          const ActIco = act?.icon;
          return (
            <div key={i} className="flex items-start gap-2.5 rounded-2xl px-3.5 py-3" style={{ border: `1px solid ${C.line}`, background: C.card }}>
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full" style={{ background: st.soft, color: st.color }}>
                <Ico size={13} />
              </span>
              <div className="min-w-0 flex-1">
                <strong className="block text-[13px]" style={{ color: C.navy }}>{ck.title}</strong>
                <span className="block text-[12px] leading-snug" style={{ color: C.muted }}>{ck.text}</span>
              </div>
              {act && (
                <button className="flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition hover:bg-slate-50"
                  style={{ color: C.tealDark, border: `1px solid ${C.line}` }}>
                  {ActIco && <ActIco size={12} />} {act.label}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function PatientClinicalSnapshot({ patient, hasCriticalContext, completion, isComplete, showCompleteSuggestion, onCompleteMode }) {
  // Signal uniquement : une tuile ne s'affiche que si elle contient du contenu réel.
  // Exception sécurité : des allergies renseignées s'affichent toujours en premier.
  const highlights = [];
  if (!isEmptyOrGeneric(patient.allergies)) {
    highlights.push({ label: "Allergies", value: patient.allergies, tone: "alert" });
  }
  if (!isEmptyOrGeneric(patient.traitements)) {
    highlights.push({ label: "Traitements", value: patient.traitements, tone: "teal" });
  }
  const attention = !isEmptyOrGeneric(patient.points_attention)
    ? patient.points_attention
    : !isEmptyOrGeneric(patient.facteurs_risque)
      ? patient.facteurs_risque
      : null;
  if (attention) {
    highlights.push({ label: "Attention", value: attention, tone: "amber" });
  }
  if (!isEmptyOrGenericSynthese(patient.synthese_medicale)) {
    highlights.push({ label: "Synthèse médicale", value: patient.synthese_medicale, tone: "teal", wide: true });
  }
  const contextIsEmpty = highlights.length === 0;
  return (
    <section className="mb-4 overflow-hidden rounded-3xl border bg-white shadow-[0_16px_40px_rgba(10,22,40,0.08)]" style={{ borderColor: hasCriticalContext ? "#BFE9EC" : C.line }}>
      <div className="grid gap-0 lg:grid-cols-[1.05fr_1.6fr]">
        <div className="relative overflow-hidden p-5 text-white" style={{ background: "linear-gradient(135deg, #08213E 0%, #073A55 55%, #007A80 100%)" }}>
          <div className="pointer-events-none absolute -right-12 -top-14 h-40 w-40 rounded-full bg-white/10" />
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#72D7DC]">À relire avant examen</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight">{patient.nom}</h2>
          <p className="mt-1 text-sm font-semibold text-white/72">
            {patient.age} ans{patient.sexe ? ` · ${patient.sexe}` : ""} · consultation {isComplete ? "complète" : "rapide"}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full bg-white/12 px-3 py-1.5 text-xs font-black text-white">{completion}% — mode {isComplete ? "complet" : "rapide"}</span>
            {hasCriticalContext ? (
              <span className="rounded-full bg-[#FFF7ED] px-3 py-1.5 text-xs font-black text-[#B45309]">Contexte à surveiller</span>
            ) : (
              <span className="rounded-full bg-white/12 px-3 py-1.5 text-xs font-black text-white/80">Contexte minimal</span>
            )}
          </div>
        </div>
        <div className="grid gap-3 p-4 sm:grid-cols-3">
          {contextIsEmpty ? (
            <div className="sm:col-span-3 flex items-center gap-3 rounded-2xl bg-slate-50 px-4 py-4 text-slate-500">
              <Info size={16} className="shrink-0" />
              <p className="text-[13px] font-medium leading-snug">
                Dossier encore pauvre — il s'enrichira automatiquement à chaque consultation enregistrée.
              </p>
            </div>
          ) : (
            highlights.map((item) => (
              <ClinicalHighlight key={item.label} {...item} />
            ))
          )}
          {showCompleteSuggestion ? (
            <button
              type="button"
              onClick={onCompleteMode}
              className="sm:col-span-3 rounded-2xl border border-[#BFE9EC] bg-[#F0FAFB] px-4 py-3 text-left text-sm font-bold text-[#007A80] transition hover:bg-[#E6F7F8]"
            >
              Suggestion UWI : passer en mode complet si la consultation implique constantes, examen physique ou suivi structuré.
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function PatientDossierCard({ patient, show, onToggle }) {
  const filled = DOSSIER_FIELDS.filter((f) => !isEmptyOrGeneric(patient?.[f.key]));
  const empty = DOSSIER_FIELDS.filter((f) => isEmptyOrGeneric(patient?.[f.key]));

  const synthese = !isEmptyOrGenericSynthese(patient?.synthese_medicale) ? patient.synthese_medicale : null;
  let dernierContexte = !isEmptyOrGenericSynthese(patient?.dernier_contexte_consultation)
    ? patient.dernier_contexte_consultation
    : null;
  // Dédupe stricte : si synthèse et dernier contexte sont identiques, un seul affichage.
  if (synthese && dernierContexte && normalizedText(synthese) === normalizedText(dernierContexte)) {
    dernierContexte = null;
  }

  const hasContent = filled.length > 0 || Boolean(synthese) || Boolean(dernierContexte);

  return (
    <Card icon={<User size={15} />} title="Dossier patient"
      subtitle={hasContent ? "Contexte stable — à relire avant de conclure" : "Aucune donnée structurée pour l'instant"} tinted
      right={
        <button onClick={onToggle}
          className="rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-wide transition hover:opacity-80"
          style={{ color: C.tealDark }}>
          {show ? "Masquer" : "Afficher"}
        </button>
      }>
      {show && (
        hasContent ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {filled.map((f) => (
                <ReadField key={f.key} label={f.label} value={patient[f.key]} tone={f.tone} />
              ))}
              {synthese && <ReadField label="Synthèse médicale" value={synthese} wide tone="teal" />}
              {dernierContexte && <ReadField label="Dernier contexte de consultation" value={dernierContexte} wide />}
            </div>
            {empty.length > 0 && (
              <p className="mt-3 text-[12px] font-medium text-slate-400">
                Non renseignés : {empty.map((f) => f.label.toLowerCase()).join(", ")}
              </p>
            )}
          </>
        ) : (
          <p className="rounded-2xl bg-slate-50 px-4 py-3 text-[13px] font-medium text-slate-500">
            Dossier encore pauvre — il s'enrichira automatiquement à chaque consultation enregistrée.
          </p>
        )
      )}
    </Card>
  );
}

function ClinicalHighlight({ label, value, tone, wide = false }) {
  const styles = {
    alert: { bg: "#FEF3F2", border: "#FDA29B", title: "#B42318", text: "#7A271A" },
    amber: { bg: "#FFFBEB", border: "#FCD34D", title: "#B45309", text: "#78350F" },
    teal: { bg: "#ECFDFB", border: "#99F6E4", title: "#007A80", text: "#134E4A" },
    muted: { bg: "#F8FAFC", border: "#E2E8F0", title: "#64748B", text: "#334155" },
  }[tone] || {};
  return (
    <div className={`rounded-2xl border px-3.5 py-3 ${wide ? "sm:col-span-3" : ""}`} style={{ background: styles.bg, borderColor: styles.border }}>
      <p className="text-[10px] font-black uppercase tracking-[0.16em]" style={{ color: styles.title }}>{label}</p>
      <p className="mt-1.5 line-clamp-4 text-[13px] font-semibold leading-snug" style={{ color: styles.text }}>{value}</p>
    </div>
  );
}

/* ============================ sous-composants ============================ */

function num(v) {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function ModeBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} className="rounded-full px-4 py-1.5 text-[13px] font-bold transition"
      style={{ background: active ? "#FFFFFF" : "transparent", color: active ? C.navy : C.faint, boxShadow: active ? "0 1px 4px rgba(10,22,40,0.10)" : "none" }}>
      {children}
    </button>
  );
}

function Card({ icon, title, subtitle, right, tinted, children }) {
  return (
    <section className="mb-3 rounded-3xl px-4 py-4 sm:mb-4 sm:px-6 sm:py-5" style={{ background: tinted ? "#FBFDFD" : C.card, border: `1px solid ${C.line}`, boxShadow: C.shadow }}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: C.tealSoft, color: C.tealDark }}>{icon}</span>
          <div>
            <h2 className="text-sm font-extrabold tracking-tight" style={{ color: C.navy }}>{title}</h2>
            {subtitle && <p className="text-[11px]" style={{ color: C.muted }}>{subtitle}</p>}
          </div>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Label({ children, required, noMargin, icon, pending }) {
  return (
    <p className={`flex items-center gap-1 text-[11px] font-bold uppercase tracking-[0.14em] sm:text-[10.5px] ${noMargin ? "" : "mb-1.5"}`} style={{ color: C.muted }}>
      {icon}
      {children}
      {required && <span style={{ color: C.teal }}>*</span>}
      {pending && <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full" style={{ background: C.teal }} title="Proposition de dictée en attente" />}
    </p>
  );
}

function Divider() { return <div className="my-5 h-px w-full" style={{ background: C.line }} />; }

function pendingStyle(pending) {
  return pending
    ? { borderColor: C.teal, background: "#FFFFFF", boxShadow: "inset 3px 0 0 #009CA4" }
    : { borderColor: C.line, background: "#FDFDFE" };
}

function TextArea({ value, onChange, pending, ...rest }) {
  return (
    <textarea value={value} onChange={(e) => onChange(e.target.value)}
      className="w-full resize-y rounded-xl border px-3.5 py-2.5 text-[16px] leading-relaxed outline-none transition placeholder:text-slate-300 sm:text-sm"
      style={pendingStyle(pending)}
      onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; e.currentTarget.style.background = "#FFFFFF"; }}
      onBlur={(e) => { const s = pendingStyle(pending); e.currentTarget.style.borderColor = s.borderColor; e.currentTarget.style.boxShadow = s.boxShadow || "none"; e.currentTarget.style.background = s.background; }}
      {...rest} />
  );
}

function Input({ value, onChange, type = "text", pending, ...rest }) {
  return (
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border px-3.5 py-2.5 text-[16px] outline-none transition placeholder:text-slate-300 sm:text-sm"
      style={pendingStyle(pending)}
      onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; e.currentTarget.style.background = "#FFFFFF"; }}
      onBlur={(e) => { const s = pendingStyle(pending); e.currentTarget.style.borderColor = s.borderColor; e.currentTarget.style.boxShadow = s.boxShadow || "none"; e.currentTarget.style.background = s.background; }}
      {...rest} />
  );
}

function ReadField({ label, value, wide = false, tone = "neutral" }) {
  const styles = {
    alert: { bg: "#FFF7F7", border: "#FECACA", label: "#B42318" },
    amber: { bg: "#FFFBEB", border: "#FDE68A", label: "#B45309" },
    teal: { bg: "#F0FAFB", border: "#BFE9EC", label: C.tealDark },
    neutral: { bg: "#FFFFFF", border: C.line, label: C.faint },
  }[tone] || {};
  return (
    <div className={`rounded-2xl px-3.5 py-3 ${wide ? "sm:col-span-2" : ""}`} style={{ background: styles.bg, border: `1px solid ${styles.border}` }}>
      <p className="text-[10px] font-black uppercase tracking-[0.14em]" style={{ color: styles.label }}>{label}</p>
      <p className="mt-1 text-[13px] font-medium leading-snug" style={{ color: C.ink }}>{value}</p>
    </div>
  );
}

function Vital({ icon, label, unit, value, onChange, hint, step, flag, pending }) {
  const border = pending ? C.teal : flag ? C.amberLine : C.line;
  const bg = flag ? C.amberSoft : C.card;
  return (
    <div className="rounded-2xl px-3.5 py-3 transition" style={{ border: `1px solid ${border}`, background: bg, boxShadow: pending ? "inset 0 0 0 1px #009CA4" : "none" }}>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: flag ? C.amber : pending ? C.tealDark : C.faint }}>
          {icon} {label}
        </span>
        {flag ? <AlertTriangle size={12} color={C.amber} /> : pending ? <span className="h-1.5 w-1.5 rounded-full" style={{ background: C.teal }} /> : null}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <input type="number" step={step} value={value} onChange={(e) => onChange(e.target.value)} placeholder="—"
          className="w-full min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300" style={{ color: C.navy }} />
        <span className="text-[11px] font-semibold" style={{ color: C.faint }}>{unit}</span>
      </div>
      {hint && <p className="mt-0.5 text-[10px] tabular-nums" style={{ color: flag ? C.amber : C.faint }}>norme {hint}</p>}
    </div>
  );
}

function PA({ pas, pad, setPas, setPad, pending }) {
  return (
    <div className="rounded-2xl px-3.5 py-3" style={{ border: `1px solid ${pending ? C.teal : C.line}`, background: C.card, boxShadow: pending ? "inset 0 0 0 1px #009CA4" : "none" }}>
      <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: pending ? C.tealDark : C.faint }}>
        <Activity size={13} /> PA {pending && <span className="h-1.5 w-1.5 rounded-full" style={{ background: C.teal }} />}
      </span>
      <div className="mt-1.5 flex items-baseline gap-0.5">
        <input type="number" value={pas} onChange={(e) => setPas(e.target.value)} placeholder="—"
          className="w-11 min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300" style={{ color: C.navy }} />
        <span className="text-lg font-bold" style={{ color: C.faint }}>/</span>
        <input type="number" value={pad} onChange={(e) => setPad(e.target.value)} placeholder="—"
          className="w-11 min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300" style={{ color: C.navy }} />
        <span className="text-[11px] font-semibold" style={{ color: C.faint }}>mmHg</span>
      </div>
      <p className="mt-0.5 text-[10px]" style={{ color: C.faint }}>syst / diast</p>
    </div>
  );
}
