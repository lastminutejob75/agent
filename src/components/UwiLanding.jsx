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
  Clock,
  Target,
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

const PrimaryButton = ({ children, onClick, href, className = "", ...props }) => {
  const Component = href ? 'a' : 'button';
  return (
    <Component
      href={href}
      onClick={onClick}
      className={`group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-2xl bg-orange-500 px-6 py-3 text-base font-semibold text-white shadow-sm transition hover:brightness-95 active:brightness-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-500 focus-visible:outline-offset-2 ${className}`}
      {...props}
    >
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 rotate-12 bg-white/25 blur-xl opacity-0 group-hover:opacity-100"
        initial={{ x: "-30%" }}
        whileHover={{ x: "260%" }}
        transition={{ duration: 0.9, ease: "linear" }}
      />
      <span className="pointer-events-none absolute inset-0 rounded-2xl ring-0 ring-white/30 transition-all duration-300 group-hover:ring-2" />
      <span className="relative z-10">{children}</span>
      <ArrowRight className="relative z-10 h-4 w-4 transition group-hover:translate-x-0.5" />
    </Component>
  );
};

const SecondaryButton = ({ children, href = "#how" }) => (
  <a
    href={href}
    className="inline-flex items-center justify-center rounded-2xl border bg-white px-6 py-3 text-base font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
  >
    {children}
  </a>
);

const ValueCard = ({ icon: Icon, title, description, highlight }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, amount: 0.3 }}
    transition={{ duration: 0.4 }}
    className="group relative rounded-3xl border bg-white p-8 shadow-sm transition hover:shadow-md"
  >
    <div className="flex items-start gap-4">
      <div className="rounded-2xl bg-gradient-to-br from-orange-500 to-orange-600 p-4 text-white shadow-sm">
        <Icon className="h-6 w-6" />
      </div>
      <div className="flex-1">
        <h3 className="text-xl font-semibold text-slate-900">{title}</h3>
        <p className="mt-2 text-slate-600 leading-relaxed">{description}</p>
        {highlight && (
          <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-orange-50 px-4 py-1.5 text-sm font-medium text-orange-700">
            <Sparkles className="h-4 w-4" />
            {highlight}
          </div>
        )}
      </div>
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
    <div className="fixed left-0 right-0 top-0 z-[60]">
      <div className="h-[3px] w-full bg-transparent">
        <motion.div
          className="h-full bg-gradient-to-r from-blue-600 via-orange-500 to-orange-600"
          style={{ scaleX: p, transformOrigin: "0%" }}
        />
      </div>
    </div>
  );
};

const Timeline = ({ items }) => (
  <div className="space-y-8">
    {items.map((it, idx) => (
      <motion.div
        key={it.title}
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.4, delay: idx * 0.1 }}
        className="flex gap-6"
      >
        <div className="flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-orange-500 text-white shadow-sm">
            <span className="text-lg font-semibold">{idx + 1}</span>
          </div>
          {idx < items.length - 1 && (
            <div className="mt-2 h-full w-0.5 bg-gradient-to-b from-orange-500 to-blue-500" />
          )}
        </div>
        <div className="flex-1 pb-8">
          <h3 className="text-lg font-semibold text-slate-900">{it.title}</h3>
          <p className="mt-2 text-slate-600">{it.desc}</p>
        </div>
      </motion.div>
    ))}
  </div>
);

