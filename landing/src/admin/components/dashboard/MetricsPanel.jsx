import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertCircle, Clock, RefreshCw, TrendingUp } from "lucide-react";
import { T, font, radius } from "../../theme.js";
import { PanelCard } from "../ui/Card.jsx";
import { fetchLogMetrics } from "../../../lib/adminApi.js";

const POLL_INTERVAL_MS = 15000;

/**
 * Affiche des metriques agregees calculees sur le buffer de logs courant.
 *
 * Donnees :
 * - Total requetes / 4xx / 5xx
 * - Latence p50 / p95 / p99 / max / avg
 * - Top 10 paths par volume avec taux d'erreur
 * - Repartition des logs par niveau (INFO/WARNING/ERROR)
 *
 * Source : `GET /api/admin/logs/metrics` (cf. backend/log_setup.py).
 */
export default function MetricsPanel() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const aliveRef = useRef(true);

  const load = useMemo(
    () => async () => {
      try {
        const data = await fetchLogMetrics();
        if (!aliveRef.current) return;
        setMetrics(data?.metrics || null);
        setError(null);
      } catch (e) {
        if (!aliveRef.current) return;
        setError(e?.message || "Erreur metrics");
      } finally {
        if (aliveRef.current) setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    aliveRef.current = true;
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      aliveRef.current = false;
      clearInterval(id);
    };
  }, [load]);

  if (error) {
    return (
      <PanelCard eyebrow="Metriques" title="Metriques agregees">
        <div style={{ color: T.red, fontSize: 13 }}>{error}</div>
      </PanelCard>
    );
  }

  const m = metrics || {};
  const lat = m.latency || {};
  const total = m.total_requests || 0;
  const errors4xx = m.errors_4xx || 0;
  const errors5xx = m.errors_5xx || 0;
  const errorRate = total ? (((errors4xx + errors5xx) / total) * 100).toFixed(1) : "0.0";

  return (
    <PanelCard
      eyebrow="Metriques"
      title="Metriques agregees backend"
      subtitle={loading ? "Chargement..." : `Calculees sur ${total} requetes recentes`}
      action={
        <button
          type="button"
          onClick={load}
          title="Rafraichir"
          style={iconBtnStyle(T.teal)}
        >
          <RefreshCw size={14} className={loading ? "uwi-spin" : ""} />
        </button>
      }
    >
      {/* KPIs en haut */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 10,
          marginBottom: 16,
        }}
      >
        <Kpi
          icon={<Activity size={14} />}
          label="Total requetes"
          value={total}
          tone={T.text}
        />
        <Kpi
          icon={<TrendingUp size={14} />}
          label="Taux d'erreur"
          value={`${errorRate}%`}
          tone={Number(errorRate) > 5 ? T.red : Number(errorRate) > 1 ? T.orange : T.green}
        />
        <Kpi
          icon={<AlertCircle size={14} />}
          label="4xx"
          value={errors4xx}
          tone={errors4xx > 0 ? T.orange : T.textMuted}
        />
        <Kpi
          icon={<AlertCircle size={14} />}
          label="5xx"
          value={errors5xx}
          tone={errors5xx > 0 ? T.red : T.textMuted}
        />
      </div>

      {/* Latence */}
      {lat.p50_ms !== undefined && (
        <div style={{ marginBottom: 16 }}>
          <SectionTitle icon={<Clock size={13} />}>Latence (ms)</SectionTitle>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
              gap: 8,
            }}
          >
            <LatencyCell label="p50" value={lat.p50_ms} tone={T.green} />
            <LatencyCell label="p95" value={lat.p95_ms} tone={lat.p95_ms > 500 ? T.orange : T.text} />
            <LatencyCell label="p99" value={lat.p99_ms} tone={lat.p99_ms > 1000 ? T.red : T.text} />
            <LatencyCell label="max" value={lat.max_ms} tone={T.textSecondary} />
            <LatencyCell label="avg" value={lat.avg_ms} tone={T.textSecondary} />
          </div>
        </div>
      )}

      {/* Top paths */}
      {m.top_paths && m.top_paths.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <SectionTitle>Top routes</SectionTitle>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
            }}
          >
            {m.top_paths.map((p) => (
              <div
                key={p.path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "5px 10px",
                  borderRadius: radius.sm,
                  background: T.bgSubtle,
                  border: `1px solid ${T.border}`,
                }}
              >
                <span
                  style={{
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    color: T.text,
                  }}
                >
                  {p.path}
                </span>
                <span style={{ color: T.textMuted, minWidth: 50, textAlign: "right" }}>
                  {p.count}x
                </span>
                <span style={{ color: T.textMuted, minWidth: 60, textAlign: "right" }}>
                  {p.avg_ms}ms
                </span>
                {p.errors > 0 && (
                  <span
                    style={{
                      color: T.red,
                      minWidth: 50,
                      textAlign: "right",
                      fontWeight: 600,
                    }}
                  >
                    {p.errors} err
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Repartition par niveau */}
      {m.logs_by_level && Object.keys(m.logs_by_level).length > 0 && (
        <div>
          <SectionTitle>Logs par niveau</SectionTitle>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {Object.entries(m.logs_by_level).map(([lvl, count]) => (
              <span key={lvl} style={levelPillStyle(lvl)}>
                {lvl}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      <style>{`
        .uwi-spin { animation: uwi-spin 1s linear infinite; }
        @keyframes uwi-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </PanelCard>
  );
}

function Kpi({ icon, label, value, tone }) {
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: radius.md,
        background: T.bgSubtle,
        border: `1px solid ${T.border}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          fontWeight: 700,
          marginBottom: 4,
          fontFamily: font.body,
        }}
      >
        {icon}
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: tone,
          fontFamily: font.display,
          letterSpacing: -0.3,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function LatencyCell({ label, value, tone }) {
  return (
    <div
      style={{
        padding: "6px 10px",
        borderRadius: radius.sm,
        background: T.bgSubtle,
        border: `1px solid ${T.border}`,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: T.textMuted,
          textTransform: "uppercase",
          fontWeight: 700,
          fontFamily: font.body,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: tone,
          fontFamily: "ui-monospace, monospace",
          marginTop: 2,
        }}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}

function SectionTitle({ icon, children }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11,
        color: T.textMuted,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        fontWeight: 700,
        marginBottom: 8,
        fontFamily: font.body,
      }}
    >
      {icon}
      {children}
    </div>
  );
}

function levelPillStyle(level) {
  const colors = {
    ERROR: { bg: T.redLight, color: T.red },
    WARNING: { bg: T.orangeLight, color: T.orange },
    INFO: { bg: T.tealLight, color: T.teal },
    DEBUG: { bg: T.bgSubtle, color: T.textMuted },
  };
  const c = colors[level.toUpperCase()] || colors.DEBUG;
  return {
    fontSize: 11,
    fontWeight: 700,
    padding: "3px 10px",
    borderRadius: radius.pill,
    background: c.bg,
    color: c.color,
    fontFamily: "ui-monospace, monospace",
  };
}

function iconBtnStyle(color) {
  return {
    padding: "5px 8px",
    borderRadius: radius.md,
    border: `1px solid ${T.border}`,
    background: T.bgCard,
    color,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  };
}
