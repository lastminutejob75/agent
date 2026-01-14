import React from "react";
import { Shield, Award, Clock, ThumbsUp, Lock, Headphones, Zap, RefreshCcw } from "lucide-react";

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6 lg:px-8">{children}</div>
);

export default function TrustSection() {
  const guarantees = [
    {
      icon: ThumbsUp,
      title: "30 jours satisfait ou remboursé",
      description: "Essayez UWI sans risque pendant 30 jours. Pas convaincu ? On vous rembourse intégralement.",
    },
    {
      icon: Zap,
      title: "Configuration en 30 minutes",
      description: "Notre équipe configure votre IA personnalisée en moins de 30 minutes. Démarrage immédiat garanti.",
    },
    {
      icon: Headphones,
      title: "Support français 7j/7",
      description: "Une question ? Notre équipe basée en France vous répond dans l'heure, même le weekend.",
    },
    {
      icon: RefreshCcw,
      title: "Sans engagement",
      description: "Annulez quand vous voulez en 1 clic. Pas de frais cachés, pas de piège contractuel.",
    },
  ];

  const certifications = [
    {
      icon: Shield,
      title: "Certifié RGPD",
      subtitle: "Conformité totale",
    },
    {
      icon: Lock,
      title: "Hébergement France",
      subtitle: "Données sécurisées",
    },
    {
      icon: Award,
      title: "ISO 27001",
      subtitle: "Sécurité certifiée",
    },
    {
      icon: Clock,
      title: "99.9% Uptime",
      subtitle: "Disponibilité garantie",
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-white">
      <Container>
        {/* Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
            Essayez <span className="text-[#0066CC]">sans risque</span>
          </h2>
          <p className="text-lg text-slate-600 max-w-3xl mx-auto">
            Nos garanties pour que vous testiez UWI en toute sérénité
          </p>
        </div>

        {/* Garanties */}
        <div className="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto mb-16">
          {guarantees.map((item, index) => (
            <div
              key={index}
              className="bg-gradient-to-br from-slate-50 to-white border-2 border-slate-200 rounded-2xl p-6 hover:border-[#0066CC] hover:shadow-lg transition-all card-hover"
            >
              <div className="flex gap-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-[#0066CC]/10 rounded-xl flex items-center justify-center">
                    <item.icon className="h-6 w-6 text-[#0066CC]" />
                  </div>
                </div>
                <div>
                  <h3 className="font-bold text-lg text-[#111827] mb-2">{item.title}</h3>
                  <p className="text-slate-600">{item.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Certifications */}
        <div className="bg-gradient-to-br from-blue-50/50 to-transparent rounded-2xl p-8 border border-slate-200">
          <h3 className="text-center text-xl font-bold text-[#111827] mb-8">
            Sécurité et conformité certifiées
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {certifications.map((cert, index) => (
              <div
                key={index}
                className="text-center p-4 bg-white rounded-xl shadow-soft hover:shadow-medium transition-all"
              >
                <cert.icon className="h-10 w-10 text-[#0066CC] mx-auto mb-3" />
                <div className="font-bold text-[#111827] text-sm mb-1">{cert.title}</div>
                <div className="text-xs text-slate-600">{cert.subtitle}</div>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <p className="text-sm text-slate-600">
              🔒 Vos données et celles de vos clients sont hébergées en France et protégées selon les standards les plus stricts
            </p>
          </div>
        </div>

        {/* Final CTA */}
        <div className="mt-12 text-center">
          <a
            href="#contact"
            className="inline-flex items-center gap-2 bg-[#0066CC] text-white font-semibold text-lg px-8 py-4 rounded-lg hover:bg-[#0052A3] transition-all shadow-lg hover:scale-105"
          >
            <ThumbsUp className="h-5 w-5" />
            Essai gratuit 14 jours
          </a>
          <p className="mt-4 text-sm text-slate-500">
            Sans carte bancaire • Sans engagement • Configuration offerte
          </p>
        </div>
      </Container>
    </section>
  );
}
