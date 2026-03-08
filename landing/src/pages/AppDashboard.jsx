import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const TEAL = "#00d4a0";
const TEALX = "#00b389";
const NAVY = "#0d1b2e";

const STATUS_CFG = {
  TRANSFERRED: { color: "#dc2626", bg: "#fef2f2", border: "#fecaca", label: "Urgence", icon: "⚠" },
  CONFIRMED: { color: "#00b389", bg: "#f0fdf9", border: "#99f0da", label: "Confirmé", icon: "✓" },
  ABANDONED: { color: "#94a3b8", bg: "#f8fafc", border: "#e2e8f0", label: "Abandonné", icon: "–" },
  FAQ: { color: "#d97706", bg: "#fffbeb", border: "#fde68a", label: "Info", icon: "◎" },
};

const AVATAR_GRADIENTS = {
  sophie: "linear-gradient(135deg, #00d4a0, #3b82f6)",
  camille: "linear-gradient(135deg, #f59e0b, #ec4899)",
  thomas: "linear-gradient(135deg, #2563eb, #6366f1)",
  emma: "linear-gradient(135deg, #14b8a6, #0ea5e9)",
  clara: "linear-gradient(135deg, #22c55e, #14b8a6)",
  laura: "linear-gradient(135deg, #8b5cf6, #ec4899)",
  julie: "linear-gradient(135deg, #f97316, #ef4444)",
  hugo: "linear-gradient(135deg, #3b82f6, #06b6d4)",
};

const KPI_CARDS = [
  { key: "calls", label: "Appels aujourd'hui", icon: "📞", accent: "#3b82f6", bg: "#eff6ff" },
  { key: "bookings", label: "RDV confirmés", icon: "📅", accent: TEALX, bg: "#ecfdf5" },
  { key: "pickup_rate", label: "Taux décroché", icon: "📈", accent: "#14b8a6", bg: "#f0fdfa" },
  { key: "minutes_month", label: "Min ce mois", icon: "⏱️", accent: "#8b5cf6", bg: "#f5f3ff" },
];

const SHORTCUTS = [
  { label: "Horaires", href: "/app/horaires", icon: "⏰", color: TEAL },
  { label: "FAQ", href: "/app/faq", icon: "💬", color: "#f59e0b" },
  { label: "Abonnement", href: "/app/facturation", icon: "💳", color: "#8b5cf6" },
  { label: "Paramètres", href: "/app/settings", icon: "⚙️", color: "#64748b" },
];

function Pulse({ color = TEAL, size = 8 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, opacity: 0.3, animation: "uwi-ping 1.8s ease-out infinite" }} />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: color, display: "block" }} />
    </span>
  );
}

function Skeleton({ w = "100%", h = 14, radius = 8 }) {
  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: radius,
        background: "linear-gradient(90deg,#eef2f7 25%,#e5ebf3 50%,#eef2f7 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-shimmer 1.4s infinite",
      }}
    />
  );
}

function getAssistantGradient(name) {
  const key = String(name || "").trim().toLowerCase();
  return AVATAR_GRADIENTS[key] || "linear-gradient(135deg, #00d4a0, #0d1b2e)";
}

function getAssistantInitial(name) {
  const clean = String(name || "U").trim();
  return clean ? clean.charAt(0).toUpperCase() : "U";
}

