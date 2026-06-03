/**
 * Parseur de préférences / restrictions de disponibilité (page publique UWi).
 * Miroir du module Python backend/appointment_preference_parser.py pour tests front.
 */

export type TimeWindowStrength = "hard" | "soft";

export interface TimeWindow {
  label: string;
  start: string;
  end: string;
  strength: TimeWindowStrength;
}

export interface AppointmentPreferences {
  intent: "book_appointment";
  preferred_days: string[];
  excluded_days: string[];
  preferred_time_windows: TimeWindow[];
  excluded_time_windows: TimeWindow[];
  earliest_date: string | null;
  latest_date: string | null;
  earliest_time: string | null;
  latest_time: string | null;
  urgency: "normal" | "high" | "soon";
  flexibility: "low" | "medium" | "high";
  sorting: "default" | "earliest_available";
  safety_required: boolean;
  safety_message: string | null;
  clarification_needed: string | null;
  raw_user_text: string;
}

const TIME_WINDOW_CATALOG: Record<string, [string, string]> = {
  matin: ["08:00", "12:00"],
  debut_matin: ["08:00", "10:00"],
  milieu_matin: ["10:00", "11:00"],
  fin_matin: ["10:30", "12:00"],
  pause_dejeuner: ["12:00", "14:00"],
  entre_midi_et_deux: ["12:00", "14:00"],
  debut_apres_midi: ["13:30", "15:00"],
  milieu_apres_midi: ["15:00", "16:30"],
  fin_apres_midi: ["16:30", "18:00"],
  fin_de_journee: ["17:00", "19:30"],
  soiree: ["18:00", "19:30"],
  avant_travail: ["08:00", "09:30"],
  apres_travail: ["17:30", "19:30"],
  apres_depot_enfants: ["09:00", "12:00"],
  avant_sortie_ecole: ["08:00", "16:00"],
  recuperation_enfants: ["16:00", "17:30"],
};

const DAYS_FR = [
  "lundi",
  "mardi",
  "mercredi",
  "jeudi",
  "vendredi",
  "samedi",
  "dimanche",
];

const SAFETY_KEYWORDS = [
  "douleur thoracique",
  "mal au coeur",
  "difficulte a respirer",
  "perte de connaissance",
  "urgence vitale",
  "idees suicidaires",
];

const POSITIVE_PHRASES: [string, string][] = [
  ["plutot en fin de journee", "fin_de_journee"],
  ["en fin de journee", "fin_de_journee"],
  ["fin de journee", "fin_de_journee"],
  ["plutot le matin", "matin"],
  ["plutot matinee", "matin"],
  ["pause dejeuner", "pause_dejeuner"],
  ["pendant ma pause dejeuner", "pause_dejeuner"],
  ["entre midi et deux", "entre_midi_et_deux"],
  ["apres le travail", "apres_travail"],
  ["avant le travail", "avant_travail"],
  ["apres-midi", "milieu_apres_midi"],
  ["apres midi", "milieu_apres_midi"],
];

const NEGATIVE_PHRASES: [string, string][] = [
  ["je ne suis pas dispo le matin", "matin"],
  ["je ne suis pas disponible le matin", "matin"],
  ["pas le matin", "matin"],
  ["pas l apres-midi", "milieu_apres_midi"],
  ["pas l apres midi", "milieu_apres_midi"],
  ["je travaille le matin", "matin"],
  ["je travaille l apres-midi", "milieu_apres_midi"],
];

