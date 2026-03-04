import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { getClientLoginUrl } from "../../lib/clientAppUrl";

const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8", danger: "#FF6B6B", warning: "#FFB347" };
const WINDOW_OPTIONS = [7, 14, 30];

const sectionStyle = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 20 };
const h2Style = { fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 8 };
const pMutedStyle = { fontSize: 13, color: C.muted, marginBottom: 12 };
const linkStyle = { color: C.accent, fontWeight: 600 };
const btnStyle = { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const btnPrimary = { ...btnStyle, background: "linear-gradient(135deg, #00E5A0, #00b87c)", color: C.bg };
const btnSecondary = { ...btnStyle, background: "rgba(107,144,168,0.2)", color: C.muted };
const btnSuccess = { ...btnStyle, background: "rgba(0,229,160,0.2)", color: C.accent };
const badgeAmber = { display: "inline-flex", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: "rgba(255,179,71,0.15)", color: C.warning, border: "1px solid rgba(255,179,71,0.3)" };
const badgeRed = { display: "inline-flex", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: "rgba(255,107,107,0.15)", color: C.danger, border: "1px solid rgba(255,107,107,0.3)" };

export default function AdminOperations() {
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    setActionLoading("refresh");
    try {
      const snapshot = await adminApi.operationsSnapshot(windowDays);
      setData(snapshot);
      setLastUpdated(snapshot?.generated_at ? new Date(snapshot.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : null);
    } catch (e) {
      setErr(e?.message || "Erreur chargement");
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

  if (err && !data) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
        <div style={{ ...sectionStyle, borderColor: "rgba(255,107,107,0.3)", background: "rgba(255,107,107,0.1)", color: C.danger }}>
          <p style={{ fontWeight: 600 }}>Erreur</p>
          <p style={{ fontSize: 13, marginTop: 4 }}>{err}</p>
          <button type="button" onClick={load} style={{ ...btnPrimary, marginTop: 16 }}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  const billing = data?.billing ?? {};
  const suspensions = data?.suspensions ?? { items: [] };
  const cost = data?.cost ?? { today_utc: { total_usd: 0, top: [] }, last_7d: { total_usd: 0, top: [] } };
  const errors = data?.errors ?? { top_tenants: [], errors_total: 0 };
  const quota = data?.quota ?? { month_utc: null, over_80: [], over_100: [] };

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
        <div style={{ marginBottom: 16, padding: "12px 16px", background: "rgba(255,179,71,0.1)", border: "1px solid rgba(255,179,71,0.3)", borderRadius: 12, color: C.warning, fontSize: 13 }}>
          {err}
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
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>Quota risk</h2>
        <p style={pMutedStyle}>
          Utilisation minutes ce mois UTC
          {quota.month_utc && <span style={{ marginLeft: 4 }}>({quota.month_utc})</span>}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24 }}>
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
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 24, marginTop: 16 }}>
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
      <section style={sectionStyle}>
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
