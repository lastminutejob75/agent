import React from "react";
import { Phone, MessageCircle, Mail, MessageSquare, CheckCircle, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

export default function MultiChannelSection() {
  const channels = [
    {
      icon: Phone,
      name: "Téléphone",
      description: "Réponse automatique 24/7 sur votre ligne habituelle",
      color: "from-blue-500 to-blue-600",
      bgColor: "bg-blue-100",
      textColor: "text-blue-600",
      borderColor: "border-blue-200",
      available: true,
    },
    {
      icon: MessageCircle,
      name: "WhatsApp",
      description: "Conversations naturelles et confirmations instantanées",
      color: "from-green-500 to-green-600",
      bgColor: "bg-green-100",
      textColor: "text-green-600",
      borderColor: "border-green-200",
      available: true,
    },
    {
      icon: MessageSquare,
      name: "SMS",
      description: "Rappels automatiques et confirmations de RDV",
      color: "from-purple-500 to-purple-600",
      bgColor: "bg-purple-100",
      textColor: "text-purple-600",
      borderColor: "border-purple-200",
      available: true,
    },
    {
      icon: Mail,
      name: "Email",
      description: "Récapitulatifs détaillés et suivis personnalisés",
      color: "from-orange-500 to-orange-600",
      bgColor: "bg-orange-100",
      textColor: "text-orange-600",
      borderColor: "border-orange-200",
      available: true,
    },
  ];

  return (
    <section className="section-padding bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <div className="inline-block bg-[#0066CC]/10 text-[#0066CC] px-4 py-2 rounded-full text-sm font-semibold mb-4">
            Communication Multicanal
          </div>
          <h2 className="heading-lg mb-4">
            <span className="text-[#0066CC]">UWI</span> Communique Sur Tous Les Canaux
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Offrez à vos clients la liberté de vous contacter comme ils le souhaitent.
            UWI s'adapte à leurs préférences pour une expérience optimale.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl mx-auto mb-12">
          {channels.map((channel, index) => (
            <div
              key={index}
              className="relative animate-slide-up group"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className={`bg-white rounded-2xl p-6 shadow-soft hover:shadow-medium transition-all duration-300 border-2 ${channel.borderColor} hover:scale-105 h-full flex flex-col`}>
                <div className={`w-16 h-16 rounded-2xl ${channel.bgColor} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <channel.icon className={`h-8 w-8 ${channel.textColor}`} />
                </div>
                <h3 className={`text-xl font-bold mb-2 ${channel.textColor}`}>
                  {channel.name}
                </h3>
                <p className="text-gray-600 text-sm mb-4 flex-1">
                  {channel.description}
                </p>
                <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-xs font-semibold text-green-600">
                    Disponible
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="max-w-6xl mx-auto">
          <div className="bg-white rounded-3xl shadow-2xl p-8 md:p-12 border border-gray-200">
            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div className="animate-slide-up delay-200">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  Une Expérience Client Sans Friction
                </h3>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-[#0066CC]/10 rounded-full flex items-center justify-center mt-1">
                      <CheckCircle className="h-5 w-5 text-[#0066CC]" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900 mb-1">Réponse Immédiate</p>
                      <p className="text-gray-600 text-sm">Vos clients n'attendent jamais, quel que soit le canal</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-[#0066CC]/10 rounded-full flex items-center justify-center mt-1">
                      <CheckCircle className="h-5 w-5 text-[#0066CC]" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900 mb-1">Synchronisation Automatique</p>
                      <p className="text-gray-600 text-sm">Toutes les conversations centralisées dans un seul outil</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-[#0066CC]/10 rounded-full flex items-center justify-center mt-1">
                      <CheckCircle className="h-5 w-5 text-[#0066CC]" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900 mb-1">Historique Complet</p>
                      <p className="text-gray-600 text-sm">Retrouvez toutes les interactions avec chaque client</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="relative animate-slide-up delay-300">
                <div className="relative bg-gradient-to-br from-blue-100 to-purple-100 rounded-2xl p-8 aspect-square flex items-center justify-center">
                  <div className="relative w-full h-full">
                    <div className="absolute top-4 left-4 bg-white rounded-2xl shadow-lg p-4 w-48 transform rotate-3 hover:rotate-0 transition-transform">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                          <MessageCircle className="h-4 w-4 text-white" />
                        </div>
                        <span className="font-semibold text-sm">WhatsApp</span>
                      </div>
                      <div className="space-y-2">
                        <div className="bg-green-100 rounded-lg p-2 text-xs">
                          Votre RDV est confirmé
                        </div>
                        <div className="bg-gray-100 rounded-lg p-2 text-xs ml-4">
                          Lundi 12 à 14h30
                        </div>
                      </div>
                    </div>
                    <div className="absolute bottom-4 right-4 bg-white rounded-2xl shadow-lg p-4 w-48 transform -rotate-3 hover:rotate-0 transition-transform">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                          <MessageSquare className="h-4 w-4 text-white" />
                        </div>
                        <span className="font-semibold text-sm">SMS</span>
                      </div>
                      <div className="space-y-2">
                        <div className="bg-purple-100 rounded-lg p-2 text-xs">
                          Rappel: RDV demain 14h
                        </div>
                      </div>
                    </div>
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white rounded-full shadow-2xl p-6">
                      <Phone className="h-12 w-12 text-[#0066CC]" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="text-center mt-12 animate-slide-up delay-400">
          <Link
            to="/creer-assistante?new=1"
            className="inline-flex items-center gap-2 btn-primary text-lg px-8 py-4"
          >
            Découvrir les intégrations
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
