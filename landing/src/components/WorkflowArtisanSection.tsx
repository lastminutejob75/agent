import React from "react";
import { ArrowRight, Phone, Calendar, TrendingUp } from "lucide-react";

export default function WorkflowArtisanSection() {
  const steps = [
    {
      number: "1",
      title: "Vos clients appellent",
      description: "Ils contactent votre numéro habituel, comme d'habitude",
      icon: Phone,
      image: "/images/workflow-plumber-calls.jpg",
    },
    {
      number: "2",
      title: "UWI qualifie automatiquement",
      description: "Votre IA pose les bonnes questions, identifie l'urgence et la localisation",
      icon: Calendar,
      image: "/images/workflow-uwi-qualification.jpg",
    },
    {
      number: "3",
      title: "Planning optimisé",
      description: "Vous recevez une notification avec un RDV confirmé et toutes les infos",
      icon: TrendingUp,
      image: "/images/workflow-optimized-planning.jpg",
    },
  ];

  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">
            Comment <span className="text-[#0066CC]">UWI</span> optimise votre planning
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Un processus simple en 3 étapes pour transformer chaque appel en RDV confirmé
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {steps.map((step, index) => (
            <div
              key={index}
              className="relative animate-slide-up card-hover"
              style={{ animationDelay: `${index * 0.15}s` }}
            >
              {/* Image placeholder */}
              <div className="relative h-64 bg-gradient-to-br from-blue-100 to-blue-200 rounded-2xl mb-6 overflow-hidden">
                <img
                  src={step.image}
                  alt={step.title}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    // Fallback vers SVG placeholder
                    const svgFallback = step.image.replace('.jpg', '.svg');
                    e.currentTarget.src = svgFallback;
                  }}
                />
                <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                  <div className="text-center p-4">
                    <step.icon className="h-20 w-20 mx-auto mb-4 text-blue-600 opacity-50" />
                    <p className="text-sm font-medium text-blue-700">{step.title}</p>
                  </div>
                </div>
                <div className="absolute top-4 left-4 bg-[#0066CC] text-white w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold shadow-lg">
                  {step.number}
                </div>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-soft border border-gray-100">
                <h3 className="text-xl font-bold text-gray-900 mb-3">{step.title}</h3>
                <p className="text-gray-600">{step.description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Connector arrows */}
        <div className="hidden md:flex items-center justify-center gap-4 mt-8 mb-12">
          <ArrowRight className="h-6 w-6 text-gray-400" />
          <ArrowRight className="h-6 w-6 text-gray-400" />
        </div>

        {/* CTA */}
        <div className="text-center mt-12 animate-slide-up delay-400">
          <a
            href="#contact"
            className="inline-flex items-center gap-2 btn-primary text-lg px-8 py-4"
          >
            Découvrir comment ça marche
            <ArrowRight className="h-5 w-5" />
          </a>
        </div>
      </div>
    </section>
  );
}
