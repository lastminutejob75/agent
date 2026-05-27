import { ArrowUpRight } from "lucide-react";

const NAVY = "#111827";

function Skeleton({ height = 90, radius = 14 }) {
  return (
    <div
      style={{
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
  panelHeader: {
    padding: "18px 18px 14px",
    borderBottom: "1px solid #e5e7eb",
    background: "#fafafa",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
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
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 10,
    padding: "9px 11px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    flexShrink: 0,
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
    lineHeight: 1.6,
  },
};

export default function AppDashboardWorkflowSection({
  callsLoading,
  actionQueueItems,
  onboardingProgress,
  onboardingCards,
  quickLinks,
  onNavigate,
}) {
  return (
    <>
      <section className="uwi-activation-grid" style={S.activationGrid}>
        <div style={S.actionsPanel}>
          <div style={S.panelHeader}>
            <div>
              <div style={S.panelTitle}>A traiter maintenant</div>
              <div style={S.panelSubtitle}>La file de travail prioritaire du cabinet</div>
            </div>
            <button type="button" onClick={() => onNavigate("/app/appels")} style={S.linkButton}>
              <span>Ouvrir Appels</span>
              <ArrowUpRight size={16} strokeWidth={2.2} />
            </button>
          </div>

          <div style={S.actionQueueList}>
            {callsLoading ? (
              [1, 2, 3].map((item) => <Skeleton key={item} height={90} radius={14} />)
            ) : actionQueueItems.length === 0 ? (
              <div style={S.emptyState}>
                <div style={S.emptyTitle}>Aucune action urgente</div>
                <div style={S.emptyText}>Les demandes prioritaires apparaitront ici des qu'elles necessiteront un suivi.</div>
              </div>
            ) : (
              actionQueueItems.map((call) => (
                <div key={call.call_id || call.id} style={S.actionQueueCard}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={S.actionQueueTop}>
                      <span
                        style={{
                          ...S.actionQueueBadge,
                          background: call.badge.bg,
                          color: call.badge.text,
                          borderColor: call.badge.border,
                        }}
                      >
                        {call.badge.label}
                      </span>
                      <span style={S.actionQueueTime}>{call.time || "-"}</span>
                    </div>
                    <div style={S.actionQueueTitle}>{call.patient_name || "Patient"}</div>
                    <div style={S.actionQueueText}>{call.reason_label || call.summary || "Suivi patient"}</div>
                  </div>
                  <button type="button" onClick={() => onNavigate(call.targetHref)} style={S.actionQueueButton}>
                    {call.ctaLabel}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={S.activationPanel} data-tour="activation-panel">
          <div style={S.panelHeader}>
            <div>
              <div style={S.panelTitle}>Activation du cabinet</div>
              <div style={S.panelSubtitle}>Les prochains reglages qui debloquent l'autonomie du standard</div>
            </div>
            <div style={S.progressWrap}>
              <div style={S.progressLabel}>{onboardingProgress}% pret</div>
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
                  <button type="button" onClick={() => onNavigate(item.href)} style={item.done ? S.activationButtonGhost : S.activationButton}>
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

      <section className="uwi-quick-links" style={S.quickLinks} data-tour="quick-links">
        {quickLinks.map((item) => (
          <button key={item.href} type="button" onClick={() => onNavigate(item.href)} style={S.quickLinkCard}>
            <div style={S.quickLinkTitle}>{item.label}</div>
            <div style={S.quickLinkText}>{item.sub}</div>
          </button>
        ))}
      </section>
    </>
  );
}
