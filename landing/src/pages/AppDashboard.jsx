import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

// ─── CONFIG ──────────────────────────────────────────────────────────────────

const TEAL  = "#00d4a0";
const TEALX = "#00b389";
const NAVY  = "#0d1b2e";

const STATUS_CFG = {
  TRANSFERRED: { color: "#dc2626", bg: "#fef2f2", border: "#fecaca", label: "URGENCE",   icon: "⚠" },
  CONFIRMED:   { color: "#00b389", bg: "#f0fdf9", border: "#99f0da", label: "CONFIRMÉ",  icon: "✓" },
  ABANDONED:   { color: "#94a3b8", bg: "#f8fafc", border: "#e2e8f0", label: "ABANDONNÉ", icon: "→" },
  FAQ:         { color: "#d97706", bg: "#fffbeb", border: "#fde68a", label: "INFO",      icon: "◎" },
};

// ─── MICRO COMPONENTS ────────────────────────────────────────────────────────

function Pulse({ color = TEAL, size = 8 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, opacity: 0.35, animation: "ping 1.8s ease-out infinite" }} />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: color, display: "block" }} />
    </span>
  );
}

function AnimatedNumber({ target, suffix = "" }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let v = 0;
    const step = Math.max(1, Math.ceil(target / 40));
    const t = setInterval(() => { v = Math.min(v + step, target); setVal(v); if (v >= target) clearInterval(t); }, 16);
    return () => clearInterval(t);
  }, [target]);
  return <>{val}{suffix}</>;
}

function SkeletonLine({ w = "100%", h = 14, mb = 0 }) {
  return <div style={{ width: w, height: h, borderRadius: 6, background: "linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)", backgroundSize: "200% 100%", animation: "shimmer 1.4s infinite", marginBottom: mb }} />;
}

// ─── MAIN ────────────────────────────────────────────────────────────────────

