import { ArrowUpRight, PhoneCall, Plus } from "lucide-react";

const NAVY = "#111827";

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

const S = {
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
    gap: 0,
    padding: "4px 18px",
  },
  callRow: {
    width: "100%",
    border: "none",
    borderRadius: 0,
    background: "#fff",
    padding: "18px 0",
    display: "flex",
    alignItems: "center",
    gap: 14,
    cursor: "pointer",
    fontFamily: "inherit",
    boxShadow: "none",
  },
  callIcon: {
    width: 46,
    height: 46,
    borderRadius: 14,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    boxShadow: "0 8px 20px rgba(20, 184, 166, 0.12)",
  },
  callIconLink: {
    textDecoration: "none",
  },
  callName: {
    fontSize: 16,
    fontWeight: 800,
    color: NAVY,
  },
  callPhone: {
    marginTop: 5,
    fontSize: 13,
    color: "#64748b",
    fontWeight: 600,
  },
  callOutcome: {
    marginTop: 10,
    fontSize: 13,
    color: "#4b5563",
    lineHeight: 1.45,
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
    fontSize: 12,
    color: "#475569",
    lineHeight: 1.5,
  },
  callMeta: {
    textAlign: "right",
    minWidth: 88,
    flexShrink: 0,
  },
  callTime: {
    fontSize: 16,
    color: "#374151",
    fontWeight: 700,
  },
  statusBadge: {
    display: "inline-flex",
    marginTop: 6,
    padding: "6px 10px",
    borderRadius: 999,
    border: "1px solid",
    fontSize: 11,
    fontWeight: 800,
  },
  callDuration: {
    marginTop: 8,
    fontSize: 14,
    color: NAVY,
    fontWeight: 700,
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
  appointmentCard: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    border: "1px solid #dbeafe",
    borderRadius: 16,
    background: "linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)",
    padding: "14px 16px",
    boxShadow: "0 8px 24px rgba(37,99,235,.06)",
  },
  appointmentTimeBox: {
    width: 64,
    minHeight: 58,
    borderRadius: 16,
    background: "linear-gradient(135deg, #14c8b8, #0ea899)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 10px",
    flexShrink: 0,
    boxShadow: "0 10px 24px rgba(20, 184, 166, 0.20)",
  },
  appointmentTimeValue: {
    fontSize: 17,
    fontWeight: 800,
    lineHeight: 1.05,
    textAlign: "center",
    letterSpacing: "-0.02em",
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
  agendaOverviewGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 12,
    padding: 18,
    paddingBottom: 0,
  },
  agendaOverviewCard: {
    border: "1px solid #e5e7eb",
    borderRadius: 16,
    background: "#fff",
    padding: "14px 16px",
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  agendaOverviewLabel: {
    fontSize: 11,
    fontWeight: 800,
    color: "#64748b",
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  agendaOverviewValue: {
    marginTop: 10,
    fontSize: 20,
    fontWeight: 800,
    color: NAVY,
  },
  agendaOverviewText: {
    marginTop: 6,
    fontSize: 12,
    color: "#6b7280",
    lineHeight: 1.5,
  },
  agendaOverviewBody: {
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  agendaExternalList: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  agendaExternalRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    padding: "12px 14px",
    background: "#fff",
  },
  agendaExternalTime: {
    minWidth: 56,
    fontSize: 13,
    fontWeight: 800,
    color: "#0f766e",
  },
  agendaExternalName: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  agendaExternalText: {
    marginTop: 4,
    fontSize: 12,
    color: "#6b7280",
    lineHeight: 1.4,
  },
  agendaExternalBadge: {
    display: "inline-flex",
    alignItems: "center",
    padding: "5px 9px",
    borderRadius: 999,
    border: "1px solid #cbd5e1",
    background: "#f8fafc",
    color: "#475569",
    fontSize: 10,
    fontWeight: 800,
    flexShrink: 0,
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

export default function AppDashboardMainPanels({
  callsLoading,
  recentCallItems,
  agendaLoading,
  appointmentItems,
  bookedAgendaCount,
  agendaReady,
  externalConnected,
  externalAgendaItems,
  onNavigate,
}) {
  return (
    <>
      <section className="uwi-main-grid" style={S.mainGrid}>
        <div style={S.panel} data-tour="calls-panel">
          <div style={S.panelHeader}>
            <div>
              <div style={S.panelTitle}>Appels récents</div>
              <div style={S.panelSubtitle}>Activité des dernières heures</div>
            </div>
            <button type="button" onClick={() => onNavigate("/app/appels")} style={S.linkButton}>
              <span>Voir tout</span>
              <ArrowUpRight size={16} strokeWidth={2.2} />
            </button>
          </div>

          <div style={S.callList}>
            {callsLoading ? (
              [1, 2, 3, 4].map((item) => <Skeleton key={item} height={92} radius={0} />)
            ) : recentCallItems.length === 0 ? (
              <div style={S.emptyState}>
                <div style={S.emptyTitle}>Aucun appel aujourd&apos;hui</div>
                <div style={S.emptyText}>Votre journal d&apos;appels apparaîtra ici.</div>
              </div>
            ) : (
              recentCallItems.map((call, index, rows) => (
                <div
                  key={call.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onNavigate("/app/appels")}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onNavigate("/app/appels");
                    }
                  }}
                  style={{
                    ...S.callRow,
                    borderBottom: index === rows.length - 1 ? "none" : "1px solid #edf2f7",
                  }}
                  className="uwi-call-row"
                >
                  <a
                    href={call.dialablePhone ? `tel:${call.dialablePhone}` : undefined}
                    onClick={(event) => {
                      if (!call.dialablePhone) {
                        event.preventDefault();
                        event.stopPropagation();
                        return;
                      }
                      event.stopPropagation();
                    }}
                    aria-label={call.dialablePhone ? `Rappeler ${call.patientName || "ce client"}` : "Numéro indisponible"}
                    title={call.dialablePhone ? `Rappeler ${call.phoneLabel}` : "Numéro indisponible"}
                    style={{
                      ...S.callIconLink,
                      ...S.callIcon,
                      background: call.iconBg,
                      cursor: call.dialablePhone ? "pointer" : "default",
                      opacity: call.dialablePhone ? 1 : 0.6,
                    }}
                  >
                    <PhoneCall size={22} strokeWidth={2} color={call.iconColor} />
                  </a>

                  <div style={{ minWidth: 0, flex: 1, textAlign: "left" }}>
                    <div style={S.callName}>{call.patientName}</div>
                    <div style={S.callPhone}>{call.phoneLabel}</div>
                    <div style={S.callOutcome}>{call.summary}</div>
                    {call.reasonLabel ? (
                      <div style={S.callReasonRow}>
                        <span
                          style={{
                            ...S.callReasonBadge,
                            background: call.reasonBadge.bg,
                            color: call.reasonBadge.text,
                            borderColor: call.reasonBadge.border,
                          }}
                        >
                          {call.reasonBadge.label}
                        </span>
                        <span style={S.callReasonText}>{call.reasonLabel}</span>
                      </div>
                    ) : null}
                  </div>

                  <div style={S.callMeta}>
                    <div style={S.callTime}>{call.time}</div>
                    <span
                      style={{
                        ...S.statusBadge,
                        background: call.statusBadge.chipBg,
                        color: call.statusBadge.chipText,
                        borderColor: call.statusBadge.chipBorder,
                      }}
                    >
                      {call.statusBadge.label}
                    </span>
                    <div style={S.callDuration}>⏱ {call.duration}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={S.panel} data-tour="appointments-panel">
          <div style={S.panelHeader}>
            <div>
              <div style={S.panelTitle}>Rendez-vous</div>
              <div style={S.panelSubtitle}>
                {agendaLoading
                  ? "Chargement des rendez-vous confirmés"
                  : appointmentItems.length > 0
                    ? "Rendez-vous pris et visibles par le cabinet"
                    : "Les prochains rendez-vous confirmés s'afficheront ici"}
              </div>
            </div>
            <button type="button" onClick={() => onNavigate("/app/agenda")} style={S.linkButton}>
              <span>Voir les RDV</span>
              <ArrowUpRight size={16} strokeWidth={2.2} />
            </button>
          </div>

          <div style={S.agendaList}>
            {agendaLoading ? (
              [1, 2, 3].map((item) => <Skeleton key={item} height={96} radius={16} />)
            ) : appointmentItems.length > 0 ? (
              <>
                {!agendaReady && bookedAgendaCount > 0 ? (
                  <div style={S.agendaNotice}>
                    <div>
                      <div style={S.agendaNoticeTitle}>Rendez-vous UWI bien remontés</div>
                      <div style={S.agendaNoticeText}>
                        Les rendez-vous pris par UWI apparaissent déjà ici, même avant la connexion d&apos;un agenda externe.
                      </div>
                    </div>
                  </div>
                ) : null}

                {appointmentItems.map((item) => (
                  <div key={item.key} style={S.appointmentCard}>
                    <div style={S.appointmentTimeBox}>
                      <div style={S.appointmentTimeValue}>{item.displayTime || "—"}</div>
                    </div>

                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={S.agendaName}>{item.patient}</div>
                      <div style={S.agendaType}>{item.type || "Rendez-vous"}</div>
                      <div style={S.agendaMetaRow}>
                        <span>{item.source === "UWI" ? "Pris par UWI" : "Agenda externe"}</span>
                        <span>{item.done ? "Terminée" : "À venir"}</span>
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
                <div style={S.emptyTitle}>Aucun rendez-vous à venir</div>
                <div style={S.emptyText}>
                  Les rendez-vous pris par le standard apparaîtront ici dès qu&apos;ils seront confirmés.
                </div>
              </div>
            )}
          </div>

          <button type="button" onClick={() => onNavigate("/app/agenda")} style={S.planButton}>
            <Plus size={16} strokeWidth={2.2} />
            <span>Gérer les rendez-vous</span>
          </button>
        </div>
      </section>

      <section style={{ ...S.panel, marginTop: 16 }} data-tour="agenda-panel">
        <div style={S.panelHeader}>
          <div>
            <div style={S.panelTitle}>Agenda</div>
            <div style={S.panelSubtitle}>
              {agendaLoading
                ? "Connexion et synchronisation du cabinet"
                : externalConnected
                  ? "Connexion et synchronisation du cabinet"
                  : "Configuration de l'agenda du cabinet"}
            </div>
          </div>
          <button type="button" onClick={() => onNavigate("/app/agenda")} style={S.linkButton}>
            <span>Ouvrir agenda</span>
            <ArrowUpRight size={16} strokeWidth={2.2} />
          </button>
        </div>

        <div style={S.agendaOverviewGrid}>
          {agendaLoading ? (
            [1, 2, 3].map((item) => (
              <div key={item} style={S.agendaOverviewCard}>
                <Skeleton width={72} height={12} radius={8} />
                <div style={{ marginTop: 12 }}>
                  <Skeleton width={110} height={28} radius={10} />
                </div>
                <div style={{ marginTop: 10 }}>
                  <Skeleton width="100%" height={14} radius={8} />
                </div>
              </div>
            ))
          ) : (
            <>
              <div style={S.agendaOverviewCard}>
                <div style={S.agendaOverviewLabel}>Mode</div>
                <div style={S.agendaOverviewValue}>{externalConnected ? "Google connecté" : "Mode UWI"}</div>
                <div style={S.agendaOverviewText}>
                  {externalConnected
                    ? "Les événements externes remontent dans le tableau de bord."
                    : "UWI gère déjà les rendez-vous en attendant la connexion."}
                </div>
              </div>
              <div style={S.agendaOverviewCard}>
                <div style={S.agendaOverviewLabel}>Rendez-vous UWI</div>
                <div style={S.agendaOverviewValue}>{bookedAgendaCount}</div>
                <div style={S.agendaOverviewText}>Rendez-vous détectés sur la période affichée.</div>
              </div>
              <div style={S.agendaOverviewCard}>
                <div style={S.agendaOverviewLabel}>Agenda externe</div>
                <div style={S.agendaOverviewValue}>{externalAgendaItems.length}</div>
                <div style={S.agendaOverviewText}>
                  {externalConnected
                    ? "Événements synchronisés depuis le calendrier du cabinet."
                    : "Connectez votre agenda pour voir aussi les événements externes."}
                </div>
              </div>
            </>
          )}
        </div>

        <div style={S.agendaOverviewBody}>
          {agendaLoading ? (
            <div style={S.agendaExternalList}>
              {[1, 2].map((item) => (
                <Skeleton key={item} height={72} radius={14} />
              ))}
            </div>
          ) : !agendaReady ? (
            <div style={S.agendaNotice}>
              <div>
                <div style={S.agendaNoticeTitle}>Agenda externe non connecté</div>
                <div style={S.agendaNoticeText}>
                  La section Rendez-vous ci-dessus reste opérationnelle. Cette section Agenda servira à afficher aussi les événements du cabinet.
                </div>
              </div>
            </div>
          ) : null}

          {externalAgendaItems.length > 0 ? (
            <div style={S.agendaExternalList}>
              {externalAgendaItems.map((item) => (
                <div key={item.key} style={S.agendaExternalRow}>
                  <div style={S.agendaExternalTime}>{item.displayTime || "—"}</div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={S.agendaExternalName}>{item.patient}</div>
                    <div style={S.agendaExternalText}>{item.type || "Événement agenda"}</div>
                  </div>
                  <span style={S.agendaExternalBadge}>Externe</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={S.emptyState}>
              <div style={S.emptyTitle}>Aucun événement agenda synchronisé</div>
              <div style={S.emptyText}>
                Cette section affichera les événements de votre agenda connecté sans les mélanger avec les rendez-vous pris par UWI.
              </div>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
