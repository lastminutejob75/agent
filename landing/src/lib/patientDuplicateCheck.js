import { api } from "./api";

export function parsePatientDuplicateError(err) {
  const detail = err?.data?.detail;
  if (detail && typeof detail === "object") {
    return {
      message: String(detail.message || "Ce numéro ou cet email est déjà utilisé par une autre fiche patient."),
      hasConflict: Boolean(detail.has_conflict),
      conflicts: Array.isArray(detail.conflicts) ? detail.conflicts : [],
    };
  }
  return {
    message: String(err?.message || "Conflit avec une fiche patient existante."),
    hasConflict: false,
    conflicts: [],
  };
}

export function formatPatientDuplicateConflict(conflict) {
  if (!conflict) return "";
  const name = String(conflict.display_name || "un autre patient").trim() || "un autre patient";
  if (conflict.field === "email") {
    return `Cet email est déjà utilisé par la fiche de ${name}.`;
  }
  return `Une fiche existe déjà pour ce numéro (${name}).`;
}

export function patientDuplicateDashboardUrl(conflict) {
  const phone = String(conflict?.phone || "").trim();
  if (!phone) return "/app/patient-dashboard";
  return `/app/patient-dashboard?phone=${encodeURIComponent(phone)}`;
}

/** Bloque si le numéro ou l'email appartient déjà à une autre fiche (création agenda / anti-fraude). */
export function hasBlockingPatientDuplicate(conflicts) {
  return (conflicts || []).some((c) => c?.field === "email" || c?.field === "phone");
}

export async function checkPatientDuplicates({ phone, email, excludePhone, signal } = {}) {
  const params = new URLSearchParams();
  const phoneNorm = String(phone || "").trim();
  const emailNorm = String(email || "").trim();
  const excludeNorm = String(excludePhone || "").trim();
  if (phoneNorm) params.set("phone", phoneNorm);
  if (emailNorm) params.set("email", emailNorm);
  if (excludeNorm) params.set("exclude_phone", excludeNorm);
  if (!phoneNorm && !emailNorm) {
    return { has_conflict: false, conflicts: [] };
  }
  return api.tenantCheckPatientDuplicate(`?${params.toString()}`, { signal });
}
