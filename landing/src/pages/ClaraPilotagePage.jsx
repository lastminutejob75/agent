import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { assistantDisplayFromMe } from "../lib/assistantDisplay.js";
import ClaraRuleModulePanel from "../components/ClaraRuleModulePanel.jsx";
import ClaraControlTiles from "../components/ClaraControlTiles.jsx";

const CLARA_PHOTO = "/images/clara-headset.jpg";

const C = {
  navy: "#071A33",
  navy2: "#063A4A",
  teal: "#009CA4",
  teal2: "#00B8B0",
  border: "#DDE7EF",
  muted: "#66758B",
  red: "#EF4444",
  orange: "#F97316",
  green: "#16A34A",
  blue: "#2563EB",
  purple: "#7C3AED",
};

const soft = {
  red: "#FEF2F2",
  orange: "#FFF7ED",
  green: "#ECFDF3",
  blue: "#EFF6FF",
  purple: "#F5F3FF",
  teal: "#E8FAFA",
};

const border = {
  red: "#FECACA",
  orange: "#FED7AA",
  green: "#BBF7D0",
  blue: "#BFDBFE",
  purple: "#DDD6FE",
  teal: "#A7F3F0",
};

const MODES = [
  { id: "active", label: "Active", text: "Clara répond, qualifie et applique vos consignes.", color: C.green },
  { id: "messages", label: "Prise de messages", text: "Clara note les messages sans prendre d'action.", color: C.orange },
  { id: "pause", label: "En pause", text: "Clara est désactivée temporairement.", color: C.red },
];

const tiles = [
  ["Urgences", "warn", "red", "Definir la conduite a tenir et les redirections.", "Gerer les urgences"],
  ["Horaires exceptionnels", "clock", "blue", "Modifier les horaires, jours feries et fermetures.", "Modifier les horaires"],
  ["Absence programmee", "plane", "purple", "Organiser les reponses pendant votre absence.", "Gerer l'absence"],
  ["Bloquer des creneaux", "calendar", "orange", "Empecher Clara de proposer certains creneaux.", "Bloquer des creneaux"],
];

const actionRows = [
  ["08:45", "Ouverture anticipee", "Appliquee", "green"],
  ["09:10", "2 appels urgents traites", "OK", "green"],
  ["10:20", "SMS d'information envoye", "Envoye", "blue"],
  ["14:00", "Fermeture anticipee", "A venir", "orange"],
];

const DEFAULT_INSTRUCTION = "Informer les patients que le cabinet ferme exceptionnellement à 17h aujourd'hui.";
const DEFAULT_RULE_STATE = {
  enabled: true,
  notifyTeam: true,
  notifyPatients: false,
  note: "",
};

const MODULE_META = {
  urgences: {
    key: "urgences",
    title: "Urgences",
    description: "Definir la conduite a tenir et les redirections d'urgence.",
    tone: "red",
  },
  horaires_exceptionnels: {
    key: "horaires_exceptionnels",
    title: "Horaires exceptionnels",
    description: "Configurer les jours feries et les plages exceptionnelles.",
    tone: "blue",
  },
  absence_programmee: {
    key: "absence_programmee",
    title: "Absence programmee",
    description: "Planifier le comportement de Clara pendant votre absence.",
    tone: "purple",
  },
  bloquer_des_creneaux: {
    key: "bloquer_des_creneaux",
    title: "Bloquer des creneaux",
    description: "Empêcher Clara de proposer certains creneaux horaires.",
    tone: "orange",
  },
};

