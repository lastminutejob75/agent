import React from "react";
import { Calendar, RefreshCw, TrendingUp, AlertCircle, CheckCircle, X, ArrowRight, Clock, Smile } from "lucide-react";

export default function CancellationManagementSection() {
  const scenario = {
    problem: {
      title: "Heures de pointe",
      description: "Appels ignorés, annulations de RDV, « no-shows » des clients",
      impact: "Appels ignorés, TPE défliés",
      image: "/images/before-stressed-professional.svg",
    },
    solution1: {
      title: "Relance Automatique",
      description: "UWI recontacte et propose un créneau libre à chaque annulation",
      message: "Nouveau créneau : Votre RDV annulé 17:45 a été replanifié demain 11:30.",
      image: "/images/workflow-optimized-planning.svg",
    },
    solution2: {
      title: "Planning Rempli",
      description: "Clients recontactés, calendrier optimisé, taux de remplissage maximal",
      image: "/images/after-organized-professional.svg",
    },
  };

  return (
    <section className="section-padding bg-gradient-to-br from-slate-50 via-white to-red-50/20">
      <div className="container-custom">
        {/* Header */}
        <div className="text-center mb-16 animate-slide-up">
          <div className="inline-block bg-gradient-to-r from-red-100 to-orange-100 text-red-700 px-5 py-2.5 rounded-full text-sm font-bold mb-6 shadow-md">
            Gestion Intelligente des Annulations
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            <span className="text-[#0066CC]">UWI</span> Réduit vos <span className="text-red-600">Annulations</span><br/>
            et Remplit Votre Planning
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Ne perdez plus de temps ni d'argent avec les créneaux vides et les annulations de dernière minute
          </p>

          {/* Icons flow - amélioration visuelle */}
          <div className="flex items-center justify-center gap-4 mt-10">
            <div className="flex flex-col items-center">
              <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-red-600 rounded-2xl flex items-center justify-center shadow-lg mb-2">
                <Calendar className="h-8 w-8 text-white" />
              </div>
              <span className="text-xs font-medium text-gray-500">Annulation</span>
            </div>

            <div className="flex items-center gap-2 mb-6">
              <div className="w-12 h-0.5 bg-gradient-to-r from-red-400 to-green-400"></div>
              <ArrowRight className="h-6 w-6 text-gray-400" />
            </div>

            <div className="flex flex-col items-center">
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center shadow-lg mb-2">
                <RefreshCw className="h-8 w-8 text-white" />
              </div>
              <span className="text-xs font-medium text-gray-500">Relance Auto</span>
            </div>

            <div className="flex items-center gap-2 mb-6">
              <div className="w-12 h-0.5 bg-gradient-to-r from-green-400 to-blue-400"></div>
              <ArrowRight className="h-6 w-6 text-gray-400" />
            </div>

            <div className="flex flex-col items-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg mb-2">
                <TrendingUp className="h-8 w-8 text-white" />
              </div>
              <span className="text-xs font-medium text-gray-500">Planning Plein</span>
            </div>
          </div>
        </div>

        {/* Before/After Grid - Design amélioré */}
        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto mb-16">
          {/* Problem Card */}
          <div className="animate-slide-up">
            <div className="rounded-3xl overflow-hidden shadow-xl hover:shadow-2xl transition-all duration-500 bg-white h-full flex flex-col border-2 border-red-100 hover:border-red-200">
              {/* Image section */}
              <div className="relative h-80 overflow-hidden bg-gradient-to-br from-red-100 to-red-200">
                <img
                  src={scenario.problem.image}
                  alt={scenario.problem.title}
                  className="w-full h-full object-cover transition-transform duration-700 hover:scale-105"
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />

                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-red-900/40 via-red-900/10 to-transparent"></div>

                {/* Problem badge */}
                <div className="absolute top-6 right-6 bg-red-500 text-white rounded-full p-4 shadow-2xl">
                  <AlertCircle className="h-7 w-7" strokeWidth={2.5} />
                </div>

                {/* Problem indicator at bottom */}
                <div className="absolute bottom-6 left-6 right-6">
                  <div className="bg-white/95 backdrop-blur-md rounded-2xl p-5 shadow-2xl border-2 border-red-200">
                    <div className="flex items-start gap-3">
                      <Clock className="h-6 w-6 text-red-600 flex-shrink-0" />
                      <div>
                        <p className="font-bold text-red-900 text-sm mb-1">Heures de pointe</p>
                        <p className="text-xs text-red-700">Appels ignorés, TPE défliés</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 flex-1 flex flex-col bg-gradient-to-br from-red-50/50 to-white">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                    <X className="h-5 w-5 text-red-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-bold text-gray-900 mb-2">{scenario.problem.title}</p>
                    <p className="text-sm text-gray-700">{scenario.problem.description}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Solution 1: Auto Rebook Card */}
          <div className="animate-slide-up delay-100">
            <div className="rounded-3xl overflow-hidden shadow-xl hover:shadow-2xl transition-all duration-500 bg-white h-full flex flex-col border-2 border-green-200 hover:border-green-300">
              {/* Image section */}
              <div className="relative h-80 overflow-hidden bg-gradient-to-br from-green-100 to-green-200">
                <img
                  src={scenario.solution1.image}
                  alt={scenario.solution1.title}
                  className="w-full h-full object-cover transition-transform duration-700 hover:scale-105"
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />

                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-green-900/40 via-green-900/10 to-transparent"></div>

                {/* Success badge */}
                <div className="absolute top-6 right-6 bg-green-500 text-white rounded-full p-4 shadow-2xl">
                  <CheckCircle className="h-7 w-7" strokeWidth={2.5} />
                </div>

                {/* WhatsApp mockup - enhanced */}
                <div className="absolute bottom-6 left-6 right-6">
                  <div className="bg-gradient-to-br from-green-50 to-white/95 backdrop-blur-md rounded-2xl p-5 shadow-2xl border-2 border-green-200">
                    <div className="flex items-start gap-3 mb-3 pb-3 border-b border-green-200">
                      <div className="bg-green-500 rounded-xl p-2.5">
                        <RefreshCw className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                          <p className="font-bold text-gray-900 text-xs">Nouveau créneau</p>
                        </div>
                        <p className="text-xs text-gray-700">
                          Votre RDV annulé 17:45 a été replanifié demain 11:30
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className="flex-1 bg-green-500 text-white text-xs py-2 px-3 rounded-lg font-bold hover:bg-green-600 transition-colors">
                        ✓ Confirmer
                      </button>
                      <button className="flex-1 bg-gray-100 text-gray-700 text-xs py-2 px-3 rounded-lg font-medium hover:bg-gray-200 transition-colors">
                        Autre heure
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 flex-1 flex flex-col bg-gradient-to-br from-green-50/50 to-white">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                    <RefreshCw className="h-5 w-5 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-bold text-gray-900 mb-2">{scenario.solution1.title}</p>
                    <p className="text-sm text-gray-700">{scenario.solution1.description}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Solution 2: Optimized Planning Card */}
          <div className="animate-slide-up delay-200">
            <div className="rounded-3xl overflow-hidden shadow-xl hover:shadow-2xl transition-all duration-500 bg-white h-full flex flex-col border-2 border-blue-200 hover:border-blue-300">
              {/* Image section */}
              <div className="relative h-80 overflow-hidden bg-gradient-to-br from-blue-100 to-blue-200">
                <img
                  src={scenario.solution2.image}
                  alt={scenario.solution2.title}
                  className="w-full h-full object-cover transition-transform duration-700 hover:scale-105"
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />

                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-blue-900/40 via-blue-900/10 to-transparent"></div>

                {/* Success badge */}
                <div className="absolute top-6 right-6 bg-blue-500 text-white rounded-full p-4 shadow-2xl">
                  <TrendingUp className="h-7 w-7" strokeWidth={2.5} />
                </div>

                {/* Happy customer indicator */}
                <div className="absolute bottom-6 left-6 right-6">
                  <div className="bg-white/95 backdrop-blur-md rounded-2xl p-5 shadow-2xl border-2 border-blue-200">
                    <div className="flex items-start gap-3">
                      <Smile className="h-6 w-6 text-blue-600 flex-shrink-0" />
                      <div>
                        <p className="font-bold text-blue-900 text-sm mb-1">Planning Optimisé</p>
                        <p className="text-xs text-blue-700">Taux de remplissage: 95%</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 flex-1 flex flex-col bg-gradient-to-br from-blue-50/50 to-white">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                    <TrendingUp className="h-5 w-5 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-bold text-gray-900 mb-2">{scenario.solution2.title}</p>
                    <p className="text-sm text-gray-700">{scenario.solution2.description}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Stats bar - Design premium */}
        <div className="bg-gradient-to-r from-[#0066CC] via-purple-600 to-[#0052A3] rounded-3xl p-10 md:p-14 shadow-2xl max-w-6xl mx-auto mb-12 animate-slide-up delay-300">
          <div className="grid md:grid-cols-3 gap-10 text-center text-white">
            <div className="space-y-3">
              <div className="text-6xl font-bold drop-shadow-lg">-80%</div>
              <p className="text-blue-100 font-semibold text-lg">d'annulations non gérées</p>
              <div className="w-16 h-1 bg-white/30 mx-auto rounded-full"></div>
            </div>
            <div className="space-y-3">
              <div className="text-6xl font-bold drop-shadow-lg">+35%</div>
              <p className="text-purple-100 font-semibold text-lg">de taux de remplissage</p>
              <div className="w-16 h-1 bg-white/30 mx-auto rounded-full"></div>
            </div>
            <div className="space-y-3">
              <div className="text-6xl font-bold drop-shadow-lg">100%</div>
              <p className="text-blue-100 font-semibold text-lg">des créneaux optimisés</p>
              <div className="w-16 h-1 bg-white/30 mx-auto rounded-full"></div>
            </div>
          </div>
        </div>

        {/* Bottom summary badges - Design modernisé */}
        <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto animate-slide-up delay-400">
          <div className="bg-white rounded-2xl p-6 shadow-lg border-2 border-red-100 hover:border-red-300 transition-all duration-300 group transform hover:-translate-y-1">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110 shadow-md">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <X className="h-4 w-4 text-red-600" />
                  <p className="font-bold text-gray-900 text-sm">Heures de pointe</p>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">
                  Appels ignorés, annulations de RDV, « no-shows » des clients
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border-2 border-green-100 hover:border-green-300 transition-all duration-300 group transform hover:-translate-y-1">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110 shadow-md">
                <RefreshCw className="h-6 w-6 text-green-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <p className="font-bold text-gray-900 text-sm">Relance Automatique</p>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">
                  UWI recontacte et propose un créneau libre à chaque annulation
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border-2 border-blue-100 hover:border-blue-300 transition-all duration-300 group transform hover:-translate-y-1">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110 shadow-md">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="h-4 w-4 text-blue-600" />
                  <p className="font-bold text-gray-900 text-sm">Planning Rempli</p>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">
                  Clients recontactés, calendrier optimisé, taux de remplissage maximal
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CTA - Design premium */}
        <div className="text-center mt-16 animate-slide-up delay-500">
          <a
            href="/creer-assistante?new=1"
            className="inline-flex items-center gap-3 bg-gradient-to-r from-[#0066CC] to-[#0052A3] text-white font-bold text-lg px-10 py-5 rounded-2xl hover:shadow-2xl hover:scale-105 transition-all duration-300 shadow-lg"
          >
            Optimiser mon planning
            <ArrowRight className="h-6 w-6" />
          </a>
          <p className="mt-6 text-sm text-gray-500 font-medium">
            Réduisez vos pertes et maximisez votre chiffre d'affaires
          </p>
        </div>
      </div>
    </section>
  );
}
