import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import {
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Phone,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api.js";
import ASSISTANTS from "../assistants.config.js";

const AppDashboardMainPanels = lazy(() => import("../components/AppDashboardMainPanels.jsx"));
const AppDashboardWorkflowSection = lazy(() => import("../components/AppDashboardWorkflowSection.jsx"));

const TEAL_DARK = "#0ea899";
const NAVY = "#111827";
const DASHBOARD_KPIS_CACHE_KEY = "uwi_app_dashboard_kpis";
const DASHBOARD_CALLS_CACHE_KEY = "uwi_app_dashboard_calls";
const DASHBOARD_AGENDA_CACHE_KEY = "uwi_app_dashboard_agenda";

const STATUS_CFG = {
  TRANSFERRED: {
    chipBg: "#fee2e2",
    chipText: "#b91c1c",
    chipBorder: "#fecaca",
    iconBg: "#fee2e2",
    iconText: "#dc2626",
    label: "Manqué",
  },
  CONFIRMED: {
    chipBg: "#dcfce7",
    chipText: "#15803d",
    chipBorder: "#bbf7d0",
    iconBg: "#dcfce7",
    iconText: "#10b981",
    label: "OK",
  },
  ABANDONED: {
    chipBg: "#fee2e2",
    chipText: "#be123c",
    chipBorder: "#fecdd3",
    iconBg: "#fee2e2",
    iconText: "#e11d48",
    label: "Manqué",
  },
  FAQ: {
    chipBg: "#dbeafe",
    chipText: "#2563eb",
    chipBorder: "#bfdbfe",
    iconBg: "#dbeafe",
    iconText: "#3b82f6",
    label: "Prévu",
  },
};

const AVATAR_THEME = {
  sophie: { ring: "#ccfbf1", bg: "linear-gradient(135deg, #14c8b8, #34d399)" },
  emma: { ring: "#fce7f3", bg: "linear-gradient(135deg, #f9a8d4, #fbcfe8)" },
  clara: { ring: "#dbeafe", bg: "linear-gradient(135deg, #93c5fd, #c4b5fd)" },
  camille: { ring: "#fef3c7", bg: "linear-gradient(135deg, #fcd34d, #fb7185)" },
  thomas: { ring: "#dbeafe", bg: "linear-gradient(135deg, #60a5fa, #818cf8)" },
};

function Skeleton({ width = "100%", height = 16, radius = 12 }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-shimmer 1.35s infinite linear",
      }}
    />
  );
}

function DotPulse({ size = 8 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size }}>
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: "#10b981",
          opacity: 0.3,
          animation: "uwi-ping 1.8s ease-out infinite",
        }}
      />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: "#10b981" }} />
    </span>
  );
}

function WorkflowSectionFallback() {
  return (
    <>
      <section className="uwi-activation-grid" style={S.activationGrid}>
        {[1, 2].map((item) => (
          <div key={item} style={item === 1 ? S.actionsPanel : S.activationPanel}>
            <div style={{ padding: 18 }}>
              <Skeleton height={24} width={180} radius={10} />
              <div style={{ height: 12 }} />
              <Skeleton height={90} radius={14} />
              <div style={{ height: 12 }} />
              <Skeleton height={90} radius={14} />
            </div>
          </div>
        ))}
      </section>
      <section className="uwi-quick-links" style={S.quickLinks}>
        {[1, 2, 3, 4].map((item) => (
          <div key={item} style={S.quickLinkCard}>
            <Skeleton height={18} width="60%" radius={8} />
            <div style={{ height: 10 }} />
            <Skeleton height={14} width="90%" radius={8} />
          </div>
        ))}
      </section>
    </>
  );
}

