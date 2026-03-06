import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const TEAL = "#00d4a0";
const TEALX = "#00b389";
const NAVY = "#0d1b2e";

const STATUS_CFG = {
  TRANSFERRED: { color: "#dc2626", light: "#fef2f2", border: "#fecaca", icon: "⚠", label: "URGENCE" },
  ABANDONED: { color: "#d97706", light: "#fffbeb", border: "#fde68a", icon: "◎", label: "À VALIDER" },
  CONFIRMED: { color: "#00b389", light: "#f0fdf9", border: "#99f0da", icon: "✓", label: "CONFIRMÉ" },
  FAQ: { color: "#94a3b8", light: "#f8fafc", border: "#e2e8f0", icon: "→", label: "TRANSMIS" },
};

const HOURS = ["08h", "09h", "10h", "11h", "12h", "13h", "14h", "15h", "16h", "17h"];

function Pulse({ color = TEAL, size = 8 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: color,
          opacity: 0.35,
          animation: "ping 1.8s ease-out infinite",
        }}
      />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: color, display: "block" }} />
    </span>
  );
}

function AnimatedNumber({ target, suffix = "" }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let current = 0;
    const step = Math.max(1, Math.ceil((target || 0) / 40));
    const timer = window.setInterval(() => {
      current = Math.min(current + step, target || 0);
      setVal(current);
      if (current >= (target || 0)) window.clearInterval(timer);
    }, 16);
    return () => window.clearInterval(timer);
  }, [target]);
  return (
    <>
      {val}
      {suffix}
    </>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <style>{CSS}</style>
      <div className="dash-skel" style={{ height: 96 }} />
      <div style={{ display: "flex", gap: 14 }}>
        <div className="dash-skel" style={{ height: 140, flex: 1 }} />
        <div className="dash-skel" style={{ height: 140, width: 280, flexShrink: 0 }} />
      </div>
      <div style={{ display: "flex", gap: 14, minHeight: 420 }}>
        <div className="dash-skel" style={{ flex: 1 }} />
        <div className="dash-skel" style={{ width: 320, flexShrink: 0 }} />
      </div>
    </div>
  );
}

