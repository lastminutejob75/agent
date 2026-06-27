export const COLORS = {
  bg: "#F6F8FB",
  border: "#E5E7EB",
  title: "#0A1628",
  text: "#475569",
  muted: "#94A3B8",
  teal: "#009CA4",
  tealSoft: "#E8F7F7",
};

export const ROUTES = {
  "/app": { title: "Tableau de bord", sub: "Vue d'ensemble de votre cabinet aujourd'hui." },
  "/app/clara": { title: "Clara - Centre de pilotage", sub: "Pilotez Clara : urgences, horaires, absences et consignes." },
  "/app/agenda": { title: "Agenda du cabinet", sub: "Visualisez votre journée, semaine et mois" },
  "/app/demandes": { title: "Demandes patients", sub: "Toutes les demandes en attente de revue" },
  "/app/appels": { title: "Journal des appels", sub: "Historique des appels traités par Clara" },
  "/app/patients": { title: "Patients", sub: "Liste et suivi des dossiers patients" },
  "/app/patient-dashboard": { title: "Patients", sub: "" },
  "/app/settings": { title: "Paramètres", sub: "Configuration du cabinet, transfert d'appel et sécurité" },
  "/app/profile": { title: "Mon cabinet", sub: "Centre de configuration du cabinet medical" },
};

export const NAV_ITEMS = [
  { to: "/app", label: "Accueil", icon: "⌂", end: true },
  { to: "/app/demandes", label: "Demandes", icon: "✉" },
  { to: "/app/agenda", label: "Agenda", icon: "▦" },
  { to: "/app/patient-dashboard", label: "Patients", icon: "●" },
  { to: "/app/appels", label: "Appels", icon: "☎" },
  { to: "/app/profile", label: "Mon cabinet", icon: "⌘" },
  { to: "/app/settings", label: "Paramètres", icon: "⚙" },
];
