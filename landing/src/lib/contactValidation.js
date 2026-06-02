/**
 * Validation téléphone / e-mail alignée sur le backend (`is_valid_patient_phone`,
 * `is_valid_contact_email` dans `backend/db.py` et `backend/guards.py`).
 */
import { normalizePhoneBusinessKey } from "./phoneNormalize";

const CONTACT_EMAIL_PATTERN = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

/** Numéro patient plausible en E.164 (+ puis 8–15 chiffres). */
export function isValidPatientPhone(value) {
  const norm = normalizePhoneBusinessKey(value);
  if (!norm) return false;
  return /^\+\d{8,15}$/.test(norm);
}

/**
 * @param {{ required?: boolean }} opts
 * @returns {{ ok: boolean, message?: string }}
 */
export function validatePatientPhone(value, opts = {}) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return opts.required
      ? { ok: false, message: "Indiquez un numéro de téléphone." }
      : { ok: true };
  }
  if (!isValidPatientPhone(trimmed)) {
    return {
      ok: false,
      message: "Numéro invalide (format attendu : 06 12 34 56 78 ou +33 6 12 34 56 78).",
    };
  }
  return { ok: true };
}

/** E-mail contact (vide = valide si facultatif). */
export function isValidContactEmail(value) {
  const t = String(value ?? "").trim();
  if (!t) return true;
  return CONTACT_EMAIL_PATTERN.test(t);
}

/**
 * @param {{ required?: boolean }} opts
 * @returns {{ ok: boolean, message?: string }}
 */
export function validateContactEmail(value, opts = {}) {
  const t = String(value ?? "").trim();
  if (!t) {
    return opts.required
      ? { ok: false, message: "Indiquez une adresse e-mail." }
      : { ok: true };
  }
  if (!CONTACT_EMAIL_PATTERN.test(t)) {
    return {
      ok: false,
      message: "Email invalide (format attendu : prenom@domaine.fr).",
    };
  }
  return { ok: true };
}

/**
 * @param {{ required?: boolean }} opts
 * @returns {{ ok: boolean, message?: string }}
 */
export function validatePatientBirthDate(value, opts = {}) {
  const v = String(value ?? "").trim();
  if (!v) {
    return opts.required
      ? { ok: false, message: "Indiquez la date de naissance." }
      : { ok: true };
  }
  if (v.length !== 10 || v[4] !== "-" || v[7] !== "-") {
    return {
      ok: false,
      message: "Date de naissance invalide (format attendu : AAAA-MM-JJ).",
    };
  }
  const parsed = new Date(`${v}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return { ok: false, message: "Date de naissance invalide." };
  }
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  if (parsed > today) {
    return { ok: false, message: "La date de naissance ne peut pas être dans le futur." };
  }
  return { ok: true };
}

/**
 * @param {{ required?: boolean, label?: string, maxLength?: number }} opts
 * @returns {{ ok: boolean, message?: string }}
 */
export function validateRequiredText(value, opts = {}) {
  const label = opts.label || "ce champ";
  const t = String(value ?? "").trim();
  if (!t) {
    return opts.required
      ? { ok: false, message: `Indiquez ${label}.` }
      : { ok: true };
  }
  if (opts.maxLength && t.length > opts.maxLength) {
    return { ok: false, message: `${label} trop long.` };
  }
  return { ok: true };
}