function formatPlanLabel(planKey) {
  const clean = String(planKey || "starter").replace(/[_-]+/g, " ");
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export default function AppDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState(null);
  const [calls, setCalls] = useState([]);
  const [agenda, setAgenda] = useState(null);
  const [me, setMe] = useState(null);

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

  const dateStr = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const assistantName = me?.assistant_name || "Sophie";
  const callsCount = kpis?.current?.calls ?? 0;
  const bookingCount = kpis?.current?.bookings ?? 0;
  const pickupRate = `${Math.round((kpis?.pickup_rate ?? 0) * 100)}%`;
  const monthMinutes = kpis?.minutes_month ?? 0;
  const showPhoneBanner = !loading && !me?.voice_number;
  const agendaReady = !!me?.onboarding_steps?.calendar_ready;

  const stats = [
    { ...KPI_CARDS[0], value: callsCount },
    { ...KPI_CARDS[1], value: bookingCount },
    { ...KPI_CARDS[2], value: pickupRate },
    { ...KPI_CARDS[3], value: monthMinutes },
  ];

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      <div className="uwi-dashboard-shell">
        <section style={S.heroCard}>
          <div className="uwi-hero-grid" style={S.heroGrid}>
            <div style={S.assistantBlock}>
              <div style={{ ...S.avatarWrap, background: getAssistantGradient(assistantName) }}>
                <span style={S.avatarLetter}>{getAssistantInitial(assistantName)}</span>
                <div style={S.avatarOnline}>
                  <Pulse color="#22c55e" size={7} />
                </div>
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                {loading ? (
                  <>
                    <Skeleton w={150} h={22} />
                    <div style={{ marginTop: 8 }}>
                      <Skeleton w={190} h={14} />
                    </div>
                    <div style={{ marginTop: 10 }}>
                      <Skeleton w={220} h={14} />
                    </div>
                  </>
                ) : (
                  <>
                    <div style={S.assistantTopLine}>
                      <div style={S.assistantName}>{assistantName}</div>
                      <span style={S.liveBadge}>
                        <Pulse color="#22c55e" size={7} />
                        En ligne
                      </span>
                    </div>
                    <div style={S.assistantMeta}>
                      Assistante vocale UWI · {formatPlanLabel(me?.plan_key)}
                    </div>
                    <div style={S.phoneLine}>
                      <span style={{ color: "#64748b" }}>Numéro vocal :</span>{" "}
                      <strong style={{ color: me?.voice_number ? NAVY : "#d97706", fontFamily: "monospace" }}>
                        {me?.voice_number || "Configuration en cours"}
                      </strong>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div style={S.heroMetrics}>
              {loading ? (
                <>
                  <Skeleton w={80} h={12} />
                  <div style={{ marginTop: 6 }}>
                    <Skeleton w={56} h={32} />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Skeleton w={120} h={12} />
                  </div>
                </>
              ) : (
                <>
                  <div style={S.metricLabel}>Appels du jour</div>
                  <div style={S.metricValue}>{callsCount}</div>
                  <div style={S.metricSub}>
                    Cabinet {me?.tenant_name || "UWI"} · {dateStr}
                  </div>
                </>
              )}
            </div>
          </div>
        </section>

        {showPhoneBanner && (
          <div style={S.pendingBanner}>
            <span style={{ fontSize: 18 }}>⏳</span>
            <div>
              <div style={S.pendingTitle}>Configuration en cours</div>
              <div style={S.pendingText}>
                Notre équipe active votre numéro sous 24h.
              </div>
            </div>
          </div>
        )}

        <section className="uwi-kpi-grid" style={S.kpiGrid}>
          {loading
            ? [1, 2, 3, 4].map((item) => (
                <div key={item} style={S.kpiCard}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Skeleton w={40} h={40} radius={12} />
                    <Skeleton w={28} h={12} />
                  </div>
                  <div style={{ marginTop: 18 }}>
                    <Skeleton w={80} h={28} />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Skeleton w={110} h={12} />
                  </div>
                </div>
              ))
            : stats.map((stat) => (
                <div key={stat.key} style={S.kpiCard}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
                    <div style={{ ...S.kpiIcon, background: stat.bg, color: stat.accent }}>{stat.icon}</div>
                  </div>
                  <div style={{ fontSize: 30, fontWeight: 800, color: NAVY, lineHeight: 1 }}>{stat.value}</div>
                  <div style={{ fontSize: 13, color: "#64748b", marginTop: 8 }}>{stat.label}</div>
                </div>
              ))}
        </section>

        <section className="uwi-main-grid" style={S.mainGrid}>
          <div style={S.mainCard}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>Aujourd&apos;hui</div>
                <div style={S.cardTitle}>Appels récents</div>
              </div>
              <button type="button" onClick={() => navigate("/app/appels")} style={S.linkBtn}>
                Voir tous →
              </button>
            </div>

            <div style={S.cardBodyScrollable}>
              {loading ? (
                <div style={{ display: "grid", gap: 12 }}>
                  {[1, 2, 3, 4].map((item) => (
                    <Skeleton key={item} h={88} radius={16} />
                  ))}
                </div>
              ) : calls.length === 0 ? (
                <div style={S.emptyState}>
                  <div style={S.emptyIcon}>📵</div>
                  <div style={S.emptyTitle}>Aucun appel aujourd&apos;hui</div>
                  <div style={S.emptyText}>Votre assistant est prêt à recevoir les prochains appels.</div>
                </div>
              ) : (
                <div style={{ display: "grid", gap: 12 }}>
                  {calls.map((call) => {
                    const status = STATUS_CFG[call.status] || STATUS_CFG.ABANDONED;
                    return (
                      <button
                        key={call.id}
                        type="button"
                        onClick={() => navigate("/app/appels")}
                        className="uwi-dashboard-row"
                        style={{ ...S.callRow, borderLeft: `4px solid ${status.color}` }}
                      >
                        <div style={S.callTimeBlock}>
                          <div style={S.callTime}>{call.time || "--:--"}</div>
                          <div style={S.callDuration}>{call.duration || "—"}</div>
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={S.callTop}>
                            <div style={S.callName}>{call.patient_name || "Patient inconnu"}</div>
                            <span style={{ ...S.agentChip, color: TEALX }}>{call.agent_name || assistantName}</span>
                          </div>
                          <div style={S.callSummary}>{call.summary || "Aucun résumé disponible."}</div>
                        </div>

                        <span style={{ ...S.statusBadge, color: status.color, background: status.bg, borderColor: status.border }}>
                          {status.icon} {status.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div style={S.mainCard}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>Planning</div>
                <div style={S.cardTitle}>Agenda</div>
              </div>
              <button type="button" onClick={() => navigate("/app/agenda")} style={S.linkBtn}>
                Ouvrir l&apos;agenda →
              </button>
            </div>

            {loading ? (
              <div style={{ display: "grid", gap: 12 }}>
                <Skeleton h={72} radius={16} />
                {[1, 2, 3, 4].map((item) => (
                  <Skeleton key={item} h={58} radius={14} />
                ))}
              </div>
            ) : !agendaReady ? (
              <div style={S.emptyState}>
                <div style={S.emptyIcon}>📅</div>
                <div style={S.emptyTitle}>Agenda non connecté</div>
                <div style={S.emptyText}>Connectez votre agenda pour voir les rendez-vous du jour.</div>
                <button type="button" onClick={() => navigate("/app/agenda")} style={{ ...S.primaryBtn, marginTop: 14 }}>
                  Connecter l&apos;agenda
                </button>
              </div>
            ) : !agenda?.slots?.length ? (
              <div style={S.emptyState}>
                <div style={S.emptyIcon}>🗓️</div>
                <div style={S.emptyTitle}>Aucun rendez-vous aujourd&apos;hui</div>
                <div style={S.emptyText}>Votre timeline sera affichée ici dès qu&apos;un créneau sera planifié.</div>
              </div>
            ) : (
              <>
                <div style={S.agendaSummary}>
                  {[
                    { label: "Total", value: agenda.total ?? 0, color: NAVY },
                    { label: "Passés", value: agenda.done ?? 0, color: TEALX },
                    { label: "À venir", value: agenda.remaining ?? 0, color: "#3b82f6" },
                  ].map((item) => (
                    <div key={item.label} style={S.agendaStat}>
                      <div style={{ fontSize: 24, fontWeight: 800, color: item.color, lineHeight: 1 }}>{item.value}</div>
                      <div style={{ fontSize: 11, color: "#64748b", marginTop: 6 }}>{item.label}</div>
                    </div>
                  ))}
                </div>

                <div style={S.timeline}>
                  {agenda.slots.map((slot, index) => {
                    const hasPatient = !!slot.patient;
                    return (
                      <div key={`${slot.hour}_${index}`} style={S.timelineRow}>
                        <div style={{ ...S.timelineHour, color: slot.current ? TEALX : "#64748b" }}>{slot.hour}</div>
                        <div style={S.timelineLine}>
                          <div
                            style={{
                              ...S.timelineDot,
                              background: slot.current ? TEAL : slot.done ? "#c7f9ea" : hasPatient ? "#cbd5e1" : "#eef2f7",
                              boxShadow: slot.current ? "0 0 0 4px rgba(0,212,160,0.12)" : "none",
                            }}
                          />
                          {index < agenda.slots.length - 1 ? <div style={S.timelineBar} /> : null}
                        </div>
                        <div
                          style={{
                            ...S.timelineCard,
                            background: slot.current ? "rgba(0,212,160,0.06)" : "#fff",
                            borderColor: slot.current ? "rgba(0,212,160,0.22)" : "#edf2f7",
                            opacity: slot.done ? 0.65 : 1,
                          }}
                        >
                          {hasPatient ? (
                            <>
                              <div style={S.timelineTop}>
                                <div style={S.timelinePatient}>
                                  {slot.patient}
                                  {slot.current ? (
                                    <span style={S.timelineNow}>
                                      <Pulse color={TEAL} size={6} />
                                      En cours
                                    </span>
                                  ) : null}
                                </div>
                                <span style={S.sourceBadge}>{slot.source || "Agenda"}</span>
                              </div>
                              <div style={S.timelineType}>{slot.type || "Rendez-vous"}</div>
                            </>
                          ) : (
                            <div style={{ ...S.timelineType, color: "#cbd5e1", fontStyle: "italic" }}>Libre</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </section>

        <section className="uwi-shortcuts-grid" style={S.shortcutsGrid}>
          {SHORTCUTS.map((shortcut) => (
            <button
              key={shortcut.label}
              type="button"
              onClick={() => navigate(shortcut.href)}
              className="uwi-shortcut-card"
              style={{ ...S.shortcutCard, borderColor: `${shortcut.color}2a` }}
            >
              <div style={{ ...S.shortcutIcon, color: shortcut.color, background: `${shortcut.color}14` }}>
                {shortcut.icon}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 800, color: NAVY }}>{shortcut.label}</div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>Ouvrir</div>
              </div>
            </button>
          ))}
        </section>
      </div>
    </div>
  );
}

const S = {
  root: {
    background: "#f4f7fb",
    minHeight: "100%",
    fontFamily: "'DM Sans', sans-serif",
    color: NAVY,
  },
  heroCard: {
    background: "linear-gradient(135deg, #ecfdf8 0%, #ffffff 55%, #eef6ff 100%)",
    border: "1px solid rgba(0,212,160,0.16)",
    borderRadius: 24,
    boxShadow: "0 14px 40px rgba(13,27,46,0.07)",
    padding: 24,
  },
  heroGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gap: 20,
    alignItems: "center",
  },
  assistantBlock: {
    display: "flex",
    alignItems: "center",
    gap: 18,
    minWidth: 0,
  },
  avatarWrap: {
    width: 86,
    height: 86,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#fff",
    fontSize: 32,
    fontWeight: 800,
    position: "relative",
    boxShadow: "0 12px 28px rgba(59,130,246,0.18)",
    flexShrink: 0,
  },
  avatarLetter: {
    fontFamily: "'Syne', 'DM Sans', sans-serif",
    letterSpacing: "-0.03em",
  },
  avatarOnline: {
    position: "absolute",
    right: 6,
    bottom: 6,
    width: 18,
    height: 18,
    borderRadius: "50%",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  assistantTopLine: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  assistantName: {
    fontSize: 32,
    lineHeight: 1,
    fontWeight: 800,
    fontFamily: "'Syne', 'DM Sans', sans-serif",
    letterSpacing: "-0.03em",
  },
  liveBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    background: "rgba(34,197,94,0.1)",
    border: "1px solid rgba(34,197,94,0.18)",
    color: "#15803d",
    borderRadius: 999,
    padding: "6px 10px",
    fontSize: 12,
    fontWeight: 700,
  },
  assistantMeta: {
    marginTop: 10,
    color: "#64748b",
    fontSize: 14,
  },
  phoneLine: {
    marginTop: 10,
    fontSize: 14,
    color: NAVY,
  },
  heroMetrics: {
    minWidth: 170,
    padding: "18px 20px",
    borderRadius: 18,
    background: "rgba(255,255,255,0.72)",
    border: "1px solid rgba(13,27,46,0.06)",
    boxShadow: "0 8px 22px rgba(13,27,46,0.05)",
  },
  metricLabel: {
    fontSize: 12,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    fontWeight: 700,
  },
  metricValue: {
    marginTop: 6,
    fontSize: 42,
    lineHeight: 1,
    fontWeight: 800,
    color: NAVY,
    fontFamily: "'Syne', 'DM Sans', sans-serif",
  },
  metricSub: {
    marginTop: 10,
    color: "#64748b",
    fontSize: 13,
  },
  pendingBanner: {
    marginTop: 16,
    display: "flex",
    alignItems: "center",
    gap: 12,
    borderRadius: 18,
    background: "#fff8eb",
    border: "1px solid rgba(245,158,11,0.24)",
    padding: "14px 16px",
  },
  pendingTitle: {
    fontSize: 14,
    color: "#b45309",
    fontWeight: 800,
  },
  pendingText: {
    marginTop: 3,
    fontSize: 13,
    color: "#92400e",
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 16,
    marginTop: 20,
  },
  kpiCard: {
    background: "#fff",
    border: "1px solid #e8eef5",
    borderRadius: 22,
    padding: 20,
    boxShadow: "0 10px 24px rgba(13,27,46,0.04)",
  },
  kpiIcon: {
    width: 48,
    height: 48,
    borderRadius: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 24,
  },
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 2fr) minmax(320px, 1fr)",
    gap: 18,
    marginTop: 20,
    alignItems: "stretch",
  },
  mainCard: {
    background: "#fff",
    border: "1px solid #e8eef5",
    borderRadius: 24,
    padding: 22,
    boxShadow: "0 14px 34px rgba(13,27,46,0.04)",
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
  },
  cardHead: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 18,
  },
  cardTag: {
    fontSize: 11,
    color: "#94a3b8",
    textTransform: "uppercase",
    letterSpacing: "0.12em",
    fontWeight: 700,
    marginBottom: 4,
  },
  cardTitle: {
    fontSize: 22,
    lineHeight: 1.15,
    color: NAVY,
    fontWeight: 800,
    fontFamily: "'Syne', 'DM Sans', sans-serif",
  },
  linkBtn: {
    border: "none",
    background: "rgba(0,212,160,0.08)",
    color: TEALX,
    padding: "9px 12px",
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
    fontFamily: "inherit",
  },
  cardBodyScrollable: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  callRow: {
    width: "100%",
    display: "flex",
    alignItems: "flex-start",
    gap: 16,
    padding: "16px 18px",
    borderRadius: 18,
    border: "1px solid #edf2f7",
    background: "#fff",
    textAlign: "left",
    cursor: "pointer",
    transition: "transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease",
    fontFamily: "inherit",
  },
  callTimeBlock: {
    width: 60,
    flexShrink: 0,
  },
  callTime: {
    fontSize: 14,
    fontWeight: 800,
    color: NAVY,
    fontFamily: "monospace",
  },
  callDuration: {
    marginTop: 6,
    fontSize: 12,
    color: "#94a3b8",
    fontFamily: "monospace",
  },
  callTop: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  callName: {
    fontSize: 15,
    fontWeight: 800,
    color: NAVY,
  },
  agentChip: {
    padding: "4px 8px",
    borderRadius: 999,
    background: "rgba(0,212,160,0.08)",
    border: "1px solid rgba(0,212,160,0.16)",
    fontSize: 11,
    fontWeight: 700,
  },
  callSummary: {
    marginTop: 8,
    fontSize: 13,
    color: "#64748b",
    lineHeight: 1.55,
  },
  statusBadge: {
    flexShrink: 0,
    padding: "6px 10px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 12,
    fontWeight: 800,
    whiteSpace: "nowrap",
  },
  emptyState: {
    padding: "38px 16px",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  emptyIcon: {
    fontSize: 34,
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 16,
    color: NAVY,
    fontWeight: 800,
  },
  emptyText: {
    marginTop: 8,
    fontSize: 13,
    color: "#64748b",
    maxWidth: 300,
  },
  primaryBtn: {
    border: "none",
    borderRadius: 12,
    background: `linear-gradient(135deg, ${TEAL}, ${TEALX})`,
    color: NAVY,
    padding: "11px 14px",
    fontSize: 13,
    fontWeight: 800,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  agendaSummary: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 10,
    marginBottom: 18,
  },
  agendaStat: {
    background: "#f8fbff",
    border: "1px solid #edf2f7",
    borderRadius: 16,
    padding: "16px 12px",
    textAlign: "center",
  },
  timeline: {
    display: "grid",
    gap: 10,
  },
  timelineRow: {
    display: "grid",
    gridTemplateColumns: "58px 16px minmax(0, 1fr)",
    gap: 12,
    alignItems: "stretch",
  },
  timelineHour: {
    paddingTop: 10,
    fontSize: 12,
    fontWeight: 800,
    fontFamily: "monospace",
    textAlign: "right",
  },
  timelineLine: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: 14,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    flexShrink: 0,
  },
  timelineBar: {
    width: 2,
    flex: 1,
    minHeight: 26,
    marginTop: 4,
    background: "#eef2f7",
    borderRadius: 999,
  },
  timelineCard: {
    borderRadius: 16,
    border: "1px solid #edf2f7",
    padding: "12px 14px",
    background: "#fff",
  },
  timelineTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    flexWrap: "wrap",
  },
  timelinePatient: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 14,
    fontWeight: 800,
    color: NAVY,
  },
  timelineNow: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    fontWeight: 700,
    color: TEALX,
  },
  sourceBadge: {
    padding: "4px 8px",
    borderRadius: 999,
    background: "rgba(59,130,246,0.08)",
    color: "#3b82f6",
    fontSize: 11,
    fontWeight: 700,
    border: "1px solid rgba(59,130,246,0.12)",
  },
  timelineType: {
    marginTop: 6,
    fontSize: 13,
    color: "#64748b",
    lineHeight: 1.5,
  },
  shortcutsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 14,
    marginTop: 20,
    paddingBottom: 8,
  },
  shortcutCard: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    width: "100%",
    border: "1px solid",
    borderRadius: 18,
    padding: "16px 18px",
    background: "#fff",
    cursor: "pointer",
    textAlign: "left",
    boxShadow: "0 10px 24px rgba(13,27,46,0.04)",
    transition: "transform 0.15s ease, box-shadow 0.15s ease",
    fontFamily: "inherit",
  },
  shortcutIcon: {
    width: 46,
    height: 46,
    borderRadius: 14,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 22,
    flexShrink: 0,
  },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Syne:wght@700;800&display=swap');

  * { box-sizing: border-box; }

  @keyframes uwi-ping {
    0% { transform: scale(1); opacity: .4; }
    80%, 100% { transform: scale(2.5); opacity: 0; }
  }

  @keyframes uwi-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .uwi-dashboard-shell {
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px;
  }

  .uwi-dashboard-row:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 24px rgba(13,27,46,0.06);
    background: #fbfdff !important;
  }

  .uwi-shortcut-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 24px rgba(13,27,46,0.06);
  }

  @media (max-width: 1080px) {
    .uwi-main-grid {
      grid-template-columns: 1fr !important;
    }

    .uwi-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    .uwi-shortcuts-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
  }

  @media (max-width: 760px) {
    .uwi-dashboard-shell {
      padding: 16px;
    }

    .uwi-hero-grid {
      grid-template-columns: 1fr !important;
    }

    .uwi-kpi-grid {
      grid-template-columns: 1fr !important;
    }

    .uwi-shortcuts-grid {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 640px) {
    .uwi-dashboard-row {
      flex-direction: column;
      gap: 12px;
    }
  }
`;
