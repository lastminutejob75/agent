/**
 * Aligné sur `normalize_phone_number` dans `backend/db.py` pour les comparaisons téléphone /
 * clés d’API (liste patients, filtres agenda, etc.).
 */
export function normalizePhoneBusinessKey(value: unknown): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  let cleaned = raw.replace(/[^\d+]/g, "");
  if (cleaned.startsWith("00")) {
    cleaned = `+${cleaned.slice(2)}`;
  }
  if (cleaned.startsWith("+")) {
    return cleaned;
  }
  if (cleaned.startsWith("0") && cleaned.length === 10) {
    return `+33${cleaned.slice(1)}`;
  }
  /* Même correction que backend : « + » manglé en « ?phone= » (URLSearchParams) → « 336… » brut. */
  if (/^33\d{9}$/.test(cleaned)) {
    return `+${cleaned}`;
  }
  return cleaned;
}
