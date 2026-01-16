import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Phone,
  MessagesSquare,
  Calendar,
  UserRound,
  ShieldCheck,
  Zap,
  ArrowRight,
  Headphones,
  Sparkles,
  Check,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

const stagger = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.06,
    },
  },
};

const Container = ({ children }) => (
  <div className="max-w-7xl mx-auto px-6">{children}</div>
);

const Pill = ({ children }) => (
  <span className="inline-flex items-center gap-2 rounded-full border bg-white/70 backdrop-blur px-3 py-1 text-xs text-slate-700 shadow-sm">
    {children}
  </span>
);

const FloatingBadge = ({ icon: Icon, text, className = "", delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35, delay }}
    className={
      "absolute rounded-2xl border bg-white/90 px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm backdrop-blur " +
      className
    }
  >
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4" />
      <span>{text}</span>
    </div>
  </motion.div>
);

const PrimaryButton = ({ children }) => (
  <button className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-2xl bg-orange-500 px-6 py-3 text-base font-semibold text-white shadow-sm transition hover:brightness-95 active:brightness-90">
    {/* shimmer */}
    <motion.span
      aria-hidden
      className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 rotate-12 bg-white/25 blur-xl opacity-0 group-hover:opacity-100"
      initial={{ x: "-30%" }}
      whileHover={{ x: "260%" }}
      transition={{ duration: 0.9, ease: "linear" }}
    />

    {/* subtle pulse ring */}
    <span className="pointer-events-none absolute inset-0 rounded-2xl ring-0 ring-white/30 transition-all duration-300 group-hover:ring-2" />

    <span className="relative z-10">{children}</span>
    <ArrowRight className="relative z-10 h-4 w-4 transition group-hover:translate-x-0.5" />
  </button>
);

const SecondaryButton = ({ children, href = "#how" }) => (
  <a
    href={href}
    className="inline-flex items-center justify-center rounded-2xl border bg-white px-6 py-3 text-base font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50"
  >
    {children}
  </a>
);

const FeatureCard = ({ icon: Icon, title, children }) => (
  <motion.div
    variants={fadeUp}
    className="rounded-3xl border bg-white p-6 shadow-sm"
    whileHover={{ y: -3 }}
    transition={{ duration: 0.25 }}
  >
    <div className="flex items-start gap-4">
      <div className="rounded-2xl border bg-slate-50 p-3">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="font-semibold text-slate-900">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">{children}</p>
      </div>
    </div>
  </motion.div>
);

const Stat = ({ value, label }) => (
  <div className="rounded-3xl border bg-white/70 p-5 shadow-sm">
    <div className="text-2xl font-semibold tracking-tight">{value}</div>
    <div className="mt-1 text-sm text-slate-600">{label}</div>
  </div>
);

const MotionGrid = ({ children, className = "" }) => (
  <motion.div
    variants={stagger}
    initial="hidden"
    whileInView="show"
    viewport={{ once: true, amount: 0.25 }}
    className={className}
  >
    {children}
  </motion.div>
);

const TestimonialCard = ({ quote, name, role }) => (
  <motion.div
    variants={fadeUp}
    className="rounded-3xl border bg-white p-6 shadow-sm"
    whileHover={{ y: -3 }}
    transition={{ duration: 0.25 }}
  >
    <p className="text-sm leading-relaxed text-slate-700">"{quote}"</p>
    <div className="mt-5 flex items-center gap-3">
      <div className="h-10 w-10 rounded-2xl border bg-slate-50" />
      <div className="leading-tight">
        <div className="text-sm font-semibold">{name}</div>
        <div className="text-xs text-slate-500">{role}</div>
      </div>
    </div>
  </motion.div>
);

const IntegrationLogo = ({ label }) => (
  <motion.div
    variants={fadeUp}
    className="rounded-2xl border bg-white px-4 py-3 text-center text-xs font-semibold text-slate-700 shadow-sm"
    whileHover={{ y: -2 }}
    transition={{ duration: 0.2 }}
  >
    {label}
  </motion.div>
);

