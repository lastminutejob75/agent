import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Bug,
  RefreshCw,
  Pause,
  Play,
  Download,
  Search,
  Layers,
  X,
} from "lucide-react";
import { T, font, radius, formatRelative } from "../../theme.js";
import { PanelCard } from "../ui/Card.jsx";
import { fetchRecentLogs } from "../../../lib/adminApi.js";

const LEVEL_OPTIONS = [
  { value: "", label: "Tous" },
  { value: "ERROR", label: "Errors" },
  { value: "WARNING", label: "Warnings" },
  { value: "INFO", label: "Infos" },
  { value: "DEBUG", label: "Debug" },
];

const LEVEL_CFG = {
  ERROR: { color: T.red, bg: T.redLight, Icon: AlertCircle },
  WARNING: { color: T.orange, bg: T.orangeLight, Icon: AlertTriangle },
  INFO: { color: T.teal, bg: T.tealLight, Icon: Info },
  DEBUG: { color: T.textMuted, bg: T.bgSubtle, Icon: Bug },
};

const POLL_INTERVAL_MS = 10000;

const selectStyle = {
  padding: "5px 10px",
  borderRadius: radius.md,
  border: `1px solid ${T.border}`,
  background: T.bgCard,
  color: T.text,
  fontSize: 12,
  fontFamily: font.body,
  cursor: "pointer",
};

/**
 * Affiche les ~N derniers logs structures du backend (cf. docs/OBSERVABILITE.md).
 *
 * Caracteristiques :
 * - Poll toutes les 10s (mise en pause possible).
 * - Filtre par niveau (ERROR, WARNING, INFO, DEBUG, ou Tous).
 * - Mise en page compacte avec niveau colore + path/method/status_code/duration_ms.
 * - Click sur une ligne : expand le JSON brut.
 *
 * Necessite auth admin (cookie ou Bearer).
 */
