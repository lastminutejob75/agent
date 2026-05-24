import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { patientDashboardFileHasValidatedIdentity } from "../lib/callsService.js";

const NAVY = "#111827";
const TEAL = "#0DC991";
const TEAL_DARK = "#0AAF7A";
const BORDER = "#e5e7eb";
const BLUE = "#2563EB";

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
  if (days < 7) return `Il y a ${days}j`;
  if (days < 30) return `Il y a ${Math.floor(days / 7)} sem.`;
  if (days < 365) return `Il y a ${Math.floor(days / 30)} mois`;
  return `Il y a ${Math.floor(days / 365)} an(s)`;
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

const STATUS_CONFIG = {
  active: { label: "Actif", color: "#22c55e", bg: "#dcfce7" },
  new: { label: "Nouveau", color: "#f59e0b", bg: "#fef3c7" },
  inactive: { label: "Inactif", color: "#94a3b8", bg: "#f1f5f9" },
};

export default function AppPatients() {
  const navigate = useNavigate();
  const openPatientDashboard = (phone) => {
    const params = new URLSearchParams();
    params.set("phone", phone);
    navigate(`/app/patient-dashboard?${params.toString()}`);
  };
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [editingPhone, setEditingPhone] = useState("");
  const [editDraft, setEditDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api.tenantGetPatients("?limit=500")
      .then((data) => { if (!cancelled) setPatients(data?.items || []); })
      .catch((e) => { if (!cancelled) setError(e?.message || "Impossible de charger les patients."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!toast) return undefined;
    const t = window.setTimeout(() => setToast(""), 2500);
    return () => window.clearTimeout(t);
  }, [toast]);

  const enriched = useMemo(() =>
    patients.map((p) => ({ ...p, _status: deriveStatus(p) })),
    [patients],
  );

  const stats = useMemo(() => ({
    total: enriched.length,
    active: enriched.filter((p) => p._status === "active").length,
    new: enriched.filter((p) => p._status === "new").length,
    inactive: enriched.filter((p) => p._status === "inactive").length,
    unconfirmed: enriched.filter((p) => !patientDashboardFileHasValidatedIdentity(p)).length,
  }), [enriched]);

  const filtered = useMemo(() => {
    return enriched.filter((p) => {
      const haystack = `${p.display_name} ${p.raw_name} ${p.validated_name} ${p.phone} ${p.last_booking_motif}`.toLowerCase();
      const matchSearch = !search.trim() || haystack.includes(search.trim().toLowerCase());
      let matchFilter = true;
      if (filter === "active") matchFilter = p._status === "active";
      else if (filter === "new") matchFilter = p._status === "new";
      else if (filter === "inactive") matchFilter = p._status === "inactive";
      else if (filter === "unconfirmed") matchFilter = !patientIdentityValidated(p);
      return matchSearch && matchFilter;
    });
  }, [enriched, search, filter]);

  async function confirmName(patient) {
    const name = editDraft.trim();
    if (name.length < 2) {
      setToast("Le nom doit contenir au moins 2 caractères.");
      return;
    }
    const callId = patient.source_call_id || patient.last_call_id;
    setSaving(true);
    try {
      if (callId) {
        await api.tenantUpdateCallPatient(callId, { validated_name: name, raw_name: patient.raw_name || "" });
      } else {
        await api.tenantRegisterPatient({
          patient_phone: patient.phone,
          validated_name: name,
          raw_name: (patient.raw_name || patient.display_name || "").trim() || name,
        });
      }
      setPatients((prev) =>
        prev.map((p) =>
          p.phone === patient.phone
            ? { ...p, validated_name: name, display_name: name, validation_status: "validated" }
            : p,
        ),
      );
      setEditingPhone("");
      setToast(`Nom validé sur la fiche : ${name}`);
    } catch (e) {
      setToast(e?.message || "Erreur");
    } finally {
      setSaving(false);
    }
  }

  const FILTERS = [
    ["all", `Tous`, stats.total],
    ["active", `Actifs`, stats.active],
    ["new", `Nouveaux`, stats.new],
    ["unconfirmed", `À valider`, stats.unconfirmed],
    ["inactive", `Inactifs`, stats.inactive],
  ];

  return (
    <div style={S.page}>
      <style>{CSS}</style>

      {/* HEADER */}
      <div style={S.header}>
        <div>
          <h1 style={S.title}>Patients</h1>
          <p style={S.subtitle}>{stats.total} patient{stats.total > 1 ? "s" : ""} enregistré{stats.total > 1 ? "s" : ""}</p>
        </div>
      </div>

      {toast ? <div style={S.toast}>{toast}</div> : null}

      {/* SEARCH + FILTERS */}
      <div style={S.toolbar}>
        <div style={S.searchBox}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher par nom, téléphone, motif…"
            style={S.searchInput}
          />
          {search ? <button type="button" onClick={() => setSearch("")} style={S.clearBtn}>✕</button> : null}
        </div>
        <div style={S.filterRow}>
          {FILTERS.map(([key, label, count]) => (
            <button key={key} type="button" onClick={() => setFilter(key)} className="filter-chip" style={filter === key ? S.filterActive : S.filterBtn}>
              {label} <span style={S.filterCount}>{count}</span>
            </button>
          ))}
        </div>
      </div>

      {error ? <div style={S.errorBox}>{error}</div> : null}

      {/* LIST */}
      <div style={S.listContainer}>
        {/* Table header */}
        <div style={S.listHeader}>
          <span style={{ ...S.colPatient }}>Patient</span>
          <span style={S.colStatus}>Statut</span>
          <span style={S.colContact}>Dernier contact</span>
          <span style={S.colMotif}>Motif</span>
          <span style={S.colAction} />
        </div>

        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={S.row}><div style={S.skeleton} /></div>
          ))
        ) : filtered.length === 0 ? (
          <div style={S.empty}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>👤</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: NAVY }}>Aucun patient trouvé</div>
            <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>Les patients apparaîtront ici après leur premier appel.</div>
          </div>
        ) : (
          filtered.map((patient) => {
            const isEditing = editingPhone === patient.phone;
            const isValidated = patientDashboardFileHasValidatedIdentity(patient);
            const st = STATUS_CONFIG[patient._status];

            return (
              <div
                key={patient.phone}
                className="patient-row"
                style={S.row}
                onClick={() => !isEditing && openPatientDashboard(patient.phone)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (!isEditing && e.key === "Enter") openPatientDashboard(patient.phone); }}
              >
                {/* Patient identity */}
                <div style={S.colPatient}>
                  <div style={{ ...S.avatar, background: isValidated ? `linear-gradient(135deg, ${TEAL}, ${TEAL_DARK})` : "linear-gradient(135deg, #fbbf24, #f59e0b)" }}>
                    {(patient.display_name || "?")[0]?.toUpperCase()}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    {isEditing ? (
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }} onClick={(e) => e.stopPropagation()}>
                        <input
                          value={editDraft}
                          onChange={(e) => setEditDraft(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") confirmName(patient); if (e.key === "Escape") setEditingPhone(""); }}
                          autoFocus
                          style={S.editInput}
                        />
                        <button type="button" onClick={() => confirmName(patient)} disabled={saving} style={S.confirmBtn}>{saving ? "…" : "✓"}</button>
                        <button type="button" onClick={() => setEditingPhone("")} style={S.cancelBtn}>✕</button>
                      </div>
                    ) : (
                      <>
                        <div style={S.patientName}>{patient.display_name || patient.raw_name || "Inconnu"}</div>
                        <a href={`tel:${patient.phone}`} style={S.phoneLink} onClick={(e) => e.stopPropagation()}>{formatPhone(patient.phone)}</a>
                      </>
                    )}
                  </div>
                </div>

                {/* Status */}
                <div style={S.colStatus}>
                  <span style={{ ...S.statusBadge, color: st.color, background: st.bg }}>{st.label}</span>
                  {!isValidated && (
                    <span style={S.unconfirmedBadge}>Identité à valider</span>
                  )}
                </div>

                {/* Last contact */}
                <div style={S.colContact}>
                  <span style={S.contactDate}>{timeAgo(patient.updated_at)}</span>
                </div>

                {/* Motif */}
                <div style={S.colMotif}>
                  {patient.last_booking_motif ? (
                    <span style={S.motifText}>{patient.last_booking_motif}</span>
                  ) : (
                    <span style={S.motifEmpty}>—</span>
                  )}
                </div>

                {/* Action */}
                <div style={S.colAction} onClick={(e) => e.stopPropagation()}>
                  {!isEditing && !isValidated ? (
                    <button type="button" onClick={() => { setEditingPhone(patient.phone); setEditDraft(patient.display_name || patient.raw_name || ""); }} style={S.confirmNameBtn}>
                      Confirmer
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

const S = {
  page: { minHeight: "100%", background: "#f9fafb", fontFamily: "'Inter', 'DM Sans', sans-serif", color: NAVY, padding: "24px 28px 36px", maxWidth: 1200, margin: "0 auto" },

  header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 },
  title: { margin: 0, fontSize: 20, fontWeight: 800, color: NAVY },
  subtitle: { margin: "4px 0 0", fontSize: 13, color: "#6b7280" },

  toast: { marginBottom: 14, borderRadius: 10, border: "1px solid #a7f3d0", background: "#ecfdf5", color: "#047857", padding: "10px 14px", fontSize: 13, fontWeight: 700 },
  errorBox: { marginBottom: 14, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", color: "#b91c1c", padding: "12px 14px", fontSize: 14, fontWeight: 600 },

  toolbar: { display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 },
  searchBox: { display: "flex", alignItems: "center", gap: 10, background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10, padding: "10px 14px", maxWidth: 480 },
  searchInput: { border: "none", background: "transparent", fontSize: 14, color: NAVY, outline: "none", width: "100%", fontFamily: "inherit" },
  clearBtn: { background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 12, padding: 0, fontFamily: "inherit" },
  filterRow: { display: "flex", gap: 6, flexWrap: "wrap" },
  filterBtn: { padding: "6px 14px", borderRadius: 8, border: `1px solid ${BORDER}`, background: "#fff", color: "#6b7280", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6 },
  filterActive: { padding: "6px 14px", borderRadius: 8, border: `1px solid ${BLUE}`, background: "#eff6ff", color: BLUE, fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6 },
  filterCount: { fontSize: 11, opacity: 0.7, fontWeight: 500 },

  listContainer: { background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, overflow: "hidden" },
  listHeader: { display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1.2fr 100px", gap: 12, padding: "10px 20px", borderBottom: `1px solid ${BORDER}`, background: "#fafafa", fontSize: 11, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em" },
  row: { display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1.2fr 100px", gap: 12, padding: "14px 20px", borderBottom: `1px solid #f5f5f5`, cursor: "pointer", alignItems: "center" },
  skeleton: { height: 44, borderRadius: 8, gridColumn: "1 / -1", background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)", backgroundSize: "200% 100%", animation: "uwi-p-shimmer 1.35s infinite linear" },

  colPatient: { display: "flex", alignItems: "center", gap: 12, minWidth: 0 },
  colStatus: { display: "flex", flexDirection: "column", gap: 4 },
  colContact: { display: "flex", alignItems: "center" },
  colMotif: { display: "flex", alignItems: "center", minWidth: 0 },
  colAction: { display: "flex", justifyContent: "flex-end" },

  avatar: { width: 36, height: 36, borderRadius: 10, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, flexShrink: 0, boxShadow: "0 2px 8px rgba(0,0,0,.06)" },
  patientName: { fontSize: 14, fontWeight: 700, color: NAVY, lineHeight: 1.3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  phoneLink: { fontSize: 12, color: "#6b7280", textDecoration: "none", display: "block", marginTop: 1 },

  statusBadge: { fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 999, display: "inline-block" },
  unconfirmedBadge: { fontSize: 10, color: "#f59e0b", fontWeight: 600 },

  contactDate: { fontSize: 13, color: "#475569" },
  motifText: { fontSize: 12, color: "#475569", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" },
  motifEmpty: { fontSize: 12, color: "#d1d5db" },

  confirmNameBtn: { padding: "5px 12px", borderRadius: 8, border: "none", background: "#fef3c7", color: "#92400e", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap" },

  editInput: { border: `2px solid ${TEAL}`, borderRadius: 8, padding: "4px 10px", fontSize: 13, fontWeight: 700, color: NAVY, outline: "none", width: 150, fontFamily: "inherit" },
  confirmBtn: { width: 28, height: 28, borderRadius: 8, border: "none", background: TEAL_DARK, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" },
  cancelBtn: { width: 28, height: 28, borderRadius: 8, border: `1px solid ${BORDER}`, background: "#fff", color: "#6b7280", fontSize: 11, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" },

  empty: { gridColumn: "1 / -1", padding: "48px 18px", textAlign: "center" },
};

const CSS = `
  @keyframes uwi-p-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .patient-row { transition: background .08s ease; }
  .patient-row:hover { background: #f9fafb !important; }
  .patient-row:last-child { border-bottom: none !important; }
  .filter-chip { transition: all .1s ease; }
  @media (max-width: 768px) {
    .patient-row { grid-template-columns: 1fr !important; gap: 8px !important; }
  }
`;
