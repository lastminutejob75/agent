// Wizard public "Créer votre assistant" — diagnostic + projection ROI + capture lead.
// Identité light UWi (cohérence landing publique). Architecture : 6 étapes,
// persistance localStorage, modal de capture (email/phone) en fin de parcours.
import { Suspense, lazy, useState, useEffect, useCallback, useMemo } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  Stethoscope,
  Phone,
  Sparkles,
  MessageSquare,
  TrendingUp,
  ArrowLeft,
  ArrowRight,
  Check,
  AlertCircle,
  Mail,
  X,
  ChevronDown,
} from "lucide-react";
import { api } from "../lib/api.js";

const UWIFinalization = lazy(() => import("../components/UWIFinalization.jsx"));
const AssistantSelector = lazy(() => import("../components/AssistantSelector.jsx"));

// =============================================================================
// CONSTANTS — logique métier inchangée
// =============================================================================

const STORAGE_KEY = "uwi_creer_assistante";
const COMMIT_DONE_KEY = "uwi_creer_assistante_done";

/** POST /commit : id renvoyé par FastAPI (`lead_id`), ou variantes si proxy / ancienne API. */
function parseCommitLeadId(res) {
  if (!res || typeof res !== "object") return "";
  const v = res.lead_id ?? res.leadId ?? res.id;
  if (v == null) return "";
  return String(v).trim();
}

const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const TOTAL_STEPS = 6;

const STEP_LABELS = [
  "Spécialité",
  "Volume",
  "Voix",
  "Prénom",
  "Situation",
  "Estimation",
];

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

const PAIN_POINT_OPTIONS = [
  "Je suis interrompu(e) en consultation par les appels",
  "On me laisse beaucoup de messages à rappeler",
  "Mon secrétariat n'arrive pas à suivre",
  "Je passe trop de temps à gérer les rendez-vous",
  "Je veux mieux orienter les patients (infos, consignes, urgence)",
  "Autre",
];

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
  { value: "<10", label: "Moins de 10", hint: "Cabinet calme" },
  { value: "10-25", label: "10–25", hint: "Cabinet régulier" },
  { value: "25-50", label: "25–50", hint: "Cabinet actif" },
  { value: "50-100", label: "50–100", hint: "Forte activité" },
  { value: "100+", label: "Plus de 100", hint: "Très forte activité" },
  { value: "unknown", label: "Je ne sais pas", hint: "Estimation possible" },
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

// =============================================================================
// HELPERS
// =============================================================================

function formatMinutesForDisplay(min) {
  const m = Math.round(Number(min) || 0);
  if (m >= 120) return "2 h+";
  if (m >= 90) return "1 à 2 h";
  if (m >= 60) return "1 h";
  if (m >= 30) return "30 min";
  if (m >= 15) return "15 min";
  return m <= 0 ? "0 min" : `${m} min`;
}

function computeDiagnostic(data) {
  const vol = data.daily_call_volume || "unknown";
  const pain = (data.primary_pain_point || "").trim();
  const estimated_minutes_per_day = MINUTES_BY_VOLUME[vol] ?? MINUTES_BY_VOLUME.unknown;
  const label_time_gain = LABEL_TIME_GAIN_BY_VOLUME[vol] || LABEL_TIME_GAIN_BY_VOLUME.unknown;
  const annual_hours = Math.round((estimated_minutes_per_day / 60) * 200);
  const label_consultations = LABEL_CONSULTATIONS_BY_VOLUME[vol] || LABEL_CONSULTATIONS_BY_VOLUME.unknown;
  const message = PAIN_POINT_MESSAGE[pain] || PAIN_POINT_MESSAGE.Autre;
  return { estimated_minutes_per_day, label_time_gain, annual_hours, label_consultations, message };
}

function defaultOpeningHours() {
  // Preset cabinet standard (L-V 08:30-18:00, samedi/dimanche fermé) appliqué
  // automatiquement : l'utilisateur ne saisit plus ses horaires dans le wizard
  // de capture lead, l'équipe finalisera ensuite l'onboarding.
  return { ...PRESET_HOURS };
}

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

