// Wizard "Créer votre assistante" — 5 steps, full-screen, 0 scroll, premium médical
import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

const STORAGE_KEY = "uwi_creer_assistante";
const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const VOLUME_OPTIONS = [
  { value: "<10", label: "<10" },
  { value: "10-25", label: "10–25" },
  { value: "25-50", label: "25–50" },
  { value: "50+", label: "50+" },
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

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return {
    step: 1,
    daily_call_volume: "",
    opening_hours: defaultOpeningHours(),
    voice_gender: "",
    assistant_name: "",
  };
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
  const [state, setState] = useState(loadState);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalEmail, setModalEmail] = useState("");
  const [modalCallback, setModalCallback] = useState(false);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitDone, setCommitDone] = useState(false);
  const [commitError, setCommitError] = useState("");

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
    if (state.step === 1) return !!state.daily_call_volume;
    if (state.step === 2) return atLeastOneOpen();
    if (state.step === 3) return !!state.voice_gender;
    if (state.step === 4) return !!(state.assistant_name || "").trim();
    return true;
  };

  const volumeMicroText = () => {
    const v = state.daily_call_volume;
    if (v === "25-50" || v === "50+")
      return "UWi peut vous faire gagner plusieurs heures par semaine.";
    if (v) return "UWi vous aide à ne manquer aucun appel.";
    return null;
  };

  const handleCommit = async () => {
    setCommitError("");
    setCommitLoading(true);
    try {
      const oh = state.opening_hours || defaultOpeningHours();
      const payload = {
        email: modalEmail.trim(),
        daily_call_volume: state.daily_call_volume,
        opening_hours: oh,
        voice_gender: state.voice_gender,
        assistant_name: (state.assistant_name || "").trim(),
        source: "landing_cta",
        wants_callback: modalCallback,
      };
      await api.preOnboardingCommit(payload);
      clearState();
      setCommitDone(true);
      setModalOpen(false);
    } catch (e) {
      setCommitError(e.message || "Erreur enregistrement");
    } finally {
      setCommitLoading(false);
    }
  };

  if (commitDone) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center p-6">
        <div className="max-w-md text-center">
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Demande enregistrée</h1>
          <p className="text-slate-600 mb-6">
            Vous recevrez sous peu un numéro de test pour écouter votre assistante.
          </p>
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-xl bg-teal-600 text-white font-semibold px-6 py-3 hover:bg-teal-700"
          >
            Retour à l'accueil
          </Link>
        </div>
      </div>
    );
  }

  const step = Math.min(5, Math.max(1, state.step));
  const isStep5 = step === 5;
  const names = state.voice_gender === "female" ? NAMES_FEMALE : NAMES_MALE;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Progress */}
      <div className="flex-shrink-0 px-6 pt-8 pb-2">
        <div className="max-w-xl mx-auto flex justify-between text-xs text-slate-400">
          <span>Étape {step} sur 5</span>
        </div>
        <div className="max-w-xl mx-auto h-1 bg-slate-100 rounded-full mt-1 overflow-hidden">
          <div
            className="h-full bg-teal-500 rounded-full transition-all duration-300"
            style={{ width: `${(step / 5) * 100}%` }}
          />
        </div>
      </div>

      {/* Content — no scroll */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-6 overflow-hidden">
        <div className="w-full max-w-xl flex flex-col items-center justify-center min-h-0">
          {step === 1 && (
            <>
              <h2 className="text-xl font-bold text-slate-800 text-center mb-2">
                Combien d'appels recevez-vous par jour ?
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full mt-6">
                {VOLUME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => persist({ daily_call_volume: opt.value })}
                    className={`py-4 px-4 rounded-xl border-2 text-sm font-semibold transition-all ${
                      state.daily_call_volume === opt.value
                        ? "border-teal-500 bg-teal-50 text-teal-800"
                        : "border-slate-200 text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {volumeMicroText() && (
                <p className="text-sm text-slate-500 mt-4 text-center">{volumeMicroText()}</p>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-xl font-bold text-slate-800 text-center mb-1">
                À quels horaires votre cabinet est-il ouvert ?
              </h2>
              <p className="text-sm text-slate-500 text-center mb-4">
                Ces horaires servent à informer vos patients et gérer les appels hors ouverture.
              </p>
              <button
                type="button"
                onClick={applyPreset}
                className="text-sm text-teal-600 font-medium mb-4 hover:underline"
              >
                Cabinet standard (L-V 08:30–18:00)
              </button>
              <div className="w-full space-y-2 max-h-64 overflow-auto">
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
                        className="flex items-center gap-3 py-2 border-b border-slate-100"
                      >
                        <span className="w-10 text-sm font-medium text-slate-600">{label}</span>
                        <label className="flex items-center gap-2 text-sm">
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
                          />
                          Fermé
                        </label>
                        {!slot.closed && (
                          <>
                            <input
                              type="time"
                              value={slot.start}
                              onChange={(e) =>
                                persist({
                                  opening_hours: {
                                    ...state.opening_hours,
                                    [key]: { ...slot, start: e.target.value },
                                  },
                                })
                              }
                              className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                            />
                            <span className="text-slate-400">–</span>
                            <input
                              type="time"
                              value={slot.end}
                              onChange={(e) =>
                                persist({
                                  opening_hours: {
                                    ...state.opening_hours,
                                    [key]: { ...slot, end: e.target.value },
                                  },
                                })
                              }
                              className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                            />
                          </>
                        )}
                      </div>
                    );
                  })}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="text-xl font-bold text-slate-800 text-center mb-6">
                Quelle voix pour votre assistante ?
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                <button
                  type="button"
                  onClick={() => persist({ voice_gender: "female" })}
                  className={`p-6 rounded-2xl border-2 text-left transition-all ${
                    state.voice_gender === "female"
                      ? "border-teal-500 bg-teal-50"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="font-semibold text-slate-800">Voix féminine</div>
                  <div className="text-sm text-slate-500 mt-1">douce et rassurante</div>
                </button>
                <button
                  type="button"
                  onClick={() => persist({ voice_gender: "male" })}
                  className={`p-6 rounded-2xl border-2 text-left transition-all ${
                    state.voice_gender === "male"
                      ? "border-teal-500 bg-teal-50"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="font-semibold text-slate-800">Voix masculine</div>
                  <div className="text-sm text-slate-500 mt-1">posée et professionnelle</div>
                </button>
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h2 className="text-xl font-bold text-slate-800 text-center mb-2">
                Comment souhaitez-vous l'appeler ?
              </h2>
              <div className="flex flex-wrap gap-2 justify-center mt-4">
                {names.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => persist({ assistant_name: n })}
                    className={`px-4 py-2 rounded-xl border-2 text-sm font-medium ${
                      state.assistant_name === n
                        ? "border-teal-500 bg-teal-50 text-teal-800"
                        : "border-slate-200 text-slate-700 hover:border-slate-300"
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
                className="mt-4 w-full max-w-xs rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
              />
            </>
          )}

          {step === 5 && (
            <>
              <h2 className="text-xl font-bold text-slate-800 text-center mb-4">
                Votre assistante est prête.
              </h2>
              <p className="text-slate-600 text-center max-w-lg mb-2">
                {(state.assistant_name || "Votre assistante")} répond à vos patients 7j/7, propose les créneaux
                disponibles, enregistre automatiquement les rendez-vous dans votre agenda et filtre
                les demandes urgentes selon vos consignes.
              </p>
              <p className="text-xs text-slate-400 text-center mb-6">
                Configuration modifiable à tout moment · Conforme RGPD
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  className="px-6 py-3 rounded-xl border-2 border-slate-200 text-slate-700 font-semibold hover:bg-slate-50"
                >
                  🎧 Écouter {state.assistant_name || "l'assistante"}
                </button>
                <button
                  type="button"
                  onClick={() => setModalOpen(true)}
                  className="px-6 py-3 rounded-xl bg-teal-600 text-white font-semibold hover:bg-teal-700"
                >
                  📞 Recevoir un numéro de test
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Sticky buttons */}
      {!isStep5 && (
        <div className="flex-shrink-0 sticky bottom-0 bg-white border-t border-slate-100 px-6 py-4">
          <div className="max-w-xl mx-auto flex justify-between gap-4">
            {step > 1 ? (
              <button
                type="button"
                onClick={() => persist({ step: step - 1 })}
                className="px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 font-medium hover:bg-slate-50"
              >
                Retour
              </button>
            ) : (
              <div />
            )}
            <button
              type="button"
              onClick={() => persist({ step: step + 1 })}
              disabled={!canContinue()}
              className="px-6 py-2.5 rounded-xl bg-teal-600 text-white font-semibold hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Continuer
            </button>
          </div>
        </div>
      )}

      {/* Modal email */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-4">
              Recevez votre numéro de test
            </h3>
            <input
              type="email"
              value={modalEmail}
              onChange={(e) => setModalEmail(e.target.value)}
              placeholder="votre@email.com"
              className="w-full rounded-xl border border-slate-200 px-4 py-3 mb-4 focus:ring-2 focus:ring-teal-500"
            />
            <label className="flex items-center gap-2 text-sm text-slate-600 mb-4">
              <input
                type="checkbox"
                checked={modalCallback}
                onChange={(e) => setModalCallback(e.target.checked)}
              />
              Je souhaite être rappelé
            </label>
            {commitError && (
              <p className="text-sm text-red-600 mb-2">{commitError}</p>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="flex-1 py-2.5 rounded-xl border border-slate-300 text-slate-700 font-medium"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleCommit}
                disabled={!modalEmail.trim() || commitLoading}
                className="flex-1 py-2.5 rounded-xl bg-teal-600 text-white font-semibold hover:bg-teal-700 disabled:opacity-50"
              >
                {commitLoading ? "Envoi…" : "Recevoir mon numéro"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
