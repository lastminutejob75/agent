/** Libellés métier agenda patient (alignés AppAgenda / booking_origin). */

export function bookingOriginLabel(code) {
  const c = String(code || "unknown").toLowerCase();
  if (c === "voice") return "Agent vocal (Clara)";
  if (c === "public_page") return "Page publique";
  if (c === "praticien") return "Espace cabinet";
  if (c === "external") return "Agenda externe";
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

export function agendaSlotDurationMinutes(slot) {
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
  return 30;
}

export function agendaOriginLabel(slot) {
  const origin = bookingOriginLabel(slot?.booking_origin);
  if (origin !== "Non précisée") return origin;
  return agendaLegacySourceLabel(slot);
}

export function agendaLegacySourceLabel(slot) {
  const src = String(slot?.source || "").toUpperCase();
  if (src === "UWI") return "Pris par Clara (UWi)";
  if (src === "PAGE_PUBLIQUE") return "Page publique";
  if (src === "EXTERNAL") return "Agenda cabinet";
  return src || "—";
}
