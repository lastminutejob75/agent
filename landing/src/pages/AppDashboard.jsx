import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const TEAL = "#00d4a0";
const TEALX = "#00b389";
const NAVY = "#0d1b2e";

const STATUS_CFG = {
  TRANSFERRED: { color: "#dc2626", bg: "#fef2f2", border: "#fecaca", label: "TRANSFÉRÉ", icon: "↗" },
  CONFIRMED: { color: "#00b389", bg: "#f0fdf9", border: "#99f0da", label: "CONFIRMÉ", icon: "✓" },
  ABANDONED: { color: "#94a3b8", bg: "#f8fafc", border: "#e2e8f0", label: "RACCROCHÉ", icon: "–" },
  FAQ: { color: "#d97706", bg: "#fffbeb", border: "#fde68a", label: "INFO", icon: "?" },
};

function Pulse({ color = TEAL, size = 8 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, opacity: 0.35, animation: "uwi-ping 1.8s ease-out infinite" }} />
      <span style={{ width: "100%", height: "100%", borderRadius: "50%", background: color, display: "block" }} />
    </span>
  );
}

function Skeleton({ w = "100%", h = 14, radius = 6 }) {
  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: radius,
        background: "linear-gradient(90deg,#f1f5f9 25%,#e8edf2 50%,#f1f5f9 75%)",
        backgroundSize: "200% 100%",
        animation: "uwi-shimmer 1.4s infinite",
      }}
    />
  );
}

