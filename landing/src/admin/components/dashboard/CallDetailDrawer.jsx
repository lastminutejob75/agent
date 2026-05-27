import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  X,
  RefreshCw,
  Copy,
  CheckCheck,
  Phone,
  Clock,
  User,
  CalendarCheck,
  ArrowRight,
  ArrowLeftRight,
  XCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { adminApi } from "../../../lib/adminApi";
import { T, font, radius, shadow, formatTime, formatDateShort } from "../../theme.js";
import { Button } from "../ui/Button.jsx";
import { Badge } from "../ui/Badge.jsx";

/**
 * Drawer partagé pour afficher le détail d'un appel.
 * Utilisé depuis AdminDashboard (flux d'activité), AdminCalls (table) et AdminTenantPage (onglet Appels).
 *
 * Props :
 *  - tenantId, callId : identifient l'appel (si null, le drawer est fermé)
 *  - tenantName : optionnel, affiché dans l'entête
 *  - onClose : callback de fermeture
 */

const RESULT_CFG = {
  rdv: { label: "RDV confirmé", variant: "green", icon: CalendarCheck },
  booking_confirmed: { label: "RDV confirmé", variant: "green", icon: CalendarCheck },
  transfer: { label: "Transfert humain", variant: "yellow", icon: ArrowLeftRight },
  transferred: { label: "Transfert humain", variant: "yellow", icon: ArrowLeftRight },
  transferred_human: { label: "Transfert humain", variant: "yellow", icon: ArrowLeftRight },
  abandoned: { label: "Abandon", variant: "orange", icon: XCircle },
  user_abandon: { label: "Abandon", variant: "orange", icon: XCircle },
  abandon: { label: "Abandon", variant: "orange", icon: XCircle },
  error: { label: "Erreur", variant: "red", icon: AlertCircle },
  other: { label: "Autre", variant: "neutral", icon: Phone },
};

function ResultBadge({ result }) {
  const cfg = RESULT_CFG[(result || "").toLowerCase()] || RESULT_CFG.other;
  const Icon = cfg.icon;
  return (
    <Badge variant={cfg.variant} size="md">
      <Icon size={12} strokeWidth={2.4} style={{ marginRight: 4 }} />
      {cfg.label}
    </Badge>
  );
}

function formatDuration(detail) {
  const sec = Number(detail?.duration_sec);
  if (Number.isFinite(sec) && sec >= 0) {
    const min = Math.floor(sec / 60);
    const rem = sec % 60;
    return `${min}'${String(rem).padStart(2, "0")}`;
  }
  const m = Number(detail?.duration_min);
  if (Number.isFinite(m) && m >= 0) return `${Math.floor(m)}'00`;
  return "—";
}

