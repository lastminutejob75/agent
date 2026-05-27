/** Tags d'insights patient — alignés sur backend/patient_insights.py */

export const ABSENCE_NOTE_PREFIX = "[ABSENCE-RDV]";

export function buildAbsenceNoteText(startDate) {
  if (!(startDate instanceof Date) || Number.isNaN(startDate.getTime())) {
    return `${ABSENCE_NOTE_PREFIX} Patient absent au rendez-vous.`;
  }
  const label = startDate.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${ABSENCE_NOTE_PREFIX} Patient absent au rendez-vous du ${label}.`;
}

export function normalizePatientInsightTags(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((tag) => ({
      key: String(tag?.key || ""),
      label: String(tag?.label || "").trim(),
      tone: tag?.tone === "red" ? "red" : "blue",
    }))
    .filter((tag) => tag.label);
}
