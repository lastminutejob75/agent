import React from "react";
import { ArrowRight, Phone, MapPin, Wrench, Calendar, TrendingUp } from "lucide-react";

export default function WorkflowSection() {
  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        {/* Header */}
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">
            <span className="text-[#0066CC]">UWI</span> Optimise Votre{" "}
            <span className="text-[#0066CC]">Planning d'Interventions</span>
          </h2>

          {/* Icons flow */}
          <div className="flex items-center justify-center gap-8 mt-8">
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Calendar className="h-8 w-8 text-[#0066CC]" />
            </div>
            <ArrowRight className="h-6 w-6 text-gray-400" />
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Wrench className="h-8 w-8 text-[#0066CC]" />
            </div>
            <ArrowRight className="h-6 w-6 text-gray-400" />
            <div className="w-16 h-16 bg-[#0066CC]/10 rounded-2xl flex items-center justify-center">
              <Phone className="h-8 w-8 text-[#0066CC]" />
            </div>
          </div>
        </div>

        {/* 3 étapes avec images */}
        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {/* Étape 1 : Plombier débordé */}
          <div className="relative animate-slide-up delay-100">
            <div className="rounded-2xl overflow-hidden shadow-lg">
              {/* Image placeholder */}
              <div className="relative h-72 bg-gradient-to-br from-red-100 to-orange-100">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-red-600 p-4">
                    <Phone className="h-20 w-20 mx-auto mb-4 opacity-50" />
                    <p className="text-sm font-medium">Image: Plombier sur chantier au téléphone</p>
                  </div>
                </div>
                {/* Badge problème */}
                <div className="absolute top-4 left-4 bg-red-500 text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Plombier Débordé
                </div>
              </div>

              {/* Content */}
              <div className="bg-white p-6">
                <h3 className="font-bold text-xl text-gray-900 mb-4">Le Problème</h3>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" />
                      </svg>
                    </div>
                    <span className="text-gray-700">3 appels entrants, demandes multiples</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" />
                      </svg>
                    </div>
                    <span className="text-gray-700">Manque de temps pour qualifier</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" />
                      </svg>
                    </div>
                    <span className="text-gray-700">Déplacements non rentables</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Étape 2 : Qualification */}
          <div className="relative animate-slide-up delay-200">
            <div className="rounded-2xl overflow-hidden shadow-lg">
              {/* Image placeholder */}
              <div className="relative h-72 bg-gradient-to-br from-blue-100 to-[#0066CC]/20">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-[#0066CC] p-4">
                    <Wrench className="h-20 w-20 mx-auto mb-4 opacity-50" />
                    <p className="text-sm font-medium">Image: Smartphone avec interface UWI</p>
                  </div>
                </div>
                {/* Badge solution */}
                <div className="absolute top-4 left-4 bg-[#0066CC] text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Qualification Automatique
                </div>
              </div>

              {/* Content */}
              <div className="bg-white p-6">
                <h3 className="font-bold text-xl text-gray-900 mb-4">UWI trie les appels</h3>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <MapPin className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">Urgence</p>
                      <p className="text-sm text-gray-600">Fuite, panne, demain matin...</p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <MapPin className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">Localisation</p>
                      <p className="text-sm text-gray-600">Dijon, Longvic, dans votre zone</p>
                    </div>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Wrench className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">Type d'intervention</p>
                      <p className="text-sm text-gray-600">Fuite à réparer, radiateur à purger...</p>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Étape 3 : Planning optimal */}
          <div className="relative animate-slide-up delay-300">
            <div className="rounded-2xl overflow-hidden shadow-lg">
              {/* Image placeholder */}
              <div className="relative h-72 bg-gradient-to-br from-green-100 to-emerald-200">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-green-600 p-4">
                    <Calendar className="h-20 w-20 mx-auto mb-4 opacity-50" />
                    <p className="text-sm font-medium">Image: Artisan avec planning optimisé</p>
                  </div>
                </div>
                {/* Badge résultat */}
                <div className="absolute top-4 left-4 bg-green-500 text-white px-4 py-2 rounded-full text-sm font-bold shadow-lg flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Planification Optimale
                </div>
              </div>

              {/* Content */}
              <div className="bg-white p-6">
                <h3 className="font-bold text-xl text-gray-900 mb-4">Le Résultat</h3>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <span className="text-gray-700">Agenda complet, zéro trou</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <span className="text-gray-700">Déplacements réduits de 40%</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <TrendingUp className="w-4 h-4 text-green-600" />
                    </div>
                    <span className="text-gray-700">CA maximisé (+400€/mois)</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}