function tileKeyFromTitle(title) {
  return String(title || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function Icon({ name, size = 18, color = "currentColor" }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", style: { flexShrink: 0 } };
  const paths = {
    phone: <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.1 9.9a16 16 0 0 0 6 6l1.26-1.26a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z" />,
    calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></>,
    message: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    warn: <><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4M12 17h.01" /></>,
    clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
    plane: <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.4-.1.9.3 1.1L11 12l-2 3H6l-2 2 4-1 4-1 2 7.3c.2.4.7.6 1.1.4l.5-.3c.4-.2.5-.7.4-1.1z" />,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    star: <path d="M12 2l2.7 6.7 7.3.6-5.5 4.7 1.7 7-6.2-3.7L5.8 21l1.7-7L2 9.3l7.3-.6z" />,
  };
  return <svg {...common}>{paths[name] || paths.calendar}</svg>;
}

function Pill({ tone = "teal", children }) {
  return <span style={{ ...S.pill, color: C[tone] || C.teal, background: soft[tone] || soft.teal, borderColor: border[tone] || border.teal }}>{children}</span>;
}

function Btn({ children, icon, variant = "outline", onClick, style }) {
  const base = variant === "dark"
    ? S.btnDark
    : variant === "teal"
      ? S.btnTeal
      : variant === "green"
        ? S.btnGreen
        : variant === "orange"
          ? S.btnOrange
          : S.btnOutline;
  return (
    <button type="button" onClick={onClick} style={{ ...base, ...style }}>
      {icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}

function ClaraPhoto({ size = 98 }) {
  const [ok, setOk] = useState(true);
  return (
    <div style={{ ...S.claraPhoto, width: size, height: size }}>
      {ok ? (
        <img src={CLARA_PHOTO} alt="Clara" onError={() => setOk(false)} style={S.claraImg} />
      ) : (
        <div style={S.claraFallback}>C</div>
      )}
    </div>
  );
}

export default function ClaraPilotagePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState("active");
  const [tab, setTab] = useState("overview");
  const [instruction, setInstruction] = useState(DEFAULT_INSTRUCTION);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState([]);
  const [rulesConfig, setRulesConfig] = useState({});
  const [tenantProfile, setTenantProfile] = useState(null);
  const current = MODES.find((m) => m.id === mode) || MODES[0];
  const assistantDisplay = assistantDisplayFromMe(tenantProfile || {});

  const notify = (msg) => {
    setToast(msg);
    window.clearTimeout(notify.t);
    notify.t = window.setTimeout(() => setToast(""), 2200);
  };

  useEffect(() => {
    let cancelled = false;
    api.tenantMe()
      .then((me) => {
        if (cancelled) return;
        setTenantProfile(me);
        const modeFromApi = String(me?.clara_mode || "").trim();
        if (MODES.some((m) => m.id === modeFromApi)) setMode(modeFromApi);
        const instructionFromApi = String(me?.clara_temp_instruction || "").trim();
        if (instructionFromApi) setInstruction(instructionFromApi);
        const rawRules = me?.clara_rules_config;
        if (rawRules && typeof rawRules === "object" && !Array.isArray(rawRules)) {
          setRulesConfig(rawRules);
        } else if (typeof rawRules === "string" && rawRules.trim()) {
          try {
            const parsed = JSON.parse(rawRules);
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) setRulesConfig(parsed);
          } catch {
            setRulesConfig({});
          }
        }
        const rawHistory = me?.clara_action_history;
        if (Array.isArray(rawHistory)) {
          setHistory(rawHistory.slice(0, 20));
        } else if (typeof rawHistory === "string" && rawHistory.trim()) {
          try {
            const parsed = JSON.parse(rawHistory);
            if (Array.isArray(parsed)) setHistory(parsed.slice(0, 20));
          } catch {
            setHistory([]);
          }
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  async function persistClaraParams(payload) {
    setSaving(true);
    try {
      await api.tenantPatchParams(payload);
    } catch {
      notify("Sauvegarde impossible");
    } finally {
      setSaving(false);
    }
  }

  function appendHistory(label, tone = "blue") {
    const item = {
      at: new Date().toISOString(),
      label,
      status: "Effectué",
      tone,
    };
    const next = [item, ...history].slice(0, 20);
    setHistory(next);
    api.tenantPatchParams({ clara_action_history: next }).catch(() => {});
  }

  async function handleModeChange(nextMode) {
    setMode(nextMode);
    appendHistory(`Mode passé à ${MODES.find((m) => m.id === nextMode)?.label || nextMode}`, "green");
    await persistClaraParams({ clara_mode: nextMode });
  }

  async function handleApplyInstruction() {
    appendHistory("Consigne temporaire appliquée", "blue");
    notify("Consigne appliquée");
    await persistClaraParams({ clara_temp_instruction: instruction.trim() || DEFAULT_INSTRUCTION });
  }

  function getRuleStateFor(tileKey) {
    const existing = rulesConfig?.[tileKey];
    if (!existing || typeof existing !== "object") return { ...DEFAULT_RULE_STATE };
    return {
      enabled: existing.enabled !== false,
      notifyTeam: existing.notifyTeam !== false,
      notifyPatients: Boolean(existing.notifyPatients),
      note: String(existing.note || ""),
    };
  }

  function getRuleCompleteness(tileKey) {
    const state = getRuleStateFor(tileKey);
    const hasAnyNotification = state.notifyTeam || state.notifyPatients;
    const hasNote = String(state.note || "").trim().length >= 3;
    const configured = state.enabled && hasAnyNotification && hasNote;
    return configured
      ? { label: "Configurée", tone: "green" }
      : { label: "À compléter", tone: "orange" };
  }

  const rulesSummary = tiles.reduce((acc, [title]) => {
    const key = tileKeyFromTitle(title);
    if (getRuleCompleteness(key).label === "Configurée") acc.configured += 1;
    acc.total += 1;
    return acc;
  }, { configured: 0, total: 0 });
  const activeModuleKey = String(searchParams.get("module") || "").trim();
  const activeModule = MODULE_META[activeModuleKey] || null;
  const activeRuleState = activeModule ? getRuleStateFor(activeModule.key) : DEFAULT_RULE_STATE;

  useEffect(() => {
    try {
      const payload = { configured: rulesSummary.configured, total: rulesSummary.total };
      window.localStorage.setItem("uwi_clara_rules_summary", JSON.stringify(payload));
      window.dispatchEvent(new CustomEvent("uwi:clara-rules-summary", { detail: payload }));
    } catch {
      // no-op
    }
  }, [rulesSummary.configured, rulesSummary.total]);

  function openModule(moduleKey) {
    const next = new URLSearchParams(searchParams);
    next.set("module", moduleKey);
    setSearchParams(next, { replace: false });
    setTab("rules");
  }

  function closeModule() {
    const next = new URLSearchParams(searchParams);
    next.delete("module");
    setSearchParams(next, { replace: false });
  }

  function updateActiveModuleRule(field, value) {
    if (!activeModule) return;
    setRulesConfig((prev) => {
      const currentRule = prev?.[activeModule.key] && typeof prev[activeModule.key] === "object"
        ? prev[activeModule.key]
        : DEFAULT_RULE_STATE;
      return {
        ...prev,
        [activeModule.key]: {
          enabled: currentRule.enabled !== false,
          notifyTeam: currentRule.notifyTeam !== false,
          notifyPatients: Boolean(currentRule.notifyPatients),
          note: String(currentRule.note || ""),
          [field]: value,
        },
      };
    });
  }

  async function saveActiveModule() {
    if (!activeModule) return;
    const updatedRules = {
      ...rulesConfig,
      [activeModule.key]: {
        ...activeRuleState,
      },
    };
    setRulesConfig(updatedRules);
    appendHistory(`${activeModule.title} mis à jour`, activeModule.tone || "blue");
    notify(`${activeModule.title} mis à jour`);
    await persistClaraParams({
      clara_rules_config: updatedRules,
      clara_last_tile: activeModule.title,
      clara_last_tile_updated_at: new Date().toISOString(),
    });
  }

  return (
    <div className="uwi-clara-page" style={S.page}>
      <button type="button" onClick={() => navigate("/app")} style={S.backBtn}>← Retour à l'accueil</button>
      {loading || saving ? <div style={S.syncLine}>{saving ? "Synchronisation..." : "Chargement..."}</div> : null}

      <section className="uwi-clara-hero" style={S.hero}>
        <div className="uwi-clara-hero-left" style={S.heroLeft}>
          <ClaraPhoto />
          <div>
            <div style={S.heroTitleRow}>
              <h2 style={S.heroTitle}>{assistantDisplay.assistantName}</h2>
              <Pill tone={assistantDisplay.statusTone}>{assistantDisplay.statusLabel}</Pill>
            </div>
            <p style={S.meta}>
              <Icon name="phone" size={14} />
              {assistantDisplay.displayPhone} · <Icon name="message" size={14} />
              {assistantDisplay.displayEmail}
            </p>
          </div>
        </div>
        <div style={S.modeSummary}><b>{current.label}</b><span>{current.text}</span></div>
      </section>

      <section style={S.panel}>
        <div className="uwi-clara-tabs" style={S.tabs}>
          {[["overview", "Vue d'ensemble"], ["rules", "Règles"], ["history", "Historique"]].map(([id, label]) => (
            <button key={id} type="button" onClick={() => setTab(id)} style={{ ...S.tab, ...(tab === id ? S.tabActive : {}) }}>{label}</button>
          ))}
        </div>
        <div style={S.rulesCounterRow}>
          <Pill tone={rulesSummary.configured === rulesSummary.total ? "green" : "orange"}>
            {rulesSummary.configured}/{rulesSummary.total} règles configurées
          </Pill>
          <span style={S.rulesCounterHint}>
            Completez chaque tuile pour un pilotage Clara optimal.
          </span>
        </div>
        <div className="uwi-clara-quick-actions" style={S.quickActions}>
          <Btn variant="dark" icon="star" onClick={() => { appendHistory("Consultation des consignes actives", "blue"); notify("Consignes actives"); }}>Voir les consignes actives</Btn>
          <Btn variant="orange" icon="edit" onClick={() => { appendHistory("Préparation d'une nouvelle règle", "orange"); notify("Nouvelle règle"); }}>Ajouter une règle</Btn>
          <Btn variant="green" icon="plus" onClick={() => { appendHistory("Partage d'une information cabinet", "green"); notify("Information cabinet"); }}>Partager une information cabinet</Btn>
        </div>
      </section>

      {tab === "history" ? (
        <section style={S.historyCard}>
          <h3 style={S.h3}>Historique récent</h3>
          {!history.length ? <p style={{ margin: 0, color: C.muted }}>Aucune action enregistrée pour le moment.</p> : null}
          {history.map((h, idx) => {
            const dt = new Date(h.at || "");
            const label = String(h.label || "Action");
            const at = Number.isNaN(dt.getTime())
              ? "recent"
              : dt.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
            return (
              <div key={`${label}-${idx}`} className="uwi-clara-history-row" style={S.historyRow}>
                <span>{at}</span>
                <b>{label}</b>
                <Pill tone={h.tone || "blue"}>{h.status || "Effectué"}</Pill>
              </div>
            );
          })}
        </section>
      ) : null}

      <div className="uwi-clara-top-grid" style={S.topGrid}>
        <section style={S.modeCard}>
          <h3 style={S.h3}>Mode de fonctionnement</h3>
          <p style={{ margin: "0 0 10px", color: C.muted }}>{current.text}</p>
          <div className="uwi-clara-segmented" style={S.segmented}>
            {MODES.map((m) => (
              <button key={m.id} type="button" onClick={() => handleModeChange(m.id)} style={mode === m.id ? S.segActive : S.seg}>{m.label}</button>
            ))}
          </div>
          <label style={S.label}>Consigne temporaire</label>
          <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} style={S.textarea} />
          <div style={S.formActions}>
            <Btn onClick={() => setInstruction("")}>Réinitialiser</Btn>
            <Btn variant="teal" onClick={handleApplyInstruction}>Appliquer</Btn>
          </div>
        </section>

        <section style={S.card}>
          <h3 style={S.h3}>Actions du jour</h3>
          {actionRows.map(([time, title, status, tone]) => (
            <button key={`${time}-${title}`} type="button" onClick={() => { appendHistory(title, tone); notify(title); }} style={S.actionRow}>
              <b>{time}</b>
              <span>{title}</span>
              <Pill tone={tone}>{status}</Pill>
            </button>
          ))}
        </section>
      </div>

      <ClaraControlTiles
        tiles={tiles}
        onOpenModule={openModule}
        getRuleCompleteness={getRuleCompleteness}
        styles={S}
        colors={C}
        soft={soft}
        borders={border}
        renderIcon={(name) => <Icon name={name} size={22} />}
        PillComponent={Pill}
        BtnComponent={Btn}
        tileKeyFromTitle={tileKeyFromTitle}
      />

      <ClaraRuleModulePanel
        activeModule={activeModule}
        activeRuleState={activeRuleState}
        getRuleCompleteness={getRuleCompleteness}
        onToggle={updateActiveModuleRule}
        onChangeNote={(text) => updateActiveModuleRule("note", text)}
        onClose={closeModule}
        onSave={saveActiveModule}
        styles={S}
        colors={C}
        PillComponent={Pill}
        BtnComponent={Btn}
      />

      <div className="uwi-clara-bottom-grid" style={S.bottomGrid}>
        <section style={S.darkCard}>
          <h3 style={S.darkTitle}><Icon name="star" />Consignes actives</h3>
          <p style={S.darkText}>Clara répond selon les consignes en vigueur. Deux urgences actives avec rappel automatique. Horaires modifiés : 8h30 à 17h00.</p>
          <small style={S.darkFooter}>Mis à jour · Aujourd'hui à 14:32</small>
        </section>
        <section style={S.notesDark}>
          <h3 style={S.darkTitle}><Icon name="edit" />Notes de l'équipe</h3>
          <p style={{ color: "rgba(255,255,255,.78)" }}>Partagez une information avec le cabinet.</p>
          <input style={S.inputDark} placeholder="Ajouter une note pour l'équipe..." />
          <Btn variant="teal" onClick={() => notify("Note enregistrée")}>Enregistrer</Btn>
        </section>
      </div>

      {toast ? <div style={S.toast}>✓ {toast}</div> : null}
      <style>{CSS}</style>
    </div>
  );
}

const S = {
  page: { maxWidth: 1280, margin: "0 auto", padding: "18px 24px 30px", color: C.navy },
  backBtn: { border: 0, background: "transparent", color: C.teal, fontWeight: 800, cursor: "pointer", marginBottom: 8, fontFamily: "inherit" },
  syncLine: { marginBottom: 8, color: C.muted, fontSize: 12, fontWeight: 700 },
  hero: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 24, padding: 24, display: "flex", justifyContent: "space-between", gap: 18, boxShadow: "0 18px 44px rgba(7,26,51,.07)", marginBottom: 14 },
  heroLeft: { display: "flex", alignItems: "center", gap: 20 },
  claraPhoto: { borderRadius: 999, border: `3px solid ${C.teal}`, overflow: "hidden", boxShadow: "0 14px 30px rgba(0,156,164,.18)" },
  claraImg: { width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" },
  claraFallback: { width: "100%", height: "100%", background: "linear-gradient(135deg,#2EE6D0,#009CA4,#071A33)", color: "#fff", display: "grid", placeItems: "center", fontSize: 34, fontWeight: 800 },
  heroTitleRow: { display: "flex", alignItems: "center", gap: 12, marginBottom: 5 },
  heroTitle: { margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: "-.03em" },
  meta: { margin: 0, display: "flex", alignItems: "center", gap: 7, color: C.muted, fontWeight: 600, fontSize: 13 },
  modeSummary: { maxWidth: 360, padding: 16, borderRadius: 14, background: "linear-gradient(135deg,#F8FCFD,#E8FAFA)", border: `1px solid ${C.border}`, display: "flex", flexDirection: "column", gap: 4 },
  panel: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 20, boxShadow: "0 10px 28px rgba(7,26,51,.055)", overflow: "hidden", marginBottom: 14 },
  rulesCounterRow: { display: "flex", alignItems: "center", gap: 10, padding: "10px 14px 0", flexWrap: "wrap" },
  rulesCounterHint: { fontSize: 12, color: C.muted, fontWeight: 600 },
  historyCard: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 16, padding: 18, marginBottom: 14, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  historyRow: { display: "grid", gridTemplateColumns: "130px 1fr auto", alignItems: "center", gap: 10, padding: "10px 0", borderTop: `1px solid ${C.border}` },
  tabs: { display: "flex", height: 52, borderBottom: `1px solid ${C.border}` },
  tab: { padding: "0 30px", border: 0, background: "transparent", fontWeight: 800, cursor: "pointer", color: C.navy, fontFamily: "inherit" },
  tabActive: { color: C.teal, borderBottom: `3px solid ${C.teal}` },
  quickActions: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 14, padding: 14 },
  topGrid: { display: "grid", gridTemplateColumns: "1fr .9fr", gap: 18, marginBottom: 14 },
  modeCard: { background: "#fff", border: `1px solid ${C.border}`, borderLeft: `4px solid ${C.teal}`, borderRadius: 20, padding: 22, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  h3: { margin: "0 0 8px", fontSize: 22, fontWeight: 800 },
  segmented: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, margin: "16px 0" },
  seg: { height: 40, borderRadius: 10, border: `1px solid ${C.border}`, background: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  segActive: { height: 40, borderRadius: 10, border: 0, background: "linear-gradient(135deg,#071A33,#063A4A)", color: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  label: { fontSize: 13, fontWeight: 700 },
  textarea: { width: "100%", minHeight: 76, borderRadius: 12, border: `1px solid ${C.border}`, padding: 13, boxSizing: "border-box", marginTop: 8, fontFamily: "inherit" },
  formActions: { display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 10 },
  card: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 20, padding: 22, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  actionRow: { width: "100%", display: "grid", gridTemplateColumns: "52px 1fr auto", gap: 10, alignItems: "center", border: 0, borderTop: `1px solid ${C.border}`, background: "transparent", padding: "12px 0", textAlign: "left", cursor: "pointer", fontFamily: "inherit" },
  tileGrid: { display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 14, marginBottom: 14 },
  tile: { background: "#fff", border: `1px solid ${C.border}`, borderTop: "4px solid", borderRadius: 16, padding: 18, display: "grid", gridTemplateColumns: "54px 1fr", gap: 14, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  tileHead: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 6, flexWrap: "wrap" },
  moduleCard: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 16, padding: 18, marginBottom: 14, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  moduleCardHead: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 },
  moduleChecks: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 10 },
  moduleActions: { marginTop: 10, display: "flex", justifyContent: "flex-end", gap: 10, flexWrap: "wrap" },
  bottomGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 },
  darkCard: { borderRadius: 22, background: "linear-gradient(135deg,#071A33 0%,#063A4A 52%,#009CA4 135%)", color: "#fff", padding: 26, boxShadow: "0 20px 44px rgba(7,26,51,.24)" },
  notesDark: { borderRadius: 22, background: "linear-gradient(135deg,#08233F,#0B4D5B)", color: "#fff", padding: 26, boxShadow: "0 20px 44px rgba(7,26,51,.20)" },
  darkTitle: { margin: "0 0 8px", display: "inline-flex", alignItems: "center", gap: 8, fontSize: 21, fontWeight: 800 },
  darkText: { margin: 0, lineHeight: 1.5, color: "rgba(255,255,255,.92)" },
  darkFooter: { display: "block", marginTop: 12, color: "rgba(255,255,255,.75)" },
  inputDark: { width: "100%", height: 50, borderRadius: 12, border: 0, padding: "0 14px", boxSizing: "border-box", margin: "10px 0", fontFamily: "inherit" },
  check: { display: "flex", gap: 10, margin: "10px 0", fontWeight: 700, color: C.navy },
  toast: { position: "fixed", left: "50%", bottom: 24, transform: "translateX(-50%)", background: C.navy, color: "#fff", padding: "13px 24px", borderRadius: 999, fontWeight: 800, boxShadow: "0 18px 44px rgba(7,26,51,.28)", zIndex: 40 },
  pill: { display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid", borderRadius: 9, padding: "6px 10px", fontSize: 12, fontWeight: 800, whiteSpace: "nowrap" },
  btnDark: { height: 44, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: 0, borderRadius: 12, padding: "0 17px", background: "linear-gradient(135deg,#071A33,#063A4A)", color: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnTeal: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: 0, borderRadius: 12, padding: "0 17px", background: "linear-gradient(135deg,#009CA4,#00B8B0)", color: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnOutline: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: `1.5px solid ${C.border}`, borderRadius: 12, padding: "0 17px", background: "#fff", color: C.navy, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnOrange: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: "1.5px solid #FED7AA", borderRadius: 12, padding: "0 17px", background: "#fff", color: C.orange, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnGreen: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: "1.5px solid #BBF7D0", borderRadius: 12, padding: "0 17px", background: "#fff", color: C.green, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
};

const CSS = `
  @media (max-width: 1180px) {
    .uwi-clara-top-grid,
    .uwi-clara-bottom-grid,
    .uwi-clara-tile-grid { grid-template-columns: 1fr !important; }
    .uwi-clara-module-checks { grid-template-columns: 1fr !important; }
  }
  @media (max-width: 760px) {
    .uwi-clara-page { padding: 14px 12px 20px !important; }
    .uwi-clara-hero { flex-direction: column !important; align-items: flex-start !important; padding: 16px !important; }
    .uwi-clara-hero-left { flex-direction: column !important; align-items: flex-start !important; gap: 14px !important; }
    .uwi-clara-quick-actions,
    .uwi-clara-segmented { grid-template-columns: 1fr !important; }
    .uwi-clara-tabs { overflow-x: auto !important; }
    .uwi-clara-tabs button { flex: 0 0 auto !important; padding: 0 18px !important; }
    .uwi-clara-history-row { grid-template-columns: 1fr !important; gap: 6px !important; }
    .uwi-clara-history-row > span { font-size: 12px !important; }
  }
`;
