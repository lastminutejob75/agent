import React, { useState } from "react";
import { TrendingUp, Phone, Clock, Users, ArrowRight } from "lucide-react";

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6 lg:px-8">{children}</div>
);

export default function ROICalculator() {
  const [callsPerDay, setCallsPerDay] = useState(30);
  const [missedCallRate, setMissedCallRate] = useState(30);
  const [avgClientValue, setAvgClientValue] = useState(150);
  const [hoursPerWeek, setHoursPerWeek] = useState(10);

  // Calculs
  const missedCallsPerDay = (callsPerDay * missedCallRate) / 100;
  const missedCallsPerMonth = missedCallsPerDay * 22; // jours ouvrables
  const monthlyLostRevenue = missedCallsPerMonth * avgClientValue * 0.3; // 30% de conversion
  const yearlyLostRevenue = monthlyLostRevenue * 12;

  const hoursSavedPerMonth = hoursPerWeek * 4;
  const monthlyCost = hoursSavedPerMonth * 50; // valeur horaire estimée
  const yearlyCost = monthlyCost * 12;

  const totalYearlySavings = yearlyLostRevenue + yearlyCost;
  const uwiCost = 249 * 12; // Plan Pro annuel
  const netGain = totalYearlySavings - uwiCost;
  const roi = ((netGain / uwiCost) * 100).toFixed(0);

  return (
    <section className="py-20 md:py-28 bg-gradient-to-br from-blue-50/50 via-white to-blue-50/30">
      <Container>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
              Calculez votre <span className="text-[#0066CC]">ROI avec UWI</span>
            </h2>
            <p className="text-lg text-slate-600 max-w-3xl mx-auto">
              Découvrez combien vous pourriez économiser et gagner chaque année
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Calculateur */}
            <div className="bg-white rounded-2xl p-8 shadow-medium">
              <h3 className="text-xl font-bold mb-6 text-[#111827]">Votre situation actuelle</h3>

              <div className="space-y-6">
                {/* Appels par jour */}
                <div>
                  <label className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                      <Phone className="h-4 w-4 text-[#0066CC]" />
                      Appels reçus par jour
                    </span>
                    <span className="text-lg font-bold text-[#0066CC]">{callsPerDay}</span>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    value={callsPerDay}
                    onChange={(e) => setCallsPerDay(Number(e.target.value))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0066CC]"
                  />
                </div>

                {/* Taux d'appels manqués */}
                <div>
                  <label className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-[#0066CC]" />
                      Taux d'appels manqués
                    </span>
                    <span className="text-lg font-bold text-[#0066CC]">{missedCallRate}%</span>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="50"
                    value={missedCallRate}
                    onChange={(e) => setMissedCallRate(Number(e.target.value))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0066CC]"
                  />
                </div>

                {/* Valeur client moyenne */}
                <div>
                  <label className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                      <Users className="h-4 w-4 text-[#0066CC]" />
                      Valeur client moyenne
                    </span>
                    <span className="text-lg font-bold text-[#0066CC]">{avgClientValue}€</span>
                  </label>
                  <input
                    type="range"
                    min="50"
                    max="500"
                    step="10"
                    value={avgClientValue}
                    onChange={(e) => setAvgClientValue(Number(e.target.value))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0066CC]"
                  />
                </div>

                {/* Heures admin par semaine */}
                <div>
                  <label className="flex items-center justify-between mb-3">
                    <span className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                      <Clock className="h-4 w-4 text-[#0066CC]" />
                      Heures admin/semaine
                    </span>
                    <span className="text-lg font-bold text-[#0066CC]">{hoursPerWeek}h</span>
                  </label>
                  <input
                    type="range"
                    min="2"
                    max="20"
                    value={hoursPerWeek}
                    onChange={(e) => setHoursPerWeek(Number(e.target.value))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#0066CC]"
                  />
                </div>
              </div>
            </div>

            {/* Résultats */}
            <div className="bg-gradient-to-br from-[#0066CC] to-[#0052A3] text-white rounded-2xl p-8 shadow-hard">
              <h3 className="text-xl font-bold mb-6">Vos économies avec UWI</h3>

              <div className="space-y-6">
                {/* Revenue perdu récupéré */}
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
                  <div className="text-sm font-medium mb-1 opacity-90">CA récupéré</div>
                  <div className="text-3xl font-bold">
                    {Math.round(yearlyLostRevenue).toLocaleString()}€
                    <span className="text-sm font-normal opacity-90">/an</span>
                  </div>
                  <div className="text-xs opacity-75 mt-1">
                    {Math.round(missedCallsPerMonth)} appels manqués récupérés/mois
                  </div>
                </div>

                {/* Temps économisé */}
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
                  <div className="text-sm font-medium mb-1 opacity-90">Temps économisé</div>
                  <div className="text-3xl font-bold">
                    {Math.round(yearlyCost).toLocaleString()}€
                    <span className="text-sm font-normal opacity-90">/an</span>
                  </div>
                  <div className="text-xs opacity-75 mt-1">
                    {hoursSavedPerMonth * 12}h/an libérées pour votre métier
                  </div>
                </div>

                {/* Gain net */}
                <div className="bg-white rounded-xl p-6 text-[#111827] shadow-lg">
                  <div className="text-center">
                    <div className="text-sm font-semibold text-slate-600 mb-2">Gain net annuel</div>
                    <div className="text-5xl font-black text-[#0066CC] mb-2">
                      +{Math.round(netGain / 1000)}K€
                    </div>
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-100 text-green-700 rounded-full text-sm font-bold">
                      <TrendingUp className="h-4 w-4" />
                      ROI de {roi}%
                    </div>
                  </div>
                </div>

                {/* CTA */}
                <a
                  href="#contact"
                  className="block w-full bg-white hover:bg-slate-50 text-[#0066CC] font-bold py-4 px-6 rounded-lg transition-all hover:scale-105 active:scale-95 shadow-lg text-center"
                >
                  Créer mon assistant
                  <ArrowRight className="inline ml-2 h-5 w-5" />
                </a>

                <p className="text-xs text-center opacity-75">
                  Coût UWI : {uwiCost.toLocaleString()}€/an • ROI atteint en moins de 2 mois
                </p>
              </div>
            </div>
          </div>

          {/* Bottom note */}
          <div className="mt-12 text-center">
            <div className="inline-flex items-center gap-2 px-6 py-3 bg-white rounded-full shadow-soft">
              <span className="text-sm text-slate-600">
                💡 Calculs conservateurs basés sur nos données clients réelles
              </span>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
