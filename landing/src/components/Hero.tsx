import React from "react";
import { Link } from "react-router-dom";
import { Calendar, CheckCircle, Clock, Phone } from "lucide-react";

interface HeroProps {
  title: string;
  subtitle: string;
}

export default function Hero({ title, subtitle }: HeroProps) {
  return (
    <section className="pt-12 md:pt-16 pb-16 bg-gradient-to-br from-white via-blue-50/30 to-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          {/* Left side - Text content */}
          <div className="animate-slide-up">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 mb-6 leading-tight">
              {title}
            </h1>
            <p className="text-lg md:text-xl text-slate-700 mb-8 leading-relaxed">
              {subtitle}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 mb-4">
              <Link
                to="/onboarding"
                className="inline-flex items-center justify-center rounded-xl bg-[#0066CC] px-8 py-4 text-base font-semibold text-white shadow-lg hover:bg-[#0052A3] transition hover:scale-105"
              >
                Démarrer l'essai gratuit
              </Link>
              <a
                href="#roi"
                className="inline-flex items-center justify-center rounded-xl border-2 border-[#0066CC] bg-white px-8 py-4 text-base font-semibold text-[#0066CC] hover:bg-[#0066CC]/5 transition hover:scale-105"
              >
                Voir le ROI
              </a>
            </div>
            <p className="text-sm text-slate-600">
              Sans carte bancaire • Configuration en 30 minutes
            </p>
          </div>

          {/* Right side - UWI Interface Mockup */}
          <div className="animate-slide-up delay-200">
            {/* Main interface card */}
            <div className="relative">
              {/* Background decoration */}
              <div className="absolute -top-4 -right-4 w-72 h-72 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse"></div>
              <div className="absolute -bottom-4 -left-4 w-72 h-72 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-pulse" style={{ animationDelay: '2s' }}></div>

              {/* Main mockup card */}
              <div className="relative bg-white rounded-3xl shadow-2xl p-6 border-2 border-gray-100">
                {/* Header */}
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-gradient-to-br from-[#0066CC] to-[#0052A3] rounded-2xl flex items-center justify-center shadow-lg">
                      <span className="text-white font-bold text-xl">UWI</span>
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">📅 Prise de Rendez-vous</p>
                      <p className="text-xs text-gray-500">Gestion automatique</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 bg-green-100 px-3 py-1.5 rounded-full">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-xs font-semibold text-green-700">En ligne</span>
                  </div>
                </div>

                {/* Call activities */}
                <div className="space-y-3 mb-6">
                  <div className="bg-gradient-to-r from-blue-50 to-blue-100/50 rounded-xl p-4 border border-blue-200">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center flex-shrink-0">
                        <Phone className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <CheckCircle className="h-4 w-4 text-blue-600" />
                          <p className="font-semibold text-gray-900 text-sm">Appels traités</p>
                        </div>
                        <p className="text-xs text-gray-600">Dr. Martin - Consultation prévue lundi 14h</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-green-50 to-green-100/50 rounded-xl p-4 border border-green-200">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-green-500 rounded-xl flex items-center justify-center flex-shrink-0">
                        <Calendar className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <CheckCircle className="h-4 w-4 text-green-600" />
                          <p className="font-semibold text-gray-900 text-sm">RDV confirmés</p>
                        </div>
                        <p className="text-xs text-gray-600">Mme Dubois - RDV confirmé pour mardi 10h30</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-purple-50 to-purple-100/50 rounded-xl p-4 border border-purple-200">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-purple-500 rounded-xl flex items-center justify-center flex-shrink-0">
                        <Clock className="h-5 w-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <CheckCircle className="h-4 w-4 text-purple-600" />
                          <p className="font-semibold text-gray-900 text-sm">Disponible 24/7</p>
                        </div>
                        <p className="text-xs text-gray-600">Réponse immédiate même hors horaires</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Stats bar at bottom */}
                <div className="grid grid-cols-3 gap-3 pt-4 border-t border-gray-200">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-[#0066CC] mb-1">98%</p>
                    <p className="text-xs text-gray-600">Taux de réponse</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-[#0066CC] mb-1">15s</p>
                    <p className="text-xs text-gray-600">Temps moyen</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-[#0066CC] mb-1">24/7</p>
                    <p className="text-xs text-gray-600">Disponibilité</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats cards below */}
            <div className="grid grid-cols-3 gap-4 mt-6">
              <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-blue-100 text-center hover:scale-105 transition-transform">
                <div className="text-2xl font-bold text-[#0066CC] mb-1">24/7</div>
                <div className="text-xs text-slate-600">Réponses</div>
              </div>
              <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-green-100 text-center hover:scale-105 transition-transform">
                <div className="text-2xl font-bold text-[#0066CC] mb-1">+30K€</div>
                <div className="text-xs text-slate-600">Gains/an</div>
              </div>
              <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-purple-100 text-center hover:scale-105 transition-transform">
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
