import { useEffect, useMemo, useState } from "react";
import { Outlet, useMatch, useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../lib/api.js";
import { patientDashboardFileHasValidatedIdentity } from "../lib/callsService.js";

const NAVY = "#111827";
const TEAL = "#0DC991";
const TEAL_DARK = "#0AAF7A";
const BLUE = "#2563EB";
const BORDER = "#e5e7eb";

function formatPhone(phone) {
  const raw = String(phone || "").trim();
  if (!raw) return "—";
  if (raw.startsWith("+33") && raw.length === 12)
    return `0${raw.slice(3, 4)} ${raw.slice(4, 6)} ${raw.slice(6, 8)} ${raw.slice(8, 10)} ${raw.slice(10)}`;
  return raw;
}

function timeAgo(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Date.now() - date.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return `${days}j`;
  if (days < 30) return `${Math.floor(days / 7)} sem.`;
  return `${Math.floor(days / 30)} mois`;
}

function deriveStatus(patient) {
  const now = Date.now();
  const updatedAt = new Date(patient.updated_at || 0).getTime();
  const createdAt = new Date(patient.created_at || 0).getTime();
  const daysSinceUpdate = (now - updatedAt) / 86400000;
  const daysSinceCreation = (now - createdAt) / 86400000;
  if (daysSinceCreation < 14 && !patientDashboardFileHasValidatedIdentity(patient)) return "new";
  if (daysSinceUpdate > 60) return "inactive";
  return "active";
}

const STATUS_DOT = { active: "#22c55e", new: "#f59e0b", inactive: "#cbd5e1" };

export function usePatientListContext() {
  return useOutletContext();
}

export default function AppPatientsLayout() {
  const navigate = useNavigate();
  const match = useMatch("/app/patients/:phone");
  const selectedPhone = match?.params?.phone ? decodeURIComponent(match.params.phone) : null;

  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.tenantGetPatients("?limit=500")
      .then((data) => { if (!cancelled) setPatients(data?.items || []); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const enriched = useMemo(() =>
    patients.map((p) => ({ ...p, _status: deriveStatus(p) })),
    [patients],
  );

  const stats = useMemo(() => ({
    total: enriched.length,
    active: enriched.filter((p) => p._status === "active").length,
    new: enriched.filter((p) => p._status === "new").length,
    unconfirmed: enriched.filter((p) => !patientDashboardFileHasValidatedIdentity(p)).length,
    inactive: enriched.filter((p) => p._status === "inactive").length,
  }), [enriched]);

  const filtered = useMemo(() => {
    return enriched.filter((p) => {
      const haystack = `${p.display_name} ${p.raw_name} ${p.validated_name} ${p.phone} ${p.last_booking_motif}`.toLowerCase();
      const matchSearch = !search.trim() || haystack.includes(search.trim().toLowerCase());
      let matchFilter = true;
      if (filter === "active") matchFilter = p._status === "active";
      else if (filter === "new") matchFilter = p._status === "new";
      else if (filter === "inactive") matchFilter = p._status === "inactive";
      else if (filter === "unconfirmed") matchFilter = !patientDashboardFileHasValidatedIdentity(p);
      return matchSearch && matchFilter;
    });
  }, [enriched, search, filter]);

  const selectedIndex = useMemo(() => {
    if (!selectedPhone) return -1;
    return filtered.findIndex((p) => p.phone === selectedPhone);
  }, [filtered, selectedPhone]);

  function goToPatient(phone) {
    navigate(`/app/patients/${encodeURIComponent(phone)}`);
  }

  function goPrev() {
    if (selectedIndex > 0) goToPatient(filtered[selectedIndex - 1].phone);
  }
  function goNext() {
    if (selectedIndex >= 0 && selectedIndex < filtered.length - 1) goToPatient(filtered[selectedIndex + 1].phone);
  }

  const FILTERS = [
    ["all", "Tous", stats.total],
    ["active", "Actifs", stats.active],
    ["new", "Nouveaux", stats.new],
    ["unconfirmed", "À valider", stats.unconfirmed],
  ];

  const outletContext = {
    patients: enriched,
    filtered,
    selectedIndex,
    goPrev,
    goNext,
    hasPrev: selectedIndex > 0,
    hasNext: selectedIndex >= 0 && selectedIndex < filtered.length - 1,
    refreshPatients: () => {
      api.tenantGetPatients("?limit=500")
        .then((data) => setPatients(data?.items || []))
        .catch(() => {});
    },
    updatePatientInList: (phone, updates) => {
      setPatients((prev) => prev.map((p) => p.phone === phone ? { ...p, ...updates } : p));
    },
  };

  return (
    <div style={S.container}>
      <style>{CSS}</style>

      {/* ─── LEFT: Patient list sidebar ─── */}
      <div className={`patients-sidebar ${selectedPhone ? "has-selection" : ""}`} style={S.sidebar}>
        {/* Sidebar header */}
        <div style={S.sidebarHeader}>
          <h2 style={S.sidebarTitle}>Patients</h2>
          <span style={S.sidebarCount}>{stats.total}</span>
        </div>

        {/* Search */}
        <div style={S.searchBox}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher…"
            style={S.searchInput}
          />
          {search ? <button type="button" onClick={() => setSearch("")} style={S.clearBtn}>✕</button> : null}
        </div>

        {/* Filters */}
        <div style={S.filterRow}>
          {FILTERS.map(([key, label, count]) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className="filter-pill"
              style={filter === key ? S.filterActive : S.filterBtn}
            >
              {label} <span style={S.filterCount}>{count}</span>
            </button>
          ))}
        </div>

        {/* Patient list */}
        <div className="patient-list-scroll" style={S.listScroll}>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={S.skeletonRow}><div style={S.skeleton} /></div>
            ))
          ) : filtered.length === 0 ? (
            <div style={S.emptyList}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>👤</div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Aucun patient trouvé</div>
            </div>
          ) : (
            filtered.map((patient) => {
              const isActive = patient.phone === selectedPhone;
              const dotColor = STATUS_DOT[patient._status] || "#cbd5e1";
              return (
                <div
                  key={patient.phone}
                  className={`sidebar-patient ${isActive ? "active" : ""}`}
                  style={{ ...S.patientItem, ...(isActive ? S.patientItemActive : {}) }}
                  onClick={() => goToPatient(patient.phone)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") goToPatient(patient.phone); }}
                >
                  <div style={{ ...S.miniAvatar, background: patientDashboardFileHasValidatedIdentity(patient) ? `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})` : "linear-gradient(135deg, #fbbf24, #f59e0b)" }}>
                    {(patient.display_name || "?")[0]?.toUpperCase()}
                  </div>
                  <div style={S.patientInfo}>
                    <div style={S.patientName}>{patient.display_name || patient.raw_name || "Inconnu"}</div>
                    <div style={S.patientMeta}>
                      <span style={{ ...S.statusDot, background: dotColor }} />
                      <span>{formatPhone(patient.phone)}</span>
                      {patient.updated_at ? <><span style={S.sep}>·</span><span>{timeAgo(patient.updated_at)}</span></> : null}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ─── RIGHT: Content area ─── */}
      <div className="patients-main" style={S.main}>
        {selectedPhone ? (
          <Outlet context={outletContext} />
        ) : (
          /* Welcome / index screen */
          <div style={S.welcomeContainer}>
            <div style={S.welcomeCard}>
              <div style={S.welcomeIcon}>👤</div>
              <h2 style={S.welcomeTitle}>Sélectionnez un patient</h2>
              <p style={S.welcomeText}>
                Choisissez un patient dans la liste pour voir sa fiche complète,
                son historique d'interactions et ses demandes.
              </p>
              <div style={S.welcomeStats}>
                <div style={S.welcomeStat}>
                  <div style={S.welcomeStatNum}>{stats.total}</div>
                  <div style={S.welcomeStatLabel}>Patients</div>
                </div>
                <div style={S.welcomeStat}>
                  <div style={{ ...S.welcomeStatNum, color: "#22c55e" }}>{stats.active}</div>
                  <div style={S.welcomeStatLabel}>Actifs</div>
                </div>
                <div style={S.welcomeStat}>
                  <div style={{ ...S.welcomeStatNum, color: "#f59e0b" }}>{stats.new}</div>
                  <div style={S.welcomeStatLabel}>Nouveaux</div>
                </div>
                <div style={S.welcomeStat}>
                  <div style={{ ...S.welcomeStatNum, color: "#94a3b8" }}>{stats.unconfirmed}</div>
                  <div style={S.welcomeStatLabel}>À valider</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const SIDEBAR_W = 310;

const S = {
  container: { display: "flex", height: "100%", minHeight: 0, background: "#f9fafb", fontFamily: "'Inter', 'DM Sans', sans-serif", color: NAVY },

  // Sidebar
  sidebar: { width: SIDEBAR_W, flexShrink: 0, background: "#fff", borderRight: `1px solid ${BORDER}`, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" },
  sidebarHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 16px 0" },
  sidebarTitle: { margin: 0, fontSize: 16, fontWeight: 800, color: NAVY },
  sidebarCount: { fontSize: 12, fontWeight: 600, color: "#94a3b8", background: "#f1f5f9", padding: "2px 10px", borderRadius: 999 },

  searchBox: { display: "flex", alignItems: "center", gap: 8, margin: "12px 16px 8px", background: "#f9fafb", border: `1px solid ${BORDER}`, borderRadius: 8, padding: "7px 10px" },
  searchInput: { border: "none", background: "transparent", fontSize: 13, color: NAVY, outline: "none", width: "100%", fontFamily: "inherit" },
  clearBtn: { background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 11, padding: 0, fontFamily: "inherit" },

  filterRow: { display: "flex", gap: 4, padding: "0 16px 10px", flexWrap: "wrap" },
  filterBtn: { padding: "4px 9px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "#fff", color: "#6b7280", fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 4 },
  filterActive: { padding: "4px 9px", borderRadius: 6, border: `1px solid ${BLUE}`, background: "#eff6ff", color: BLUE, fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 4 },
  filterCount: { fontSize: 10, opacity: 0.6, fontWeight: 500 },

  listScroll: { flex: 1, overflowY: "auto", overflowX: "hidden" },
  skeletonRow: { padding: "10px 16px" },
  skeleton: { height: 40, borderRadius: 8, background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)", backgroundSize: "200% 100%", animation: "uwi-pl-shimmer 1.35s infinite linear" },
  emptyList: { padding: "32px 16px", textAlign: "center" },

  patientItem: { display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", cursor: "pointer", borderBottom: `1px solid #f8f8f8`, borderLeft: "3px solid transparent" },
  patientItemActive: { background: "#f0fdf4", borderLeftColor: TEAL },
  miniAvatar: { width: 32, height: 32, borderRadius: 8, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, flexShrink: 0 },
  patientInfo: { flex: 1, minWidth: 0 },
  patientName: { fontSize: 13, fontWeight: 700, color: NAVY, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  patientMeta: { display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#94a3b8", marginTop: 2 },
  statusDot: { width: 6, height: 6, borderRadius: "50%", flexShrink: 0 },
  sep: { color: "#d1d5db" },

  // Main
  main: { flex: 1, overflow: "auto", minWidth: 0 },

  // Welcome
  welcomeContainer: { display: "flex", alignItems: "center", justifyContent: "center", height: "100%", padding: 24 },
  welcomeCard: { textAlign: "center", maxWidth: 400 },
  welcomeIcon: { fontSize: 48, marginBottom: 16 },
  welcomeTitle: { margin: "0 0 8px", fontSize: 20, fontWeight: 800, color: NAVY },
  welcomeText: { margin: "0 0 24px", fontSize: 14, color: "#6b7280", lineHeight: 1.5 },
  welcomeStats: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 },
  welcomeStat: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "14px 8px" },
  welcomeStatNum: { fontSize: 22, fontWeight: 800, color: NAVY },
  welcomeStatLabel: { fontSize: 11, color: "#6b7280", marginTop: 2 },
};

const CSS = `
  @keyframes uwi-pl-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .sidebar-patient { transition: background .08s ease; }
  .sidebar-patient:hover { background: #fafafa; }
  .sidebar-patient.active:hover { background: #f0fdf4; }
  .filter-pill { transition: all .08s ease; }
  .patient-list-scroll::-webkit-scrollbar { width: 4px; }
  .patient-list-scroll::-webkit-scrollbar-track { background: transparent; }
  .patient-list-scroll::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 4px; }
  .patient-list-scroll::-webkit-scrollbar-thumb:hover { background: #cbd5e1; }
  @media (max-width: 768px) {
    .patients-sidebar { position: fixed; left: 0; top: 0; bottom: 0; z-index: 40; width: 100% !important; transform: translateX(0); transition: transform .2s ease; }
    .patients-sidebar.has-selection { transform: translateX(-100%); }
    .patients-main { width: 100% !important; }
  }
`;
