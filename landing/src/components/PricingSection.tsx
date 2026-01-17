import React from "react";
import { Check, ArrowRight } from "lucide-react";

export default function PricingSection() {
  const plans = [
    {
      name: "Starter",
      price: "99",
      period: "mois",
      description: "Parfait pour commencer",
      features: [
        "Jusqu'à 500 appels/mois",
        "Prise de RDV automatique",
        "Qualification basique",
        "Support par email",
      ],
      cta: "Commencer",
      popular: false,
    },
    {
      name: "Pro",
      price: "249",
      period: "mois",
      description: "Pour les professionnels",
      features: [
        "Appels illimités",
        "Qualification avancée",
        "Intégrations agenda",
        "Support prioritaire 7j/7",
        "Analytics détaillés",
        "Personnalisation avancée",
      ],
      cta: "Essayer 14 jours",
      popular: true,
    },
    {
      name: "Enterprise",
      price: "Sur mesure",
      period: "",
      description: "Pour les grandes structures",
      features: [
        "Tout du plan Pro",
        "Compte dédié",
        "Formation équipe",
        "Support dédié",
        "Personnalisation complète",
        "API avancée",
      ],
      cta: "Nous contacter",
      popular: false,
    },
  ];

  return (
    <section id="pricing" className="section-padding bg-gray-50">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">Tarifs transparents</h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Choisissez le plan qui correspond à vos besoins
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-white rounded-2xl p-8 shadow-soft hover:shadow-hard transition-all card-hover animate-slide-up ${
                plan.popular ? "border-2 border-[#0066CC] shadow-lg" : "border border-gray-200"
              }`}
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-[#0066CC] text-white px-4 py-1 rounded-full text-sm font-bold">
                  Le plus populaire
                </div>
              )}
              
              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                <p className="text-gray-600 mb-4">{plan.description}</p>
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-4xl font-bold text-gray-900">{plan.price}</span>
                  {plan.period && <span className="text-gray-600">€/{plan.period}</span>}
                </div>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href="#contact"
                className={`block w-full text-center py-4 px-6 rounded-xl font-semibold transition-all ${
                  plan.popular
                    ? "bg-[#0066CC] text-white hover:bg-[#0052A3] shadow-lg"
                    : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                }`}
              >
                {plan.cta}
              </a>
            </div>
          ))}
        </div>

        <div className="text-center mt-12 text-sm text-gray-600">
          <p>Tous les plans incluent l'essai gratuit de 14 jours • Sans engagement</p>
        </div>
      </div>
    </section>
  );
}
