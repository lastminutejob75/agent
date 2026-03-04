import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { formatOpeningHoursCompact, formatOpeningHoursPretty, getAmplitudeBadge, getAmplitudeScore } from "../../lib/openingHoursPretty.js";

const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8" };
const STATUS_LABELS = { new: "Nouveau", contacted: "Contacté", converted: "Converti", lost: "Perdu" };
const STATUS_FILTERS = [
  { value: "", label: "Tous" },
  { value: "new", label: "Nouveaux" },
  { value: "contacted", label: "Contactés" },
  { value: "converted", label: "Convertis" },
  { value: "lost", label: "Perdus" },
];

// Score commercial : volume + spécialité + douleur + amplitude horaire
function getLeadPriority(lead) {
  let score = 0;
  const vol = lead.daily_call_volume;
  if (vol === "100+") score += 50;
  else if (vol === "50-100") score += 30;
  else if (vol === "25-50") score += 20;
  const spec = (lead.medical_specialty || "").toLowerCase();
  if (spec === "centre_medical" || spec === "clinique_privee") score += 30;
  const pain = lead.primary_pain_point || "";
  if (pain.includes("secrétariat n'arrive pas") || pain.includes("secrétariat est débordé")) score += 20;
  score += getAmplitudeScore(lead);
  if (score >= 70) return { score, label: "Haute priorité", style: { background: "rgba(255,107,107,0.2)", color: "#FF6B6B" } };
  if (score >= 40) return { score, label: "Moyenne", style: { background: "rgba(255,179,71,0.2)", color: "#FFB347" } };
  return { score, label: "Standard", style: { background: "rgba(107,144,168,0.15)", color: "#6B90A8", border: "1px solid #1E3D56" } };
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}


