import { useEffect } from "react";
import {
  validateContactEmail,
  validatePatientBirthDate,
  validatePatientPhone,
  validateRequiredText,
} from "./contactValidation.js";
import { checkPatientDuplicates, hasBlockingPatientDuplicate } from "./patientDuplicateCheck.js";

export const PATIENT_CREATE_FORM_EMPTY = {
  firstName: "",
  lastName: "",
  phone: "",
  email: "",
  birthDate: "",
  treatingPhysicianName: "",
  treatingPhysicianCity: "",
  initialNote: "",
  agendaMotif: "",
  rawCalendarName: "",
  callId: "",
};

export function splitPatientFullName(value) {
  const full = String(value || "").trim();
  if (!full) return { firstName: "", lastName: "" };
  const parts = full.split(/\s+/);
  if (parts.length === 1) return { firstName: "", lastName: parts[0] };
  return { firstName: parts.slice(0, -1).join(" "), lastName: parts.slice(-1)[0] };
}

export function composePatientCreateName({ firstName, lastName }) {
  return [String(firstName || "").trim(), String(lastName || "").trim()].filter(Boolean).join(" ").trim();
}

export function buildPatientCreateFormFromCall(call) {
  // Pour un appelant inconnu, `call.patient.name` est un libellé ("Patient
  // inconnu · 8414") : on ne pré-remplit donc pas nom/prénom dans ce cas
  // (l'extraction depuis la transcription s'en chargera si possible).
  const known = Boolean(call?.patient?.known);
  const fromName = known ? splitPatientFullName(call?.patient?.name) : { firstName: "", lastName: "" };
  const fallbackNote = call?.claraResume || call?.summary || "Aucun résumé Clara disponible.";
  return {
    ...PATIENT_CREATE_FORM_EMPTY,
    firstName: fromName.firstName,
    lastName: fromName.lastName,
    phone: String(call?.phone || call?.patient?.phone || "").trim(),
    initialNote: fallbackNote,
    callId: call?.id || "",
  };
}

export function computePatientCreateFieldErrors(form) {
  const phoneRaw = String(form?.phone || "").trim();
  const phoneCheck = validatePatientPhone(phoneRaw, { required: true });
  const emailCheck = validateContactEmail(form?.email || "", { required: true });
  const birthCheck = validatePatientBirthDate(form?.birthDate || "", { required: true });
  const physicianNameCheck = validateRequiredText(form?.treatingPhysicianName || "", {
    required: true,
    label: "le médecin traitant",
    maxLength: 200,
  });
  const physicianCityCheck = validateRequiredText(form?.treatingPhysicianCity || "", {
    required: true,
    label: "la ville du médecin traitant",
    maxLength: 120,
  });
  return {
    phoneError: phoneCheck.ok ? "" : phoneCheck.message || "Numéro invalide.",
    emailError: emailCheck.ok ? "" : emailCheck.message || "Email invalide.",
    birthDateError: birthCheck.ok ? "" : birthCheck.message || "Date de naissance invalide.",
    physicianNameError: physicianNameCheck.ok ? "" : physicianNameCheck.message || "Médecin traitant requis.",
    physicianCityError: physicianCityCheck.ok ? "" : physicianCityCheck.message || "Ville requise.",
    submitBlocked:
      !phoneCheck.ok
      || !emailCheck.ok
      || !birthCheck.ok
      || !physicianNameCheck.ok
      || !physicianCityCheck.ok,
  };
}

export function isPatientCreateSubmitBlocked(fieldErrors, conflicts) {
  return Boolean(fieldErrors?.submitBlocked) || hasBlockingPatientDuplicate(conflicts);
}

/** Valide le formulaire avant envoi ; retourne les valeurs normalisées ou un message d'erreur. */
export function validatePatientCreateFormForSubmit(form) {
  const errors = computePatientCreateFieldErrors(form);
  if (errors.submitBlocked) {
    const first =
      errors.phoneError
      || errors.emailError
      || errors.birthDateError
      || errors.physicianNameError
      || errors.physicianCityError;
    return { ok: false, message: first || "Complétez le formulaire." };
  }
  const name = composePatientCreateName(form);
  if (name.length < 2) {
    return { ok: false, message: "Indiquez au moins le nom ou le prénom (2 caractères minimum)." };
  }
  return {
    ok: true,
    name,
    firstName: String(form.firstName || "").trim(),
    lastName: String(form.lastName || "").trim(),
    phone: String(form.phone || "").trim(),
    email: String(form.email || "").trim().toLowerCase(),
    birthDate: String(form.birthDate || "").trim(),
    treatingPhysicianName: String(form.treatingPhysicianName || "").trim(),
    treatingPhysicianCity: String(form.treatingPhysicianCity || "").trim(),
  };
}

export function buildCallPatientApiPayload(form, { validatedName, rawName }) {
  const validated = validatePatientCreateFormForSubmit(form);
  if (!validated.ok) return { ok: false, message: validated.message };
  return {
    ok: true,
    body: {
      validated_name: validatedName || validated.name,
      raw_name: (rawName || validated.name).trim() || validated.name,
      first_name: validated.firstName || undefined,
      last_name: validated.lastName || undefined,
      patient_phone: validated.phone,
      patient_email: validated.email,
      birth_date: validated.birthDate,
      treating_physician_name: validated.treatingPhysicianName,
      treating_physician_city: validated.treatingPhysicianCity,
    },
  };
}

export function usePatientCreateDuplicateCheck({ enabled, phone, email, onConflicts }) {
  useEffect(() => {
    if (!enabled) {
      onConflicts([]);
      return undefined;
    }
    const phoneRaw = String(phone || "").trim();
    const emailRaw = String(email || "").trim();
    const phoneCheck = validatePatientPhone(phoneRaw, { required: true });
    if (!phoneCheck.ok && !emailRaw) {
      onConflicts([]);
      return undefined;
    }
    if (!phoneCheck.ok && emailRaw) {
      const emailCheck = validateContactEmail(emailRaw);
      if (!emailCheck.ok) {
        onConflicts([]);
        return undefined;
      }
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({
        phone: phoneCheck.ok ? phoneRaw : "",
        email: emailRaw,
        signal: ctrl.signal,
      })
        .then((res) => {
          if (!cancelled) {
            onConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) onConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [enabled, phone, email, onConflicts]);
}
