/** Affichage profil patient (âge, médecin traitant). */

export function computePatientAgeYears(birthDateRaw, today = new Date()) {
  const raw = String(birthDateRaw || "").trim().slice(0, 10);
  if (!raw || raw.length !== 10) return null;
  const birth = new Date(`${raw}T12:00:00`);
  if (Number.isNaN(birth.getTime())) return null;

  const ref = new Date(today);
  ref.setHours(12, 0, 0, 0);

  let age = ref.getFullYear() - birth.getFullYear();
  const monthDiff = ref.getMonth() - birth.getMonth();
  const dayDiff = ref.getDate() - birth.getDate();
  if (monthDiff < 0 || (monthDiff === 0 && dayDiff < 0)) age -= 1;
  if (age < 0 || age > 130) return null;
  return age;
}

export function formatPatientAgeLabel(birthDateRaw, today = new Date()) {
  const age = computePatientAgeYears(birthDateRaw, today);
  if (age == null) return "";
  return `${age} ans`;
}

export function formatBirthDateWithAge(birthDateRaw, formatBirthDateDisplay, today = new Date()) {
  const label = formatBirthDateDisplay(birthDateRaw);
  if (!label || label === "Non renseignée") return label;
  const ageLabel = formatPatientAgeLabel(birthDateRaw, today);
  if (!ageLabel) return label;
  return `${label} · ${ageLabel}`;
}

export function formatPhysicianWithCity(nameRaw, cityRaw) {
  const name = String(nameRaw || "").trim();
  const city = String(cityRaw || "").trim();
  if (name && city) return `${name} · ${city}`;
  if (name) return name;
  if (city) return city;
  return "Non renseigné";
}
