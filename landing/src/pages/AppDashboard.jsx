import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const TEAL = "#17c3b2";
const TEAL_DARK = "#11b1a1";
const NAVY = "#181c27";

const STATUS_CFG = {
  TRANSFERRED: { label: "Manqué", bg: "#fff1f2", color: "#e11d48", border: "#fecdd3" },
  CONFIRMED: { label: "OK", bg: "#ecfdf5", color: "#10b981", border: "#bbf7d0" },
  ABANDONED: { label: "Manqué", bg: "#fff1f2", color: "#e11d48", border: "#fecdd3" },
  FAQ: { label: "Prévu", bg: "#eff6ff", color: "#60a5fa", border: "#bfdbfe" },
};

const AVATAR_THEME = {
  sophie: { ring: "#d1fae5", bg: "linear-gradient(135deg, #14c8b8, #34d399)" },
  emma: { ring: "#fce7f3", bg: "linear-gradient(135deg, #f9a8d4, #fbcfe8)" },
  clara: { ring: "#dbeafe", bg: "linear-gradient(135deg, #93c5fd, #c4b5fd)" },
  camille: { ring: "#fef3c7", bg: "linear-gradient(135deg, #fcd34d, #fb7185)" },
  thomas: { ring: "#dbeafe", bg: "linear-gradient(135deg, #60a5fa, #818cf8)" },
};

function Skeleton({ w = "100%", h = 14, radius = 8 }) {
  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: radius,
        background: "linear-gradient(90deg, #f1f5f9 25%, #e8edf3 50%, #f1f5f9 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-shimmer 1.4s infinite linear",
      }}
    />
  );
}

function DotPulse() {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 7, height: 7 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "#10b981", opacity: 0.28, animation: "uwi-ping 1.7s ease-out infinite" }} />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: "#10b981" }} />
    </span>
  );
}

function getAvatarTheme(name) {
  return AVATAR_THEME[String(name || "").trim().toLowerCase()] || {
    ring: "#ccfbf1",
    bg: "linear-gradient(135deg, #17c3b2, #93c5fd)",
  };
}

function getInitial(name) {
  const value = String(name || "U").trim();
  return value ? value.charAt(0).toUpperCase() : "U";
}

