// Page de découverte client — quelques questions pour orienter (questions à définir avec l'expert)
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowLeft, Sparkles } from "lucide-react";

// Questions à personnaliser avec l'expert (structure prête)
const QUESTIONS = [
  {
    id: "q1",
    label: "Quel est votre profil ?",
    placeholder: "Ex. cabinet médical, centre de soins…",
    type: "text",
  },
  {
    id: "q2",
    label: "Combien d'appels recevez-vous en moyenne par jour ?",
    type: "choice",
    options: ["Moins de 10", "10 à 30", "30 à 50", "Plus de 50"],
  },
  {
    id: "q3",
    label: "Quelle est votre priorité aujourd'hui ?",
    type: "choice",
    options: ["Ne plus rater d'appels", "Prendre les RDV automatiquement", "Dégager du temps pour les patients", "Autre"],
  },
];

export default function DecouverteClient() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const isLastStep = step === QUESTIONS.length;
  const currentQuestion = QUESTIONS[step];

  const inputClass =
    "w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-3 text-white placeholder-slate-500 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-colors";
  const btnPrimary =
    "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black px-6 py-3 hover:shadow-xl hover:shadow-teal-500/30 transition-all";
  const btnSecondary =
    "inline-flex items-center justify-center gap-2 rounded-xl border border-slate-600 text-slate-300 hover:bg-slate-800 px-6 py-3 font-semibold transition-colors";

  function setAnswer(value) {
    if (currentQuestion) setAnswers((a) => ({ ...a, [currentQuestion.id]: value }));
  }

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="rounded-2xl border border-slate-700 bg-slate-900/80 backdrop-blur p-6 sm:p-10 shadow-2xl">
        {/* Progression */}
        <div className="mb-8">
          <div className="flex justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Étape {Math.min(step + 1, QUESTIONS.length)} sur {QUESTIONS.length}</span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-teal-500 to-cyan-400 rounded-full transition-all duration-300"
              style={{ width: `${((step + 1) / QUESTIONS.length) * 100}%` }}
            />
          </div>
        </div>

        {!isLastStep ? (
          <>
            {step === 0 && (
              <p className="text-teal-400 font-semibold text-sm uppercase tracking-wider mb-4">
                Découvrez votre solution
              </p>
            )}
            <h2 className="text-xl sm:text-2xl font-black text-white mb-2">
              {currentQuestion.label}
            </h2>
            {currentQuestion.type === "text" && (
              <input
                type="text"
                value={answers[currentQuestion.id] || ""}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={currentQuestion.placeholder}
                className={inputClass}
                autoFocus
              />
            )}
            {currentQuestion.type === "choice" && (
              <div className="space-y-2 mt-4">
                {(currentQuestion.options || []).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setAnswer(opt)}
                    className={`w-full text-left rounded-xl border px-4 py-3 font-medium transition-all ${
                      answers[currentQuestion.id] === opt
                        ? "border-teal-500 bg-teal-500/20 text-teal-300"
                        : "border-slate-600 bg-slate-800/50 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-3 mt-8">
              {step > 0 && (
                <button
                  type="button"
                  onClick={() => setStep((s) => s - 1)}
                  className={btnSecondary}
                >
                  <ArrowLeft className="w-4 h-4" />
                  Retour
                </button>
              )}
              <button
                type="button"
                onClick={() => setStep((s) => s + 1)}
                disabled={
                  currentQuestion.type === "choice"
                    ? !answers[currentQuestion.id]
                    : false
                }
                className={btnPrimary}
              >
                {step === QUESTIONS.length - 1 ? "Voir ma recommandation" : "Suivant"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          <div className="text-center py-4">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-teal-500/20 mb-6">
              <Sparkles className="w-8 h-8 text-teal-400" />
            </div>
            <h2 className="text-2xl font-black text-white mb-2">
              Merci pour ces précisions
            </h2>
            <p className="text-slate-400 mb-8 max-w-md mx-auto">
              Nous avons une meilleure idée de vos besoins. Passez à l'essai gratuit pour découvrir UWi adapté à votre activité.
            </p>
            <Link to="/essai-gratuit" className={btnPrimary}>
              Accéder à mon essai gratuit 1 mois
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
