import { Suspense, lazy } from "react";
import { Search } from "lucide-react";

const AppAgendaMiniCalendar = lazy(() => import("./AppAgendaMiniCalendar.jsx"));

const TEXT = "#111827";
const BORDER = "#e5e7eb";
const CARD = "#ffffff";

const S = {
  sidebar: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
    position: "sticky",
    top: 16,
  },
  sidebarCard: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 16,
    padding: 14,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
  },
  sidebarHeroCard: {
    background: "linear-gradient(180deg, #ffffff 0%, #f8fffc 100%)",
    borderColor: "#c7f9e7",
  },
  sidebarHeroTop: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 10,
  },
  sidebarHeroEyebrow: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#94a3b8",
  },
  sidebarHeroTitle: {
    marginTop: 8,
    fontSize: 16,
    lineHeight: 1.25,
    fontWeight: 800,
    color: TEXT,
  },
  sidebarHeroBadge: {
    borderRadius: 999,
    padding: "7px 10px",
    background: "#ecfdf5",
    border: "1px solid #a7f3d0",
    color: "#047857",
    fontSize: 12,
    fontWeight: 800,
    whiteSpace: "nowrap",
  },
  sidebarHeroMeta: {
    marginTop: 12,
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    fontSize: 12,
    color: "#64748b",
  },
  sidebarQuickGrid: {
    marginTop: 14,
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  sidebarQuickButton: {
    border: "1px solid #dbeafe",
    borderRadius: 12,
    background: "#fff",
    color: "#334155",
    fontSize: 12,
    fontWeight: 700,
    padding: "10px 8px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  sidebarTitle: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#94a3b8",
    marginBottom: 10,
  },
  searchBox: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#f8fafc",
    padding: "10px 12px",
  },
  searchInput: {
    border: "none",
    background: "transparent",
    outline: "none",
    width: "100%",
    fontSize: 13,
    color: TEXT,
    fontFamily: "inherit",
  },
  sidebarSegmented: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
  },
  sidebarSegmentButton: {
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    background: "#f8fafc",
    color: "#64748b",
    fontSize: 12,
    fontWeight: 700,
    padding: "10px 0",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  sidebarSegmentActive: {
    border: "1px solid #99f6e4",
    borderRadius: 12,
    background: "linear-gradient(135deg, #14b8a6, #0f766e)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 800,
    padding: "10px 0",
    cursor: "pointer",
    boxShadow: "0 8px 18px rgba(20,184,166,.18)",
    fontFamily: "inherit",
  },
  filterPillGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 8,
  },
  filterPill: {
    width: "100%",
    border: "1px solid #e5e7eb",
    background: "#fff",
    borderRadius: 14,
    padding: "10px 10px 9px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left",
    boxShadow: "0 1px 6px rgba(15,23,42,.03)",
  },
  filterPillActive: {
    background: "#f0fdfa",
    borderColor: "#99f6e4",
    boxShadow: "0 8px 18px rgba(20,184,166,.08)",
  },
  filterPillTop: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    minWidth: 0,
  },
  filterDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    flexShrink: 0,
  },
  filterLabel: {
    flex: 1,
    fontSize: 12,
    fontWeight: 600,
    color: "#334155",
  },
  filterCount: {
    fontSize: 11,
    fontWeight: 700,
    color: "#64748b",
    background: "rgba(148,163,184,.12)",
    borderRadius: 999,
    padding: "2px 8px",
  },
  miniCalendarFooter: {
    marginTop: 10,
    display: "flex",
    justifyContent: "center",
  },
  miniCalendarTodayButton: {
    border: "none",
    background: "transparent",
    color: "#0f766e",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  agentCard: {
    background: "#e8faf4",
    borderColor: "#a7f3d0",
  },
  agentTitle: {
    fontSize: 13,
    fontWeight: 800,
    color: "#0aaf7a",
  },
  agentText: {
    marginTop: 6,
    fontSize: 12,
    lineHeight: 1.5,
    color: "#047857",
  },
  agentStatusRow: {
    marginTop: 10,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    borderRadius: 999,
    background: "#fff",
    border: "1px solid #bbf7d0",
    padding: "5px 10px",
  },
  agentStatusDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "#10b981",
  },
  agentStatusText: {
    fontSize: 11,
    fontWeight: 800,
    color: "#047857",
  },
};