function isValidEmail(s) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(s || "").trim());
}

function isValidPhone(s) {
  const digits = String(s || "").replace(/\D/g, "");
  return digits.length >= 9;
}

// =============================================================================
// UI PRIMITIVES — design system light UWi (cohérence landing publique)
// =============================================================================

function WizardPanelFallback({ text = "Chargement…" }) {
  return (
    <div className="w-full flex-1 min-h-[420px] flex items-center justify-center text-center px-6">
      <div className="max-w-sm">
        <div className="mx-auto mb-4 h-10 w-10 rounded-full border-2 border-slate-200 border-t-teal-600 animate-spin" />
        <p className="text-sm text-slate-600">{text}</p>
      </div>
    </div>
  );
}

function Stepper({ current, total, labels }) {
  return (
    <div className="w-full">
      <div className="flex items-center gap-1 sm:gap-2">
        {Array.from({ length: total }).map((_, i) => {
          const idx = i + 1;
          const done = idx < current;
          const active = idx === current;
          return (
            <div key={idx} className="flex-1 flex items-center gap-1 sm:gap-2">
              <div
                className={`flex-shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-all duration-300 ${
                  done
                    ? "bg-gradient-to-br from-teal-600 to-cyan-500 text-white shadow-lg shadow-teal-500/30"
                    : active
                    ? "bg-white border-2 border-teal-600 text-teal-700 ring-4 ring-teal-500/10"
                    : "bg-slate-100 border border-slate-200 text-slate-400"
                }`}
                aria-current={active ? "step" : undefined}
                aria-label={`Étape ${idx} ${labels[i] ? "— " + labels[i] : ""}`}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : idx}
              </div>
              {idx < total && (
                <div className="flex-1 h-[2px] rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${
                      done ? "w-full bg-gradient-to-r from-teal-600 to-cyan-500" : "w-0"
                    }`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-slate-500">
        <span>
          Étape {current} sur {total}
        </span>
        <span className="text-slate-700">{labels[current - 1]}</span>
      </div>
    </div>
  );
}

function StepHeader({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center text-center mb-6">
      {Icon && (
        <div className="mb-3 h-11 w-11 rounded-xl bg-gradient-to-br from-teal-500/15 to-cyan-400/10 border border-teal-500/40 flex items-center justify-center">
          <Icon className="h-5 w-5 text-teal-700" />
        </div>
      )}
      <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">{title}</h2>
      {subtitle && (
        <p className="mt-1.5 text-sm text-slate-600 max-w-md">{subtitle}</p>
      )}
    </div>
  );
}

function ChoiceTile({ active, onClick, children, dense = false, icon: Icon }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative ${dense ? "py-3 px-3" : "py-4 px-3"} rounded-xl border-2 text-sm font-semibold transition-all text-left flex items-center gap-2 group ${
        active
          ? "border-teal-600 bg-teal-50 text-teal-700 shadow-[0_0_0_3px_rgba(20,184,166,0.12)]"
          : "border-slate-200 text-slate-700 bg-white hover:border-teal-400 hover:bg-slate-50"
      }`}
    >
      {active ? (
        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-gradient-to-br from-teal-600 to-cyan-500 flex items-center justify-center text-white">
          <Check className="h-3 w-3" strokeWidth={3} />
        </span>
      ) : Icon ? (
        <Icon className="h-4 w-4 text-slate-400 group-hover:text-teal-600" />
      ) : null}
      <span className="flex-1 leading-tight">{children}</span>
    </button>
  );
}

function PrimaryButton({ children, onClick, disabled, type = "button", className = "" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-6 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-500 text-white font-bold hover:shadow-lg hover:shadow-teal-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 ${className}`}
    >
      {children}
    </button>
  );
}

function SecondaryButton({ children, onClick, className = "" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-5 py-2.5 rounded-xl border-2 border-slate-200 text-slate-700 font-medium hover:bg-slate-50 hover:border-teal-400 transition-all flex items-center gap-2 ${className}`}
    >
      {children}
    </button>
  );
}

function NavBar({ onBack, onNext, nextDisabled, nextLabel = "Continuer", showBack = true }) {
  return (
    <div className="w-full max-w-xl mx-auto flex justify-between gap-3 mt-6">
      {showBack ? (
        <SecondaryButton onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> Retour
        </SecondaryButton>
      ) : (
        <span />
      )}
      <PrimaryButton onClick={onNext} disabled={nextDisabled}>
        {nextLabel} <ArrowRight className="h-4 w-4" />
      </PrimaryButton>
    </div>
  );
}

function InlineHint({ children, tone = "info" }) {
  const cls = {
    info: "text-teal-700 bg-teal-50 border-teal-200",
    warn: "text-amber-700 bg-amber-50 border-amber-200",
    error: "text-rose-700 bg-rose-50 border-rose-200",
  }[tone];
  return (
    <div className={`mt-3 text-xs px-3 py-2 rounded-lg border ${cls} flex items-center gap-2`}>
      {tone === "error" ? (
        <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
      ) : (
        <Sparkles className="h-3.5 w-3.5 flex-shrink-0" />
      )}
      <span>{children}</span>
    </div>
  );
}

// =============================================================================
// STEP COMPONENTS
// =============================================================================

function Step1Specialty({ state, persist, goNext }) {
  const tileSlugs = STEP1_TILES.map((t) => t.slug);
  const otherSelected = state.medical_specialty && !tileSlugs.includes(state.medical_specialty);
  return (
    <>
      <StepHeader
        icon={Stethoscope}
        title="Quelle est votre spécialité ?"
        subtitle="Nous adaptons l'accueil et la prise de rendez-vous à votre spécialité."
      />
      <div className="w-full max-w-lg grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        {STEP1_TILES.map(({ slug, label }) => (
          <ChoiceTile
            key={slug}
            active={state.medical_specialty === slug}
            onClick={() =>
              goNext({
                medical_specialty: slug,
                medical_specialty_label: label,
                specialty_other: "",
              })
            }
          >
            {label}
          </ChoiceTile>
        ))}
      </div>
      <div className="w-full max-w-lg mt-4">
        <label className="block text-xs font-medium text-slate-600 mb-1.5">
          Autres spécialités
        </label>
        <div className="relative">
          <select
            value={otherSelected ? state.medical_specialty : ""}
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
            className="w-full appearance-none rounded-xl border-2 border-slate-200 bg-white px-4 py-3 pr-10 text-slate-900 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
          >
            <option value="">Choisir…</option>
            {STEP1_OTHER_GROUPS.map(({ group, options }) => (
              <optgroup key={group} label={group}>
                {options.map(({ slug: s, label: l }) => (
                  <option key={s} value={s}>
                    {l}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
        </div>
      </div>
      {state.medical_specialty === "autre" && (
        <input
          type="text"
          value={state.specialty_other || ""}
          onChange={(e) => persist({ specialty_other: e.target.value })}
          placeholder="Précisez (optionnel)"
          className="mt-3 w-full max-w-md rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
        />
      )}
      {state.medical_specialty && (
        <InlineHint>Parfait — votre assistant sera adapté à votre spécialité.</InlineHint>
      )}
    </>
  );
}

function Step2Volume({ state, goNext }) {
  const v = state.daily_call_volume;
  const microText =
    v === "25-50" || v === "50-100" || v === "100+"
      ? "UWi peut vous faire gagner plusieurs heures par semaine."
      : v
      ? "UWi vous aide à ne manquer aucun appel."
      : null;
  return (
    <>
      <StepHeader
        icon={Phone}
        title="Combien d'appels recevez-vous par jour ?"
        subtitle="Une estimation suffit — nous ajustons le calibrage."
      />
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 w-full max-w-lg">
        {VOLUME_OPTIONS.map((opt) => (
          <ChoiceTile
            key={opt.value}
            active={state.daily_call_volume === opt.value}
            onClick={() => goNext({ daily_call_volume: opt.value })}
          >
            <span className="flex flex-col">
              <span>{opt.label}</span>
              <span className="text-[11px] font-normal text-slate-500 mt-0.5 group-hover:text-slate-600">{opt.hint}</span>
            </span>
          </ChoiceTile>
        ))}
      </div>
      {microText && <InlineHint>{microText}</InlineHint>}
    </>
  );
}

function Step5Name({ state, persist, onNext, onBack }) {
  const names = state.voice_gender === "female" ? NAMES_FEMALE : NAMES_MALE;
  const valid = !!(state.assistant_name || "").trim();
  return (
    <>
      <StepHeader
        icon={Sparkles}
        title="Comment souhaitez-vous l'appeler ?"
        subtitle="Choisissez un prénom suggéré ou saisissez le vôtre."
      />
      <div className="flex flex-wrap gap-2 justify-center max-w-lg">
        {names.map((n) => (
          <ChoiceTile
            key={n}
            dense
            active={state.assistant_name === n}
            onClick={() => persist({ assistant_name: n })}
          >
            {n}
          </ChoiceTile>
        ))}
      </div>
      <input
        type="text"
        value={state.assistant_name}
        onChange={(e) => persist({ assistant_name: e.target.value })}
        placeholder="Ou un prénom de votre choix"
        className="mt-4 w-full max-w-xs rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none text-center"
      />
      <NavBar onBack={onBack} onNext={onNext} nextDisabled={!valid} />
    </>
  );
}

function Step6Pain({ state, goNext }) {
  return (
    <>
      <StepHeader
        icon={MessageSquare}
        title="Quelle situation vous arrive le plus souvent ?"
        subtitle="Une seule réponse — nous personnaliserons notre recommandation."
      />
      <div className="w-full max-w-lg space-y-2">
        {PAIN_POINT_OPTIONS.map((opt) => (
          <ChoiceTile
            key={opt}
            active={state.primary_pain_point === opt}
            onClick={() => goNext({ primary_pain_point: opt })}
          >
            {opt}
          </ChoiceTile>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-500 text-center">
        UWi s&apos;adaptera automatiquement à votre situation.
      </p>
    </>
  );
}

function Step7Result({ diagnostic, animMinutes, animAnnual, onCTAClick }) {
  return (
    <>
      <StepHeader
        icon={TrendingUp}
        title="Votre estimation personnalisée"
        subtitle="Estimation indicative basée sur votre volume d'appels et vos réponses."
      />
      <div className="w-full max-w-lg space-y-3">
        <div
          className="rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50 to-cyan-50 p-5 text-center"
          aria-live="polite"
        >
          <p className="text-[11px] font-semibold text-teal-700 uppercase tracking-wider mb-1.5">
            Temps potentiellement économisé
          </p>
          <p>
            <span className="text-4xl font-bold bg-gradient-to-r from-teal-600 to-cyan-600 bg-clip-text text-transparent tabular-nums">
              {formatMinutesForDisplay(Math.round(animMinutes))}
            </span>
            <span className="text-base font-medium text-slate-600 ml-1">/ jour</span>
          </p>
          <p className="text-xs text-slate-500 mt-1.5">
            principalement via filtrage des appels et automatisation des RDV
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
            Sur une année (estimation)
          </p>
          <p>
            <span className="text-3xl font-bold text-slate-900 tabular-nums">
              ≈ {Math.round(animAnnual / 5) * 5}
            </span>
            <span className="text-base font-medium text-slate-500 ml-1">heures / an</span>
          </p>
          <p className="text-xs text-slate-500 mt-1">calcul basé sur 200 jours ouvrés</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
            Ce que cela peut représenter
          </p>
          <p>
            <span className="text-2xl font-bold text-slate-900">
              {diagnostic.label_consultations === "1"
                ? "1 consultation potentielle"
                : `${diagnostic.label_consultations} consultations potentielles`}
            </span>
            <span className="text-sm font-medium text-slate-500"> / jour</span>
          </p>
          <p className="text-xs text-slate-500 mt-1">
            ou simplement moins d&apos;interruptions et plus de continuité de soin
          </p>
        </div>
        <p
          className="text-sm text-slate-600 text-center italic pt-1 line-clamp-2"
          title={diagnostic.message}
        >
          {diagnostic.message}
        </p>
      </div>
      <div className="flex flex-col items-center mt-6 w-full max-w-lg">
        <button
          type="button"
          onClick={onCTAClick}
          className="w-full max-w-sm px-6 py-3.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-500 text-white font-bold hover:shadow-lg hover:shadow-teal-500/40 transition-all flex items-center justify-center gap-2"
        >
          <Sparkles className="h-4 w-4" />
          Profiter de mon mois offert
        </button>
        <p className="text-xs text-slate-500 mt-2 text-center">
          Numéro de test envoyé par email en moins d&apos;une minute.
        </p>
        <p className="text-[11px] text-slate-400 text-center mt-3">
          Configuration modifiable à tout moment.
        </p>
      </div>
    </>
  );
}

// =============================================================================
// CONTACT MODAL
// =============================================================================

function ContactModal({
  open,
  email,
  phone,
  onEmailChange,
  onPhoneChange,
  loading,
  error,
  onClose,
  onSubmit,
}) {
  if (!open) return null;
  const emailValid = !email || isValidEmail(email);
  const phoneValid = !phone || isValidPhone(phone);
  const canSubmit =
    !loading && (email.trim() || phone.trim()) && emailValid && phoneValid;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Recevez votre numéro de test"
    >
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl max-w-md w-full p-6 relative">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 h-8 w-8 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 flex items-center justify-center"
          aria-label="Fermer"
        >
          <X className="h-4 w-4" />
        </button>
        <div className="mb-4 h-11 w-11 rounded-xl bg-gradient-to-br from-teal-500/15 to-cyan-400/10 border border-teal-500/40 flex items-center justify-center">
          <Mail className="h-5 w-5 text-teal-700" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 mb-1.5">Recevez votre numéro de test</h3>
        <p className="text-sm text-slate-600 mb-4">
          Indiquez au moins l&apos;un des deux pour que nous puissions vous recontacter.
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              placeholder="vous@cabinet.fr"
              className={`w-full rounded-xl border-2 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-400 focus:ring-2 outline-none ${
                emailValid
                  ? "border-slate-200 focus:ring-teal-500 focus:border-teal-500"
                  : "border-rose-400 focus:ring-rose-300"
              }`}
            />
            {!emailValid && (
              <p className="mt-1 text-[11px] text-rose-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" /> Email invalide
              </p>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Téléphone</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => onPhoneChange(e.target.value)}
              placeholder="06 12 34 56 78"
              className={`w-full rounded-xl border-2 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-400 focus:ring-2 outline-none ${
                phoneValid
                  ? "border-slate-200 focus:ring-teal-500 focus:border-teal-500"
                  : "border-rose-400 focus:ring-rose-300"
              }`}
            />
            {!phoneValid && (
              <p className="mt-1 text-[11px] text-rose-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" /> Numéro invalide
              </p>
            )}
          </div>
        </div>
        {error && (
          <div className="mt-3 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-500 text-white font-bold hover:shadow-lg hover:shadow-teal-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {loading ? "Envoi…" : "Terminer la configuration avec un expert"}
        </button>
        <p className="mt-2 text-[11px] text-slate-500 text-center">
          En envoyant, vous acceptez d&apos;être contacté par UWi pour finaliser votre essai.
        </p>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

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

  // Nettoyer ?new=1 / ?start=1 dans l'URL après reset
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("new") === "1" || params.get("start") === "1") {
      params.delete("new");
      params.delete("start");
      const newSearch = params.toString();
      const url =
        window.location.pathname +
        (newSearch ? `?${newSearch}` : "") +
        window.location.hash;
      window.history.replaceState({}, "", url);
    }
  }, []);

  // Pre-remplissage depuis AgentsSpotlight : si l'utilisateur arrive en ayant
  // cliqué sur un avatar (Sophie, Hugo, etc.), location.state contient l'agent.
  // On pre-remplit assistant_name et voice_gender pour faire gagner du temps.
  // (saveState est appelé automatiquement via le useEffect [state] plus bas.)
  const location = useLocation();
  useEffect(() => {
    const agent = location.state;
    if (!agent || typeof agent !== "object") return;
    const prenom = (agent.prenom || "").trim();
    const gender = agent.gender === "m" ? "male" : agent.gender === "f" ? "female" : "";
    if (!prenom && !gender) return;
    setState((s) => {
      const next = { ...s };
      if (prenom && !s.assistant_name) next.assistant_name = prenom;
      if (gender && !s.voice_gender) next.voice_gender = gender;
      return next;
    });
    // On nettoie le state d'historique pour eviter de re-prefiller au refresh
    if (typeof window !== "undefined") {
      window.history.replaceState({}, "", window.location.pathname + window.location.search + window.location.hash);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalEmail, setModalEmail] = useState("");
  const [modalPhone, setModalPhone] = useState("");
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitDone, setCommitDone] = useState(() => {
    try {
      const raw = typeof window !== "undefined" && sessionStorage.getItem(COMMIT_DONE_KEY);
      if (!raw) return false;
      const data = JSON.parse(raw);
      return Boolean(String(data?.lead_id ?? "").trim());
    } catch (_) {
      return false;
    }
  });
  const [submittedEmail, setSubmittedEmail] = useState(() => {
    try {
      const raw = typeof window !== "undefined" && sessionStorage.getItem(COMMIT_DONE_KEY);
      if (!raw) return "";
      const data = JSON.parse(raw);
      if (!String(data?.lead_id ?? "").trim()) return "";
      return data.contact != null ? String(data.contact) : "";
    } catch (_) {}
    return "";
  });
  const [commitError, setCommitError] = useState("");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Restaurer la finalisation uniquement si sessionStorage contient un lead_id valide (sinon écran « lien expiré » vide).
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = sessionStorage.getItem(COMMIT_DONE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      const lid = String(data?.lead_id ?? "").trim();
      if (!lid) {
        sessionStorage.removeItem(COMMIT_DONE_KEY);
        setCommitDone(false);
        return;
      }
      setCommitDone(true);
      setSubmittedEmail(data.contact != null ? String(data.contact) : "");
      setState((s) => ({ ...s, lead_id: lid, lead_token: data.token ? String(data.token) : s.lead_token }));
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

  // Prefill email du modal si lien ?ref= ou ?email= ou stockage session
  const getRefEmail = () => {
    if (typeof window === "undefined") return "";
    const params = new URLSearchParams(window.location.search);
    if (params.get("email")?.trim()) return params.get("email").trim();
    if (params.get("ref")?.trim()) return params.get("ref").trim();
    try {
      const stored = sessionStorage.getItem("uwi_demo_ref");
      if (stored?.trim()) return stored.trim();
    } catch (_) {}
    return "";
  };

  useEffect(() => {
    if (modalOpen && !modalEmail.trim()) {
      const ref = getRefEmail();
      if (ref && ref.includes("@")) {
        setModalEmail(ref);
        try {
          sessionStorage.removeItem("uwi_demo_ref");
        } catch (_) {}
      }
    }
  }, [modalOpen, modalEmail]);

  const goNext = (updates) =>
    persist({ ...updates, step: Math.min(TOTAL_STEPS, state.step + 1) });

  const goBack = () => persist({ step: Math.max(1, state.step - 1) });
  const goToStep = (n) => persist({ step: Math.max(1, Math.min(TOTAL_STEPS, n)) });

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
        source: "landing_create_assistant",
        wants_callback: !!phoneTrim,
        callback_phone: phoneTrim,
      };
      const res = await api.preOnboardingCommit(payload);
      const contact = emailTrim || phoneTrim || "";
      const leadId = parseCommitLeadId(res);
      if (!leadId) {
        throw new Error(
          "Réponse serveur incomplète (pas d’identifiant de demande). Réessayez dans un instant ou vérifiez que le site pointe vers le bon backend.",
        );
      }
      const leadToken = res && res.token ? String(res.token) : "";
      try {
        sessionStorage.setItem(
          COMMIT_DONE_KEY,
          JSON.stringify({
            contact,
            phone: phoneTrim,
            email: emailTrim,
            lead_id: leadId,
            token: leadToken,
          }),
        );
      } catch (_) {}
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          p.set("lead_id", leadId);
          if (leadToken) p.set("token", leadToken);
          return p;
        },
        { replace: true },
      );
      setSubmittedEmail(contact);
      setCommitDone(true);
      setState((s) => ({ ...s, lead_id: leadId, lead_token: leadToken }));
      persist({ lead_id: leadId, lead_token: leadToken });
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

  // Toujours appeler les hooks avant tout return conditionnel
  const step = Math.min(TOTAL_STEPS, Math.max(1, state.step));
  const isFinalStep = step === TOTAL_STEPS;
  const diagnostic = useMemo(
    () =>
      computeDiagnostic({
        daily_call_volume: state.daily_call_volume,
        primary_pain_point: state.primary_pain_point,
      }),
    [state.daily_call_volume, state.primary_pain_point]
  );

  // Animation des chiffres sur l'étape finale (estimation)
  const [animMinutes, setAnimMinutes] = useState(0);
  const [animAnnual, setAnimAnnual] = useState(0);
  useEffect(() => {
    if (!isFinalStep) return;
    const targetMin = diagnostic.estimated_minutes_per_day;
    const targetAnnual = diagnostic.annual_hours;
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
  }, [isFinalStep, diagnostic.estimated_minutes_per_day, diagnostic.annual_hours]);

  // Si lead déjà créé : afficher l'écran de finalisation (UWIFinalization)
  const leadIdFromUrl = (searchParams.get("lead_id") || "").trim();
  const leadTokenFromUrl = (searchParams.get("token") || "").trim();
  const showFinalization = commitDone || Boolean(leadIdFromUrl);

  /** Sync lead_id dans l'URL (hors rendu) pour éviter une course où UWIFinalization monte sans id. */
  useEffect(() => {
    if (!showFinalization || typeof window === "undefined") return;
    if (leadIdFromUrl) return;
    let id = "";
    try {
      const raw = sessionStorage.getItem(COMMIT_DONE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        id = String(data?.lead_id || "").trim();
      }
    } catch (_) {}
    if (!id) id = String(state.lead_id || "").trim();
    if (!id) return;
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("lead_id", id);
        return p;
      },
      { replace: true },
    );
  }, [showFinalization, leadIdFromUrl, setSearchParams, state.lead_id]);

  if (showFinalization) {
    let leadId = leadIdFromUrl;
    let initialPhone = "";
    let initialEmail = "";
    let leadToken = "";
    if (typeof window !== "undefined") {
      try {
        const raw = sessionStorage.getItem(COMMIT_DONE_KEY);
        if (raw) {
          const data = JSON.parse(raw);
          if (data && data.phone) initialPhone = String(data.phone).replace(/\D/g, "").slice(0, 10);
          if (data && data.email) initialEmail = String(data.email).trim();
          if (data && data.token) leadToken = String(data.token);
          if (!leadId) leadId = data?.lead_id ? String(data.lead_id) : state.lead_id || "";
        }
      } catch (_) {}
    }
    if (!leadId) leadId = state.lead_id || "";
    if (!leadToken) leadToken = leadTokenFromUrl || state.lead_token || "";
    const assistantName = state.assistant_name || "Emma";
    return (
      <div className="min-h-screen w-full bg-white">
        <Suspense fallback={<WizardPanelFallback text="Préparation de votre assistant…" />}>
          <UWIFinalization
            leadId={leadId}
            leadToken={leadToken}
            initialPhone={initialPhone}
            initialEmail={initialEmail}
            assistantName={assistantName}
            practitioner="votre cabinet"
            onComplete={handleBackToHome}
          />
        </Suspense>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen bg-white flex flex-col relative overflow-hidden"
      style={{ fontFamily: "'DM Sans', system-ui, -apple-system, sans-serif" }}
    >
      {/* Header identité landing — retour accueil */}
      <header className="flex-shrink-0 px-6 py-4 relative z-20">
        <div className="max-w-3xl mx-auto flex justify-between items-center">
          <Link
            to="/"
            className="text-slate-900 font-bold tracking-tight hover:text-teal-700 transition-colors flex items-center gap-2"
          >
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-600 to-cyan-500 flex items-center justify-center text-white text-sm font-black">
              U
            </span>
            <span>UWi Medical</span>
          </Link>
          <Link
            to="/login"
            className="text-sm text-slate-600 hover:text-teal-700 transition-colors"
          >
            Connexion
          </Link>
        </div>
      </header>

      {/* Fond identité (orbs subtils + grille très légère) */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-teal-200/30 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-cyan-200/30 rounded-full blur-[120px]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_40%,transparent_110%)] opacity-40" />
      </div>

      {/* Stepper */}
      <div className="flex-shrink-0 px-6 pt-2 pb-4 relative z-10">
        <div className="max-w-2xl mx-auto">
          <Stepper current={step} total={TOTAL_STEPS} labels={STEP_LABELS} />
        </div>
      </div>

      {/* Contenu */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-4 relative z-10">
        <div className="w-full max-w-2xl flex flex-col items-center justify-center">
          {step === 1 && (
            <Step1Specialty state={state} persist={persist} goNext={goNext} />
          )}
          {step === 2 && <Step2Volume state={state} goNext={goNext} />}
          {step === 3 && (
            <div className="w-full flex-1 min-h-0 flex flex-col -mx-6 -my-4 self-stretch">
              <Suspense fallback={<WizardPanelFallback text="Chargement des assistants…" />}>
                <AssistantSelector
                  onBack={() => goToStep(2)}
                  onSelect={(assistant) => {
                    persist({
                      voice_gender: assistant.gender === "f" ? "female" : "male",
                      assistant_name: assistant.prenom,
                      step: 4,
                    });
                  }}
                />
              </Suspense>
            </div>
          )}
          {step === 4 && (
            <Step5Name
              state={state}
              persist={persist}
              onNext={() => goToStep(5)}
              onBack={() => goToStep(3)}
            />
          )}
          {step === 5 && <Step6Pain state={state} goNext={goNext} />}
          {step === 6 && (
            <Step7Result
              diagnostic={diagnostic}
              animMinutes={animMinutes}
              animAnnual={animAnnual}
              onCTAClick={() => setModalOpen(true)}
            />
          )}
        </div>
      </div>

      {/* Footer "retour" discret pour étapes 1, 2, 5, 6 (les autres ont leur NavBar) */}
      {(step === 1 || step === 2 || step === 5 || step === 6) && step > 1 && (
        <div className="flex-shrink-0 pb-6 px-6 relative z-10">
          <div className="max-w-2xl mx-auto flex justify-center">
            <button
              type="button"
              onClick={goBack}
              className="text-sm text-slate-500 hover:text-teal-700 transition-colors flex items-center gap-1.5"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Étape précédente
            </button>
          </div>
        </div>
      )}

      <ContactModal
        open={modalOpen}
        email={modalEmail}
        phone={modalPhone}
        onEmailChange={setModalEmail}
        onPhoneChange={setModalPhone}
        loading={commitLoading}
        error={commitError}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCommit}
      />
    </div>
  );
}