export function normalizeFrText(text: string): string {
  return (text || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

export function emptyPreferences(raw = ""): AppointmentPreferences {
  return {
    intent: "book_appointment",
    preferred_days: [],
    excluded_days: [],
    preferred_time_windows: [],
    excluded_time_windows: [],
    earliest_date: null,
    latest_date: null,
    earliest_time: null,
    latest_time: null,
    urgency: "normal",
    flexibility: "medium",
    sorting: "default",
    safety_required: false,
    safety_message: null,
    clarification_needed: null,
    raw_user_text: raw,
  };
}

function windowDict(label: string, strength: TimeWindowStrength): TimeWindow {
  const [start, end] = TIME_WINDOW_CATALOG[label] || ["08:00", "18:00"];
  return { label, start, end, strength };
}

function appendWindow(
  target: TimeWindow[],
  label: string,
  strength: TimeWindowStrength
): void {
  if (!target.some((w) => w.label === label && w.strength === strength)) {
    target.push(windowDict(label, strength));
  }
}

function checkSafety(norm: string): { required: boolean; message: string | null } {
  if (SAFETY_KEYWORDS.some((k) => norm.includes(k))) {
    return {
      required: true,
      message:
        "Si vous pensez être face à une urgence médicale, appelez immédiatement le 15 ou le 112.",
    };
  }
  return { required: false, message: null };
}

function parseHourLimits(norm: string, result: AppointmentPreferences): void {
  const pasAvant = norm.match(/pas\s+(?:avant|apres|apres)\s+(\d{1,2})\s*h/);
  if (pasAvant) {
    const hour = parseInt(pasAvant[1], 10);
    if (pasAvant[0].includes("avant")) {
      result.earliest_time = `${String(hour).padStart(2, "0")}:00`;
    } else {
      result.latest_time = `${String(hour).padStart(2, "0")}:00`;
    }
  }
  const travaille = norm.match(/travaille\s+jusqu\s*a\s+(\d{1,2})\s*h/);
  if (travaille) {
    const hour = parseInt(travaille[1], 10);
    result.earliest_time = `${String(hour).padStart(2, "0")}:30`;
    appendWindow(result.preferred_time_windows, "fin_de_journee", "soft");
  }
}

function parseDays(raw: string, norm: string, result: AppointmentPreferences): void {
  const pasJour = /(?:pas|eviter|jamais)\s+(?:le\s+)?(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)/gi;
  let m: RegExpExecArray | null;
  while ((m = pasJour.exec(raw)) !== null) {
    const day = m[1].toLowerCase();
    if (!result.excluded_days.includes(day)) result.excluded_days.push(day);
  }
  const plutotJour =
    /(?:plutot|de preference|si possible)\s+(?:le\s+)?(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)/gi;
  while ((m = plutotJour.exec(raw)) !== null) {
    const day = m[1].toLowerCase();
    if (!result.preferred_days.includes(day)) result.preferred_days.push(day);
  }
  if (norm.includes("semaine prochaine")) {
    result.urgency = "soon";
  }
}

export function parseAppointmentPreferences(text: string): AppointmentPreferences {
  const raw = (text || "").trim();
  const result = emptyPreferences(raw);
  if (!raw) return result;

  const norm = normalizeFrText(raw);
  const safety = checkSafety(norm);
  result.safety_required = safety.required;
  result.safety_message = safety.message;

  const sortedPos = [...POSITIVE_PHRASES].sort((a, b) => b[0].length - a[0].length);
  for (const [phrase, label] of sortedPos) {
    if (norm.includes(phrase)) appendWindow(result.preferred_time_windows, label, "soft");
  }

  const sortedNeg = [...NEGATIVE_PHRASES].sort((a, b) => b[0].length - a[0].length);
  for (const [phrase, label] of sortedNeg) {
    if (norm.includes(phrase)) appendWindow(result.excluded_time_windows, label, "hard");
  }

  parseHourLimits(norm, result);
  parseDays(raw, norm, result);

  if (norm.includes("je suis flexible") || norm.includes("peu importe")) {
    result.flexibility = "high";
  }
  if (norm.includes("premier disponible") || norm.includes("premier creneau")) {
    result.flexibility = "high";
    result.sorting = "earliest_available";
  }
  if (
    norm.includes("au plus vite") ||
    norm.includes("le plus tot possible") ||
    norm.includes("urgent")
  ) {
    result.urgency = "high";
  }

  if (norm.includes("pas trop tard") && !result.latest_time) {
    result.clarification_needed =
      "D'accord. Vous préférez plutôt avant 17h ou avant 18h ?";
  }

  return result;
}

export function buildPreferenceAck(prefs: AppointmentPreferences): string {
  const hardMatin = prefs.excluded_time_windows.some(
    (w) => w.label === "matin" && w.strength === "hard"
  );
  const softFin = prefs.preferred_time_windows.some((w) => w.label === "fin_de_journee");
  if (hardMatin && softFin) {
    return (
      "Très bien, je vais éviter les créneaux du matin et vous proposer " +
      "en priorité des rendez-vous en fin de journée."
    );
  }
  if (prefs.earliest_time) {
    return `D'accord, je cherche plutôt après ${prefs.earliest_time}.`;
  }
  if (hardMatin) return "D'accord, je cherche des créneaux en évitant le matin.";
  if (softFin) return "Très bien, je privilégie des créneaux en fin de journée.";
  return "Très bien, je consulte l'agenda avec vos préférences.";
}

export { DAYS_FR, TIME_WINDOW_CATALOG };
