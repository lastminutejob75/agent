import { agendaSlotMotif } from "./agendaSlotParse.js";

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function agendaSlotStatusText(slot) {
  return normalizeSearchText(`${slot?.booking_status || ""} ${slot?.status || ""}`);
}

export function agendaSlotSearchText(slot) {
  const motif = agendaSlotMotif(slot);
  return normalizeSearchText(
    [
      motif,
      slot?.type,
      slot?.reason,
      slot?.summary,
      slot?.slot_label,
      slot?.patient,
      slot?.patient_name,
      slot?.reason_category,
    ].join(" "),
  );
}

export function isAgendaSlotCancelled(slot) {
  const status = agendaSlotStatusText(slot);
  return status.includes("cancel") || status.includes("annul");
}

export function isAgendaSlotPending(slot) {
  const status = agendaSlotStatusText(slot);
  return status.includes("pending") || status.includes("a confirmer");
}

export function isAgendaSlotConfirmed(slot) {
  if (isAgendaSlotCancelled(slot) || isAgendaSlotPending(slot)) return false;
  const status = agendaSlotStatusText(slot);
  if (status.includes("confirm")) return true;
  return isClaraManagedSlot(slot);
}

export function isClaraManagedSlot(slot) {
  const src = String(slot?.source || "").toUpperCase();
  if (src === "UWI" || src === "PAGE_PUBLIQUE") return true;
  const origin = String(slot?.booking_origin || "").toLowerCase();
  return origin === "voice" || origin === "public_page";
}

export function isRecoveredAgendaSlot(slot) {
  const text = agendaSlotSearchText(slot);
  return /(?:creneau\s+)?recuper|repris|sauve|suite\s+annulation/.test(text);
}

function isUrgentAgendaSlot(slot) {
  const text = agendaSlotSearchText(slot);
  const priority = normalizeSearchText(slot?.priority || slot?.handoff_priority || "");
  return priority.includes("urgent")
    || /urgence|prioritaire|douleur\s+(?:forte|aigue)/.test(text);
}

function isPrescriptionAgendaSlot(slot) {
  const reason = normalizeSearchText(slot?.reason || "");
  if (reason === "ordonnance") return true;
  const text = agendaSlotSearchText(slot);
  return /ordonnance|renouvel|prescription|traitement|medicament/.test(text);
}

function isDocumentAgendaSlot(slot) {
  const reason = normalizeSearchText(slot?.reason || "");
  if (reason === "admin" || reason.includes("document")) return true;
  const text = agendaSlotSearchText(slot);
  return /document\s+demand|certificat|arret\s+maladie|piece\s+demand/.test(text);
}

/** Pastille agenda : priorité la plus spécifique en premier. */
export function toneForAgendaSlot(slot) {
  if (isAgendaSlotPending(slot)) return "orange";
  if (isRecoveredAgendaSlot(slot)) return "purple";
  if (isUrgentAgendaSlot(slot)) return "red";
  if (isPrescriptionAgendaSlot(slot)) return "indigo";
  if (isDocumentAgendaSlot(slot)) return "blue";
  if (isAgendaSlotConfirmed(slot)) return "green";
  return "teal";
}

export function semanticLabelForAgendaTone(tone) {
  if (tone === "red") return "Urgence";
  if (tone === "blue") return "Documents";
  if (tone === "indigo") return "Ordonnance";
  if (tone === "orange") return "À confirmer";
  if (tone === "purple") return "Récupéré";
  if (tone === "green") return "Confirmé";
  return "Consultation";
}

export const AGENDA_SEMANTIC_LEGEND = [
  { tone: "green", label: "Confirmé" },
  { tone: "orange", label: "À confirmer" },
  { tone: "indigo", label: "Ordonnance / renouvellement" },
  { tone: "blue", label: "Documents demandés" },
  { tone: "red", label: "Urgence / prioritaire" },
  { tone: "purple", label: "Créneau récupéré" },
];

export function countAgendaTones(appointments) {
  const base = { green: 0, orange: 0, purple: 0, red: 0, blue: 0, indigo: 0, teal: 0 };
  (appointments || []).forEach((appt) => {
    const tone = appt?.tone || toneForAgendaSlot(appt);
    base[tone] = (base[tone] || 0) + 1;
  });
  return base;
}

export function patientAgendaRowStatus(slot, start) {
  if (isAgendaSlotCancelled(slot)) return "Annulé";
  if (start instanceof Date && !Number.isNaN(start.getTime()) && start.getTime() >= Date.now()) {
    if (isAgendaSlotPending(slot)) return "À confirmer";
    if (isAgendaSlotConfirmed(slot)) return "Confirmé";
    return "Confirmé";
  }
  return "Passé";
}
