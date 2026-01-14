import React from "react";
import { X, Check, TrendingDown, TrendingUp, ArrowRight } from "lucide-react";

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6 lg:px-8">{children}</div>
);

export default function ComparisonSection() {
  const before = [
    {
      problem: "30% d'appels manqués",
      impact: "Clients perdus définitivement",
      cost: "↓ -10K€/an en CA",
    },
    {
      problem: "3h/jour de gestion RDV",
      impact: "Temps perdu sur l'administration",
      cost: "↓ -15h/semaine productive",
    },
    {
      problem: "25% de no-shows",
      impact: "Planning troué, pertes sèches",
      cost: "↓ -5K€/an",
    },
    {
      problem: "Pas de suivi client",
      impact: "Expérience client médiocre",
      cost: "↓ Réputation impactée",
    },
  ];

  const after = [
    {
      solution: "0% d'appels manqués",
      impact: "Tous les clients sont pris en charge",
      gain: "↑ +10K€/an en CA",
    },
    {
      solution: "Gestion automatisée 24/7",
      impact: "Focus à 100% sur votre métier",
      gain: "↑ +15h/semaine productive",
    },
    {
      solution: "5% de no-shows seulement",
      impact: "Rappels auto, planning optimisé",
      gain: "↑ +5K€/an récupérés",
    },
    {
      solution: "Suivi client automatique",
      impact: "Expérience premium garantie",
      gain: "↑ Satisfaction x2",
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-white">
      <Container>
        {/* Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
            Avant vs Après <span className="text-[#0066CC]">UWI</span>
          </h2>
          <p className="text-lg text-slate-600 max-w-3xl mx-auto">
            Découvrez l'impact concret de l'IA sur votre activité
          </p>
        </div>

        {/* Comparison Grid */}
        <div className="grid md:grid-cols-2 gap-8 max-w-6xl mx-auto">
          {/* AVANT */}
          <div className="relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-red-500 text-white px-6 py-2 rounded-full text-sm font-bold shadow-lg z-10">
              <TrendingDown className="inline h-4 w-4 mr-1" />
              SANS UWI
            </div>

            <div className="bg-gradient-to-br from-red-50 to-red-100/50 border-2 border-red-200 rounded-2xl p-8 pt-12 h-full">
              <div className="space-y-6">
                {before.map((item, index) => (
                  <div
                    key={index}
                    className="bg-white/80 backdrop-blur-sm rounded-xl p-5 border border-red-200/50 hover:shadow-md transition-all"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className="mt-1 flex-shrink-0">
                        <X className="h-5 w-5 text-red-500" />
                      </div>
                      <div className="flex-1">
                        <p className="font-bold text-[#111827] mb-1">{item.problem}</p>
                        <p className="text-sm text-slate-600">{item.impact}</p>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-red-600 flex items-center gap-2 ml-8">
                      {item.cost}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-4 bg-red-100 rounded-lg border border-red-200">
                <p className="text-sm font-bold text-red-800 text-center">
                  Total pertes estimées : -30K€/an 📉
                </p>
              </div>
            </div>
          </div>

          {/* APRÈS */}
          <div className="relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-green-500 text-white px-6 py-2 rounded-full text-sm font-bold shadow-lg z-10">
              <TrendingUp className="inline h-4 w-4 mr-1" />
              AVEC UWI
            </div>

            <div className="bg-gradient-to-br from-green-50 to-emerald-100/50 border-2 border-green-300 rounded-2xl p-8 pt-12 h-full shadow-lg">
              <div className="space-y-6">
                {after.map((item, index) => (
                  <div
                    key={index}
                    className="bg-white/90 backdrop-blur-sm rounded-xl p-5 border border-green-200/50 hover:shadow-md transition-all"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className="mt-1 flex-shrink-0">
                        <Check className="h-5 w-5 text-green-600" />
                      </div>
                      <div className="flex-1">
                        <p className="font-bold text-[#111827] mb-1">{item.solution}</p>
                        <p className="text-sm text-slate-600">{item.impact}</p>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-green-600 flex items-center gap-2 ml-8">
                      {item.gain}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-4 bg-green-100 rounded-lg border border-green-300">
                <p className="text-sm font-bold text-green-800 text-center">
                  Total gains estimés : +30K€/an 📈
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-12">
          <a
            href="#contact"
            className="inline-flex items-center gap-2 bg-[#0066CC] text-white font-semibold text-lg px-8 py-4 rounded-lg hover:bg-[#0052A3] transition-all shadow-lg hover:scale-105"
          >
            Essayer gratuitement 14 jours
            <TrendingUp className="h-5 w-5" />
          </a>
          <p className="mt-4 text-sm text-slate-500">
            Sans carte bancaire • Sans engagement • Configuration en 30 minutes
          </p>
        </div>
      </Container>
    </section>
  );
}
