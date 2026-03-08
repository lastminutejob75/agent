import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Bell,
  Calendar,
  CheckCircle2,
  Phone,
  PhoneCall,
  Plus,
  Search,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api.js";

const TEAL = "#14c8b8";
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
  const showPhoneBanner = !loading && !me?.voice_number;
  const agendaReady = !!me?.onboarding_steps?.calendar_ready;

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

  const agendaItems = (agenda?.slots || []).filter((slot) => slot.patient).slice(0, 3);

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      <div className="uwi-dashboard-wrap">
        <div className="uwi-header-row" style={S.header}>
          <div>
            <h1 style={S.title}>Tableau de bord</h1>
            <p style={S.subtitle}>Activité de l&apos;agent médical aujourd&apos;hui</p>
          </div>

          <div style={S.headerRight}>
            <button type="button" style={S.iconButton} aria-label="Notifications">
              <Bell size={18} strokeWidth={1.8} color="#6b7280" />
              <span style={S.bellDot} />
            </button>

            <div className="uwi-search" style={S.searchWrap}>
              <Search size={18} strokeWidth={1.8} color="#9ca3af" />
              <input placeholder="Rechercher..." style={S.searchInput} />
            </div>
          </div>
        </div>

        <section style={S.assistantCard}>
          <div style={S.assistantLabel}>Votre Assistante</div>

          <div className="uwi-assistant-row" style={S.assistantRow}>
            <div style={S.assistantLeft}>
              <div style={{ ...S.avatarRing, background: avatarTheme.ring }}>
                <div style={{ ...S.avatar, background: avatarTheme.bg }}>
                  <span style={S.avatarText}>{getInitial(assistantName)}</span>
                </div>
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
                        <span style={{ color: TEAL_DARK }}>✦</span>
                        Calme · Pro
                      </span>
                      <span style={{ ...S.assistantMetaItem, color: "#10b981", fontWeight: 600 }}>
                        <DotPulse size={8} />
                        En ligne
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div style={S.assistantRight}>
              <div style={S.assistantRightLabel}>Appels aujourd&apos;hui</div>
              <div style={S.assistantRightValue}>{loading ? <Skeleton width={36} height={30} radius={8} /> : kpis?.current?.calls ?? 0}</div>
            </div>
          </div>
        </section>

        {showPhoneBanner ? (
          <div style={S.banner}>⏳ Configuration en cours — Notre équipe active votre numéro sous 24h</div>
        ) : null}

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
              ) : calls.length === 0 ? (
                <div style={S.emptyState}>
                  <div style={S.emptyTitle}>Aucun appel aujourd&apos;hui</div>
                  <div style={S.emptyText}>Votre journal d&apos;appels apparaîtra ici.</div>
                </div>
              ) : (
                calls.slice(0, 4).map((call) => {
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
                <div style={S.panelSubtitle}>Prochains appels</div>
              </div>
              <div style={{ color: TEAL_DARK, display: "flex", alignItems: "center" }}>
                <TrendingUp size={18} strokeWidth={2} />
              </div>
            </div>

            {!agendaReady && !loading ? (
              <div style={S.emptyState}>
                <div style={S.emptyTitle}>Agenda non connecté</div>
                <div style={S.emptyText}>Configurez votre agenda pour afficher vos rendez-vous.</div>
              </div>
            ) : (
              <div style={S.agendaList}>
                {loading ? (
                  [1, 2, 3].map((item) => <Skeleton key={item} height={90} radius={12} />)
                ) : agendaItems.length > 0 ? (
                  agendaItems.map((item, index) => (
                    <div key={`${item.hour}_${index}`} style={S.agendaRow}>
                      <div style={S.timelineCol}>
                        <div style={S.timeCard}>
                          <div style={S.timeTop}>{String(item.hour || "").split(":")[0]}</div>
                          <div style={S.timeBottom}>{String(item.hour || "").split(":")[1] || "00"}</div>
                        </div>
                        {index < agendaItems.length - 1 ? <div style={S.timelineLine} /> : null}
                      </div>

                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={S.agendaName}>{item.patient}</div>
                        <div style={S.agendaType}>{item.type || "Rendez-vous"}</div>
                        <button type="button" onClick={() => navigate("/app/agenda")} style={S.detailButton}>
                          Détails <ArrowUpRight size={13} strokeWidth={2.2} />
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={S.emptyState}>
                    <div style={S.emptyTitle}>Aucun rendez-vous aujourd&apos;hui</div>
                    <div style={S.emptyText}>Votre planning apparaîtra ici.</div>
                  </div>
                )}
              </div>
            )}

            <button type="button" onClick={() => navigate("/app/agenda")} style={S.planButton}>
              <Plus size={16} strokeWidth={2.2} />
              <span>Planifier un appel</span>
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
    background: "#f6f7f9",
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
    fontSize: 40,
    lineHeight: 1,
    fontWeight: 800,
    color: NAVY,
    letterSpacing: "-0.03em",
  },
  subtitle: {
    marginTop: 10,
    fontSize: 16,
    color: "#6b7280",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 14,
  },
  iconButton: {
    width: 42,
    height: 42,
    borderRadius: 12,
    border: "none",
    background: "transparent",
    cursor: "pointer",
    position: "relative",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  bellDot: {
    position: "absolute",
    top: 10,
    right: 10,
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#ef4444",
  },
  searchWrap: {
    width: 260,
    height: 46,
    borderRadius: 14,
    border: "1px solid #e8edf3",
    background: "#fff",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "0 14px",
  },
  searchInput: {
    flex: 1,
    border: "none",
    outline: "none",
    background: "transparent",
    fontSize: 14,
    color: "#374151",
    fontFamily: "inherit",
  },
  assistantCard: {
    background: "linear-gradient(135deg, #f2fffb 0%, #ffffff 100%)",
    border: "1px solid #d8f3ec",
    borderRadius: 24,
    padding: "18px 22px",
    boxShadow: "0 2px 8px rgba(17,24,39,0.03)",
  },
  assistantLabel: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.08em",
    color: TEAL_DARK,
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
    width: 68,
    height: 68,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    flexShrink: 0,
  },
  avatar: {
    width: 58,
    height: 58,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 12px 24px rgba(20,200,184,0.16)",
  },
  avatarText: {
    color: "#fff",
    fontSize: 24,
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
    fontSize: 26,
    fontWeight: 800,
    color: NAVY,
    lineHeight: 1,
  },
  assistantMetaRow: {
    marginTop: 8,
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
    fontSize: 14,
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
    fontSize: 13,
    color: "#9ca3af",
    marginBottom: 8,
  },
  assistantRightValue: {
    fontSize: 34,
    lineHeight: 1,
    fontWeight: 800,
    color: NAVY,
  },
  banner: {
    marginTop: 16,
    padding: "12px 14px",
    borderRadius: 14,
    border: "1px solid #fed7aa",
    background: "#fff7ed",
    color: "#c2410c",
    fontSize: 13,
    fontWeight: 600,
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 18,
    marginTop: 24,
  },
  kpiCard: {
    background: "#fff",
    border: "1px solid #e9eef4",
    borderRadius: 24,
    padding: 22,
    boxShadow: "0 2px 8px rgba(17,24,39,0.03)",
  },
  kpiTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 18,
  },
  kpiIconBox: {
    width: 52,
    height: 52,
    borderRadius: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  kpiChange: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 12,
    color: "#10b981",
    fontWeight: 600,
  },
  kpiValue: {
    fontSize: 42,
    lineHeight: 1,
    fontWeight: 800,
    color: NAVY,
  },
  kpiLabel: {
    marginTop: 12,
    fontSize: 14,
    color: "#6b7280",
  },
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 2fr) minmax(320px, 1fr)",
    gap: 18,
    marginTop: 24,
  },
  panel: {
    background: "#fff",
    border: "1px solid #e9eef4",
    borderRadius: 24,
    overflow: "hidden",
    boxShadow: "0 2px 8px rgba(17,24,39,0.03)",
  },
  panelHeader: {
    padding: "18px 22px",
    borderBottom: "1px solid #eef2f7",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  panelTitle: {
    fontSize: 24,
    lineHeight: 1.1,
    fontWeight: 700,
    color: NAVY,
  },
  panelSubtitle: {
    marginTop: 6,
    fontSize: 13,
    color: "#6b7280",
  },
  panelLink: {
    border: "none",
    background: "transparent",
    color: TEAL_DARK,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  callList: {
    display: "flex",
    flexDirection: "column",
  },
  callRow: {
    width: "100%",
    border: "none",
    background: "#fff",
    padding: "18px 22px",
    display: "flex",
    alignItems: "center",
    gap: 16,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  callIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  callName: {
    fontSize: 16,
    fontWeight: 700,
    color: NAVY,
  },
  callPhone: {
    marginTop: 4,
    fontSize: 13,
    color: "#9ca3af",
  },
  callOutcome: {
    marginTop: 10,
    fontSize: 14,
    color: "#4b5563",
    lineHeight: 1.5,
  },
  callMeta: {
    textAlign: "right",
    minWidth: 84,
    flexShrink: 0,
  },
  callTime: {
    fontSize: 14,
    color: "#374151",
    fontWeight: 600,
  },
  statusBadge: {
    display: "inline-flex",
    marginTop: 8,
    padding: "4px 10px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 12,
    fontWeight: 600,
  },
  callDuration: {
    marginTop: 10,
    fontSize: 14,
    color: NAVY,
    fontWeight: 600,
  },
  agendaList: {
    padding: "18px 22px 10px",
  },
  agendaRow: {
    display: "flex",
    gap: 16,
    marginBottom: 18,
  },
  timelineCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    flexShrink: 0,
  },
  timeCard: {
    width: 56,
    height: 56,
    borderRadius: 16,
    background: `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})`,
    color: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 12px 24px rgba(20,200,184,0.18)",
  },
  timeTop: {
    fontSize: 11,
    fontWeight: 700,
    lineHeight: 1,
    opacity: 0.92,
  },
  timeBottom: {
    marginTop: 2,
    fontSize: 18,
    fontWeight: 800,
    lineHeight: 1,
  },
  timelineLine: {
    width: 2,
    height: 28,
    marginTop: 8,
    borderRadius: 999,
    background: "linear-gradient(180deg, rgba(20,200,184,0.25), transparent)",
  },
  agendaName: {
    fontSize: 16,
    fontWeight: 700,
    color: NAVY,
  },
  agendaType: {
    marginTop: 6,
    fontSize: 14,
    color: "#6b7280",
  },
  detailButton: {
    marginTop: 10,
    border: "none",
    background: "transparent",
    padding: 0,
    color: TEAL_DARK,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontFamily: "inherit",
  },
  planButton: {
    margin: "10px 22px 22px",
    height: 46,
    borderRadius: 14,
    border: "1px dashed #d1d5db",
    background: "#fff",
    color: "#4b5563",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    fontFamily: "inherit",
  },
  emptyState: {
    padding: "48px 24px",
    textAlign: "center",
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: NAVY,
  },
  emptyText: {
    marginTop: 10,
    fontSize: 13,
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
  }
`;
