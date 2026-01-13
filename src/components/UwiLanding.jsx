import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Phone,
  MessagesSquare,
  Calendar,
  ShieldCheck,
  Zap,
  ArrowRight,
  Headphones,
  Check,
  Clock,
  Target,
  TrendingUp,
  Users,
  BarChart3,
  CheckCircle2,
  Star,
  Play,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0 },
};

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6 lg:px-8">{children}</div>
);

const Badge = ({ children, className = "" }) => (
  <span className={`inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-orange-500/10 to-orange-600/10 border border-orange-500/20 px-4 py-1.5 text-sm font-medium text-orange-700 ${className}`}>
    {children}
  </span>
);

const PrimaryButton = ({ children, onClick, href, className = "", variant = "default", ...props }) => {
  const Component = href ? 'a' : 'button';
  const baseClasses = "group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-xl font-semibold shadow-lg transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";
  
  const variants = {
    default: "bg-gradient-to-r from-orange-500 to-orange-600 text-white px-8 py-4 text-lg hover:from-orange-600 hover:to-orange-700 hover:shadow-xl hover:scale-105 focus-visible:outline-orange-500",
    large: "bg-gradient-to-r from-orange-500 to-orange-600 text-white px-10 py-5 text-xl hover:from-orange-600 hover:to-orange-700 hover:shadow-2xl hover:scale-105 focus-visible:outline-orange-500",
    outline: "border-2 border-orange-500 text-orange-600 px-8 py-4 text-lg hover:bg-orange-50 focus-visible:outline-orange-500"
  };
  
  return (
    <Component
      href={href}
      onClick={onClick}
      className={`${baseClasses} ${variants[variant]} ${className}`}
      {...props}
    >
      <motion.span
        aria-hidden
        className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-200%] group-hover:translate-x-[200%] transition-transform duration-1000"
      />
      <span className="relative z-10 flex items-center gap-2">
        {children}
      </span>
      <ArrowRight className="relative z-10 h-5 w-5 transition-transform group-hover:translate-x-1" />
    </Component>
  );
};

const ValueCard = ({ icon: Icon, title, description, stat, statLabel, gradient }) => {
  const gradients = {
    orange: "from-orange-500 to-orange-600",
    blue: "from-blue-500 to-blue-600",
    purple: "from-purple-500 to-purple-600",
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5 }}
      className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-8 shadow-sm transition-all duration-300 hover:shadow-xl hover:border-orange-200"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-slate-50/50 to-white opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      
      <div className="relative">
        <div className={`inline-flex rounded-2xl bg-gradient-to-br ${gradients[gradient] || gradients.orange} p-4 text-white shadow-lg`}>
          <Icon className="h-7 w-7" />
        </div>
        
        <div className="mt-6">
          <h3 className="text-2xl font-bold text-slate-900">{title}</h3>
          <p className="mt-3 text-slate-600 leading-relaxed text-base">{description}</p>
          
          {stat && (
            <div className="mt-6 flex items-baseline gap-2">
              <span className="text-4xl font-bold text-slate-900">{stat}</span>
              {statLabel && <span className="text-sm text-slate-500">{statLabel}</span>}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

const BenefitCard = ({ icon: Icon, title, description }) => (
  <motion.div
    initial={{ opacity: 0, x: -20 }}
    whileInView={{ opacity: 1, x: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4 }}
    className="flex items-start gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
  >
    <div className="flex-shrink-0 rounded-xl bg-orange-50 p-3">
      <Icon className="h-6 w-6 text-orange-600" />
    </div>
    <div>
      <h4 className="font-semibold text-slate-900">{title}</h4>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  </motion.div>
);

const ScrollProgress = () => {
  const [p, setP] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement;
      const scrollTop = el.scrollTop || document.body.scrollTop;
      const height = el.scrollHeight - el.clientHeight;
      const next = height > 0 ? Math.min(1, scrollTop / height) : 0;
      setP(next);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="fixed left-0 right-0 top-0 z-[60] h-1 bg-slate-100">
      <motion.div
        className="h-full bg-gradient-to-r from-orange-500 via-orange-600 to-orange-500"
        style={{ scaleX: p, transformOrigin: "0%" }}
      />
    </div>
  );
};

const FAQ = ({ q, a }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4 }}
  >
    <details className="group rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:border-orange-200 hover:shadow-md">
      <summary className="cursor-pointer list-none font-semibold text-slate-900">
        <div className="flex items-center justify-between gap-6">
          <span className="text-lg">{q}</span>
          <span className="flex-shrink-0 rounded-lg bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 transition-colors group-open:bg-orange-50 group-open:text-orange-700">
            <span className="group-open:hidden">Voir la réponse</span>
            <span className="hidden group-open:inline">Masquer</span>
          </span>
        </div>
      </summary>
      <p className="mt-4 text-slate-600 leading-relaxed">{a}</p>
    </details>
  </motion.div>
);