const FAQ = ({ q, a }) => (
  <details className="group rounded-2xl border bg-white p-6 shadow-sm">
    <summary className="cursor-pointer list-none font-semibold text-slate-900">
      <div className="flex items-center justify-between gap-6">
        <span>{q}</span>
        <span className="rounded-full border bg-slate-50 px-3 py-1 text-xs text-slate-600 group-open:hidden">
          Ouvrir
        </span>
        <span className="hidden rounded-full border bg-slate-50 px-3 py-1 text-xs text-slate-600 group-open:inline">
          Fermer
        </span>
      </div>
    </summary>
    <p className="mt-3 text-sm leading-relaxed text-slate-600">{a}</p>
  </details>
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
    <div className="min-h-screen bg-white text-slate-900">
      <ScrollProgress />

      {/* Background */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute -top-24 left-1/2 h-96 w-[42rem] -translate-x-1/2 rounded-full bg-orange-200/20 blur-3xl" />
        <div className="absolute top-40 left-10 h-72 w-72 rounded-full bg-blue-200/15 blur-3xl" />
        <div className="absolute bottom-10 right-10 h-72 w-72 rounded-full bg-slate-200/20 blur-3xl" />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur-lg">
        <Container>
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-blue-600 to-orange-500 text-white shadow-sm">
                <span className="text-sm font-semibold">UW<span className="text-white">i</span></span>
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold">UWi</div>
                <div className="text-xs text-slate-500">Agent d'accueil IA</div>
              </div>
            </div>

            <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex" aria-label="Navigation principale">
              <a className="hover:text-slate-900 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2 rounded" href="#values">
                Valeurs
              </a>
              <a className="hover:text-slate-900 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2 rounded" href="#how">
                Fonctionnement
              </a>
              <a className="hover:text-slate-900 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2 rounded" href="#faq">
                FAQ
              </a>
            </nav>

            <PrimaryButton href="#contact" aria-label="Demander une démo">Demander une démo</PrimaryButton>
          </div>
        </Container>
      </header>

      {/* Hero - Proposition principale */}
      <section className="pt-20 pb-16 md:pt-28 md:pb-24">
        <Container>
          <div className="mx-auto max-w-4xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <div className="mb-6 flex flex-wrap items-center justify-center gap-2">
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

              <h1 className="text-5xl font-bold tracking-tight md:text-6xl lg:text-7xl">
                <span className="bg-gradient-to-r from-blue-600 via-orange-500 to-orange-600 bg-clip-text text-transparent">
                  Aucune demande ne se perd
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-2xl text-xl text-slate-600 md:text-2xl">
                UWi transforme chaque demande entrante en action concrète : réponse immédiate, rendez-vous planifié, ou transfert humain.
              </p>

              <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                <PrimaryButton href="#contact" className="px-8 py-4 text-lg">
                  Essayer gratuitement
                </PrimaryButton>
                <SecondaryButton href="#how">Voir comment ça marche</SecondaryButton>
              </div>

              <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border bg-white/50 p-6 backdrop-blur">
                  <div className="text-3xl font-bold text-slate-900">0</div>
                  <div className="mt-1 text-sm text-slate-600">demande oubliée</div>
                </div>
                <div className="rounded-2xl border bg-white/50 p-6 backdrop-blur">
                  <div className="text-3xl font-bold text-slate-900">24/7</div>
                  <div className="mt-1 text-sm text-slate-600">disponible</div>
                </div>
                <div className="rounded-2xl border bg-white/50 p-6 backdrop-blur">
                  <div className="text-3xl font-bold text-slate-900">1</div>
                  <div className="mt-1 text-sm text-slate-600">agent, plusieurs canaux</div>
                </div>
              </div>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* 3 Valeurs principales */}
      <section id="values" className="py-16 md:py-24">
        <Container>
          <div className="mx-auto max-w-3xl text-center mb-12">
            <Pill>
              <Target className="h-3.5 w-3.5" /> Nos promesses
            </Pill>
            <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">
              Trois promesses simples
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              UWi fait trois choses, et les fait bien.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <ValueCard
              icon={Zap}
              title="Réponse immédiate"
              description="Vos clients obtiennent une réponse instantanée, 24h/24 et 7j/7. Plus d'attente, plus de frustration."
              highlight="Temps de réponse : instantané"
            />
            <ValueCard
              icon={Sparkles}
              title="Qualification automatique"
              description="Chaque demande est analysée, structurée et résumée. Vous récupérez l'essentiel, prêt à traiter."
              highlight="100% des infos capturées"
            />
            <ValueCard
              icon={Calendar}
              title="Action déclenchée"
              description="Rendez-vous planifié, email envoyé, ou transfert humain : chaque interaction produit une action concrète."
              highlight="0 demande perdue"
            />
          </div>
        </Container>
      </section>

      {/* Comment ça marche - Simplifié */}
      <section id="how" className="py-16 md:py-24 bg-slate-50">
        <Container>
          <div className="mx-auto max-w-3xl text-center mb-12">
            <Pill>
              <Clock className="h-3.5 w-3.5" /> En 3 étapes
            </Pill>
            <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">
              Comment ça marche
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              Un processus simple et efficace, de la demande à l'action.
            </p>
          </div>

          <div className="mx-auto max-w-2xl">
            <Timeline
              items={[
                {
                  title: "Accueil",
                  desc: "UWi répond instantanément à chaque demande, quelle que soit l'heure ou le canal (voix, chat, email).",
                },
                {
                  title: "Qualification",
                  desc: "Les informations essentielles sont extraites et structurées : motif, urgence, disponibilité, besoins.",
                },
                {
                  title: "Action",
                  desc: "Selon vos règles, UWi propose un rendez-vous, répond directement, ou transfère à un humain avec toutes les informations.",
                },
              ]}
            />
          </div>
        </Container>
      </section>

      {/* FAQ - Simplifiée */}
      <section id="faq" className="py-16 md:py-24">
        <Container>
          <div className="mx-auto max-w-3xl">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Questions fréquentes</h2>
              <p className="mt-4 text-lg text-slate-600">Tout ce que vous devez savoir sur UWi</p>
            </div>
            <div className="space-y-4">
              <FAQ
                q="UWi fonctionne-t-il uniquement par téléphone ?"
                a="Non. UWi est multicanal par nature. La voix est le premier canal activé, puis chat et email selon vos besoins. Une seule logique d'accueil pour tous les canaux."
              />
              <FAQ
                q="Que se passe-t-il si la demande est complexe ?"
                a="UWi qualifie la demande puis transfère proprement à un humain avec toutes les informations. L'objectif : ne jamais perdre une demande et accélérer le traitement."
              />
              <FAQ
                q="Puis-je contrôler ce que UWi répond ?"
                a="Oui, totalement. Vous définissez le périmètre, les règles et les réponses autorisées. UWi reste dans un cadre maîtrisé que vous contrôlez."
              />
              <FAQ
                q="Combien de temps pour mettre en place UWi ?"
                a="Quelques minutes. UWi s'intègre à votre agenda existant (Google Calendar, Outlook) et à votre téléphonie. Utile dès le premier jour."
              />
            </div>
          </div>
        </Container>
      </section>

      {/* Contact - CTA final */}
      <section id="contact" className="py-16 md:py-24 bg-gradient-to-br from-slate-900 to-slate-800 text-white">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                Prêt à ne plus perdre de demande ?
              </h2>
              <p className="mt-4 text-xl text-white/80">
                Essayez UWi gratuitement pendant 14 jours. Configuration en 5 minutes.
              </p>
              <form className="mt-8 flex flex-col gap-4 sm:flex-row sm:justify-center" onSubmit={(e) => e.preventDefault()}>
                <input
                  type="email"
                  placeholder="Votre email professionnel"
                  className="flex-1 rounded-2xl border border-white/20 bg-white/10 px-6 py-4 text-base text-white placeholder:text-white/60 backdrop-blur focus:border-white/40 focus:outline-none focus:ring-2 focus:ring-white/20 sm:max-w-md"
                  aria-label="Email professionnel"
                />
                <PrimaryButton type="submit" className="bg-white text-slate-900 hover:bg-slate-100">
                  Démarrer maintenant
                </PrimaryButton>
              </form>
              <p className="mt-4 text-sm text-white/60">
                Gratuit pendant 14 jours • Sans carte bancaire • Support inclus
              </p>
            </motion.div>
          </div>
        </Container>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white py-12" role="contentinfo">
        <Container>
          <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-blue-600 to-orange-500 text-white">
                <span className="text-sm font-semibold">UW<span className="text-white">i</span></span>
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-900">UWi</div>
                <div className="text-xs text-slate-500">Agent d'accueil IA multicanal</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-slate-600">
              <a href="#values" className="hover:text-slate-900 transition-colors">Valeurs</a>
              <a href="#how" className="hover:text-slate-900 transition-colors">Fonctionnement</a>
              <a href="#faq" className="hover:text-slate-900 transition-colors">FAQ</a>
              <a href="#contact" className="hover:text-slate-900 transition-colors">Contact</a>
            </div>
          </div>
          <div className="mt-8 border-t pt-8 text-center text-sm text-slate-500">
            © {new Date().getFullYear()} UWi. Tous droits réservés.
          </div>
        </Container>
      </footer>
    </div>
  );
}
