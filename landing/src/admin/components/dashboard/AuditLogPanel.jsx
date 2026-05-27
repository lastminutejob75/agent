import { useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { T, font, radius, formatRelative } from "../../theme.js";
import { PanelCard } from "../ui/Card.jsx";
import { fetchAuditLog } from "../../../lib/adminApi.js";

const METHOD_OPTIONS = [
  { value: "", label: "Toutes" },
  { value: "POST", label: "POST" },
  { value: "PUT", label: "PUT" },
  { value: "PATCH", label: "PATCH" },
  { value: "DELETE", label: "DELETE" },
];

const POLL_INTERVAL_MS = 30000;

/**
 * Affiche les actions admin recentes (writes sur /api/admin/*).
 * Source : table admin_audit_log alimentee par le middleware FastAPI.
 *
 * Filtres : method, tenant_id, actor_email, prefixe URL.
 * Click sur une ligne = expand le payload sanitise.
 *
 * Necessite auth admin (cookie ou Bearer).
 */
export default function AuditLogPanel({ defaultLimit = 100 }) {
  const [items, setItems] = useState([]);
  const [method, setMethod] = useState("");
  const [actorEmail, setActorEmail] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [pathPrefix, setPathPrefix] = useState("");
  const [limit, setLimit] = useState(defaultLimit);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetchAt, setLastFetchAt] = useState(null);
  const [expanded, setExpanded] = useState({});

  const aliveRef = useRef(true);

  const load = useMemo(
    () => async () => {
      try {
        const data = await fetchAuditLog({
          limit,
          method: method || undefined,
          actor_email: actorEmail || undefined,
          tenant_id: tenantId ? Number(tenantId) : undefined,
          path_prefix: pathPrefix || undefined,
        });
        if (!aliveRef.current) return;
        setItems(Array.isArray(data?.items) ? data.items : []);
        setError(null);
        setLastFetchAt(new Date().toISOString());
      } catch (e) {
        if (!aliveRef.current) return;
        setError(e?.message || "Erreur de chargement de l'audit-log");
      } finally {
        if (aliveRef.current) setLoading(false);
      }
    },
    [limit, method, actorEmail, tenantId, pathPrefix]
  );

  useEffect(() => {
    aliveRef.current = true;
    load();
    return () => {
      aliveRef.current = false;
    };
  }, [load]);

  useEffect(() => {
    const id = setInterval(() => {
      load();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <PanelCard
      eyebrow={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <ShieldCheck size={12} /> Audit
        </span>
      }
      title="Actions admin recentes"
      subtitle={
        lastFetchAt
          ? `${items.length} entrees • mis a jour ${formatRelative(lastFetchAt)}`
          : "Chargement..."
      }
      action={
        <button
          type="button"
          onClick={() => load()}
          title="Rafraichir"
          style={iconBtnStyle(T.teal)}
        >
          <RefreshCw size={14} className={loading ? "uwi-spin" : ""} />
        </button>
      }
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr 100px",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          style={inputStyle}
        >
          {METHOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Email admin"
          value={actorEmail}
          onChange={(e) => setActorEmail(e.target.value)}
          style={inputStyle}
        />
        <input
          type="text"
          placeholder="Tenant ID"
          value={tenantId}
          onChange={(e) => setTenantId(e.target.value.replace(/[^0-9]/g, ""))}
          style={inputStyle}
        />
        <input
          type="text"
          placeholder="Prefixe URL (ex: /api/admin/tenants)"
          value={pathPrefix}
          onChange={(e) => setPathPrefix(e.target.value)}
          style={inputStyle}
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          style={inputStyle}
        >
          {[50, 100, 200, 500].map((n) => (
            <option key={n} value={n}>{`${n} max`}</option>
          ))}
        </select>
      </div>

      {error ? (
        <div
          style={{
            padding: 12,
            background: T.redLight,
            border: `1px solid ${T.red}40`,
            borderRadius: radius.md,
            color: T.red,
            fontSize: 13,
            fontFamily: font.body,
          }}
        >
          {error}
        </div>
      ) : items.length === 0 ? (
        <div
          style={{
            padding: 24,
            textAlign: "center",
            color: T.textMuted,
            fontSize: 13,
            fontFamily: font.body,
          }}
        >
          {loading ? "Chargement..." : "Aucune action admin enregistree."}
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
            maxHeight: 480,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {items.map((entry) => (
            <AuditRow
              key={entry.id}
              entry={entry}
              expanded={!!expanded[entry.id]}
              onToggle={() =>
                setExpanded((prev) => ({ ...prev, [entry.id]: !prev[entry.id] }))
              }
            />
          ))}
        </div>
      )}
      <style>{`
        .uwi-spin { animation: uwi-spin 1s linear infinite; }
        @keyframes uwi-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </PanelCard>
  );
}

function AuditRow({ entry, expanded, onToggle }) {
  const status = entry.status_code;
  const ts = entry.created_at
    ? new Date(entry.created_at).toLocaleString("fr-FR", { hour12: false })
    : "";
  const methodColor = methodColorOf(entry.method);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle();
        }
      }}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
        padding: "8px 10px",
        borderRadius: radius.sm,
        background: T.bgSubtle,
        border: `1px solid ${T.border}`,
        cursor: "pointer",
        fontFamily: font.body,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 12,
          flexWrap: "wrap",
        }}
      >
        <span style={methodPillStyle(methodColor)}>{entry.method}</span>
        <span
          style={{
            color: T.text,
            fontFamily: "ui-monospace, monospace",
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
        >
          {entry.path}
        </span>
        {status != null && <span style={statusPillStyle(status)}>{status}</span>}
        <span style={{ color: T.textMuted, fontSize: 11, fontFamily: "ui-monospace, monospace" }}>
          {ts}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          gap: 10,
          fontSize: 11,
          color: T.textSecondary,
          flexWrap: "wrap",
        }}
      >
        <span>
          <span style={{ color: T.textMuted }}>par</span>{" "}
          <strong style={{ color: T.text }}>{entry.actor_email || "system"}</strong>
        </span>
        {entry.tenant_id && (
          <span>
            <span style={{ color: T.textMuted }}>tenant</span>{" "}
            <strong style={{ color: T.text }}>#{entry.tenant_id}</strong>
          </span>
        )}
        {entry.ip && (
          <span style={{ fontFamily: "ui-monospace, monospace" }}>
            <span style={{ color: T.textMuted }}>ip</span> {entry.ip}
          </span>
        )}
        {entry.request_id && (
          <span style={{ fontFamily: "ui-monospace, monospace", color: T.textMuted }}>
            rid={String(entry.request_id).slice(0, 8)}
          </span>
        )}
        {entry.description && (
          <span style={{ marginLeft: "auto", color: T.text, fontStyle: "italic" }}>
            {entry.description}
          </span>
        )}
      </div>
      {expanded && entry.payload && (
        <pre
          style={{
            marginTop: 4,
            padding: 8,
            background: T.bgCard,
            border: `1px solid ${T.border}`,
            borderRadius: radius.sm,
            fontSize: 11,
            color: T.textSecondary,
            overflowX: "auto",
            maxHeight: 240,
            fontFamily: "ui-monospace, monospace",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {JSON.stringify(entry.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

const inputStyle = {
  padding: "5px 10px",
  borderRadius: radius.md,
  border: `1px solid ${T.border}`,
  background: T.bgCard,
  color: T.text,
  fontSize: 12,
  fontFamily: font.body,
};

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

function methodColorOf(method) {
  switch ((method || "").toUpperCase()) {
    case "POST":
      return T.green;
    case "PUT":
    case "PATCH":
      return T.orange;
    case "DELETE":
      return T.red;
    default:
      return T.textMuted;
  }
}

function methodPillStyle(color) {
  return {
    fontSize: 11,
    fontWeight: 700,
    padding: "1px 8px",
    borderRadius: radius.pill,
    background: `${color}20`,
    color,
    fontFamily: "ui-monospace, monospace",
    minWidth: 52,
    textAlign: "center",
  };
}

function statusPillStyle(status) {
  const s = Number(status);
  let color = T.textMuted;
  let bg = T.neutralLight;
  if (s >= 500) {
    color = T.red;
    bg = T.redLight;
  } else if (s >= 400) {
    color = T.orange;
    bg = T.orangeLight;
  } else if (s >= 200 && s < 300) {
    color = T.green;
    bg = T.greenLight;
  }
  return {
    fontSize: 11,
    fontWeight: 700,
    padding: "1px 8px",
    borderRadius: radius.pill,
    background: bg,
    color,
    fontFamily: "ui-monospace, monospace",
  };
}
