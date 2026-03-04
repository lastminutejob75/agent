import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8", warning: "#FFB347" };
const WINDOW_OPTIONS = [7, 14, 30];

const sectionStyle = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 20 };
const h2Style = { fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 12 };
const linkStyle = { color: C.accent, fontWeight: 600 };
const btnStyle = { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, background: "linear-gradient(135deg, #00E5A0, #00b87c)", color: C.bg, border: "none", cursor: "pointer" };
const btnLinkStyle = { display: "inline-block", padding: "6px 12px", fontSize: 12, fontWeight: 600, color: C.accent, background: "rgba(0,229,160,0.1)", border: `1px solid rgba(0,229,160,0.2)`, borderRadius: 8, textDecoration: "none" };

function TopTable({ title, items, resultFilter, windowDays }) {
  if (!items?.length) {
    return (
      <section style={sectionStyle}>
        <h2 style={h2Style}>{title}</h2>
        <p style={{ fontSize: 13, color: C.muted, marginTop: 12 }}>Aucune donnée sur la période.</p>
      </section>
    );
  }
  return (
    <section style={sectionStyle}>
      <h2 style={h2Style}>{title}</h2>
      <div style={{ marginTop: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}`, textAlign: "left" }}>
              <th style={{ padding: "8px 16px 8px 0", color: C.muted, fontWeight: 600 }}>Client</th>
              <th style={{ padding: "8px 16px 8px 0", color: C.muted, fontWeight: 600, textAlign: "right" }}>Count</th>
              <th style={{ padding: "8px 16px 8px 0", color: C.muted, fontWeight: 600 }}>Dernier incident</th>
              <th style={{ padding: "8px 0", width: 120 }} />
            </tr>
          </thead>
          <tbody>
            {items.map((row, i) => (
              <tr key={row.tenant_id} style={{ borderBottom: i < items.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <td style={{ padding: "10px 16px 10px 0" }}>
                  <Link to={`/admin/tenants/${row.tenant_id}`} style={linkStyle}>{row.name}</Link>
                </td>
                <td style={{ padding: "10px 16px 10px 0", fontFamily: "monospace", textAlign: "right", color: C.text }}>{row.count}</td>
                <td style={{ padding: "10px 16px 10px 0", color: C.muted }}>{row.last_at ? new Date(row.last_at).toLocaleString("fr-FR") : "—"}</td>
                <td style={{ padding: "10px 0" }}>
                  <Link
                    to={`/admin/calls?tenant_id=${row.tenant_id}&result=${resultFilter}&days=${windowDays}`}
                    style={btnLinkStyle}
                  >
                    Voir appels
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AdminQuality() {
  const [windowDays, setWindowDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const snapshot = await adminApi.qualitySnapshot(windowDays);
      setData(snapshot);
    } catch (e) {
      setErr(e?.message || "Erreur chargement");
    } finally {
      setLoading(false);
    }
  }, [windowDays]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !data) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: C.muted }}>
        <div style={{ width: 40, height: 40, border: `2px solid ${C.border}`, borderTopColor: C.accent, borderRadius: "50%", animation: "spin 0.8s linear infinite", marginBottom: 16 }} />
        <span>Chargement Quality…</span>
      </div>
    );
  }

  if (err && !data) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
        <div style={{ ...sectionStyle, borderColor: "rgba(255,107,107,0.3)", background: "rgba(255,107,107,0.1)", color: "#FF6B6B" }}>
          <p style={{ fontWeight: 600 }}>Erreur</p>
          <p style={{ fontSize: 13, marginTop: 4 }}>{err}</p>
          <button type="button" onClick={load} style={{ ...btnStyle, marginTop: 16 }}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  const kpis = data?.kpis ?? {};
  const top = data?.top ?? { anti_loop: [], abandons: [], transfers: [] };

  const kpiItemStyle = { fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase", letterSpacing: 1 };
  const kpiValueStyle = { fontSize: 28, fontWeight: 800, color: C.text, marginTop: 4 };
  const kpiWarningStyle = { ...kpiValueStyle, color: C.warning };

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, marginBottom: 4 }}>Quality</h1>
          <p style={{ fontSize: 14, color: C.muted }}>
            Améliorer l'agent · {data?.window_days ?? 7} derniers jours
            {data?.generated_at && <> · Mis à jour {new Date(data.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</>}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, color: C.muted }}>Fenêtre</span>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}
          >
            {WINDOW_OPTIONS.map((d) => (
              <option key={d} value={d}>{d} j</option>
            ))}
          </select>
          <button type="button" onClick={load} disabled={loading} style={{ ...btnStyle, opacity: loading ? 0.6 : 1 }}>
            Rafraîchir
          </button>
        </div>
      </div>

      {err && data && (
        <div style={{ marginBottom: 16, padding: "12px 16px", background: "rgba(255,179,71,0.1)", border: "1px solid rgba(255,179,71,0.3)", borderRadius: 12, color: C.warning, fontSize: 13 }}>
          {err}
        </div>
      )}

      {/* KPIs globaux */}
      <section style={{ ...sectionStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>KPIs globaux</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 16, marginTop: 16 }}>
          <div>
            <div style={kpiItemStyle}>Appels</div>
            <div style={kpiValueStyle}>{kpis.calls_total ?? "—"}</div>
          </div>
          <div>
            <div style={kpiItemStyle}>Abandons</div>
            <div style={kpiValueStyle}>{kpis.abandons ?? "—"}</div>
          </div>
          <div>
            <div style={kpiItemStyle}>Transferts</div>
            <div style={kpiValueStyle}>{kpis.transfers ?? "—"}</div>
          </div>
          <div>
            <div style={kpiItemStyle}>Anti-loop</div>
            <div style={kpiWarningStyle}>{kpis.anti_loop ?? "—"}</div>
          </div>
          <div>
            <div style={kpiItemStyle}>RDV confirmés</div>
            <div style={kpiValueStyle}>{kpis.appointments ?? "—"}</div>
          </div>
          <div>
            <div style={kpiItemStyle}>Taux abandon</div>
            <div style={kpiValueStyle}>{kpis.abandon_rate_pct != null ? `${kpis.abandon_rate_pct} %` : "—"}</div>
          </div>
        </div>
      </section>

      {/* Top tenants par problème */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
        <TopTable title="Top 10 · Anti-loop" items={top.anti_loop} resultFilter="error" windowDays={windowDays} />
        <TopTable title="Top 10 · Abandons" items={top.abandons} resultFilter="abandoned" windowDays={windowDays} />
        <TopTable title="Top 10 · Transferts" items={top.transfers} resultFilter="transfer" windowDays={windowDays} />
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
