import { Shield, Award, Clock, ThumbsUp, Lock, Headphones, Zap, RefreshCcw } from "lucide-react";

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
    <section className="section-padding bg-white">
      <div className="container-custom">
        {/* Header */}
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">
            Essayez <span className="text-[#0066CC]">sans risque</span>
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Nos garanties pour que vous testiez UWI en toute sérénité
          </p>
        </div>

        {/* Garanties */}
        <div className="grid md:grid-cols-2 gap-6 max-w-5xl mx-auto mb-16">
          {guarantees.map((item, index) => (
            <div
              key={index}
              className="bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-6 hover:border-[#0066CC] hover:shadow-lg transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="flex gap-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-[#0066CC]/10 rounded-xl flex items-center justify-center">
                    <item.icon className="h-6 w-6 text-[#0066CC]" />
                  </div>
                </div>
                <div>
                  <h3 className="font-bold text-lg text-gray-900 mb-2">{item.title}</h3>
                  <p className="text-gray-600">{item.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Certifications */}
        <div className="bg-gradient-to-br from-[#0066CC]/5 to-transparent rounded-2xl p-8 border border-gray-200 animate-slide-up delay-400">
          <h3 className="text-center text-xl font-bold text-gray-900 mb-8">
            Sécurité et conformité certifiées
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {certifications.map((cert, index) => (
              <div
                key={index}
                className="text-center p-4 bg-white rounded-xl shadow-soft hover:shadow-medium transition-all"
              >
                <cert.icon className="h-10 w-10 text-[#0066CC] mx-auto mb-3" />
                <div className="font-bold text-gray-900 text-sm mb-1">{cert.title}</div>
                <div className="text-xs text-gray-600">{cert.subtitle}</div>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <p className="text-sm text-gray-600">
              🔒 Vos données et celles de vos clients sont hébergées en France et protégées selon les standards les plus stricts
            </p>
          </div>
        </div>

        {/* Final CTA */}
        <div className="mt-12 text-center animate-slide-up delay-500">
          <a
            href="/#contact"
            className="inline-flex items-center gap-2 btn-primary text-lg px-8 py-4 shadow-lg"
          >
            <ThumbsUp className="h-5 w-5" />
            Essai gratuit 14 jours
          </a>
          <p className="mt-4 text-sm text-gray-500">
            Sans carte bancaire • Sans engagement • Configuration offerte
          </p>
        </div>
      </div>
    </section>
  );
}