export default function AppDashboard() {
  const navigate = useNavigate();
  const [now, setNow] = useState(new Date());
  const [selected, setSelected] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [me, setMe] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [callsData, setCallsData] = useState({ calls: [], total: 0, date: "" });
  const [agendaData, setAgendaData] = useState({ slots: [], total: 0, done: 0, remaining: 0, date: "" });

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.tenantKpis(1),
      api.tenantGetCalls("?limit=10&days=1"),
      api.tenantGetAgenda(),
      api.tenantMe(),
    ])
      .then(([kpisRes, callsRes, agendaRes, meRes]) => {
        if (!alive) return;
        setKpis(kpisRes || null);
        setCallsData(callsRes || { calls: [], total: 0, date: "" });
        setAgendaData(agendaRes || { slots: [], total: 0, done: 0, remaining: 0, date: "" });
        setMe(meRes || null);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Impossible de charger le dashboard.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const calls = callsData?.calls || [];
  const urgences = calls.filter((call) => call.status === "TRANSFERRED");
  const actions = calls
    .filter((call) => call.status === "TRANSFERRED" || call.status === "ABANDONED")
    .slice(0, 3)
    .map((call) => ({
      id: call.id,
      patient: call.patient_name,
      resume: call.summary,
      action: call.status === "TRANSFERRED" ? "Rappeler patient" : "Traiter le dossier",
      color: call.status === "TRANSFERRED" ? "#dc2626" : "#d97706",
      bg: call.status === "TRANSFERRED" ? "#fef2f2" : "#fffbeb",
      border: call.status === "TRANSFERRED" ? "#fecaca" : "#fde68a",
    }));

  const agendaByHour = useMemo(() => {
    const indexed = new Map();
    for (const slot of agendaData?.slots || []) indexed.set(slot.hour, slot);
    return HOURS.map((hour) => ({ hour, ...(indexed.get(hour) || { patient: null }) }));
  }, [agendaData]);

  const pickupRate = kpis?.pickup_rate ?? 0;
  const rdvPris = kpis?.current?.bookings ?? 0;
  const minutesMonth = kpis?.minutes_month ?? 0;
  const assistantName = ((me?.assistant_name || "sophie").trim() || "sophie").replace(/^./, (s) => s.toUpperCase());
  const shortTenantName = me?.tenant_name || "uwi";
  const dateLabel = now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const hasUrgences = urgences.length > 0 && !dismissed;

  const go = (path) => () => navigate(path);

  if (loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <div style={{ ...S.page, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 320 }}>
        <style>{CSS}</style>
        <div style={{ ...S.card, maxWidth: 520, width: "100%" }}>
          <div style={S.cardTitle}>Chargement impossible</div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>{error}</div>
          <button type="button" style={{ ...S.ghost, marginTop: 14 }} onClick={() => window.location.reload()}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <style>{CSS}</style>

      {hasUrgences && (
        <div style={S.urgBar} className="urg-bar">
          <div style={S.urgBarLeft}>
            <div style={S.urgIcon}>⚠</div>
            <div>
              <div style={S.urgTitle}>
                {urgences.length} urgence{urgences.length > 1 ? "s" : ""} signalée{urgences.length > 1 ? "s" : ""}
              </div>
              <div style={S.urgItems}>
                {urgences.map((urgence) => (
                  <span key={urgence.id} style={S.urgItem}>
                    <strong>{urgence.patient_name}</strong> — {urgence.summary}
                    <span style={S.urgTime}>{urgence.time}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button type="button" style={S.urgCta} onClick={go("/app/appels")}>📞 Rappeler maintenant</button>
            <button type="button" style={S.urgDismiss} onClick={() => setDismissed(true)}>✕</button>
          </div>
        </div>
      )}

      <div style={S.level2}>
        <div style={S.hero}>
          <div style={S.heroGrid} />
          <div style={S.heroGlow} />
          <div style={{ position: "relative" }}>
            <div style={S.heroGreeting}>Bonjour, {shortTenantName} 👋</div>
            <div style={S.heroSub}>
              {dateLabel} · UWI a traité <strong style={{ color: TEAL }}>{callsData.total || 0} appels</strong> aujourd&apos;hui
            </div>
          </div>
          <div style={{ position: "relative", display: "flex", gap: 8 }}>
            {[
              { n: pickupRate, s: "%", label: "DÉCROCHÉ", color: TEAL },
              { n: rdvPris, s: "", label: "RDV PRIS", color: "#a78bfa" },
              { n: minutesMonth, s: "", label: "MIN / MOIS", color: "#60a5fa" },
            ].map((metric) => (
              <div key={metric.label} style={S.kpi} className="kpi-card">
                <div style={{ fontSize: 24, fontWeight: 800, color: metric.color, lineHeight: 1 }}>
                  <AnimatedNumber target={metric.n} suffix={metric.s} />
                </div>
                <div style={{ fontSize: 9, color: "rgba(255,255,255,0.5)", letterSpacing: 1.2, marginTop: 4, fontWeight: 700 }}>
                  {metric.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={S.actionsCol}>
          <div style={S.scanLabel}>À TRAITER</div>
          {actions.length ? actions.map((action) => (
            <div key={action.id} style={{ ...S.actionCard, background: action.bg, border: `1px solid ${action.border}` }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: NAVY }}>{action.patient}</div>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>{action.resume}</div>
              </div>
              <button type="button" style={{ ...S.actionCta, background: action.color }} onClick={go("/app/appels")}>
                {action.action} →
              </button>
            </div>
          )) : (
            <div style={{ ...S.card, padding: "14px 16px", boxShadow: "none" }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Aucune action urgente à traiter.</div>
            </div>
          )}
        </div>
      </div>

      <div style={S.level3}>
        <div style={{ ...S.card, flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={S.cardHead}>
            <div>
              <div style={S.cardTag}>AUJOURD&apos;HUI · {callsData.total || 0} APPELS</div>
              <div style={S.cardTitle}>Appels récents</div>
            </div>
            <button type="button" style={S.ghost} onClick={go("/app/appels")}>Historique →</button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5, overflowY: "auto" }}>
            {calls.length ? calls.map((call, index) => {
              const status = STATUS_CFG[call.status] || STATUS_CFG.FAQ;
              const open = selected === call.id;
              return (
                <div
                  key={call.id}
                  style={{
                    ...S.callRow,
                    background: open ? status.light : "#fff",
                    borderColor: open ? status.border : "#f1f5f9",
                    borderLeft: `3px solid ${status.color}`,
                    animationDelay: `${index * 60}ms`,
                  }}
                  className="call-row"
                  onClick={() => setSelected(open ? null : call.id)}
                >
                  <div style={{ width: 46, flexShrink: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", fontFamily: "'DM Mono', monospace" }}>{call.time}</div>
                    <div style={{ fontSize: 10, color: "#cbd5e1", marginTop: 1 }}>{call.duration}</div>
                  </div>
                  <Pulse color={status.color} size={7} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 8 }}>
                      {call.patient_name}
                      <span style={S.agentChip}>{call.agent_name || assistantName}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 3, lineHeight: 1.5 }}>{call.summary}</div>
                    {open && (
                      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }} className="expand-in">
                        <button type="button" style={{ ...S.pillBtn, background: status.color }} onClick={go("/app/appels")}>
                          {call.status === "ABANDONED" ? "✓ Traiter" : "📞 Ouvrir"}
                        </button>
                        <button type="button" style={S.ghost} onClick={go("/app/appels")}>Transcription</button>
                      </div>
                    )}
                  </div>
                  <span style={{ ...S.statusTag, background: status.light, color: status.color, border: `1px solid ${status.border}` }}>
                    {status.icon} {status.label}
                  </span>
                </div>
              );
            }) : (
              <div style={{ padding: "18px 4px", fontSize: 12, color: "#94a3b8" }}>Aucun appel aujourd&apos;hui.</div>
            )}
          </div>
        </div>

        <div style={{ ...S.card, width: 320, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={S.cardHead}>
            <div>
              <div style={S.cardTag}>{(agendaData.date || now.toISOString().slice(0, 10)).toUpperCase()}</div>
              <div style={S.cardTitle}>Agenda du jour</div>
            </div>
            <button type="button" style={S.ghost} onClick={go("/app/agenda")}>Ouvrir →</button>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600 }}>Progression</span>
              <span style={{ fontSize: 10, color: TEALX, fontWeight: 700 }}>{now.toTimeString().slice(0, 5)} · en cours</span>
            </div>
            <div style={{ height: 4, background: "#f1f5f9", borderRadius: 2, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${agendaData.total ? Math.max(10, Math.round((agendaData.done / Math.max(agendaData.total, 1)) * 100)) : 8}%`,
                  background: `linear-gradient(90deg, ${TEAL}, #60a5fa)`,
                  borderRadius: 2,
                }}
                className="bar-fill"
              />
            </div>
          </div>

          <div style={S.agSummary}>
            {[
              { n: agendaData.total || 0, l: "RDV", c: NAVY },
              { n: agendaData.done || 0, l: "Terminés", c: TEALX },
              { n: agendaData.remaining || 0, l: "Restants", c: "#3b82f6" },
            ].map((summary) => (
              <div key={summary.l} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: summary.c }}>{summary.n}</div>
                <div style={{ fontSize: 9, color: "#94a3b8", marginTop: 2, fontWeight: 600 }}>{summary.l}</div>
              </div>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            {agendaByHour.some((slot) => slot.patient) ? agendaByHour.map((slot, index) => {
              const empty = !slot.patient;
              const current = !!slot.current;
              const done = !!slot.done;
              return (
                <div key={slot.hour}>
                  {current && (
                    <div style={{ display: "flex", alignItems: "center", margin: "3px 0", position: "relative" }}>
                      <div style={{ width: 36, flexShrink: 0 }} />
                      <div style={{ width: 20, display: "flex", justifyContent: "center", flexShrink: 0 }}>
                        <div
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            background: "#ef4444",
                            border: "2px solid #fff",
                            boxShadow: "0 0 0 3px rgba(239,68,68,0.18), 0 0 8px rgba(239,68,68,0.35)",
                            flexShrink: 0,
                          }}
                        />
                      </div>
                      <div style={{ flex: 1, height: 2, marginLeft: 4, background: "linear-gradient(90deg, #ef4444 60%, rgba(239,68,68,0.08))", borderRadius: 1 }} />
                      <span
                        style={{
                          position: "absolute",
                          right: 0,
                          fontSize: 9,
                          fontWeight: 800,
                          color: "#ef4444",
                          fontFamily: "'DM Mono', monospace",
                          background: "#fff",
                          padding: "1px 6px",
                          borderRadius: 4,
                          border: "1px solid rgba(239,68,68,0.2)",
                          letterSpacing: 0.5,
                        }}
                      >
                        MAINTENANT
                      </span>
                    </div>
                  )}
                  <div style={{ display: "flex", minHeight: 36 }}>
                    <div
                      style={{
                        width: 36,
                        paddingTop: 8,
                        fontSize: 10,
                        fontFamily: "'DM Mono', monospace",
                        color: current ? TEALX : done ? "#cbd5e1" : "#94a3b8",
                        fontWeight: current ? 700 : 400,
                        flexShrink: 0,
                        textAlign: "right",
                        paddingRight: 8,
                      }}
                    >
                      {slot.hour}
                    </div>
                    <div style={{ width: 20, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 10, flexShrink: 0 }}>
                      <div
                        style={{
                          width: 9,
                          height: 9,
                          borderRadius: "50%",
                          flexShrink: 0,
                          background: current ? TEAL : done ? "#d1fae5" : empty ? "#f1f5f9" : "#e2e8f0",
                          border: `2px solid ${current ? "rgba(0,212,160,0.4)" : "transparent"}`,
                          boxShadow: current ? "0 0 0 3px rgba(0,212,160,0.12)" : "none",
                        }}
                      />
                      {index < agendaByHour.length - 1 && (
                        <div style={{ width: 2, flex: 1, background: done ? "rgba(0,212,160,0.15)" : "#f1f5f9", borderRadius: 1 }} />
                      )}
                    </div>
                    <div style={{ flex: 1, paddingLeft: 6, paddingBottom: 2 }}>
                      {empty ? (
                        <div style={{ paddingTop: 6, fontSize: 10, color: "#e2e8f0", fontStyle: "italic" }}>Libre</div>
                      ) : (
                        <div
                          style={{
                            margin: "3px 0 3px",
                            padding: "8px 10px",
                            borderRadius: 7,
                            background: current ? "rgba(0,212,160,0.05)" : done ? "#fafafa" : "#fff",
                            border: `1px solid ${current ? "rgba(0,212,160,0.2)" : done ? "#f1f5f9" : "#e2e8f0"}`,
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            opacity: done ? 0.55 : 1,
                            boxShadow: current ? "0 2px 10px rgba(0,212,160,0.08)" : "0 1px 2px rgba(0,0,0,0.03)",
                          }}
                          className={current ? "slot-now" : ""}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 6 }}>
                              {slot.patient}
                              {done && <span style={{ fontSize: 9, color: TEALX, fontWeight: 700 }}>✓</span>}
                              {current && <Pulse color={TEAL} size={6} />}
                            </div>
                            <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 1 }}>{slot.type}</div>
                          </div>
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 700,
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: slot.source === "UWI" ? "rgba(0,212,160,0.08)" : "rgba(99,102,241,0.08)",
                              color: slot.source === "UWI" ? TEALX : "#6366f1",
                              border: `1px solid ${slot.source === "UWI" ? "rgba(0,212,160,0.2)" : "rgba(99,102,241,0.2)"}`,
                            }}
                          >
                            {slot.source}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            }) : (
              <div style={{ padding: "18px 4px", fontSize: 12, color: "#94a3b8" }}>
                Agenda non connecté — configurez dans Horaires.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const S = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
    fontFamily: "'DM Sans', sans-serif",
    color: NAVY,
  },
  level2: { display: "flex", gap: 14, flexShrink: 0 },
  level3: { display: "flex", gap: 14, flex: 1, overflow: "hidden", minHeight: 0 },
  hero: {
    flex: 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: `linear-gradient(135deg, #0a2540 0%, ${NAVY} 100%)`,
    border: "1px solid rgba(0,212,160,0.15)",
    borderRadius: 12,
    padding: "18px 22px",
    position: "relative",
    overflow: "hidden",
    boxShadow: "0 4px 20px rgba(13,27,46,0.12)",
  },
  heroGrid: {
    position: "absolute",
    inset: 0,
    backgroundImage:
      "linear-gradient(rgba(0,212,160,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,160,0.04) 1px, transparent 1px)",
    backgroundSize: "28px 28px",
    pointerEvents: "none",
  },
  heroGlow: {
    position: "absolute",
    top: -30,
    right: -30,
    width: 160,
    height: 160,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(0,212,160,0.1) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  heroGreeting: { fontSize: 20, fontWeight: 700, color: "#fff", position: "relative" },
  heroSub: { fontSize: 12, color: "rgba(255,255,255,0.55)", marginTop: 4, position: "relative" },
  kpi: {
    padding: "10px 16px",
    borderRadius: 9,
    background: "rgba(0,0,0,0.2)",
    border: "1px solid rgba(255,255,255,0.07)",
    textAlign: "center",
    minWidth: 80,
  },
  actionsCol: { display: "flex", flexDirection: "column", gap: 8, width: 280, flexShrink: 0 },
  scanLabel: { fontSize: 9, color: "#94a3b8", letterSpacing: 1.8, fontWeight: 700, marginBottom: 2 },
  actionCard: { display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 10, flex: 1 },
  actionCta: {
    padding: "7px 13px",
    borderRadius: 7,
    border: "none",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
    fontFamily: "inherit",
  },
  urgBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 18px",
    background: "#7f1d1d",
    borderRadius: 12,
    border: "2px solid #991b1b",
    gap: 16,
  },
  urgBarLeft: { display: "flex", alignItems: "center", gap: 14, flex: 1 },
  urgIcon: { fontSize: 20, flexShrink: 0, filter: "drop-shadow(0 0 6px rgba(255,100,100,0.6))" },
  urgTitle: { fontSize: 13, fontWeight: 800, color: "#fff", letterSpacing: 0.3 },
  urgItems: { display: "flex", flexDirection: "column", gap: 1, marginTop: 2 },
  urgItem: { fontSize: 11, color: "rgba(255,255,255,0.75)", display: "flex", alignItems: "center", gap: 8 },
  urgTime: { fontSize: 10, color: "rgba(255,255,255,0.45)", fontFamily: "'DM Mono', monospace", marginLeft: 4 },
  urgCta: {
    padding: "8px 18px",
    borderRadius: 7,
    background: "#fff",
    border: "none",
    color: "#7f1d1d",
    fontSize: 12,
    fontWeight: 800,
    cursor: "pointer",
    whiteSpace: "nowrap",
    boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
    fontFamily: "inherit",
  },
  urgDismiss: {
    width: 28,
    height: 28,
    borderRadius: 6,
    background: "rgba(255,255,255,0.12)",
    border: "1px solid rgba(255,255,255,0.2)",
    color: "rgba(255,255,255,0.7)",
    fontSize: 12,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "inherit",
  },
  card: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    padding: "16px 18px",
    boxShadow: "0 1px 6px rgba(0,0,0,0.05)",
    flexShrink: 0,
  },
  cardHead: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  cardTag: { fontSize: 9, color: "#94a3b8", letterSpacing: 1.8, fontWeight: 700, marginBottom: 3 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: NAVY },
  ghost: {
    background: "none",
    border: "1px solid #e2e8f0",
    color: "#94a3b8",
    fontSize: 11,
    padding: "4px 11px",
    borderRadius: 6,
    cursor: "pointer",
    fontWeight: 600,
    fontFamily: "inherit",
  },
  callRow: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 10,
    padding: "10px 12px",
    borderRadius: 9,
    border: "1px solid",
    cursor: "pointer",
    transition: "all 0.15s",
  },
  agentChip: {
    fontSize: 10,
    padding: "2px 7px",
    borderRadius: 4,
    background: "rgba(0,212,160,0.08)",
    color: TEALX,
    fontWeight: 700,
    border: "1px solid rgba(0,212,160,0.2)",
  },
  statusTag: {
    fontSize: 10,
    fontWeight: 800,
    padding: "3px 8px",
    borderRadius: 5,
    letterSpacing: 0.3,
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  pillBtn: {
    padding: "6px 13px",
    borderRadius: 6,
    border: "none",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  agSummary: {
    display: "grid",
    gridTemplateColumns: "repeat(3,1fr)",
    gap: 6,
    marginBottom: 10,
    padding: "8px 0",
    borderTop: "1px solid #f1f5f9",
    borderBottom: "1px solid #f1f5f9",
  },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@500;700&display=swap');
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-thumb { background: rgba(0,212,160,0.2); border-radius: 4px; }
  @keyframes ping { 0% { transform: scale(1); opacity: 0.4; } 80%,100% { transform: scale(2.5); opacity: 0; } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes growWidth { from { width: 0 !important; } }
  @keyframes slideDown { from { opacity: 0; transform: translateY(-100%); } to { opacity: 1; transform: translateY(0); } }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .call-row { animation: fadeUp 0.3s ease both; }
  .call-row:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.07) !important; transform: translateY(-1px); }
  .kpi-card { transition: transform 0.2s; }
  .kpi-card:hover { transform: translateY(-2px); }
  .expand-in { animation: fadeUp 0.2s ease both; }
  .bar-fill { animation: growWidth 1.2s cubic-bezier(.4,0,.2,1) 0.3s both; }
  .slot-now { box-shadow: 0 2px 10px rgba(0,212,160,0.1) !important; }
  .urg-bar { animation: slideDown 0.35s cubic-bezier(.4,0,.2,1); }
  .dash-skel {
    border-radius: 12px;
    background: linear-gradient(90deg, #eef3f8 20%, #f8fbfd 50%, #eef3f8 80%);
    background-size: 200% 100%;
    animation: shimmer 1.4s linear infinite;
  }
`;