export default function UwiLanding() {
  useEffect(() => {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }, []);

  return (
    <div className="min-h-screen bg-white text-slate-900 antialiased">
      <ScrollProgress />

      {/* Background décoratif */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-gradient-to-br from-orange-400/20 to-orange-600/10 blur-3xl" />
        <div className="absolute top-1/2 -left-40 h-96 w-96 rounded-full bg-gradient-to-br from-blue-400/20 to-blue-600/10 blur-3xl" />
        <div className="absolute -bottom-40 right-1/3 h-96 w-96 rounded-full bg-gradient-to-br from-purple-400/20 to-purple-600/10 blur-3xl" />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-xl">
        <Container>
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg">
                <span className="text-base font-bold">UW<span className="text-orange-100">i</span></span>
              </div>
              <div>
                <div className="text-base font-bold text-slate-900">UWi</div>
                <div className="text-xs text-slate-500">Agent d'accueil IA</div>
              </div>
            </div>

            <nav className="hidden items-center gap-8 text-sm font-medium text-slate-700 md:flex" aria-label="Navigation">
              <a href="#benefits" className="transition-colors hover:text-orange-600">Avantages</a>
              <a href="#how" className="transition-colors hover:text-orange-600">Fonctionnement</a>
              <a href="#pricing" className="transition-colors hover:text-orange-600">Tarifs</a>
            </nav>

            <PrimaryButton href="#contact" variant="default">Essayer gratuitement</PrimaryButton>
          </div>
        </Container>
      </header>

      {/* Hero - Plus vendeur */}
      <section className="relative overflow-hidden pt-20 pb-16 md:pt-28 md:pb-24">
        <Container>
          <div className="mx-auto max-w-5xl">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="text-center"
            >
              <Badge className="mb-6">
                <Zap className="h-4 w-4" />
                Ne perdez plus jamais une demande client
              </Badge>

              <h1 className="text-5xl font-extrabold tracking-tight text-slate-900 md:text-6xl lg:text-7xl">
                Transformez chaque appel en
                <br />
                <span className="bg-gradient-to-r from-orange-500 via-orange-600 to-orange-700 bg-clip-text text-transparent">
                  opportunité concrète
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-2xl text-xl text-slate-600 md:text-2xl leading-relaxed">
                UWi répond instantanément, qualifie chaque demande, et déclenche l'action : 
                <span className="font-semibold text-slate-900"> rendez-vous planifié, réponse envoyée, ou transfert intelligent.</span>
              </p>

              <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                <PrimaryButton href="#contact" variant="large">
                  Démarrer gratuitement - 14 jours
                </PrimaryButton>
                <button className="group inline-flex items-center gap-2 rounded-xl border-2 border-slate-300 bg-white px-6 py-4 text-lg font-semibold text-slate-900 transition-all hover:border-orange-300 hover:bg-orange-50">
                  <Play className="h-5 w-5 text-orange-600" />
                  Voir la démo
                </button>
              </div>

              <div className="mt-12 flex items-center justify-center gap-8 text-sm text-slate-500">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>Sans carte bancaire</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>Configuration en 5 min</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>Support inclus</span>
                </div>
              </div>

              {/* Stats sociales */}
              <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-3">
                <div className="text-center">
                  <div className="text-4xl font-bold text-slate-900">100%</div>
                  <div className="mt-2 text-sm font-medium text-slate-600">Des demandes traitées</div>
                  <div className="mt-1 text-xs text-slate-500">Aucune perdue</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-slate-900">24/7</div>
                  <div className="mt-2 text-sm font-medium text-slate-600">Disponibilité</div>
                  <div className="mt-1 text-xs text-slate-500">Tous les jours, toute l'année</div>
                </div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-slate-900">&lt;2s</div>
                  <div className="mt-2 text-sm font-medium text-slate-600">Temps de réponse</div>
                  <div className="mt-1 text-xs text-slate-500">Réponse immédiate</div>
                </div>
              </div>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* 3 Valeurs principales - Plus vendeur */}
      <section id="benefits" className="py-20 md:py-28 bg-gradient-to-b from-white to-slate-50">
        <Container>
          <div className="mx-auto max-w-3xl text-center mb-16">
            <Badge className="mb-4">Votre avantage concurrentiel</Badge>
            <h2 className="text-4xl font-extrabold text-slate-900 md:text-5xl">
              Pourquoi choisir UWi ?
            </h2>
            <p className="mt-4 text-xl text-slate-600">
              Trois avantages qui transforment votre accueil client
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            <ValueCard
              icon={Zap}
              title="Réponse instantanée"
              description="Vos clients sont accueillis en moins de 2 secondes, 24h/24. Plus d'attente, plus de clients qui raccrochent. Chaque appel devient une opportunité."
              stat="<2s"
              statLabel="de réponse"
              gradient="orange"
            />
            <ValueCard
              icon={TrendingUp}
              title="Qualification automatique"
              description="Chaque demande est analysée, structurée et enrichie. Vous récupérez 100% des informations essentielles, prêtes à être traitées."
              stat="100%"
              statLabel="d'informations capturées"
              gradient="blue"
            />
            <ValueCard
              icon={Target}
              title="Action garantie"
              description="Rendez-vous planifié, email envoyé, ou transfert intelligent : chaque interaction produit un résultat mesurable. Aucune perte."
              stat="0"
              statLabel="demande perdue"
              gradient="purple"
            />
          </div>
        </Container>
      </section>

      {/* Bénéfices concrets */}
      <section className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-4xl">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-extrabold text-slate-900 md:text-5xl">
                Résultats mesurables
              </h2>
              <p className="mt-4 text-xl text-slate-600">
                Ce que vous obtenez avec UWi
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <BenefitCard
                icon={Users}
                title="+45% de conversions"
                description="Plus de demandes transformées en rendez-vous grâce à une réponse immédiate et une qualification précise."
              />
              <BenefitCard
                icon={Clock}
                title="-80% de temps perdu"
                description="Fini les appels non qualifiés. Votre équipe se concentre sur ce qui compte vraiment."
              />
              <BenefitCard
                icon={BarChart3}
                title="+60% de satisfaction client"
                description="Vos clients apprécient la réactivité et la clarté. Ils recommandent votre entreprise."
              />
              <BenefitCard
                icon={ShieldCheck}
                title="100% de traçabilité"
                description="Chaque interaction est enregistrée, analysée et disponible. Vous gardez le contrôle total."
              />
            </div>
          </div>
        </Container>
      </section>

      {/* Comment ça marche */}
      <section id="how" className="py-20 md:py-28 bg-gradient-to-b from-slate-50 to-white">
        <Container>
          <div className="mx-auto max-w-4xl">
            <div className="text-center mb-16">
              <Badge className="mb-4">Simple et efficace</Badge>
              <h2 className="text-4xl font-extrabold text-slate-900 md:text-5xl">
                En 3 étapes simples
              </h2>
              <p className="mt-4 text-xl text-slate-600">
                Un processus optimisé pour maximiser vos conversions
              </p>
            </div>

            <div className="space-y-12">
              {[
                {
                  step: "01",
                  title: "Accueil instantané",
                  description: "Dès la première seconde, UWi répond et guide votre client. Plus d'attente, plus de frustration. L'expérience commence bien.",
                  icon: Phone,
                },
                {
                  step: "02",
                  title: "Qualification intelligente",
                  description: "UWi pose les bonnes questions et capture toutes les informations essentielles : besoin, urgence, disponibilité, contexte.",
                  icon: Target,
                },
                {
                  step: "03",
                  title: "Action immédiate",
                  description: "Rendez-vous planifié automatiquement, réponse envoyée, ou transfert à votre équipe avec toutes les informations. Résultat garanti.",
                  icon: CheckCircle2,
                },
              ].map((item, idx) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, x: idx % 2 === 0 ? -40 : 40 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.5, delay: idx * 0.1 }}
                  className={`flex flex-col gap-8 md:flex-row md:items-center ${idx % 2 === 1 ? 'md:flex-row-reverse' : ''}`}
                >
                  <div className="flex-1">
                    <div className="inline-flex items-center gap-3 mb-4">
                      <span className="text-5xl font-extrabold text-slate-200">{item.step}</span>
                      <div className="h-px w-12 bg-gradient-to-r from-orange-500 to-transparent" />
                    </div>
                    <h3 className="text-3xl font-bold text-slate-900 mb-3">{item.title}</h3>
                    <p className="text-lg text-slate-600 leading-relaxed">{item.description}</p>
                  </div>
                  <div className="flex-shrink-0">
                    <div className="flex h-32 w-32 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-xl">
                      <item.icon className="h-16 w-16" />
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* Pricing/CTA */}
      <section id="pricing" className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-4xl">
            <div className="text-center mb-16">
              <Badge className="mb-4">Essayez sans risque</Badge>
              <h2 className="text-4xl font-extrabold text-slate-900 md:text-5xl">
                Commencez gratuitement dès aujourd'hui
              </h2>
              <p className="mt-4 text-xl text-slate-600">
                Testez UWi pendant 14 jours. Aucune carte bancaire requise.
              </p>
            </div>

            <div className="rounded-2xl border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white p-8 shadow-xl md:p-12">
              <div className="grid gap-8 md:grid-cols-2 md:items-center">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-orange-100 px-4 py-1.5 text-sm font-semibold text-orange-700 mb-4">
                    <Star className="h-4 w-4 fill-orange-500" />
                    Offre la plus populaire
                  </div>
                  <h3 className="text-3xl font-bold text-slate-900 mb-2">Essai gratuit 14 jours</h3>
                  <p className="text-slate-600 mb-6">
                    Accès complet à toutes les fonctionnalités. Configurez UWi en 5 minutes et commencez à ne plus perdre de demandes.
                  </p>
                  <ul className="space-y-3">
                    {[
                      "Réponse 24/7 automatique",
                      "Qualification intelligente",
                      "Intégration agenda",
                      "Handoff humain",
                      "Support prioritaire",
                      "Analytics et reporting",
                    ].map((feature) => (
                      <li key={feature} className="flex items-center gap-3">
                        <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                        <span className="text-slate-700">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="text-center">
                  <div className="mb-6">
                    <div className="text-5xl font-extrabold text-slate-900">Gratuit</div>
                    <div className="text-slate-600 mt-2">pendant 14 jours</div>
                    <div className="text-lg text-slate-500 mt-4">Ensuite à partir de 49€/mois</div>
                  </div>
                  <PrimaryButton href="#contact" variant="large" className="w-full justify-center">
                    Démarrer maintenant
                  </PrimaryButton>
                  <p className="mt-4 text-sm text-slate-500">
                    Aucun engagement • Résiliez à tout moment
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-20 md:py-28 bg-slate-50">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-extrabold text-slate-900 md:text-5xl">
                Questions fréquentes
              </h2>
              <p className="mt-4 text-xl text-slate-600">
                Tout ce que vous devez savoir avant de commencer
              </p>
            </div>
            <div className="space-y-4">
              <FAQ
                q="Combien de temps pour mettre UWi en place ?"
                a="Moins de 5 minutes. UWi s'intègre directement à votre agenda (Google Calendar, Outlook) et à votre téléphonie. Aucune compétence technique requise."
              />
              <FAQ
                q="UWi fonctionne-t-il pour tous les secteurs ?"
                a="Oui. UWi s'adapte à tous les secteurs : cabinets médicaux, PME de services, artisans, commerces, professionnels libéraux. La configuration s'adapte à vos besoins spécifiques."
              />
              <FAQ
                q="Que se passe-t-il après les 14 jours d'essai ?"
                a="Rien automatiquement. Nous vous contactons pour discuter de vos besoins et vous proposer la formule adaptée. Aucun prélèvement sans votre accord explicite."
              />
              <FAQ
                q="Puis-je contrôler ce que UWi dit à mes clients ?"
                a="Absolument. Vous définissez le script, les réponses autorisées, et le périmètre d'action. UWi reste dans le cadre que vous définissez."
              />
              <FAQ
                q="UWi fonctionne-t-il si j'ai déjà un système téléphonique ?"
                a="Oui, UWi s'intègre à tous les systèmes téléphoniques standards (VoIP, PABX, Twilio, etc.). L'intégration est transparente et ne nécessite aucun changement de votre infrastructure."
              />
            </div>
          </div>
        </Container>
      </section>

      {/* Contact - CTA final vendeur */}
      <section id="contact" className="relative overflow-hidden py-20 md:py-28 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
        <div className="absolute inset-0 opacity-10" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fillRule='evenodd'%3E%3Cg fill='%23ffffff' fillOpacity='0.3'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }} />
        
        <Container>
          <div className="relative mx-auto max-w-3xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <Badge className="bg-white/10 border-white/20 text-white mb-6">
                <Zap className="h-4 w-4" />
                Prêt à transformer votre accueil client ?
              </Badge>
              
              <h2 className="text-4xl font-extrabold md:text-5xl lg:text-6xl mb-6">
                Ne perdez plus jamais une opportunité
              </h2>
              
              <p className="text-xl text-white/80 mb-10 leading-relaxed">
                Rejoignez les entreprises qui ont transformé leur accueil client avec UWi.
                <br />
                <span className="font-semibold text-white">Démarrez votre essai gratuit dès maintenant.</span>
              </p>

              <form className="mx-auto max-w-lg" onSubmit={(e) => e.preventDefault()}>
                <div className="flex flex-col gap-4 sm:flex-row">
                  <input
                    type="email"
                    placeholder="Votre email professionnel"
                    className="flex-1 rounded-xl border-0 bg-white/10 px-6 py-4 text-base text-white placeholder:text-white/60 backdrop-blur focus:bg-white/15 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    aria-label="Email professionnel"
                  />
                  <PrimaryButton type="submit" variant="large" className="bg-white text-slate-900 hover:bg-slate-100">
                    Commencer gratuitement
                  </PrimaryButton>
                </div>
                <p className="mt-4 text-sm text-white/60">
                  <CheckCircle2 className="inline h-4 w-4 mr-1" />
                  Gratuit 14 jours • Sans carte bancaire • Configuration en 5 minutes
                </p>
              </form>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-12" role="contentinfo">
        <Container>
          <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 text-white">
                <span className="text-sm font-bold">UW<span className="text-orange-100">i</span></span>
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900">UWi</div>
                <div className="text-xs text-slate-500">Agent d'accueil IA multicanal</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-slate-600">
              <a href="#benefits" className="font-medium transition-colors hover:text-orange-600">Avantages</a>
              <a href="#how" className="font-medium transition-colors hover:text-orange-600">Fonctionnement</a>
              <a href="#pricing" className="font-medium transition-colors hover:text-orange-600">Tarifs</a>
              <a href="#contact" className="font-medium transition-colors hover:text-orange-600">Contact</a>
            </div>
          </div>
          <div className="mt-8 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
            © {new Date().getFullYear()} UWi. Tous droits réservés. | 
            <a href="#" className="ml-2 hover:text-slate-700">Mentions légales</a> | 
            <a href="#" className="ml-2 hover:text-slate-700">Confidentialité</a>
          </div>
        </Container>
      </footer>
    </div>
  );
}