const ScrollProgress = () => {
  const [p, setP] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement;
      const scrollTop = el.scrollTop || document.body.scrollTop;
      const height = el.scrollHeight - el.clientHeight;
      const next = height > 0 ? Math.min(1, Math.max(0, scrollTop / height)) : 0;
      setP(next);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="fixed left-0 right-0 top-0 z-[60]">
      <div className="h-[3px] w-full bg-transparent">
        <motion.div
          className="h-[3px] bg-orange-500"
          style={{ scaleX: p, transformOrigin: "0% 50%" }}
        />
      </div>
    </div>
  );
};

const IllustrationPanel = ({ title = "Aperçu", subtitle = "" }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, amount: 0.25 }}
    transition={{ duration: 0.35 }}
    className="relative overflow-hidden rounded-[2.25rem] border bg-white shadow-sm"
  >
    <div className="border-b px-6 py-4">
      <div className="text-sm font-semibold">{title}</div>
      {subtitle ? <div className="text-xs text-slate-500">{subtitle}</div> : null}
    </div>

    {/* Animated SVG illustration (no external assets) */}
    <div className="relative p-6">
      <svg viewBox="0 0 640 360" className="h-56 w-full">
        <defs>
          <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgb(37 99 235)" stopOpacity="0.18" />
            <stop offset="55%" stopColor="rgb(249 115 22)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="rgb(15 23 42)" stopOpacity="0.06" />
          </linearGradient>
        </defs>

        <rect x="24" y="24" width="592" height="312" rx="28" fill="url(#g1)" />

        <circle cx="145" cy="170" r="30" fill="white" opacity="0.85" />
        <circle cx="495" cy="110" r="26" fill="white" opacity="0.85" />
        <circle cx="510" cy="255" r="26" fill="white" opacity="0.85" />

        <circle cx="320" cy="180" r="46" fill="white" opacity="0.95" />
        <motion.circle
          cx="320"
          cy="180"
          r="22"
          fill="rgb(249 115 22)"
          opacity="0.9"
          initial={{ scale: 0.96 }}
          whileInView={{ scale: [0.96, 1.03, 0.96] }}
          viewport={{ once: true }}
          transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
        />

        <motion.path
          d="M175 170 C235 150, 260 130, 320 180"
          fill="none"
          stroke="rgb(37 99 235)"
          strokeWidth="6"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0.35 }}
          whileInView={{ pathLength: 1, opacity: 0.65 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease: "easeInOut" }}
        />
        <motion.path
          d="M366 170 C410 135, 445 125, 495 110"
          fill="none"
          stroke="rgb(249 115 22)"
          strokeWidth="6"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0.35 }}
          whileInView={{ pathLength: 1, opacity: 0.65 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease: "easeInOut", delay: 0.1 }}
        />
        <motion.path
          d="M355 205 C410 230, 450 245, 510 255"
          fill="none"
          stroke="rgb(37 99 235)"
          strokeWidth="6"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0.35 }}
          whileInView={{ pathLength: 1, opacity: 0.65 }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease: "easeInOut", delay: 0.2 }}
        />

        <motion.g
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <rect x="70" y="235" width="210" height="60" rx="18" fill="white" opacity="0.92" />
          <rect x="92" y="255" width="140" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.12" />
          <rect x="92" y="273" width="110" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.08" />
        </motion.g>

        <motion.g
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.25 }}
        >
          <rect x="360" y="35" width="240" height="60" rx="18" fill="white" opacity="0.92" />
          <rect x="382" y="55" width="170" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.12" />
          <rect x="382" y="73" width="120" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.08" />
        </motion.g>

        <motion.g
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.35 }}
        >
          <rect x="370" y="275" width="230" height="60" rx="18" fill="white" opacity="0.92" />
          <rect x="392" y="295" width="150" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.12" />
          <rect x="392" y="313" width="110" height="10" rx="6" fill="rgb(15 23 42)" opacity="0.08" />
        </motion.g>
      </svg>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {["Voix", "Chat", "Handoff"].map((x) => (
          <div
            key={x}
            className="rounded-2xl border bg-slate-50 px-4 py-3 text-center text-xs font-semibold text-slate-700"
          >
            {x}
          </div>
        ))}
      </div>
    </div>

    <div className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 rounded-full bg-orange-200/30 blur-3xl" />
  </motion.div>
);

