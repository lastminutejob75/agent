// Tags de note structurés, encodés en préfixe dans le texte de la note
// (ex. "[Allergie] pénicilline"). Le texte étant déjà transmis au contexte
// patient, Clara « voit » le tag ; l'UI peut afficher une puce colorée.

export const NOTE_TAGS = [
  { id: "allergie", label: "Allergie", color: "#E11D48", bg: "#FFF1F3" },
  { id: "preference", label: "Préférence", color: "#5B34B0", bg: "#F4F3FF" },
  { id: "rappel", label: "Rappel", color: "#B45309", bg: "#FEF3C7" },
  { id: "important", label: "Important", color: "#B91C1C", bg: "#FEE2E2" },
  { id: "administratif", label: "Administratif", color: "#0369A1", bg: "#E0F2FE" },
];

export function noteTagByLabel(label) {
  const l = String(label || "").trim().toLowerCase();
  return NOTE_TAGS.find((t) => t.label.toLowerCase() === l) || null;
}

/** Ajoute un tag en préfixe du texte (sans doublonner). */
export function prependNoteTag(text, label) {
  const prev = String(text || "");
  const tag = `[${label}]`;
  if (prev.includes(tag)) return prev;
  const body = prev.trim();
  return body ? `${tag} ${body}` : `${tag} `;
}

/** Sépare les tags en tête de note du reste du texte. */
export function parseNoteTags(text) {
  const tags = [];
  let rest = String(text || "");
  const re = /^\s*\[([^\]]+)\]\s*/;
  let m = re.exec(rest);
  while (m) {
    tags.push(m[1].trim());
    rest = rest.slice(m[0].length);
    m = re.exec(rest);
  }
  return { tags, text: rest };
}
