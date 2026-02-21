// UWi Medical - Landing Page (design unifié uwiapp.com)
// Déployé via Vercel depuis landing/ — ce composant est utilisé par landing/src/App.jsx (route /)
import {
  Calendar,
  Phone,
  Star,
  ArrowRight,
  CheckCircle2,
  Brain,
  MessageSquare,
  Stethoscope,
  BarChart3,
  Shield,
  Clock,
  UserCheck,
  FileText,
  AlertCircle,
  Sparkles,
  ChevronDown,
  Heart,
  Activity,
  Mail,
  Zap,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

export default function UwiLanding() {
  const [openFaq, setOpenFaq] = useState(-1);

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="fixed top-0 left-0 right-0 bg-slate-950/90 backdrop-blur-2xl border-b border-slate-800 z-50">
        <nav className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex items-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-teal-500 rounded-xl blur-lg opacity-50"></div>
                <div className="relative w-12 h-12 bg-gradient-to-br from-teal-500 to-cyan-400 rounded-xl flex items-center justify-center shadow-2xl transform -rotate-3">
                  <Stethoscope className="w-7 h-7 text-slate-950 font-bold" strokeWidth={2.5} />
                </div>
              </div>
              <div>
                <div className="text-2xl font-black text-white tracking-tight">UWi Medical</div>
                <div className="text-[10px] text-teal-400 font-semibold tracking-widest uppercase">IA Secrétariat</div>
              </div>
            </Link>
          </div>
          <div className="hidden lg:flex items-center gap-8">
            <a href="#metiers" className="text-slate-400 hover:text-teal-400 transition-colors text-sm font-semibold">Spécialités</a>
            <a href="#fonctionnalites" className="text-slate-400 hover:text-teal-400 transition-colors text-sm font-semibold">Fonctionnalités</a>
            <a href="#fonctionnalites" className="text-slate-400 hover:text-teal-400 transition-colors text-sm font-semibold">Sécurité</a>
            <a href="#pricing" className="text-slate-400 hover:text-teal-400 transition-colors text-sm font-semibold">Tarifs</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="hidden sm:block text-slate-300 hover:text-white px-5 py-2.5 rounded-lg text-sm font-bold transition-colors">
              Connexion
            </Link>
            <Link to="/onboarding" className="relative group bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 px-7 py-3 rounded-lg text-sm font-black hover:shadow-2xl hover:shadow-teal-500/50 hover:scale-105 transition-all duration-200 inline-flex">
              <div className="absolute inset-0 bg-white/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"></div>
              <span className="relative">Démarrer →</span>
            </Link>
          </div>
        </nav>
      </header>

      <main className="pt-24">
        <section className="relative overflow-hidden bg-slate-950">
          <div className="absolute inset-0">
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-teal-500/20 rounded-full blur-[120px]"></div>
            <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-cyan-400/20 rounded-full blur-[120px]"></div>
            <div className="absolute bottom-0 left-1/2 w-96 h-96 bg-blue-500/20 rounded-full blur-[120px]"></div>
          </div>
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_110%)]"></div>

          <div className="max-w-7xl mx-auto px-6 py-24 lg:py-32 relative">
            <div className="grid lg:grid-cols-2 gap-20 items-start">
              <div className="space-y-10 lg:pt-12">
                <a href="tel:+33939240575" className="inline-flex items-center gap-3 bg-gradient-to-r from-teal-500/20 to-cyan-400/20 backdrop-blur-sm text-teal-400 px-6 py-4 rounded-2xl text-sm font-bold border border-teal-500/40 shadow-lg hover:shadow-2xl hover:shadow-teal-500/30 hover:scale-105 transition-all duration-300 group">
                  <div className="relative flex items-center justify-center">
                    <div className="absolute inset-0 bg-teal-400 rounded-full blur-md opacity-50 group-hover:opacity-75 transition-opacity"></div>
                    <Phone className="relative w-5 h-5 group-hover:rotate-12 transition-transform" />
                  </div>
                  <div className="flex flex-col items-start">
                    <span className="text-xs text-teal-300/80 font-semibold uppercase tracking-wider">📞 Écouter la démo vocale : 09 39 24 05 75</span>
                    <span className="text-base text-white font-black">Numéro de démonstration (public).</span>
                  </div>
                </a>

                <h1 className="text-6xl lg:text-7xl xl:text-8xl font-black text-white leading-[0.95] tracking-tighter">
                  Votre cabinet
                  <span className="block mt-3 bg-gradient-to-r from-teal-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
                    ne rate plus
                  </span>
                  <span className="block mt-3 text-white">
                    un seul appel
                  </span>
                </h1>

                <p className="text-xl text-slate-400 leading-relaxed max-w-xl">
                  L'IA médicale qui transforme chaque appel en opportunité.
                  <span className="block mt-3 text-slate-300 font-semibold">
                    Prise de RDV · Urgences · Renouvellements · Disponible 24/7
                  </span>
                </p>

                <div className="flex flex-col sm:flex-row gap-4 pt-4">
                  <Link to="/essai-gratuit" className="group relative bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 px-10 py-5 rounded-xl font-black hover:shadow-2xl hover:shadow-teal-500/50 hover:scale-105 transition-all duration-200 flex items-center justify-center gap-3 text-lg overflow-hidden">
                    <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <span className="relative">Essai gratuit 1 mois</span>
                    <ArrowRight className="relative w-6 h-6 group-hover:translate-x-2 transition-transform" />
                  </Link>
                  <a href="tel:+33652398414" className="group bg-slate-800/50 backdrop-blur text-white px-10 py-5 rounded-xl font-bold border-2 border-slate-700 hover:border-teal-500 hover:bg-slate-800 hover:shadow-xl transition-all duration-200 text-lg flex items-center justify-center gap-3">
                    <Phone className="w-5 h-5 group-hover:rotate-12 transition-transform" />
                    Parler à un expert
                  </a>
                </div>

                <div className="grid grid-cols-3 gap-6 pt-6 pb-8">
                  <div className="space-y-2">
                    <Shield className="w-5 h-5 text-teal-400" />
                    <div className="text-2xl font-black text-white">HDS</div>
                    <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Certifié</div>
                  </div>
                  <div className="space-y-2">
                    <Clock className="w-5 h-5 text-cyan-400" />
                    <div className="text-2xl font-black text-white">15min</div>
                    <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Setup</div>
                  </div>
                  <div className="space-y-2">
                    <UserCheck className="w-5 h-5 text-blue-400" />
                    <div className="text-2xl font-black text-white">500+</div>
                    <div className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Praticiens</div>
                  </div>
                </div>
              </div>

              <div className="relative flex justify-center lg:justify-end">
                <div className="absolute inset-0 bg-gradient-to-r from-teal-500 via-cyan-400 to-blue-500 rounded-[3rem] blur-3xl opacity-30"></div>
                <div className="relative w-full max-w-xs">
                  <div className="absolute -top-6 -right-6 w-32 h-32 bg-teal-500 rounded-3xl opacity-20 blur-2xl"></div>
                  <div className="absolute -bottom-6 -left-6 w-32 h-32 bg-cyan-400 rounded-3xl opacity-20 blur-2xl"></div>
                  <div className="relative w-full aspect-[3/4] bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl shadow-2xl border-2 border-slate-700 ring-1 ring-white/10 flex items-center justify-center">
                    <Phone className="w-24 h-24 text-teal-400" />
                  </div>
                  <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 px-6 py-3 rounded-full text-sm font-black shadow-2xl flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    IA en direct
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-slate-900 py-24 border-y border-slate-800">
          <div className="max-w-7xl mx-auto px-6">
            <div className="grid md:grid-cols-4 gap-12">
              <div className="group text-center space-y-3 p-6 rounded-2xl hover:bg-slate-800/50 transition-all">
                <div className="text-6xl font-black bg-gradient-to-br from-teal-400 to-cyan-300 bg-clip-text text-transparent group-hover:scale-110 transition-transform">24/7</div>
                <div className="text-base font-black text-white uppercase tracking-wide">Disponibilité</div>
                <div className="text-sm text-slate-500 font-medium">Permanence complète</div>
              </div>
              <div className="group text-center space-y-3 p-6 rounded-2xl hover:bg-slate-800/50 transition-all">
                <div className="text-6xl font-black bg-gradient-to-br from-teal-400 to-cyan-300 bg-clip-text text-transparent group-hover:scale-110 transition-transform">-92%</div>
                <div className="text-base font-black text-white uppercase tracking-wide">Appels manqués</div>
                <div className="text-sm text-slate-500 font-medium">Zéro perte de patients</div>
              </div>
              <div className="group text-center space-y-3 p-6 rounded-2xl hover:bg-slate-800/50 transition-all">
                <div className="text-6xl font-black bg-gradient-to-br from-teal-400 to-cyan-300 bg-clip-text text-transparent group-hover:scale-110 transition-transform">15min</div>
                <div className="text-base font-black text-white uppercase tracking-wide">Installation</div>
                <div className="text-sm text-slate-500 font-medium">Déploiement express</div>
              </div>
              <div className="group text-center space-y-3 p-6 rounded-2xl hover:bg-slate-800/50 transition-all">
                <div className="text-6xl font-black bg-gradient-to-br from-teal-400 to-cyan-300 bg-clip-text text-transparent group-hover:scale-110 transition-transform">98%</div>
                <div className="text-base font-black text-white uppercase tracking-wide">Satisfaction</div>
                <div className="text-sm text-slate-500 font-medium">Score confirmé</div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-gradient-to-b from-slate-900 to-slate-950 py-32 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-teal-500 to-transparent"></div>
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-20">
              <div className="inline-flex items-center gap-2 bg-teal-500/10 text-teal-400 px-5 py-2.5 rounded-full text-sm font-black mb-8 border border-teal-500/30">
                <Star className="w-4 h-4 fill-current" />
                TÉMOIGNAGES
              </div>
              <h2 className="text-5xl md:text-6xl font-black text-white mb-6 tracking-tight">
                Ils ont révolutionné
                <span className="block mt-2 bg-gradient-to-r from-teal-400 to-cyan-300 bg-clip-text text-transparent">leur cabinet médical</span>
              </h2>
              <p className="text-xl text-slate-400 max-w-2xl mx-auto">500+ praticiens libérés des contraintes téléphoniques</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="group relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-8 border border-slate-700 hover:border-teal-500/50 hover:shadow-2xl hover:shadow-teal-500/20 hover:-translate-y-2 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-3xl"></div>
                <div className="flex gap-1 mb-6">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-teal-400 text-teal-400" />
                  ))}
                </div>
                <p className="text-slate-300 leading-relaxed mb-8 text-base relative z-10">"UWi a transformé mon cabinet. Plus d'appels manqués, mes patients ont une réponse immédiate. Je me concentre enfin sur la médecine."</p>
                <div className="flex items-center gap-4 relative z-10">
                  <div className="w-14 h-14 bg-gradient-to-br from-teal-500 to-cyan-400 rounded-xl flex items-center justify-center text-slate-950 font-black text-lg shadow-lg transform -rotate-3">SM</div>
                  <div>
                    <div className="font-bold text-white">Dr. Sophie Martin</div>
                    <div className="text-sm text-slate-500 font-medium">Médecin généraliste · Paris</div>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-8 border border-slate-700 hover:border-cyan-400/50 hover:shadow-2xl hover:shadow-cyan-400/20 hover:-translate-y-2 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-400/10 rounded-full blur-3xl"></div>
                <div className="flex gap-1 mb-6">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-cyan-400 text-cyan-400" />
                  ))}
                </div>
                <p className="text-slate-300 leading-relaxed mb-8 text-base relative z-10">"L'IA comprend parfaitement les demandes dentaires. Elle trie les urgences et optimise mon planning. Disponible même le week-end."</p>
                <div className="flex items-center gap-4 relative z-10">
                  <div className="w-14 h-14 bg-gradient-to-br from-cyan-400 to-blue-400 rounded-xl flex items-center justify-center text-slate-950 font-black text-lg shadow-lg transform rotate-3">TD</div>
                  <div>
                    <div className="font-bold text-white">Dr. Thomas Dubois</div>
                    <div className="text-sm text-slate-500 font-medium">Chirurgien-dentiste · Lyon</div>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-8 border border-slate-700 hover:border-blue-400/50 hover:shadow-2xl hover:shadow-blue-400/20 hover:-translate-y-2 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-400/10 rounded-full blur-3xl"></div>
                <div className="flex gap-1 mb-6">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-blue-400 text-blue-400" />
                  ))}
                </div>
                <p className="text-slate-300 leading-relaxed mb-8 text-base relative z-10">"Installation en 10 minutes, efficacité immédiate. Les patients apprécient la rapidité. Rentabilisé dès le premier mois."</p>
                <div className="flex items-center gap-4 relative z-10">
                  <div className="w-14 h-14 bg-gradient-to-br from-blue-400 to-teal-400 rounded-xl flex items-center justify-center text-slate-950 font-black text-lg shadow-lg transform -rotate-3">MR</div>
                  <div>
                    <div className="font-bold text-white">Marie Rousseau</div>
                    <div className="text-sm text-slate-500 font-medium">Kinésithérapeute · Bordeaux</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-slate-950 py-32 relative overflow-hidden">
          <div className="absolute inset-0">
            <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-teal-500/10 rounded-full blur-[120px]"></div>
            <div className="absolute bottom-1/4 right-1/3 w-96 h-96 bg-cyan-400/10 rounded-full blur-[120px]"></div>
          </div>
          <div className="max-w-7xl mx-auto px-6 relative z-10">
            <div className="text-center space-y-8 mb-20">
              <div className="inline-flex items-center gap-2 bg-gradient-to-r from-teal-500/20 to-cyan-400/20 text-teal-400 px-6 py-3 rounded-full text-sm font-black border border-teal-500/30 backdrop-blur-sm">
                <Brain className="w-5 h-5" />
                INTELLIGENCE ARTIFICIELLE MÉDICALE
              </div>
              <h2 className="text-6xl md:text-7xl font-black text-white leading-tight tracking-tighter">
                Un système qui
                <span className="block mt-2 bg-gradient-to-r from-teal-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
                  ne dort jamais
                </span>
              </h2>
              <p className="text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed">
                Chaque appel devient une opportunité. Découvrez comment l'IA transforme votre accueil téléphonique.
              </p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12 items-center mb-20">
              <div className="relative group">
                <div className="absolute -inset-2 bg-gradient-to-r from-teal-600 via-blue-500 to-teal-600 rounded-[2.5rem] blur-2xl opacity-20 group-hover:opacity-30 transition-opacity duration-700 animate-pulse"></div>
                <div className="relative bg-gradient-to-br from-lime-100 to-lime-200 rounded-3xl p-8 shadow-2xl border-2 border-lime-300 aspect-square flex items-center justify-center">
                  <Stethoscope className="w-40 h-40 text-teal-600" />
                </div>
              </div>

              <div className="relative">
                <div className="absolute -inset-6 bg-gradient-to-r from-teal-500 via-cyan-400 to-blue-500 rounded-3xl blur-3xl opacity-20"></div>
                <div className="relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-12 border-2 border-teal-500/30 shadow-2xl">
                  <div className="inline-flex items-center gap-2 bg-teal-500/20 text-teal-400 px-4 py-2 rounded-full text-sm font-bold mb-6 border border-teal-500/40">
                    <Phone className="w-4 h-4" />
                    DÉMO EN DIRECT
                  </div>
                  <h3 className="text-4xl font-black text-white mb-4 leading-tight">
                    Testez l'IA médicale
                    <span className="block mt-2 bg-gradient-to-r from-teal-400 to-cyan-300 bg-clip-text text-transparent">en temps réel</span>
                  </h3>
                  <p className="text-slate-300 text-lg leading-relaxed mb-8">
                    Appelez notre numéro de démonstration public pour découvrir comment UWi Medical répond à vos patients.
                  </p>
                  <div className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 mb-8">
                    <div className="text-sm text-slate-400 font-semibold uppercase tracking-wide mb-3">Numéro de démonstration public</div>
                    <div className="flex items-center gap-4">
                      <div className="bg-gradient-to-br from-teal-500 to-cyan-400 rounded-xl p-3 shadow-lg">
                        <Phone className="w-6 h-6 text-slate-950" />
                      </div>
                      <a href="tel:+33939240575" className="text-4xl font-black text-white tracking-tight hover:text-teal-300 transition-colors">
                        09 39 24 05 75
                      </a>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-teal-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CheckCircle2 className="w-4 h-4 text-teal-400" />
                      </div>
                      <p className="text-slate-300">Disponible 24/7</p>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-cyan-400/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                      </div>
                      <p className="text-slate-300">Réponse immédiate</p>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-blue-400/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CheckCircle2 className="w-4 h-4 text-blue-400" />
                      </div>
                      <p className="text-slate-300">Expérience patient réelle</p>
                    </div>
                  </div>
                  <a href="tel:+33939240575" className="mt-8 w-full group relative bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 px-8 py-5 rounded-xl font-black hover:shadow-2xl hover:shadow-teal-500/50 hover:scale-105 transition-all duration-200 flex items-center justify-center gap-3 text-lg overflow-hidden inline-block text-center">
                    <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <Phone className="relative w-6 h-6 group-hover:rotate-12 transition-transform" />
                    <span className="relative">Appeler maintenant</span>
                  </a>
                </div>
              </div>
            </div>

            <div className="grid lg:grid-cols-3 gap-12 relative">
              <div className="absolute top-1/3 left-0 right-0 hidden lg:block h-0.5 bg-gradient-to-r from-transparent via-teal-300 to-transparent -z-10"></div>

              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-br from-teal-600 to-blue-600 rounded-3xl blur-xl opacity-0 group-hover:opacity-20 transition-opacity duration-500"></div>
                <div className="relative bg-white rounded-3xl p-8 border-2 border-slate-200 hover:border-teal-300 hover:shadow-2xl transition-all duration-500 h-full">
                  <div className="absolute -top-6 left-8 bg-gradient-to-br from-teal-600 to-blue-600 text-white w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-xl shadow-lg">1</div>
                  <div className="mt-4 mb-6">
                    <div className="bg-gradient-to-br from-teal-100 to-blue-100 w-20 h-20 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                      <Calendar className="w-10 h-10 text-teal-600" />
                    </div>
                    <h3 className="text-3xl font-bold text-slate-900 mb-4">Prise de RDV Patients</h3>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Agenda médical synchronisé</p>
                        <p className="text-sm text-slate-600">Créneaux disponibles en temps réel</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Qualification du motif</p>
                        <p className="text-sm text-slate-600">Consultation, urgence, renouvellement</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Rappels automatiques patients</p>
                        <p className="text-sm text-slate-600">Réduction de 85% des absences</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 p-4 bg-gradient-to-br from-teal-50 to-blue-50 rounded-xl border border-teal-100">
                    <p className="text-sm text-slate-700 leading-relaxed">
                      <span className="font-bold text-teal-600">Résultat:</span> Agenda optimisé et patients jamais laissés sans réponse, jour comme nuit.
                    </p>
                  </div>
                </div>
              </div>

              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-br from-blue-600 to-sky-600 rounded-3xl blur-xl opacity-0 group-hover:opacity-20 transition-opacity duration-500"></div>
                <div className="relative bg-white rounded-3xl p-8 border-2 border-slate-200 hover:border-blue-300 hover:shadow-2xl transition-all duration-500 h-full">
                  <div className="absolute -top-6 left-8 bg-gradient-to-br from-blue-600 to-sky-600 text-white w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-xl shadow-lg">2</div>
                  <div className="mt-4 mb-6">
                    <div className="bg-gradient-to-br from-blue-100 to-sky-100 w-20 h-20 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                      <Phone className="w-10 h-10 text-blue-600" />
                    </div>
                    <h3 className="text-3xl font-bold text-slate-900 mb-4">Gestion Urgences</h3>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Détection urgences</p>
                        <p className="text-sm text-slate-600">Transfert immédiat si nécessaire</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Escalade intelligente</p>
                        <p className="text-sm text-slate-600">Priorité aux cas urgents</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Traçabilité médicale</p>
                        <p className="text-sm text-slate-600">Chaque appel documenté</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 p-4 bg-gradient-to-br from-blue-50 to-sky-50 rounded-xl border border-blue-100">
                    <p className="text-sm text-slate-700 leading-relaxed">
                      <span className="font-bold text-blue-600">Résultat:</span> Aucun patient urgent ne reste sans réponse, protection juridique renforcée.
                    </p>
                  </div>
                </div>
              </div>

              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-br from-emerald-600 to-green-600 rounded-3xl blur-xl opacity-0 group-hover:opacity-20 transition-opacity duration-500"></div>
                <div className="relative bg-white rounded-3xl p-8 border-2 border-slate-200 hover:border-emerald-300 hover:shadow-2xl transition-all duration-500 h-full">
                  <div className="absolute -top-6 left-8 bg-gradient-to-br from-emerald-600 to-green-600 text-white w-12 h-12 rounded-2xl flex items-center justify-center font-bold text-xl shadow-lg">3</div>
                  <div className="mt-4 mb-6">
                    <div className="bg-gradient-to-br from-emerald-100 to-green-100 w-20 h-20 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                      <MessageSquare className="w-10 h-10 text-emerald-600" />
                    </div>
                    <h3 className="text-3xl font-bold text-slate-900 mb-4">Demandes Courantes</h3>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Renouvellement ordonnances</p>
                        <p className="text-sm text-slate-600">Prise en charge automatisée</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Résultats d'examens</p>
                        <p className="text-sm text-slate-600">Information et planification RDV</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold text-slate-900 mb-1">Informations pratiques</p>
                        <p className="text-sm text-slate-600">Horaires, localisation, tarifs</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-8 p-4 bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl border border-emerald-100">
                    <p className="text-sm text-slate-700 leading-relaxed">
                      <span className="font-bold text-emerald-600">Résultat:</span> 70% des appels gérés sans votre intervention, plus de temps pour vos patients.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-20 text-center">
              <div className="inline-flex items-center justify-center gap-6 bg-white rounded-2xl p-8 shadow-lg border border-slate-200">
                <div className="text-center">
                  <div className="text-4xl font-bold text-teal-600">15 min</div>
                  <div className="text-sm text-slate-600 font-medium mt-1">Installation</div>
                </div>
                <div className="w-px h-12 bg-slate-200"></div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-blue-600">24/7</div>
                  <div className="text-sm text-slate-600 font-medium mt-1">Accueil patients</div>
                </div>
                <div className="w-px h-12 bg-slate-200"></div>
                <div className="text-center">
                  <div className="text-4xl font-bold text-emerald-600">100%</div>
                  <div className="text-sm text-slate-600 font-medium mt-1">RGPD conforme</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="fonctionnalites" className="bg-white py-32">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-20">
              <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-sm font-bold mb-6">
                <Zap className="w-4 h-4" />
                Fonctionnalités
              </div>
              <h2 className="text-5xl md:text-6xl font-black text-slate-900 mb-4">Technologie médicale de pointe</h2>
              <p className="text-xl text-slate-600 max-w-3xl mx-auto">Une solution complète pensée pour les professionnels de santé</p>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-teal-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-teal-600/10 to-blue-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-teal-600 to-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <Brain className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">IA Médicale Avancée</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Formée spécifiquement au vocabulaire médical. Détecte les urgences, qualifie les symptômes et oriente parfaitement chaque patient.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-teal-100 text-teal-700 rounded-lg">Urgences</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg">Symptômes</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg">Orientation</span>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-blue-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-blue-600/10 to-teal-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-teal-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <Calendar className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">Agenda Synchronisé</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Intégration native avec tous les logiciels médicaux. Gestion automatique des consultations, urgences et visites à domicile.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg">Doctolib</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-teal-100 text-teal-700 rounded-lg">Maiia</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg">Autre</span>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-emerald-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-emerald-600/10 to-teal-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <AlertCircle className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">Gestion Urgences</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Détection instantanée des urgences médicales. Transfert immédiat vers vous ou votre ligne d'urgence avec transcription complète.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-red-100 text-red-700 rounded-lg">Détection</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-orange-100 text-orange-700 rounded-lg">Transfert</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg">Traçabilité</span>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-sky-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-sky-600/10 to-blue-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-sky-600 to-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <FileText className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">Renouvellements Auto</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Gestion autonome des demandes de renouvellement d'ordonnances. Validation, planification RDV et notification automatique.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg">Ordonnances</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg">Validation</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-teal-100 text-teal-700 rounded-lg">RDV</span>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-red-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-red-600/10 to-pink-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-red-600 to-pink-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <Shield className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">Sécurité Maximale</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Hébergement HDS certifié. Conformité RGPD santé stricte. Chiffrement bout en bout. Vos données patients ultra-protégées.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-red-100 text-red-700 rounded-lg">HDS</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-pink-100 text-pink-700 rounded-lg">RGPD</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg">Chiffrement</span>
                  </div>
                </div>
              </div>

              <div className="group relative bg-gradient-to-br from-slate-50 to-white rounded-3xl p-8 border-2 border-slate-200 hover:border-violet-300 hover:shadow-2xl transition-all duration-300">
                <div className="absolute top-8 right-8 w-20 h-20 bg-gradient-to-br from-violet-600/10 to-purple-600/10 rounded-2xl blur-2xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-violet-600 to-purple-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform">
                    <BarChart3 className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900 mb-3">Analytics Cabinet</h3>
                  <p className="text-slate-600 leading-relaxed mb-4">Tableau de bord complet : motifs de consultation, taux de remplissage, pics d'affluence. Optimisez votre activité.</p>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold px-3 py-1.5 bg-violet-100 text-violet-700 rounded-lg">Statistiques</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg">Insights</span>
                    <span className="text-xs font-semibold px-3 py-1.5 bg-pink-100 text-pink-700 rounded-lg">KPIs</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-slate-950 py-32 relative overflow-hidden">
          <div className="absolute inset-0">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-teal-500/10 rounded-full blur-[120px]"></div>
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-400/10 rounded-full blur-[120px]"></div>
          </div>
          <div className="max-w-7xl mx-auto px-6 relative z-10">
            <div className="text-center space-y-6 mb-20">
              <div className="inline-flex items-center gap-2 bg-gradient-to-r from-teal-500/20 to-cyan-400/20 text-teal-400 px-6 py-3 rounded-full text-sm font-black border border-teal-500/30 backdrop-blur-sm">
                <MessageSquare className="w-5 h-5" />
                Communication Multicanal
              </div>
              <h2 className="text-5xl md:text-6xl font-black text-white leading-tight tracking-tight">
                <span className="bg-gradient-to-r from-teal-400 to-cyan-300 bg-clip-text text-transparent">UWi</span> Communique Sur Tous Les Canaux
              </h2>
              <p className="text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed">
                Offrez à vos clients la liberté de vous contacter comme ils le souhaitent. UWi s'adapte à leurs préférences pour une expérience optimale.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="group relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 border-2 border-teal-500/30 hover:border-teal-500/60 hover:shadow-2xl hover:shadow-teal-500/20 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-3xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-teal-500/20 to-teal-600/20 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-6 border border-teal-500/30 group-hover:scale-110 transition-transform">
                    <Phone className="w-8 h-8 text-teal-400" strokeWidth={2} />
                  </div>
                  <h3 className="text-2xl font-black text-white mb-3">Téléphone</h3>
                  <p className="text-slate-400 leading-relaxed mb-6">Réponse automatique 24/7 sur votre ligne habituelle</p>
                  <div className="flex items-center gap-2 text-teal-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-bold">Disponible</span>
                  </div>
                </div>
              </div>
              <div className="group relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 border-2 border-emerald-500/30 hover:border-emerald-500/60 hover:shadow-2xl hover:shadow-emerald-500/20 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-emerald-500/20 to-emerald-600/20 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-6 border border-emerald-500/30 group-hover:scale-110 transition-transform">
                    <MessageSquare className="w-8 h-8 text-emerald-400" strokeWidth={2} />
                  </div>
                  <h3 className="text-2xl font-black text-white mb-3">WhatsApp</h3>
                  <p className="text-slate-400 leading-relaxed mb-6">Conversations naturelles et confirmations instantanées</p>
                  <div className="flex items-center gap-2 text-emerald-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-bold">Disponible</span>
                  </div>
                </div>
              </div>
              <div className="group relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 border-2 border-purple-500/30 hover:border-purple-500/60 hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-purple-500/20 to-purple-600/20 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-6 border border-purple-500/30 group-hover:scale-110 transition-transform">
                    <MessageSquare className="w-8 h-8 text-purple-400" strokeWidth={2} />
                  </div>
                  <h3 className="text-2xl font-black text-white mb-3">SMS</h3>
                  <p className="text-slate-400 leading-relaxed mb-6">Rappels automatiques et confirmations de RDV</p>
                  <div className="flex items-center gap-2 text-purple-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-bold">Disponible</span>
                  </div>
                </div>
              </div>
              <div className="group relative bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 border-2 border-orange-500/30 hover:border-orange-500/60 hover:shadow-2xl hover:shadow-orange-500/20 transition-all duration-300">
                <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/10 rounded-full blur-3xl"></div>
                <div className="relative">
                  <div className="w-16 h-16 bg-gradient-to-br from-orange-500/20 to-orange-600/20 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-6 border border-orange-500/30 group-hover:scale-110 transition-transform">
                    <Mail className="w-8 h-8 text-orange-400" strokeWidth={2} />
                  </div>
                  <h3 className="text-2xl font-black text-white mb-3">Email</h3>
                  <p className="text-slate-400 leading-relaxed mb-6">Récapitulatifs détaillés et suivis personnalisés</p>
                  <div className="flex items-center gap-2 text-orange-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-bold">Disponible</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="metiers" className="max-w-7xl mx-auto px-6 py-24 bg-white">
          <div className="text-center space-y-6 mb-16">
            <h2 className="text-6xl md:text-7xl font-bold text-slate-950 leading-tight">
              Toutes les professions médicales
            </h2>
            <p className="text-xl text-slate-600 max-w-3xl mx-auto leading-relaxed">
              UWi Medical s'adapte parfaitement à votre spécialité
            </p>
          </div>
          <div className="grid lg:grid-cols-3 gap-8">
            <div className="relative group">
              <div className="absolute -inset-2 bg-gradient-to-r from-teal-600 via-blue-500 to-teal-600 rounded-[2.5rem] blur-2xl opacity-20 group-hover:opacity-30 transition-opacity duration-700"></div>
              <div className="relative bg-white rounded-3xl p-12 shadow-2xl border-2 border-slate-100 hover:border-teal-300 transition-all duration-300 aspect-square flex flex-col items-center justify-center gap-6">
                <Stethoscope className="w-24 h-24 text-teal-600" />
                <h3 className="text-2xl font-bold text-slate-900">Médecins</h3>
              </div>
            </div>
            <div className="relative group">
              <div className="absolute -inset-2 bg-gradient-to-r from-blue-600 via-sky-500 to-blue-600 rounded-[2.5rem] blur-2xl opacity-20 group-hover:opacity-30 transition-opacity duration-700"></div>
              <div className="relative bg-white rounded-3xl p-12 shadow-2xl border-2 border-slate-100 hover:border-blue-300 transition-all duration-300 aspect-square flex flex-col items-center justify-center gap-6">
                <Heart className="w-24 h-24 text-blue-600" />
                <h3 className="text-2xl font-bold text-slate-900">Dentistes</h3>
              </div>
            </div>
            <div className="relative group">
              <div className="absolute -inset-2 bg-gradient-to-r from-emerald-600 via-green-500 to-emerald-600 rounded-[2.5rem] blur-2xl opacity-20 group-hover:opacity-30 transition-opacity duration-700"></div>
              <div className="relative bg-white rounded-3xl p-12 shadow-2xl border-2 border-slate-100 hover:border-emerald-300 transition-all duration-300 aspect-square flex flex-col items-center justify-center gap-6">
                <Activity className="w-24 h-24 text-emerald-600" />
                <h3 className="text-2xl font-bold text-slate-900">Kinésithérapeutes</h3>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="bg-white py-24">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center space-y-4 mb-20">
              <h2 className="text-5xl font-bold text-slate-950">Mise en place simple</h2>
              <p className="text-xl text-slate-600 max-w-2xl mx-auto">Démarrez en 3 étapes simples</p>
            </div>
            <div className="grid md:grid-cols-3 gap-8 relative">
              <div className="absolute top-20 left-1/3 right-1/3 hidden md:block h-1 bg-gradient-to-r from-teal-600 to-blue-600 -z-10"></div>
              <div className="relative">
                <div className="bg-gradient-to-br from-teal-600 to-blue-600 w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-2xl mb-6 mx-auto">1</div>
                <h3 className="text-2xl font-bold text-slate-900 mb-3 text-center">Configuration en 15 min</h3>
                <p className="text-slate-600 text-center">Connectez votre ligne téléphonique et synchronisez votre logiciel médical. Notre équipe vous accompagne.</p>
              </div>
              <div className="relative">
                <div className="bg-gradient-to-br from-teal-600 to-blue-600 w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-2xl mb-6 mx-auto">2</div>
                <h3 className="text-2xl font-bold text-slate-900 mb-3 text-center">UWi accueille vos patients</h3>
                <p className="text-slate-600 text-center">L'IA médicale répond 24/7, qualifie les demandes, prend les RDV et détecte les urgences.</p>
              </div>
              <div className="relative">
                <div className="bg-gradient-to-br from-teal-600 to-blue-600 w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-2xl mb-6 mx-auto">3</div>
                <h3 className="text-2xl font-bold text-slate-900 mb-3 text-center">Concentrez-vous sur vos patients</h3>
                <p className="text-slate-600 text-center">Plus d'appels manqués, agenda optimisé, patients mieux pris en charge. Plus de temps pour soigner.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="bg-gradient-to-br from-white via-teal-50 to-blue-50 py-32">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center space-y-6 mb-20">
              <h2 className="text-6xl md:text-7xl font-bold text-slate-950 leading-tight">
                Tarifs adaptés aux cabinets médicaux
              </h2>
              <p className="text-xl text-slate-600 max-w-3xl mx-auto leading-relaxed">
                Choisissez la formule adaptée à votre volume de patients
              </p>
            </div>
            <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
              <div className="bg-white rounded-3xl border-2 border-slate-200 p-10 hover:border-slate-300 hover:shadow-xl transition-all duration-300 flex flex-col">
                <h3 className="text-3xl font-bold text-slate-900 mb-2">Cabinet Solo</h3>
                <p className="text-slate-600 mb-8 text-base">Pour les praticiens seuls</p>
                <div className="mb-10">
                  <span className="text-6xl font-bold text-slate-900">149</span>
                  <span className="text-xl text-slate-600 ml-1">€/mois</span>
                </div>
                <ul className="space-y-4 mb-10 flex-grow">
                  {['Jusqu\'à 500 appels patients/mois', 'Prise de RDV automatique', 'Qualification médicale basique', 'Support par email'].map((item, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <CheckCircle2 className="w-6 h-6 text-teal-500 flex-shrink-0 mt-0.5" />
                      <span className="text-slate-700 text-base">{item}</span>
                    </li>
                  ))}
                </ul>
                <button className="w-full bg-slate-100 text-slate-900 py-4 rounded-xl font-semibold hover:bg-slate-200 transition-colors text-base">Commencer</button>
              </div>
              <div className="relative">
                <div className="absolute -top-5 left-1/2 -translate-x-1/2 z-10">
                  <div className="bg-teal-600 text-white px-6 py-2 rounded-full text-sm font-bold shadow-lg">Le plus populaire</div>
                </div>
                <div className="bg-white rounded-3xl border-4 border-teal-600 p-10 shadow-2xl hover:shadow-3xl transition-all duration-300 flex flex-col h-full">
                  <h3 className="text-3xl font-bold text-slate-900 mb-2">Cabinet Multi</h3>
                  <p className="text-slate-600 mb-8 text-base">Pour les cabinets de groupe</p>
                  <div className="mb-10">
                    <span className="text-6xl font-bold text-slate-900">299</span>
                    <span className="text-xl text-slate-600 ml-1">€/mois</span>
                  </div>
                  <ul className="space-y-4 mb-10 flex-grow">
                    {['Appels patients illimités', 'Qualification médicale avancée', 'Intégration logiciel médical', 'Support prioritaire médical 7j/7', 'Statistiques cabinet détaillées', 'Multi-praticiens'].map((item, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-6 h-6 text-teal-500 flex-shrink-0 mt-0.5" />
                        <span className="text-slate-700 text-base">{item}</span>
                      </li>
                    ))}
                  </ul>
                  <button className="w-full bg-teal-600 text-white py-4 rounded-xl font-semibold hover:bg-teal-700 transition-colors text-base shadow-lg">Essayer 14 jours</button>
                </div>
              </div>
              <div className="bg-white rounded-3xl border-2 border-slate-200 p-10 hover:border-slate-300 hover:shadow-xl transition-all duration-300 flex flex-col">
                <h3 className="text-3xl font-bold text-slate-900 mb-2">Clinique</h3>
                <p className="text-slate-600 mb-8 text-base">Pour les établissements médicaux</p>
                <div className="mb-10">
                  <span className="text-5xl font-bold text-slate-900">Sur mesure</span>
                </div>
                <ul className="space-y-4 mb-10 flex-grow">
                  {['Tout du plan Cabinet Multi', 'Gestionnaire de compte médical', 'Formation équipe médicale', 'Support dédié 24/7', 'Personnalisation par spécialité', 'API et intégrations avancées'].map((item, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <CheckCircle2 className="w-6 h-6 text-teal-500 flex-shrink-0 mt-0.5" />
                      <span className="text-slate-700 text-base">{item}</span>
                    </li>
                  ))}
                </ul>
                <button className="w-full bg-slate-900 text-white py-4 rounded-xl font-semibold hover:bg-slate-800 transition-colors text-base">Nous contacter</button>
              </div>
            </div>
            <div className="text-center mt-12">
              <p className="text-slate-600 text-base">Tous les plans incluent l'essai gratuit de 14 jours • Sans engagement</p>
            </div>
          </div>
        </section>

        <section id="faq" className="max-w-4xl mx-auto px-6 py-24 bg-white">
          <div className="text-center space-y-4 mb-16">
            <h2 className="text-5xl font-bold text-slate-950">Questions fréquentes</h2>
            <p className="text-xl text-slate-600">Tout ce que vous devez savoir sur UWi Medical</p>
          </div>
          <div className="space-y-4">
            {[
              { q: "UWi Medical est-il conforme aux normes de santé ?", a: "Oui, totalement. Hébergement certifié HDS (Hébergeur de Données de Santé), conformité RGPD santé stricte, chiffrement de bout en bout. Toutes vos données patients sont protégées selon les plus hauts standards." },
              { q: "Comment l'IA gère-t-elle les urgences médicales ?", a: "L'IA est formée à détecter les mots-clés et situations d'urgence. Elle transfère immédiatement l'appel vers vous ou votre ligne d'urgence, tout en documentant l'appel pour traçabilité." },
              { q: "Puis-je intégrer UWi à mon logiciel médical ?", a: "Oui. UWi Medical s'intègre avec les principaux logiciels médicaux (Doctolib, Maiia, etc.). Les RDV sont automatiquement synchronisés avec votre agenda existant." },
              { q: "Que se passe-t-il pendant mes consultations ?", a: "UWi continue de répondre aux appels, prend les messages et les RDV sur vos créneaux disponibles. Vous recevez une notification discrète pour les urgences uniquement." },
              { q: "Mes patients accepteront-ils de parler à une IA ?", a: "L'expérience montre que 95% des patients sont satisfaits. L'IA est naturelle, efficace et disponible 24/7. Vos patients apprécient de ne plus tomber sur un répondeur." },
            ].map((item, index) => (
              <div key={index} className="bg-white rounded-xl border border-slate-200 hover:border-teal-300 hover:shadow-lg transition-all duration-300 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setOpenFaq(openFaq === index ? -1 : index)}
                  className="w-full flex items-center justify-between p-6 text-left"
                >
                  <h3 className="text-lg font-semibold text-slate-900">{item.q}</h3>
                  <ChevronDown className={`w-5 h-5 text-slate-600 transition-transform duration-300 ${openFaq === index ? 'rotate-180' : ''}`} />
                </button>
                {openFaq === index && (
                  <div className="border-t border-slate-100 bg-teal-50/30 p-6">
                    <p className="text-slate-600 leading-relaxed">{item.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-6 py-24 text-center bg-white">
          <div className="bg-gradient-to-r from-teal-600 via-blue-600 to-teal-600 rounded-3xl p-12 md:p-16 text-white space-y-8">
            <h2 className="text-5xl md:text-6xl font-bold">Prêt à optimiser votre accueil patient ?</h2>
            <p className="text-xl text-teal-100 max-w-2xl mx-auto">Rejoignez les 300+ praticiens qui retrouvent du temps pour soigner avec UWi Medical</p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
              <Link to="/essai-gratuit" className="bg-white text-teal-600 px-10 py-4 rounded-xl font-semibold hover:bg-teal-50 transition-colors text-base text-center">Essai gratuit 1 mois</Link>
              <a href="tel:+33939240575" className="bg-teal-500/30 backdrop-blur text-white px-10 py-4 rounded-xl font-semibold border border-white/30 hover:bg-teal-500/40 transition-colors text-base inline-block text-center">📞 Écouter la démo vocale : 09 39 24 05 75</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-slate-950 border-t border-slate-800 text-slate-400 py-20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-16 mb-16">
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="relative">
                  <div className="absolute inset-0 bg-teal-500 rounded-xl blur-lg opacity-50"></div>
                  <div className="relative w-10 h-10 bg-gradient-to-br from-teal-500 to-cyan-400 rounded-xl flex items-center justify-center shadow-2xl transform -rotate-3">
                    <Stethoscope className="w-6 h-6 text-slate-950 font-bold" strokeWidth={2.5} />
                  </div>
                </div>
                <span className="font-black text-white text-lg">UWi Medical</span>
              </div>
              <p className="text-sm text-slate-500 leading-relaxed">L'IA qui révolutionne l'accueil téléphonique médical.</p>
              <div className="flex items-center gap-3 mt-6">
                <div className="px-3 py-1.5 bg-teal-500/10 border border-teal-500/30 rounded-lg">
                  <span className="text-xs font-black text-teal-400">HDS</span>
                </div>
                <div className="px-3 py-1.5 bg-cyan-400/10 border border-cyan-400/30 rounded-lg">
                  <span className="text-xs font-black text-cyan-400">RGPD</span>
                </div>
              </div>
            </div>
            <div>
              <h4 className="font-black text-white mb-6 uppercase text-sm tracking-wider">Produit</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#fonctionnalites" className="hover:text-teal-400 transition-colors font-medium">Fonctionnalités</a></li>
                <li><a href="#pricing" className="hover:text-teal-400 transition-colors font-medium">Tarifs</a></li>
                <li><a href="#securite" className="hover:text-teal-400 transition-colors font-medium">Sécurité</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Intégrations</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-black text-white mb-6 uppercase text-sm tracking-wider">Entreprise</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">À propos</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Blog</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Contact</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Carrières</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-black text-white mb-6 uppercase text-sm tracking-wider">Légal</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Confidentialité</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">CGU</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Mentions légales</a></li>
                <li><a href="#" className="hover:text-teal-400 transition-colors font-medium">Cookies</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-slate-800 pt-10 flex flex-col md:flex-row items-center justify-between text-sm">
            <p className="text-slate-500 font-medium">&copy; {new Date().getFullYear()} UWi Medical. Tous droits réservés.</p>
            <div className="flex gap-6 mt-6 md:mt-0">
              <a href="#" className="text-slate-500 hover:text-teal-400 transition-colors font-semibold">Twitter</a>
              <a href="#" className="text-slate-500 hover:text-teal-400 transition-colors font-semibold">LinkedIn</a>
              <a href="#" className="text-slate-500 hover:text-teal-400 transition-colors font-semibold">GitHub</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