export default function AppDashboard() {
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState(null);
  const [calls, setCalls] = useState([]);
  const [agenda, setAgenda] = useState(null);
  const [me, setMe] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    Promise.all([
      api.tenantKpis(1).catch(() => null),
      api.tenantGetCalls("?limit=20&days=1").catch(() => ({ calls: [] })),
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

  const dateStr = now.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  const showPendingSetupBanner = !loading && !me?.voice_number && !me?.vapi_assistant_id;

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      <div style={S.identity}>
        <div style={S.identityLeft}>
          <div style={S.identityIcon}>
            <span style={{ fontSize: 18 }}>🎙️</span>
          </div>
          <div>
            <div style={S.identityName}>
              {loading ? <Skeleton w={120} h={16} /> : (me?.assistant_name || "Sophie")}
              <span style={S.identityBadge}>IA ACTIVE</span>
            </div>
            <div style={S.identityPlan}>
              {loading ? (
                <Skeleton w={160} h={11} />
              ) : (
                <>
                  {me?.plan_key?.toUpperCase() || "STARTER"}
                  {me?.voice_number && (
                    <>
                      {" "}
                      · <span style={{ fontFamily: "monospace", color: TEAL, fontWeight: 700 }}>{me.voice_number}</span>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
        <div style={S.identityRight}>
          <Pulse color={TEAL} size={7} />
          <span style={{ fontSize: 11, color: TEAL, fontWeight: 600 }}>En ligne</span>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", fontFamily: "monospace" }}>
            {now.toTimeString().slice(0, 5)}
          </span>
        </div>
      </div>

      {showPendingSetupBanner && (
        <div style={S.pendingBanner}>
          <span style={{ fontSize: 16 }}>⏳</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>
              Configuration en cours
            </div>
            <div style={{ fontSize: 11, color: "#7c2d12", marginTop: 2 }}>
              Notre équipe active votre assistant vocal sous 24h. Vous recevrez un email dès que votre numéro est prêt.
            </div>
          </div>
        </div>
      )}

      <div style={S.kpiRow}>
        {loading ? (
          [1, 2, 3, 4].map((i) => (
            <div key={i} style={S.kpiCard}>
              <Skeleton w={40} h={22} />
              <div style={{ marginTop: 4 }}>
                <Skeleton w={60} h={10} />
              </div>
            </div>
          ))
        ) : (
          [
            { value: kpis?.current?.calls ?? 0, label: "Appels", color: NAVY },
            { value: kpis?.current?.bookings ?? 0, label: "RDV confirmés", color: TEALX },
            { value: `${Math.round((kpis?.pickup_rate ?? 0) * 100)}%`, label: "Décroché", color: "#3b82f6" },
            { value: kpis?.minutes_month ?? 0, label: "Min ce mois", color: "#8b5cf6" },
          ].map((k) => (
            <div key={k.label} style={S.kpiCard}>
              <div style={{ fontSize: 22, fontWeight: 800, color: k.color, lineHeight: 1 }}>{k.value}</div>
              <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 3, fontWeight: 600 }}>{k.label}</div>
            </div>
          ))
        )}
      </div>

      <div style={S.main}>
        <div style={S.panel}>
          <div style={S.panelHead}>
            <div>
              <div style={S.panelLabel}>{dateStr.toUpperCase()}</div>
              <div style={S.panelTitle}>Appels du jour</div>
            </div>
            <a href="/app/appels" style={S.linkBtn}>Tout voir →</a>
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} h={60} radius={10} />)}
              </div>
            ) : calls.length === 0 ? (
              <div style={S.empty}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>📵</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#475569" }}>Aucun appel aujourd&apos;hui</div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>Votre assistante est active et prête à répondre</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {calls.map((c, i) => {
                  const s = STATUS_CFG[c.status] || STATUS_CFG.ABANDONED;
                  const open = expanded === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => setExpanded(open ? null : c.id)}
                      style={{
                        ...S.callRow,
                        background: open ? s.bg : "#fff",
                        borderLeft: `3px solid ${s.color}`,
                        animationDelay: `${i * 35}ms`,
                      }}
                      className="uwi-call-row"
                    >
                      <div style={S.callTime}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "#334155", fontFamily: "monospace" }}>{c.time}</div>
                        <div style={{ fontSize: 10, color: "#cbd5e1", marginTop: 1 }}>{c.duration}</div>
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 8 }}>
                          {c.patient_name || "Numéro masqué"}
                          <span style={{ ...S.chip, background: "rgba(0,212,160,0.08)", color: TEALX, border: "1px solid rgba(0,212,160,0.2)" }}>
                            {c.agent_name || "UWI"}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginTop: 3, lineHeight: 1.5 }}>{c.summary}</div>
                        {open && (
                          <div style={{ display: "flex", gap: 8, marginTop: 10 }} className="uwi-expand">
                            {c.status === "TRANSFERRED" && (
                              <button style={{ ...S.btn, background: "#dc2626" }}>📞 Rappeler</button>
                            )}
                            <a href="/app/appels" style={{ ...S.btn, background: "#f1f5f9", color: "#475569", textDecoration: "none" }}>
                              Transcription →
                            </a>
                          </div>
                        )}
                      </div>
                      <span style={{ ...S.chip, background: s.bg, color: s.color, border: `1px solid ${s.border}`, flexShrink: 0, fontSize: 10, fontWeight: 800 }}>
                        {s.icon} {s.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div style={{ ...S.panel, width: 290, flexShrink: 0 }}>
          <div style={S.panelHead}>
            <div>
              <div style={S.panelLabel}>AUJOURD&apos;HUI</div>
              <div style={S.panelTitle}>Agenda</div>
            </div>
            <a href="/app/agenda" style={S.linkBtn}>Ouvrir →</a>
          </div>

          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} h={36} radius={8} />)}
            </div>
          ) : !agenda?.slots?.length ? (
            <div style={S.empty}>
              <div style={{ fontSize: 30, marginBottom: 10 }}>📅</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#475569" }}>Aucun RDV aujourd&apos;hui</div>
              {!me?.onboarding_steps?.calendar_ready && (
                <a href="/app/agenda" style={{ ...S.btn, background: TEAL, color: NAVY, textDecoration: "none", marginTop: 14, display: "inline-block" }}>
                  Connecter l&apos;agenda →
                </a>
              )}
            </div>
          ) : (
            <>
              <div style={S.agendaSummary}>
                {[
                  { n: agenda.total, l: "Total", c: NAVY },
                  { n: agenda.done, l: "Passés", c: TEALX },
                  { n: agenda.remaining, l: "À venir", c: "#3b82f6" },
                ].map((s) => (
                  <div key={s.l} style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: s.c }}>{s.n}</div>
                    <div style={{ fontSize: 9, color: "#94a3b8", marginTop: 1, fontWeight: 600 }}>{s.l}</div>
                  </div>
                ))}
              </div>
              <div style={{ height: 3, background: "#f1f5f9", borderRadius: 2, overflow: "hidden", marginBottom: 12, flexShrink: 0 }}>
                <div style={{ height: "100%", width: `${agenda.total > 0 ? Math.round((agenda.done / agenda.total) * 100) : 0}%`, background: `linear-gradient(90deg,${TEAL},#60a5fa)`, borderRadius: 2 }} className="uwi-bar" />
              </div>
              <div style={{ flex: 1, overflowY: "auto" }}>
                {agenda.slots.map((slot, i) => {
                  const empty = !slot.patient;
                  const current = !!slot.current;
                  const done = !!slot.done;
                  return (
                    <div key={slot.hour} style={{ display: "flex", minHeight: 34 }}>
                      <div style={{ width: 34, paddingTop: 7, fontSize: 10, fontFamily: "monospace", color: current ? TEALX : done ? "#d1d5db" : "#94a3b8", fontWeight: current ? 700 : 400, flexShrink: 0, textAlign: "right", paddingRight: 8 }}>
                        {slot.hour}
                      </div>
                      <div style={{ width: 18, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 9, flexShrink: 0 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: current ? TEAL : done ? "#d1fae5" : empty ? "#f1f5f9" : "#e2e8f0", border: `2px solid ${current ? "rgba(0,212,160,0.4)" : "transparent"}` }} />
                        {i < agenda.slots.length - 1 && <div style={{ width: 2, flex: 1, background: done ? "rgba(0,212,160,0.12)" : "#f1f5f9" }} />}
                      </div>
                      <div style={{ flex: 1, paddingLeft: 6, paddingBottom: 2 }}>
                        {empty ? (
                          <div style={{ paddingTop: 5, fontSize: 10, color: "#e2e8f0", fontStyle: "italic" }}>Libre</div>
                        ) : (
                          <div style={{ margin: "2px 0", padding: "7px 9px", borderRadius: 7, background: current ? "rgba(0,212,160,0.04)" : done ? "#fafafa" : "#fff", border: `1px solid ${current ? "rgba(0,212,160,0.18)" : "#f1f5f9"}`, opacity: done ? 0.5 : 1 }}>
                            <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 5 }}>
                              {slot.patient}
                              {done && <span style={{ fontSize: 9, color: TEALX }}>✓</span>}
                              {current && <Pulse color={TEAL} size={5} />}
                            </div>
                            <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 1 }}>{slot.type}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>

      <div style={S.shortcuts}>
        {[
          { icon: "⏰", label: "Horaires", href: "/app/horaires", color: TEAL },
          { icon: "💬", label: "FAQ", href: "/app/faq", color: "#f59e0b" },
          { icon: "💳", label: "Abonnement", href: "/app/facturation", color: "#8b5cf6" },
          { icon: "⚙️", label: "Paramètres", href: "/app/settings", color: "#64748b" },
        ].map((s) => (
          <a key={s.label} href={s.href} style={{ ...S.shortcut, borderColor: s.color + "30" }} className="uwi-shortcut">
            <span style={{ fontSize: 20 }}>{s.icon}</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: s.color }}>{s.label}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

const S = {
  root: { display: "flex", flexDirection: "column", height: "100%", background: "#f5f7fa", fontFamily: "'DM Sans', sans-serif", color: NAVY, overflow: "hidden" },
  identity: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "11px 24px", background: NAVY, flexShrink: 0 },
  identityLeft: { display: "flex", alignItems: "center", gap: 12 },
  identityIcon: { width: 36, height: 36, borderRadius: 9, background: "rgba(0,212,160,0.15)", border: "1px solid rgba(0,212,160,0.25)", display: "flex", alignItems: "center", justifyContent: "center" },
  identityName: { fontSize: 14, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 8 },
  identityBadge: { fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 10, background: "rgba(0,212,160,0.15)", color: TEAL, border: "1px solid rgba(0,212,160,0.3)", letterSpacing: 0.8 },
  identityPlan: { fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 2 },
  identityRight: { display: "flex", alignItems: "center", gap: 8 },
  pendingBanner: {
    background: "rgba(245,158,11,0.1)",
    border: "1px solid rgba(245,158,11,0.25)",
    borderRadius: 0,
    padding: "10px 24px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexShrink: 0,
  },
  kpiRow: { display: "flex", gap: 10, padding: "10px 24px", background: "#fff", borderBottom: "1px solid #f1f5f9", flexShrink: 0 },
  kpiCard: { flex: 1, padding: "8px 12px", borderRadius: 8, background: "#f8fafc", border: "1px solid #f1f5f9" },
  main: { display: "flex", gap: 12, flex: 1, padding: "12px 24px", overflow: "hidden", minHeight: 0 },
  panel: { flex: 1, background: "#fff", borderRadius: 12, border: "1px solid #e8ecf0", padding: "16px 18px", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" },
  panelHead: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14, flexShrink: 0 },
  panelLabel: { fontSize: 9, color: "#94a3b8", letterSpacing: 1.6, fontWeight: 700, marginBottom: 2 },
  panelTitle: { fontSize: 15, fontWeight: 700, color: NAVY },
  linkBtn: { fontSize: 11, color: TEALX, fontWeight: 700, textDecoration: "none", padding: "4px 10px", borderRadius: 6, background: "rgba(0,212,160,0.06)", border: "1px solid rgba(0,212,160,0.18)" },
  callRow: { display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", borderRadius: 9, border: "1px solid #f1f5f9", cursor: "pointer", transition: "all 0.15s" },
  callTime: { width: 42, flexShrink: 0 },
  chip: { fontSize: 10, padding: "2px 7px", borderRadius: 5, fontWeight: 700 },
  btn: { padding: "6px 12px", borderRadius: 6, border: "none", color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  agendaSummary: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 4, marginBottom: 10, padding: "8px 0", borderTop: "1px solid #f8fafc", borderBottom: "1px solid #f8fafc", flexShrink: 0 },
  empty: { flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px 16px", textAlign: "center" },
  shortcuts: { display: "flex", gap: 8, padding: "10px 24px 16px", flexShrink: 0 },
  shortcut: { flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "10px 8px", borderRadius: 10, border: "1px solid", background: "#fff", textDecoration: "none", transition: "all 0.15s" },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; }
  @keyframes uwi-ping    { 0%{transform:scale(1);opacity:.4} 80%,100%{transform:scale(2.5);opacity:0} }
  @keyframes uwi-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  @keyframes uwi-fadeup  { from{opacity:0;transform:translateY(5px)} to{opacity:1;transform:translateY(0)} }
  @keyframes uwi-grow    { from{width:0!important} }
  .uwi-call-row { animation: uwi-fadeup 0.25s ease both; }
  .uwi-call-row:hover { background: #fafbfc !important; box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important; }
  .uwi-expand   { animation: uwi-fadeup 0.2s ease both; }
  .uwi-bar      { animation: uwi-grow 1s cubic-bezier(.4,0,.2,1) 0.3s both; }
  .uwi-shortcut:hover { transform: translateY(-1px); box-shadow: 0 3px 10px rgba(0,0,0,0.06); }
`;
