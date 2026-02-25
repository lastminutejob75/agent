// Wizard "Créer votre assistant" — 7 steps, diagnostic + projection ROI (1 question par écran, 0 scroll)
import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import UWIFinalization from "../components/UWIFinalization.jsx";

const STORAGE_KEY = "uwi_creer_assistante";
const COMMIT_DONE_KEY = "uwi_creer_assistante_done";
const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

// Diagnostic : minutes/jour pour calcul + label (200 jours ouvrés/an)
const MINUTES_BY_VOLUME = {
  "<10": 15,
  "10-25": 30,
  "25-50": 60,
  "50-100": 90,
  "100+": 120,
  unknown: 30,
};

const LABEL_TIME_GAIN_BY_VOLUME = {
  "<10": "15 min",
  "10-25": "30 min",
  "25-50": "1 h",
  "50-100": "1 à 2 h",
  "100+": "2 h+",
  unknown: "—",
};

const LABEL_CONSULTATIONS_BY_VOLUME = {
  "<10": "1",
  "10-25": "1 à 2",
  "25-50": "2 à 3",
  "50-100": "3 à 4",
  "100+": "4 à 5",
  unknown: "plusieurs",
};

// Message personnalisé selon primary_pain_point (step 6 — wording institutionnel)
const PAIN_POINT_MESSAGE = {
  "Je suis interrompu(e) en consultation par les appels":
    "En filtrant les appels et en supprimant les interruptions pendant vos consultations.",
  "On me laisse beaucoup de messages à rappeler":
    "En répondant aux appels et en réduisant les messages à rappeler.",
  "Mon secrétariat n'arrive pas à suivre":
    "En absorbant une partie du flux d'appels et en automatisant la prise de rendez-vous.",
  "Je passe trop de temps à gérer les rendez-vous":
    "En proposant des créneaux disponibles et en enregistrant automatiquement les rendez-vous.",
  "Je veux mieux orienter les patients (infos, consignes, urgence)":
    "En apportant une réponse immédiate et structurée à chaque appel.",
  Autre: "En réduisant les interruptions et en automatisant la prise de rendez-vous.",
};

/** Formate des minutes pour affichage (15 min, 30 min, 1 h, 1 à 2 h, 2 h+). Préférer passer un entier (ex. Math.round) pour éviter clignotements. */
function formatMinutesForDisplay(min) {
  const m = Math.round(Number(min) || 0);
  if (m >= 120) return "2 h+";
  if (m >= 90) return "1 à 2 h";
  if (m >= 60) return "1 h";
  if (m >= 30) return "30 min";
  if (m >= 15) return "15 min";
  return m <= 0 ? "0 min" : `${m} min`;
}

/**
 * computeDiagnostic({ daily_call_volume, primary_pain_point })
 * Retourne: estimated_minutes_per_day, label_time_gain, annual_hours, label_consultations, message.
 */
function computeDiagnostic(data) {
  const vol = data.daily_call_volume || "unknown";
  const pain = (data.primary_pain_point || "").trim();
  const estimated_minutes_per_day = MINUTES_BY_VOLUME[vol] ?? MINUTES_BY_VOLUME.unknown;
  const label_time_gain = LABEL_TIME_GAIN_BY_VOLUME[vol] || LABEL_TIME_GAIN_BY_VOLUME.unknown;
  const annual_hours = Math.round((estimated_minutes_per_day / 60) * 200);
  const label_consultations = LABEL_CONSULTATIONS_BY_VOLUME[vol] || LABEL_CONSULTATIONS_BY_VOLUME.unknown;
  const message = PAIN_POINT_MESSAGE[pain] || PAIN_POINT_MESSAGE.Autre;

  return {
    estimated_minutes_per_day,
    label_time_gain,
    annual_hours,
    label_consultations,
    message,
  };
}