export default function AppAgendaSidebar({
  selectedDateLabel,
  selectedDayCount,
  selectedDayAiCount,
  viewMode,
  onSetViewMode,
  onSelectDate,
  todayIso,
  tomorrowIso,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  sidebarStats,
  selectedDate,
  isConnected,
}) {
  return (
    <aside style={S.sidebar}>
      <div style={{ ...S.sidebarCard, ...S.sidebarHeroCard }}>
        <div style={S.sidebarHeroTop}>
          <div>
            <div style={S.sidebarHeroEyebrow}>Date selectionnee</div>
            <div style={S.sidebarHeroTitle}>{selectedDateLabel}</div>
          </div>
          <div style={S.sidebarHeroBadge}>{selectedDayCount} RDV</div>
        </div>
        <div style={S.sidebarHeroMeta}>
          <span>{selectedDayAiCount} pris par UWI</span>
          <span>{viewMode === "month" ? "Vue mois" : viewMode === "day" ? "Vue jour" : "Vue semaine"}</span>
        </div>
        <div style={S.sidebarQuickGrid}>
          <button type="button" onClick={() => { onSelectDate(todayIso); onSetViewMode("day"); }} style={S.sidebarQuickButton}>
            Aujourd'hui
          </button>
          <button type="button" onClick={() => { onSelectDate(tomorrowIso); onSetViewMode("day"); }} style={S.sidebarQuickButton}>
            Demain
          </button>
          <button type="button" onClick={() => { onSelectDate(todayIso); onSetViewMode("week"); }} style={S.sidebarQuickButton}>
            Cette semaine
          </button>
          <button type="button" onClick={() => { onSelectDate(todayIso); onSetViewMode("month"); }} style={S.sidebarQuickButton}>
            Ce mois
          </button>
        </div>
      </div>

      <div style={S.sidebarCard}>
        <div style={S.sidebarTitle}>Vue</div>
        <div style={S.sidebarSegmented}>
          <button type="button" onClick={() => onSetViewMode("day")} style={viewMode === "day" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
            Jour
          </button>
          <button type="button" onClick={() => onSetViewMode("week")} style={viewMode === "week" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
            Semaine
          </button>
          <button type="button" onClick={() => onSetViewMode("month")} style={viewMode === "month" ? S.sidebarSegmentActive : S.sidebarSegmentButton}>
            Mois
          </button>
        </div>
      </div>

      <div style={S.sidebarCard}>
        <div style={S.sidebarTitle}>Recherche</div>
        <div style={S.searchBox}>
          <Search size={15} strokeWidth={2.2} color="#94a3b8" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Rechercher un patient..."
            style={S.searchInput}
          />
        </div>
      </div>

      <div style={S.sidebarCard}>
        <div style={S.sidebarTitle}>Filtrer</div>
        <div style={S.filterPillGrid}>
          {[
            ["all", "Tous", "#94a3b8", sidebarStats.all],
            ["confirmed", "Confirmes", "#0dc991", sidebarStats.confirmed],
            ["pending", "En attente", "#f97316", sidebarStats.pending],
            ["ai_booked", "Via IA", "#8b5cf6", sidebarStats.ai_booked],
            ["arrived", "Arrives", "#10b981", sidebarStats.arrived],
          ].map(([value, label, dot, count]) => {
            const active = statusFilter === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => setStatusFilter(value)}
                style={{
                  ...S.filterPill,
                  ...(active ? S.filterPillActive : null),
                }}
              >
                <span style={S.filterPillTop}>
                  <span style={{ ...S.filterDot, background: dot }} />
                  <span style={S.filterLabel}>{label}</span>
                </span>
                <span style={S.filterCount}>{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div style={S.sidebarCard}>
        <div style={S.sidebarTitle}>Calendrier</div>
        <Suspense fallback={<div style={{ minHeight: 290 }} />}>
          <AppAgendaMiniCalendar selectedDate={selectedDate} onSelect={onSelectDate} />
        </Suspense>
        <div style={S.miniCalendarFooter}>
          <button type="button" onClick={() => onSelectDate(todayIso)} style={S.miniCalendarTodayButton}>
            Revenir a aujourd'hui
          </button>
        </div>
      </div>

      <div style={{ ...S.sidebarCard, ...S.agentCard }}>
        <div style={S.agentTitle}>{isConnected ? "Agenda connecte" : "Agenda UWI actif"}</div>
        <div style={S.agentText}>
          <b>{sidebarStats.ai_booked}</b> rendez-vous geres par UWI sur la periode affichee.
        </div>
        <div style={S.agentText}>
          {isConnected ? "Google Calendar est bien synchronise." : "Le planning UWI continue de fonctionner meme sans Google."}
        </div>
        <div style={S.agentStatusRow}>
          <span style={S.agentStatusDot} />
          <span style={S.agentStatusText}>{viewMode === "month" ? "Mode mois" : viewMode === "day" ? "Mode jour" : "Mode semaine"}</span>
        </div>
      </div>
    </aside>
  );
}
