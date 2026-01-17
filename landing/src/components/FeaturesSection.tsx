import React from "react";
import { Phone, Calendar, Headphones, Shield, Zap, BarChart3 } from "lucide-react";

export default function FeaturesSection() {
  const features = [
    {
      icon: Phone,
      title: "Réponse 24/7",
      description: "Votre IA répond instantanément à chaque appel, même en dehors des horaires d'ouverture.",
    },
    {
      icon: Calendar,
      title: "Prise de RDV automatique",
      description: "Propose des créneaux disponibles, confirme et envoie les rappels automatiquement.",
    },
    {
      icon: Headphones,
      title: "Qualification intelligente",
      description: "Pose les bonnes questions pour comprendre la demande et identifier l'urgence.",
    },
    {
      icon: Shield,
      title: "Transfert humain",
      description: "Transfère à un humain si la demande sort du cadre ou nécessite une intervention.",
    },
    {
      icon: Zap,
      title: "Configuration rapide",
      description: "En 30 minutes, votre IA est configurée et prête à répondre aux appels.",
    },
    {
      icon: BarChart3,
      title: "Analytics en temps réel",
      description: "Suivez les appels, les RDV pris, les conversions et les performances.",
    },
  ];

  return (
    <section id="features" className="section-padding bg-white">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">
            Toutes les fonctionnalités dont vous avez besoin
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Un outil complet pour automatiser votre accueil client
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-2xl p-6 hover:border-[#0066CC] hover:shadow-lg transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="w-12 h-12 bg-[#0066CC]/10 rounded-xl flex items-center justify-center mb-4">
                <feature.icon className="h-6 w-6 text-[#0066CC]" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">{feature.title}</h3>
              <p className="text-gray-600 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
