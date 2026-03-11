import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

function Skeleton({ height = 80, radius = 14 }) {
  return (
    <div
      style={{
        height,
        borderRadius: radius,
        background: "linear-gradient(90deg, #eef2f7 25%, #e6ebf2 50%, #eef2f7 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-calls-shimmer 1.35s infinite linear",
      }}
    />
  );
}

const ERROR_BOX = {
  borderRadius: 14,
  border: "1px solid #fecaca",
  background: "#fef2f2",
  color: "#b91c1c",
  padding: "12px 14px",
  fontSize: 14,
  fontWeight: 600,
};

async function copyToClipboard(text) {
  if (!text || !navigator?.clipboard?.writeText) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function getActionLabel(call) {
  return call?.contextual_action?.label || "Voir le détail";
}

function getDialablePhone(value) {
  const raw = String(value || "").trim();
  if (!raw || /num[eé]ro non identifi[eé]/i.test(raw)) return "";
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("00")) return `+${cleaned.slice(2)}`;
  return cleaned;
}

function getDisplayedPhone(value) {
  const raw = String(value || "").trim();
  return raw || "Numéro non identifié";
}

function getPhoneIconTheme(status) {
  if (status === "CONFIRMED" || status === "FAQ") {
    return { bg: "#ecfdf5", color: "#16a34a", border: "#bbf7d0" };
  }
  return { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" };
}

const T = {
  teal: "#0DC991",
  tealDark: "#0AAF7A",
  tealLight: "#E8FAF4",
  tealBorder: "#A7F3D0",
  orange: "#F97316",
  orangeLight: "#FFF7ED",
  orangeBorder: "#FDBA74",
  purple: "#8B5CF6",
  purpleLight: "#F5F3FF",
  purpleBorder: "#DDD6FE",
  red: "#EF4444",
  redLight: "#FEF2F2",
  redBorder: "#FCA5A5",
  blue: "#3B82F6",
  blueLight: "#EFF6FF",
  blueBorder: "#BFDBFE",
  text: "#0f172a",
  textMid: "#334155",
  textSoft: "#64748b",
  textFaint: "#94a3b8",
  border: "#e2e8f0",
  borderLight: "#f1f5f9",
  bg: "#f1f5f9",
  card: "#ffffff",
};

const MODEL_STATUS = {
  ok: { label: "OK", color: T.tealDark, bg: T.tealLight, border: T.tealBorder },
  missed: { label: "Manqué", color: T.red, bg: T.redLight, border: T.redBorder },
  planned: { label: "Prévu", color: T.blue, bg: T.blueLight, border: T.blueBorder },
  callback: { label: "Rappel", color: T.orange, bg: T.orangeLight, border: T.orangeBorder },
};

const MODEL_INTENTS = {
  rdv: { label: "Prise de RDV", color: T.tealDark, bg: T.tealLight },
  cancel: { label: "Annulation RDV", color: T.red, bg: T.redLight },
  info: { label: "Demande d'info", color: T.blue, bg: T.blueLight },
  hours: { label: "Horaires", color: T.orange, bg: T.orangeLight },
  urgent: { label: "Urgence", color: "#DC2626", bg: "#FEF2F2" },
  reschedule: { label: "Reprogrammation", color: T.purple, bg: T.purpleLight },
};

function getModelStatusKey(call) {
  if ((call?.followup_state || "") === "callback") return "callback";
  if (call?.status === "ABANDONED" || call?.status === "TRANSFERRED") return "missed";
  if (call?.contextual_action?.kind === "followup_callback") return "planned";
  return "ok";
}

function getModelIntentKey(call) {
  const summary = String(call?.summary || "").toLowerCase();
  if (call?.reason_category === "urgency") return "urgent";
  if (call?.reason_category === "agenda" || call?.status === "CONFIRMED") {
    if (/annul/.test(summary)) return "cancel";
    if (/reprogramm|déplac|deplac/.test(summary)) return "reschedule";
    return "rdv";
  }
  if (/horaire/.test(summary)) return "hours";
  return "info";
}

function getModelStatusUi(call) {
  return MODEL_STATUS[getModelStatusKey(call)] || MODEL_STATUS.ok;
}

function getModelIntentUi(call) {
  return MODEL_INTENTS[getModelIntentKey(call)] || MODEL_INTENTS.info;
}

function getIntentGlyph(intent) {
  switch (intent) {
    case "rdv":
      return "📅";
    case "cancel":
      return "❌";
    case "hours":
      return "🕒";
    case "urgent":
      return "🚨";
    case "reschedule":
      return "🔁";
    case "info":
    default:
      return "💬";
  }
}

function parseHourFromTime(value) {
  const match = String(value || "").match(/(\d{1,2})[:h]/i);
  return match ? Number(match[1]) : -1;
}

function parseDurationMinutes(value) {
  const text = String(value || "").trim();
  if (!text || text === "—") return 0;
  if (/^\d+$/.test(text)) return Number(text);
  const colon = text.match(/^(\d{1,2}):(\d{2})$/);
  if (colon) return Number(colon[1]) + Math.round(Number(colon[2]) / 60);
  const minutes = text.match(/(\d+)\s*(min|m)/i);
  if (minutes) return Number(minutes[1]);
  return 0;
}

function extractRdv(call) {
  const summary = String(call?.summary || "");
  const reasonLabel = String(call?.reason_label || "");
  if (!(call?.status === "CONFIRMED" || call?.reason_category === "agenda" || /rdv|rendez-vous/i.test(summary))) {
    return null;
  }
  const dateMatch = summary.match(/\b(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\b/);
  const timeMatch = summary.match(/(?:à|a)\s*(\d{1,2}(?::\d{2}|h\d{0,2})?)/i) || summary.match(/\b(\d{1,2}:\d{2})\b/);
  return {
    date: dateMatch?.[1] || "Date à confirmer",
    time: (timeMatch?.[1] || call?.time || "—").replace(/^(\d{1,2})h$/, "$1h00"),
    type: reasonLabel || "Consultation",
  };
}

function buildTranscriptLines(transcript) {
  const text = String(transcript || "").trim();
  if (!text) return [];
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      if (/^(agent|uwi|assistant)\s*:/i.test(line)) {
        return { speaker: "agent", text: line.replace(/^[^:]+:\s*/i, "") };
      }
      if (/^(patient|client|caller|appelant)\s*:/i.test(line)) {
        return { speaker: "patient", text: line.replace(/^[^:]+:\s*/i, "") };
      }
      return { speaker: index % 2 === 0 ? "patient" : "agent", text: line };
    });
}

function deriveAiScore(call) {
  const confidence =
    call?.status === "CONFIRMED" ? 94 :
      call?.status === "FAQ" ? 86 :
        call?.status === "TRANSFERRED" ? 62 :
          call?.status === "ABANDONED" ? 38 : 72;
  const sentiment = call?.reason_category === "urgency" ? "négatif" : call?.status === "CONFIRMED" ? "positif" : "neutre";
  const resolved = Boolean(call?.status === "CONFIRMED" || call?.status === "FAQ" || call?.followup_state === "processed");
  return { confidence, sentiment, resolved };
}

function normalizeSummaryCall(call) {
  return {
    id: call?.call_id || call?.id || "",
    name: call?.patient_name || "Patient",
    phone: getDisplayedPhone(call?.customer_number),
    dialablePhone: getDialablePhone(call?.customer_number),
    time: call?.time || "—",
    hour: parseHourFromTime(call?.time),
    durationFmt: call?.duration || "—",
    status: getModelStatusKey(call),
    statusUi: getModelStatusUi(call),
    intent: getModelIntentKey(call),
    intentUi: getModelIntentUi(call),
    aiHandled: call?.status !== "ABANDONED",
    recalled: call?.followup_state === "processed",
    summary: call?.summary || "Aucun résumé disponible.",
    rdv: extractRdv(call),
    aiScore: deriveAiScore(call),
    transcript: [],
    raw: call,
  };
}

