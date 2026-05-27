import { useEffect, useState } from "react";
import { Cpu, RefreshCw, Server } from "lucide-react";
import { T, font, radius, formatRelative } from "../../theme.js";
import { PanelCard } from "../ui/Card.jsx";
import { fetchSystemInfo } from "../../../lib/adminApi.js";

/**
 * Affiche les infos systeme/runtime/build (sans secrets).
 *
 * Sections :
 * - Build : git sha, branch, version
 * - Runtime : Python, Node, plateforme
 * - Process : uptime, started_at
 * - Env safe : variables whitelistees + flags de presence (sans valeur)
 *
 * Auto-refresh manuel uniquement (info change rarement).
 */
export default function SystemInfoPanel() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetchAt, setLastFetchAt] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchSystemInfo();
      setInfo(data?.info || null);
      setError(null);
      setLastFetchAt(new Date().toISOString());
    } catch (e) {
      setError(e?.message || "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <PanelCard
      eyebrow={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Server size={12} /> Systeme
        </span>
      }
      title="Infos runtime & build"
      subtitle={
        lastFetchAt
          ? `Mis a jour ${formatRelative(lastFetchAt)}`
          : "Chargement..."
      }
      action={
        <button
          type="button"
          onClick={load}
          title="Rafraichir"
          style={{
            padding: "5px 8px",
            borderRadius: radius.md,
            border: `1px solid ${T.border}`,
            background: T.bgCard,
            color: T.teal,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <RefreshCw size={14} className={loading ? "uwi-spin" : ""} />
        </button>
      }
    >
      {error ? (
        <div
          style={{
            padding: 12,
            background: T.redLight,
            border: `1px solid ${T.red}40`,
            borderRadius: radius.md,
            color: T.red,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      ) : !info ? (
        <div style={{ padding: 24, textAlign: "center", color: T.textMuted, fontSize: 13 }}>
          Chargement...
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Section title="Build">
            <Row label="Git SHA" value={info.build?.git_sha || "—"} mono />
            <Row label="Branche" value={info.build?.git_branch || "—"} />
            <Row label="Version" value={info.build?.version || "—"} mono />
          </Section>

          <Section title="Runtime">
            <Row label="Python" value={info.runtime?.python_version || "—"} mono />
            <Row label="Node" value={info.runtime?.node_version || "—"} mono />
            <Row label="Plateforme" value={info.runtime?.platform || "—"} />
          </Section>

          <Section title="Process">
            <Row label="PID" value={info.process?.pid ?? "—"} mono />
            <Row
              label="Demarre"
              value={
                info.process?.started_at
                  ? new Date(info.process.started_at).toLocaleString("fr-FR")
                  : "—"
              }
            />
            <Row
              label="Uptime"
              value={info.process?.uptime_label || "—"}
              valueColor={T.green}
            />
          </Section>

          <Section title="Variables d'environnement">
            {Object.entries(info.env?.vars || {}).map(([k, v]) => (
              <Row key={k} label={k} value={String(v)} mono />
            ))}
          </Section>

          <div style={{ gridColumn: "1 / -1" }}>
            <Section title="Services configures">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: 6,
                }}
              >
                {Object.entries(info.env?.configured || {}).map(([k, v]) => (
                  <div
                    key={k}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 12,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: v ? T.green : T.textMuted,
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        color: v ? T.text : T.textMuted,
                        fontFamily: "ui-monospace, monospace",
                        fontSize: 11,
                      }}
                    >
                      {k}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
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

function Section({ title, children }) {
  return (
    <div>
      <div
        style={{
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: T.textMuted,
          fontSize: 10,
          fontWeight: 700,
          marginBottom: 8,
          fontFamily: font.body,
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>{children}</div>
    </div>
  );
}

function Row({ label, value, mono = false, valueColor }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12 }}>
      <span style={{ color: T.textSecondary }}>{label}</span>
      <span
        style={{
          color: valueColor || T.text,
          fontFamily: mono ? "ui-monospace, monospace" : font.body,
          fontWeight: 500,
          textAlign: "right",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </span>
    </div>
  );
}