export default function AppDashboard() {
  const [loading, setLoading]     = useState(true);
  const [kpis, setKpis]           = useState(null);
  const [calls, setCalls]         = useState([]);
  const [agenda, setAgenda]       = useState(null);
  const [me, setMe]               = useState(null);
  const [selected, setSelected]   = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [now, setNow]             = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    Promise.all([
      api.tenantKpis(1).catch(() => null),
      api.tenantGetCalls("?limit=10&days=1").catch(() => ({ calls: [] })),
      api.tenantGetAgenda().catch(() => null),
      api.tenantMe().catch(() => null),
    ]).then(([k, c, a, m]) => {
      setKpis(k);
      setCalls(c?.calls || []);
      setAgenda(a);
      setMe(m);
      setLoading(false);
    });
  }, []);

  const today = now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const urgences = calls.filter(c => c.status === "TRANSFERRED" && !dismissed);
  const aTraiter = calls.filter(c => ["FAQ", "TRANSFERRED"].includes(c.status));

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      {/* ── TOPBAR ── */}
      <header style={S.header}>
        <div>
          <h1 style={S.h1}>Vue d'ensemble</h1>
          <p style={{ fontSize: 12, color: "#94a3b8", margin: "2px 0 0" }}>{today}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={S.liveBadge}>
            <Pulse color={TEAL} />
            <span style={{ fontSize: 11, color: TEALX, fontWeight: 700 }}>IA ACTIVE</span>
          </div>
          <div style={S.clockBox}>
            <span style={{ fontFamily: "monospace", fontWeight: 700, letterSpacing: 1.5, color: NAVY }}>
              {now.toTimeString().slice(0, 8)}
            </span>
          </div>
          <button style={S.bellBtn}>
            <span style={{ fontSize: 16 }}>🔔</span>
            {urgences.length > 0 && <div style={S.bellDot} />}
          </button>
        </div>
      </header>

      <div style={S.body}>

        {/* ── URGENCES ── */}
        {urgences.length > 0 && (
          <div style={S.urgBar} className="urg-bar">
            <div style={S.urgBarLeft}>
              <div style={{ fontSize: 20 }}>⚠</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: "#fff" }}>
                  {urgences.length} urgence{urgences.length > 1 ? "s" : ""} signalée{urgences.length > 1 ? "s" : ""}
                </div>
                {urgences.map(u => (
                  <div key={u.id} style={{ fontSize: 11, color: "rgba(255,255,255,0.75)", marginTop: 2 }}>
                    <strong>{u.patient_name}</strong> — {u.summary}
                    <span style={{ fontSize: 10, color: "rgba(255,255,255,0.45)", fontFamily: "monospace", marginLeft: 8 }}>{u.time}</span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <button style={S.urgCta}>📞 Rappeler maintenant</button>
              <button style={S.urgDismiss} onClick={() => setDismissed(true)}>✕</button>
            </div>
          </div>
        )}

        {/* ── NIVEAU 2 : HERO + À TRAITER ── */}
        <div style={S.level2}>

          {/* Hero dark */}
          <div style={S.hero}>
            <div style={S.heroGrid} />
            <div style={S.heroGlow} />
            <div style={{ position: "relative" }}>
              <div style={S.heroGreeting}>
                {loading ? "Chargement…" : `Bonjour, ${me?.tenant_name || "cabinet"} 👋`}
              </div>
              <div style={S.heroSub}>
                {loading
                  ? <SkeletonLine w={180} h={12} />
                  : <>UWI a traité <strong style={{ color: TEAL }}>{kpis?.current?.calls ?? 0} appels</strong> aujourd'hui</>
                }
              </div>
            </div>
            <div style={{ position: "relative", display: "flex", gap: 8 }}>
              {loading ? (
                [1,2,3].map(i => <div key={i} style={{ ...S.kpi }}><SkeletonLine w={40} h={24} mb={4} /><SkeletonLine w={50} h={8} /></div>)
              ) : (
                [
                  { n: Math.round((kpis?.pickup_rate ?? 0) * 100),  s: "%", label: "DÉCROCHÉ",   color: TEAL },
                  { n: kpis?.current?.bookings ?? 0,                 s: "",  label: "RDV PRIS",   color: "#a78bfa" },
                  { n: kpis?.minutes_month ?? 0,                     s: "",  label: "MIN / MOIS", color: "#60a5fa" },
                ].map(k => (
                  <div key={k.label} style={S.kpi} className="kpi-card">
                    <div style={{ fontSize: 24, fontWeight: 800, color: k.color, lineHeight: 1 }}>
                      <AnimatedNumber target={k.n} suffix={k.s} />
                    </div>
                    <div style={{ fontSize: 9, color: "rgba(255,255,255,0.5)", letterSpacing: 1.2, marginTop: 4, fontWeight: 700 }}>
                      {k.label}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* À traiter */}
          {aTraiter.length > 0 && (
            <div style={S.actionsCol}>
              <div style={S.scanLabel}>À TRAITER</div>
              {aTraiter.slice(0, 3).map(c => {
                const s = STATUS_CFG[c.status] || STATUS_CFG.FAQ;
                return (
                  <div key={c.id} style={{ ...S.actionCard, background: s.bg, border: `1px solid ${s.border}` }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: NAVY }}>{c.patient_name || "Patient"}</div>
                      <div style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>{c.summary}</div>
                    </div>
                    <button style={{ ...S.actionCta, background: s.color }}>
                      {c.status === "FAQ" ? "Voir →" : "📞 Rappeler"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── NIVEAU 3 : APPELS + AGENDA ── */}
        <div style={S.level3}>

          {/* Appels */}
          <div style={{ ...S.card, flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>AUJOURD'HUI · {calls.length} APPELS</div>
                <div style={S.cardTitle}>Appels récents</div>
              </div>
              <a href="/app/appels" style={S.ghost}>Historique →</a>
            </div>

            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1,2,3].map(i => <SkeletonLine key={i} h={52} />)}
              </div>
            ) : calls.length === 0 ? (
              <div style={{ textAlign: "center", color: "#94a3b8", fontSize: 13, padding: "32px 0" }}>
                Aucun appel aujourd'hui
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 5, overflowY: "auto" }}>
                {calls.map((c, i) => {
                  const s = STATUS_CFG[c.status] || STATUS_CFG.ABANDONED;
                  const open = selected === c.id;
                  return (
                    <div key={c.id}
                      style={{
                        ...S.callRow,
                        background: open ? s.bg : "#fff",
                        borderColor: open ? s.border : "#f1f5f9",
                        borderLeft: `3px solid ${s.color}`,
                        animationDelay: `${i * 60}ms`,
                      }}
                      className="call-row"
                      onClick={() => setSelected(open ? null : c.id)}
                    >
                      <div style={{ width: 46, flexShrink: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", fontFamily: "monospace" }}>{c.time}</div>
                        <div style={{ fontSize: 10, color: "#cbd5e1", marginTop: 1 }}>{c.duration}</div>
                      </div>
                      <Pulse color={s.color} size={7} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 8 }}>
                          {c.patient_name || "Inconnu"}
                          <span style={S.agentChip}>{c.agent_name || "UWI"}</span>
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginTop: 3, lineHeight: 1.5 }}>{c.summary}</div>
                        {open && (
                          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }} className="expand-in">
                            <button style={{ ...S.pillBtn, background: s.color }}>
                              {c.status === "CONFIRMED" ? "✓ Confirmé" : "📞 Rappeler"}
                            </button>
                            <a href="/app/appels" style={S.ghost}>Transcription</a>
                          </div>
                        )}
                      </div>
                      <span style={{ ...S.statusTag, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
                        {s.icon} {s.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Agenda */}
          <div style={{ ...S.card, width: 320, display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0 }}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>{now.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).toUpperCase()}</div>
                <div style={S.cardTitle}>Agenda du jour</div>
              </div>
              <a href="/app/agenda" style={S.ghost}>Ouvrir →</a>
            </div>

            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1,2,3,4].map(i => <SkeletonLine key={i} h={40} />)}
              </div>
            ) : !agenda || !agenda.slots?.length ? (
              <div style={{ textAlign: "center", padding: "24px 16px" }}>
                <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 12 }}>Agenda non connecté</div>
                <a href="/app/agenda" style={{ ...S.pillBtn, background: TEAL, color: NAVY, textDecoration: "none", padding: "8px 16px", borderRadius: 8, fontSize: 12, fontWeight: 700 }}>
                  Connecter →
                </a>
              </div>
            ) : (
              <>
                {/* Summary */}
                <div style={S.agSummary}>
                  {[
                    { n: agenda.total,     l: "RDV",      c: NAVY },
                    { n: agenda.done,      l: "Terminés", c: TEALX },
                    { n: agenda.remaining, l: "Restants",  c: "#3b82f6" },
                  ].map(s => (
                    <div key={s.l} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: s.c }}>{s.n}</div>
                      <div style={{ fontSize: 9, color: "#94a3b8", marginTop: 2, fontWeight: 600 }}>{s.l}</div>
                    </div>
                  ))}
                </div>

                {/* Progress */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ height: 4, background: "#f1f5f9", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      height: "100%",
                      width: `${agenda.total > 0 ? Math.round((agenda.done / agenda.total) * 100) : 0}%`,
                      background: `linear-gradient(90deg, ${TEAL}, #60a5fa)`,
                      borderRadius: 2,
                    }} className="bar-fill" />
                  </div>
                </div>

                {/* Timeline */}
                <div style={{ flex: 1, overflowY: "auto" }}>
                  {agenda.slots.map((slot, i) => {
                    const empty   = !slot.patient;
                    const current = !!slot.current;
                    const done    = !!slot.done;
                    return (
                      <div key={slot.hour}>
                        {current && (
                          <div style={{ display: "flex", alignItems: "center", margin: "3px 0", position: "relative" }}>
                            <div style={{ width: 36, flexShrink: 0 }} />
                            <div style={{ width: 20, display: "flex", justifyContent: "center", flexShrink: 0 }}>
                              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", border: "2px solid #fff", boxShadow: "0 0 0 3px rgba(239,68,68,0.18)" }} />
                            </div>
                            <div style={{ flex: 1, height: 2, marginLeft: 4, background: "linear-gradient(90deg, #ef4444 60%, rgba(239,68,68,0.08))", borderRadius: 1 }} />
                            <span style={{ position: "absolute", right: 0, fontSize: 9, fontWeight: 800, color: "#ef4444", fontFamily: "monospace", background: "#fff", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(239,68,68,0.2)" }}>
                              MAINTENANT
                            </span>
                          </div>
                        )}
                        <div style={{ display: "flex", minHeight: 36 }}>
                          <div style={{ width: 36, paddingTop: 8, fontSize: 10, fontFamily: "monospace", color: current ? TEALX : done ? "#cbd5e1" : "#94a3b8", fontWeight: current ? 700 : 400, flexShrink: 0, textAlign: "right", paddingRight: 8 }}>
                            {slot.hour}
                          </div>
                          <div style={{ width: 20, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 10, flexShrink: 0 }}>
                            <div style={{
                              width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
                              background: current ? TEAL : done ? "#d1fae5" : empty ? "#f1f5f9" : "#e2e8f0",
                              border: `2px solid ${current ? "rgba(0,212,160,0.4)" : "transparent"}`,
                              boxShadow: current ? `0 0 0 3px rgba(0,212,160,0.12)` : "none",
                            }} />
                            {i < agenda.slots.length - 1 && (
                              <div style={{ width: 2, flex: 1, background: done ? "rgba(0,212,160,0.15)" : "#f1f5f9", borderRadius: 1 }} />
                            )}
                          </div>
                          <div style={{ flex: 1, paddingLeft: 6, paddingBottom: 2 }}>
                            {empty ? (
                              <div style={{ paddingTop: 6, fontSize: 10, color: "#e2e8f0", fontStyle: "italic" }}>Libre</div>
                            ) : (
                              <div style={{
                                margin: "3px 0", padding: "8px 10px", borderRadius: 7,
                                background: current ? "rgba(0,212,160,0.05)" : done ? "#fafafa" : "#fff",
                                border: `1px solid ${current ? "rgba(0,212,160,0.2)" : done ? "#f1f5f9" : "#e2e8f0"}`,
                                display: "flex", alignItems: "center", gap: 8,
                                opacity: done ? 0.55 : 1,
                                boxShadow: current ? "0 2px 10px rgba(0,212,160,0.08)" : "0 1px 2px rgba(0,0,0,0.03)",
                              }}
                              className={current ? "slot-now" : ""}
                              >
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 6 }}>
                                    {slot.patient}
                                    {done    && <span style={{ fontSize: 9, color: TEALX, fontWeight: 700 }}>✓</span>}
                                    {current && <Pulse color={TEAL} size={6} />}
                                  </div>
                                  <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 1 }}>{slot.type}</div>
                                </div>
                                <span style={{
                                  fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 4,
                                  background: slot.source === "UWI" ? "rgba(0,212,160,0.08)" : "rgba(99,102,241,0.08)",
                                  color: slot.source === "UWI" ? TEALX : "#6366f1",
                                  border: `1px solid ${slot.source === "UWI" ? "rgba(0,212,160,0.2)" : "rgba(99,102,241,0.2)"}`,
                                }}>{slot.source || "EXT"}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── RACCOURCIS RAPIDES ── */}
        <div style={S.shortcuts}>
          {[
            { label: "⏰ Horaires",    href: "/app/horaires",  color: TEAL },
            { label: "📅 Agenda",      href: "/app/agenda",    color: "#60a5fa" },
            { label: "💳 Facturation", href: "/app/facturation", color: "#a78bfa" },
            { label: "⚙️ Paramètres", href: "/app/settings",    color: "#94a3b8" },
          ].map(s => (
            <a key={s.label} href={s.href} style={{ ...S.shortcut, borderColor: s.color + "33", color: s.color }}>
              {s.label}
            </a>
          ))}
        </div>

      </div>
    </div>
  );
}

// ─── STYLES ──────────────────────────────────────────────────────────────────

const S = {
  root:    { display: "flex", flexDirection: "column", height: "100%", background: "#f0f4f8", fontFamily: "'DM Sans', sans-serif", color: NAVY, overflow: "hidden" },
  body:    { flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 0 },

  header:  { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 28px 14px", background: "#fff", borderBottom: "1px solid #f1f5f9", flexShrink: 0 },
  h1:      { fontSize: 19, fontWeight: 700, color: NAVY, margin: 0 },
  liveBadge: { display: "flex", alignItems: "center", gap: 7, background: "rgba(0,212,160,0.08)", border: "1px solid rgba(0,212,160,0.22)", borderRadius: 20, padding: "5px 12px" },
  clockBox:  { background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "5px 11px", fontSize: 12 },
  bellBtn:   { position: "relative", width: 34, height: 34, borderRadius: 8, background: "#fff", border: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" },
  bellDot:   { position: "absolute", top: 5, right: 5, width: 7, height: 7, borderRadius: "50%", background: "#dc2626", border: "2px solid #fff" },

  urgBar:     { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 28px", background: "#7f1d1d", borderBottom: "2px solid #991b1b", flexShrink: 0, gap: 16 },
  urgBarLeft: { display: "flex", alignItems: "center", gap: 14, flex: 1 },
  urgCta:     { padding: "8px 18px", borderRadius: 7, background: "#fff", border: "none", color: "#7f1d1d", fontSize: 12, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  urgDismiss: { width: 28, height: 28, borderRadius: 6, background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.7)", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit" },

  level2:      { display: "flex", gap: 14, padding: "14px 28px 0", flexShrink: 0 },
  hero:        { flex: 1, display: "flex", justifyContent: "space-between", alignItems: "center", background: `linear-gradient(135deg, #0a2540 0%, ${NAVY} 100%)`, border: "1px solid rgba(0,212,160,0.15)", borderRadius: 12, padding: "18px 22px", position: "relative", overflow: "hidden", boxShadow: "0 4px 20px rgba(13,27,46,0.12)" },
  heroGrid:    { position: "absolute", inset: 0, backgroundImage: `linear-gradient(rgba(0,212,160,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,160,0.04) 1px, transparent 1px)`, backgroundSize: "28px 28px", pointerEvents: "none" },
  heroGlow:    { position: "absolute", top: -30, right: -30, width: 160, height: 160, borderRadius: "50%", background: `radial-gradient(circle, rgba(0,212,160,0.1) 0%, transparent 70%)`, pointerEvents: "none" },
  heroGreeting:{ fontSize: 20, fontWeight: 700, color: "#fff", position: "relative" },
  heroSub:     { fontSize: 12, color: "rgba(255,255,255,0.55)", marginTop: 4, position: "relative" },
  kpi:         { padding: "10px 16px", borderRadius: 9, background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.07)", textAlign: "center", minWidth: 80 },

  actionsCol:  { display: "flex", flexDirection: "column", gap: 8, width: 280, flexShrink: 0 },
  scanLabel:   { fontSize: 9, color: "#94a3b8", letterSpacing: 1.8, fontWeight: 700, marginBottom: 2 },
  actionCard:  { display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 10 },
  actionCta:   { padding: "7px 13px", borderRadius: 7, border: "none", color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap", fontFamily: "inherit" },

  level3:      { display: "flex", gap: 14, flex: 1, padding: "12px 28px 12px", overflow: "hidden", minHeight: 0 },
  card:        { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: "16px 18px", boxShadow: "0 1px 6px rgba(0,0,0,0.05)", flexShrink: 0 },
  cardHead:    { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  cardTag:     { fontSize: 9, color: "#94a3b8", letterSpacing: 1.8, fontWeight: 700, marginBottom: 3 },
  cardTitle:   { fontSize: 14, fontWeight: 700, color: NAVY },
  ghost:       { background: "none", border: "1px solid #e2e8f0", color: "#94a3b8", fontSize: 11, padding: "4px 11px", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontFamily: "inherit", textDecoration: "none" },

  callRow:     { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, padding: "10px 12px", borderRadius: 9, border: "1px solid", cursor: "pointer", transition: "all 0.15s" },
  agentChip:   { fontSize: 10, padding: "2px 7px", borderRadius: 4, background: "rgba(0,212,160,0.08)", color: TEALX, fontWeight: 700, border: "1px solid rgba(0,212,160,0.2)" },
  statusTag:   { fontSize: 10, fontWeight: 800, padding: "3px 8px", borderRadius: 5, letterSpacing: 0.3, whiteSpace: "nowrap", flexShrink: 0 },
  pillBtn:     { padding: "6px 13px", borderRadius: 6, border: "none", color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },

  agSummary:   { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 6, marginBottom: 10, padding: "8px 0", borderTop: "1px solid #f1f5f9", borderBottom: "1px solid #f1f5f9" },

  shortcuts:   { display: "flex", gap: 10, padding: "12px 28px 20px", flexShrink: 0 },
  shortcut:    { flex: 1, padding: "10px 16px", borderRadius: 10, border: "1px solid", background: "#fff", fontSize: 12, fontWeight: 700, textAlign: "center", textDecoration: "none", cursor: "pointer", transition: "all 0.15s" },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; }
  @keyframes ping { 0% { transform: scale(1); opacity: 0.4; } 80%,100% { transform: scale(2.5); opacity: 0; } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes growWidth { from { width: 0 !important; } }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  @keyframes slideDown { from { opacity: 0; transform: translateY(-100%); } to { opacity: 1; transform: translateY(0); } }
  .call-row { animation: fadeUp 0.3s ease both; }
  .call-row:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.07) !important; transform: translateY(-1px); }
  .kpi-card { transition: transform 0.2s; }
  .kpi-card:hover { transform: translateY(-2px); }
  .expand-in { animation: fadeUp 0.2s ease both; }
  .bar-fill { animation: growWidth 1.2s cubic-bezier(.4,0,.2,1) 0.3s both; }
  .slot-now { box-shadow: 0 2px 10px rgba(0,212,160,0.1) !important; }
  .urg-bar { animation: slideDown 0.35s cubic-bezier(.4,0,.2,1); }
  a.ghost:hover { border-color: #cbd5e1 !important; color: #64748b !important; }
`;