function normalizeDetailCall(detail, fallback) {
  const base = detail || fallback?.raw || {};
  return {
    id: base?.call_id || fallback?.id || "",
    name: fallback?.name || base?.patient_name || "Patient",
    phone: getDisplayedPhone(base?.customer_number || fallback?.phone),
    dialablePhone: getDialablePhone(base?.customer_number || fallback?.dialablePhone),
    time: base?.started_time || fallback?.time || "—",
    hour: parseHourFromTime(base?.started_time || fallback?.time),
    durationFmt: base?.duration || fallback?.durationFmt || "—",
    status: getModelStatusKey(base),
    statusUi: getModelStatusUi(base),
    intent: getModelIntentKey(base),
    intentUi: getModelIntentUi(base),
    aiHandled: base?.status !== "ABANDONED",
    recalled: base?.followup_state === "processed",
    summary: base?.summary || fallback?.summary || "Aucun résumé disponible.",
    rdv: extractRdv(base) || fallback?.rdv || null,
    aiScore: deriveAiScore(base),
    transcript: buildTranscriptLines(base?.transcript),
    raw: base,
  };
}

function buildSparkSeries(calls) {
  const bins = [
    { min: 0, max: 8 },
    { min: 8, max: 10 },
    { min: 10, max: 12 },
    { min: 12, max: 14 },
    { min: 14, max: 16 },
    { min: 16, max: 18 },
    { min: 18, max: 24 },
  ];
  const seeded = bins.map((bin) => calls.filter((call) => call.hour >= bin.min && call.hour < bin.max));
  return {
    calls: seeded.map((items) => items.length || 0),
    rdv: seeded.map((items) => items.filter((call) => call.intent === "rdv" || call.intent === "reschedule").length || 0),
    rate: seeded.map((items) => {
      if (!items.length) return 0;
      const resolved = items.filter((call) => call.aiScore?.resolved).length;
      return Math.round((resolved / items.length) * 100);
    }),
    duration: seeded.map((items) => {
      if (!items.length) return 0;
      const total = items.reduce((sum, call) => sum + parseDurationMinutes(call.durationFmt), 0);
      return Math.round(total / items.length);
    }),
  };
}

function Sparkline({ data, color, w = 110, h = 34 }) {
  const safe = data.some((value) => value > 0) ? data : [0, 0, 0, 0, 0, 0, 0];
  const min = Math.min(...safe);
  const max = Math.max(...safe);
  const range = max - min || 1;
  const pts = safe.map((v, i) => {
    const x = (i / (safe.length - 1 || 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  }).join(" ");
  const [lastX, lastY] = pts.split(" ").pop().split(",");
  const gradientId = `g${String(color).replace("#", "")}`;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${gradientId})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="3" fill={color} />
    </svg>
  );
}

function AIScoreCard({ score }) {
  if (!score) {
    return (
      <div style={{ background: T.bg, border: `1px solid ${T.borderLight}`, borderRadius: "12px", padding: "16px", textAlign: "center", color: T.textFaint, fontSize: "12px" }}>
        Aucune analyse disponible pour cet appel
      </div>
    );
  }
  const confColor = score.confidence >= 90 ? T.tealDark : score.confidence >= 75 ? T.orange : T.red;
  const sentEmoji = score.sentiment === "positif" ? "😊" : score.sentiment === "négatif" ? "😟" : "😐";
  const sentColor = score.sentiment === "positif" ? T.tealDark : score.sentiment === "négatif" ? T.red : T.textSoft;
  return (
    <div style={{ background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "12px", padding: "16px" }}>
      <div style={{ fontSize: "11px", fontWeight: 700, color: T.purple, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "14px" }}>Analyse UWI</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Confiance</div>
          <div style={{ position: "relative", width: "56px", height: "56px", margin: "0 auto 6px" }}>
            <svg width="56" height="56" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="28" cy="28" r="22" fill="none" stroke={T.purpleBorder} strokeWidth="5" />
              <circle
                cx="28"
                cy="28"
                r="22"
                fill="none"
                stroke={confColor}
                strokeWidth="5"
                strokeDasharray={`${2 * Math.PI * 22}`}
                strokeDashoffset={`${2 * Math.PI * 22 * (1 - score.confidence / 100)}`}
                strokeLinecap="round"
              />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "13px", fontWeight: 800, color: confColor }}>
              {score.confidence}%
            </div>
          </div>
          <div style={{ fontSize: "10px", color: confColor, fontWeight: 600 }}>
            {score.confidence >= 90 ? "Élevée" : score.confidence >= 75 ? "Bonne" : "Faible"}
          </div>
        </div>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Sentiment</div>
          <div style={{ fontSize: "32px", marginBottom: "4px" }}>{sentEmoji}</div>
          <div style={{ fontSize: "11px", fontWeight: 600, color: sentColor }}>{score.sentiment}</div>
        </div>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "10px", color: T.purple, marginBottom: "8px" }}>Résolution</div>
          <div style={{ fontSize: "32px", marginBottom: "4px" }}>{score.resolved ? "✅" : "❌"}</div>
          <div style={{ fontSize: "11px", fontWeight: 600, color: score.resolved ? T.tealDark : T.red }}>
            {score.resolved ? "Résolu" : "Escalade"}
          </div>
        </div>
      </div>
    </div>
  );
}

