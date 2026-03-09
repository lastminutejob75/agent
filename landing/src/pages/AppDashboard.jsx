import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Calendar,
  CheckCircle2,
  Phone,
  PhoneCall,
  Plus,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api.js";
import ASSISTANTS from "../assistants.config.js";

const TEAL_DARK = "#0ea899";
const NAVY = "#111827";

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
  return call.agent_name || fallbackAgent || "UWI";
}

function getInitials(name) {
  return String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "RDV";
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

export default function AppDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState(null);
  const [calls, setCalls] = useState([]);
  const [agenda, setAgenda] = useState(null);
  const [me, setMe] = useState(null);
  const [assistantImageFailed, setAssistantImageFailed] = useState(false);

  useEffect(() => {
    Promise.all([
      api.tenantKpis(1).catch(() => null),
      api.tenantGetCalls("?limit=20&days=1").catch(() => ({ calls: [] })),
      api.tenantGetAgenda().catch(() => null),
      api.tenantMe().catch(() => null),
    ]).then(([k, c, a, m]) => {
      setKpis(k);
      setCalls(c?.calls || []);
      setAgenda(a);
      setMe(m);
      setLoading(false);
    });
  }, []);

  const assistantName = me?.assistant_name || "Emma";
  const avatarTheme = getAvatarTheme(assistantName);
  const showPhoneBanner = !loading && !me?.voice_number;
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
        value: `${Math.round((kpis?.pickup_rate ?? 0) * 100)}%`,
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

  const agendaItems = safeAgendaSlots
    .filter((slot) => slot.patient)
    .slice(0, 3)
    .map((slot, index) => ({
      ...slot,
      key: slot.event_id || `${slot.hour || "slot"}-${index}`,
      displayTime: formatAgendaTime(slot.hour),
      initials: getInitials(slot.patient),
      badge: getAgendaBadge(slot),
    }));

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

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      <div className="uwi-dashboard-wrap">
        <div className="uwi-header-row" style={S.header}>
          <div>
            <h1 style={S.title}>Tableau de bord</h1>
            <p style={S.subtitle}>Voyez immédiatement ce qui est prêt et ce qui demande une action</p>
          </div>

          <div style={S.headerRight}>
            <div style={S.headerChip}>{actionQueue.length} action{actionQueue.length > 1 ? "s" : ""} active{actionQueue.length > 1 ? "s" : ""}</div>
            <button type="button" onClick={() => navigate("/app/appels")} style={S.headerButton}>
              Ouvrir Appels
            </button>
          </div>
        </div>

        <section className="uwi-control-grid" style={S.controlGrid}>
          {headerCards.map((card) => (
            <div key={card.label} style={S.controlCard}>
              <div style={S.controlLabel}>{card.label}</div>
              <div style={S.controlValue}>{loading ? <Skeleton width={120} height={24} radius={10} /> : card.value}</div>
              <div style={S.controlHint}>{loading ? <Skeleton width={90} height={12} radius={8} /> : card.hint}</div>
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
                {loading ? (
                  <>
                    <Skeleton width={96} height={28} radius={10} />
                    <div style={{ marginTop: 8 }}>
                      <Skeleton width={180} height={16} radius={8} />
                    </div>
                  </>
                ) : (
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
                )}
              </div>
            </div>

            <div style={S.assistantRight}>
              <div style={S.assistantRightLabel}>Actions à traiter</div>
              <div style={S.assistantRightValue}>{loading ? <Skeleton width={36} height={30} radius={8} /> : actionQueue.length}</div>
            </div>
          </div>
        </section>

        {showPhoneBanner ? (
          <div style={S.banner}>⏳ Configuration en cours — Notre équipe active votre numéro sous 24h</div>
        ) : null}

        <section className="uwi-main-grid" style={S.mainGrid}>
          <div style={S.panel}>
            <div style={S.panelHeader}>
              <div>
                <div style={S.panelTitle}>Appels récents</div>
                <div style={S.panelSubtitle}>Activité des dernières heures</div>
              </div>
              <button type="button" onClick={() => navigate("/app/appels")} style={S.linkButton}>
                <span>Voir tout</span>
                <ArrowUpRight size={16} strokeWidth={2.2} />
              </button>
            </div>

            <div style={S.callList}>
              {loading ? (
                [1, 2, 3, 4].map((item) => <Skeleton key={item} height={92} radius={0} />)
              ) : safeCalls.length === 0 ? (
                <div style={S.emptyState}>
                  <div style={S.emptyTitle}>Aucun appel aujourd&apos;hui</div>
                  <div style={S.emptyText}>Votre journal d&apos;appels apparaîtra ici.</div>
                </div>
              ) : (
                safeCalls.slice(0, 4).map((call) => {
                  const status = STATUS_CFG[call.status] || STATUS_CFG.ABANDONED;
                  const icon = callIconTheme(call.status);
                  return (
                    <button key={call.id} type="button" onClick={() => navigate("/app/appels")} style={S.callRow} className="uwi-call-row">
                      <div style={{ ...S.callIcon, background: icon.bg }}>
                        <PhoneCall size={22} strokeWidth={2} color={icon.color} />
                      </div>

                      <div style={{ minWidth: 0, flex: 1, textAlign: "left" }}>
                        <div style={S.callName}>{call.patient_name || "Patient inconnu"}</div>
                        <div style={S.callPhone}>{getPhoneSummary(call, assistantName)}</div>
                        <div style={S.callOutcome}>{call.summary || "Aucun résumé disponible."}</div>
                        {call.reason_label ? (
                          <div style={S.callReasonRow}>
                            <span
                              style={{
                                ...S.callReasonBadge,
                                background: getReasonBadge(call).bg,
                                color: getReasonBadge(call).text,
                                borderColor: getReasonBadge(call).border,
                              }}
                            >
                              {getReasonBadge(call).label}
                            </span>
                            <span style={S.callReasonText}>{call.reason_label}</span>
                          </div>
                        ) : null}
                      </div>

                      <div style={S.callMeta}>
                        <div style={S.callTime}>{call.time || "--:--"}</div>
                        <span
                          style={{
                            ...S.statusBadge,
                            background: status.chipBg,
                            color: status.chipText,
                            borderColor: status.chipBorder,
                          }}
                        >
                          {status.label}
                        </span>
                        <div style={S.callDuration}>{call.duration || "—"}</div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div style={S.panel}>
            <div style={S.panelHeader}>
              <div>
                <div style={S.panelTitle}>Agenda</div>
                <div style={S.panelSubtitle}>
                  {agenda?.external_connected ? "Rendez-vous du jour" : "Rendez-vous UWI du jour"}
                </div>
              </div>
              <div style={{ color: TEAL_DARK, display: "flex", alignItems: "center" }}>
                <TrendingUp size={18} strokeWidth={2} />
              </div>
            </div>

            <div style={S.agendaList}>
              {loading ? (
                [1, 2, 3].map((item) => <Skeleton key={item} height={96} radius={16} />)
              ) : agendaItems.length > 0 ? (
                <>
                  {!agendaReady ? (
                    <div style={S.agendaNotice}>
                      <div>
                        <div style={S.agendaNoticeTitle}>Agenda médecin non connecté</div>
                        <div style={S.agendaNoticeText}>
                          Les rendez-vous ci-dessous viennent déjà du calendrier UWI. Vous pouvez connecter Google ensuite.
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {agendaItems.map((item) => (
                    <div key={item.key} style={S.agendaAppointmentCard}>
                      <div style={S.agendaAvatar}>{item.initials}</div>

                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={S.agendaName}>{item.patient}</div>
                        <div style={S.agendaType}>{item.type || "Rendez-vous"}</div>
                        <div style={S.agendaMetaRow}>
                          <span>🕘 {item.displayTime}</span>
                          <span>{item.source === "UWI" ? "Téléphone" : "Agenda externe"}</span>
                        </div>
                      </div>

                      <div style={S.agendaBadges}>
                        <span
                          style={{
                            ...S.agendaStatusBadge,
                            background: item.badge.bg,
                            color: item.badge.text,
                            borderColor: item.badge.border,
                          }}
                        >
                          {item.badge.label}
                        </span>
                        <span
                          style={{
                            ...S.agendaSourceBadge,
                            background: item.source === "UWI" ? "#eff6ff" : "#f1f5f9",
                            color: item.source === "UWI" ? "#1d4ed8" : "#475569",
                            borderColor: item.source === "UWI" ? "#bfdbfe" : "#cbd5e1",
                          }}
                        >
                          {item.source === "UWI" ? "UWI" : "Externe"}
                        </span>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <div style={S.emptyState}>
                  <div style={S.emptyTitle}>Aucun rendez-vous aujourd&apos;hui</div>
                  <div style={S.emptyText}>
                    {agendaReady
                      ? "Votre planning apparaîtra ici au fil des réservations."
                      : "Aucun RDV pour le moment. Vous pouvez déjà connecter votre agenda ou attendre les premières réservations UWI."}
                  </div>
                </div>
              )}
            </div>

            <button type="button" onClick={() => navigate("/app/agenda")} style={S.planButton}>
              <Plus size={16} strokeWidth={2.2} />
              <span>Ouvrir l&apos;agenda</span>
            </button>
          </div>
        </section>

        <section className="uwi-kpi-grid" style={S.kpiGrid}>
          {loading
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

        <section className="uwi-activation-grid" style={S.activationGrid}>
          <div style={S.actionsPanel}>
            <div style={S.panelHeader}>
              <div>
                <div style={S.panelTitle}>À traiter maintenant</div>
                <div style={S.panelSubtitle}>La file de travail prioritaire du cabinet</div>
              </div>
              <button type="button" onClick={() => navigate("/app/appels")} style={S.linkButton}>
                <span>Ouvrir Appels</span>
                <ArrowUpRight size={16} strokeWidth={2.2} />
              </button>
            </div>

            <div style={S.actionQueueList}>
              {loading ? (
                [1, 2, 3].map((item) => <Skeleton key={item} height={90} radius={14} />)
              ) : actionQueue.length === 0 ? (
                <div style={S.emptyState}>
                  <div style={S.emptyTitle}>Aucune action urgente</div>
                  <div style={S.emptyText}>Les demandes prioritaires apparaîtront ici dès qu&apos;elles nécessiteront un suivi.</div>
                </div>
              ) : (
                actionQueue.map((call) => {
                  const badge = getReasonBadge(call);
                  const ctaLabel = getActionCta(call);
                  return (
                    <div key={call.call_id || call.id} style={S.actionQueueCard}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={S.actionQueueTop}>
                          <span
                            style={{
                              ...S.actionQueueBadge,
                              background: badge.bg,
                              color: badge.text,
                              borderColor: badge.border,
                            }}
                          >
                            {badge.label}
                          </span>
                          <span style={S.actionQueueTime}>{call.time || "—"}</span>
                        </div>
                        <div style={S.actionQueueTitle}>{call.patient_name || "Patient"}</div>
                        <div style={S.actionQueueText}>{call.reason_label || call.summary || "Suivi patient"}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => navigate(call?.contextual_action?.kind === "open_agenda" ? "/app/agenda" : "/app/appels")}
                        style={S.actionQueueButton}
                      >
                        {ctaLabel}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div style={S.activationPanel}>
            <div style={S.panelHeader}>
              <div>
                <div style={S.panelTitle}>Activation du cabinet</div>
                <div style={S.panelSubtitle}>Les prochains réglages qui débloquent l’autonomie du standard</div>
              </div>
              <div style={S.progressWrap}>
                <div style={S.progressLabel}>{onboardingProgress}% prêt</div>
                <div style={S.progressTrack}>
                  <div style={{ ...S.progressFill, width: `${onboardingProgress}%` }} />
                </div>
              </div>
            </div>

            <div style={S.activationList}>
              {onboardingCards.map((item) => (
                <div key={item.key} style={{ ...S.activationItem, borderColor: item.done ? "#bbf7d0" : "#e5e7eb" }}>
                  <div style={S.activationIcon}>{item.done ? "✓" : "•"}</div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ ...S.activationTitle, color: item.done ? "#047857" : NAVY }}>{item.title}</div>
                    <div style={S.activationText}>{item.text}</div>
                  </div>
                  {item.href ? (
                    <button type="button" onClick={() => navigate(item.href)} style={item.done ? S.activationButtonGhost : S.activationButton}>
                      {item.cta}
                    </button>
                  ) : (
                    <div style={S.activationWaiting}>{item.done ? "OK" : "UWI"}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="uwi-quick-links" style={S.quickLinks}>
          {quickLinks.map((item) => (
            <button key={item.href} type="button" onClick={() => navigate(item.href)} style={S.quickLinkCard}>
              <div style={S.quickLinkTitle}>{item.label}</div>
              <div style={S.quickLinkText}>{item.sub}</div>
            </button>
          ))}
        </section>
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
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 2fr) minmax(320px, 1fr)",
    gap: 16,
    marginTop: 18,
  },
  panel: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  panelHeader: {
    padding: "18px 18px 14px",
    borderBottom: "1px solid #e5e7eb",
    background: "#fafafa",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  panelTitle: {
    fontSize: 15,
    lineHeight: 1.1,
    fontWeight: 700,
    color: NAVY,
  },
  panelSubtitle: {
    marginTop: 4,
    fontSize: 12,
    color: "#6b7280",
  },
  linkButton: {
    border: "1px solid #e5e7eb",
    background: "#fff",
    color: "#475569",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    borderRadius: 10,
    padding: "8px 10px",
  },
  callList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    padding: 18,
  },
  callRow: {
    width: "100%",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    background: "#fff",
    padding: "14px 16px",
    display: "flex",
    alignItems: "flex-start",
    gap: 14,
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "0 1px 4px rgba(15,23,42,.02)",
  },
  callIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  callName: {
    fontSize: 15,
    fontWeight: 700,
    color: NAVY,
  },
  callPhone: {
    marginTop: 6,
    fontSize: 12,
    color: "#4b5563",
  },
  callOutcome: {
    marginTop: 5,
    fontSize: 11,
    color: "#4b5563",
    lineHeight: 1.5,
  },
  callReasonRow: {
    marginTop: 8,
    display: "flex",
    gap: 8,
    alignItems: "center",
    flexWrap: "wrap",
  },
  callReasonBadge: {
    display: "inline-flex",
    alignItems: "center",
    border: "1px solid",
    borderRadius: 999,
    padding: "4px 8px",
    fontSize: 10,
    fontWeight: 700,
  },
  callReasonText: {
    fontSize: 11,
    color: "#475569",
    lineHeight: 1.5,
  },
  callMeta: {
    textAlign: "right",
    minWidth: 84,
    flexShrink: 0,
  },
  callTime: {
    fontSize: 12,
    color: "#374151",
    fontWeight: 600,
  },
  statusBadge: {
    display: "inline-flex",
    marginTop: 6,
    padding: "5px 10px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 10,
    fontWeight: 700,
  },
  callDuration: {
    marginTop: 8,
    fontSize: 11,
    color: NAVY,
    fontWeight: 600,
  },
  agendaList: {
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  agendaNotice: {
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    background: "#f8fafc",
    padding: "12px 14px",
  },
  agendaNoticeTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: NAVY,
  },
  agendaNoticeText: {
    marginTop: 4,
    fontSize: 12,
    lineHeight: 1.5,
    color: "#0f766e",
  },
  agendaAppointmentCard: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    background: "#ffffff",
    padding: "14px 16px",
    boxShadow: "0 1px 4px rgba(15,23,42,.02)",
  },
  agendaAvatar: {
    width: 40,
    height: 40,
    borderRadius: 10,
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 14,
    fontWeight: 800,
    flexShrink: 0,
    boxShadow: "0 6px 12px rgba(37,99,235,.12)",
  },
  agendaName: {
    fontSize: 15,
    fontWeight: 700,
    color: NAVY,
  },
  agendaType: {
    marginTop: 5,
    fontSize: 12,
    color: "#6b7280",
  },
  agendaMetaRow: {
    marginTop: 8,
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
    fontSize: 11,
    color: "#6b7280",
  },
  agendaBadges: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    gap: 8,
    flexShrink: 0,
  },
  agendaStatusBadge: {
    display: "inline-flex",
    padding: "5px 10px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 10,
    fontWeight: 700,
  },
  agendaSourceBadge: {
    display: "inline-flex",
    padding: "5px 9px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 10,
    fontWeight: 700,
  },
  planButton: {
    margin: "0 18px 18px",
    height: 40,
    borderRadius: 10,
    border: "1px solid #e5e7eb",
    background: "#fff",
    color: "#4b5563",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    fontFamily: "inherit",
  },
  emptyState: {
    padding: "28px 18px 20px",
    textAlign: "center",
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: NAVY,
  },
  emptyText: {
    marginTop: 8,
    fontSize: 14,
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