function callIconTheme(status) {
  if (status === "TRANSFERRED") return { bg: "#fff1f2", color: "#e11d48" };
  if (status === "CONFIRMED") return { bg: "#ecfdf5", color: "#10b981" };
  if (status === "FAQ") return { bg: "#eff6ff", color: "#60a5fa" };
  return { bg: "#f8fafc", color: "#94a3b8" };
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

  const assistantName = me?.assistant_name || "Emma";
  const avatarTheme = getAvatarTheme(assistantName);
  const callsCount = kpis?.current?.calls ?? 0;
  const bookingsCount = kpis?.current?.bookings ?? 0;
  const pickupRate = `${Math.round((kpis?.pickup_rate ?? 0) * 100)}%`;
  const minutesMonth = kpis?.minutes_month ?? 0;
  const agendaReady = !!me?.onboarding_steps?.calendar_ready;
  const showPhoneBanner = !loading && !me?.voice_number;
  const agendaSlots = (agenda?.slots || []).filter((slot) => slot.patient).slice(0, 3);

  const stats = [
    { label: "Appels traités", value: callsCount, icon: "📞", iconBg: "#eef5ff", iconColor: "#4f87ff", micro: "↗ + live" },
    { label: "RDV planifiés", value: bookingsCount, icon: "📅", iconBg: "#eefcf7", iconColor: "#17b56d", micro: "↗ agenda" },
    { label: "Taux de réponse", value: pickupRate, icon: "📈", iconBg: "#effcf9", iconColor: "#14b8a6", micro: "↗ instant" },
    { label: "Minutes ce mois", value: minutesMonth, icon: "◔", iconBg: "#f6f1ff", iconColor: "#8b5cf6", micro: "↗ cumul" },
  ];

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      <div className="uwi-dashboard-wrap">
        <div className="uwi-header-row" style={S.header}>
          <div>
            <div style={S.title}>Tableau de bord</div>
            <div style={S.subtitle}>Activité de l&apos;agent médical aujourd&apos;hui</div>
          </div>

          <div style={S.headerRight}>
            <button type="button" style={S.bellBtn} aria-label="Notifications">
              <span style={{ fontSize: 14 }}>🔔</span>
              <span style={S.bellDot} />
            </button>
            <div className="uwi-search" style={S.searchBox}>
              <span style={{ color: "#b8c0cb", fontSize: 13 }}>⌕</span>
              <input placeholder="Rechercher..." style={S.searchInput} />
            </div>
          </div>
        </div>

        <section style={S.assistantCard}>
          <div style={S.assistantLabel}>VOTRE ASSISTANTE</div>
          <div className="uwi-assistant-row" style={S.assistantRow}>
            <div style={S.assistantLeft}>
              <div style={{ ...S.avatarRing, background: avatarTheme.ring }}>
                <div style={{ ...S.avatar, background: avatarTheme.bg }}>
                  <span style={S.avatarLetter}>{getInitial(assistantName)}</span>
                </div>
                <div style={S.avatarDot}>
                  <DotPulse />
                </div>
              </div>

              <div style={{ minWidth: 0 }}>
                {loading ? (
                  <>
                    <Skeleton w={76} h={16} />
                    <div style={{ marginTop: 6 }}>
                      <Skeleton w={114} h={10} />
                    </div>
                  </>
                ) : (
                  <>
                    <div style={S.assistantName}>{assistantName}</div>
                    <div style={S.assistantMeta}>
                      <span>✦ Calme · Pro</span>
                      <span style={S.assistantOnline}>
                        <DotPulse />
                        En ligne
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div style={S.assistantCounter}>
              <div style={S.assistantCounterLabel}>Appels aujourd&apos;hui</div>
              <div style={S.assistantCounterValue}>{loading ? <Skeleton w={22} h={22} /> : callsCount}</div>
            </div>
          </div>
        </section>

        {showPhoneBanner ? (
          <div style={S.banner}>⏳ Configuration en cours — Notre équipe active votre numéro sous 24h</div>
        ) : null}

        <section className="uwi-kpis-grid" style={S.kpiGrid}>
          {loading
            ? [1, 2, 3, 4].map((item) => (
                <div key={item} style={S.kpiCard}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <Skeleton w={34} h={34} radius={10} />
                    <Skeleton w={42} h={10} />
                  </div>
                  <div style={{ marginTop: 18 }}>
                    <Skeleton w={40} h={24} />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Skeleton w={88} h={10} />
                  </div>
                </div>
              ))
            : stats.map((stat) => (
                <div key={stat.label} style={S.kpiCard}>
                  <div style={S.kpiHead}>
                    <div style={{ ...S.kpiIcon, background: stat.iconBg, color: stat.iconColor }}>{stat.icon}</div>
                    <div style={S.kpiMicro}>{stat.micro}</div>
                  </div>
                  <div style={S.kpiValue}>{stat.value}</div>
                  <div style={S.kpiLabel}>{stat.label}</div>
                </div>
              ))}
        </section>

        <section className="uwi-main-grid" style={S.mainGrid}>
          <div style={S.panel}>
            <div style={S.panelHeader}>
              <div>
                <div style={S.panelTitle}>Appels récents</div>
                <div style={S.panelSubtitle}>Activité des dernières heures</div>
              </div>
              <button type="button" onClick={() => navigate("/app/appels")} style={S.panelLink}>
                Voir tout ↗
              </button>
            </div>

            <div style={S.rows}>
              {loading ? (
                [1, 2, 3, 4].map((item) => <Skeleton key={item} h={66} radius={0} />)
              ) : calls.length === 0 ? (
                <div style={S.emptyBox}>
                  <div style={S.emptyTitle}>Aucun appel aujourd&apos;hui</div>
                  <div style={S.emptyText}>Votre journal d&apos;appels apparaîtra ici.</div>
                </div>
              ) : (
                calls.slice(0, 4).map((call) => {
                  const status = STATUS_CFG[call.status] || STATUS_CFG.ABANDONED;
                  const icon = callIconTheme(call.status);
                  return (
                    <button
                      key={call.id}
                      type="button"
                      onClick={() => navigate("/app/appels")}
                      style={S.callRow}
                      className="uwi-call-row"
                    >
                      <div style={{ ...S.callIcon, background: icon.bg, color: icon.color }}>📞</div>

                      <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
                        <div style={S.callName}>{call.patient_name || "Patient inconnu"}</div>
                        <div style={S.callSub}>{call.agent_name || assistantName}</div>
                        <div style={S.callText}>{call.summary || "Aucun résumé disponible."}</div>
                      </div>

                      <div style={S.callMeta}>
                        <div style={S.callHour}>{call.time || "--:--"}</div>
                        <span style={{ ...S.callBadge, background: status.bg, color: status.color, borderColor: status.border }}>
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
                <div style={S.panelSubtitle}>Prochains appels</div>
              </div>
              <div style={{ fontSize: 17, color: TEAL_DARK }}>〰</div>
            </div>

            {!agendaReady && !loading ? (
              <div style={S.emptyBox}>
                <div style={S.emptyTitle}>Agenda non connecté</div>
                <div style={S.emptyText}>Configurez votre agenda pour afficher vos rendez-vous.</div>
              </div>
            ) : (
              <div style={S.agendaRows}>
                {loading ? (
                  [1, 2, 3].map((item) => <Skeleton key={item} h={70} radius={10} />)
                ) : agendaSlots.length > 0 ? (
                  agendaSlots.map((slot, index) => (
                    <div key={`${slot.hour}_${index}`} style={S.agendaRow}>
                      <div style={S.timeCol}>
                        <div style={S.timeBox}>
                          <div style={S.timeTop}>{String(slot.hour || "").split(":")[0]}</div>
                          <div style={S.timeBottom}>{String(slot.hour || "").split(":")[1] || "00"}</div>
                        </div>
                        {index < agendaSlots.length - 1 ? <div style={S.timeLine} /> : null}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={S.agendaName}>{slot.patient}</div>
                        <div style={S.agendaText}>{slot.type || "Rendez-vous"}</div>
                        <button type="button" onClick={() => navigate("/app/agenda")} style={S.detailBtn}>
                          Détails ↗
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={S.emptyBox}>
                    <div style={S.emptyTitle}>Aucun rendez-vous aujourd&apos;hui</div>
                    <div style={S.emptyText}>Votre planning apparaîtra ici.</div>
                  </div>
                )}
              </div>
            )}

            <button type="button" onClick={() => navigate("/app/agenda")} style={S.planBtn}>
              ＋ Planifier un appel
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

const S = {
  root: {
    minHeight: "100%",
    background: "#f7f8fa",
    fontFamily: "'Inter', 'DM Sans', sans-serif",
    color: NAVY,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 18,
    marginBottom: 18,
  },
  title: {
    fontSize: 24,
    lineHeight: 1.05,
    fontWeight: 700,
    color: NAVY,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    marginTop: 8,
    fontSize: 12,
    color: "#757f8c",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  bellBtn: {
    width: 34,
    height: 34,
    border: "none",
    background: "transparent",
    borderRadius: 10,
    cursor: "pointer",
    position: "relative",
    color: "#6b7280",
  },
  bellDot: {
    position: "absolute",
    top: 7,
    right: 7,
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#ef4444",
  },
  searchBox: {
    width: 184,
    height: 34,
    borderRadius: 10,
    border: "1px solid #edf1f5",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    gap: 7,
    padding: "0 10px",
  },
  searchInput: {
    flex: 1,
    border: "none",
    outline: "none",
    background: "transparent",
    fontSize: 12,
    color: "#4b5563",
    fontFamily: "inherit",
  },
  assistantCard: {
    background: "linear-gradient(135deg, #f5fffb 0%, #ffffff 100%)",
    border: "1px solid #dff5ee",
    borderRadius: 16,
    padding: "13px 16px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
  },
  assistantLabel: {
    fontSize: 9,
    fontWeight: 800,
    letterSpacing: "0.1em",
    color: TEAL_DARK,
    marginBottom: 9,
  },
  assistantRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  assistantLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    minWidth: 0,
  },
  avatarRing: {
    width: 50,
    height: 50,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    flexShrink: 0,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 8px 18px rgba(23,195,178,0.14)",
  },
  avatarLetter: {
    color: "#fff",
    fontSize: 18,
    fontWeight: 700,
  },
  avatarDot: {
    position: "absolute",
    right: 2,
    bottom: 2,
    width: 14,
    height: 14,
    borderRadius: "50%",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  assistantName: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  assistantMeta: {
    marginTop: 4,
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
    fontSize: 11,
    color: "#6b7280",
  },
  assistantOnline: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    color: "#16a34a",
    fontWeight: 600,
  },
  assistantCounter: {
    textAlign: "right",
    minWidth: 82,
    flexShrink: 0,
  },
  assistantCounterLabel: {
    fontSize: 10,
    color: "#9ca3af",
    marginBottom: 6,
  },
  assistantCounterValue: {
    fontSize: 18,
    fontWeight: 700,
    color: NAVY,
    lineHeight: 1,
  },
  banner: {
    marginTop: 12,
    padding: "10px 12px",
    borderRadius: 12,
    background: "#fff7ed",
    border: "1px solid #fed7aa",
    color: "#c2410c",
    fontSize: 12,
    fontWeight: 600,
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 14,
    marginTop: 16,
  },
  kpiCard: {
    background: "#fff",
    border: "1px solid #edf1f5",
    borderRadius: 16,
    padding: 16,
    boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
  },
  kpiHead: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  kpiIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
  },
  kpiMicro: {
    fontSize: 10,
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
    marginTop: 10,
    fontSize: 11,
    color: "#6b7280",
  },
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 2fr) minmax(280px, 0.95fr)",
    gap: 14,
    marginTop: 16,
  },
  panel: {
    background: "#fff",
    border: "1px solid #edf1f5",
    borderRadius: 16,
    overflow: "hidden",
    boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
  },
  panelHeader: {
    padding: "14px 16px",
    borderBottom: "1px solid #f1f5f9",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 10,
  },
  panelTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  panelSubtitle: {
    marginTop: 4,
    fontSize: 11,
    color: "#6b7280",
  },
  panelLink: {
    border: "none",
    background: "transparent",
    color: TEAL_DARK,
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  rows: {
    display: "flex",
    flexDirection: "column",
  },
  callRow: {
    width: "100%",
    border: "none",
    background: "#fff",
    padding: "13px 16px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  callIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
    flexShrink: 0,
  },
  callName: {
    fontSize: 12,
    fontWeight: 700,
    color: NAVY,
  },
  callSub: {
    marginTop: 3,
    fontSize: 11,
    color: "#9ca3af",
  },
  callText: {
    marginTop: 8,
    fontSize: 11,
    color: "#4b5563",
    lineHeight: 1.45,
  },
  callMeta: {
    textAlign: "right",
    minWidth: 62,
    flexShrink: 0,
  },
  callHour: {
    fontSize: 11,
    color: "#374151",
    fontWeight: 600,
  },
  callBadge: {
    display: "inline-flex",
    marginTop: 8,
    padding: "2px 7px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 10,
    fontWeight: 600,
  },
  callDuration: {
    marginTop: 8,
    fontSize: 11,
    color: NAVY,
    fontWeight: 600,
  },
  agendaRows: {
    padding: "14px 16px 8px",
  },
  agendaRow: {
    display: "flex",
    gap: 12,
    marginBottom: 14,
  },
  timeCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    flexShrink: 0,
  },
  timeBox: {
    width: 42,
    height: 42,
    borderRadius: 12,
    background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`,
    color: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 10px 18px rgba(23,195,178,0.16)",
  },
  timeTop: {
    fontSize: 9,
    lineHeight: 1,
    fontWeight: 700,
    opacity: 0.9,
  },
  timeBottom: {
    marginTop: 2,
    fontSize: 14,
    lineHeight: 1,
    fontWeight: 700,
  },
  timeLine: {
    width: 2,
    height: 24,
    marginTop: 6,
    borderRadius: 999,
    background: "linear-gradient(180deg, rgba(23,195,178,0.26), transparent)",
  },
  agendaName: {
    fontSize: 12,
    fontWeight: 700,
    color: NAVY,
  },
  agendaText: {
    marginTop: 4,
    fontSize: 11,
    color: "#6b7280",
  },
  detailBtn: {
    marginTop: 8,
    border: "none",
    background: "transparent",
    padding: 0,
    color: TEAL_DARK,
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  planBtn: {
    margin: "8px 16px 16px",
    height: 40,
    borderRadius: 12,
    border: "1px dashed #d1d5db",
    background: "#fff",
    color: "#4b5563",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  emptyBox: {
    padding: "28px 18px",
    textAlign: "center",
  },
  emptyTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: NAVY,
  },
  emptyText: {
    marginTop: 8,
    fontSize: 11,
    color: "#6b7280",
  },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  * { box-sizing: border-box; }

  @keyframes uwi-ping {
    0% { transform: scale(1); opacity: .38; }
    80%, 100% { transform: scale(2.2); opacity: 0; }
  }

  @keyframes uwi-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .uwi-dashboard-wrap {
    max-width: 1040px;
    margin: 0 auto;
    padding: 22px 22px 28px;
  }

  .uwi-call-row {
    transition: background .14s ease;
  }

  .uwi-call-row:hover {
    background: #fbfcfd;
  }

  @media (max-width: 1080px) {
    .uwi-main-grid,
    .uwi-kpis-grid {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 720px) {
    .uwi-dashboard-wrap {
      padding: 16px 14px 20px;
    }

    .uwi-header-row,
    .uwi-assistant-row {
      flex-direction: column;
      align-items: flex-start !important;
    }

    .uwi-search {
      width: 100% !important;
    }
  }
`;
