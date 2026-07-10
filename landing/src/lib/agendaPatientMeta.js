/** Libellés métier agenda patient — 3 origines : praticien, agent vocal, page publique. */

export function bookingOriginLabel(code) {
  const c = String(code || "unknown").toLowerCase();
  if (c === "voice") return "Agent vocal";
  if (c === "public_page") return "Page publique";
  if (c === "praticien") return "Praticien";
  if (!code || c === "unknown") return "Non précisée";
  return String(code);
}

export function contactTypeLabel(value) {
  const c = String(value || "").toLowerCase();
  if (c === "phone") return "Téléphone";
  if (c === "email") return "Email";
  if (!c) return "—";
  return value;
}

export function timePreferenceLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const c = raw.toLowerCase();
  if (c.includes("matin")) return "Matin";
  if (c.includes("apres") || c.includes("après") || c.includes("midi")) return "Après-midi";
  if (c.includes("soir")) return "Soir";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function agendaSlotDurationMinutes(slot, tenantDefaultMinutes = 30) {
  const explicit = Number(slot?.duration_minutes);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  const startRaw = slot?.start_iso;
  const endRaw = slot?.end_iso;
  if (startRaw && endRaw) {
    const start = new Date(String(startRaw));
    const end = new Date(String(endRaw));
    if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end > start) {
      return Math.max(5, Math.round((end.getTime() - start.getTime()) / 60000));
    }
  }
  const fallback = Number(tenantDefaultMinutes);
  return Number.isFinite(fallback) && fallback > 0 ? fallback : 30;
}

/** Origine affichée sur la fiche patient (booking_origin prioritaire). */
export function agendaOriginLabel(slot) {
  const fromOrigin = bookingOriginLabel(slot?.booking_origin);
  if (fromOrigin !== "Non précisée") return fromOrigin;

  const src = String(slot?.source || "").toUpperCase();
  if (src === "PAGE_PUBLIQUE") return "Page publique";
  if (src === "UWI" || src === "VAPI" || src === "VOICE") return "Agent vocal";
  if (src === "PRATICIEN" || src === "AGENDA" || src === "CABINET") return "Praticien";
  return "Praticien";
}
