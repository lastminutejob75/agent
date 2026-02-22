/**
 * Format opening_hours en texte lisible avec regroupement des jours consécutifs.
 * Entrée: { "0": { start, end, closed }, ... } ou { monday: ... }
 * Sortie multi-lignes: "Lun–Ven : 08:30–18:00\nSam : Fermé\nDim : Fermé"
 */

const DAYS_ABBREV = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const DAY_KEYS = ["0", "1", "2", "3", "4", "5", "6"];
const DAY_KEYS_ALT = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

function getSlot(oh, dayIndex) {
  if (!oh || typeof oh !== "object") return null;
  const key = DAY_KEYS[dayIndex];
  const alt = DAY_KEYS_ALT[dayIndex];
  const slot = oh[key] ?? oh[alt] ?? oh[alt?.slice(0, 3)];
  return slot && typeof slot === "object" ? slot : null;
}

function normalizeSlotValue(slot) {
  if (!slot || slot.closed) return "Fermé";
  const start = (slot.start || "").trim();
  const end = (slot.end || "").trim();
  if (!start && !end) return "Fermé";
  return `${start || "?"}–${end || "?"}`;
}

/**
 * @param {Record<string, { start?: string, end?: string, closed?: boolean }>} openingHours
 * @returns {string} Lignes séparées par \n (Lun–Ven : 08:30–18:00, etc.)
 */
export function formatOpeningHoursPretty(openingHours) {
  if (!openingHours || typeof openingHours !== "object") return "—";

  const values = DAYS_ABBREV.map((_, i) => {
    const slot = getSlot(openingHours, i);
    return normalizeSlotValue(slot);
  });

  const lines = [];
  let i = 0;
  while (i < 7) {
    const value = values[i];
    let j = i + 1;
    while (j < 7 && values[j] === value) j++;
    const startAbbrev = DAYS_ABBREV[i];
    const endAbbrev = DAYS_ABBREV[j - 1];
    const label = i === j - 1 ? startAbbrev : `${startAbbrev}–${endAbbrev}`;
    lines.push(`${label} : ${value}`);
    i = j;
  }
  return lines.join("\n");
}

/** Variante 1 ligne pour table admin: "Lun–Ven 08:30–18:00 · Sam Fermé · Dim Fermé" */
export function formatOpeningHoursCompact(openingHours) {
  const multiline = formatOpeningHoursPretty(openingHours);
  if (multiline === "—") return "—";
  return multiline
    .split("\n")
    .map((line) => line.replace(" : ", " "))
    .join(" · ");
}

function timeToHours(t) {
  if (!t || typeof t !== "string") return 0;
  const parts = t.trim().split(":");
  const h = parseInt(parts[0], 10) || 0;
  const m = parseInt(parts[1], 10) || 0;
  return h + m / 60;
}

/**
 * Calcule l'amplitude max (end - start) en heures sur la semaine.
 * @param {Record<string, { start?: string, end?: string, closed?: boolean }>} openingHours
 * @returns {number|null}
 */
export function computeMaxDailyAmplitude(openingHours) {
  if (!openingHours || typeof openingHours !== "object") return null;
  let maxH = 0;
  for (let i = 0; i < 7; i++) {
    const slot = getSlot(openingHours, i);
    if (!slot || slot.closed) continue;
    const start = (slot.start || "").trim();
    const end = (slot.end || "").trim();
    if (!start && !end) continue;
    const sh = timeToHours(start);
    const eh = timeToHours(end);
    if (eh > sh) maxH = Math.max(maxH, eh - sh);
  }
  return maxH > 0 ? maxH : null;
}

/**
 * Points de score pour amplitude : >=12h → 20, >=10h → 10, sinon 0.
 * @param {{ max_daily_amplitude?: number | null, opening_hours?: object }} lead
 * @returns {number}
 */
export function getAmplitudeScore(lead) {
  const maxH = lead?.max_daily_amplitude ?? computeMaxDailyAmplitude(lead?.opening_hours ?? {});
  if (maxH == null || maxH < 10) return 0;
  if (maxH >= 12) return 20;
  return 10;
}

/**
 * Badge amplitude pour admin : >=12 "Amplitude élevée", >=10 "Amplitude étendue".
 * @param {{ max_daily_amplitude?: number | null, opening_hours?: object }} lead
 * @returns {{ label: string, className: string } | null}
 */
export function getAmplitudeBadge(lead) {
  const maxH = lead?.max_daily_amplitude ?? computeMaxDailyAmplitude(lead?.opening_hours ?? {});
  if (maxH == null || maxH < 10) return null;
  if (maxH >= 12) return { label: "Amplitude élevée", className: "bg-violet-100 text-violet-800" };
  return { label: "Amplitude étendue", className: "bg-sky-100 text-sky-800" };
}