// Step 6 — Quelle situation vous arrive le plus souvent (1 clic)
const PAIN_POINT_OPTIONS = [
  "Je suis interrompu(e) en consultation par les appels",
  "On me laisse beaucoup de messages à rappeler",
  "Mon secrétariat n'arrive pas à suivre",
  "Je passe trop de temps à gérer les rendez-vous",
  "Je veux mieux orienter les patients (infos, consignes, urgence)",
  "Autre",
];

// Step 1 — Spécialité : slug (stockage/API) + label (affichage). 6 tuiles + Autres (dropdown)
const STEP1_TILES = [
  { slug: "medecin_generaliste", label: "Médecin généraliste" },
  { slug: "dentiste", label: "Dentiste" },
  { slug: "kinesitherapeute", label: "Kinésithérapeute" },
  { slug: "infirmier_liberal", label: "Infirmier(e) libéral(e)" },
  { slug: "osteopathe", label: "Ostéopathe" },
  { slug: "centre_medical", label: "Centre médical / Maison de santé" },
];
const STEP1_OTHER_GROUPS = [
  {
    group: "Médecins spécialistes",
    options: [
      { slug: "pediatre", label: "Pédiatre" },
      { slug: "dermatologue", label: "Dermatologue" },
      { slug: "gynecologue", label: "Gynécologue" },
      { slug: "ophtalmologue", label: "Ophtalmologue" },
      { slug: "cardiologue", label: "Cardiologue" },
      { slug: "orl", label: "ORL" },
      { slug: "psychiatre", label: "Psychiatre" },
      { slug: "neurologue", label: "Neurologue" },
      { slug: "rhumatologue", label: "Rhumatologue" },
      { slug: "gastro_enterologue", label: "Gastro-entérologue" },
    ],
  },
  {
    group: "Paramédical",
    options: [
      { slug: "orthophoniste", label: "Orthophoniste" },
      { slug: "sage_femme", label: "Sage-femme" },
      { slug: "psychologue", label: "Psychologue" },
      { slug: "pedicure_podologue", label: "Pédicure-podologue" },
      { slug: "ergotherapeute", label: "Ergothérapeute" },
      { slug: "dieteticien", label: "Diététicien(ne)" },
    ],
  },
  {
    group: "Structures",
    options: [
      { slug: "cabinet_de_groupe", label: "Cabinet de groupe" },
      { slug: "clinique_privee", label: "Clinique privée" },
      { slug: "imagerie_labo", label: "Laboratoire / Imagerie" },
      { slug: "pharmacie", label: "Pharmacie" },
    ],
  },
  {
    group: "Autre",
    options: [{ slug: "autre", label: "Autre profession de santé…" }],
  },
];

const VOLUME_OPTIONS = [
  { value: "<10", label: "Moins de 10" },
  { value: "10-25", label: "10–25" },
  { value: "25-50", label: "25–50" },
  { value: "50-100", label: "50–100" },
  { value: "100+", label: "Plus de 100" },
  { value: "unknown", label: "Je ne sais pas" },
];
const PRESET_HOURS = {
  0: { start: "08:30", end: "18:00", closed: false },
  1: { start: "08:30", end: "18:00", closed: false },
  2: { start: "08:30", end: "18:00", closed: false },
  3: { start: "08:30", end: "18:00", closed: false },
  4: { start: "08:30", end: "18:00", closed: false },
  5: { start: "", end: "", closed: true },
  6: { start: "", end: "", closed: true },
};
const NAMES_FEMALE = ["Clara", "Sophie", "Emma", "Julie", "Laura"];
const NAMES_MALE = ["Thomas", "Hugo", "Nicolas", "Julien", "Alexandre"];

const defaultOpeningHours = () =>
  Object.fromEntries(
    DAYS.map((_, i) => [String(i), { start: "", end: "", closed: false }])
  );

function getInitialState() {
  return {
    step: 1,
    medical_specialty: "",
    medical_specialty_label: "",
    specialty_other: "",
    daily_call_volume: "",
    primary_pain_point: "",
    opening_hours: defaultOpeningHours(),
    voice_gender: "",
    assistant_name: "",
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return getInitialState();
}

function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_) {}
}

