import { ArrowUpRight } from "lucide-react";

const NAVY = "#111827";

function Skeleton({ width = "100%", height = 16, radius = 12 }) {
  return (
    <div style={{ width, height, borderRadius: radius, background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)", backgroundSize: "200% 100%", animation: "uwi-shimmer 1.35s infinite linear" }} />
  );
}

const S = {
  grid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, 1fr)",
    gap: 16,
    marginTop: 18,
  },
  card: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 1px 4px rgba(15,23,42,.03)",
  },
  cardHeader: {
    padding: "16px 18px 12px",
    borderBottom: "1px solid #f1f5f9",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: NAVY,
  },
  cardSub: { marginTop: 2, fontSize: 11, color: "#94a3b8" },
  linkBtn: {
    border: "1px solid #e5e7eb",
    background: "#fff",
    color: "#475569",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    borderRadius: 8,
    padding: "6px 10px",
  },
  list: {
    padding: 0,
    margin: 0,
  },
  callRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 18px",
    borderBottom: "1px solid #f1f5f9",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  callDot: {
    width: 4,
    minHeight: 32,
    borderRadius: 2,
    flexShrink: 0,
  },
  callIntent: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: "#f8fafc",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 14,
    flexShrink: 0,
  },
  callMain: {
    flex: 1,
    minWidth: 0,
  },
  callName: { fontSize: 13, fontWeight: 700, color: NAVY, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  callSummary: { marginTop: 2, fontSize: 11, color: "#64748b", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  callMeta: { textAlign: "right", flexShrink: 0 },
  callTime: {
    fontSize: 13,
    fontWeight: 700,
    color: "#374151",
  },
  callDuration: {
    marginTop: 2,
    fontSize: 10,
    color: "#94a3b8",
    fontWeight: 600,
  },
  callBadge: {
    marginTop: 4,
    display: "inline-block",
    padding: "2px 7px",
    borderRadius: 10,
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid",
  },
  rdvRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "10px 18px",
    borderBottom: "1px solid #f1f5f9",
    cursor: "pointer",
  },
  rdvTime: {
    width: 52,
    height: 44,
    borderRadius: 10,
    background: "linear-gradient(135deg, #009CA4, #0DC991)",
    color: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  rdvTimeVal: {
    fontSize: 14,
    fontWeight: 800,
    lineHeight: 1,
  },
  rdvDateLabel: {
    fontSize: 8,
    fontWeight: 600,
    opacity: 0.85,
    marginTop: 2,
    textTransform: "uppercase",
  },
  rdvMain: { flex: 1, minWidth: 0 },
  rdvName: { fontSize: 13, fontWeight: 700, color: NAVY },
  rdvType: { marginTop: 2, fontSize: 11, color: "#64748b" },
  actionButton: {
    border: "1px solid #e5e7eb",
    borderRadius: 9,
    background: "#fff",
    color: "#0f172a",
    fontSize: 11,
    fontWeight: 700,
    padding: "5px 10px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  empty: {
    padding: "32px 18px",
    textAlign: "center",
  },
  emptyIcon: {
    fontSize: 28,
    marginBottom: 6,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: NAVY,
  },
  emptyText: {
    marginTop: 4,
    fontSize: 12,
    color: "#94a3b8",
  },
};

export default function AppDashboardMainPanels({
  callsLoading,
  recentCallItems,
  agendaLoading,
  appointmentItems,
  onNavigate,
}) {
  const actionItems = recentCallItems.map((call) => {
    const tone =
      call.statusBadge.label === "Manqué"
        ? { bg: "#fef2f2", border: "#fecaca", text: "#b91c1c", ctaBg: "#dc2626", cta: "Appeler" }
        : call.intent.label === "RDV"
          ? { bg: "#eff6ff", border: "#bfdbfe", text: "#1d4ed8", ctaBg: "#009CA4", cta: "Proposer" }
          : { bg: "#f8fafc", border: "#e2e8f0", text: "#334155", ctaBg: "#ffffff", cta: "Voir" };
    return { ...call, tone };
  });

  return (
    <section className="uwi-main-grid" style={S.grid}>
      <div style={S.card}>
        <div style={S.cardHeader}>
          <div>
            <div style={S.cardTitle}>À traiter</div>
            <div style={S.cardSub}>{actionItems.length > 0 ? `${actionItems.length} actions en attente de votre décision` : "Aucune action urgente"}</div>
          </div>
          <button type="button" onClick={() => onNavigate("/app/demandes")} style={S.linkBtn}>
            <span>Tout voir</span>
            <ArrowUpRight size={14} strokeWidth={2.2} />
          </button>
        </div>

        <div style={S.list}>
          {callsLoading ? (
            <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              {[1, 2, 3].map((i) => <Skeleton key={i} height={56} />)}
            </div>
          ) : actionItems.length === 0 ? (
            <div style={S.empty}>
              <div style={S.emptyIcon}>✅</div>
              <div style={S.emptyTitle}>Aucune action en attente</div>
              <div style={S.emptyText}>Clara a déjà traité toutes les demandes urgentes.</div>
            </div>
          ) : (
            actionItems.map((call, i, arr) => (
              <div
                key={call.id}
                role="button"
                tabIndex={0}
                onClick={() => onNavigate("/app/demandes")}
                onKeyDown={(e) => { if (e.key === "Enter") onNavigate("/app/demandes"); }}
                style={{
                  ...S.callRow,
                  borderBottom: i === arr.length - 1 ? "none" : S.callRow.borderBottom,
                  background: call.tone.bg,
                  borderLeft: `3px solid ${call.tone.border}`,
                }}
                className="uwi-call-row"
              >
                <div style={{ ...S.callDot, background: call.tone.text }} />
                <div style={S.callIntent}>{call.intent.icon}</div>
                <div style={S.callMain}>
                  <div style={S.callName}>{call.name}</div>
                  <div style={S.callSummary}>
                    {call.summary
                      ? call.summary.length > 60 ? `${call.summary.slice(0, 60)}…` : call.summary
                      : call.phone}
                  </div>
                </div>
                <div style={S.callMeta}>
                  <div style={S.callTime}>{call.time}</div>
                  <div style={S.callDuration}>{call.duration}</div>
                  <span style={{ ...S.callBadge, background: "#fff", color: call.tone.text, borderColor: call.tone.border }}>
                    {call.statusBadge.label === "Manqué" ? "Prioritaire" : call.intent.label}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onNavigate("/app/demandes"); }}
                  style={{
                    ...S.actionButton,
                    background: call.tone.ctaBg,
                    color: call.tone.ctaBg === "#ffffff" ? "#0f172a" : "#fff",
                    borderColor: call.tone.ctaBg === "#ffffff" ? "#e5e7eb" : call.tone.ctaBg,
                  }}
                >
                  {call.tone.cta}
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <div style={S.card}>
        <div style={S.cardHeader}>
          <div>
            <div style={S.cardTitle}>Agenda du jour</div>
            <div style={S.cardSub}>
              {agendaLoading ? "Chargement…" : appointmentItems.length > 0 ? `${appointmentItems.length} rendez-vous aujourd'hui` : "Aucun RDV planifié"}
            </div>
          </div>
          <button type="button" onClick={() => onNavigate("/app/agenda")} style={S.linkBtn}>
            <span>Ouvrir l'agenda</span>
            <ArrowUpRight size={14} strokeWidth={2.2} />
          </button>
        </div>

        <div style={S.list}>
          {agendaLoading ? (
            <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              {[1, 2, 3].map((i) => <Skeleton key={i} height={52} />)}
            </div>
          ) : appointmentItems.length > 0 ? (
            appointmentItems.map((item, i, arr) => (
              <div
                key={item.key}
                role="button"
                tabIndex={0}
                onClick={() => onNavigate("/app/agenda")}
                onKeyDown={(e) => { if (e.key === "Enter") onNavigate("/app/agenda"); }}
                style={{ ...S.rdvRow, borderBottom: i === arr.length - 1 ? "none" : S.rdvRow.borderBottom }}
                className="uwi-call-row"
              >
                <div style={S.rdvTime}>
                  <div style={S.rdvTimeVal}>{item.displayTime || "—"}</div>
                  {item.displayDate && <div style={S.rdvDateLabel}>{item.displayDate}</div>}
                </div>
                <div style={S.rdvMain}>
                  <div style={S.rdvName}>{item.patient || "Patient"}</div>
                  <div style={S.rdvType}>{item.type || item.motif || "Consultation"}</div>
                </div>
              </div>
            ))
          ) : (
            <div style={S.empty}>
              <div style={S.emptyIcon}>📅</div>
              <div style={S.emptyTitle}>Aucun rendez-vous</div>
              <div style={S.emptyText}>Les prochains RDV apparaîtront ici.</div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
