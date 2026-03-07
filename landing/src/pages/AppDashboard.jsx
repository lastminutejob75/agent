import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

const TEAL = "#00d4a0";
const TEALX = "#00b389";
const NAVY = "#0d1b2e";

const STATUS_CFG = {
  TRANSFERRED: { color: "#dc2626", bg: "#fef2f2", border: "#fecaca", label: "URGENCE", icon: "⚠" },
  CONFIRMED: { color: "#00b389", bg: "#f0fdf9", border: "#99f0da", label: "CONFIRMÉ", icon: "✓" },
  ABANDONED: { color: "#94a3b8", bg: "#f8fafc", border: "#e2e8f0", label: "ABANDONNÉ", icon: "→" },
  FAQ: { color: "#d97706", bg: "#fffbeb", border: "#fde68a", label: "INFO", icon: "◎" },
};

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
    const t = setInterval(() => {
      v = Math.min(v + step, target);
      setVal(v);
      if (v >= target) clearInterval(t);
    }, 16);
    return () => clearInterval(t);
  }, [target]);

  return (
    <>
      {val}
      {suffix}
    </>
  );
}

function SkeletonLine({ w = "100%", h = 14, mb = 0 }) {
  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: 6,
        background: "linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s infinite",
        marginBottom: mb,
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
  const [selected, setSelected] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [now, setNow] = useState(new Date());

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

  const urgences = calls.filter((c) => c.status === "TRANSFERRED" && !dismissed);
  const aTraiter = calls.filter((c) => ["FAQ", "TRANSFERRED"].includes(c.status));
  const onboardingSteps = me?.onboarding_steps || {};
  const onboardingDoneCount = Object.values(onboardingSteps).filter(Boolean).length;
  const onboardingTotal = Object.keys(onboardingSteps).length || 1;
  const onboardingProgress = Math.round((onboardingDoneCount / onboardingTotal) * 100);
  const onboardingItems = [
    {
      key: "assistant_ready",
      icon: "🎙️",
      label: "Assistant vocal",
      sub: onboardingSteps.assistant_ready ? `${me?.assistant_name || "Votre assistant"} est prêt` : "Choisissez votre assistante",
      href: "/app/settings",
      cta: "Configurer",
    },
    {
      key: "phone_ready",
      icon: "📞",
      label: "Numéro d'appel",
      sub: onboardingSteps.phone_ready ? `Vos patients appellent le ${me?.voice_number}` : "Numéro non assigné — contacter UWI",
      href: null,
      cta: null,
    },
    {
      key: "calendar_ready",
      icon: "📅",
      label: "Agenda connecté",
      sub: onboardingSteps.calendar_ready ? "Google Calendar connecté" : "Connectez votre agenda",
      href: "/app/agenda",
      cta: "Connecter",
    },
    {
      key: "horaires_ready",
      icon: "⏰",
      label: "Horaires configurés",
      sub: onboardingSteps.horaires_ready ? "Horaires enregistrés" : "Définissez vos heures d'ouverture",
      href: "/app/horaires",
      cta: "Configurer",
    },
    {
      key: "faq_ready",
      icon: "💬",
      label: "FAQ",
      sub: "Bientôt disponible",
      href: null,
      cta: null,
      soon: true,
    },
  ];

  return (
    <div style={S.root}>
      <style>{CSS}</style>

      {me && !me.onboarding_completed && (
        <div style={S.onboarding}>
          <div style={S.onboardingHeader}>
            <div>
              <div style={S.onboardingTitle}>🚀 Activez votre assistant vocal</div>
              <div style={S.onboardingSub}>
                {onboardingDoneCount} / {onboardingTotal} étapes complétées
              </div>
            </div>
            <div style={{ width: 120 }}>
              <div style={{ height: 6, background: "rgba(255,255,255,0.15)", borderRadius: 3, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${onboardingProgress}%`,
                    background: TEAL,
                    borderRadius: 3,
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
            </div>
          </div>

          <div style={S.onboardingSteps}>
            {onboardingItems.map((step) => {
              const done = onboardingSteps[step.key];
              return (
                <div
                  key={step.key}
                  style={{
                    ...S.onboardingStep,
                    borderColor: done ? "rgba(0,212,160,0.3)" : "rgba(255,255,255,0.1)",
                    opacity: step.soon ? 0.5 : 1,
                  }}
                >
                  <div style={{ fontSize: 20, flexShrink: 0 }}>{step.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: done ? TEAL : "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                      {done && <span style={{ color: TEAL }}>✓</span>}
                      {step.label}
                    </div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>{step.sub}</div>
                  </div>
                  {!done && step.href && (
                    <a
                      href={step.href}
                      style={{
                        padding: "5px 12px",
                        borderRadius: 6,
                        background: TEAL,
                        color: NAVY,
                        fontSize: 11,
                        fontWeight: 700,
                        textDecoration: "none",
                        whiteSpace: "nowrap",
                        flexShrink: 0,
                      }}
                    >
                      {step.cta} →
                    </a>
                  )}
                  {step.soon && (
                    <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", fontWeight: 600 }}>Bientôt</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {urgences.length > 0 && (
        <div style={S.urgBar} className="urg-bar">
          <div style={S.urgBarLeft}>
            <div style={{ fontSize: 18 }}>⚠</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#fff" }}>
                {urgences.length} urgence{urgences.length > 1 ? "s" : ""} signalée{urgences.length > 1 ? "s" : ""}
              </div>
              {urgences.map((u) => (
                <div key={u.id} style={{ fontSize: 11, color: "rgba(255,255,255,.8)", marginTop: 1 }}>
                  <strong>{u.patient_name}</strong> — {u.summary}
                  <span style={{ fontFamily: "monospace", color: "rgba(255,255,255,.45)", marginLeft: 6 }}>{u.time}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button style={S.urgCta}>📞 Rappeler</button>
            <button onClick={() => setDismissed(true)} style={S.urgDismiss}>✕</button>
          </div>
        </div>
      )}

      <div style={S.body}>
        <div style={S.level2}>
          <div style={S.hero}>
            <div style={S.heroGrid} />
            <div style={S.heroGlow} />
            <div style={{ position: "relative" }}>
              <div style={S.heroGreeting}>
                {loading ? "Chargement…" : `Bonjour, ${me?.tenant_name || "cabinet"} 👋`}
              </div>
              <div style={S.heroSub}>
                {loading ? (
                  <SkeletonLine w={180} h={12} />
                ) : (
                  <>
                    Sophie a traité <strong style={{ color: TEAL }}>{kpis?.current?.calls ?? 0} appels</strong> aujourd&apos;hui
                  </>
                )}
              </div>
              {me?.voice_number && (
                <div
                  style={{
                    position: "relative",
                    marginTop: 8,
                    fontSize: 11,
                    color: "rgba(255,255,255,0.6)",
                  }}
                >
                  📞 Vos patients appellent le{" "}
                  <strong style={{ color: TEAL, fontFamily: "monospace" }}>
                    {me.voice_number}
                  </strong>
                </div>
              )}
            </div>
            <div style={{ position: "relative", display: "flex", gap: 7 }}>
              {loading ? (
                [1, 2, 3].map((i) => (
                  <div key={i} style={S.kpi}>
                    <SkeletonLine w={40} h={24} mb={4} />
                    <SkeletonLine w={50} h={8} />
                  </div>
                ))
              ) : (
                [
                  { n: Math.round((kpis?.pickup_rate ?? 0) * 100), s: "%", l: "DÉCROCHÉ", c: TEAL },
                  { n: kpis?.current?.bookings ?? 0, s: "", l: "RDV PRIS", c: "#a78bfa" },
                  { n: kpis?.minutes_month ?? 0, s: "", l: "MIN/MOIS", c: "#60a5fa" },
                ].map((k) => (
                  <div key={k.l} className="kp" style={S.kpi}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: k.c, lineHeight: 1 }}>
                      <AnimatedNumber target={k.n} suffix={k.s} />
                    </div>
                    <div style={{ fontSize: 8, color: "rgba(255,255,255,.45)", letterSpacing: 1.1, marginTop: 3, fontWeight: 700 }}>
                      {k.l}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {aTraiter.length > 0 && (
            <div style={S.actionsCol}>
              <div style={S.scanLabel}>À TRAITER</div>
              {aTraiter.slice(0, 1).map((c) => {
                const s = STATUS_CFG[c.status] || STATUS_CFG.FAQ;
                return (
                  <div key={c.id} style={{ ...S.actionCard, background: s.bg, border: `1px solid ${s.border}` }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: NAVY }}>{c.patient_name || "Patient"}</div>
                      <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>{c.summary}</div>
                    </div>
                    <button style={{ ...S.actionCta, background: s.color }}>
                      {c.status === "FAQ" ? "Voir →" : "Valider →"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={S.level3}>
          <div style={S.cardCalls}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>AUJOURD&apos;HUI · {calls.length} APPELS</div>
                <div style={S.cardTitle}>Appels récents</div>
              </div>
              <a href="/app/appels" style={S.ghost}>Historique →</a>
            </div>

            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1, 2, 3].map((i) => <SkeletonLine key={i} h={52} />)}
              </div>
            ) : calls.length === 0 ? (
              <div style={{ textAlign: "center", color: "#94a3b8", fontSize: 13, padding: "32px 0" }}>
                Aucun appel aujourd&apos;hui
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4, overflowY: "auto" }}>
                {calls.map((c, i) => {
                  const s = STATUS_CFG[c.status] || STATUS_CFG.ABANDONED;
                  const open = selected === c.id;
                  return (
                    <div
                      key={c.id}
                      className="cr"
                      style={{
                        ...S.callRow,
                        border: `1px solid ${open ? s.border : "#f1f5f9"}`,
                        borderLeft: `3px solid ${s.color}`,
                        background: open ? s.bg : "#fff",
                        animationDelay: `${i * 50}ms`,
                      }}
                      onClick={() => setSelected(open ? null : c.id)}
                    >
                      <div style={{ width: 42, flexShrink: 0 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", fontFamily: "monospace" }}>{c.time}</div>
                        <div style={{ fontSize: 9, color: "#94a3b8", marginTop: 1 }}>{c.duration}</div>
                      </div>
                      <Pulse color={s.color} size={7} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 7 }}>
                          {c.patient_name || "Inconnu"}
                          <span style={S.agentChip}>{c.agent_name || "UWI"}</span>
                        </div>
                        <div style={{ fontSize: 10, color: "#64748b", marginTop: 2, lineHeight: 1.4 }}>{c.summary}</div>
                        {open && (
                          <div className="xp" style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                            <button style={{ ...S.smallPrimary, background: s.color }}>
                              {c.status === "FAQ" ? "✓ Valider" : "📞 Rappeler"}
                            </button>
                            <button style={S.smallGhost}>Transcription</button>
                            <button style={S.smallGhost}>Fiche patient</button>
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

          <div style={S.cardAgenda}>
            <div style={S.cardHead}>
              <div>
                <div style={S.cardTag}>{now.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).toUpperCase()}</div>
                <div style={S.cardTitle}>Agenda du jour</div>
              </div>
              <a href="/app/agenda" style={S.ghost}>Ouvrir →</a>
            </div>

            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[1, 2, 3, 4].map((i) => <SkeletonLine key={i} h={40} />)}
              </div>
            ) : !agenda || !agenda.slots?.length ? (
              <div style={{ textAlign: "center", padding: "24px 16px" }}>
                <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 12 }}>Agenda non connecté</div>
                <a href="/app/agenda" style={{ ...S.smallPrimary, display: "inline-flex", textDecoration: "none", background: TEAL, color: NAVY, padding: "8px 16px" }}>
                  Connecter →
                </a>
              </div>
            ) : (
              <>
                <div style={{ marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 9, color: "#94a3b8", fontWeight: 600 }}>Progression journée</span>
                    <span style={{ fontSize: 9, color: TEALX, fontWeight: 700 }}>
                      {now.toTimeString().slice(0, 5)} · en cours
                    </span>
                  </div>
                  <div style={{ height: 3, background: "#f1f5f9", borderRadius: 2, overflow: "hidden" }}>
                    <div
                      className="bf"
                      style={{
                        height: "100%",
                        width: `${agenda.total > 0 ? Math.round((agenda.done / agenda.total) * 100) : 0}%`,
                        background: "linear-gradient(90deg,#00d4a0,#60a5fa)",
                        borderRadius: 2,
                      }}
                    />
                  </div>
                </div>

                <div style={S.agSummary}>
                  {[
                    { n: agenda.total, l: "RDV", c: NAVY },
                    { n: agenda.done, l: "Terminés", c: TEALX },
                    { n: agenda.remaining, l: "Restants", c: "#3b82f6" },
                  ].map((s) => (
                    <div key={s.l} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: s.c }}>{s.n}</div>
                      <div style={{ fontSize: 8, color: "#94a3b8", marginTop: 1, fontWeight: 600 }}>{s.l}</div>
                    </div>
                  ))}
                </div>

                <div style={{ flex: 1, overflowY: "auto" }}>
                  {agenda.slots.map((slot, i) => {
                    const empty = !slot.patient;
                    const curr = !!slot.current;
                    const done = !!slot.done;
                    return (
                      <div key={slot.hour}>
                        {curr && (
                          <div style={{ display: "flex", alignItems: "center", margin: "2px 0", position: "relative" }}>
                            <div style={{ width: 32, flexShrink: 0 }} />
                            <div style={{ width: 18, display: "flex", justifyContent: "center", flexShrink: 0 }}>
                              <div style={{ width: 9, height: 9, borderRadius: "50%", background: "#ef4444", border: "2px solid #fff", boxShadow: "0 0 0 2px rgba(239,68,68,.2),0 0 6px rgba(239,68,68,.3)" }} />
                            </div>
                            <div style={{ flex: 1, height: 2, marginLeft: 3, background: "linear-gradient(90deg,#ef4444,rgba(239,68,68,.04))", borderRadius: 1 }} />
                            <span style={{ position: "absolute", right: 0, fontSize: 8, fontWeight: 800, color: "#ef4444", background: "#fff", padding: "1px 5px", borderRadius: 3, border: "1px solid rgba(239,68,68,.2)" }}>
                              MAINTENANT
                            </span>
                          </div>
                        )}
                        <div style={{ display: "flex", minHeight: 32 }}>
                          <div style={{ width: 32, paddingTop: 7, fontSize: 9, fontFamily: "monospace", color: curr ? TEALX : done ? "#cbd5e1" : "#94a3b8", fontWeight: curr ? 700 : 400, flexShrink: 0, textAlign: "right", paddingRight: 6 }}>
                            {slot.hour}
                          </div>
                          <div style={{ width: 18, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 9, flexShrink: 0 }}>
                            <div style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: curr ? "#00d4a0" : done ? "#d1fae5" : empty ? "#f1f5f9" : "#e2e8f0", border: `2px solid ${curr ? "rgba(0,212,160,.4)" : "transparent"}`, boxShadow: curr ? "0 0 0 2px rgba(0,212,160,.12)" : "none" }} />
                            {i < agenda.slots.length - 1 && <div style={{ width: 2, flex: 1, background: done ? "rgba(0,212,160,.15)" : "#f1f5f9", borderRadius: 1 }} />}
                          </div>
                          <div style={{ flex: 1, paddingLeft: 5, paddingBottom: 1 }}>
                            {empty ? (
                              <div style={{ paddingTop: 5, fontSize: 9, color: "#cbd5e1", fontStyle: "italic" }}>Libre</div>
                            ) : (
                              <div style={{ margin: "2px 0", padding: "6px 8px", borderRadius: 6, background: curr ? "rgba(0,212,160,.05)" : done ? "#fafafa" : "#fff", border: `1px solid ${curr ? "rgba(0,212,160,.2)" : done ? "#f1f5f9" : "#e2e8f0"}`, display: "flex", alignItems: "center", gap: 6, opacity: done ? 0.5 : 1 }}>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{ fontSize: 11, fontWeight: 700, color: NAVY, display: "flex", alignItems: "center", gap: 5 }}>
                                    {slot.patient}
                                    {done && <span style={{ fontSize: 8, color: TEALX, fontWeight: 700 }}>✓</span>}
                                    {curr && <Pulse color="#00d4a0" size={5} />}
                                  </div>
                                  <div style={{ fontSize: 9, color: "#94a3b8", marginTop: 1 }}>{slot.type}</div>
                                </div>
                                <span style={{ fontSize: 8, fontWeight: 700, padding: "1px 5px", borderRadius: 3, background: slot.source === "UWI" ? "rgba(0,212,160,.08)" : "rgba(99,102,241,.08)", color: slot.source === "UWI" ? TEALX : "#6366f1", border: `1px solid ${slot.source === "UWI" ? "rgba(0,212,160,.2)" : "rgba(99,102,241,.2)"}` }}>
                                  {slot.source || "EXT"}
                                </span>
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
      </div>
    </div>
  );
}

const S = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: 0,
    background: "#f0f4f8",
    fontFamily: "'DM Sans', sans-serif",
    color: NAVY,
    overflow: "hidden",
  },
  body: {
    flex: 1,
    minHeight: 0,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
  },
  onboarding: {
    margin: "14px 28px 0",
    background: `linear-gradient(135deg, #0a2540, ${NAVY})`,
    border: "1px solid rgba(0,212,160,0.2)",
    borderRadius: 12,
    padding: "16px 20px",
    flexShrink: 0,
  },
  onboardingHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
    gap: 16,
  },
  onboardingTitle: { fontSize: 14, fontWeight: 700, color: "#fff" },
  onboardingSub: { fontSize: 11, color: "rgba(255,255,255,0.5)", marginTop: 2 },
  onboardingSteps: { display: "flex", gap: 8, flexWrap: "wrap" },
  onboardingStep: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 14px",
    borderRadius: 10,
    border: "1px solid",
    background: "rgba(255,255,255,0.04)",
    flex: "1 1 200px",
    minWidth: 0,
  },
  urgBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 24px",
    background: "#7f1d1d",
    borderBottom: "2px solid #991b1b",
    flexShrink: 0,
    gap: 12,
  },
  urgBarLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flex: 1,
  },
  urgCta: {
    padding: "7px 16px",
    borderRadius: 6,
    background: "#fff",
    border: "none",
    color: "#7f1d1d",
    fontSize: 11,
    fontWeight: 800,
    cursor: "pointer",
  },
  urgDismiss: {
    width: 26,
    height: 26,
    borderRadius: 5,
    background: "rgba(255,255,255,.12)",
    border: "1px solid rgba(255,255,255,.2)",
    color: "#fff",
    fontSize: 11,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  level2: {
    display: "flex",
    gap: 12,
    padding: "12px 24px 0",
    flexShrink: 0,
  },
  hero: {
    flex: 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: "linear-gradient(135deg,#0a2540,#0d1b2e)",
    border: "1px solid rgba(0,212,160,.15)",
    borderRadius: 12,
    padding: "16px 20px",
    position: "relative",
    overflow: "hidden",
  },
  heroGrid: {
    position: "absolute",
    inset: 0,
    backgroundImage: "linear-gradient(rgba(0,212,160,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,160,.04) 1px,transparent 1px)",
    backgroundSize: "26px 26px",
    pointerEvents: "none",
  },
  heroGlow: {
    position: "absolute",
    top: -20,
    right: -20,
    width: 140,
    height: 140,
    borderRadius: "50%",
    background: "radial-gradient(circle,rgba(0,212,160,.1),transparent 70%)",
    pointerEvents: "none",
  },
  heroGreeting: { fontSize: 18, fontWeight: 700, color: "#fff" },
  heroSub: { fontSize: 12, color: "rgba(255,255,255,.5)", marginTop: 3 },
  kpi: {
    padding: "9px 14px",
    borderRadius: 8,
    background: "rgba(0,0,0,.2)",
    border: "1px solid rgba(255,255,255,.07)",
    textAlign: "center",
    minWidth: 76,
    transition: "transform .2s",
  },
  actionsCol: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    width: 265,
    flexShrink: 0,
  },
  scanLabel: {
    fontSize: 9,
    color: "#94a3b8",
    letterSpacing: 1.8,
    fontWeight: 700,
  },
  actionCard: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: 12,
    borderRadius: 9,
    flex: 1,
  },
  actionCta: {
    padding: "6px 11px",
    borderRadius: 6,
    border: "none",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  level3: {
    display: "flex",
    gap: 12,
    flex: 1,
    minHeight: 0,
    padding: "10px 24px 18px",
    overflow: "hidden",
  },
  cardCalls: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 11,
    padding: "14px 16px",
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  cardAgenda: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 11,
    padding: "14px 16px",
    width: 295,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    flexShrink: 0,
  },
  cardHead: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 10,
  },
  cardTag: {
    fontSize: 9,
    color: "#94a3b8",
    letterSpacing: 1.8,
    fontWeight: 700,
    marginBottom: 2,
  },
  cardTitle: { fontSize: 14, fontWeight: 700, color: NAVY },
  ghost: {
    background: "none",
    border: "1px solid #e2e8f0",
    color: "#94a3b8",
    fontSize: 10,
    padding: "3px 9px",
    borderRadius: 5,
    cursor: "pointer",
    textDecoration: "none",
  },
  callRow: {
    display: "flex",
    alignItems: "flex-start",
    gap: 9,
    padding: "9px 11px",
    borderRadius: 8,
    cursor: "pointer",
  },
  agentChip: {
    fontSize: 9,
    padding: "1px 6px",
    borderRadius: 3,
    background: "rgba(0,212,160,.08)",
    color: TEALX,
    fontWeight: 700,
    border: "1px solid rgba(0,212,160,.2)",
  },
  statusTag: {
    fontSize: 9,
    fontWeight: 800,
    padding: "2px 7px",
    borderRadius: 4,
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  smallPrimary: {
    padding: "5px 11px",
    borderRadius: 5,
    border: "none",
    color: "#fff",
    fontSize: 10,
    fontWeight: 700,
    cursor: "pointer",
  },
  smallGhost: {
    background: "none",
    border: "1px solid #e2e8f0",
    color: "#94a3b8",
    fontSize: 10,
    padding: "3px 9px",
    borderRadius: 5,
    cursor: "pointer",
  },
  agSummary: {
    display: "grid",
    gridTemplateColumns: "repeat(3,1fr)",
    gap: 4,
    marginBottom: 8,
    padding: "6px 0",
    borderTop: "1px solid #f1f5f9",
    borderBottom: "1px solid #f1f5f9",
  },
};

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; }
  @keyframes ping { 0% { transform: scale(1); opacity: 0.4; } 80%,100% { transform: scale(2.5); opacity: 0; } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes growWidth { from { width: 0 !important; } }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  @keyframes slideDown { from { opacity: 0; transform: translateY(-100%); } to { opacity: 1; transform: translateY(0); } }
  .cr { animation: fadeUp .3s ease both; }
  .cr:hover { box-shadow: 0 3px 12px rgba(0,0,0,.07); transform: translateY(-1px); }
  .kp:hover { transform: translateY(-2px); }
  .xp { animation: fadeUp .2s ease both; }
  .bf { animation: growWidth 1.2s cubic-bezier(.4,0,.2,1) .3s both; }
  .urg-bar { animation: slideDown .35s cubic-bezier(.4,0,.2,1); }
`;