export default function LogsPanel({ defaultLimit = 100 }) {
  const [items, setItems] = useState([]);
  const [bufferSize, setBufferSize] = useState(0);
  const [level, setLevel] = useState("");
  const [limit, setLimit] = useState(defaultLimit);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [paused, setPaused] = useState(false);
  const [lastFetchAt, setLastFetchAt] = useState(null);
  const [expanded, setExpanded] = useState({});
  // Filtre full-text (msg + path + logger + request_id)
  const [search, setSearch] = useState("");
  // Mode "groupe par request_id" : regroupe les logs partageant la meme rid
  const [groupByRid, setGroupByRid] = useState(false);
  // Si selectionne, on filtre uniquement sur ce request_id
  const [pinnedRid, setPinnedRid] = useState("");

  const aliveRef = useRef(true);

  const load = useMemo(
    () => async () => {
      try {
        const data = await fetchRecentLogs(limit, level || null);
        if (!aliveRef.current) return;
        setItems(Array.isArray(data?.items) ? data.items : []);
        setBufferSize(Number(data?.buffer_size || 0));
        setError(null);
        setLastFetchAt(new Date().toISOString());
      } catch (e) {
        if (!aliveRef.current) return;
        setError(e?.message || "Erreur de chargement des logs");
      } finally {
        if (aliveRef.current) setLoading(false);
      }
    },
    [limit, level]
  );

  useEffect(() => {
    aliveRef.current = true;
    load();
    return () => {
      aliveRef.current = false;
    };
  }, [load]);

  useEffect(() => {
    if (paused) return undefined;
    const id = setInterval(() => {
      load();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [paused, load]);

  // ---- Filtrage local : recherche full-text + pinned rid ----
  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((entry) => {
      if (pinnedRid && entry.request_id !== pinnedRid) return false;
      if (!q) return true;
      const hay = [
        entry.msg,
        entry.path,
        entry.logger,
        entry.request_id,
        entry.level,
        entry.method,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, search, pinnedRid]);

  // ---- Groupement par request_id : { rid: [entries...] } ----
  const groupedByRid = useMemo(() => {
    if (!groupByRid) return null;
    const groups = new Map();
    for (const entry of filteredItems) {
      const rid = entry.request_id || "(no-rid)";
      if (!groups.has(rid)) groups.set(rid, []);
      groups.get(rid).push(entry);
    }
    // Trier par ts du log le plus recent (desc)
    return Array.from(groups.entries())
      .map(([rid, entries]) => ({ rid, entries }))
      .sort((a, b) => {
        const ta = new Date(a.entries[0]?.ts || 0).getTime();
        const tb = new Date(b.entries[0]?.ts || 0).getTime();
        return tb - ta;
      });
  }, [filteredItems, groupByRid]);

  // ---- Export JSON des logs filtres ----
  const handleExportJson = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      filters: { level: level || null, search: search || null, pinned_rid: pinnedRid || null },
      count: filteredItems.length,
      items: filteredItems,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  return (
    <PanelCard
      eyebrow="Logs recents"
      title="Logs structures backend"
      subtitle={
        lastFetchAt
          ? `Buffer ${bufferSize} entrees • mis a jour ${formatRelative(lastFetchAt)}`
          : "Chargement..."
      }
      action={
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <Search
              size={12}
              style={{
                position: "absolute",
                left: 8,
                top: "50%",
                transform: "translateY(-50%)",
                color: T.textMuted,
                pointerEvents: "none",
              }}
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher (msg, path, rid...)"
              style={{
                padding: "5px 10px 5px 26px",
                borderRadius: radius.md,
                border: `1px solid ${T.border}`,
                background: T.bgCard,
                color: T.text,
                fontSize: 12,
                fontFamily: font.body,
                width: 220,
              }}
            />
          </div>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            style={selectStyle}
          >
            {LEVEL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={selectStyle}
          >
            {[50, 100, 200, 500].map((n) => (
              <option key={n} value={n}>{`${n} max`}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setGroupByRid((g) => !g)}
            title={groupByRid ? "Mode liste plate" : "Grouper par request_id"}
            style={iconBtnStyle(groupByRid ? T.teal : T.textSecondary)}
          >
            <Layers size={14} />
          </button>
          <button
            type="button"
            onClick={handleExportJson}
            title="Exporter en JSON les logs filtres"
            style={iconBtnStyle(T.textSecondary)}
            disabled={filteredItems.length === 0}
          >
            <Download size={14} />
          </button>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            title={paused ? "Reprendre le poll automatique" : "Mettre en pause le poll automatique"}
            style={iconBtnStyle(paused ? T.orange : T.textSecondary)}
          >
            {paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          <button
            type="button"
            onClick={() => load()}
            title="Rafraichir"
            style={iconBtnStyle(T.teal)}
          >
            <RefreshCw size={14} className={loading ? "uwi-spin" : ""} />
          </button>
        </div>
      }
    >
      {pinnedRid && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 10px",
            marginBottom: 8,
            background: T.tealLight,
            border: `1px solid ${T.teal}40`,
            borderRadius: radius.sm,
            fontSize: 12,
            fontFamily: font.body,
          }}
        >
          <span style={{ color: T.text }}>
            Filtrage sur request_id :{" "}
            <strong style={{ fontFamily: "ui-monospace, monospace" }}>{pinnedRid.slice(0, 12)}…</strong>
          </span>
          <button
            type="button"
            onClick={() => setPinnedRid("")}
            style={{
              marginLeft: "auto",
              padding: "2px 6px",
              border: "none",
              background: "transparent",
              color: T.text,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
            }}
          >
            <X size={12} /> Effacer
          </button>
        </div>
      )}
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
      ) : filteredItems.length === 0 ? (
        <div
          style={{
            padding: 24,
            textAlign: "center",
            color: T.textMuted,
            fontSize: 13,
            fontFamily: font.body,
          }}
        >
          {loading
            ? "Chargement des logs..."
            : items.length === 0
            ? "Aucun log dans le buffer."
            : "Aucun log ne correspond aux filtres."}
        </div>
      ) : groupByRid && groupedByRid ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            maxHeight: 480,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
          {groupedByRid.map((group) => (
            <RidGroup
              key={group.rid}
              rid={group.rid}
              entries={group.entries}
              onPin={() => setPinnedRid(group.rid === "(no-rid)" ? "" : group.rid)}
            />
          ))}
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
          {filteredItems.map((entry, idx) => (
            <LogRow
              key={`${entry.ts}-${idx}`}
              entry={entry}
              expanded={!!expanded[`${entry.ts}-${idx}`]}
              onToggle={() =>
                setExpanded((prev) => ({
                  ...prev,
                  [`${entry.ts}-${idx}`]: !prev[`${entry.ts}-${idx}`],
                }))
              }
              onPinRid={
                entry.request_id ? () => setPinnedRid(entry.request_id) : undefined
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

function RidGroup({ rid, entries, onPin }) {
  // Resume du groupe : 1ere/derniere date, status final, path principal, duree.
  const first = entries[entries.length - 1]; // entries triees desc, le 1er = le plus recent
  const last = entries[0];
  const requestEnd = entries.find((e) => e.msg === "request_end");
  const status = requestEnd?.status_code;
  const duration = requestEnd?.duration_ms;
  const path = requestEnd?.path || first?.path || last?.path;
  const method = requestEnd?.method || first?.method || last?.method;
  const cfg = status >= 500 ? LEVEL_CFG.ERROR : status >= 400 ? LEVEL_CFG.WARNING : LEVEL_CFG.INFO;

  return (
    <div
      style={{
        border: `1px solid ${cfg.color}30`,
        borderRadius: radius.md,
        background: cfg.bg,
        padding: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 12,
          marginBottom: 6,
          fontFamily: font.body,
        }}
      >
        <span
          style={{
            fontFamily: "ui-monospace, monospace",
            fontSize: 11,
            color: T.text,
            fontWeight: 700,
          }}
        >
          {rid === "(no-rid)" ? "(no request_id)" : rid.slice(0, 12) + "…"}
        </span>
        {method && (
          <span style={{ fontSize: 11, color: T.textSecondary }}>{method}</span>
        )}
        {path && (
          <span
            style={{
              fontSize: 11,
              color: T.text,
              fontFamily: "ui-monospace, monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              minWidth: 0,
            }}
          >
            {path}
          </span>
        )}
        {status != null && <span style={statusPillStyle(status)}>{status}</span>}
        {typeof duration === "number" && (
          <span style={{ color: T.textMuted, fontSize: 11, fontFamily: "ui-monospace, monospace" }}>
            {duration}ms
          </span>
        )}
        <span style={{ color: T.textMuted, fontSize: 11 }}>{entries.length} logs</span>
        {onPin && rid !== "(no-rid)" && (
          <button
            type="button"
            onClick={onPin}
            title="Filtrer uniquement ce request_id"
            style={{
              padding: "2px 6px",
              border: `1px solid ${T.border}`,
              background: T.bgCard,
              borderRadius: radius.sm,
              color: T.text,
              cursor: "pointer",
              fontSize: 10,
            }}
          >
            Pin
          </button>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {entries.map((entry, idx) => (
          <LogRow
            key={`${entry.ts}-${idx}`}
            entry={entry}
            expanded={false}
            onToggle={() => {}}
            compact
          />
        ))}
      </div>
    </div>
  );
}

function LogRow({ entry, expanded, onToggle, onPinRid, compact = false }) {
  const cfg = LEVEL_CFG[(entry.level || "").toUpperCase()] || LEVEL_CFG.INFO;
  const ts = entry.ts ? new Date(entry.ts).toLocaleTimeString("fr-FR", { hour12: false }) : "";
  const path = entry.path;
  const method = entry.method;
  const status = entry.status_code;
  const duration = entry.duration_ms;
  const rid = entry.request_id;

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
        background: cfg.bg,
        border: `1px solid ${cfg.color}25`,
        cursor: "pointer",
        fontFamily: font.body,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
        <cfg.Icon size={13} color={cfg.color} strokeWidth={2.4} style={{ flexShrink: 0 }} />
        <span
          style={{
            color: cfg.color,
            fontWeight: 700,
            minWidth: 56,
            fontSize: 11,
            letterSpacing: "0.04em",
          }}
        >
          {entry.level || "INFO"}
        </span>
        <span style={{ color: T.textMuted, fontFamily: "ui-monospace, monospace", fontSize: 11 }}>
          {ts}
        </span>
        <span
          style={{
            color: T.text,
            fontWeight: 500,
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {entry.msg}
        </span>
        {typeof status !== "undefined" && (
          <span style={statusPillStyle(status)}>{status}</span>
        )}
        {typeof duration === "number" && (
          <span style={{ color: T.textMuted, fontSize: 11, fontFamily: "ui-monospace, monospace" }}>
            {duration}ms
          </span>
        )}
      </div>
      {(path || rid) && (
        <div
          style={{
            display: "flex",
            gap: 10,
            fontSize: 11,
            color: T.textSecondary,
            fontFamily: "ui-monospace, monospace",
            marginLeft: 21,
          }}
        >
          {method && <span>{method}</span>}
          {path && <span style={{ color: T.text }}>{path}</span>}
          {rid && (
            <span
              role={onPinRid ? "button" : undefined}
              tabIndex={onPinRid ? 0 : -1}
              onClick={(e) => {
                if (!onPinRid) return;
                e.stopPropagation();
                onPinRid();
              }}
              onKeyDown={(e) => {
                if (!onPinRid) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onPinRid();
                }
              }}
              title={onPinRid ? "Cliquer pour filtrer ce request_id" : undefined}
              style={{
                color: T.textMuted,
                cursor: onPinRid ? "pointer" : "default",
                textDecoration: onPinRid ? "underline dotted" : "none",
              }}
            >
              rid={String(rid).slice(0, 8)}
            </span>
          )}
          {entry.logger && <span style={{ color: T.textMuted, marginLeft: "auto" }}>{entry.logger}</span>}
        </div>
      )}
      {expanded && (
        <pre
          style={{
            marginTop: 4,
            marginLeft: 21,
            padding: 8,
            background: T.bgCard,
            border: `1px solid ${T.border}`,
            borderRadius: radius.sm,
            fontSize: 11,
            color: T.textSecondary,
            overflowX: "auto",
            maxHeight: 200,
            fontFamily: "ui-monospace, monospace",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {JSON.stringify(entry, null, 2)}
        </pre>
      )}
    </div>
  );
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