function clearState() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (_) {}
}

export default function CreerAssistante() {
  const [state, setState] = useState(() => {
    if (typeof window === "undefined") return getInitialState();
    const params = new URLSearchParams(window.location.search);
    if (params.get("new") === "1" || params.get("start") === "1") {
      clearState();
      return getInitialState();
    }
    return loadState();
  });
  const [modalOpen, setModalOpen] = useState(false);

  // Retirer ?new=1 de l'URL pour que le rafraîchissement ne réinitialise pas
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("new") === "1" || params.get("start") === "1") {
      params.delete("new");
      params.delete("start");
      const newSearch = params.toString();
      const url = window.location.pathname + (newSearch ? `?${newSearch}` : "") + window.location.hash;
      window.history.replaceState({}, "", url);
    }
  }, []);
  const [modalEmail, setModalEmail] = useState("");
  const [modalPhone, setModalPhone] = useState("");
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitDone, setCommitDone] = useState(() => {
    try {
      const raw = typeof window !== "undefined" && sessionStorage.getItem(COMMIT_DONE_KEY);
      if (raw) {
        const { contact } = JSON.parse(raw);
        return true;
      }
    } catch (_) {}
    return false;
  });
  const [submittedEmail, setSubmittedEmail] = useState(() => {
    try {
      const raw = typeof window !== "undefined" && sessionStorage.getItem(COMMIT_DONE_KEY);
      if (raw) {
        const { contact } = JSON.parse(raw);
        return contact || "";
      }
    } catch (_) {}
    return "";
  });
  const [commitError, setCommitError] = useState("");
  const navigate = useNavigate();

  // Restaurer l'écran de validation si l'utilisateur a déjà soumis (ex. remontage du composant)
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = sessionStorage.getItem(COMMIT_DONE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        if (data != null) {
          setCommitDone(true);
          setSubmittedEmail(data.contact != null ? String(data.contact) : "");
          if (data.lead_id) setState((s) => ({ ...s, lead_id: data.lead_id }));
        }
      }
    } catch (_) {}
  }, []);

  const persist = useCallback((next) => {
    setState((prev) => {
      const out = typeof next === "function" ? next(prev) : { ...prev, ...next };
      saveState(out);
      return out;
    });
  }, []);

  useEffect(() => {
    saveState(state);
  }, [state]);

  const applyPreset = () => {
    persist({ opening_hours: { ...PRESET_HOURS } });
  };

  const atLeastOneOpen = () => {
    const oh = state.opening_hours || defaultOpeningHours();
    return Object.values(oh).some((d) => !d.closed && (d.start || d.end));
  };

  const canContinue = () => {
    if (state.step === 1) return !!(state.medical_specialty || "").trim();
    if (state.step === 2) return !!state.daily_call_volume;
    if (state.step === 3) return atLeastOneOpen();
    if (state.step === 4) return !!state.voice_gender;
    if (state.step === 5) return !!(state.assistant_name || "").trim();
    if (state.step === 6) return !!(state.primary_pain_point || "").trim();
    return true;
  };

  /** Persiste et passe à l'étape suivante (pour les écrans à choix unique : clic = passage auto) */
  const goNext = (updates) => persist({ ...updates, step: Math.min(7, state.step + 1) });

  const volumeMicroText = () => {
    const v = state.daily_call_volume;
    if (v === "25-50" || v === "50-100" || v === "100+")
      return "UWi peut vous faire gagner plusieurs heures par semaine.";
    if (v) return "UWi vous aide à ne manquer aucun appel.";
    return null;
  };

  const handleCommit = async () => {
    setCommitError("");
    setCommitLoading(true);
    try {
      const oh = state.opening_hours || defaultOpeningHours();
      const emailTrim = modalEmail.trim();
      const phoneTrim = modalPhone.trim();
      const payload = {
        email: emailTrim,
        medical_specialty: (state.medical_specialty || "").trim(),
        medical_specialty_label: (state.medical_specialty_label || "").trim() || undefined,
        specialty_other: (state.specialty_other || "").trim() || undefined,
        daily_call_volume: state.daily_call_volume,
        primary_pain_point: (state.primary_pain_point || "").trim(),
        opening_hours: oh,
        voice_gender: state.voice_gender,
        assistant_name: (state.assistant_name || "").trim(),
        source: "landing_cta",
        wants_callback: !!phoneTrim,
        callback_phone: phoneTrim,
      };
      const res = await api.preOnboardingCommit(payload);
      const contact = emailTrim || phoneTrim || "";
      const leadId = (res && res.lead_id) || "";
      try {
        sessionStorage.setItem(COMMIT_DONE_KEY, JSON.stringify({ contact, phone: phoneTrim, lead_id: leadId }));
      } catch (_) {}
      setSubmittedEmail(contact);
      setCommitDone(true);
      if (leadId) setState((s) => ({ ...s, lead_id: leadId }));
      setModalOpen(false);
    } catch (e) {
      setCommitError(e.message || "Erreur enregistrement");
    } finally {
      setCommitLoading(false);
    }
  };

  const handleBackToHome = () => {
    try {
      sessionStorage.removeItem(COMMIT_DONE_KEY);
      clearState();
    } catch (_) {}
    navigate("/", { replace: true });
  };

  // Toujours appeler les mêmes hooks (règles des Hooks React) — avant tout return conditionnel
  const step = Math.min(7, Math.max(1, state.step));
  const isStep7 = step === 7;
  const names = state.voice_gender === "female" ? NAMES_FEMALE : NAMES_MALE;
  const diagnostic = computeDiagnostic({
    daily_call_volume: state.daily_call_volume,
    primary_pain_point: state.primary_pain_point,
  });

  const [animMinutes, setAnimMinutes] = useState(0);
  const [animAnnual, setAnimAnnual] = useState(0);
  useEffect(() => {
    if (!isStep7) return;
    const targetMin = diagnostic.estimated_minutes_per_day;
    const targetAnnual = diagnostic.annual_hours;
    const reduceMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setAnimMinutes(targetMin);
      setAnimAnnual(targetAnnual);
      return;
    }
    setAnimMinutes(0);
    setAnimAnnual(0);
    const duration = 800;
    const start = performance.now();
    let rafId = 0;
    const tick = (now) => {
      const elapsed = now - start;
      const t = Math.min(elapsed / duration, 1);
      const ease = 1 - (1 - t) * (1 - t);
      setAnimMinutes(t >= 1 ? targetMin : ease * targetMin);
      setAnimAnnual(t >= 1 ? targetAnnual : ease * targetAnnual);
      if (t < 1) rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [isStep7, diagnostic.estimated_minutes_per_day, diagnostic.annual_hours]);

  if (commitDone) {
    let leadId = state.lead_id || "";
    let initialPhone = "";
    if (typeof window !== "undefined") {
      try {
        const raw = sessionStorage.getItem(COMMIT_DONE_KEY);
        if (raw) {
          const data = JSON.parse(raw);
          if (data && data.lead_id) leadId = data.lead_id;
          if (data && data.phone) initialPhone = String(data.phone).replace(/\D/g, "").slice(0, 10);
        }
      } catch (_) {}
    }
    return (
      <div className="min-h-screen w-full" style={{ backgroundColor: "#0A1828" }}>
        <UWIFinalization
          leadId={leadId}
          initialPhone={initialPhone}
          assistantName={state.assistant_name || "Emma"}
          practitioner="votre cabinet"
          onComplete={handleBackToHome}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col relative overflow-hidden">
      {/* Header identité landing — retour accueil */}
      <header className="flex-shrink-0 px-6 py-4 relative z-20">
        <div className="max-w-xl mx-auto flex justify-between items-center">
          <Link
            to="/"
            className="text-white font-bold tracking-tight hover:text-teal-400 transition-colors flex items-center gap-2"
          >
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-400 flex items-center justify-center text-slate-950 text-sm font-black">U</span>
            <span>UWi Medical</span>
          </Link>
          <Link to="/login" className="text-sm text-slate-400 hover:text-teal-400 transition-colors">Connexion</Link>
        </div>
      </header>

      {/* Fond identité landing (orbs + grille légère) */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-teal-500/10 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-cyan-400/10 rounded-full blur-[120px]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_40%,transparent_110%)] opacity-50" />
      </div>

      {/* Progress */}
      <div className="flex-shrink-0 px-6 pt-8 pb-2 relative z-10">
        <div className="max-w-xl mx-auto flex justify-between text-xs text-slate-400">
          <span>Étape {step} sur 7</span>
        </div>
        <div className="max-w-xl mx-auto h-1.5 bg-slate-800 rounded-full mt-1 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-teal-500 to-cyan-400 rounded-full transition-all duration-300"
            style={{ width: `${(step / 7) * 100}%` }}
          />
        </div>
      </div>

      {/* Content — no scroll */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-6 overflow-hidden relative z-10">
        <div className="w-full max-w-xl flex flex-col items-center justify-center min-h-0">
          {step === 1 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-2">
                Quelle est votre spécialité ?
              </h2>
              <p className="text-sm text-slate-400 text-center mb-4">
                Nous adaptons automatiquement l'accueil et la prise de rendez-vous à votre spécialité.
              </p>
              <div className="w-full max-w-lg grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                {STEP1_TILES.map(({ slug, label }) => (
                  <button
                    key={slug}
                    type="button"
                    onClick={() => goNext({ medical_specialty: slug, medical_specialty_label: label, specialty_other: "" })}
                    className={`py-4 px-3 rounded-xl border-2 text-sm font-semibold transition-all text-left flex items-center gap-2 ${
                      state.medical_specialty === slug
                        ? "border-teal-500 bg-teal-500/20 text-teal-400"
                        : "border-slate-600 text-slate-300 bg-slate-800/50 hover:border-slate-500"
                    }`}
                  >
                    {state.medical_specialty === slug && (
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center text-slate-950 text-xs">✓</span>
                    )}
                    {label}
                  </button>
                ))}
              </div>
              <div className="w-full max-w-lg">
                <label className="block text-xs font-medium text-slate-500 mb-1.5">Autres spécialités</label>
                <select
                  value={STEP1_TILES.some((t) => t.slug === state.medical_specialty) ? "" : (state.medical_specialty || "")}
                  onChange={(e) => {
                    const slug = e.target.value;
                    if (!slug) {
                      persist({ medical_specialty: "", medical_specialty_label: "", specialty_other: "" });
                      return;
                    }
                    const found = STEP1_OTHER_GROUPS.flatMap((g) => g.options).find((o) => o.slug === slug);
                    goNext({
                      medical_specialty: slug,
                      medical_specialty_label: found ? found.label : slug,
                      specialty_other: slug === "autre" ? state.specialty_other : "",
                    });
                  }}
                  className="w-full rounded-xl border-2 border-slate-600 bg-slate-800/80 px-4 py-3 text-white focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                >
                  <option value="">Choisir…</option>
                  {STEP1_OTHER_GROUPS.map(({ group, options }) => (
                    <optgroup key={group} label={group}>
                      {options.map(({ slug: s, label: l }) => (
                        <option key={s} value={s}>{l}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              {state.medical_specialty === "autre" && (
                <input
                  type="text"
                  value={state.specialty_other || ""}
                  onChange={(e) => persist({ specialty_other: e.target.value })}
                  placeholder="Précisez (optionnel)"
                  className="mt-3 w-full max-w-md rounded-xl border-2 border-slate-600 bg-slate-800/80 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                />
              )}
              {state.medical_specialty && (
                <p className="mt-4 text-sm text-teal-400/90 text-center">
                  Parfait. Nous allons configurer un assistant adapté à votre spécialité.
                </p>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-2">
                Combien d'appels recevez-vous par jour ?
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full mt-6">
                {VOLUME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => goNext({ daily_call_volume: opt.value })}
                    className={`py-4 px-4 rounded-xl border-2 text-sm font-semibold transition-all ${
                      state.daily_call_volume === opt.value
                        ? "border-teal-500 bg-teal-500/20 text-teal-400"
                        : "border-slate-600 text-slate-300 bg-slate-800/50 hover:border-slate-500"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {volumeMicroText() && (
                <p className="text-sm text-slate-400 mt-4 text-center">{volumeMicroText()}</p>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-1">
                À quels horaires votre cabinet est-il ouvert ?
              </h2>
              <p className="text-sm text-slate-400 text-center mb-4">
                Ces horaires servent à informer vos patients et gérer les appels hors ouverture.
              </p>
              <button
                type="button"
                onClick={applyPreset}
                className="text-sm text-teal-400 font-medium mb-4 hover:text-teal-300"
              >
                Cabinet standard (L-V 08:30–18:00)
              </button>
              <div className="w-full space-y-2 max-h-64 overflow-auto rounded-xl border border-slate-700 bg-slate-800/50 p-3">
                {(state.opening_hours || defaultOpeningHours()) &&
                  DAYS.map((label, i) => {
                    const key = String(i);
                    const slot = (state.opening_hours || {})[key] || {
                      start: "",
                      end: "",
                      closed: false,
                    };
                    return (
                      <div
                        key={key}
                        className="flex items-center gap-3 py-2 border-b border-slate-700 last:border-0"
                      >
                        <span className="w-10 text-sm font-medium text-slate-400">{label}</span>
                        <label className="flex items-center gap-2 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            checked={!!slot.closed}
                            onChange={(e) =>
                              persist({
                                opening_hours: {
                                  ...state.opening_hours,
                                  [key]: {
                                    ...slot,
                                    closed: e.target.checked,
                                    ...(e.target.checked ? { start: "", end: "" } : {}),
                                  },
                                },
                              })
                            }
                            className="rounded border-slate-600 bg-slate-700 text-teal-500 focus:ring-teal-500"
                          />
                          Fermé
                        </label>
                        {!slot.closed && (
                          <>
                            <input
                              type="time"
                              value={slot.start}
                              min="06:00"
                              max="22:00"
                              step="900"
                              onChange={(e) =>
                                persist({
                                  opening_hours: {
                                    ...state.opening_hours,
                                    [key]: { ...slot, start: e.target.value },
                                  },
                                })
                              }
                              className="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
                            />
                            <span className="text-slate-500">–</span>
                            <input
                              type="time"
                              value={slot.end}
                              min="06:00"
                              max="22:00"
                              step="900"
                              onChange={(e) =>
                                persist({
                                  opening_hours: {
                                    ...state.opening_hours,
                                    [key]: { ...slot, end: e.target.value },
                                  },
                                })
                              }
                              className="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
                            />
                          </>
                        )}
                      </div>
                    );
                  })}
              </div>
              {/* Boutons uniquement sur l'écran horaires — juste sous le formulaire */}
              <div className="max-w-xl w-full flex justify-between gap-4 mt-6">
                <button
                  type="button"
                  onClick={() => persist({ step: 2 })}
                  className="px-5 py-2.5 rounded-xl border-2 border-slate-600 text-slate-300 font-medium hover:bg-slate-800/80 hover:border-slate-500"
                >
                  Retour
                </button>
                <button
                  type="button"
                  onClick={() => persist({ step: 4 })}
                  disabled={!atLeastOneOpen()}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  Continuer
                </button>
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-6">
                Quelle voix pour votre assistant ?
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                <button
                  type="button"
                  onClick={() => goNext({ voice_gender: "female" })}
                  className={`p-6 rounded-2xl border-2 text-left transition-all ${
                    state.voice_gender === "female"
                      ? "border-teal-500 bg-teal-500/20"
                      : "border-slate-600 bg-slate-800/50 hover:border-slate-500"
                  }`}
                >
                  <div className="font-semibold text-white">Voix féminine</div>
                  <div className="text-sm text-slate-400 mt-1">douce et rassurante</div>
                </button>
                <button
                  type="button"
                  onClick={() => goNext({ voice_gender: "male" })}
                  className={`p-6 rounded-2xl border-2 text-left transition-all ${
                    state.voice_gender === "male"
                      ? "border-teal-500 bg-teal-500/20"
                      : "border-slate-600 bg-slate-800/50 hover:border-slate-500"
                  }`}
                >
                  <div className="font-semibold text-white">Voix masculine</div>
                  <div className="text-sm text-slate-400 mt-1">posée et professionnelle</div>
                </button>
              </div>
            </>
          )}

          {step === 5 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-2">
                Comment souhaitez-vous l'appeler ?
              </h2>
              <div className="flex flex-wrap gap-2 justify-center mt-4">
                {names.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => goNext({ assistant_name: n })}
                    className={`px-4 py-2 rounded-xl border-2 text-sm font-medium ${
                      state.assistant_name === n
                        ? "border-teal-500 bg-teal-500/20 text-teal-400"
                        : "border-slate-600 text-slate-300 bg-slate-800/50 hover:border-slate-500"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <input
                type="text"
                value={state.assistant_name}
                onChange={(e) => persist({ assistant_name: e.target.value })}
                placeholder="Ou un prénom de votre choix"
                className="mt-4 w-full max-w-xs rounded-xl border-2 border-slate-600 bg-slate-800/80 px-4 py-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              />
              {/* Boutons pour saisie manuelle du prénom */}
              <div className="max-w-xl w-full flex justify-between gap-4 mt-6">
                <button
                  type="button"
                  onClick={() => persist({ step: 4 })}
                  className="px-5 py-2.5 rounded-xl border-2 border-slate-600 text-slate-300 font-medium hover:bg-slate-800/80 hover:border-slate-500"
                >
                  Retour
                </button>
                <button
                  type="button"
                  onClick={() => persist({ step: 6 })}
                  disabled={!canContinue()}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  Continuer
                </button>
              </div>
            </>
          )}

          {step === 6 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-2">
                Quelle situation vous arrive le plus souvent ?
              </h2>
              <p className="text-sm text-slate-400 text-center mb-4">
                Une seule réponse — nous personnaliserons notre recommandation.
              </p>
              <div className="w-full max-w-lg space-y-2">
                {PAIN_POINT_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => goNext({ primary_pain_point: opt })}
                    className={`w-full py-3 px-4 rounded-xl border-2 text-left text-sm font-medium transition-all flex items-center gap-2 ${
                      state.primary_pain_point === opt
                        ? "border-teal-500 bg-teal-500/20 text-teal-400"
                        : "border-slate-600 text-slate-300 bg-slate-800/50 hover:border-slate-500"
                    }`}
                  >
                    {state.primary_pain_point === opt && (
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center text-slate-950 text-xs">✓</span>
                    )}
                    {opt}
                  </button>
                ))}
              </div>
              <p className="mt-4 text-xs text-slate-500 text-center">
                UWi s'adaptera automatiquement à votre situation.
              </p>
            </>
          )}

          {step === 7 && (
            <>
              <h2 className="text-xl font-bold text-white text-center mb-1">
                Votre estimation personnalisée
              </h2>
              <p className="text-sm text-slate-400 text-center mb-6">
                Estimation indicative basée sur votre volume d'appels et vos réponses.
              </p>
              <div className="w-full max-w-lg space-y-4">
                {/* Card 1 — Temps potentiellement économisé (compteur animé, valeur arrondie) */}
                <div className="rounded-xl border border-slate-700 bg-slate-800/80 p-4 text-center ring-1 ring-white/5" aria-live="polite" aria-atomic="true">
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
                    Temps potentiellement économisé
                  </p>
                  <p>
                    <span className="text-3xl font-bold bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent tabular-nums">{formatMinutesForDisplay(Math.round(animMinutes))}</span>
                    <span className="text-base font-medium text-slate-500 ml-1">/ jour</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    principalement via filtrage des appels et automatisation des RDV
                  </p>
                </div>
                {/* Card 2 — Projection annuelle (arrondi par pas de 5 pour éviter effet slot) */}
                <div className="rounded-xl border border-slate-700 bg-slate-800/80 p-4 text-center ring-1 ring-white/5">
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
                    Sur une année (estimation)
                  </p>
                  <p>
                    <span className="text-3xl font-bold text-white tabular-nums">≈ {Math.round(animAnnual / 5) * 5}</span>
                    <span className="text-base font-medium text-slate-500 ml-1">heures / an</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    calcul basé sur 200 jours ouvrés
                  </p>
                </div>
                {/* Card 3 — Consultations potentielles (valeur en avant) */}
                <div className="rounded-xl border border-slate-700 bg-slate-800/80 p-4 text-center ring-1 ring-white/5">
                  <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
                    Ce que cela peut représenter
                  </p>
                  <p>
                    <span className="text-2xl font-bold text-white">
                      {diagnostic.label_consultations === "1" ? "1 consultation potentielle" : `${diagnostic.label_consultations} consultations potentielles`}
                    </span>
                    <span className="text-sm font-medium text-slate-500"> / jour</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    ou simplement moins d'interruptions et plus de continuité de soin
                  </p>
                </div>
                {/* Phrase personnalisée (pain point) — 1 ligne max, tooltip si tronqué */}
                <p
                  className="text-sm text-slate-400 text-center italic pt-1 line-clamp-1"
                  title={diagnostic.message}
                >
                  {diagnostic.message}
                </p>
              </div>
              <div className="flex flex-col items-center justify-center mt-6">
                <button
                  type="button"
                  onClick={() => setModalOpen(true)}
                  className="w-full max-w-sm px-6 py-3 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black hover:shadow-lg hover:shadow-teal-500/30 transition-all"
                >
                  Profiter de mon mois offert
                </button>
                <p className="text-xs text-slate-500 mt-1.5 text-center">
                  Numéro de test envoyé par email en moins d'une minute.
                </p>
              </div>
              <p className="text-xs text-slate-500 text-center mt-4">
                Configuration modifiable à tout moment.
              </p>
            </>
          )}
        </div>
      </div>

      {/* Plus de barre sticky Continuer : affichée uniquement sur l'écran horaires (step 3), intégrée sous le formulaire */}

      {/* Modal coordonnées — email et/ou téléphone (au moins un requis), enregistré comme lead en admin */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl max-w-md w-full p-6 ring-1 ring-white/10">
            <h3 className="text-lg font-bold text-white mb-2">
              Recevez votre numéro de test
            </h3>
            <p className="text-sm text-slate-400 mb-4">
              Indiquez au moins l'un des deux pour que nous puissions vous recontacter.
            </p>
            <input
              type="email"
              value={modalEmail}
              onChange={(e) => setModalEmail(e.target.value)}
              placeholder="Email (optionnel)"
              className="w-full rounded-xl border-2 border-slate-600 bg-slate-800 px-4 py-3 mb-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            />
            <input
              type="tel"
              value={modalPhone}
              onChange={(e) => setModalPhone(e.target.value)}
              placeholder="Téléphone (optionnel)"
              className="w-full rounded-xl border-2 border-slate-600 bg-slate-800 px-4 py-3 mb-4 text-white placeholder-slate-500 focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            />
            {commitError && (
              <p className="text-sm text-red-400 mb-2">{commitError}</p>
            )}
            <button
              type="button"
              onClick={handleCommit}
              disabled={(!modalEmail.trim() && !modalPhone.trim()) || commitLoading}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black hover:shadow-teal-500/30 disabled:opacity-50 transition-all"
            >
              {commitLoading ? "Envoi…" : "Terminer la configuration de mon assistant avec un expert"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