function MainPanelsFallback() {
  return (
    <>
      <section
        className="uwi-main-grid"
        style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(320px, 1fr)", gap: 16, marginTop: 18 }}
      >
        {[1, 2].map((item) => (
          <div
            key={item}
            style={{
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 14,
              overflow: "hidden",
              boxShadow: "0 2px 10px rgba(15,23,42,.035)",
            }}
          >
            <div style={{ padding: 18 }}>
              <Skeleton height={20} width={150} radius={10} />
              <div style={{ height: 14 }} />
              {[1, 2, 3].map((row) => (
                <div key={row} style={{ marginBottom: row === 3 ? 0 : 12 }}>
                  <Skeleton height={80} radius={14} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>
      <section
        style={{
          marginTop: 16,
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 14,
          overflow: "hidden",
          boxShadow: "0 2px 10px rgba(15,23,42,.035)",
        }}
      >
        <div style={{ padding: 18 }}>
          <Skeleton height={20} width={120} radius={10} />
          <div style={{ height: 14 }} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
            {[1, 2, 3].map((item) => (
              <Skeleton key={item} height={110} radius={16} />
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

function getAvatarTheme(name) {
  return AVATAR_THEME[String(name || "").trim().toLowerCase()] || {
    ring: "#ccfbf1",
    bg: "linear-gradient(135deg, #14c8b8, #60a5fa)",
  };
}

function getInitial(name) {
  const value = String(name || "U").trim();
  return value ? value.charAt(0).toUpperCase() : "U";
}

function getPhoneSummary(call, fallbackAgent) {
  return call.customer_number || call.agent_name || fallbackAgent || "Numéro non identifié";
}

function getCallSortValue(call) {
  const raw = String(call?.last_event_at || call?.started_at || "").trim();
  if (raw) {
    const parsed = new Date(raw).getTime();
    if (!Number.isNaN(parsed)) return parsed;
  }
  return 0;
}

function formatCallTimeFallback(call) {
  const raw = String(call?.started_at || call?.last_event_at || "").trim();
  if (!raw) return "--:--";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return "--:--";
  return `${String(parsed.getHours()).padStart(2, "0")}:${String(parsed.getMinutes()).padStart(2, "0")}`;
}

function formatCallDurationFallback(call) {
  const fromText = String(call?.duration || "").trim();
  if (fromText && fromText !== "—" && fromText !== "-") return fromText;
  const sec = Number(call?.duration_sec);
  if (Number.isFinite(sec) && sec >= 0) {
    const minutes = Math.floor(sec / 60);
    const seconds = sec % 60;
    return `${minutes}'${String(seconds).padStart(2, "0")}`;
  }
  const startRaw = String(call?.started_at || "").trim();
  const endRaw = String(call?.last_event_at || "").trim();
  if (startRaw && endRaw) {
    const startTs = new Date(startRaw).getTime();
    const endTs = new Date(endRaw).getTime();
    if (!Number.isNaN(startTs) && !Number.isNaN(endTs) && endTs >= startTs) {
      const totalSec = Math.floor((endTs - startTs) / 1000);
      const minutes = Math.floor(totalSec / 60);
      const seconds = totalSec % 60;
      return `${minutes}'${String(seconds).padStart(2, "0")}`;
    }
  }
  return "0'00";
}

function getDialablePhone(value) {
  const raw = String(value || "").trim();
  if (!raw || /num[eé]ro non identifi[eé]/i.test(raw)) return "";
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("00")) return `+${cleaned.slice(2)}`;
  return cleaned;
}

function formatAgendaTime(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  if (/^\d{2}h$/.test(raw)) return `${raw.slice(0, 2)}:00`;
  if (/^\d{1,2}h$/.test(raw)) return `${raw.replace("h", "").padStart(2, "0")}:00`;
  if (/^\d{2}:\d{2}$/.test(raw)) return raw;
  return raw;
}

function getAgendaBadge(slot) {
  if (slot?.current) {
    return {
      label: "En cours",
      bg: "#fef3c7",
      text: "#b45309",
      border: "#fcd34d",
    };
  }
  if (slot?.done) {
    return {
      label: "Confirmé",
      bg: "#dcfce7",
      text: "#15803d",
      border: "#bbf7d0",
    };
  }
  return {
    label: "Prévu",
    bg: "#dbeafe",
    text: "#1d4ed8",
    border: "#bfdbfe",
  };
}

function getReasonBadge(call) {
  switch (call?.reason_category) {
    case "urgency":
      return { label: "Urgence", bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" };
    case "callback":
      return { label: "Rappel", bg: "#fff7ed", text: "#c2410c", border: "#fdba74" };
    case "prescription":
      return { label: "Ordonnance", bg: "#f5f3ff", text: "#7c3aed", border: "#ddd6fe" };
    case "agenda":
      return { label: "Agenda", bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" };
    default:
      return { label: "Suivi", bg: "#f8fafc", text: "#475569", border: "#e5e7eb" };
  }
}

function callIconTheme(status) {
  switch (status) {
    case "TRANSFERRED":
      return { bg: "#fee2e2", color: "#dc2626" };
    case "CONFIRMED":
      return { bg: "#dcfce7", color: "#10b981" };
    case "ABANDONED":
      return { bg: "#fef2f2", color: "#e11d48" };
    default:
      return { bg: "#dbeafe", color: "#2563eb" };
  }
}

function getActionCta(call) {
  return call?.contextual_action?.label || "Ouvrir";
}

function readSessionCache(key, fallback = null) {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeSessionCache(key, value) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage availability or quota issues.
  }
}

export default function AppDashboard() {
  const navigate = useNavigate();
  const outletContext = useOutletContext() || {};
  const contextMe = outletContext.me || null;
  const [kpis, setKpis] = useState(() => readSessionCache(DASHBOARD_KPIS_CACHE_KEY, null));
  const [calls, setCalls] = useState(() => readSessionCache(DASHBOARD_CALLS_CACHE_KEY, null));
  const [agenda, setAgenda] = useState(() => readSessionCache(DASHBOARD_AGENDA_CACHE_KEY, null));
  const [kpisLoading, setKpisLoading] = useState(() => readSessionCache(DASHBOARD_KPIS_CACHE_KEY, null) == null);
  const [callsLoading, setCallsLoading] = useState(() => readSessionCache(DASHBOARD_CALLS_CACHE_KEY, null) == null);
  const [agendaLoading, setAgendaLoading] = useState(() => readSessionCache(DASHBOARD_AGENDA_CACHE_KEY, null) == null);
  const [me, setMe] = useState(contextMe);
  const [assistantImageFailed, setAssistantImageFailed] = useState(false);
  const [tourStepIndex, setTourStepIndex] = useState(-1);
  const [tourRect, setTourRect] = useState(null);
  const [tourPersisting, setTourPersisting] = useState(false);
  const [tourDismissed, setTourDismissed] = useState(false);

  useEffect(() => {
    setMe(contextMe);
  }, [contextMe]);

  useEffect(() => {
    let mounted = true;
    let agendaIdleId = null;
    let agendaTimeoutId = null;
    setKpisLoading((current) => (kpis ? current : true));
    setCallsLoading((current) => (Array.isArray(calls) ? current : true));
    setAgendaLoading((current) => (agenda ? current : true));

    api.tenantKpis(1)
      .then((data) => {
        if (!mounted) return;
        setKpis(data);
        writeSessionCache(DASHBOARD_KPIS_CACHE_KEY, data);
      })
      .catch(() => {
        if (mounted) setKpis(null);
      })
      .finally(() => {
        if (mounted) setKpisLoading(false);
      });

    api.tenantGetCalls("?limit=4&days=7")
      .then((data) => {
        if (!mounted) return;
        const nextCalls = data?.calls || [];
        setCalls(nextCalls);
        writeSessionCache(DASHBOARD_CALLS_CACHE_KEY, nextCalls);
      })
      .catch(() => {
        if (mounted) setCalls([]);
      })
      .finally(() => {
        if (mounted) setCallsLoading(false);
      });

    const loadAgenda = () => {
      api.tenantGetAgenda("?upcoming_days=3&compact=1")
        .then((data) => {
          if (!mounted) return;
          setAgenda(data);
          writeSessionCache(DASHBOARD_AGENDA_CACHE_KEY, data);
        })
        .catch(() => {
          if (mounted) setAgenda(null);
        })
        .finally(() => {
          if (mounted) setAgendaLoading(false);
        });
    };

    if (typeof window !== "undefined" && typeof window.requestIdleCallback === "function") {
      agendaIdleId = window.requestIdleCallback(loadAgenda, { timeout: 1200 });
    } else if (typeof window !== "undefined") {
      agendaTimeoutId = window.setTimeout(loadAgenda, 250);
    } else {
      loadAgenda();
    }

    return () => {
      mounted = false;
      if (typeof window !== "undefined" && agendaIdleId !== null && typeof window.cancelIdleCallback === "function") {
        window.cancelIdleCallback(agendaIdleId);
      }
      if (typeof window !== "undefined" && agendaTimeoutId !== null) {
        window.clearTimeout(agendaTimeoutId);
      }
    };
  }, []);

  const loading = kpisLoading || callsLoading || agendaLoading;
  const assistantName = me?.assistant_name || "Emma";
  const avatarTheme = getAvatarTheme(assistantName);
  const showPhoneBanner = !me?.voice_number;
  const agendaReady = !!me?.onboarding_steps?.calendar_ready;
  const planLabel = String(me?.plan_key || "growth").replace(/^./, (char) => char.toUpperCase());
  const assistantConfig = useMemo(() => {
    const normalized = String(assistantName || "").trim().toLowerCase();
    return (
      ASSISTANTS.find(
        (assistant) =>
          assistant.id === normalized ||
          String(assistant.prenom || "").trim().toLowerCase() === normalized,
      ) || null
    );
  }, [assistantName]);

  useEffect(() => {
    setAssistantImageFailed(false);
  }, [assistantName]);

  const stats = useMemo(
    () => [
      {
        label: "Appels traités",
        value: kpis?.current?.calls ?? 0,
        icon: Phone,
        iconBg: "#eff6ff",
        iconColor: "#3b82f6",
        change: "Temps réel",
      },
      {
        label: "RDV planifiés",
        value: kpis?.current?.bookings ?? 0,
        icon: Calendar,
        iconBg: "#ecfdf5",
        iconColor: "#10b981",
        change: "Aujourd'hui",
      },
      {
        label: "Taux de réponse",
        value: `${Math.round(kpis?.pickup_rate ?? 0)}%`,
        icon: TrendingUp,
        iconBg: "#f0fdfa",
        iconColor: "#14b8a6",
        change: "Direct",
      },
      {
        label: "Minutes ce mois",
        value: kpis?.minutes_month ?? 0,
        icon: CheckCircle2,
        iconBg: "#f5f3ff",
        iconColor: "#8b5cf6",
        change: "Cumul",
      },
    ],
    [kpis],
  );

  const safeCalls = useMemo(() => (Array.isArray(calls) ? calls.filter(Boolean) : []), [calls]);
  const safeAgendaSlots = useMemo(
    () => (Array.isArray(agenda?.slots) ? agenda.slots.filter(Boolean) : []),
    [agenda?.slots],
  );

  const bookedAgendaSlots = useMemo(
    () =>
      safeAgendaSlots.filter(
        (slot) =>
          slot?.patient &&
          (slot.source === "UWI" || slot.appointment_id || slot.can_cancel || slot.can_reschedule),
      ),
    [safeAgendaSlots],
  );

  const appointmentItems = useMemo(
    () =>
      (bookedAgendaSlots.length ? bookedAgendaSlots : safeAgendaSlots.filter((slot) => slot?.patient))
        .slice(0, 4)
        .map((slot, index) => ({
          ...slot,
          key: `rdv-${slot.event_id || slot.appointment_id || `${slot.hour || "slot"}-${index}`}`,
          displayTime: formatAgendaTime(slot.hour),
          badge: getAgendaBadge(slot),
        })),
    [bookedAgendaSlots, safeAgendaSlots],
  );

  const externalAgendaItems = useMemo(
    () =>
      safeAgendaSlots
        .filter((slot) => slot?.patient && slot.source !== "UWI")
        .slice(0, 3)
        .map((slot, index) => ({
          ...slot,
          key: `agenda-${slot.event_id || `${slot.hour || "slot"}-${index}`}`,
          displayTime: formatAgendaTime(slot.hour),
        })),
    [safeAgendaSlots],
  );

  const recentCallItems = useMemo(
    () =>
      safeCalls
        .slice()
        .sort((a, b) => getCallSortValue(b) - getCallSortValue(a))
        .slice(0, 4)
        .map((call) => {
        const statusBadge = STATUS_CFG[call.status] || STATUS_CFG.ABANDONED;
        const icon = callIconTheme(call.status);
        const phoneLabel = getPhoneSummary(call, assistantName);
        return {
          id: call.id,
          patientName: call.patient_name || "Patient inconnu",
          phoneLabel,
          dialablePhone: getDialablePhone(call.customer_number || phoneLabel),
          summary: call.summary || "Aucun résumé disponible.",
          reasonLabel: call.reason_label || "",
          reasonBadge: getReasonBadge(call),
          time: call.time || formatCallTimeFallback(call),
          duration: formatCallDurationFallback(call),
          statusBadge,
          iconBg: icon.bg,
          iconColor: icon.color,
        };
      }),
    [assistantName, safeCalls],
  );

  const onboardingCards = useMemo(
    () => [
      {
        key: "assistant_ready",
        title: "Assistante choisie",
        done: !!me?.onboarding_steps?.assistant_ready,
        text: me?.assistant_name ? `${assistantName} est configurée` : "Choisissez une assistante",
        href: "/app/settings",
        cta: "Configurer",
      },
      {
        key: "phone_ready",
        title: "Numéro attribué",
        done: !!me?.onboarding_steps?.phone_ready,
        text: me?.voice_number ? `Vos patients appellent le ${me.voice_number}` : "Attribution en cours par UWI",
        href: null,
        cta: null,
      },
      {
        key: "calendar_ready",
        title: "Agenda connecté",
        done: !!me?.onboarding_steps?.calendar_ready,
        text: agendaReady ? "Votre agenda est prêt" : "Connectez Google ou gardez le mode UWI",
        href: "/app/agenda",
        cta: agendaReady ? "Ouvrir" : "Configurer",
      },
      {
        key: "horaires_ready",
        title: "Horaires OK",
        done: !!me?.onboarding_steps?.horaires_ready,
        text: me?.onboarding_steps?.horaires_ready ? "Les créneaux sont bien définis" : "Définissez les heures d'ouverture",
        href: "/app/horaires",
        cta: "Configurer",
      },
      {
        key: "faq_ready",
        title: "FAQ prête",
        done: !!me?.onboarding_steps?.faq_ready,
        text: me?.faq_items_count ? `${me.faq_items_count} réponses configurées` : "Ajoutez les réponses fréquentes du cabinet",
        href: "/app/faq",
        cta: me?.faq_items_count ? "Modifier" : "Compléter",
      },
    ],
    [agendaReady, assistantName, me],
  );

  const onboardingProgress = onboardingCards.length
    ? Math.round((onboardingCards.filter((item) => item.done).length / onboardingCards.length) * 100)
    : 0;

  const actionQueue = useMemo(
    () =>
      safeCalls
        .filter((call) => {
          if (call.followup_state === "processed") return false;
          return call.status === "TRANSFERRED" || call.followup_state === "callback" || call.reason_category !== "general";
        })
        .slice(0, 4),
    [safeCalls],
  );
  const actionQueueItems = useMemo(
    () =>
      actionQueue.map((call) => ({
        ...call,
        badge: getReasonBadge(call),
        ctaLabel: getActionCta(call),
        targetHref: call?.contextual_action?.kind === "open_agenda" ? "/app/agenda" : "/app/appels",
      })),
    [actionQueue],
  );

  const headerCards = [
    {
      label: "Numéro patient",
      value: me?.voice_number || "Attribution en cours",
      hint: me?.voice_number ? "Vos patients appellent ici" : "Activation par UWI",
    },
    {
      label: "Assistante",
      value: assistantName,
      hint: me?.assistant_live ? "Assistant vocal actif" : "Configuration en cours",
    },
    {
      label: "Agenda",
      value: agendaReady ? "Connecté" : "Mode UWI",
      hint: agendaReady ? "Synchronisé" : "Sans connexion externe",
    },
    {
      label: "Plan",
      value: planLabel,
      hint: "Abonnement actif",
    },
  ];

  const quickLinks = [
    { label: "Traiter les appels", sub: "Priorités et rappels", href: "/app/appels" },
    { label: "Gérer l'agenda", sub: "RDV et disponibilité", href: "/app/agenda" },
    { label: "Mettre à jour les horaires", sub: "Créneaux d'ouverture", href: "/app/horaires" },
    { label: "Compléter la FAQ", sub: "Réponses cabinet", href: "/app/faq" },
  ];

  const showSecurityTourStep =
    typeof window !== "undefined" && new URLSearchParams(window.location.search).get("welcome") === "1";

  const tourSteps = useMemo(() => {
    const steps = [];
    if (showSecurityTourStep) {
      steps.push({
        target: "security-banner",
        title: "Sécurisez d'abord votre accès",
        body: "Commencez par changer votre mot de passe temporaire. C'est la première action à faire avant de laisser l'équipe utiliser le dashboard.",
        example: "Exemple concret : si vous partagez l'ordinateur du cabinet, ce changement évite qu'une autre personne puisse rouvrir votre espace client.",
      });
    }
    steps.push(
      {
        target: "activation-panel",
        title: "Finalisez la mise en route du cabinet",
        body: "Ici, vous voyez ce qu'il reste à compléter pour que votre assistante travaille seule dans de bonnes conditions.",
        example: "Exemple concret : vérifier les horaires, la FAQ et l'agenda avant que l'assistante réponde à des questions comme \"Êtes-vous ouvert le samedi ?\" ou propose un créneau.",
      },
      {
        target: "quick-links",
        title: "Utilisez les raccourcis métier",
        body: "Ces accès rapides vous emmènent directement vers les réglages que vous modifierez le plus souvent au quotidien.",
        example: "Exemples concrets : FAQ = \"Prenez-vous la carte vitale ?\" ; Horaires = \"Lun-Ven 9h-18h\" ; Agenda = connecter Google Calendar si besoin.",
      },
      {
        target: "calls-panel",
        title: "Suivez les appels importants ici",
        body: "Cette zone vous montre les derniers appels, les résumés et les demandes qui nécessitent un suivi de votre part.",
        example: "Exemples concrets : \"Mme Dupont demande un renouvellement\", \"Patient à rappeler après consultation\", \"Demande urgente à vérifier\".",
      },
      {
        target: "agenda-panel",
        title: "Vérifiez les rendez-vous confirmés",
        body: "Vous voyez ici les rendez-vous du jour, y compris ceux pris directement par UWI avant même de connecter un agenda externe.",
        example: "Exemple concret : \"Mar 10h30 - Consultation générale - confirmé par UWI\" ou \"Jeu 16h00 - Suivi - agenda externe\".",
      },
    );
    return steps;
  }, [showSecurityTourStep]);

  const activeTourStep =
    tourStepIndex >= 0 && tourStepIndex < tourSteps.length ? tourSteps[tourStepIndex] : null;

  useEffect(() => {
    if (loading || !me || me?.dashboard_tour_completed || tourDismissed || tourStepIndex !== -1) return;
    setTourStepIndex(0);
  }, [loading, me, tourDismissed, tourStepIndex]);

  useEffect(() => {
    if (!activeTourStep || typeof window === "undefined") return undefined;
    const element = document.querySelector(`[data-tour="${activeTourStep.target}"]`);
    if (!element) {
      setTourRect(null);
      return undefined;
    }

    let timer = null;
    const measure = () => {
      const rect = element.getBoundingClientRect();
      setTourRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    };

    element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    timer = window.setTimeout(measure, 260);
    const onViewportChange = () => measure();
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    return () => {
      if (timer) window.clearTimeout(timer);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };
  }, [activeTourStep]);

  const completeTour = async () => {
    setTourDismissed(true);
    setTourStepIndex(-1);
    setTourRect(null);
    if (!me || me.dashboard_tour_completed || tourPersisting) return;
    setTourPersisting(true);
    try {
      await api.tenantPatchParams({ dashboard_tour_completed: true });
      setMe((prev) => (prev ? { ...prev, dashboard_tour_completed: true } : prev));
    } catch (_) {
      // Fail open: ne pas bloquer l'utilisateur si le flag ne se persiste pas.
    } finally {
      setTourPersisting(false);
    }
  };

  const nextTourStep = async () => {
    if (tourStepIndex >= tourSteps.length - 1) {
      await completeTour();
      return;
    }
    setTourStepIndex((prev) => prev + 1);
  };

  const restartTour = () => {
    setTourDismissed(false);
    setTourRect(null);
    setTourStepIndex(0);
  };

  const tourPopoverStyle = (() => {
    if (!tourRect || typeof window === "undefined") return null;
    const width = Math.min(380, window.innerWidth - 32);
    const estimatedHeight = 260;
    let top = tourRect.bottom + 18;
    let placement = "bottom";
    if (top + estimatedHeight > window.innerHeight - 16) {
      top = Math.max(16, tourRect.top - estimatedHeight - 18);
      placement = "top";
    }
    let left = tourRect.left;
    if (left + width > window.innerWidth - 16) {
      left = window.innerWidth - width - 16;
    }
    if (left < 16) left = 16;
    return { top, left, width, placement };
  })();

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      {activeTourStep && tourRect && tourPopoverStyle ? (
        <div style={S.tourOverlay} role="dialog" aria-modal="true" aria-label="Guide de première connexion">
          <div style={S.tourBackdrop} />
          <div
            style={{
              ...S.tourHighlight,
              top: Math.max(8, tourRect.top - 8),
              left: Math.max(8, tourRect.left - 8),
              width: Math.min(window.innerWidth - 16, tourRect.width + 16),
              height: tourRect.height + 16,
            }}
          />
          <div style={{ ...S.tourCard, ...tourPopoverStyle }}>
            <div
              style={{
                ...S.tourArrow,
                left: Math.max(28, Math.min((tourRect.left - tourPopoverStyle.left) + 36, tourPopoverStyle.width - 42)),
                ...(tourPopoverStyle.placement === "bottom"
                  ? { top: -10, borderBottom: "10px solid rgba(255,255,255,0.96)" }
                  : { bottom: -10, borderTop: "10px solid rgba(255,255,255,0.96)" }),
              }}
            />
            <div style={S.tourBadge}>
              Première connexion · {tourStepIndex + 1}/{tourSteps.length}
            </div>
            <div style={S.tourTitle}>{activeTourStep.title}</div>
            <div style={S.tourText}>{activeTourStep.body}</div>
            <div style={S.tourExampleCard}>
              <div style={S.tourExampleLabel}>Exemple concret</div>
              <div style={S.tourExampleText}>{activeTourStep.example}</div>
            </div>
            <div style={S.tourProgressRow}>
              {tourSteps.map((step, index) => (
                <span
                  key={step.target}
                  style={{
                    ...S.tourProgressDot,
                    ...(index === tourStepIndex ? S.tourProgressDotActive : null),
                  }}
                />
              ))}
            </div>
            <div style={S.tourActions}>
              <button type="button" onClick={completeTour} style={S.tourGhostButton}>
                {tourPersisting ? "Fermeture..." : "Passer"}
              </button>
              <button type="button" onClick={nextTourStep} style={S.tourPrimaryButton}>
                {tourStepIndex >= tourSteps.length - 1 ? "J'ai compris" : "Suivant"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="uwi-dashboard-wrap">
        <div className="uwi-header-row" style={S.header}>
          <div>
            <div style={S.eyebrow}>
              Cabinet · {me?.tenant_name || "Votre cabinet"}
            </div>
            <h1 style={S.title}>Tableau de bord</h1>
            <p style={S.subtitle}>
              {me?.tenant_name || "Votre cabinet"} · voyez immédiatement ce qui est prêt et ce qui demande une action
            </p>
          </div>

          <div style={S.headerRight}>
            <div style={S.headerChip}>{actionQueue.length} action{actionQueue.length > 1 ? "s" : ""} active{actionQueue.length > 1 ? "s" : ""}</div>
            <button type="button" onClick={restartTour} style={S.headerGhostButton}>
              Revoir le guide
            </button>
            <button type="button" onClick={() => navigate("/app/appels")} style={S.headerButton}>
              Ouvrir Appels
            </button>
          </div>
        </div>

        <section className="uwi-control-grid" style={S.controlGrid}>
          {headerCards.map((card) => (
            <div key={card.label} style={S.controlCard}>
              <div style={S.controlLabel}>{card.label}</div>
              <div style={S.controlValue}>{card.value}</div>
              <div style={S.controlHint}>{card.hint}</div>
            </div>
          ))}
        </section>

        <section style={S.assistantCard}>
          <div style={S.assistantLabel}>État opérationnel</div>

          <div className="uwi-assistant-row" style={S.assistantRow}>
            <div style={S.assistantLeft}>
              <div style={{ ...S.avatarRing, background: avatarTheme.ring }}>
                {assistantConfig?.img && !assistantImageFailed ? (
                  <img
                    src={assistantConfig.img}
                    alt={assistantConfig.prenom || assistantName}
                    style={S.avatarImg}
                    onError={() => setAssistantImageFailed(true)}
                  />
                ) : (
                  <div style={{ ...S.avatar, background: avatarTheme.bg }}>
                    <span style={S.avatarText}>{getInitial(assistantName)}</span>
                  </div>
                )}
                <div style={S.avatarStatus}>
                  <DotPulse size={8} />
                </div>
              </div>

              <div style={{ minWidth: 0, flex: 1 }}>
                <>
                  <div style={S.assistantName}>{assistantName}</div>
                  <div style={S.assistantMetaRow}>
                    <span style={S.assistantMetaItem}>
                      <span style={{ color: me?.assistant_live ? "#10b981" : "#f59e0b" }}>●</span>
                      {me?.assistant_live ? "Vapi actif" : "Assistant à finaliser"}
                    </span>
                    <span style={S.assistantMetaItem}>
                      📞 {me?.voice_number || "Numéro en attente"}
                    </span>
                    <span style={S.assistantMetaItem}>
                      📅 {agendaReady ? "Agenda prêt" : "Mode UWI actif"}
                    </span>
                  </div>
                </>
              </div>
            </div>

            <div style={S.assistantRight}>
              <div style={S.assistantRightLabel}>Actions à traiter</div>
              <div style={S.assistantRightValue}>{callsLoading ? <Skeleton width={36} height={30} radius={8} /> : actionQueue.length}</div>
            </div>
          </div>
        </section>

        {showPhoneBanner ? (
          <div style={S.banner}>⏳ Configuration en cours — Notre équipe active votre numéro sous 24h</div>
        ) : null}

        <Suspense fallback={<MainPanelsFallback />}>
          <AppDashboardMainPanels
            callsLoading={callsLoading}
            recentCallItems={recentCallItems}
            agendaLoading={agendaLoading}
            appointmentItems={appointmentItems}
            bookedAgendaCount={bookedAgendaSlots.length}
            agendaReady={agendaReady}
            externalConnected={Boolean(agenda?.external_connected)}
            externalAgendaItems={externalAgendaItems}
            onNavigate={navigate}
          />
        </Suspense>

        <section className="uwi-kpi-grid" style={S.kpiGrid}>
          {kpisLoading
            ? [1, 2, 3, 4].map((item) => (
                <div key={item} style={S.kpiCard}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <Skeleton width={54} height={54} radius={16} />
                    <Skeleton width={54} height={14} radius={8} />
                  </div>
                  <div style={{ marginTop: 24 }}>
                    <Skeleton width={80} height={38} radius={10} />
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <Skeleton width={140} height={16} radius={8} />
                  </div>
                </div>
              ))
            : stats.map((stat) => {
                const Icon = stat.icon;
                return (
                  <div key={stat.label} style={S.kpiCard}>
                    <div style={S.kpiTop}>
                      <div style={{ ...S.kpiIconBox, background: stat.iconBg }}>
                        <Icon size={24} strokeWidth={2} color={stat.iconColor} />
                      </div>
                      <div style={S.kpiChange}>
                        <ArrowUpRight size={14} strokeWidth={2.2} />
                        {stat.change}
                      </div>
                    </div>
                    <div style={S.kpiValue}>{stat.value}</div>
                    <div style={S.kpiLabel}>{stat.label}</div>
                  </div>
                );
              })}
        </section>

        <Suspense fallback={<WorkflowSectionFallback />}>
          <AppDashboardWorkflowSection
            callsLoading={callsLoading}
            actionQueueItems={actionQueueItems}
            onboardingProgress={onboardingProgress}
            onboardingCards={onboardingCards}
            quickLinks={quickLinks}
            onNavigate={navigate}
          />
        </Suspense>
      </div>
    </div>
  );
}

const S = {
  root: {
    minHeight: "100%",
    background: "#f5f6f8",
    fontFamily: "'Inter', 'DM Sans', sans-serif",
    color: NAVY,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 20,
    marginBottom: 28,
  },
  title: {
    margin: 0,
    fontSize: 18,
    lineHeight: 1,
    fontWeight: 800,
    color: NAVY,
  },
  eyebrow: {
    marginBottom: 8,
    fontSize: 11,
    lineHeight: 1,
    fontWeight: 800,
    color: "#0f766e",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  },
  subtitle: {
    marginTop: 6,
    fontSize: 12,
    color: "#6b7280",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 14,
  },
  headerChip: {
    display: "flex",
    alignItems: "center",
    padding: "8px 10px",
    borderRadius: 999,
    border: "1px solid #d1fae5",
    background: "#ecfdf5",
    color: "#047857",
    fontSize: 12,
    fontWeight: 700,
  },
  headerButton: {
    border: "1px solid #e5e7eb",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#111827",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  headerGhostButton: {
    border: "1px solid #dbe4ee",
    background: "#f8fafc",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#475569",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  controlGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 16,
    marginBottom: 18,
  },
  controlCard: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "14px 16px",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  controlLabel: {
    fontSize: 11,
    color: "#6b7280",
    marginBottom: 10,
    fontWeight: 700,
  },
  controlValue: {
    fontSize: 18,
    lineHeight: 1.1,
    fontWeight: 800,
    color: NAVY,
  },
  controlHint: {
    marginTop: 6,
    fontSize: 12,
    color: "#6b7280",
  },
  assistantCard: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "18px 22px",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  assistantLabel: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: "#64748b",
    textTransform: "uppercase",
    marginBottom: 14,
  },
  assistantRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 18,
  },
  assistantLeft: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    minWidth: 0,
    flex: 1,
  },
  avatarRing: {
    width: 56,
    height: 56,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    flexShrink: 0,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 6px 12px rgba(37,99,235,.12)",
  },
  avatarImg: {
    width: 48,
    height: 48,
    borderRadius: "50%",
    objectFit: "cover",
    display: "block",
    boxShadow: "0 6px 12px rgba(37,99,235,.12)",
  },
  avatarText: {
    color: "#fff",
    fontSize: 18,
    fontWeight: 800,
  },
  avatarStatus: {
    position: "absolute",
    right: 4,
    bottom: 4,
    width: 18,
    height: 18,
    borderRadius: "50%",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  assistantName: {
    fontSize: 18,
    fontWeight: 700,
    color: NAVY,
    lineHeight: 1,
  },
  assistantMetaRow: {
    marginTop: 6,
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
    fontSize: 12,
    color: "#6b7280",
  },
  assistantMetaItem: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  },
  assistantRight: {
    textAlign: "right",
    minWidth: 130,
    flexShrink: 0,
  },
  assistantRightLabel: {
    fontSize: 12,
    color: "#9ca3af",
    marginBottom: 6,
  },
  assistantRightValue: {
    fontSize: 18,
    lineHeight: 1,
    fontWeight: 700,
    color: NAVY,
  },
  banner: {
    marginTop: 16,
    padding: "12px 14px",
    borderRadius: 12,
    border: "1px solid #fed7aa",
    background: "#fff7ed",
    color: "#9a3412",
    fontSize: 12,
    fontWeight: 600,
  },
  activationGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.35fr) minmax(320px, .95fr)",
    gap: 16,
    marginTop: 18,
  },
  activationPanel: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  actionsPanel: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  progressWrap: {
    minWidth: 140,
  },
  progressLabel: {
    fontSize: 12,
    color: "#0f766e",
    fontWeight: 700,
    marginBottom: 6,
    textAlign: "right",
  },
  progressTrack: {
    height: 8,
    borderRadius: 999,
    background: "#ecfeff",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    background: "linear-gradient(90deg, #14c8b8, #34d399)",
  },
  activationList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    padding: 18,
  },
  activationItem: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "14px 16px",
    background: "#fff",
  },
  activationIcon: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: "#f0fdfa",
    color: "#0f766e",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 800,
    flexShrink: 0,
  },
  activationTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  activationText: {
    marginTop: 4,
    fontSize: 12,
    color: "#6b7280",
    lineHeight: 1.5,
  },
  activationButton: {
    border: "none",
    background: "linear-gradient(135deg, #14c8b8, #0ea899)",
    color: "#fff",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  activationButtonGhost: {
    border: "1px solid #d1fae5",
    background: "#ecfdf5",
    color: "#047857",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  activationWaiting: {
    fontSize: 12,
    fontWeight: 700,
    color: "#9a3412",
    whiteSpace: "nowrap",
  },
  actionQueueList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    padding: 18,
  },
  actionQueueCard: {
    display: "flex",
    gap: 12,
    alignItems: "center",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "14px 16px",
    background: "#fff",
  },
  actionQueueTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  actionQueueBadge: {
    display: "inline-flex",
    alignItems: "center",
    border: "1px solid",
    borderRadius: 999,
    padding: "4px 8px",
    fontSize: 10,
    fontWeight: 700,
  },
  actionQueueTime: {
    fontSize: 11,
    color: "#6b7280",
    fontWeight: 700,
  },
  actionQueueTitle: {
    marginTop: 8,
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  actionQueueText: {
    marginTop: 5,
    fontSize: 12,
    lineHeight: 1.5,
    color: "#4b5563",
  },
  actionQueueButton: {
    border: "1px solid #e5e7eb",
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  quickLinks: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 14,
    marginTop: 18,
  },
  quickLinkCard: {
    border: "1px solid #e5e7eb",
    background: "#fff",
    borderRadius: 14,
    padding: "14px 16px",
    textAlign: "left",
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  quickLinkTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: NAVY,
  },
  quickLinkText: {
    marginTop: 6,
    fontSize: 12,
    color: "#6b7280",
    lineHeight: 1.5,
  },
  tourOverlay: {
    position: "fixed",
    inset: 0,
    zIndex: 120,
    pointerEvents: "auto",
  },
  tourBackdrop: {
    position: "absolute",
    inset: 0,
    background: "rgba(15, 23, 42, 0.14)",
    backdropFilter: "blur(3px)",
  },
  tourHighlight: {
    position: "fixed",
    borderRadius: 22,
    border: "1px solid rgba(20, 200, 184, 0.8)",
    background: "rgba(255,255,255,0.04)",
    boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.10), 0 0 0 6px rgba(20, 200, 184, 0.08), 0 18px 40px rgba(20, 200, 184, 0.12)",
    pointerEvents: "none",
    transition: "all .24s cubic-bezier(.2,.8,.2,1)",
  },
  tourCard: {
    position: "fixed",
    background: "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.98) 100%)",
    border: "1px solid rgba(209, 250, 229, 0.9)",
    borderRadius: 22,
    padding: 20,
    boxShadow: "0 24px 70px rgba(15, 23, 42, 0.20), 0 6px 24px rgba(20, 200, 184, 0.08)",
    pointerEvents: "auto",
    overflow: "visible",
    animation: "uwi-tour-in .28s cubic-bezier(.2,.8,.2,1)",
  },
  tourArrow: {
    position: "absolute",
    width: 0,
    height: 0,
    borderLeft: "10px solid transparent",
    borderRight: "10px solid transparent",
  },
  tourBadge: {
    display: "inline-flex",
    alignItems: "center",
    padding: "6px 11px",
    borderRadius: 999,
    background: "linear-gradient(135deg, #ecfdf5, #f0fdfa)",
    color: "#047857",
    fontSize: 11,
    fontWeight: 800,
    marginBottom: 12,
    boxShadow: "inset 0 0 0 1px rgba(16, 185, 129, 0.08)",
  },
  tourTitle: {
    fontSize: 19,
    fontWeight: 800,
    color: NAVY,
    lineHeight: 1.2,
    letterSpacing: "-0.02em",
  },
  tourText: {
    marginTop: 9,
    fontSize: 13,
    lineHeight: 1.6,
    color: "#334155",
  },
  tourExampleCard: {
    marginTop: 15,
    borderRadius: 16,
    border: "1px solid rgba(191, 219, 254, 0.9)",
    background: "linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%)",
    padding: 14,
  },
  tourExampleLabel: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    color: "#0f766e",
    marginBottom: 8,
  },
  tourExampleText: {
    fontSize: 13,
    lineHeight: 1.6,
    color: "#334155",
  },
  tourProgressRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginTop: 14,
  },
  tourProgressDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#cbd5e1",
    transition: "all .18s ease",
  },
  tourProgressDotActive: {
    width: 22,
    borderRadius: 999,
    background: "linear-gradient(90deg, #14c8b8, #0ea899)",
  },
  tourActions: {
    marginTop: 16,
    display: "flex",
    justifyContent: "space-between",
    gap: 10,
  },
  tourGhostButton: {
    border: "1px solid #e5e7eb",
    background: "rgba(255,255,255,0.9)",
    color: "#475569",
    borderRadius: 12,
    padding: "10px 14px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  tourPrimaryButton: {
    border: "none",
    background: "linear-gradient(135deg, #14c8b8, #0ea899)",
    color: "#fff",
    borderRadius: 13,
    padding: "10px 14px",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
    marginLeft: "auto",
    boxShadow: "0 10px 24px rgba(20, 200, 184, 0.22)",
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 16,
    marginTop: 18,
  },
  kpiCard: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "14px 16px",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  kpiTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  kpiIconBox: {
    width: 34,
    height: 34,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  kpiChange: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 11,
    color: "#10b981",
    fontWeight: 600,
  },
  kpiValue: {
    fontSize: 18,
    lineHeight: 1,
    fontWeight: 700,
    color: NAVY,
  },
  kpiLabel: {
    marginTop: 8,
    fontSize: 12,
    color: "#6b7280",
  },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  * { box-sizing: border-box; }

  @keyframes uwi-ping {
    0% { transform: scale(1); opacity: .4; }
    80%, 100% { transform: scale(2.4); opacity: 0; }
  }

  @keyframes uwi-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @keyframes uwi-tour-in {
    0% { opacity: 0; transform: translateY(8px) scale(.985); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
  }

  .uwi-dashboard-wrap {
    max-width: 1280px;
    margin: 0 auto;
    padding: 28px 28px 36px;
  }

  .uwi-call-row {
    transition: background .16s ease;
  }

  .uwi-call-row:hover {
    background: #fafcfd;
  }

  @media (max-width: 1160px) {
    .uwi-control-grid,
    .uwi-activation-grid,
    .uwi-quick-links,
    .uwi-main-grid {
      grid-template-columns: 1fr !important;
    }

    .uwi-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
  }

  @media (max-width: 760px) {
    .uwi-dashboard-wrap {
      padding: 18px 14px 22px;
    }

    .uwi-header-row,
    .uwi-assistant-row {
      flex-direction: column;
      align-items: flex-start !important;
    }

    .uwi-search {
      width: 100% !important;
    }

    .uwi-kpi-grid {
      grid-template-columns: 1fr !important;
    }

    .uwi-control-grid {
      grid-template-columns: 1fr !important;
    }
  }
`;