const Timeline = ({ items }) => (
  <div className="rounded-[2.25rem] border bg-white p-8 shadow-sm md:p-10">
    <div className="text-sm font-semibold">Timeline</div>
    <p className="mt-2 text-sm text-slate-600">Un parcours simple, explicite, orienté action.</p>

    <div className="mt-7 relative">
      <div className="absolute left-[18px] top-1 bottom-1 w-px bg-slate-200" />
      <motion.div
        className="absolute left-[18px] top-1 w-px bg-orange-500"
        initial={{ height: 0 }}
        whileInView={{ height: "100%" }}
        viewport={{ once: true, amount: 0.35 }}
        transition={{ duration: 1.1, ease: "easeInOut" }}
      />

      <div className="space-y-6">
        {items.map((it, idx) => (
          <motion.div
            key={it.title}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.35, delay: idx * 0.06 }}
            className="flex gap-4"
          >
            <div className="relative">
              <div className="mt-1 h-9 w-9 rounded-2xl bg-slate-900 text-white grid place-items-center text-sm font-semibold">
                {idx + 1}
              </div>
              <div className="absolute -right-2 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-orange-500" />
            </div>
            <div>
              <div className="font-semibold">{it.title}</div>
              <div className="mt-1 text-sm text-slate-600">{it.desc}</div>
              {it.tags?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {it.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-full border bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  </div>
);

const FAQ = ({ q, a }) => (
  <details className="group rounded-3xl border bg-white p-6 shadow-sm">
    <summary className="cursor-pointer list-none font-semibold text-slate-900">
      <div className="flex items-center justify-between gap-6">
        <span>{q}</span>
        <span className="rounded-full border bg-slate-50 px-2 py-1 text-xs text-slate-600 group-open:hidden">
          Ouvrir
        </span>
        <span className="hidden rounded-full border bg-slate-50 px-2 py-1 text-xs text-slate-600 group-open:inline">
          Fermer
        </span>
      </div>
    </summary>
    <p className="mt-3 text-sm leading-relaxed text-slate-600">{a}</p>
  </details>
);

export default function UwiLanding() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <ScrollProgress />

      {/* Background */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        {/* soft blobs */}
        <div className="absolute -top-24 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-orange-200/30 blur-3xl" />
        <div className="absolute top-40 left-10 h-72 w-72 rounded-full bg-blue-200/25 blur-3xl" />
        <div className="absolute bottom-10 right-10 h-72 w-72 rounded-full bg-slate-200/35 blur-3xl" />

        {/* subtle grid like Vercel */}
        <div className="absolute inset-0 opacity-[0.08] [mask-image:radial-gradient(ellipse_at_top,black,transparent_65%)]">
          <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(15,23,42,0.7)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.7)_1px,transparent_1px)] bg-[size:48px_48px]" />
        </div>
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/75 backdrop-blur">
        <Container>
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl bg-blue-600 text-white shadow-sm">
                <span className="text-sm font-semibold">UW<span className="text-orange-400">i</span></span>
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold">UWi</div>
                <div className="text-xs text-slate-500">Agent d'accueil IA multicanal</div>
              </div>
            </div>

            <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
              <a className="hover:text-slate-900" href="#promises">
                Promesses
              </a>
              <a className="hover:text-slate-900" href="#integrations">
                Intégrations
              </a>
              <a className="hover:text-slate-900" href="#how">
                Fonctionnement
              </a>
              <a className="hover:text-slate-900" href="#testimonials">
                Témoignages
              </a>
              <a className="hover:text-slate-900" href="#trust">
                Confiance
              </a>
              <a className="hover:text-slate-900" href="#faq">
                FAQ
              </a>
            </nav>

            <div className="flex items-center gap-3">
              <a
                href="#how"
                className="hidden rounded-2xl border bg-white px-5 py-2.5 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 md:inline-flex"
              >
                Voir comment ça marche
              </a>
              <PrimaryButton>Demander une démo</PrimaryButton>
            </div>
          </div>
        </Container>
      </header>

      {/* Hero */}
      <section className="pt-14 md:pt-20">
        <Container>
          <div className="grid grid-cols-1 items-center gap-12 md:grid-cols-2">
            <motion.div initial="hidden" animate="show" variants={fadeUp}>
              <div className="flex flex-wrap items-center gap-2">
                <Pill>
                  <Zap className="h-3.5 w-3.5" /> Répond 24/7
                </Pill>
                <Pill>
                  <Calendar className="h-3.5 w-3.5" /> Prend des RDV
                </Pill>
                <Pill>
                  <Headphones className="h-3.5 w-3.5" /> Transfert humain
                </Pill>
              </div>

              <h1 className="mt-6 text-4xl font-semibold tracking-tight md:text-5xl">
                <span className="bg-gradient-to-r from-blue-600 to-orange-500 bg-clip-text text-transparent">$1</span>
              </h1>

              <p className="mt-5 text-lg leading-relaxed text-slate-600">
                UWi est l'agent d'accueil IA de votre entreprise : il répond, qualifie et
                déclenche l'action.
                <br />
                <span className="font-medium text-slate-900">Multicanal par nature</span>
                {" — "}
                voix aujourd'hui, chat/avatars/email ensuite.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <PrimaryButton>Demander une démo</PrimaryButton>
                <SecondaryButton href="#promises">Voir les promesses</SecondaryButton>
              </div>

              <div className="mt-6 rounded-3xl border bg-white/70 p-5 shadow-sm">
                <div className="text-sm font-semibold">Ce que vous obtenez</div>
                <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                  <span className="inline-flex items-center gap-2">
                    <Check className="h-4 w-4" /> Accueil immédiat
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Check className="h-4 w-4" /> Qualification structurée
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Check className="h-4 w-4" /> RDV + confirmations
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Check className="h-4 w-4" /> Handoff si nécessaire
                  </span>
                </div>
              </div>

              <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Stat value="0" label="demande oubliée (objectif)" />
                <Stat value="1" label="agent, plusieurs canaux" />
                <Stat value="24/7" label="disponible" />
              </div>

              <div className="mt-8 text-xs text-slate-500">
                Conçu pour les PME : simple, contrôlable, et orienté action.
              </div>
            </motion.div>

            {/* Hero mock */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45 }}
              className="relative"
            >
              {/* Floating value badges */}
              <FloatingBadge icon={Zap} text="Réponse immédiate" className="-top-5 left-6" delay={0.15} />
              <FloatingBadge icon={Calendar} text="RDV planifiés" className="top-10 -right-4" delay={0.25} />
              <FloatingBadge icon={ShieldCheck} text="Cadre maîtrisé" className="-bottom-5 right-8" delay={0.35} />

              <div className="rounded-3xl border bg-white shadow-sm">
                <div className="border-b px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold">Console d'accueil</div>
                      <div className="text-xs text-slate-500">Demande → Qualification → Action</div>
                    </div>
                    <Pill>
                      <span className="h-2 w-2 rounded-full bg-emerald-500" /> En ligne
                    </Pill>
                  </div>
                </div>

                <div className="p-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-3xl border bg-slate-50 p-5">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Phone className="h-4 w-4" /> Appel entrant
                      </div>
                      <div className="mt-3 rounded-2xl bg-white p-4 text-sm text-slate-600 shadow-sm">
                        Bonjour, je souhaite prendre un rendez-vous.
                      </div>
                      <div className="mt-3 rounded-2xl bg-white p-4 text-sm text-slate-600 shadow-sm">
                        UWi : Très bien. Quel est le motif et votre disponibilité ?
                      </div>
                      <div className="mt-3 rounded-2xl bg-white p-4 text-sm text-slate-600 shadow-sm">
                        UWi : Je vous propose mardi 10h ou jeudi 16h.
                      </div>
                    </div>

                    <div className="rounded-3xl border bg-slate-50 p-5">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <UserRound className="h-4 w-4" /> Résumé structuré
                      </div>
                      <div className="mt-3 space-y-2 text-sm">
                        <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 shadow-sm">
                          <span className="text-slate-600">Motif</span>
                          <span className="font-medium">RDV</span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 shadow-sm">
                          <span className="text-slate-600">Urgence</span>
                          <span className="font-medium">Standard</span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 shadow-sm">
                          <span className="text-slate-600">Canal</span>
                          <span className="font-medium">Voix</span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 shadow-sm">
                          <span className="text-slate-600">Action</span>
                          <span className="font-medium">Proposer créneaux</span>
                        </div>
                      </div>
                      <div className="mt-4 rounded-2xl border bg-white p-4 text-xs text-slate-600 shadow-sm">
                        ✅ Sortie claire : rendez-vous planifié ou transfert humain.
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <div className="rounded-3xl border bg-slate-50 p-4">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Calendar className="h-4 w-4" /> Agenda
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Créneaux + confirmations, automatiquement.</p>
                    </div>
                    <div className="rounded-3xl border bg-slate-50 p-4">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <MessagesSquare className="h-4 w-4" /> Chat
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Même logique d'accueil sur votre site.</p>
                    </div>
                    <div className="rounded-3xl border bg-slate-50 p-4">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <ShieldCheck className="h-4 w-4" /> Contrôle
                      </div>
                      <p className="mt-2 text-xs text-slate-600">Règles, périmètre, et handoff.</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pointer-events-none absolute -bottom-10 -right-8 hidden h-40 w-40 rounded-full bg-orange-200/40 blur-3xl md:block" />
            </motion.div>
          </div>
        </Container>
      </section>

      {/* Social proof */}
      <section className="mt-12 md:mt-16">
        <Container>
          <div className="rounded-[2.25rem] border bg-white/70 p-8 shadow-sm">
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-semibold">Pensé pour un accueil professionnel</div>
                <div className="mt-1 text-sm text-slate-600">Une promesse simple : aucune demande ne se perd.</div>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {["PME", "Cabinets", "Artisans", "Services"].map((l) => (
                  <div
                    key={l}
                    className="rounded-2xl border bg-slate-50 px-4 py-3 text-center text-xs font-semibold text-slate-700"
                  >
                    {l}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* Promises */}
      <section id="promises" className="mt-16 md:mt-24">
        <Container>
          <div className="grid items-start gap-8 md:grid-cols-2">
            <div>
              <div className="flex flex-col gap-3">
                <Pill>
                  <Sparkles className="h-3.5 w-3.5" /> Promesses, pas blabla
                </Pill>
                <h2 className="text-3xl font-semibold tracking-tight">Les promesses UWi</h2>
                <p className="text-slate-600">
                  UWi est un agent d'accueil : il transforme une demande entrante en action concrète — réponse,
                  rendez-vous, ou transfert humain.
                </p>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                {["Accueil immédiat", "Qualification claire", "Action rapide", "Multicanal natif"].map((t) => (
                  <Pill key={t}>
                    <Check className="h-3.5 w-3.5" /> {t}
                  </Pill>
                ))}
              </div>

              <MotionGrid className="mt-10 grid gap-6">
                <FeatureCard icon={Zap} title="Réponse immédiate">
                  Un accueil disponible en continu, pour ne plus laisser un client attendre.
                </FeatureCard>
                <FeatureCard icon={Sparkles} title="Qualification fiable">
                  Les informations essentielles sont collectées et résumées en sortie.
                </FeatureCard>
                <FeatureCard icon={Calendar} title="Rendez-vous, sans friction">
                  Propose des créneaux, confirme, et évite les allers-retours inutiles.
                </FeatureCard>
              </MotionGrid>
            </div>

            <div className="md:sticky md:top-24">
              <IllustrationPanel title="De la demande à l'action" subtitle="Une sortie claire à chaque interaction" />
              <div className="mt-6 grid gap-4">
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.35 }}
                  className="rounded-3xl border bg-white p-6 shadow-sm"
                >
                  <div className="text-sm font-semibold">Pourquoi ça convertit</div>
                  <p className="mt-2 text-sm text-slate-600">
                    Le client obtient une réponse tout de suite. Vous obtenez une demande qualifiée et une action,
                    sans surcharge.
                  </p>
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.35, delay: 0.05 }}
                  className="rounded-3xl border bg-slate-900 p-6 text-white shadow-sm"
                >
                  <div className="text-sm font-semibold">Promesse centrale</div>
                  <p className="mt-2 text-sm text-white/80">
                    Aucune demande ne se perd — et chaque interaction produit une action.
                  </p>
                </motion.div>
              </div>
            </div>
          </div>

          <MotionGrid className="mt-12 grid gap-6 md:grid-cols-3">
            <FeatureCard icon={Headphones} title="Handoff humain">
              Si la demande sort du cadre, UWi transfère proprement à un humain.
            </FeatureCard>
            <FeatureCard icon={ShieldCheck} title="Contrôle & périmètre">
              Vous définissez ce que UWi peut répondre et ce qu'il doit escalader.
            </FeatureCard>
            <FeatureCard icon={MessagesSquare} title="Multicanal natif">
              Une seule logique d'accueil, plusieurs interfaces activables au fil du temps.
            </FeatureCard>
          </MotionGrid>
        </Container>
      </section>

      {/* Integrations */}
      <section id="integrations" className="mt-16 md:mt-24">
        <Container>
          <div className="grid gap-10 md:grid-cols-2 md:items-center">
            <div>
              <Pill>
                <Zap className="h-3.5 w-3.5" /> Plug & play
              </Pill>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight">S'intègre à votre quotidien</h2>
              <p className="mt-4 text-slate-600">
                UWi s'insère dans votre organisation, sans tout changer : agenda, téléphonie, et transmission interne.
                Utile dès le premier jour.
              </p>

              <div className="mt-6 grid gap-3">
                {[
                  "Agenda : prise de rendez-vous + confirmations",
                  "Téléphonie : accueil et qualification",
                  "Transmission : handoff humain clair",
                ].map((t) => (
                  <div key={t} className="flex items-start gap-3 rounded-3xl border bg-slate-50 p-5">
                    <div className="mt-0.5 h-2 w-2 rounded-full bg-orange-500" />
                    <p className="text-sm text-slate-700">{t}</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <IllustrationPanel title="Intégrations" subtitle="Agenda • Téléphonie • Transmission" />
              <div className="mt-6 rounded-3xl border bg-white p-6 shadow-sm">
                <div className="text-sm font-semibold">Exemples (placeholders)</div>
                <p className="mt-2 text-sm text-slate-600">Remplace ces placeholders par tes logos réels quand tu veux.</p>
                <MotionGrid className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {[
                    "Google Calendar",
                    "Outlook",
                    "Calendly",
                    "Twilio",
                    "Vapi",
                    "CRM",
                  ].map((x) => (
                    <IntegrationLogo key={x} label={x} />
                  ))}
                </MotionGrid>
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* How it works */}
      <section id="how" className="mt-16 md:mt-24">
        <Container>
          <div className="flex items-end justify-between gap-6">
            <div className="max-w-2xl">
              <h2 className="text-3xl font-semibold tracking-tight">Comment ça marche</h2>
              <p className="mt-4 text-slate-600">Un flux simple : accueillir, qualifier, agir. Plus explicite, plus lisible.</p>
            </div>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Timeline
              items={[
                {
                  title: "Accueil immédiat",
                  desc: "UWi répond instantanément et guide la demande dans un cadre clair.",
                  tags: ["24/7", "pro", "sans attente"],
                },
                {
                  title: "Qualification structurée",
                  desc: "Motif, urgence, infos clés : un résumé propre et exploitable.",
                  tags: ["clair", "fiable"],
                },
                {
                  title: "Action",
                  desc: "Réponse, rendez-vous, ou transfert humain — selon vos règles.",
                  tags: ["RDV", "handoff"],
                },
              ]}
            />

            <div className="space-y-6">
              <IllustrationPanel title="Illustration : du contact à l'action" subtitle="Voix aujourd'hui • Multicanal ensuite" />
              <div className="rounded-[2.25rem] border bg-white p-8 shadow-sm md:p-10">
                <div className="text-sm font-semibold">Sortie attendue</div>
                <p className="mt-2 text-sm text-slate-600">À chaque interaction, UWi produit une sortie claire.</p>
                <div className="mt-5 grid gap-3">
                  {["Une demande qualifiée", "Un rendez-vous confirmé", "Ou un transfert humain propre"].map((t) => (
                    <div key={t} className="flex items-start gap-3 rounded-3xl border bg-slate-50 p-5">
                      <div className="mt-0.5 h-2 w-2 rounded-full bg-orange-500" />
                      <p className="text-sm text-slate-700">{t}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="mt-16 md:mt-24">
        <Container>
          <div className="rounded-[2.25rem] border bg-slate-50 p-8 shadow-sm md:p-10">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <h2 className="text-3xl font-semibold tracking-tight">Un accueil qui se ressent</h2>
                <p className="mt-4 text-slate-600">
                  Quelques retours typiques (placeholders) — à remplacer par tes vrais témoignages dès que tu as 2–3
                  clients.
                </p>
              </div>
              <Pill>
                <Sparkles className="h-3.5 w-3.5" /> Clarté • Rapidité • Sérénité
              </Pill>
            </div>

            <MotionGrid className="mt-8 grid gap-6 md:grid-cols-3">
              <TestimonialCard
                quote="Les clients ont une réponse immédiate, et nous récupérons des demandes bien qualifiées."
                name="Accueil"
                role="PME de services"
              />
              <TestimonialCard
                quote="Le téléphone ne coupe plus les équipes : UWi filtre, puis transfère quand il faut."
                name="Direction"
                role="Entreprise locale"
              />
              <TestimonialCard
                quote="La prise de rendez-vous est devenue fluide. Moins d'allers-retours, moins d'oubli."
                name="Cabinet"
                role="Profession libérale"
              />
            </MotionGrid>
          </div>
        </Container>
      </section>

      {/* Trust */}
      <section id="trust" className="mt-16 md:mt-24">
        <Container>
          <div className="rounded-[2.25rem] border bg-white p-8 shadow-sm md:p-10">
            <div className="flex flex-col gap-10 md:flex-row md:items-start md:justify-between">
              <div className="max-w-2xl">
                <h2 className="text-3xl font-semibold tracking-tight">Confiance & contrôle</h2>
                <p className="mt-4 text-slate-600">UWi est conçu pour un usage pro : cadre, supervision et escalade.</p>
              </div>
              <div className="grid w-full gap-4 md:max-w-md">
                {[
                  { t: "Cadre défini", d: "Périmètre et règles maîtrisés." },
                  { t: "Supervision", d: "Historique et suivi des interactions." },
                  { t: "Handoff", d: "Transfert humain fluide quand nécessaire." },
                ].map((x) => (
                  <div key={x.t} className="rounded-3xl border bg-slate-50 p-5">
                    <div className="text-sm font-semibold">{x.t}</div>
                    <div className="mt-1 text-sm text-slate-600">{x.d}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* FAQ */}
      <section id="faq" className="mt-16 md:mt-24">
        <Container>
          <div className="rounded-[2.25rem] border bg-slate-50 p-8 shadow-sm md:p-10">
            <h2 className="text-3xl font-semibold tracking-tight">FAQ</h2>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              <FAQ
                q="UWi est-il uniquement vocal ?"
                a="Non. UWi est multicanal par nature. La voix est le premier canal activé, puis chat, avatar (optionnel) et email selon vos besoins."
              />
              <FAQ
                q="Et si la demande est complexe ?"
                a="UWi qualifie puis transfère à un humain si nécessaire. Objectif : ne jamais perdre la demande et accélérer le traitement."
              />
              <FAQ
                q="Puis-je contrôler ce que UWi répond ?"
                a="Oui. Vous définissez le périmètre, les règles et les réponses autorisées. UWi reste dans un cadre maîtrisé."
              />
              <FAQ
                q="Quelle est la promesse principale ?"
                a="Transformer une demande entrante en action : réponse, rendez-vous, ou transfert humain."
              />
            </div>
          </div>
        </Container>
      </section>

      {/* Final CTA */}
      <section className="mt-16 md:mt-24">
        <Container>
          <div className="rounded-[2.75rem] border bg-slate-900 p-10 text-white shadow-sm">
            <div className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
              <div className="max-w-2xl">
                <h2 className="text-3xl font-semibold tracking-tight">Un accueil pro, sans demandes perdues.</h2>
                <p className="mt-3 text-white/80">UWi répond, qualifie et déclenche l'action — avec handoff humain.</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row">
                <button className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-2xl bg-white px-6 py-3 text-base font-semibold text-slate-900 shadow-sm transition hover:bg-slate-100">
                  <motion.span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 rotate-12 bg-slate-900/10 blur-xl opacity-0 group-hover:opacity-100"
                    initial={{ x: "-30%" }}
                    whileHover={{ x: "260%" }}
                    transition={{ duration: 0.9, ease: "linear" }}
                  />
                  <span className="relative z-10">Demander une démo</span>
                  <ArrowRight className="relative z-10 h-4 w-4 transition group-hover:translate-x-0.5" />
                </button>
                <a
                  href="#promises"
                  className="inline-flex items-center justify-center rounded-2xl border border-white/30 bg-white/5 px-6 py-3 text-base font-semibold text-white shadow-sm transition hover:bg-white/10"
                >
                  Revoir les promesses
                </a>
              </div>
            </div>
          </div>
        </Container>
      </section>

      {/* Footer */}
      <footer className="mt-16 border-t bg-white">
        <Container>
          <div className="flex flex-col gap-3 py-8 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
            <div className="inline-flex items-center gap-2">
              <div className="grid h-9 w-9 place-items-center rounded-2xl bg-blue-600 text-white">
                <span className="text-xs font-semibold">UW<span className="text-orange-400">i</span></span>
              </div>
              <span>© UWi</span>
            </div>
            <div className="flex flex-wrap gap-4">
              <a className="hover:text-slate-700" href="#">
                Contact
              </a>
              <a className="hover:text-slate-700" href="#">
                Mentions légales
              </a>
              <a className="hover:text-slate-700" href="#">
                Confidentialité
              </a>
            </div>
          </div>
        </Container>
      </footer>

      {/* Mobile sticky CTA */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/90 backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3">
          <div className="text-sm">
            <div className="font-semibold">UWi</div>
            <div className="text-xs text-slate-600">Accueil IA • RDV • Handoff</div>
          </div>
          <button className="relative overflow-hidden inline-flex items-center justify-center rounded-2xl bg-orange-500 px-4 py-2 text-sm font-semibold text-white shadow-sm">
            Démo
          </button>
        </div>
      </div>
    </div>
  );
}
