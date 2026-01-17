import React from "react";
import { Stethoscope, Wrench, Scale, Briefcase, Scissors, Building2 } from "lucide-react";

export default function UseCasesSection() {
  const useCases = [
    {
      icon: Stethoscope,
      title: "Médecins",
      description: "Gestion des consultations, rappels patients",
      benefits: ["Plus de RDV manqués", "Planning optimisé", "Rappels automatiques"],
    },
    {
      icon: Wrench,
      title: "Artisans",
      description: "Dépannages urgents, planification d'interventions",
      benefits: ["Qualification automatique", "Géolocalisation", "Urgence identifiée"],
    },
    {
      icon: Scale,
      title: "Avocats",
      description: "Consultations juridiques, rendez-vous clients",
      benefits: ["Qualification préalable", "Agenda structuré", "Confirmation auto"],
    },
    {
      icon: Briefcase,
      title: "Consultants",
      description: "Prise de rendez-vous, gestion clientèle",
      benefits: ["Démultiplication", "Qualification client", "Suivi automatique"],
    },
    {
      icon: Scissors,
      title: "Coiffeurs",
      description: "Réservations, gestion des créneaux",
      benefits: ["Planning en temps réel", "Rappels SMS", "Gestion multi-salons"],
    },
    {
      icon: Building2,
      title: "Services",
      description: "Accueil client, orientation, prise de RDV",
      benefits: ["24/7 disponible", "Tri intelligent", "Transfert si besoin"],
    },
  ];

  return (
    <section className="section-padding bg-gray-50">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">Conçu pour votre métier</h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            UWI s'adapte à chaque profession et à vos besoins spécifiques
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
          {useCases.map((useCase, index) => (
            <div
              key={index}
              className="bg-white rounded-2xl p-6 shadow-soft hover:shadow-medium transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="flex items-start gap-4 mb-4">
                <div className="w-12 h-12 bg-[#0066CC]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                  <useCase.icon className="h-6 w-6 text-[#0066CC]" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-1">{useCase.title}</h3>
                  <p className="text-sm text-gray-600">{useCase.description}</p>
                </div>
              </div>
              <ul className="space-y-2">
                {useCase.benefits.map((benefit, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                    <svg className="h-4 w-4 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {benefit}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-12 animate-slide-up delay-400">
          <a
            href="#contact"
            className="inline-flex items-center gap-2 btn-primary text-lg px-8 py-4"
          >
            Voir comment UWI s'adapte à mon métier
          </a>
        </div>
      </div>
    </section>
  );
}
