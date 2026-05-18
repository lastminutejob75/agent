import { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { getClientLoginUrl } from "../../lib/clientAppUrl";
import { T } from "../theme.js";

const C = {
  bg: T.bgPage,
  card: T.bgCard,
  border: T.border,
  accent: T.teal,
  text: T.text,
  muted: T.textMuted,
  danger: T.red,
  warning: T.orange,
};
const WINDOW_OPTIONS = [7, 14, 30];

const sectionStyle = {
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 12,
  padding: 20,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
};
const h2Style = { fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 8 };
const pMutedStyle = { fontSize: 13, color: C.muted, marginBottom: 12 };
const linkStyle = { color: C.accent, fontWeight: 600 };
const btnStyle = {
  padding: "8px 16px",
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  border: "none",
  cursor: "pointer",
};
const btnPrimary = { ...btnStyle, background: T.teal, color: "#FFFFFF" };
const btnSecondary = {
  ...btnStyle,
  background: T.bgCard,
  color: T.textSecondary,
  border: `1px solid ${T.borderDark}`,
};
const btnSuccess = {
  ...btnStyle,
  background: T.tealLight,
  color: T.teal,
  border: `1px solid ${T.teal}33`,
};
const badgeAmber = {
  display: "inline-flex",
  padding: "2px 8px",
  borderRadius: 6,
  fontSize: 11,
  fontWeight: 600,
  background: T.yellowLight,
  color: T.yellowText,
  border: `1px solid ${T.yellow}66`,
};
const badgeRed = {
  display: "inline-flex",
  padding: "2px 8px",
  borderRadius: 6,
  fontSize: 11,
  fontWeight: 600,
  background: T.redLight,
  color: T.red,
  border: `1px solid ${T.red}40`,
};

const SAMPLE_OPERATIONS_SNAPSHOT = {
  generated_at: new Date().toISOString(),
  billing: {
    month_utc: "2026-05",
    cost_usd_this_month: 864.42,
    tenants_past_due: [
      { tenant_id: 1010, name: "Centre Imagerie Wilson", billing_status: "past_due", current_period_end: "2026-05-30" },
      { tenant_id: 1012, name: "Cabinet ORL du Parc", billing_status: "past_due", current_period_end: "2026-05-28" },
      { tenant_id: 1015, name: "Maison Médicale Saint-Michel", billing_status: "unpaid", current_period_end: "2026-05-27" },
    ],
    top_tenants_by_cost_this_month: [
      { tenant_id: 1002, name: "Centre Médical République", total_usd: 152.4 },
      { tenant_id: 1013, name: "Centre Cardio Horizon", total_usd: 141.1 },
      { tenant_id: 1005, name: "Clinique Orion", total_usd: 133.9 },
    ],
  },
  suspensions: {
    suspended_total: 3,
    items: [
      { tenant_id: 1003, name: "Kiné Performance Lyon", reason: "Paiement en retard", mode: "soft", suspended_at: "2026-05-10" },
      { tenant_id: 1012, name: "Cabinet ORL du Parc", reason: "Erreur provisioning", mode: "soft", suspended_at: "2026-05-11" },
      { tenant_id: 1015, name: "Maison Médicale Saint-Michel", reason: "Compte inactif", mode: "hard", suspended_at: "2026-05-09" },
    ],
  },
  cost: {
    today_utc: {
      date_utc: "2026-05-17",
      total_usd: 39.8,
      top: [
        { tenant_id: 1002, name: "Centre Médical République", total_usd: 8.2 },
        { tenant_id: 1013, name: "Centre Cardio Horizon", total_usd: 7.4 },
      ],
    },
    last_7d: {
      window_days: 7,
      total_usd: 268.2,
      top: [
        { tenant_id: 1002, name: "Centre Médical République", total_usd: 46.1 },
        { tenant_id: 1013, name: "Centre Cardio Horizon", total_usd: 42.9 },
      ],
    },
  },
  errors: {
    window_days: 7,
    errors_total: 23,
    top_tenants: [
      { tenant_id: 1012, name: "Cabinet ORL du Parc", errors_total: 9 },
      { tenant_id: 1003, name: "Kiné Performance Lyon", errors_total: 6 },
      { tenant_id: 1008, name: "Laboratoire Médical Nova", errors_total: 5 },
    ],
  },
  quota: {
    month_utc: "2026-05",
    over_80: [
      { tenant_id: 1002, name: "Centre Médical République", used_minutes: 780, included_minutes: 800, usage_pct: 97.5 },
      { tenant_id: 1013, name: "Centre Cardio Horizon", used_minutes: 1690, included_minutes: 2000, usage_pct: 84.5 },
    ],
    over_100: [
      { tenant_id: 1010, name: "Centre Imagerie Wilson", used_minutes: 845, included_minutes: 800, usage_pct: 105.6 },
    ],
  },
};

const SAMPLE_CABINET_AUDIT = {
  summary: { total_tenants: 46, tenants_with_mismatch: 6, tenants_with_error: 2 },
  rows: [
    { tenant_id: 1005, tenant_name: "Clinique Orion", total_mismatch_count: 5, sections: { params_json: 2, horaires: 2, faq: 1 } },
    { tenant_id: 1010, tenant_name: "Centre Imagerie Wilson", total_mismatch_count: 4, sections: { params_json: 3, billing: 1 } },
    { tenant_id: 1012, tenant_name: "Cabinet ORL du Parc", total_mismatch_count: 3, sections: { transfer: 2, params_json: 1 }, error: "sync calendar timeout" },
  ],
};

export default function AdminOperations() {
  const [searchParams] = useSearchParams();
  const criticalOnly = (searchParams.get("severity") || "").toLowerCase() === "critical";

  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [cabinetAudit, setCabinetAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [isSampleMode, setIsSampleMode] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    setActionLoading("refresh");
    try {
      const [snapshot, audit] = await Promise.all([
        adminApi.operationsSnapshot(windowDays),
        adminApi.cabinetProfileAudit({ onlyMismatch: true, limit: 10, offset: 0 }),
      ]);
      if (snapshot) {
        setData(snapshot);
        setCabinetAudit(audit);
        setLastUpdated(snapshot?.generated_at ? new Date(snapshot.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : null);
        setIsSampleMode(false);
      } else {
        setData(SAMPLE_OPERATIONS_SNAPSHOT);
        setCabinetAudit(SAMPLE_CABINET_AUDIT);
        setLastUpdated(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
        setIsSampleMode(true);
      }
    } catch (e) {
      setErr(e?.message || "Erreur chargement");
      setData(SAMPLE_OPERATIONS_SNAPSHOT);
      setCabinetAudit(SAMPLE_CABINET_AUDIT);
      setLastUpdated(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
      setIsSampleMode(true);
    } finally {
      setLoading(false);
      setActionLoading(null);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUnsuspend(tenantId) {
    setActionLoading(tenantId);
    try {
      await adminApi.tenantUnsuspend(tenantId);
      await load();
    } catch (e) {
      setErr(e?.message || "Erreur unsuspend");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleForceActive(tenantId) {
    setActionLoading(tenantId);
    try {
      await adminApi.tenantForceActive(tenantId, 7);
      await load();
    } catch (e) {
      setErr(e?.message || "Erreur force-active");
    } finally {
      setActionLoading(null);
    }
  }

  if (loading && !data) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: C.muted }}>
        <div style={{ width: 40, height: 40, border: `2px solid ${C.border}`, borderTopColor: C.accent, borderRadius: "50%", animation: "spin 0.8s linear infinite", marginBottom: 16 }} />
        <span>Chargement Operations…</span>
      </div>
    );
  }

  const billing = data?.billing ?? {};
  const suspensions = data?.suspensions ?? { items: [] };
  const cost = data?.cost ?? { today_utc: { total_usd: 0, top: [] }, last_7d: { total_usd: 0, top: [] } };
  const errors = data?.errors ?? { top_tenants: [], errors_total: 0 };
  const quota = data?.quota ?? { month_utc: null, over_80: [], over_100: [] };
  const cabinetSummary = cabinetAudit?.summary ?? { total_tenants: 0, tenants_with_mismatch: 0, tenants_with_error: 0 };
  const cabinetRows = Array.isArray(cabinetAudit?.rows) ? cabinetAudit.rows : [];
  const cabinetRowsDisplay = criticalOnly ? cabinetRows.filter((r) => Boolean(r?.error)) : cabinetRows;

  const rowStyle = { display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "12px 0", borderBottom: `1px solid ${C.border}` };
  const lastRowStyle = { ...rowStyle, borderBottom: "none" };

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 4 }}>Operations</h1>
          <p style={pMutedStyle}>
            Risque paiement, suspendus, coûts, erreurs
            {lastUpdated && <> · Mis à jour à {lastUpdated}</>}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, color: C.muted }}>Fenêtre erreurs</span>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} j</option>
            ))}
          </select>
          <button type="button" onClick={load} disabled={loading} style={{ ...btnPrimary, border: "none", opacity: loading ? 0.6 : 1 }}>
            {actionLoading === "refresh" ? "Chargement…" : "Rafraîchir"}
          </button>
        </div>
      </div>

      {err && data && (
        <div style={{ marginBottom: 16, padding: "12px 16px", background: T.yellowLight, border: `1px solid ${T.yellow}66`, borderRadius: 12, color: T.yellowText, fontSize: 13 }}>
          {err}
        </div>
      )}
      {isSampleMode && (
        <div style={{ marginBottom: 16, padding: "12px 16px", background: T.yellowLight, border: `1px solid ${T.yellow}66`, borderRadius: 12, color: T.yellowText, fontSize: 13 }}>
          Affichage en mode exemple (opérations fictives).
        </div>
      )}

      {/* À risque paiement */}
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>À risque paiement</h2>
        <p style={pMutedStyle}>
          Coût Vapi ce mois (UTC) : <strong style={{ fontFamily: "monospace", color: C.text }}>{Number(billing.cost_usd_this_month ?? 0).toFixed(2)} $</strong>
          {billing.month_utc && <span style={{ marginLeft: 4 }}>({billing.month_utc})</span>}
        </p>
        {billing.tenants_past_due?.length > 0 ? (
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {billing.tenants_past_due.map((t, i) => (
              <li key={t.tenant_id} style={i < billing.tenants_past_due.length - 1 ? rowStyle : lastRowStyle}>
                <Link to={`/admin/tenants/${t.tenant_id}`} style={linkStyle}>{t.name}</Link>
                <span style={{ fontSize: 13, color: C.muted }}>
                  {t.billing_status}
                  {t.current_period_end && ` · Période jusqu'au ${new Date(t.current_period_end).toLocaleDateString("fr-FR")}`}
                </span>
                <a href={getClientLoginUrl(undefined, t.tenant_id)} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, fontSize: 12 }} title="Page de connexion client">
                  Connexion client ↗
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p style={pMutedStyle}>Aucun client past_due.</p>
        )}
      </section>

      {/* Quota risk */}
      <section style={{ ...(criticalOnly ? { ...sectionStyle, borderLeft: `4px solid ${C.danger}`, paddingLeft: 16 } : sectionStyle), marginBottom: 24 }}>
        <h2 style={h2Style}>Quota risk</h2>
        <p style={pMutedStyle}>
          Utilisation minutes ce mois UTC
          {quota.month_utc && <span style={{ marginLeft: 4 }}>({quota.month_utc})</span>}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24 }}>
          {!criticalOnly && (
          <div>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: C.muted, display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={badgeAmber}>80%+</span>
              {quota.over_80?.length ?? 0} tenant(s)
            </h3>
            {quota.over_80?.length > 0 ? (
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {quota.over_80.map((t) => (
                  <li key={t.tenant_id} style={rowStyle}>
                    <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "70%" }}>{t.name}</Link>
                    <span style={{ fontSize: 13, fontFamily: "monospace", color: C.muted, whiteSpace: "nowrap" }}>
                      {Number(t.used_minutes).toFixed(0)} / {t.included_minutes} min · {t.usage_pct}%
                    </span>
                    <a href={getClientLoginUrl(undefined, t.tenant_id)} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, fontSize: 12 }} title="Connexion client">↗</a>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={pMutedStyle}>Aucun.</p>
            )}
          </div>
          )}
          <div>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: C.muted, display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={badgeRed}>100%+</span>
              {quota.over_100?.length ?? 0} tenant(s)
            </h3>
            {quota.over_100?.length > 0 ? (
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {quota.over_100.map((t) => (
                  <li key={t.tenant_id} style={rowStyle}>
                    <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "70%" }}>{t.name}</Link>
                    <span style={{ fontSize: 13, fontFamily: "monospace", color: C.muted, whiteSpace: "nowrap" }}>
                      {Number(t.used_minutes).toFixed(0)} / {t.included_minutes} min · {t.usage_pct}%
                    </span>
                    <a href={getClientLoginUrl(undefined, t.tenant_id)} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, fontSize: 12 }} title="Connexion client">↗</a>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={pMutedStyle}>Aucun.</p>
            )}
          </div>
        </div>
      </section>

      {/* Mon cabinet sync audit */}
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>Mon cabinet · mismatch sync</h2>
        <p style={pMutedStyle}>
          Contrôle de cohérence entre `tenant_config.params_json` et tables normalisées (top mismatch).
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
          <span style={badgeAmber}>Mismatch: {cabinetSummary.tenants_with_mismatch ?? 0}</span>
          <span style={badgeRed}>Erreurs audit: {cabinetSummary.tenants_with_error ?? 0}</span>
        </div>
        {cabinetRowsDisplay.length > 0 ? (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", borderTop: `1px solid ${C.border}` }}>
            {cabinetRowsDisplay.map((row, index) => {
              const sectionParts = row.sections
                ? Object.entries(row.sections)
                    .filter(([, count]) => Number(count) > 0)
                    .slice(0, 3)
                    .map(([key, count]) => `${key}: ${count}`)
                : [];
              return (
                <li
                  key={`${row.tenant_id}-${index}`}
                  style={{
                    padding: "10px 0",
                    borderBottom: index < cabinetRowsDisplay.length - 1 ? `1px solid ${C.border}` : "none",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <div style={{ minWidth: 220 }}>
                    <Link to={`/admin/tenants/${row.tenant_id}`} style={linkStyle}>
                      {row.tenant_name || `Tenant ${row.tenant_id}`}
                    </Link>
                    <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
                      mismatch total: {Number(row.total_mismatch_count ?? 0)}
                      {sectionParts.length ? ` · ${sectionParts.join(" · ")}` : ""}
                    </div>
                    {row.error ? (
                      <div style={{ fontSize: 12, color: C.warning, marginTop: 2 }}>
                        erreur: {row.error}
                      </div>
                    ) : null}
                  </div>
                  <a href={getClientLoginUrl(undefined, row.tenant_id)} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, fontSize: 12 }}>
                    Connexion client ↗
                  </a>
                </li>
              );
            })}
          </ul>
        ) : (
          <p style={pMutedStyle}>{criticalOnly ? "Aucune ligne d'audit avec erreur." : "Aucun mismatch détecté."}</p>
        )}
      </section>

      {/* Suspendus */}
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>Suspendus</h2>
        <p style={pMutedStyle}>{suspensions.suspended_total ?? 0} client(s) suspendu(s)</p>
        {suspensions.items?.length > 0 ? (
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {suspensions.items.map((s, i) => (
              <li key={s.tenant_id} style={i < suspensions.items.length - 1 ? rowStyle : lastRowStyle}>
                <div>
                  <Link to={`/admin/tenants/${s.tenant_id}`} style={linkStyle}>{s.name}</Link>
                  <span style={{ marginLeft: 8, fontSize: 13, color: C.muted }}>
                    {s.reason}{s.mode && s.mode !== "hard" ? ` · ${s.mode}` : ""}
                    {s.suspended_at && ` · depuis ${new Date(s.suspended_at).toLocaleDateString("fr-FR")}`}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <a href={getClientLoginUrl(undefined, s.tenant_id)} target="_blank" rel="noopener noreferrer" style={{ ...linkStyle, fontSize: 12 }} title="Page de connexion client">
                    Connexion client ↗
                  </a>
                  <button type="button" onClick={() => handleUnsuspend(s.tenant_id)} disabled={actionLoading === s.tenant_id} style={{ ...btnSuccess, opacity: actionLoading === s.tenant_id ? 0.6 : 1 }}>
                    {actionLoading === s.tenant_id ? "…" : "Lever"}
                  </button>
                  <button type="button" onClick={() => handleForceActive(s.tenant_id)} disabled={actionLoading === s.tenant_id} style={{ ...btnSecondary, opacity: actionLoading === s.tenant_id ? 0.6 : 1 }}>
                    Forcer actif 7j
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p style={pMutedStyle}>Aucun client suspendu.</p>
        )}
      </section>

      {/* Top coût */}
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>Top coût</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 24,
            marginTop: 16,
          }}
        >
          {!criticalOnly && (
            <>
              <div>
                <h3 style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>
                  Aujourd'hui (UTC){cost.today_utc?.date_utc ? ` · ${cost.today_utc.date_utc}` : ""}
                </h3>
                <p style={{ fontSize: 20, fontWeight: 800, color: C.text, marginTop: 4 }}>{Number(cost.today_utc?.total_usd ?? 0).toFixed(2)} $</p>
                <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none" }}>
                  {(cost.today_utc?.top ?? []).slice(0, 5).map((t) => (
                    <li key={t.tenant_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                      <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>{t.name}</Link>
                      <span style={{ fontFamily: "monospace", color: C.muted }}>{Number(t.value).toFixed(2)} $</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>{cost.last_7d?.window_days ?? 7} derniers jours</h3>
                <p style={{ fontSize: 20, fontWeight: 800, color: C.text, marginTop: 4 }}>{Number(cost.last_7d?.total_usd ?? 0).toFixed(2)} $</p>
                <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none" }}>
                  {(cost.last_7d?.top ?? []).slice(0, 5).map((t) => (
                    <li key={t.tenant_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                      <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>{t.name}</Link>
                      <span style={{ fontFamily: "monospace", color: C.muted }}>{Number(t.value).toFixed(2)} $</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
          <div>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: C.muted }}>Ce mois (UTC)</h3>
            <p style={{ fontSize: 20, fontWeight: 800, color: C.text, marginTop: 4 }}>{Number(billing.cost_usd_this_month ?? 0).toFixed(2)} $</p>
            <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none" }}>
              {(billing.top_tenants_by_cost_this_month ?? []).slice(0, 5).map((t) => (
                <li key={t.tenant_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>{t.name}</Link>
                  <span style={{ fontFamily: "monospace", color: C.muted }}>{Number(t.value).toFixed(2)} $</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Erreurs */}
      <section style={criticalOnly ? { ...sectionStyle, borderLeft: `4px solid ${C.warning}`, paddingLeft: 16 } : sectionStyle}>
        <h2 style={h2Style}>Erreurs</h2>
        <p style={pMutedStyle}>
          Top 10 tenants par erreurs sur {errors.window_days ?? 7} j · Total : <strong style={{ color: C.text }}>{errors.errors_total ?? 0}</strong>
        </p>
        {errors.top_tenants?.length > 0 ? (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", borderTop: `1px solid ${C.border}` }}>
            {errors.top_tenants.map((t, i) => (
              <li key={t.tenant_id} style={{ padding: "10px 0", borderBottom: i < errors.top_tenants.length - 1 ? `1px solid ${C.border}` : "none", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <Link to={`/admin/tenants/${t.tenant_id}`} style={{ ...linkStyle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "50%" }}>{t.name}</Link>
                <span style={{ fontFamily: "monospace", fontSize: 13, color: C.muted }}>{t.errors_total}</span>
                {t.last_error_at && (
                  <span style={{ fontSize: 12, color: C.muted, marginLeft: 8 }}>{new Date(t.last_error_at).toLocaleString("fr-FR")}</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p style={pMutedStyle}>Aucune erreur sur la période.</p>
        )}
      </section>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