export default function AdminLeadsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get("status") || "";
  const enterpriseParam = searchParams.get("enterprise") === "1";
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    setLoadError(null);
    adminApi
      .leadsList({ status: statusParam || undefined, enterprise: enterpriseParam || undefined })
      .then((r) => {
        setLeads(r.leads || []);
      })
      .catch((err) => {
        setLeads([]);
        const status = err?.status;
        const msg = err?.message || String(err);
        if (status === 401) {
          setLoadError("Session expirée ou token invalide. Reconnectez-vous depuis la page Admin.");
        } else if (status === 403) {
          setLoadError("Accès refusé (CORS ou origine non autorisée). Vérifiez CORS_ORIGINS sur le backend.");
        } else if (status === 503) {
          setLoadError("Admin non configuré côté serveur (ADMIN_EMAIL / ADMIN_API_TOKEN).");
        } else {
          setLoadError(msg || "Impossible de charger les leads. Vérifiez la console et les logs backend.");
        }
      })
      .finally(() => setLoading(false));
  }, [statusParam, enterpriseParam]);

  const setStatusFilter = (value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set("status", value);
    else next.delete("status");
    setSearchParams(next);
  };
  const setEnterpriseFilter = (on) => {
    const next = new URLSearchParams(searchParams);
    if (on) next.set("enterprise", "1");
    else next.delete("enterprise");
    setSearchParams(next);
  };

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 16 }}>Leads</h1>
      <div style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>Pipeline :</span>
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setStatusFilter(value)}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              background: statusParam === value ? "rgba(0,229,160,0.1)" : C.card,
              color: statusParam === value ? C.accent : C.muted,
              border: statusParam === value ? `1px solid ${C.accent}` : `1px solid ${C.border}`,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
        <span style={{ color: C.muted, margin: "0 4px" }}>|</span>
        <button
          type="button"
          onClick={() => setEnterpriseFilter(!enterpriseParam)}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            background: enterpriseParam ? "rgba(255,179,71,0.15)" : C.card,
            color: enterpriseParam ? "#FFB347" : C.muted,
            border: enterpriseParam ? "1px solid rgba(255,179,71,0.3)" : `1px solid ${C.border}`,
            cursor: "pointer",
          }}
        >
          🔥 Grands comptes
        </button>
      </div>
      {loadError && (
        <div style={{ marginBottom: 16, borderRadius: 12, border: "1px solid rgba(255,179,71,0.3)", background: "rgba(255,179,71,0.1)", padding: "12px 16px", color: "#FFB347" }}>
          {loadError}
          {loadError.includes("Reconnectez-vous") && (
            <Link to="/admin/login" style={{ marginLeft: 8, fontWeight: 600, color: C.accent }}>
              Se connecter
            </Link>
          )}
        </div>
      )}
      {loading ? (
        <p style={{ color: C.muted }}>Chargement…</p>
      ) : (
        <>
          {/* Stats rapides */}
          <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
            {[
              ["Total", leads.length, "#6B90A8"],
              ["Nouveaux", leads.filter((l) => l.status === "new").length, "#FFB347"],
              ["Convertis", leads.filter((l) => l.status === "converted").length, "#00E5A0"],
              ["Grands comptes", leads.filter((l) => l.is_enterprise || l.daily_call_volume === "100+").length, "#a78bfa"],
            ].map(([label, count, color]) => (
              <div key={label} style={{ background: "#132840", border: "1px solid #1E3D56", borderRadius: 12, padding: "10px 18px", display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 18, fontWeight: 800, color }}>{count}</span>
                <span style={{ fontSize: 12, color: "#6B90A8" }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Cards leads */}
          {leads.length === 0 ? (
            <div style={{ background: "#132840", border: "1px solid #1E3D56", borderRadius: 16, padding: "40px", textAlign: "center", color: "#6B90A8", fontSize: 14 }}>
              Aucun lead sur cette période
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {leads.map((lead) => {
                const prio = getLeadPriority(lead);
                const ampBadge = getAmplitudeBadge(lead);
                const isEnterprise = lead.is_enterprise || lead.daily_call_volume === "100+";

                const statusStyle =
                  lead.status === "new"
                    ? { bg: "rgba(255,179,71,0.12)", color: "#FFB347", label: "Nouveau" }
                    : lead.status === "converted"
                    ? { bg: "rgba(0,229,160,0.12)", color: "#00E5A0", label: "Converti" }
                    : lead.status === "contacted"
                    ? { bg: "rgba(91,168,255,0.12)", color: "#5BA8FF", label: "Contacté" }
                    : { bg: "rgba(107,144,168,0.12)", color: "#6B90A8", label: "Perdu" };

                return (
                  <div
                    key={lead.id}
                    style={{
                      background: "#132840",
                      border: "1px solid #1E3D56",
                      borderRadius: 16,
                      padding: "18px 20px",
                      borderLeft: isEnterprise ? "3px solid #FFB347" : `3px solid ${prio.style.color}`,
                      transition: "box-shadow 0.15s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.3)")}
                    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "none")}
                  >
                    {/* Ligne 1 — Contact + badges + date + statut + action */}
                    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
                      {/* Gauche : contact + badges */}
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                        <div style={{ width: 36, height: 36, borderRadius: "50%", background: "#0F2236", border: "1px solid #1E3D56", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: "#6B90A8", flexShrink: 0 }}>
                          {(lead.email || lead.callback_phone || "?")[0].toUpperCase()}
                        </div>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: "#FFFFFF", marginBottom: 3 }}>
                            {lead.email?.trim() || lead.callback_phone || "—"}
                          </div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                            <span style={{ background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.color}30`, borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                              {statusStyle.label}
                            </span>
                            <span style={{ borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600, ...prio.style }} title={`Score: ${prio.score}`}>
                              {prio.label}
                            </span>
                            {isEnterprise && (
                              <span style={{ background: "rgba(255,179,71,0.15)", color: "#FFB347", borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                                🔥 Grand compte
                              </span>
                            )}
                            {ampBadge && (
                              <span style={{ background: ampBadge.label.includes("élevée") ? "rgba(139,92,246,0.2)" : "rgba(56,189,248,0.2)", color: ampBadge.label.includes("élevée") ? "#a78bfa" : "#38bdf8", borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600 }}>
                                ⏰ {ampBadge.label}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      {/* Droite : date + bouton */}
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                        <span style={{ fontSize: 11, color: "#6B90A8" }}>{formatDate(lead.created_at)}</span>
                        <Link
                          to={`/admin/leads/${lead.id}`}
                          style={{
                            background: "rgba(0,229,160,0.1)",
                            color: "#00E5A0",
                            border: "1px solid rgba(0,229,160,0.3)",
                            borderRadius: 8,
                            padding: "6px 14px",
                            fontSize: 12,
                            fontWeight: 700,
                            textDecoration: "none",
                          }}
                        >
                          Voir →
                        </Link>
                      </div>
                    </div>

                    {/* Ligne 2 — Infos métier en grille */}
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
                      <div style={{ background: "#0F2236", borderRadius: 10, padding: "8px 12px" }}>
                        <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 }}>Spécialité</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#FFFFFF" }}>{lead.medical_specialty_label || lead.medical_specialty || "—"}</div>
                      </div>
                      <div style={{ background: "#0F2236", borderRadius: 10, padding: "8px 12px" }}>
                        <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 }}>Appels/jour</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: lead.daily_call_volume === "100+" ? "#FFB347" : "#FFFFFF" }}>{lead.daily_call_volume || "—"}</div>
                      </div>
                      <div style={{ background: "#0F2236", borderRadius: 10, padding: "8px 12px" }}>
                        <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 }}>Assistante</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "#FFFFFF" }}>
                          {lead.assistant_name} <span style={{ color: "#6B90A8" }}>({lead.voice_gender === "female" ? "F" : "M"})</span>
                        </div>
                      </div>
                      <div style={{ background: "#0F2236", borderRadius: 10, padding: "8px 12px" }}>
                        <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 }}>Horaires</div>
                        <div style={{ fontSize: 12, color: "#FFFFFF" }} title={formatOpeningHoursPretty(lead.opening_hours)}>
                          {formatOpeningHoursCompact(lead.opening_hours) || "—"}
                        </div>
                      </div>
                      {lead.primary_pain_point && (
                        <div style={{ background: "#0F2236", borderRadius: 10, padding: "8px 12px", gridColumn: "1 / -1" }}>
                          <div style={{ fontSize: 10, color: "#6B90A8", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 3 }}>Douleur principale</div>
                          <div style={{ fontSize: 13, color: "#FFFFFF", lineHeight: 1.5 }}>{lead.primary_pain_point}</div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
