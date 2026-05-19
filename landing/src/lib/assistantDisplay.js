/** Helpers d'affichage pour l'assistante Clara (nom, téléphone, email). */

export function capitalizeAssistantName(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatFrenchPhone(raw) {
  if (!raw) return "";
  const digits = String(raw).replace(/[^\d+]/g, "");
  if (!digits) return "";
  let local = digits;
  if (digits.startsWith("+33") && digits.length === 12) {
    local = "0" + digits.slice(3);
  } else if (digits.startsWith("0033") && digits.length === 13) {
    local = "0" + digits.slice(4);
  }
  if (/^0\d{9}$/.test(local)) {
    return local.match(/.{1,2}/g).join(" ");
  }
  return String(raw).trim();
}

/**
 * Extrait les champs d'affichage depuis la réponse /api/tenant/me.
 */
export function assistantDisplayFromMe(me) {
  const assistantName = capitalizeAssistantName(me?.assistant_name) || "Clara";
  const assistantLive = Boolean(me?.assistant_live);
  const voiceNumber = me?.voice_number || me?.phone_number || "";
  const contactEmail = (me?.contact_email || "").trim();

  return {
    assistantName,
    assistantLive,
    displayPhone: formatFrenchPhone(voiceNumber) || "Numéro à attribuer",
    displayEmail: contactEmail || "Aucun email",
    statusLabel: assistantLive ? "Actif" : "À configurer",
    statusTone: assistantLive ? "green" : "orange",
  };
}