function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${formatDateShort(d)} · ${formatTime(d)}`;
}

// ---------------------------------------------------------------------------

export default function CallDetailDrawer({ tenantId, callId, tenantName, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showTranscript, setShowTranscript] = useState(true);

  const open = Boolean(tenantId && callId);

  const fetchDetail = useCallback(async () => {
    if (!tenantId || !callId) return;
    setLoading(true);
    setError(null);
    try {
      const d = await adminApi.getCallDetail(tenantId, callId);
      setDetail(d);
    } catch (e) {
      setError(e?.message || "Impossible de charger le détail");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [tenantId, callId]);

  useEffect(() => {
    if (open) {
      setDetail(null);
      fetchDetail();
    }
  }, [open, fetchDetail]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const copyCallId = () => {
    if (!callId) return;
    navigator.clipboard.writeText(callId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };

  if (!open) return null;

  return (
    <>
      <style>{`
        @keyframes uwi-drawer-slide-in {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes uwi-drawer-overlay-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>

      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(15,23,42,0.32)",
          zIndex: 999,
          animation: "uwi-drawer-overlay-in 0.15s ease both",
          backdropFilter: "blur(2px)",
        }}
      />

      {/* Drawer */}
      <aside
        role="dialog"
        aria-label="Détail de l'appel"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(520px, 100vw)",
          background: T.bgCard,
          borderLeft: `1px solid ${T.border}`,
          boxShadow: shadow.raised,
          zIndex: 1000,
          display: "flex",
          flexDirection: "column",
          fontFamily: font.body,
          animation: "uwi-drawer-slide-in 0.22s ease both",
        }}
      >
        {/* Header */}
        <header
          style={{
            padding: "18px 22px 14px",
            borderBottom: `1px solid ${T.border}`,
            background: T.bgCard,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <div style={{ minWidth: 0, flex: 1 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: T.teal,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 4,
                }}
              >
                Détail appel
              </div>
              <h2
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontWeight: 600,
                  color: T.text,
                  fontFamily: font.body,
                  lineHeight: 1.3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {tenantName ? tenantName : `Tenant #${tenantId}`}
              </h2>
              {detail?.started_at ? (
                <div style={{ fontSize: 12, color: T.textSecondary, marginTop: 4 }}>
                  {formatDateTime(detail.started_at)}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fermer"
              style={{
                background: "transparent",
                border: "none",
                padding: 6,
                color: T.textSecondary,
                cursor: "pointer",
                borderRadius: radius.sm,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "background 0.12s, color 0.12s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = T.bgSubtle;
                e.currentTarget.style.color = T.text;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = T.textSecondary;
              }}
            >
              <X size={18} strokeWidth={2.2} />
            </button>
          </div>

          {/* Result badge + meta line */}
          {detail ? (
            <div
              style={{
                display: "flex",
                gap: 10,
                alignItems: "center",
                flexWrap: "wrap",
                marginTop: 12,
              }}
            >
              <ResultBadge result={detail.result} />
              <span style={{ fontSize: 12, color: T.textSecondary, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <Clock size={12} strokeWidth={2.2} /> {formatDuration(detail)}
              </span>
              {detail.customer_number ? (
                <span style={{ fontSize: 12, color: T.textSecondary, display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <User size={12} strokeWidth={2.2} /> {detail.customer_number}
                </span>
              ) : null}
            </div>
          ) : null}
        </header>

        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 22px 24px",
          }}
        >
          {loading && !detail ? (
            <SkeletonBody />
          ) : error ? (
            <div
              style={{
                padding: 16,
                background: T.redLight,
                border: `1px solid ${T.red}30`,
                borderRadius: radius.md,
                color: T.red,
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {error}
            </div>
          ) : !detail ? (
            <div style={{ padding: 16, color: T.textMuted, fontSize: 13 }}>
              Aucun détail disponible pour cet appel.
            </div>
          ) : (
            <>
              <Section title="Identifiant">
                <CallIdRow callId={detail.call_id} onCopy={copyCallId} copied={copied} />
              </Section>

              <Section title="Timeline">
                {!detail.events || detail.events.length === 0 ? (
                  <div style={{ fontSize: 12, color: T.textMuted, padding: "8px 0" }}>
                    Aucun événement enregistré.
                  </div>
                ) : (
                  <Timeline events={detail.events} />
                )}
              </Section>

              {detail.transcript ? (
                <Section
                  title="Transcription"
                  toggle={() => setShowTranscript((v) => !v)}
                  expanded={showTranscript}
                >
                  {showTranscript ? <Transcript text={detail.transcript} /> : null}
                </Section>
              ) : null}
            </>
          )}
        </div>

        {/* Footer actions */}
        <footer
          style={{
            borderTop: `1px solid ${T.border}`,
            padding: "12px 22px",
            background: T.bgCard,
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchDetail}
              disabled={loading}
              iconLeft={<RefreshCw size={13} strokeWidth={2.2} />}
            >
              Rafraîchir
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={copyCallId}
              iconLeft={
                copied ? (
                  <CheckCheck size={13} strokeWidth={2.4} />
                ) : (
                  <Copy size={13} strokeWidth={2.2} />
                )
              }
            >
              {copied ? "Copié" : "Copier ID"}
            </Button>
          </div>
          {tenantId ? (
            <Link
              to={`/admin/tenants/${tenantId}/calls`}
              onClick={onClose}
              style={{ textDecoration: "none" }}
            >
              <Button
                variant="primary"
                size="sm"
                iconRight={<ArrowRight size={13} strokeWidth={2.4} />}
              >
                Tous les appels
              </Button>
            </Link>
          ) : null}
        </footer>
      </aside>
    </>
  );
}

// ---------------------------------------------------------------------------

function Section({ title, children, toggle, expanded = true }) {
  return (
    <section style={{ marginBottom: 20 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: T.textSecondary,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {title}
        </div>
        {toggle ? (
          <button
            type="button"
            onClick={toggle}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: 4,
              color: T.textSecondary,
              borderRadius: radius.sm,
            }}
            aria-label={expanded ? "Replier" : "Déplier"}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function CallIdRow({ callId, onCopy, copied }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        background: T.bgSubtle,
        border: `1px solid ${T.border}`,
        borderRadius: radius.md,
        padding: "8px 12px",
      }}
    >
      <code
        style={{
          flex: 1,
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: 12,
          color: T.text,
          wordBreak: "break-all",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {callId}
      </code>
      <button
        type="button"
        onClick={onCopy}
        aria-label="Copier l'ID"
        style={{
          background: "transparent",
          border: "none",
          padding: 4,
          color: copied ? T.green : T.textSecondary,
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
      </button>
    </div>
  );
}

function Timeline({ events }) {
  return (
    <ol
      style={{
        margin: 0,
        padding: 0,
        listStyle: "none",
        position: "relative",
      }}
    >
      {events.map((ev, i) => (
        <li
          key={`${ev.created_at}-${i}`}
          style={{
            display: "grid",
            gridTemplateColumns: "70px 1fr",
            gap: 12,
            padding: "8px 0",
            borderTop: i === 0 ? "none" : `1px dashed ${T.border}`,
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: T.textMuted,
              fontFamily: "ui-monospace, monospace",
              paddingTop: 2,
              whiteSpace: "nowrap",
            }}
          >
            {ev.created_at ? formatTime(ev.created_at) : "—"}
          </div>
          <div>
            <div
              style={{
                fontSize: 13,
                color: T.text,
                fontWeight: 600,
              }}
            >
              {ev.event}
            </div>
            {ev.meta && Object.keys(ev.meta).length > 0 ? (
              <EventMeta meta={ev.meta} />
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function EventMeta({ meta }) {
  const interesting = {};
  for (const k of Object.keys(meta)) {
    if (k === "context") continue;
    if (meta[k] === null || meta[k] === undefined) continue;
    interesting[k] = meta[k];
  }
  if (Object.keys(interesting).length === 0) return null;
  return (
    <div
      style={{
        marginTop: 4,
        display: "flex",
        flexWrap: "wrap",
        gap: 4,
      }}
    >
      {Object.entries(interesting).map(([k, v]) => (
        <span
          key={k}
          style={{
            fontSize: 11,
            background: T.bgSubtle,
            border: `1px solid ${T.border}`,
            borderRadius: radius.sm,
            padding: "2px 6px",
            color: T.textSecondary,
            fontFamily: "ui-monospace, monospace",
            maxWidth: 280,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={`${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`}
        >
          <strong style={{ color: T.text }}>{k}</strong>
          : {typeof v === "string" ? v : JSON.stringify(v)}
        </span>
      ))}
    </div>
  );
}

function Transcript({ text }) {
  const lines = text
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean);
  return (
    <div
      style={{
        background: T.bgSubtle,
        border: `1px solid ${T.border}`,
        borderRadius: radius.md,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {lines.map((line, i) => {
        const isAssistant = /^assistant\s*:/i.test(line);
        const isUser = /^(patient|user)\s*:/i.test(line);
        const cleaned = line.replace(/^(assistant|patient|user)\s*:\s*/i, "");
        const role = isAssistant ? "Assistant" : isUser ? "Patient" : null;
        const align = isAssistant ? "flex-start" : isUser ? "flex-end" : "flex-start";
        return (
          <div
            key={i}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: align,
              maxWidth: "100%",
            }}
          >
            {role ? (
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: isAssistant ? T.teal : T.textMuted,
                  marginBottom: 2,
                }}
              >
                {role}
              </div>
            ) : null}
            <div
              style={{
                fontSize: 13,
                lineHeight: 1.5,
                color: T.text,
                background: isAssistant ? T.tealLight : T.bgCard,
                border: `1px solid ${isAssistant ? `${T.teal}20` : T.border}`,
                borderRadius: radius.md,
                padding: "8px 12px",
                maxWidth: "85%",
              }}
            >
              {cleaned}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SkeletonBody() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            height: 18 + (i % 2) * 12,
            background: `linear-gradient(90deg, ${T.bgSubtle}, ${T.neutralLight}, ${T.bgSubtle})`,
            backgroundSize: "200% 100%",
            borderRadius: radius.sm,
            animation: "uwi-shimmer 1.5s infinite",
          }}
        />
      ))}
    </div>
  );
}
