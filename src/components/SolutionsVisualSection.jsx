import React from "react";
import { Calendar, Headphones, MessageCircle, CheckCircle } from "lucide-react";

export default function SolutionsVisualSection() {
  const solutions = [
    {
      icon: Calendar,
      title: "Prise de Rendez-vous",
      description: "Optimisez votre agenda et diminuez vos rendez-vous manqués",
      benefits: ["Optimisez votre agenda et diminuez vos rendez-vous manqués"],
      image: "/images/solution-rdv.jpg",
      color: "from-blue-500 to-blue-600",
    },
    {
      icon: Headphones,
      title: "SAV & Support",
      description: "Libérez-vous des appels répétitifs, concentrez-vous sur votre métier",
      benefits: ["Libérez-vous des appels répétitifs, concentrez-vous sur votre métier"],
      image: "/images/solution-sav.jpg",
      color: "from-green-500 to-green-600",
    },
    {
      icon: MessageCircle,
      title: "Questions Techniques",
      description: "Offrez des réponses instantanées, contactez vos clients sur leur canal préféré",
      benefits: ["Contactez vos clients sur leur canal préféré"],
      image: "/images/solution-questions.jpg",
      color: "from-purple-500 to-purple-600",
    },
  ];

  return (
    <section className="py-20 bg-gradient-to-br from-gray-50 to-white">
      <div className="max-w-7xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Comment <span className="text-[#0066CC]">UWI</span> Résout Vos Problèmes
          </h2>

          {/* Icons flow */}
          <div className="flex items-center justify-center gap-8 mt-8">
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Calendar className="h-8 w-8 text-[#0066CC]" />
            </div>
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Headphones className="h-8 w-8 text-[#0066CC]" />
            </div>
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <MessageCircle className="h-8 w-8 text-[#0066CC]" />
            </div>
          </div>
        </div>

        {/* 3 solutions avec images */}
        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {solutions.map((solution, index) => (
            <div
              key={index}
              className="relative animate-slide-up card-hover"
              style={{ animationDelay: `${index * 0.15}s` }}
            >
              <div className="rounded-2xl overflow-hidden shadow-lg hover:shadow-2xl transition-all">
                {/* Image placeholder */}
                <div className={`relative h-64 bg-gradient-to-br ${solution.color}`}>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center text-white p-4">
                      <solution.icon className="h-20 w-20 mx-auto mb-4 opacity-70" />
                      <p className="text-sm font-medium">Image: {solution.image}</p>
                    </div>
                  </div>

                  {/* Badge avec checkmark */}
                  <div className="absolute top-4 left-4 bg-white rounded-full p-3 shadow-lg">
                    <CheckCircle className="h-8 w-8 text-[#0066CC]" />
                  </div>
                </div>

                {/* Content */}
                <div className="bg-white p-6">
                  <h3 className="font-bold text-xl text-gray-900 mb-3">{solution.title}</h3>
                  
                  <div className="flex items-start gap-2 mb-4">
                    <span className="text-2xl">+</span>
                    <p className="text-gray-700">{solution.description}</p>
                  </div>

                  {/* Benefits list */}
                  <div className="space-y-2 pt-4 border-t border-gray-100">
                    {solution.benefits.map((benefit, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                        <span className="text-sm text-gray-600">{benefit}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom badges */}
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto mt-12 animate-slide-up delay-400">
          <div className="bg-white rounded-xl p-4 shadow-md border-2 border-blue-100">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-blue-600" />
              <div>
                <p className="font-bold text-gray-900">Prise de Rendez-vous</p>
                <p className="text-sm text-gray-600">Optimisez votre agenda et diminuez vos rendez-vous manqués</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl p-4 shadow-md border-2 border-green-100">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <div>
                <p className="font-bold text-gray-900">SAV & Support</p>
                <p className="text-sm text-gray-600">Libérez-vous des appels répétitifs, concentrez-vous sur votre métier</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl p-4 shadow-md border-2 border-purple-100">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-purple-600" />
              <div>
                <p className="font-bold text-gray-900">Gestions Techniques</p>
                <p className="text-sm text-gray-600">Contactez vos clients sur leur canal préféré</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}