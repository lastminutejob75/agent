import React from "react";

interface HeroProps {
  title: string;
  subtitle: string;
}

export default function Hero({ title, subtitle }: HeroProps) {
  return (
    <section className="pt-12 md:pt-16 pb-16 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          {/* Left side - Text content */}
          <div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 mb-6 leading-tight">
              {title}
            </h1>
            <p className="text-lg md:text-xl text-slate-700 mb-8 leading-relaxed">
              {subtitle}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 mb-4">
              <a
                href="#contact"
                className="inline-flex items-center justify-center rounded-xl bg-[#0066CC] px-8 py-4 text-base font-semibold text-white shadow-lg hover:bg-[#0052A3] transition"
              >
                Démarrer l'essai gratuit
              </a>
              <a
                href="#roi"
                className="inline-flex items-center justify-center rounded-xl border-2 border-[#0066CC] bg-white px-8 py-4 text-base font-semibold text-[#0066CC] hover:bg-[#0066CC]/5 transition"
              >
                Voir le ROI
              </a>
            </div>
            <p className="text-sm text-slate-600">
              Sans carte bancaire • Configuration en 30 minutes
            </p>
          </div>

          {/* Right side - Visual placeholder & stats */}
          <div>
            {/* Hero image - médecin avec tablette UWI (dernière photo envoyée) */}
            <div className="relative rounded-2xl overflow-hidden shadow-lg mb-6 group h-[400px] bg-gradient-to-br from-blue-100 to-blue-200">
              <img
                src="/images/solution-rdv.jpg"
                alt="Médecin serein avec tablette UWI - Interface montrant appels traités et RDV confirmés"
                className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                loading="eager"
                onError={(e) => {
                  // Fallback vers SVG placeholder (solution-rdv.svg existe)
                  const target = e.currentTarget;
                  if (!target.src.includes('.svg') && !target.src.includes('unsplash')) {
                    target.src = '/images/solution-rdv.svg';
                  } else if (!target.src.includes('unsplash')) {
                    target.src = 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=1200&h=800&fit=crop&q=85';
                  }
                }}
              />
              {/* Overlay discret au hover pour montrer l'interface UWI */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
            </div>

            {/* Stats cards - 3 cards in a row below placeholder */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 text-center">
                <div className="text-2xl font-bold text-[#0066CC] mb-1">24/7</div>
                <div className="text-xs text-slate-600">Réponses</div>
              </div>
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 text-center">
                <div className="text-2xl font-bold text-[#0066CC] mb-1">+30K€</div>
                <div className="text-xs text-slate-600">Gains/an</div>
              </div>
              <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 text-center">
                <div className="text-2xl font-bold text-[#0066CC] mb-1">30 min</div>
                <div className="text-xs text-slate-600">Setup</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
