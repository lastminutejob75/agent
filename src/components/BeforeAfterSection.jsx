import React from "react";
import { ArrowRight, Phone, Calendar, Users, TrendingUp } from "lucide-react";

export default function BeforeAfterSection() {
  const beforeScenarios = [
    {
      title: "Avant",
      subtitle: "Appels manqués",
      description: "Patients mécontents, pertes de RDV et de CA",
      image: "/images/before-doctor.jpg", // Photo médecin au téléphone stressé
    },
    {
      title: "Avant",
      subtitle: "Opportunités perdues",
      description: "Artisan indisponible, client potentiel perdu",
      image: "/images/before-artisan.jpg", // Photo artisan débordé
    },
  ];

  const afterScenarios = [
    {
      title: "Après",
      subtitle: "RDV pris en intervention",
      description: "Plannings pleins, maximisation des interventions",
      image: "/images/after-planning.jpg", // Photo personne consultant app UWI
    },
    {
      title: "Après",
      subtitle: "Accueil 24/7 optimisé",
      description: "Tous les appels traités, clients satisfaits",
      image: "/images/after-satisfied.jpg", // Photo client satisfait
    },
  ];

  return (
    <section className="py-20 bg-gradient-to-br from-gray-50 to-white">
      <div className="max-w-7xl mx-auto px-6">
        {/* Header avec flèche */}
        <div className="text-center mb-16 animate-slide-up">
          <div className="flex items-center justify-center gap-6 mb-8">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900">
              Sans <span className="text-gray-600">UWI</span>...
            </h2>
            <ArrowRight className="h-12 w-12 text-[#0066CC] hidden md:block" />
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900">
              Avec <span className="text-[#0066CC]">UWI</span>
            </h2>
          </div>
        </div>

        {/* Grid Before/After */}
        <div className="grid lg:grid-cols-4 gap-6 max-w-7xl mx-auto">
          {/* AVANT - 2 colonnes */}
          {beforeScenarios.map((scenario, index) => (
            <div
              key={index}
              className="relative rounded-2xl overflow-hidden shadow-lg hover:shadow-xl transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              {/* Image placeholder */}
              <div className="relative h-64 bg-gradient-to-br from-red-100 to-red-200">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-red-600 p-4">
                    <Phone className="h-16 w-16 mx-auto mb-4 opacity-50" />
                    <p className="text-sm font-medium">Image: {scenario.image}</p>
                  </div>
                </div>
                {/* Badge Avant */}
                <div className="absolute top-4 left-4 bg-white px-4 py-2 rounded-full shadow-lg">
                  <span className="text-sm font-bold text-gray-900">{scenario.title}</span>
                </div>
              </div>

              {/* Content */}
              <div className="bg-white p-6">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-bold text-lg text-gray-900 mb-1">{scenario.subtitle}</h3>
                    <p className="text-sm text-gray-600">{scenario.description}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* APRÈS - 2 colonnes */}
          {afterScenarios.map((scenario, index) => (
            <div
              key={index}
              className="relative rounded-2xl overflow-hidden shadow-lg hover:shadow-2xl transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${(index + 2) * 0.1}s` }}
            >
              {/* Image placeholder */}
              <div className="relative h-64 bg-gradient-to-br from-green-100 to-emerald-200">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-green-600 p-4">
                    <TrendingUp className="h-16 w-16 mx-auto mb-4 opacity-50" />
                    <p className="text-sm font-medium">Image: {scenario.image}</p>
                  </div>
                </div>
                {/* Badge Après */}
                <div className="absolute top-4 left-4 bg-[#0066CC] px-4 py-2 rounded-full shadow-lg">
                  <span className="text-sm font-bold text-white">{scenario.title}</span>
                </div>
              </div>

              {/* Content */}
              <div className="bg-white p-6">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-bold text-lg text-gray-900 mb-1">{scenario.subtitle}</h3>
                    <p className="text-sm text-gray-600">{scenario.description}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-12 animate-slide-up delay-400">
          <a
            href="#contact"
            className="inline-flex items-center gap-2 bg-[#0066CC] text-white font-semibold rounded-2xl px-8 py-4 text-lg hover:bg-[#0052A3] transition-colors"
          >
            Transformer mon activité maintenant
            <ArrowRight className="h-5 w-5" />
          </a>
        </div>
      </div>
    </section>
  );
}