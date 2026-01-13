import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Phone,
  Calendar,
  ShieldCheck,
  Zap,
  ArrowRight,
  Clock,
  Target,
  TrendingUp,
  CheckCircle2,
  Star,
  Play,
  Trophy,
  Lock,
  XCircle,
  AlertCircle,
  Bot,
  RefreshCw as Sync,
  Bell,
  BarChart3,
  Settings,
  Stethoscope,
  Wrench,
  Scale,
  Sparkles,
  Home,
  GraduationCap,
  Menu,
  X,
  ChevronDown,
  Mail,
  MapPin,
  Quote,
  User,
} from "lucide-react";
import SocialProof from "./SocialProof";
import ComparisonSection from "./ComparisonSection";
import ROICalculator from "./ROICalculator";
import TrustSection from "./TrustSection";

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0 },
};

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6 lg:px-8">{children}</div>
);

const Badge = ({ children, className = "" }) => (
  <span className={`inline-flex items-center gap-2 rounded-full bg-blue-500/10 border border-blue-500/20 px-4 py-1.5 text-sm font-medium text-blue-700 ${className}`}>
    {children}
  </span>
);

const PrimaryButton = ({ children, onClick, href, className = "", variant = "default", ...props }) => {
  const Component = href ? 'a' : 'button';
  const baseClasses = "group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-lg font-semibold shadow-lg btn-interactive focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";
  
  const variants = {
    default: "bg-[#0066CC] text-white px-8 py-4 text-lg hover:bg-[#0052A3] focus-visible:outline-blue-600",
    large: "bg-[#0066CC] text-white px-10 py-5 text-xl hover:bg-[#0052A3] focus-visible:outline-blue-600",
    outline: "border-2 border-[#0066CC] text-[#0066CC] px-8 py-4 text-lg hover:bg-blue-50 focus-visible:outline-blue-600"
  };
  
  return (
    <Component
      href={href}
      onClick={onClick}
      className={`${baseClasses} ${variants[variant]} ${className}`}
      {...props}
    >
      <span className="relative z-10 flex items-center gap-2">
        {children}
      </span>
      <ArrowRight className="relative z-10 h-5 w-5 transition-transform group-hover:translate-x-1" />
    </Component>
  );
};

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
        className="h-full bg-[#0066CC]"
        style={{ scaleX: p, transformOrigin: "0%" }}
      />
    </div>
  );
};

