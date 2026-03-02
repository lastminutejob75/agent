/**
 * Configuration des assistants UWI pour l'écran de sélection.
 * Images : /public/avatars/uwi-avatar-[id].png (résolu en /avatars/uwi-avatar-[id].png).
 */
const ASSISTANTS = [
  { id: "sophie", prenom: "Sophie", gender: "f", voice: "Douce et professionnelle" },
  { id: "laura", prenom: "Laura", gender: "f", voice: "Chaleureuse et rassurante" },
  { id: "emma", prenom: "Emma", gender: "f", voice: "Dynamique et claire" },
  { id: "julie", prenom: "Julie", gender: "f", voice: "Calme et professionnelle" },
  { id: "clara", prenom: "Clara", gender: "f", voice: "Précise et efficace" },
  { id: "hugo", prenom: "Hugo", gender: "m", voice: "Analytique et fiable" },
  { id: "julien", prenom: "Julien", gender: "m", voice: "Chaleureux et rassurant" },
  { id: "nicolas", prenom: "Nicolas", gender: "m", voice: "Dynamique et efficace" },
  { id: "alexandre", prenom: "Alexandre", gender: "m", voice: "Charismatique et précis" },
  { id: "thomas", prenom: "Thomas", gender: "m", voice: "Calme et professionnel" },
].map((a) => ({
  ...a,
  img: `/avatars/uwi-avatar-${a.id}.png`,
}));

export default ASSISTANTS;