function TranscriptView({ lines }) {
  if (!lines || lines.length === 0) {
    return (
      <div style={{ padding: "24px 0", textAlign: "center", color: T.textFaint, fontSize: "12px" }}>
        <div style={{ fontSize: "28px", marginBottom: "8px" }}>💬</div>
        Aucune transcription disponible
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {lines.map((line, index) => {
        const isAgent = line.speaker === "agent";
        return (
          <div key={`${line.text}-${index}`} style={{ display: "flex", flexDirection: isAgent ? "row-reverse" : "row", alignItems: "flex-start", gap: "9px" }}>
            <div style={{ width: "28px", height: "28px", borderRadius: "50%", background: isAgent ? T.tealLight : "#f0f4ff", border: `1px solid ${isAgent ? T.tealBorder : T.blueBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px", flexShrink: 0 }}>
              {isAgent ? "🤖" : "👤"}
            </div>
            <div style={{ maxWidth: "78%", background: isAgent ? T.tealLight : "#f8fafc", border: `1px solid ${isAgent ? T.tealBorder : T.borderLight}`, borderRadius: isAgent ? "14px 4px 14px 14px" : "4px 14px 14px 14px", padding: "9px 12px" }}>
              <div style={{ fontSize: "9px", fontWeight: 700, color: isAgent ? T.tealDark : T.textFaint, marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.07em" }}>
                {isAgent ? "Agent UWI" : "Patient"}
              </div>
              <div style={{ fontSize: "12px", color: T.textMid, lineHeight: 1.55 }}>{line.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RdvTooltip({ rdv }) {
  return (
    <div style={{ position: "absolute", bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)", zIndex: 999, background: T.text, borderRadius: "10px", padding: "10px 13px", width: "200px", boxShadow: "0 8px 24px rgba(0,0,0,0.18)", pointerEvents: "none", whiteSpace: "nowrap" }}>
      <div style={{ position: "absolute", bottom: "-6px", left: "50%", transform: "translateX(-50%)", width: 0, height: 0, borderLeft: "6px solid transparent", borderRight: "6px solid transparent", borderTop: `6px solid ${T.text}` }} />
      <div style={{ fontSize: "10px", fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "6px" }}>📅 Rendez-vous créé</div>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
          <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)" }}>Type</span>
          <span style={{ fontSize: "12px", fontWeight: 700, color: "#fff" }}>{rdv.type}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
          <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)" }}>Date</span>
          <span style={{ fontSize: "12px", fontWeight: 700, color: "#fff" }}>{rdv.date}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
          <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)" }}>Heure</span>
          <span style={{ fontSize: "12px", fontWeight: 700, color: T.teal }}>{rdv.time}</span>
        </div>
      </div>
    </div>
  );
}

function CallRowModel({ call, onOpen, onRecall, isLast }) {
  const [hov, setHov] = useState(false);
  const [rdvHov, setRdvHov] = useState(false);
  const dialablePhone = getDialablePhone(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
  const intentGlyph = getIntentGlyph(call.intent);
  return (
    <div
      className="calls-row"
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      onClick={() => onOpen(call)}
      style={{ display: "flex", alignItems: "center", gap: "13px", padding: "13px 18px", borderBottom: isLast ? "none" : `1px solid ${T.borderLight}`, cursor: "pointer", background: hov ? "#fafcff" : "transparent", transition: "background 0.1s" }}
    >
      {dialablePhone ? (
        <a
          href={`tel:${dialablePhone}`}
          onClick={(e) => e.stopPropagation()}
          title={`Appeler ${call.name || call.phone}`}
          aria-label={`Appeler ${call.name || call.phone}`}
          style={{ width: "40px", height: "40px", borderRadius: "11px", background: call.intentUi.bg, border: `1px solid ${call.intent === "urgent" ? T.redBorder : call.intent === "reschedule" ? T.purpleBorder : call.intent === "hours" ? T.orangeBorder : call.intent === "info" ? T.blueBorder : T.tealBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "17px", flexShrink: 0, textDecoration: "none", boxShadow: hov ? "0 6px 18px rgba(15,23,42,0.08)" : "none" }}
        >
          {intentGlyph}
        </a>
      ) : (
        <div style={{ width: "40px", height: "40px", borderRadius: "11px", background: call.intentUi.bg, border: `1px solid ${call.intent === "urgent" ? T.redBorder : call.intent === "reschedule" ? T.purpleBorder : call.intent === "hours" ? T.orangeBorder : call.intent === "info" ? T.blueBorder : T.tealBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "17px", flexShrink: 0 }}>
          {intentGlyph}
        </div>
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "14px", fontWeight: 700, color: T.text }}>{call.name}</span>
          {call.aiHandled ? <span style={{ fontSize: "9px", fontWeight: 800, color: T.purple, background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "4px", padding: "1px 5px", letterSpacing: "0.02em" }}>IA</span> : null}
          {call.intent === "urgent" ? <span style={{ fontSize: "9px", fontWeight: 800, color: T.red, background: T.redLight, border: `1px solid ${T.redBorder}`, borderRadius: "4px", padding: "1px 5px", letterSpacing: "0.02em" }}>⚠ URGENT</span> : null}
          {call.rdv ? (
            <div
              style={{ position: "relative", display: "inline-flex" }}
              onMouseEnter={(e) => { e.stopPropagation(); setRdvHov(true); }}
              onMouseLeave={(e) => { e.stopPropagation(); setRdvHov(false); }}
              onClick={(e) => e.stopPropagation()}
            >
              <span style={{ fontSize: "9px", fontWeight: 800, color: T.tealDark, background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "4px", padding: "1px 6px", cursor: "default", userSelect: "none", letterSpacing: "0.02em" }}>
                📅 RDV
              </span>
              {rdvHov ? <RdvTooltip rdv={call.rdv} /> : null}
            </div>
          ) : null}
        </div>
        <div style={{ fontSize: "11px", marginBottom: "6px" }}>
          {dialablePhone ? (
            <a
              href={`tel:${dialablePhone}`}
              onClick={(e) => e.stopPropagation()}
              style={{ color: call.statusUi.color, fontWeight: 700, textDecoration: "none" }}
            >
              {call.phone}
            </a>
          ) : (
            <span style={{ color: T.textFaint }}>{call.phone}</span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
          <span style={{ fontSize: "10px", fontWeight: 700, color: call.intentUi.color, background: call.intentUi.bg, borderRadius: "5px", padding: "2px 7px", flexShrink: 0 }}>{call.intentUi.label}</span>
          <span style={{ fontSize: "11px", color: T.textSoft, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{call.summary}</span>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "5px", flexShrink: 0 }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: T.textMid }}>{call.time}</span>
        <span style={{ fontSize: "11px", fontWeight: 700, color: call.statusUi.color, background: call.statusUi.bg, border: `1px solid ${call.statusUi.border}`, borderRadius: "20px", padding: "2px 9px" }}>{call.statusUi.label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {call.durationFmt !== "—" && call.durationFmt !== "0:00" ? <span style={{ fontSize: "10px", color: T.textFaint }}>{call.durationFmt}</span> : null}
          {call.aiScore ? (
            <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
              <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: call.aiScore.confidence >= 90 ? T.teal : call.aiScore.confidence >= 75 ? T.orange : T.red }} />
              <span style={{ fontSize: "10px", color: T.textFaint }}>{call.aiScore.confidence}%</span>
            </div>
          ) : null}
        </div>
        {(call.status === "missed" || call.status === "callback") ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRecall(call);
            }}
            style={{ fontSize: "11px", fontWeight: 700, color: call.recalled ? "#fff" : T.orange, background: call.recalled ? T.tealDark : T.orangeLight, border: `1px solid ${call.recalled ? T.tealBorder : T.orangeBorder}`, borderRadius: "7px", padding: "3px 10px", cursor: "pointer", transition: "all 0.2s" }}
          >
            {call.recalled ? "✓ Rappelé" : "Rappeler"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function CallDetailModal({
  call,
  onClose,
  onRecall,
  onContextAction,
  onMarkCallback,
  onMarkProcessed,
  onCopyTranscript,
  onCopySummary,
  onCopyId,
  followupNotes,
  setFollowupNotes,
  onSaveNotes,
  followupLoading,
  actionMessage,
}) {
  const [tab, setTab] = useState("summary");
  if (!call) return null;
  const dialablePhone = getDialablePhone(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
  const intentGlyph = getIntentGlyph(call.intent);
  const primaryActionLabel = getActionLabel(call?.raw || call);
  const followupState = call?.raw?.followup_state || "new";
  const followupBadge =
    followupState === "processed"
      ? { label: "Traité", color: T.tealDark, bg: T.tealLight, border: T.tealBorder }
      : followupState === "callback"
        ? { label: "À rappeler", color: T.orange, bg: T.orangeLight, border: T.orangeBorder }
        : { label: "Nouveau", color: T.textSoft, bg: T.bg, border: T.border };
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(15,23,42,0.3)", backdropFilter: "blur(5px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div className="calls-modal-panel" style={{ background: T.card, borderRadius: "20px", width: "540px", maxWidth: "94vw", maxHeight: "88vh", boxShadow: "0 24px 60px rgba(0,0,0,0.15)", overflow: "hidden", display: "flex", flexDirection: "column" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ height: "4px", background: call.status === "ok" ? `linear-gradient(90deg,${T.teal},${T.tealDark})` : call.statusUi.color }} />

        <div style={{ padding: "20px 22px 0", flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: call.intentUi.bg, border: `1px solid ${call.intent === "urgent" ? T.redBorder : call.intent === "reschedule" ? T.purpleBorder : call.intent === "hours" ? T.orangeBorder : call.intent === "info" ? T.blueBorder : T.tealBorder}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px" }}>
                {intentGlyph}
              </div>
              <div>
                <div style={{ fontSize: "17px", fontWeight: 800, color: T.text }}>{call.name}</div>
                <div style={{ fontSize: "12px", color: T.textSoft, marginTop: "1px" }}>
                  {dialablePhone ? (
                    <a href={`tel:${dialablePhone}`} style={{ color: call.statusUi.color, fontWeight: 700, textDecoration: "none" }}>
                      {call.phone}
                    </a>
                  ) : (
                    call.phone
                  )}
                  {" · "}
                  {call.time}
                  {" · "}
                  {call.durationFmt}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: call.intentUi.color, background: call.intentUi.bg, borderRadius: 999, padding: "3px 8px" }}>
                    {call.intentUi.label}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: followupBadge.color, background: followupBadge.bg, border: `1px solid ${followupBadge.border}`, borderRadius: 999, padding: "3px 8px" }}>
                    {followupBadge.label}
                  </span>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: "7px", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 700, color: call.statusUi.color, background: call.statusUi.bg, border: `1px solid ${call.statusUi.border}`, borderRadius: "20px", padding: "3px 10px" }}>{call.statusUi.label}</span>
              {call.aiHandled ? <span style={{ fontSize: "10px", fontWeight: 800, color: T.purple, background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "20px", padding: "3px 9px" }}>🤖 IA</span> : null}
              <button type="button" onClick={onClose} style={{ background: "#f8fafc", border: `1px solid ${T.border}`, borderRadius: "8px", width: "30px", height: "30px", cursor: "pointer", color: T.textSoft, fontSize: "13px", display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
            </div>
          </div>

          <div style={{ display: "flex", borderBottom: `1px solid ${T.borderLight}` }}>
            {[["summary", "Résumé"], ["transcript", "Transcription"], ["ai", "Analyse IA"]].map(([key, label]) => (
              <button className="calls-modal-tab" key={key} type="button" onClick={() => setTab(key)} style={{ padding: "10px 16px", fontSize: "13px", fontWeight: tab === key ? 700 : 500, color: tab === key ? T.tealDark : T.textSoft, background: "transparent", border: "none", borderBottom: tab === key ? `2px solid ${T.teal}` : "2px solid transparent", cursor: "pointer", marginBottom: "-1px", transition: "all 0.15s" }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px 22px" }}>
          {actionMessage ? <div style={{ marginBottom: 12, borderRadius: 12, border: `1px solid ${T.tealBorder}`, background: T.tealLight, color: T.tealDark, padding: "10px 12px", fontSize: 12, fontWeight: 700 }}>{actionMessage}</div> : null}

          {tab === "summary" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
                {[
                  { label: "Heure", value: call.time },
                  { label: "Durée", value: call.durationFmt },
                  { label: "Intent", value: <span style={{ fontSize: "11px", fontWeight: 700, color: call.intentUi.color, background: call.intentUi.bg, borderRadius: "5px", padding: "2px 8px" }}>{call.intentUi.label}</span> },
                ].map((row, index) => (
                  <div key={`${row.label}-${index}`} style={{ background: T.bg, borderRadius: "10px", padding: "11px 13px", border: `1px solid ${T.borderLight}` }}>
                    <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "5px" }}>{row.label}</div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: T.textMid }}>{row.value}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "12px" }}>
                <div style={{ background: T.bg, borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "6px" }}>Résumé</div>
                  <div style={{ fontSize: "13px", color: T.textMid, lineHeight: 1.55 }}>{call.summary}</div>
                </div>

                <div style={{ background: "#f8fafc", borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "8px" }}>Action recommandée</div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: T.text, marginBottom: "4px" }}>{primaryActionLabel}</div>
                  <div style={{ fontSize: "11px", lineHeight: 1.5, color: T.textSoft }}>
                    {call.status === "missed" || call.status === "callback"
                      ? "Prioriser un rappel manuel pour ne pas perdre le patient."
                      : call.rdv
                        ? "Le rendez-vous détecté peut être revu ou confirmé dans l'agenda."
                        : "Utilisez l'action métier pour ouvrir la bonne suite côté client."}
                  </div>
                </div>
              </div>

              {call.rdv ? (
                <div style={{ background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "12px", padding: "13px 15px", display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "22px" }}>📅</span>
                  <div>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: T.tealDark, marginBottom: "2px" }}>RDV détecté / créé</div>
                    <div style={{ fontSize: "12px", color: T.textSoft }}>{call.rdv.type} · {call.rdv.date} à {call.rdv.time}</div>
                  </div>
                </div>
              ) : null}

              {call.status === "missed" && !call.aiHandled ? (
                <div style={{ background: T.redLight, border: `1px solid ${T.redBorder}`, borderRadius: "12px", padding: "13px 15px" }}>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: T.red, marginBottom: "3px" }}>⚠ Appel manqué non traité par l'IA</div>
                  <div style={{ fontSize: "11px", color: "#ef9999", lineHeight: 1.5 }}>Ce patient attend un rappel manuel.</div>
                </div>
              ) : null}

              {call.aiScore ? (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                  {[
                    { label: "Confiance IA", value: `${call.aiScore.confidence}%`, accent: call.aiScore.confidence >= 90 ? T.tealDark : call.aiScore.confidence >= 75 ? T.orange : T.red },
                    { label: "Sentiment", value: call.aiScore.sentiment, accent: call.aiScore.sentiment === "positif" ? T.tealDark : call.aiScore.sentiment === "négatif" ? T.red : T.textSoft },
                    { label: "Résolution", value: call.aiScore.resolved ? "Résolu" : "Escalade", accent: call.aiScore.resolved ? T.tealDark : T.red },
                  ].map((item) => (
                    <div key={item.label} style={{ background: "#fff", border: `1px solid ${T.borderLight}`, borderRadius: 12, padding: "12px 13px" }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{item.label}</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: item.accent }}>{item.value}</div>
                    </div>
                  ))}
                </div>
              ) : null}

              <div style={{ display: "flex", gap: "8px", marginTop: "4px", flexWrap: "wrap" }}>
                {(call.status === "missed" || call.status === "callback") ? (
                  <button className="calls-primary-btn" type="button" onClick={onRecall} style={{ flex: 2, padding: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: "10px", color: "#fff", fontSize: "13px", fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 14px ${T.teal}40` }}>
                    📞 Rappeler maintenant
                  </button>
                ) : (
                  <button className="calls-primary-btn" type="button" onClick={onContextAction} style={{ flex: 2, padding: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: "10px", color: "#fff", fontSize: "13px", fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 14px ${T.teal}40` }}>
                    📅 {primaryActionLabel}
                  </button>
                )}
                <button className="calls-secondary-btn" type="button" onClick={onCopySummary} style={{ flex: 1, padding: "11px", background: T.bg, border: `1px solid ${T.border}`, borderRadius: "10px", color: T.textSoft, fontSize: "13px", fontWeight: 600, cursor: "pointer" }}>
                  Copier résumé
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                <button className="calls-secondary-btn" type="button" onClick={onMarkCallback} disabled={followupLoading} style={{ padding: "10px 11px", background: T.orangeLight, border: `1px solid ${T.orangeBorder}`, borderRadius: "10px", color: T.orange, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  À rappeler
                </button>
                <button className="calls-secondary-btn" type="button" onClick={onMarkProcessed} disabled={followupLoading} style={{ padding: "10px 11px", background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "10px", color: T.tealDark, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  Marquer traité
                </button>
                <button className="calls-secondary-btn" type="button" onClick={onCopyId} style={{ padding: "10px 11px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: "10px", color: T.textSoft, fontSize: "12px", fontWeight: 700, cursor: "pointer" }}>
                  Copier ID
                </button>
              </div>

              <div style={{ background: T.bg, borderRadius: "12px", padding: "13px 15px", border: `1px solid ${T.borderLight}` }}>
                <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "6px" }}>Suivi métier</div>
                <textarea
                  value={followupNotes}
                  onChange={(e) => setFollowupNotes(e.target.value)}
                  placeholder="Ajoutez une note interne."
                  style={{ width: "100%", minHeight: 86, resize: "vertical", border: `1px solid ${T.border}`, borderRadius: 10, padding: 10, fontSize: 12, color: T.textMid, background: "#fff", fontFamily: "inherit", outline: "none", boxSizing: "border-box" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 10 }}>
                  <button className="calls-secondary-btn" type="button" onClick={onSaveNotes} disabled={followupLoading} style={{ flex: 1, padding: "10px 12px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: 10, color: T.textSoft, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Enregistrer la note
                  </button>
                  <button className="calls-secondary-btn" type="button" onClick={onCopyTranscript} style={{ flex: 1, padding: "10px 12px", background: "#fff", border: `1px solid ${T.border}`, borderRadius: 10, color: T.textSoft, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Copier transcription
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          {tab === "transcript" ? <TranscriptView lines={call.transcript} /> : null}
          {tab === "ai" ? <AIScoreCard score={call.aiScore} /> : null}
        </div>
      </div>
    </div>
  );
}

export default function AppCalls() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState(7);
  const [statusFilter, setStatusFilter] = useState("all");
  const [intentFilter, setIntentFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("week");
  const [payload, setPayload] = useState({ calls: [], total: 0, date: "" });
  const [selectedCallId, setSelectedCallId] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [callDetail, setCallDetail] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [followupNotes, setFollowupNotes] = useState("");
  const [followupLoading, setFollowupLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .tenantGetCalls(`?limit=50&days=${days}`)
      .then((data) => {
        if (!cancelled) setPayload(data || { calls: [], total: 0, date: "" });
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Impossible de charger les appels.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  useEffect(() => {
    if (!selectedCallId) {
      setCallDetail(null);
      setDetailError("");
      setFollowupNotes("");
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError("");
    api
      .tenantGetCallDetail(selectedCallId)
      .then((data) => {
        if (!cancelled) {
          setCallDetail(data || null);
          setFollowupNotes(data?.followup_notes || "");
        }
      })
      .catch((e) => {
        if (!cancelled) setDetailError(e?.message || "Impossible de charger le détail de l'appel.");
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCallId]);

  useEffect(() => {
    if (!actionMessage) return undefined;
    const timeout = window.setTimeout(() => setActionMessage(""), 2200);
    return () => window.clearTimeout(timeout);
  }, [actionMessage]);

  useEffect(() => {
    setDays(tab === "today" ? 1 : tab === "week" ? 7 : 30);
  }, [tab]);

  const calls = payload?.calls || [];
  const normalizedCalls = useMemo(() => calls.map(normalizeSummaryCall), [calls]);
  const filteredCalls = useMemo(() => {
    return normalizedCalls.filter((call) => {
      const matchesSearch = !search.trim() || [call.name, call.phone, call.summary].join(" ").toLowerCase().includes(search.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || call.status === statusFilter;
      const matchesIntent = intentFilter === "all" || call.intent === intentFilter;
      return matchesSearch && matchesStatus && matchesIntent;
    });
  }, [intentFilter, normalizedCalls, search, statusFilter]);
  const groups = useMemo(() => {
    return [
      { label: "Matin", range: "07h – 12h", calls: filteredCalls.filter((call) => call.hour >= 7 && call.hour < 12) },
      { label: "Après-midi", range: "12h – 18h", calls: filteredCalls.filter((call) => call.hour >= 12 && call.hour < 18) },
      { label: "Soir", range: "18h – 07h", calls: filteredCalls.filter((call) => call.hour < 7 || call.hour >= 18) },
    ].filter((group) => group.calls.length > 0);
  }, [filteredCalls]);
  const sparkSeries = useMemo(() => buildSparkSeries(normalizedCalls), [normalizedCalls]);
  const stats = useMemo(() => {
    const totalAI = normalizedCalls.filter((call) => call.aiHandled).length;
    const totalMissed = normalizedCalls.filter((call) => (call.status === "missed" || call.status === "callback") && !call.recalled).length;
    const totalRdv = normalizedCalls.filter((call) => call.rdv).length;
    const resolved = normalizedCalls.filter((call) => call.aiScore?.resolved).length;
    const resolvedRate = normalizedCalls.length ? Math.round((resolved / normalizedCalls.length) * 100) : 0;
    const durationAverage = normalizedCalls.length
      ? Math.round(normalizedCalls.reduce((sum, call) => sum + parseDurationMinutes(call.durationFmt), 0) / normalizedCalls.length)
      : 0;
    return { totalAI, totalMissed, totalRdv, resolvedRate, durationAverage };
  }, [normalizedCalls]);
  const kpis = useMemo(() => ([
    { label: "Appels traités", value: String(normalizedCalls.length), delta: `${stats.totalAI} IA`, up: true, color: T.teal, spark: sparkSeries.calls },
    { label: "RDV planifiés", value: String(stats.totalRdv), delta: `${normalizedCalls.filter((call) => call.intent === "rdv").length} RDV`, up: true, color: T.blue, spark: sparkSeries.rdv },
    { label: "Taux de résolution", value: `${stats.resolvedRate}%`, delta: stats.totalMissed ? `${stats.totalMissed} à rappeler` : "0 rappel", up: stats.resolvedRate >= 70, color: T.purple, spark: sparkSeries.rate },
    { label: "Durée moy.", value: stats.durationAverage ? `${stats.durationAverage}m` : "—", delta: `${normalizedCalls.filter((call) => call.status === "callback").length} rappels`, up: false, color: T.orange, spark: sparkSeries.duration },
  ]), [normalizedCalls, sparkSeries.calls, sparkSeries.duration, sparkSeries.rate, sparkSeries.rdv, stats.durationAverage, stats.resolvedRate, stats.totalAI, stats.totalMissed, stats.totalRdv]);
  const selectedCallSummary = useMemo(
    () => normalizedCalls.find((call) => call.id === selectedCallId) || null,
    [normalizedCalls, selectedCallId],
  );
  const detailModel = useMemo(
    () => normalizeDetailCall(callDetail, selectedCallSummary),
    [callDetail, selectedCallSummary],
  );
  const upcomingItems = useMemo(() => {
    const target = normalizedCalls.filter((call) => call.status === "callback" || call.status === "missed");
    return (target.length ? target : normalizedCalls).slice(0, 4);
  }, [normalizedCalls]);
  const urgentItems = useMemo(
    () => normalizedCalls.filter((call) => call.intent === "urgent" && !call.recalled).slice(0, 3),
    [normalizedCalls],
  );
  const periodLabel = tab === "today" ? "des dernières heures" : tab === "week" ? "de la semaine en cours" : "de la période complète";

  async function persistFollowup(callId, nextState, notesOverride = "", messageOverride = "") {
    if (!callId) return;
    setFollowupLoading(true);
    try {
      const data = await api.tenantUpdateCallFollowup(callId, {
        followup_state: nextState,
        notes: notesOverride || "",
      });
      setCallDetail((prev) =>
        prev && (prev.call_id || selectedCallId) === callId
          ? {
              ...prev,
              followup_state: data?.followup_state || nextState,
              followup_notes: data?.followup_notes || "",
              followup_updated_at: data?.followup_updated_at || "",
            }
          : prev,
      );
      setPayload((prev) => ({
        ...(prev || { calls: [] }),
        calls: (prev?.calls || []).map((call) =>
          (call.call_id || call.id) === callId
            ? {
                ...call,
                followup_state: data?.followup_state || nextState,
                followup_notes: data?.followup_notes || "",
              }
            : call,
        ),
      }));
      if ((callDetail?.call_id || selectedCallId) === callId) {
        setFollowupNotes(data?.followup_notes || "");
      }
      setActionMessage(
        messageOverride ||
          (nextState === "callback"
            ? "Appel marqué à rappeler."
            : nextState === "processed"
              ? "Appel marqué comme traité."
              : "Suivi réinitialisé."),
      );
    } catch (e) {
      setActionMessage(e?.message || "Impossible d'enregistrer le suivi.");
    } finally {
      setFollowupLoading(false);
    }
  }

  async function saveFollowupState(nextState, notesOverride = followupNotes) {
    if (!selectedCallId) return;
    await persistFollowup(selectedCallId, nextState, notesOverride);
  }

  async function runContextualAction(detail) {
    const action = detail?.contextual_action?.kind || "open_detail";
    const callId = detail?.call_id || detail?.id || selectedCallId;
    if (action === "followup_callback") {
      await persistFollowup(callId, "callback", detail?.followup_notes || "", "Appel ajouté à la file de rappel.");
      return;
    }
    if (action === "mark_processed") {
      await persistFollowup(callId, "processed", detail?.followup_notes || "", "Appel marqué comme traité.");
      return;
    }
    if (action === "open_agenda") {
      navigate("/app/agenda");
      return;
    }
    if (action === "open_faq") {
      navigate("/app/faq");
      return;
    }
    setActionMessage("Les détails de l'appel sont déjà affichés.");
  }

  function clearFilters() {
    setStatusFilter("all");
    setIntentFilter("all");
    setSearch("");
  }

  function handleRecall(call) {
    const phone = getDialablePhone(call?.dialablePhone || call?.phone || call?.raw?.customer_number);
    if (phone) {
      window.location.href = `tel:${phone}`;
      return;
    }
    setActionMessage("Numéro indisponible pour rappel.");
  }

  const sidebarItems = [
    { icon: "⊞", label: "Dashboard", to: "/app" },
    { icon: "☎", label: "Appels", to: "/app/appels", active: true, badge: String(filteredCalls.length) },
    { icon: "📅", label: "Rendez-vous", to: "/app/agenda" },
    { icon: "👤", label: "Patients", to: "/app/profil" },
    { icon: "📊", label: "Statistiques", to: "/app/status" },
    { icon: "⚙", label: "Paramètres", to: "/app/settings" },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", height: "100vh", fontFamily: "'Inter', system-ui, sans-serif", background: T.bg, color: T.text, overflow: "hidden" }}>
      <style>{CSS}</style>
      <div className="calls-model-layout" style={{ display: "grid", gridTemplateColumns: "236px minmax(0, 1fr)", width: "100%", height: "100%" }}>
        <div style={{ background: T.card, borderRight: `1px solid ${T.border}`, display: "flex", flexDirection: "column", minHeight: "100%", overflow: "hidden" }}>
          <div style={{ padding: "18px 16px 14px", borderBottom: `1px solid ${T.borderLight}`, display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ width: "36px", height: "36px", borderRadius: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "18px" }}>🎙</div>
            <div>
              <div style={{ fontSize: "15px", fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>UWI</div>
              <div style={{ fontSize: "10px", color: T.textFaint }}>Agent vocal IA</div>
            </div>
          </div>

          <div style={{ padding: "10px 10px 0" }}>
            {sidebarItems.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => navigate(item.to)}
                style={{ width: "100%", display: "flex", alignItems: "center", gap: "9px", padding: "8px 10px", borderRadius: "9px", marginBottom: "1px", background: item.active ? T.tealLight : "transparent", color: item.active ? T.tealDark : T.textSoft, fontSize: "13px", fontWeight: item.active ? 700 : 400, border: "none", cursor: item.active ? "default" : "pointer", textAlign: "left" }}
              >
                <span style={{ fontSize: "14px", opacity: item.active ? 1 : 0.5 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge ? <span style={{ fontSize: "10px", fontWeight: 700, background: `${T.teal}20`, color: T.tealDark, borderRadius: "10px", padding: "1px 7px" }}>{item.badge}</span> : null}
              </button>
            ))}
          </div>

          <div style={{ height: "1px", background: T.borderLight, margin: "10px 12px" }} />

          <div style={{ padding: "0 10px" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "7px", paddingLeft: "2px" }}>Statut</div>
            {[["all", "Tous", "#94a3b8", normalizedCalls.length], ...Object.entries(MODEL_STATUS).map(([key, value]) => [key, value.label, value.color, normalizedCalls.filter((call) => call.status === key).length])].map(([key, label, color, count]) => {
              const active = statusFilter === key;
              return (
                <button type="button" key={key} onClick={() => setStatusFilter(key)} style={{ width: "100%", display: "flex", alignItems: "center", gap: "8px", padding: "7px 9px", borderRadius: "8px", marginBottom: "2px", cursor: "pointer", background: active ? T.tealLight : "transparent", border: active ? `1px solid ${T.tealBorder}` : "1px solid transparent", textAlign: "left" }}>
                  <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: "12px", fontWeight: active ? 700 : 400, color: active ? T.tealDark : T.textSoft, flex: 1 }}>{label}</span>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: active ? T.tealDark : T.textFaint, background: active ? `${T.teal}15` : "rgba(148,163,184,0.1)", borderRadius: "6px", padding: "1px 7px" }}>{count}</span>
                </button>
              );
            })}
          </div>

          <div style={{ height: "1px", background: T.borderLight, margin: "10px 12px" }} />

          <div style={{ padding: "0 10px" }}>
            <div style={{ fontSize: "10px", fontWeight: 700, color: T.textFaint, textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: "7px", paddingLeft: "2px" }}>Type d&apos;appel</div>
            {[["all", "Tous"], ...Object.entries(MODEL_INTENTS).map(([key, value]) => [key, value.label])].map(([key, label]) => {
              const active = intentFilter === key;
              return (
                <button type="button" key={key} onClick={() => setIntentFilter(key)} style={{ width: "100%", display: "flex", alignItems: "center", gap: "8px", padding: "6px 9px", borderRadius: "8px", marginBottom: "1px", cursor: "pointer", background: active ? T.tealLight : "transparent", border: "none", textAlign: "left" }}>
                  <span style={{ fontSize: "12px", fontWeight: active ? 700 : 400, color: active ? T.tealDark : T.textSoft }}>{label}</span>
                </button>
              );
            })}
          </div>

          <div style={{ margin: "auto 10px 12px", background: T.tealLight, border: `1px solid ${T.tealBorder}`, borderRadius: "11px", padding: "11px 13px", marginTop: "auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "7px", marginBottom: "5px" }}>
              <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: T.teal, boxShadow: `0 0 0 3px ${T.teal}30` }} />
              <span style={{ fontSize: "11px", fontWeight: 700, color: T.tealDark }}>Agent UWI actif</span>
            </div>
            <div style={{ fontSize: "11px", color: T.textSoft, lineHeight: 1.5 }}>
              <b style={{ color: T.tealDark }}>{stats.totalAI} appels</b> traités par IA sur la période affichée
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, background: T.bg }}>
          <div style={{ background: T.card, borderBottom: `1px solid ${T.border}`, padding: "15px 28px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
            <div>
              <h1 style={{ margin: 0, fontSize: "21px", fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>Journal d&apos;appels</h1>
              <p style={{ margin: 0, fontSize: "13px", color: T.textFaint, marginTop: "1px" }}>Activité des {days === 1 ? "dernières 24h" : `${days} derniers jours`}</p>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "7px", background: T.bg, border: `1px solid ${T.border}`, borderRadius: "9px", padding: "8px 13px" }}>
                <span style={{ fontSize: "13px", color: T.textFaint }}>🔍</span>
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Rechercher…" style={{ border: "none", background: "transparent", fontSize: "13px", color: T.textMid, outline: "none", width: "150px" }} />
                {search ? <button type="button" onClick={() => setSearch("")} style={{ background: "none", border: "none", cursor: "pointer", color: T.textFaint, fontSize: "11px" }}>✕</button> : null}
              </div>
              <button type="button" onClick={() => navigate("/app/agenda")} style={{ display: "flex", alignItems: "center", gap: "7px", padding: "10px 18px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, border: "none", borderRadius: "11px", color: "#fff", fontSize: "13px", fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 14px ${T.teal}40` }}>
                <span style={{ fontSize: "16px", lineHeight: 1 }}>+</span> Planifier un appel
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px" }}>
            {error ? <div style={{ ...ERROR_BOX, marginBottom: 14 }}>{error}</div> : null}
            {actionMessage && !selectedCallId ? <div style={{ marginBottom: 14, borderRadius: 12, border: `1px solid ${T.tealBorder}`, background: T.tealLight, color: T.tealDark, padding: "10px 12px", fontSize: 12, fontWeight: 700 }}>{actionMessage}</div> : null}

            <div className="calls-kpis-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 20 }}>
              {kpis.map((kpi) => (
                <div key={kpi.label} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "16px", padding: "18px 20px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: kpi.color, boxShadow: `0 0 0 4px ${kpi.color}18`, flexShrink: 0 }} />
                      <div style={{ fontSize: "12px", color: T.textFaint }}>{kpi.label}</div>
                    </div>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: kpi.up ? T.tealDark : T.orange, background: kpi.up ? T.tealLight : T.orangeLight, padding: "2px 8px", borderRadius: "20px" }}>
                      {kpi.up ? "↑ " : "↓ "}
                      {kpi.delta}
                    </span>
                  </div>
                  <div style={{ fontSize: "28px", fontWeight: 800, color: T.text, lineHeight: 1, marginBottom: "10px" }}>{kpi.value}</div>
                  <Sparkline data={kpi.spark} color={kpi.color} />
                </div>
              ))}
            </div>

            <div className="calls-main-columns" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 284px", gap: 18, alignItems: "start" }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "16px", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <div style={{ padding: "16px 18px 0", borderBottom: `1px solid ${T.borderLight}` }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
                      <div>
                        <div style={{ fontSize: "16px", fontWeight: 800, color: T.text }}>Appels récents</div>
                        <div style={{ fontSize: "12px", color: T.textFaint, marginTop: "1px" }}>Activité {periodLabel}</div>
                      </div>
                      <span style={{ fontSize: "13px", fontWeight: 600, color: T.tealDark, cursor: "default" }}>Voir tout ↗</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center" }}>
                      {[["today", "Aujourd&apos;hui"], ["week", "Cette semaine"], ["all", "Tous"]].map(([value, label]) => (
                        <button key={value} type="button" onClick={() => setTab(value)} style={{ padding: "8px 14px", fontSize: "13px", fontWeight: tab === value ? 700 : 500, color: tab === value ? T.tealDark : T.textSoft, background: "transparent", border: "none", borderBottom: tab === value ? `2px solid ${T.teal}` : "2px solid transparent", cursor: "pointer", marginBottom: "-1px" }}>
                          <span dangerouslySetInnerHTML={{ __html: label }} />
                        </button>
                      ))}
                      {(statusFilter !== "all" || intentFilter !== "all" || search) ? (
                        <button type="button" onClick={clearFilters} style={{ marginLeft: "auto", fontSize: "11px", color: T.red, background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>
                          Effacer filtres ✕
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {loading ? (
                    <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
                      {[1, 2, 3, 4, 5].map((item) => <Skeleton key={item} height={88} />)}
                    </div>
                  ) : groups.length === 0 ? (
                    <div style={{ padding: "40px 20px", textAlign: "center", color: T.textFaint }}>
                      <div style={{ fontSize: "32px", marginBottom: "8px" }}>📭</div>
                      <div style={{ fontSize: "14px", fontWeight: 600 }}>Aucun appel trouvé</div>
                    </div>
                  ) : groups.map((group, groupIndex) => (
                    <div key={group.label}>
                      <div style={{ padding: "9px 18px 5px", display: "flex", alignItems: "center", gap: "10px", background: "#fafbfc", borderTop: groupIndex > 0 ? `1px solid ${T.borderLight}` : "none" }}>
                        <span style={{ fontSize: "11px", fontWeight: 700, color: T.textSoft, textTransform: "uppercase", letterSpacing: "0.08em" }}>{group.label}</span>
                        <span style={{ fontSize: "10px", color: T.textFaint }}>{group.range}</span>
                        <span style={{ marginLeft: "auto", fontSize: "10px", fontWeight: 600, color: T.textFaint, background: T.borderLight, borderRadius: "10px", padding: "1px 8px" }}>{group.calls.length} appel{group.calls.length > 1 ? "s" : ""}</span>
                      </div>
                      {group.calls.map((call, index) => (
                        <CallRowModel key={call.id} call={call} onOpen={(item) => setSelectedCallId(item.id)} onRecall={handleRecall} isLast={groupIndex === groups.length - 1 && index === group.calls.length - 1} />
                      ))}
                    </div>
                  ))}

                  {stats.totalMissed > 0 ? (
                    <div style={{ padding: "11px 18px", background: T.orangeLight, borderTop: `1px solid ${T.orangeBorder}`, display: "flex", alignItems: "center", gap: "10px" }}>
                      <span>⚠️</span>
                      <span style={{ fontSize: "12px", color: T.orange, fontWeight: 600 }}>{stats.totalMissed} appel{stats.totalMissed > 1 ? "s" : ""} à rappeler</span>
                      <button type="button" onClick={() => setStatusFilter("callback")} style={{ marginLeft: "auto", fontSize: "12px", fontWeight: 700, color: T.orange, background: "none", border: `1px solid ${T.orangeBorder}`, borderRadius: "8px", padding: "4px 12px", cursor: "pointer" }}>
                        Voir →
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>

              <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: "16px", padding: "18px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                  <div style={{ fontSize: "15px", fontWeight: 800, color: T.text, marginBottom: "2px" }}>Agenda</div>
                  <div style={{ fontSize: "12px", color: T.textFaint, marginBottom: "14px" }}>Prochains appels à traiter</div>
                  {upcomingItems.map((item) => {
                    const [hh, mm] = String(item.time || "00:00").split(":");
                    const dialablePhone = getDialablePhone(item?.dialablePhone || item?.phone || item?.raw?.customer_number);
                    return (
                      <div key={item.id} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px 0", borderBottom: `1px solid ${T.borderLight}` }}>
                        <div style={{ width: "44px", height: "44px", borderRadius: "11px", background: `linear-gradient(135deg,${T.teal},${T.tealDark})`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          <div style={{ fontSize: "13px", fontWeight: 800, color: "#fff", lineHeight: 1 }}>{hh || "—"}</div>
                          <div style={{ fontSize: "10px", fontWeight: 700, color: "rgba(255,255,255,0.8)", lineHeight: 1 }}>{mm || "—"}</div>
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: "13px", fontWeight: 700, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: "3px" }}>
                            <span style={{ fontSize: "10px", fontWeight: 700, color: item.intentUi.color, background: item.intentUi.bg, borderRadius: 999, padding: "2px 8px" }}>{item.intentUi.label}</span>
                            <span style={{ fontSize: "10px", color: T.textFaint }}>{item.phone}</span>
                          </div>
                          <span role="button" tabIndex={0} onClick={() => setSelectedCallId(item.id)} onKeyDown={(e) => { if (e.key === "Enter") setSelectedCallId(item.id); }} style={{ fontSize: "10px", fontWeight: 600, color: T.tealDark, cursor: "pointer" }}>Détails ↗</span>
                        </div>
                        {dialablePhone ? (
                          <a href={`tel:${dialablePhone}`} onClick={(e) => e.stopPropagation()} style={{ width: 34, height: 34, borderRadius: 10, background: item.statusUi.bg, border: `1px solid ${item.statusUi.border}`, color: item.statusUi.color, display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", fontSize: 15, flexShrink: 0 }}>
                            {item.status === "missed" ? "📵" : item.status === "planned" ? "📞" : "📲"}
                          </a>
                        ) : null}
                      </div>
                    );
                  })}
                  <button type="button" onClick={() => navigate("/app/agenda")} style={{ width: "100%", marginTop: "12px", padding: "9px", background: "transparent", border: `1.5px dashed ${T.border}`, borderRadius: "10px", color: T.textSoft, fontSize: "12px", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "5px" }}>
                    <span>+</span> Ouvrir l&apos;agenda
                  </button>
                </div>

                <div style={{ background: T.purpleLight, border: `1px solid ${T.purpleBorder}`, borderRadius: "16px", padding: "16px 18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <span style={{ fontSize: "17px" }}>🤖</span>
                    <div style={{ fontSize: "14px", fontWeight: 800, color: T.purple }}>Résumé UWI du jour</div>
                  </div>
                  {[
                    { icon: "📞", label: "Appels traités", value: `${normalizedCalls.length}` },
                    { icon: "📅", label: "RDV détectés", value: `${stats.totalRdv}` },
                    { icon: "✅", label: "Taux de résolution", value: `${stats.resolvedRate}%` },
                    { icon: "⏱", label: "Durée moy.", value: stats.durationAverage ? `${stats.durationAverage} min` : "—" },
                  ].map((row, index) => (
                    <div key={row.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: index < 3 ? `1px solid ${T.purpleBorder}` : "none" }}>
                      <span style={{ fontSize: "12px", color: T.purple }}>{row.icon} {row.label}</span>
                      <span style={{ fontSize: "13px", fontWeight: 700, color: T.purple }}>{row.value}</span>
                    </div>
                  ))}
                  <div style={{ marginTop: 12, fontSize: 11, lineHeight: 1.55, color: T.purple }}>
                    UWI absorbe la majorité des demandes simples et remonte surtout les urgences, rappels et cas non résolus.
                  </div>
                </div>

                {urgentItems.length > 0 ? (
                  <div style={{ background: T.redLight, border: `1px solid ${T.redBorder}`, borderRadius: "16px", padding: "15px 17px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: "10px" }}>
                      <div style={{ fontSize: "13px", fontWeight: 800, color: T.red }}>⚠ Rappels urgents</div>
                      <span style={{ fontSize: 10, fontWeight: 800, color: T.red, background: "#fff", border: `1px solid ${T.redBorder}`, borderRadius: 999, padding: "3px 8px" }}>
                        {urgentItems.length} priorité{urgentItems.length > 1 ? "s" : ""}
                      </span>
                    </div>
                    {urgentItems.map((call, index) => (
                      <div key={call.id} style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 0", borderBottom: index < urgentItems.length - 1 ? "1px solid #FCA5A5" : "none" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "12px", fontWeight: 700, color: T.red }}>{call.name}</div>
                          <div style={{ fontSize: "11px", color: "#ef9999" }}>{call.phone}</div>
                        </div>
                        <button type="button" onClick={() => handleRecall(call)} style={{ fontSize: "11px", fontWeight: 700, color: "#fff", background: T.red, border: "none", borderRadius: "7px", padding: "4px 10px", cursor: "pointer" }}>
                          Rappeler
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      {selectedCallId ? (
        detailLoading ? (
          <div style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(15,23,42,0.3)", backdropFilter: "blur(5px)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ background: "#fff", borderRadius: 20, width: 540, maxWidth: "94vw", padding: 22 }}>
              <Skeleton height={80} />
              <div style={{ height: 12 }} />
              <Skeleton height={180} />
            </div>
          </div>
        ) : detailError ? (
          <div style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(15,23,42,0.3)", backdropFilter: "blur(5px)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setSelectedCallId("")}>
            <div style={{ background: "#fff", borderRadius: 20, width: 540, maxWidth: "94vw", padding: 22 }} onClick={(e) => e.stopPropagation()}>
              <div style={ERROR_BOX}>Erreur: {detailError}</div>
            </div>
          </div>
        ) : (
          <CallDetailModal
            call={detailModel}
            onClose={() => setSelectedCallId("")}
            onRecall={() => handleRecall(detailModel)}
            onContextAction={() => runContextualAction(callDetail || selectedCallSummary?.raw)}
            onMarkCallback={() => saveFollowupState("callback")}
            onMarkProcessed={() => saveFollowupState("processed")}
            onCopyTranscript={async () => {
              const ok = await copyToClipboard(callDetail?.transcript || "");
              setActionMessage(ok ? "Transcription copiée." : "Impossible de copier la transcription.");
            }}
            onCopySummary={async () => {
              const ok = await copyToClipboard(callDetail?.summary || selectedCallSummary?.summary || "");
              setActionMessage(ok ? "Résumé copié." : "Impossible de copier le résumé.");
            }}
            onCopyId={async () => {
              const ok = await copyToClipboard(selectedCallId);
              setActionMessage(ok ? "ID d'appel copié." : "Impossible de copier l'identifiant.");
            }}
            followupNotes={followupNotes}
            setFollowupNotes={setFollowupNotes}
            onSaveNotes={() => saveFollowupState(callDetail?.followup_state || "new", followupNotes)}
            followupLoading={followupLoading}
            actionMessage={actionMessage}
          />
        )
      ) : null}
    </div>
  );
}

const CSS = `
  @keyframes uwi-calls-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @keyframes calls-modal-enter {
    from {
      opacity: 0;
      transform: translateY(10px) scale(.985);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .calls-row {
    transition: background .16s ease, transform .16s ease, box-shadow .16s ease;
  }

  .calls-row:hover {
    background: #fafcfd;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(15,23,42,.05);
  }

  .calls-modal-panel {
    animation: calls-modal-enter .18s ease-out;
    transform-origin: center top;
  }

  .calls-modal-tab:hover {
    color: #0AAF7A !important;
    background: rgba(13, 201, 145, 0.04) !important;
  }

  .calls-primary-btn,
  .calls-secondary-btn {
    transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
  }

  .calls-primary-btn:hover,
  .calls-secondary-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(15,23,42,.08);
    filter: saturate(1.03);
  }

  @media (max-width: 1100px) {
    .calls-kpis-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
  }

  @media (max-width: 760px) {
    .calls-kpis-grid {
      grid-template-columns: 1fr !important;
    }

    .calls-row {
      flex-direction: column;
    }

    .calls-model-layout,
    .calls-main-columns {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 720px) {
    .calls-modal-panel {
      width: calc(100vw - 20px) !important;
      max-height: calc(100vh - 20px) !important;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .calls-row,
    .calls-modal-panel,
    .calls-modal-tab,
    .calls-primary-btn,
    .calls-secondary-btn {
      animation: none !important;
      transition: none !important;
    }
  }
`;