const FAQ = ({ q, a, isOpen, onToggle }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4 }}
  >
    <div
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:border-blue-200 hover:shadow-md cursor-pointer"
      onClick={onToggle}
    >
      <div className="flex items-center justify-between gap-6">
        <h3 className="font-semibold text-slate-900 text-lg">{q}</h3>
        <ChevronDown className={`h-5 w-5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </div>
      {isOpen && (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-4 text-slate-600 leading-relaxed"
        >
          {a}
        </motion.p>
      )}
    </div>
  </motion.div>
);

export default function UwiLanding() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          setMobileMenuOpen(false);
        }
      });
    });

    // Header sticky intelligent
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-white text-[#111827] antialiased">
      <ScrollProgress />

      {/* Header */}
      <header className={`sticky top-0 z-50 border-b transition-all duration-300 ${
        scrolled 
          ? 'bg-white shadow-medium border-[#E5E7EB]' 
          : 'bg-white/80 backdrop-blur-xl border-[#E5E7EB]/50'
      }`}>
        <Container>
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#0066CC] text-white shadow-lg">
                <span className="text-base font-bold">UW<span className="text-blue-200">i</span></span>
              </div>
              <div className="text-base font-bold text-[#111827]">UWI</div>
            </div>

            <nav className="hidden items-center gap-8 text-sm font-medium text-[#111827] md:flex" aria-label="Navigation">
              <a href="/" className="transition-colors hover:text-[#0066CC]">Accueil</a>
              <a href="#use-cases" className="transition-colors hover:text-[#0066CC]">Médecins</a>
              <a href="#use-cases" className="transition-colors hover:text-[#0066CC]">Artisans</a>
              <a href="#use-cases" className="transition-colors hover:text-[#0066CC]">Avocats</a>
            </nav>

            <div className="hidden md:flex items-center gap-4">
              <PrimaryButton href="#contact" variant="default">
                Essai gratuit 14 jours
              </PrimaryButton>
            </div>

            <button
              className="md:hidden p-2"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Menu"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>

          {mobileMenuOpen && (
            <div className="md:hidden py-4 border-t border-[#E5E7EB]">
              <nav className="flex flex-col gap-4">
                <a href="/" className="text-sm font-medium text-[#111827] hover:text-[#0066CC]">Accueil</a>
                <a href="#use-cases" className="text-sm font-medium text-[#111827] hover:text-[#0066CC]">Médecins</a>
                <a href="#use-cases" className="text-sm font-medium text-[#111827] hover:text-[#0066CC]">Artisans</a>
                <a href="#use-cases" className="text-sm font-medium text-[#111827] hover:text-[#0066CC]">Avocats</a>
                <PrimaryButton href="#contact" variant="default" className="w-full justify-center">
                  Essai gratuit
                </PrimaryButton>
              </nav>
            </div>
          )}
        </Container>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden pt-20 pb-16 md:pt-28 md:pb-24 bg-gradient-light">
        {/* Cercles décoratifs */}
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-gradient-to-br from-blue-400/20 to-blue-600/10 blur-3xl animate-fade-in" />
        <div className="absolute top-1/2 -left-40 h-96 w-96 rounded-full bg-gradient-to-br from-blue-300/20 to-blue-500/10 blur-3xl animate-fade-in delay-200" />
        
        <Container>
          <div className="mx-auto max-w-5xl text-center relative z-10">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="animate-slide-up"
            >
              <motion.h1 
                className="text-4xl font-bold tracking-tight text-[#111827] md:text-5xl lg:text-6xl leading-tight animate-slide-up"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                Votre IA d'accueil prend vos RDV
                <br />
                <span className="text-[#0066CC]">pendant que vous travaillez</span>
              </motion.h1>

              <motion.p 
                className="mx-auto mt-6 max-w-3xl text-lg text-slate-600 md:text-xl leading-relaxed animate-slide-up delay-100"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
              >
                Ne perdez plus de clients : votre assistant IA répond 24/7, prend les rendez-vous et les synchronise dans votre agenda en temps réel
              </motion.p>

              <motion.div 
                className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row animate-slide-up delay-200"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
              >
                <PrimaryButton href="#contact" variant="large">
                  🚀 Essai gratuit 14 jours
                </PrimaryButton>
                <button className="btn-interactive inline-flex items-center gap-2 rounded-lg border-2 border-[#E5E7EB] bg-white px-6 py-4 text-lg font-semibold text-[#111827] hover:border-[#0066CC] hover:bg-blue-50">
                  <Play className="h-5 w-5 text-[#0066CC]" />
                  📅 Démo personnalisée
                </button>
              </motion.div>

              <motion.div 
                className="mt-12 flex flex-wrap items-center justify-center gap-8 text-sm text-slate-600 animate-slide-up delay-300"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
              >
                <div className="glass-border rounded-full px-4 py-2 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>✅ Disponible 24/7</span>
                </div>
                <div className="glass-border rounded-full px-4 py-2 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>✅ Votre numéro</span>
                </div>
                <div className="glass-border rounded-full px-4 py-2 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <span>✅ Setup 30min</span>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* Social Proof */}
      <SocialProof />

      {/* Comparison Section */}
      <ComparisonSection />

      {/* Problèmes */}
      <section className="py-20 md:py-28 bg-slate-50">
        <Container>
          <div className="mx-auto max-w-4xl">
            <h2 className="text-3xl font-bold text-center text-[#111827] md:text-4xl mb-12">
              Fini la galère de la prise de rendez-vous
            </h2>

            <div className="space-y-8">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                className="flex gap-6 p-6 bg-white rounded-xl border border-slate-200 shadow-sm"
              >
                <div className="flex-shrink-0">
                  <div className="rounded-full bg-red-100 p-3">
                    <Phone className="h-6 w-6 text-red-600" />
                  </div>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-[#111827] mb-2">📞 Appels manqués = clients perdus</h3>
                  <p className="text-slate-600">
                    Vous êtes avec un client, votre téléphone sonne... Résultat : 30% des prospects partent chez vos concurrents disponibles immédiatement.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="flex gap-6 p-6 bg-white rounded-xl border border-slate-200 shadow-sm"
              >
                <div className="flex-shrink-0">
                  <div className="rounded-full bg-orange-100 p-3">
                    <Clock className="h-6 w-6 text-orange-600" />
                  </div>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-[#111827] mb-2">⏰ Gestion chronophage</h3>
                  <p className="text-slate-600">
                    Entre 2h et 5h par jour perdues en appels, SMS, emails pour gérer les RDV. C'est 20% de votre temps de travail qui disparaît.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="flex gap-6 p-6 bg-white rounded-xl border border-slate-200 shadow-sm"
              >
                <div className="flex-shrink-0">
                  <div className="rounded-full bg-red-100 p-3">
                    <XCircle className="h-6 w-6 text-red-600" />
                  </div>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-[#111827] mb-2">❌ Annulations et no-shows</h3>
                  <p className="text-slate-600">
                    15 à 25% de vos RDV annulés en dernière minute ou clients qui ne viennent pas. Votre planning troué = manque à gagner direct.
                  </p>
                </div>
              </motion.div>
            </div>
          </div>
        </Container>
      </section>

      {/* Solution 3 étapes */}
      <section id="how" className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-4xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Comment ça marche ? Simple comme 1-2-3
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {[
                {
                  number: "1",
                  title: "Vos clients appellent votre numéro habituel",
                  description: "Aucun changement de numéro. Votre IA répond instantanément.",
                  icon: Phone,
                },
                {
                  number: "2",
                  title: "Votre IA conversationnelle répond, qualifie, propose des créneaux et confirme le RDV",
                  description: "Dialogue naturel, qualification intelligente, proposition de créneaux adaptés.",
                  icon: Bot,
                },
                {
                  number: "3",
                  title: "Vous recevez la notification de RDV confirmé",
                  description: "Synchronisé dans votre agenda en temps réel. Tout est tracé.",
                  icon: CheckCircle2,
                },
              ].map((step, idx) => (
                <motion.div
                  key={step.number}
                  initial={{ opacity: 0, y: 40 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                  className="text-center"
                >
                  <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-[#0066CC] text-white text-2xl font-bold mb-6">
                    {step.number}
                  </div>
                  <div className="mb-4 flex justify-center">
                    <div className="rounded-xl bg-blue-50 p-4">
                      <step.icon className="h-8 w-8 text-[#0066CC]" />
                    </div>
                  </div>
                  <h3 className="text-xl font-semibold text-[#111827] mb-3">{step.title}</h3>
                  <p className="text-slate-600">{step.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* Cas d'usage */}
      <section id="use-cases" className="py-20 md:py-28 bg-slate-50">
        <Container>
          <div className="mx-auto max-w-6xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Conçu pour votre métier
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {[
                { icon: Stethoscope, title: "🏥 Médecins", desc: "Gestion cabinet", href: "/medecins" },
                { icon: Wrench, title: "🔧 Artisans", desc: "Dépannages", href: "/artisans" },
                { icon: Scale, title: "⚖️ Avocats", desc: "Consultations", href: "/avocats" },
                { icon: Sparkles, title: "💆 Bien-être", desc: "Spa, massage" },
                { icon: Home, title: "🏠 Services", desc: "Nettoyage, etc" },
                { icon: GraduationCap, title: "📚 Formation", desc: "Cours, coaching" },
              ].map((item, idx) => (
                <motion.a
                  key={idx}
                  href={item.href || "#contact"}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                  className="card-hover group flex flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8 text-center shadow-soft hover:border-[#0066CC]"
                >
                  <div className="text-4xl mb-2">{item.title.split(' ')[0]}</div>
                  <h3 className="text-lg font-semibold text-[#111827]">{item.title.split(' ').slice(1).join(' ')}</h3>
                  <p className="text-slate-600 text-sm">{item.desc}</p>
                  {item.href && (
                    <div className="flex items-center gap-2 text-[#0066CC] opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-sm font-medium">En savoir plus</span>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </div>
                  )}
                </motion.a>
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* Fonctionnalités */}
      <section className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-4xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Toutes les fonctionnalités dont vous avez besoin
              </h2>
            </div>

            <div className="space-y-6">
              {[
                {
                  icon: Bot,
                  title: "🤖 IA conversationnelle naturelle",
                  description: "Pas de robot monotone : dialogue naturel en français",
                },
                {
                  icon: Sync,
                  title: "📅 Synchronisation agenda temps réel",
                  description: "Google Calendar, Outlook, Doctolib... tout est sync",
                },
                {
                  icon: Bell,
                  title: "🔔 Rappels automatiques",
                  description: "SMS et email 24h avant = -70% de no-shows",
                },
                {
                  icon: BarChart3,
                  title: "📊 Tableaux de bord et analytics",
                  description: "Suivez vos stats en temps réel",
                },
                {
                  icon: ShieldCheck,
                  title: "🔒 Sécurité et confidentialité",
                  description: "Hébergement France, certifié RGPD",
                },
                {
                  icon: Settings,
                  title: "🛠️ Configuration personnalisée",
                  description: "Adaptez l'IA à votre métier en quelques clics",
                },
              ].map((feature, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                  className="flex gap-6 p-6 rounded-xl border border-slate-200 bg-slate-50"
                >
                  <div className="flex-shrink-0">
                    <div className="rounded-lg bg-blue-100 p-3">
                      <feature.icon className="h-6 w-6 text-[#0066CC]" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-[#111827] mb-1">{feature.title}</h3>
                    <p className="text-slate-600">{feature.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* ROI Calculator */}
      <ROICalculator />

      {/* Pricing */}
      <section id="pricing" className="py-20 md:py-28 bg-slate-50">
        <Container>
          <div className="mx-auto max-w-5xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Des tarifs simples et transparents
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {/* Starter */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="card-hover rounded-xl border-2 border-slate-200 bg-white p-8 shadow-medium"
              >
                <h3 className="text-2xl font-bold text-[#111827] mb-2">STARTER</h3>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-[#111827]">149€</span>
                  <span className="text-slate-600"> /mois</span>
                </div>
                <ul className="space-y-3 mb-8">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">200 appels /mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">1 agenda</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">SMS rappel</span>
                  </li>
                </ul>
                <PrimaryButton href="#contact" variant="default" className="w-full justify-center">
                  Essai
                </PrimaryButton>
              </motion.div>

              {/* Pro */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="card-hover rounded-xl border-2 border-[#0066CC] bg-white p-8 shadow-medium relative scale-105"
              >
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#0066CC] px-4 py-1 text-sm font-semibold text-white">
                    <Star className="h-4 w-4 fill-white" />
                    POPULAIRE
                  </span>
                </div>
                <h3 className="text-2xl font-bold text-[#111827] mb-2">PRO</h3>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-[#111827]">249€</span>
                  <span className="text-slate-600"> /mois</span>
                </div>
                <ul className="space-y-3 mb-8">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">500 appels</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Multi-agenda</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">3 agendas</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Analytics</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Support prioritaire</span>
                  </li>
                </ul>
                <PrimaryButton href="#contact" variant="large" className="w-full justify-center">
                  Essai
                </PrimaryButton>
              </motion.div>

              {/* Enterprise */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="card-hover rounded-xl border-2 border-slate-200 bg-white p-8 shadow-medium"
              >
                <h3 className="text-2xl font-bold text-[#111827] mb-2">ENTERPRISE</h3>
                <div className="mb-6">
                  <span className="text-2xl font-bold text-[#111827]">Sur mesure</span>
                </div>
                <ul className="space-y-3 mb-8">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Illimité</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Multi-sites</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">API</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span className="text-slate-700">Support dédié</span>
                  </li>
                </ul>
                <PrimaryButton href="#contact" variant="outline" className="w-full justify-center">
                  Contact
                </PrimaryButton>
              </motion.div>
            </div>

            <p className="text-center mt-8 text-slate-600">
              Tous les plans : 14 jours d'essai gratuit • Sans engagement
            </p>
          </div>
        </Container>
      </section>

      {/* Trust Section */}
      <TrustSection />

      {/* FAQ */}
      <section id="faq" className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Questions fréquentes
              </h2>
            </div>
            <div className="space-y-4">
              {[
                {
                  q: "Comment fonctionne l'intégration avec mon agenda ?",
                  a: "UWI se connecte en temps réel à Google Calendar, Outlook, Doctolib et tous les systèmes d'agenda standards. La synchronisation est bidirectionnelle et automatique. Vous voyez vos créneaux disponibles en temps réel, et les RDV pris par UWI apparaissent instantanément dans votre agenda.",
                },
                {
                  q: "Puis-je personnaliser les questions posées ?",
                  a: "Absolument. UWI s'adapte à votre métier. Vous définissez les questions essentielles, les réponses possibles, et le parcours de qualification. L'IA s'entraîne sur vos spécificités pour offrir une expérience personnalisée à vos clients.",
                },
                {
                  q: "Que se passe-t-il si l'IA ne comprend pas ?",
                  a: "UWI gère les cas complexes intelligemment : demande de clarification, transfert vers un humain selon vos règles, ou proposition d'alternative. Vous gardez le contrôle total avec des règles de routing personnalisables.",
                },
                {
                  q: "Comment gérez-vous les données personnelles ?",
                  a: "Hébergement en France, conformité RGPD stricte, chiffrement des données, accès sécurisé. Vos données clients restent votre propriété. Certifications et audits réguliers garantissent votre conformité légale.",
                },
                {
                  q: "Puis-je garder mon numéro de téléphone actuel ?",
                  a: "Oui, c'est même recommandé ! UWI s'intègre à votre infrastructure téléphonique existante. Vos clients appellent le même numéro, mais c'est l'IA qui répond intelligemment.",
                },
                {
                  q: "Quel est le délai de mise en place ?",
                  a: "Moins de 30 minutes. Configuration de l'IA, connexion de votre agenda, test avec un appel réel, et c'est parti ! Aucune compétence technique requise, notre équipe vous guide si besoin.",
                },
                {
                  q: "Proposez-vous un support technique ?",
                  a: "Oui, support inclus dans tous les plans. Pour Pro et Enterprise : support prioritaire par email, chat et téléphone. Documentation complète, vidéos tutoriels, et assistance à la configuration.",
                },
              ].map((faq, idx) => (
                <FAQ
                  key={idx}
                  q={faq.q}
                  a={faq.a}
                  isOpen={openFaq === idx}
                  onToggle={() => setOpenFaq(openFaq === idx ? null : idx)}
                />
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* Témoignages */}
      <section className="py-20 md:py-28 bg-white">
        <Container>
          <div className="mx-auto max-w-6xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Ce que disent nos clients
              </h2>
              <div className="mt-6 flex items-center justify-center gap-6 text-sm text-slate-600">
                <div className="glass-border rounded-full px-4 py-2 flex items-center gap-2">
                  <Star className="h-5 w-5 text-yellow-400 fill-yellow-400" />
                  <span className="font-semibold">4.9/5</span>
                  <span>sur Google</span>
                </div>
                <div className="glass-border rounded-full px-4 py-2">
                  <span className="font-semibold">500+</span> clients satisfaits
                </div>
                <div className="glass-border rounded-full px-4 py-2">
                  <span className="font-semibold">50,000+</span> RDV gérés/mois
                </div>
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {[
                {
                  name: "Dr. Marie Dubois",
                  role: "Médecin généraliste",
                  avatar: "MD",
                  quote: "UWI a transformé mon cabinet. Je gagne 3h par jour que je peux consacrer à mes patients. Plus jamais d'appels manqués !",
                  roi: "3h gagnées/jour",
                  rating: 5,
                },
                {
                  name: "Thomas Laurent",
                  role: "Plombier",
                  avatar: "TL",
                  quote: "Depuis UWI, je ne perds plus de clients. L'IA qualifie parfaitement les demandes et mon CA a augmenté de 30%.",
                  roi: "+30% de CA",
                  rating: 5,
                },
                {
                  name: "Maître Sophie Martin",
                  role: "Avocate",
                  avatar: "SM",
                  quote: "10h économisées par mois en gestion administrative. UWI prend tous mes rendez-vous et je garde le contrôle total.",
                  roi: "10h/mois économisées",
                  rating: 5,
                },
              ].map((testimonial, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                  className="card-hover rounded-xl border border-slate-200 bg-white p-6 shadow-soft"
                >
                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-primary text-white font-bold text-sm">
                      {testimonial.avatar}
                    </div>
                    <div>
                      <div className="font-semibold text-[#111827]">{testimonial.name}</div>
                      <div className="text-sm text-slate-600">{testimonial.role}</div>
                    </div>
                  </div>
                  <div className="flex gap-1 mb-4">
                    {[...Array(testimonial.rating)].map((_, i) => (
                      <Star key={i} className="h-4 w-4 text-yellow-400 fill-yellow-400" />
                    ))}
                  </div>
                  <div className="relative">
                    <Quote className="absolute -top-2 -left-2 h-8 w-8 text-blue-100" />
                    <p className="text-slate-700 leading-relaxed relative z-10">{testimonial.quote}</p>
                  </div>
                  <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-green-50 px-3 py-1 text-sm font-medium text-green-700">
                    <TrendingUp className="h-4 w-4" />
                    {testimonial.roi}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </Container>
      </section>

      {/* Contact */}
      <section id="contact" className="py-20 md:py-28 bg-gradient-light">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-[#111827] md:text-4xl mb-4">
                Prêt à transformer votre gestion de rendez-vous ?
              </h2>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="rounded-xl border-2 border-slate-200 bg-white p-8 shadow-medium"
            >
              <form onSubmit={(e) => e.preventDefault()} className="space-y-6">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-[#111827] mb-2">
                    Nom et Prénom*
                  </label>
                  <input
                    type="text"
                    id="name"
                    required
                    className="focus-ring w-full rounded-lg border-2 border-[#E5E7EB] px-4 py-3 transition-colors hover:border-[#0066CC]/50"
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-[#111827] mb-2">
                    Email professionnel*
                  </label>
                  <input
                    type="email"
                    id="email"
                    required
                    className="focus-ring w-full rounded-lg border-2 border-[#E5E7EB] px-4 py-3 transition-colors hover:border-[#0066CC]/50"
                  />
                </div>
                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-[#111827] mb-2">
                    Téléphone*
                  </label>
                  <input
                    type="tel"
                    id="phone"
                    required
                    className="focus-ring w-full rounded-lg border-2 border-[#E5E7EB] px-4 py-3 transition-colors hover:border-[#0066CC]/50"
                  />
                </div>
                <div>
                  <label htmlFor="profession" className="block text-sm font-medium text-[#111827] mb-2">
                    Votre profession*
                  </label>
                  <select
                    id="profession"
                    required
                    className="focus-ring w-full rounded-lg border-2 border-[#E5E7EB] px-4 py-3 transition-colors hover:border-[#0066CC]/50"
                  >
                    <option value="">Sélectionnez...</option>
                    <option value="medecin">Médecin</option>
                    <option value="artisan">Artisan</option>
                    <option value="avocat">Avocat</option>
                    <option value="autre">Autre...</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="message" className="block text-sm font-medium text-[#111827] mb-2">
                    Message (optionnel)
                  </label>
                  <textarea
                    id="message"
                    rows={4}
                    className="focus-ring w-full rounded-lg border-2 border-[#E5E7EB] px-4 py-3 transition-colors hover:border-[#0066CC]/50"
                  />
                </div>
                <PrimaryButton type="submit" variant="large" className="w-full justify-center">
                  Envoyer ma demande
                </PrimaryButton>
              </form>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* CTA Final */}
      <section className="py-20 md:py-28 bg-[#0066CC] text-white">
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <h2 className="text-3xl font-bold md:text-4xl mb-8">
                Rejoignez les 500+ PME qui gagnent du temps
              </h2>
              <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
                <PrimaryButton href="#contact" variant="large" className="bg-white text-[#0066CC] hover:bg-slate-100">
                  🚀 Commencer l'essai gratuit
                </PrimaryButton>
                <button className="inline-flex items-center gap-2 rounded-lg border-2 border-white/30 bg-white/10 backdrop-blur px-6 py-4 text-lg font-semibold text-white transition-all hover:bg-white/20">
                  📞 Démo
                </button>
              </div>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E7EB] bg-white py-12" role="contentinfo">
        <Container>
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0066CC] text-white">
                  <span className="text-sm font-bold">UW<span className="text-blue-200">i</span></span>
                </div>
                <div className="text-sm font-bold text-[#111827]">UWI</div>
              </div>
              <p className="text-sm text-slate-600">
                L'assistant IA qui prend vos RDV 24/7
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-[#111827] mb-4">Solutions</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="#features" className="hover:text-[#0066CC]">Fonctionnalités</a></li>
                <li><a href="#pricing" className="hover:text-[#0066CC]">Tarifs</a></li>
                <li><a href="#integrations" className="hover:text-[#0066CC]">Intégrations</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-[#111827] mb-4">Professions</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="/medecins" className="hover:text-[#0066CC]">Médecins</a></li>
                <li><a href="/artisans" className="hover:text-[#0066CC]">Artisans</a></li>
                <li><a href="/avocats" className="hover:text-[#0066CC]">Avocats</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-[#111827] mb-4">Entreprise</h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="#about" className="hover:text-[#0066CC]">À propos</a></li>
                <li><a href="#contact" className="hover:text-[#0066CC]">Contact</a></li>
                <li><a href="#blog" className="hover:text-[#0066CC]">Blog</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-[#E5E7EB] pt-8 text-center text-sm text-slate-600">
            © {new Date().getFullYear()} UWI. Tous droits réservés. | 
            <a href="#" className="ml-2 hover:text-[#0066CC]">Mentions légales</a> | 
            <a href="#" className="ml-2 hover:text-[#0066CC]">CGV</a> | 
            <a href="#" className="ml-2 hover:text-[#0066CC]">Politique de confidentialité</a>
          </div>
        </Container>
      </footer>
    </div>
  );
}
