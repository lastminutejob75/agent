import { Calendar, Headphones, MessageCircle, CheckCircle, ArrowRight } from "lucide-react";

export default function SolutionsGridSection() {
  const solutions = [
    {
      icon: Calendar,
      title: "Prise de Rendez-vous",
      description: "Optimisez votre agenda et diminuez vos rendez-vous manqués",
      benefit: "Optimisez votre agenda et diminuez vos rendez-vous manqués",
      image: "/images/solution-rdv.jpg",
      color: "from-blue-500 to-blue-600",
      bgGradient: "from-blue-100 to-blue-200",
    },
    {
      icon: Headphones,
      title: "SAV & Support",
      description: "Libérez-vous des appels répétitifs, concentrez-vous sur votre métier",
      benefit: "Libérez-vous des appels répétitifs, concentrez-vous sur votre métier",
      image: "/images/solution-sav.jpg",
      color: "from-green-500 to-green-600",
      bgGradient: "from-green-100 to-green-200",
    },
    {
      icon: MessageCircle,
      title: "Questions Techniques",
      description: "Offrez des réponses instantanées, contactez vos clients sur leur canal préféré",
      benefit: "Contactez vos clients sur leur canal préféré",
      image: "/images/solution-questions.jpg",
      color: "from-purple-500 to-purple-600",
      bgGradient: "from-purple-100 to-purple-200",
    },
  ];

  return (
    <section className="section-padding bg-gradient-to-br from-gray-50 to-white">
      <div className="container-custom">
        {/* Header */}
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">
            Comment <span className="text-[#0066CC]">UWI</span> Résout Vos Problèmes
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            3 solutions puissantes pour transformer votre relation client
          </p>

          {/* Icons flow */}
          <div className="flex items-center justify-center gap-6 mt-8">
            <div className="w-14 h-14 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Calendar className="h-7 w-7 text-[#0066CC]" />
            </div>
            <ArrowRight className="h-6 w-6 text-gray-400" />
            <div className="w-14 h-14 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Headphones className="h-7 w-7 text-[#0066CC]" />
            </div>
            <ArrowRight className="h-6 w-6 text-gray-400" />
            <div className="w-14 h-14 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <MessageCircle className="h-7 w-7 text-[#0066CC]" />
            </div>
          </div>
        </div>

        {/* 3 solutions grid */}
        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {solutions.map((solution, index) => (
            <div
              key={index}
              className="relative animate-slide-up group"
              style={{ animationDelay: `${index * 0.15}s` }}
            >
              <div className="rounded-2xl overflow-hidden shadow-lg hover:shadow-2xl transition-all duration-300 bg-white h-full flex flex-col">
                {/* Image zone - améliorée */}
                <div className={`relative h-80 bg-gradient-to-br ${solution.bgGradient} overflow-hidden`}>
                  <img
                    src={solution.image}
                    alt={solution.title}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    loading="lazy"
                    onError={(e) => {
                      // Fallback vers SVG placeholder
                      const svgFallback = solution.image.replace('.jpg', '.svg');
                      e.currentTarget.src = svgFallback;
                    }}
                  />
                  
                  {/* Overlay gradient pour meilleure lisibilité */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

                  {/* Badge avec checkmark - position améliorée */}
                  <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-sm rounded-full p-3 shadow-lg transform group-hover:scale-110 transition-transform">
                    <CheckCircle className="h-6 w-6 text-[#0066CC]" />
                  </div>

                  {/* Icon overlay au hover - plus discret */}
                  <div className="absolute inset-0 flex items-center justify-center p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                    <div className={`bg-gradient-to-br ${solution.color} rounded-2xl p-4 shadow-2xl transform group-hover:scale-100 scale-95 transition-transform`}>
                      <solution.icon className="h-12 w-12 text-white" />
                    </div>
                  </div>
                </div>

                {/* Content - amélioré */}
                <div className="p-6 flex-1 flex flex-col">
                  <h3 className="font-bold text-xl text-gray-900 mb-3 group-hover:text-[#0066CC] transition-colors">
                    {solution.title}
                  </h3>

                  <div className="flex items-start gap-2 mb-4 flex-1">
                    <span className="text-2xl text-[#0066CC] font-bold flex-shrink-0">+</span>
                    <p className="text-gray-700 leading-relaxed">{solution.description}</p>
                  </div>

                  {/* Benefit - style amélioré */}
                  <div className="pt-4 border-t border-gray-100 mt-auto">
                    <div className="flex items-start gap-2">
                      <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-600 font-medium">{solution.benefit}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom summary badges - améliorés */}
        <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto mt-16 animate-slide-up delay-300">
          {solutions.map((solution, index) => (
            <div
              key={index}
              className={`bg-white rounded-xl p-5 shadow-soft border-2 ${
                index === 0 ? 'border-blue-100 hover:border-blue-300' :
                index === 1 ? 'border-green-100 hover:border-green-300' :
                'border-purple-100 hover:border-purple-300'
              } hover:shadow-medium transition-all duration-300 group cursor-default`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110 ${
                  index === 0 ? 'bg-blue-100' :
                  index === 1 ? 'bg-green-100' :
                  'bg-purple-100'
                }`}>
                  <solution.icon className={`h-5 w-5 ${
                    index === 0 ? 'text-blue-600' :
                    index === 1 ? 'text-green-600' :
                    'text-purple-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="font-bold text-gray-900 text-sm mb-1">{solution.title}</p>
                  <p className="text-xs text-gray-600 leading-relaxed">{solution.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-12 animate-slide-up delay-400">
          <a
            href="/#contact"
            className="inline-flex items-center gap-2 btn-primary text-lg px-8 py-4"
          >
            Découvrir toutes les solutions
            <ArrowRight className="h-5 w-5" />
          </a>
        </div>
      </div>
    </section>
  );
}
