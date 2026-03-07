import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearTenantToken, isTenantUnauthorized } from "../lib/api.js";

const TOTAL = 8;
const TEAL = "#00d4a0";

const SPECIALTIES = [
  { key: "medecin_generaliste", label: "Médecin généraliste", icon: "🩺" },
  { key: "dentiste", label: "Dentiste", icon: "🦷" },
  { key: "specialiste", label: "Spécialiste", icon: "🧠" },
  { key: "clinique", label: "Clinique", icon: "🏥" },
  { key: "kine", label: "Kiné / Ostéo", icon: "💆" },
  { key: "ophtalmo", label: "Ophtalmo", icon: "👁️" },
  { key: "orthopediste", label: "Orthopédiste", icon: "🦴" },
  { key: "autre", label: "Autre", icon: "✨" },
];

const AGENTS = [
  { key: "sophie", label: "Sophie", sub: "Douce · Pro", icon: "👩‍⚕️", gradient: "linear-gradient(135deg,#00d4a0,#60a5fa)" },
  { key: "camille", label: "Camille", sub: "Chaleureuse", icon: "👩", gradient: "linear-gradient(135deg,#f59e0b,#ec4899)" },
  { key: "lea", label: "Léa", sub: "Dynamique", icon: "👩‍💼", gradient: "linear-gradient(135deg,#8b5cf6,#ec4899)" },
  { key: "marie", label: "Marie", sub: "Posée", icon: "👩‍🦱", gradient: "linear-gradient(135deg,#ef4444,#f59e0b)" },
  { key: "julie", label: "Julie", sub: "Énergique", icon: "👩‍🦰", gradient: "linear-gradient(135deg,#06b6d4,#3b82f6)" },
  { key: "thomas", label: "Thomas", sub: "Professionnel", icon: "👨‍⚕️", gradient: "linear-gradient(135deg,#1e40af,#3b82f6)" },
  { key: "lucas", label: "Lucas", sub: "Chaleureux", icon: "👨", gradient: "linear-gradient(135deg,#065f46,#00d4a0)" },
  { key: "antoine", label: "Antoine", sub: "Rassurant", icon: "👨‍💼", gradient: "linear-gradient(135deg,#7c3aed,#8b5cf6)" },
  { key: "pierre", label: "Pierre", sub: "Posé", icon: "👨‍🦱", gradient: "linear-gradient(135deg,#b45309,#f59e0b)" },
  { key: "nicolas", label: "Nicolas", sub: "Autoritaire", icon: "👨‍🦳", gradient: "linear-gradient(135deg,#9f1239,#ef4444)" },
];

const AGENDA_OPTIONS = [
  { key: "google", label: "Google Calendar", sub: "Connexion automatique, synchronisation en temps réel", icon: "📅", tag: "Recommandé", tagStyle: { background: "rgba(0,212,160,0.1)", color: TEAL, border: "1px solid rgba(0,212,160,0.2)" } },
  { key: "doctolib", label: "Doctolib", sub: "Notre équipe vous contacte pour la configuration", icon: "🏥", tag: "Bientôt", tagStyle: { background: "rgba(99,102,241,0.1)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.2)" } },
  { key: "maiia", label: "Maiia / Autre", sub: "Notre équipe vous contacte pour la configuration", icon: "📋", tag: "Bientôt", tagStyle: { background: "rgba(99,102,241,0.1)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.2)" } },
  { key: "none", label: "Sans agenda pour l'instant", sub: "L'assistante gère les rendez-vous sans connexion agenda", icon: "⏭️" },
];

const PLAN_OPTIONS = [
  {
    key: "starter",
    name: "Starter",
    price: "99€",
    desc: "Idéal pour un cabinet solo ou une petite structure.",
    features: ["500 min / mois incluses", "1 numéro dédié", "1 assistante IA", "Prise de RDV 24h/24"],
  },
  {
    key: "growth",
    name: "Growth",
    price: "149€",
    desc: "Pour les cabinets avec plus de volume et de suivi.",
    badge: "POPULAIRE",
    features: ["1000 min / mois incluses", "1 numéro dédié", "FAQ personnalisée", "Rapports avancés"],
  },
  {
    key: "pro",
    name: "Pro",
    price: "199€",
    desc: "Pour les structures à forte activité ou multi-praticiens.",
    features: ["2000 min / mois incluses", "Assistantes multiples", "Priorité support", "Configuration avancée"],
  },
];

const DAYS = [
  { value: 0, label: "Lundi" },
  { value: 1, label: "Mardi" },
  { value: 2, label: "Mercredi" },
  { value: 3, label: "Jeudi" },
  { value: 4, label: "Vendredi" },
  { value: 5, label: "Samedi" },
  { value: 6, label: "Dimanche" },
];

function normalizeAssistantKey(value) {
  const raw = (value || "").toString().trim().toLowerCase();
  if (!raw) return "sophie";
  const direct = AGENTS.find((item) => item.key === raw);
  if (direct) return direct.key;
  const byLabel = AGENTS.find((item) => item.label.toLowerCase() === raw);
  return byLabel?.key || "sophie";
}

function hh(hour) {
  return `${String(hour).padStart(2, "0")}h`;
}

function dayHoursText(form, day) {
  if (!form.booking_days.includes(day.value)) return "Fermé";
  return `${hh(form.booking_start_hour)} – ${hh(form.booking_end_hour)}`;
}

function stepTitle(step, tenantName) {
  const safeName = tenantName || "Docteur";
  switch (step) {
    case 1:
      return (
        <>
          Bonjour,<br />
          <em>{safeName}</em> 👋
        </>
      );
    case 2:
      return <>Quelle est votre <em>spécialité</em> ?</>;
    case 3:
      return <>Où êtes-vous <em>situé</em> ?</>;
    case 4:
      return <>Vos <em>horaires</em> d&apos;ouverture</>;
    case 5:
      return <>Qui répondra à vos <em>patients</em> ?</>;
    case 6:
      return <>Quel logiciel utilisez-vous pour vos <em>rendez-vous</em> ?</>;
    case 7:
      return <>Choisissez votre <em>formule</em></>;
    default:
      return <>Votre assistant est prêt !</>;
  }
}

function stepEyebrow(step) {
  return ["Bienvenue", "Votre activité", "Votre cabinet", "Disponibilités", "Votre assistante", "Agenda", "Abonnement", "Succès"][step - 1];
}

export default function AppFirstOnboarding() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState(1);
  const [me, setMe] = useState(null);
  const [form, setForm] = useState({
    tenant_name: "",
    contact_email: "",
    phone_number: "",
    specialty_key: "medecin_generaliste",
    specialty_label: "Médecin généraliste",
    address_line1: "",
    postal_code: "",
    city: "",
    booking_days: [0, 1, 2, 3, 4],
    booking_start_hour: 9,
    booking_end_hour: 18,
    booking_duration_minutes: 15,
    booking_buffer_minutes: 0,
    assistant_name: "sophie",
    agenda_software: "google",
    plan_key: "growth",
  });

  useEffect(() => {
    Promise.all([api.tenantMe(), api.tenantGetHoraires().catch(() => null)])
      .then(([tenant, horaires]) => {
        if (tenant?.client_onboarding_completed) {
          navigate("/app", { replace: true });
          return;
        }
        setMe(tenant);
        setForm({
          tenant_name: tenant?.tenant_name || "",
          contact_email: tenant?.contact_email || tenant?.email || "",
          phone_number: tenant?.phone_number || "",
          specialty_key: tenant?.sector || "medecin_generaliste",
          specialty_label:
            tenant?.specialty_label ||
            SPECIALTIES.find((item) => item.key === (tenant?.sector || "medecin_generaliste"))?.label ||
            "Médecin généraliste",
          address_line1: tenant?.address_line1 || "",
          postal_code: tenant?.postal_code || "",
          city: tenant?.city || "",
          booking_days: horaires?.booking_days || [0, 1, 2, 3, 4],
          booking_start_hour: horaires?.booking_start_hour || 9,
          booking_end_hour: horaires?.booking_end_hour || 18,
          booking_duration_minutes: horaires?.booking_duration_minutes || 15,
          booking_buffer_minutes: horaires?.booking_buffer_minutes || 0,
          assistant_name: normalizeAssistantKey(tenant?.assistant_name),
          agenda_software: tenant?.agenda_software || (tenant?.calendar_provider === "google" ? "google" : "none"),
          plan_key: tenant?.plan_key || "growth",
        });
      })
      .catch((e) => {
        if (isTenantUnauthorized(e)) {
          clearTenantToken();
          window.location.href = "/";
          return;
        }
        setError(e?.message || "Chargement impossible");
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (loading || saving) return;
      if (e.key === "Enter") {
        e.preventDefault();
        handleNext();
      }
      if (e.key === "ArrowLeft" || e.key === "Escape") {
        e.preventDefault();
        if (step > 1 && step < 8) setStep((prev) => prev - 1);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [loading, saving, step, form]);

  const selectedAgent = useMemo(
    () => AGENTS.find((item) => item.key === form.assistant_name) || AGENTS[0],
    [form.assistant_name],
  );

  const canContinue = useMemo(() => {
    if (step === 1) return form.tenant_name && form.contact_email && form.phone_number;
    if (step === 2) return form.specialty_key;
    if (step === 3) return form.address_line1 && form.postal_code && form.city;
    if (step === 4) return form.booking_days.length > 0 && form.booking_end_hour > form.booking_start_hour;
    if (step === 5) return form.assistant_name;
    if (step === 6) return form.agenda_software;
    if (step === 7) return form.plan_key;
    return true;
  }, [form, step]);

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleDay(day) {
    setForm((prev) => {
      const exists = prev.booking_days.includes(day);
      const nextDays = exists ? prev.booking_days.filter((item) => item !== day) : [...prev.booking_days, day].sort((a, b) => a - b);
      return { ...prev, booking_days: nextDays };
    });
  }

  async function handleSubmit() {
    setSaving(true);
    setError("");
    try {
      await api.tenantPatchParams({
        tenant_name: form.tenant_name,
        contact_email: form.contact_email,
        phone_number: form.phone_number,
        sector: form.specialty_key,
        specialty_label: form.specialty_label,
        address_line1: form.address_line1,
        postal_code: form.postal_code,
        city: form.city,
        assistant_name: form.assistant_name,
        agenda_software: form.agenda_software,
        plan_key: form.plan_key,
        client_onboarding_completed: true,
      });
      await api.tenantUpdateHoraires({
        booking_days: form.booking_days,
        booking_start_hour: Number(form.booking_start_hour),
        booking_end_hour: Number(form.booking_end_hour),
        booking_duration_minutes: Number(form.booking_duration_minutes),
        booking_buffer_minutes: Number(form.booking_buffer_minutes),
      });
      if (form.agenda_software === "doctolib") {
        await api.agendaContactRequest("doctolib", "").catch(() => null);
      } else if (form.agenda_software === "maiia") {
        await api.agendaContactRequest("autre", "Maiia").catch(() => null);
      }
      if (form.agenda_software === "none") {
        await api.agendaActivateNone().catch(() => null);
      }
      setMe((prev) => ({
        ...(prev || {}),
        tenant_name: form.tenant_name,
        contact_email: form.contact_email,
        phone_number: form.phone_number,
        sector: form.specialty_key,
        specialty_label: form.specialty_label,
        address_line1: form.address_line1,
        postal_code: form.postal_code,
        city: form.city,
        assistant_name: form.assistant_name,
        agenda_software: form.agenda_software,
        plan_key: form.plan_key,
        client_onboarding_completed: true,
      }));
      setStep(8);
    } catch (e) {
      setError(e?.message || "Impossible d'enregistrer l'onboarding");
    } finally {
      setSaving(false);
    }
  }

  function handleNext() {
    if (step === 7) {
      handleSubmit();
      return;
    }
    if (step === 8) {
      navigate("/app", { replace: true });
      return;
    }
    if (canContinue) setStep((prev) => Math.min(TOTAL, prev + 1));
  }

  function handleBack() {
    if (step > 1 && step < 8) setStep((prev) => prev - 1);
  }

  if (loading) {
    return (
      <div className="ufi-shell-loader" style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#0a1628", color: "#fff", fontFamily: "'DM Sans', sans-serif" }}>
        Chargement de votre onboarding...
      </div>
    );
  }

  if (error && !me) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#0a1628", color: "#fff", fontFamily: "'DM Sans', sans-serif", padding: 24 }}>
        <div style={{ maxWidth: 520, width: "100%", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16, padding: 24, background: "rgba(255,255,255,0.03)" }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Chargement impossible</div>
          <div style={{ color: "rgba(255,255,255,0.6)", marginBottom: 16 }}>{error}</div>
          <button className="btn-next" onClick={() => window.location.reload()}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ufi-root">
      <style>{CSS}</style>
      <div className="shell">
        <div className="topbar">
          <div className="logo">UWI</div>
          <div className="step-label">{`Étape ${step} sur ${TOTAL}`}</div>
        </div>

        <div className="progress-wrap">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${(step / TOTAL) * 100}%` }} />
          </div>
          <div className="step-dots">
            {Array.from({ length: TOTAL }).map((_, idx) => {
              const value = idx + 1;
              const cls = value < step ? "dot done" : value === step ? "dot active" : "dot";
              return <div key={value} className={cls} onClick={() => setStep(value)} />;
            })}
          </div>
        </div>

        <div className="content">
          {step !== 8 && (
            <div className="screen active">
              <div className="screen-eyebrow">{stepEyebrow(step)}</div>
              <div className="screen-title">{stepTitle(step, form.tenant_name)}</div>
              {step === 1 && (
                <>
                  <div className="screen-sub">
                    UWI a déjà préparé votre espace. Confirmons ensemble quelques informations pour finaliser votre assistant vocal.
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div className="confirm-chip">
                      <span className="confirm-chip-icon">✉️</span>
                      <span>{form.contact_email || "Email à renseigner"}</span>
                    </div>
                    <div className="confirm-chip">
                      <span className="confirm-chip-icon">📞</span>
                      <span>{form.phone_number || "Téléphone à renseigner"}</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div className="input-group">
                      <div className="input-label">NOM DU CABINET</div>
                      <input className="input-field" value={form.tenant_name} onChange={(e) => setField("tenant_name", e.target.value)} placeholder="Cabinet Médical du Centre" />
                    </div>
                    <div className="input-row">
                      <div className="input-group">
                        <div className="input-label">EMAIL DE CONTACT</div>
                        <input className="input-field" value={form.contact_email} onChange={(e) => setField("contact_email", e.target.value)} placeholder="contact@cabinet.fr" />
                      </div>
                      <div className="input-group">
                        <div className="input-label">TÉLÉPHONE CABINET</div>
                        <input className="input-field" value={form.phone_number} onChange={(e) => setField("phone_number", e.target.value)} placeholder="01 23 45 67 89" />
                      </div>
                    </div>
                  </div>
                </>
              )}

              {step === 2 && (
                <div className="tiles tiles-auto">
                  {SPECIALTIES.map((item) => (
                    <div
                      key={item.key}
                      className={`tile ${form.specialty_key === item.key ? "selected" : ""}`}
                      onClick={() => {
                        setField("specialty_key", item.key);
                        setField("specialty_label", item.label);
                      }}
                    >
                      <div className="tile-icon">{item.icon}</div>
                      <div className="tile-label">{item.label}</div>
                    </div>
                  ))}
                </div>
              )}

              {step === 3 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div className="screen-sub">Permet à votre assistante de donner l&apos;adresse aux patients.</div>
                  <div className="input-group">
                    <div className="input-label">ADRESSE</div>
                    <input className="input-field" value={form.address_line1} onChange={(e) => setField("address_line1", e.target.value)} placeholder="12 rue de la Paix" />
                  </div>
                  <div className="input-row">
                    <div className="input-group">
                      <div className="input-label">CODE POSTAL</div>
                      <input className="input-field" value={form.postal_code} onChange={(e) => setField("postal_code", e.target.value)} placeholder="75001" />
                    </div>
                    <div className="input-group">
                      <div className="input-label">VILLE</div>
                      <input className="input-field" value={form.city} onChange={(e) => setField("city", e.target.value)} placeholder="Paris" />
                    </div>
                  </div>
                </div>
              )}

              {step === 4 && (
                <>
                  <div className="screen-sub">Quand vos patients peuvent-ils appeler pour prendre rendez-vous ?</div>
                  <div className="hours-grid">
                    {DAYS.map((day) => {
                      const active = form.booking_days.includes(day.value);
                      return (
                        <div key={day.value} className="day-row">
                          <div className={`day-toggle ${active ? "on" : ""}`} onClick={() => toggleDay(day.value)} />
                          <div className="day-name" style={{ color: active ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.3)" }}>{day.label}</div>
                          <div className="day-hours">{dayHoursText(form, day)}</div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="input-row">
                    <div className="input-group">
                      <div className="input-label">OUVERTURE</div>
                      <select className="input-field" value={form.booking_start_hour} onChange={(e) => setField("booking_start_hour", Number(e.target.value))}>
                        {Array.from({ length: 15 }).map((_, idx) => {
                          const hour = idx + 6;
                          return <option key={hour} value={hour}>{hh(hour)}</option>;
                        })}
                      </select>
                    </div>
                    <div className="input-group">
                      <div className="input-label">FERMETURE</div>
                      <select className="input-field" value={form.booking_end_hour} onChange={(e) => setField("booking_end_hour", Number(e.target.value))}>
                        {Array.from({ length: 15 }).map((_, idx) => {
                          const hour = idx + 8;
                          return <option key={hour} value={hour}>{hh(hour)}</option>;
                        })}
                      </select>
                    </div>
                  </div>
                  <div className="input-row">
                    <div className="input-group">
                      <div className="input-label">DURÉE RDV</div>
                      <select className="input-field" value={form.booking_duration_minutes} onChange={(e) => setField("booking_duration_minutes", Number(e.target.value))}>
                        {[15, 20, 30, 45, 60].map((value) => <option key={value} value={value}>{value} min</option>)}
                      </select>
                    </div>
                    <div className="input-group">
                      <div className="input-label">BUFFER</div>
                      <select className="input-field" value={form.booking_buffer_minutes} onChange={(e) => setField("booking_buffer_minutes", Number(e.target.value))}>
                        {[0, 5, 10, 15].map((value) => <option key={value} value={value}>{value} min</option>)}
                      </select>
                    </div>
                  </div>
                </>
              )}

              {step === 5 && (
                <>
                  <div className="screen-sub">Choisissez la voix qui représentera votre cabinet 24h/24.</div>
                  <div className="agent-grid">
                    {AGENTS.map((agent) => (
                      <div key={agent.key} className={`agent-card ${form.assistant_name === agent.key ? "selected" : ""}`} onClick={() => setField("assistant_name", agent.key)}>
                        <div className="agent-avatar" style={{ background: agent.gradient }}>
                          {agent.icon}
                          <div className="agent-check">✓</div>
                        </div>
                        <div className="agent-name">{agent.label}</div>
                        <div className="agent-gender">{agent.sub}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {step === 6 && (
                <>
                  <div className="screen-sub">Notre équipe se charge de la connexion technique si nécessaire.</div>
                  <div className="agenda-opts">
                    {AGENDA_OPTIONS.map((item) => (
                      <div key={item.key} className={`agenda-opt ${form.agenda_software === item.key ? "selected" : ""}`} onClick={() => setField("agenda_software", item.key)}>
                        <div className="agenda-opt-icon">{item.icon}</div>
                        <div>
                          <div className="agenda-opt-name">{item.label}</div>
                          <div className="agenda-opt-sub">{item.sub}</div>
                        </div>
                        {item.tag ? <div className="agenda-opt-tag" style={item.tagStyle}>{item.tag}</div> : null}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {step === 7 && (
                <>
                  <div className="screen-sub">30 jours d&apos;essai gratuit, sans engagement. Résiliable à tout moment.</div>
                  <div className="plan-grid">
                    {PLAN_OPTIONS.map((plan) => (
                      <div key={plan.key} className={`plan-card ${form.plan_key === plan.key ? "selected" : ""}`} onClick={() => setField("plan_key", plan.key)}>
                        {plan.badge ? <div className="plan-badge">{plan.badge}</div> : null}
                        <div className="plan-name">{plan.name}</div>
                        <div className="plan-price">{plan.price} <span>/ mois</span></div>
                        <div className="plan-desc">{plan.desc}</div>
                        <div className="plan-features">
                          {plan.features.map((feature) => <div key={feature} className="plan-feature">{feature}</div>)}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {error ? <div className="inline-error">{error}</div> : null}
            </div>
          )}

          {step === 8 && (
            <div className="screen active">
              <div className="success-wrap">
                <div className="success-icon">🎉</div>
                <div className="success-title">Votre assistant est prêt !</div>
                <div className="success-sub">
                  {me?.voice_number
                    ? "Votre assistant est activé. Vous pouvez maintenant accéder à votre dashboard et suivre vos appels."
                    : "Notre équipe finalise la configuration de votre assistant vocal et de votre agenda sous 24h."}
                </div>

                <div className="recap-row">
                  <div className="recap-item">
                    <div className="recap-val">{selectedAgent.label}</div>
                    <div className="recap-key">ASSISTANTE</div>
                  </div>
                  <div style={{ width: 1, height: 32, background: "rgba(255,255,255,0.08)" }} />
                  <div className="recap-item">
                    <div className="recap-val">{me?.voice_number || "Activation en cours"}</div>
                    <div className="recap-key">NUMÉRO PATIENT</div>
                  </div>
                  <div style={{ width: 1, height: 32, background: "rgba(255,255,255,0.08)" }} />
                  <div className="recap-item">
                    <div className="recap-val">{PLAN_OPTIONS.find((item) => item.key === form.plan_key)?.name || form.plan_key}</div>
                    <div className="recap-key">FORMULE</div>
                  </div>
                </div>

                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.35)", textAlign: "center", lineHeight: 1.6 }}>
                  Un email de confirmation vous a été envoyé à<br />
                  <strong style={{ color: "rgba(255,255,255,0.6)" }}>{form.contact_email}</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="footer">
          <button className="btn-back" id="btnBack" onClick={handleBack} style={{ visibility: step === 1 || step === 8 ? "hidden" : "visible" }}>
            ← Retour
          </button>
          <div className="footer-hint">{step === 8 ? "" : "Entrée ↵"}</div>
          <button className="btn-next" onClick={handleNext} disabled={!canContinue || saving}>
            <span>{step === 8 ? "Accéder au dashboard" : step === 7 ? (saving ? "Enregistrement..." : "Finaliser") : "Continuer"}</span>
            <span>→</span>
          </button>
        </div>
      </div>
    </div>
  );
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --teal: #00d4a0;
  --teal-dim: #00a87e;
  --navy: #0a1628;
  --navy-2: #111f35;
  --navy-3: #1a2f4a;
  --slate: #64748b;
  --muted: #94a3b8;
  --border: rgba(255,255,255,0.08);
  --white: #ffffff;
}
html, body, .ufi-root {
  min-height: 100%;
  font-family: 'DM Sans', sans-serif;
  background: var(--navy);
  color: var(--white);
}
.ufi-root { min-height: 100vh; overflow: auto; }
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  padding: 0 24px;
}
.topbar { display:flex; align-items:center; justify-content:space-between; padding:20px 0 0; flex-shrink:0; }
.logo { font-family:'Syne', sans-serif; font-size:20px; font-weight:800; color:var(--teal); letter-spacing:-0.5px; }
.step-label { font-size:11px; color:rgba(255,255,255,0.35); letter-spacing:1.2px; text-transform:uppercase; }
.progress-wrap { padding:16px 0 0; flex-shrink:0; }
.progress-track { height:2px; background:rgba(255,255,255,0.08); border-radius:2px; overflow:hidden; }
.progress-fill { height:100%; background:linear-gradient(90deg, var(--teal), #60a5fa); border-radius:2px; transition:width .5s cubic-bezier(.4,0,.2,1); }
.step-dots { display:flex; gap:6px; margin-top:10px; }
.dot { width:6px; height:6px; border-radius:50%; background:rgba(255,255,255,0.12); transition:all .3s; cursor:pointer; }
.dot.done { background: rgba(0,212,160,0.5); }
.dot.active { background: var(--teal); width:20px; border-radius:3px; }
.content { flex:1; display:flex; flex-direction:column; justify-content:center; padding:20px 0; }
.screen { animation:fadeUp .35s ease both; display:flex; flex-direction:column; gap:28px; }
.screen-eyebrow { font-size:11px; color:var(--teal); letter-spacing:1.8px; text-transform:uppercase; font-weight:600; }
.screen-title { font-family:'Syne', sans-serif; font-size:clamp(24px, 4vw, 36px); font-weight:700; line-height:1.15; color:#fff; }
.screen-title em { color:var(--teal); font-style:normal; }
.screen-sub { font-size:15px; color:rgba(255,255,255,0.45); line-height:1.6; margin-top:-16px; }
.confirm-chip { display:inline-flex; align-items:center; gap:10px; padding:12px 16px; background:rgba(0,212,160,0.08); border:1px solid rgba(0,212,160,0.2); border-radius:12px; font-size:14px; font-weight:600; color:#fff; width:fit-content; }
.confirm-chip-icon { font-size:18px; }
.tiles { display:grid; gap:10px; }
.tiles-auto { grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); }
.tile { padding:16px; border-radius:12px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); cursor:pointer; transition:all .2s; display:flex; flex-direction:column; gap:6px; }
.tile:hover { border-color:rgba(0,212,160,0.3); background:rgba(0,212,160,0.05); }
.tile.selected { border-color:var(--teal); background:rgba(0,212,160,0.1); }
.tile-icon { font-size:22px; }
.tile-label { font-size:13px; font-weight:700; color:#fff; }
.input-group { display:flex; flex-direction:column; gap:8px; }
.input-label { font-size:12px; color:rgba(255,255,255,0.4); font-weight:600; letter-spacing:.5px; }
.input-field { width:100%; padding:14px 16px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); background:rgba(255,255,255,0.05); color:#fff; font-size:15px; font-family:inherit; outline:none; transition:all .2s; }
.input-field:focus { border-color:rgba(0,212,160,0.4); background:rgba(0,212,160,0.04); }
.input-field::placeholder { color:rgba(255,255,255,0.2); }
.input-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.input-field option { color:#0a1628; }
.agent-grid { display:grid; grid-template-columns:repeat(5, 1fr); gap:10px; }
.agent-card { display:flex; flex-direction:column; align-items:center; gap:8px; padding:14px 8px; border-radius:12px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); cursor:pointer; transition:all .2s; }
.agent-card:hover { border-color:rgba(0,212,160,0.3); background:rgba(0,212,160,0.05); transform:translateY(-2px); }
.agent-card.selected { border-color:var(--teal); background:rgba(0,212,160,0.1); }
.agent-avatar { width:56px; height:56px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:28px; position:relative; overflow:hidden; background:rgba(255,255,255,0.05); border:2px solid transparent; transition:border-color .2s; }
.agent-card.selected .agent-avatar { border-color:var(--teal); }
.agent-name { font-size:12px; font-weight:700; color:#fff; text-align:center; }
.agent-gender { font-size:10px; color:rgba(255,255,255,0.35); }
.agent-check { position:absolute; bottom:-2px; right:-2px; width:18px; height:18px; border-radius:50%; background:var(--teal); color:var(--navy); font-size:10px; font-weight:800; display:none; align-items:center; justify-content:center; border:2px solid var(--navy); }
.agent-card.selected .agent-check { display:flex; }
.hours-grid { display:flex; flex-direction:column; gap:8px; }
.day-row { display:flex; align-items:center; gap:12px; padding:10px 14px; border-radius:10px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.02); }
.day-toggle { width:36px; height:20px; border-radius:10px; background:rgba(255,255,255,0.1); position:relative; cursor:pointer; flex-shrink:0; transition:background .2s; }
.day-toggle.on { background:var(--teal); }
.day-toggle::after { content:''; position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%; background:#fff; transition:transform .2s; }
.day-toggle.on::after { transform:translateX(16px); }
.day-name { font-size:13px; font-weight:600; width:80px; }
.day-hours { font-size:12px; color:rgba(255,255,255,0.35); margin-left:auto; }
.agenda-opts { display:flex; flex-direction:column; gap:8px; }
.agenda-opt { display:flex; align-items:center; gap:14px; padding:14px 18px; border-radius:12px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); cursor:pointer; transition:all .2s; }
.agenda-opt:hover { border-color:rgba(0,212,160,0.3); }
.agenda-opt.selected { border-color:var(--teal); background:rgba(0,212,160,0.07); }
.agenda-opt-icon { font-size:24px; flex-shrink:0; }
.agenda-opt-name { font-size:14px; font-weight:700; color:#fff; }
.agenda-opt-sub { font-size:11px; color:rgba(255,255,255,0.35); margin-top:2px; }
.agenda-opt-tag { margin-left:auto; font-size:10px; font-weight:700; padding:2px 8px; border-radius:5px; flex-shrink:0; }
.plan-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; }
.plan-card { padding:20px; border-radius:14px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); cursor:pointer; transition:all .2s; position:relative; }
.plan-card:hover { border-color:rgba(0,212,160,0.3); }
.plan-card.selected { border-color:var(--teal); background:rgba(0,212,160,0.07); }
.plan-badge { position:absolute; top:-10px; right:16px; background:var(--teal); color:var(--navy); font-size:10px; font-weight:800; padding:3px 10px; border-radius:10px; letter-spacing:.5px; }
.plan-name { font-family:'Syne', sans-serif; font-size:20px; font-weight:700; color:#fff; }
.plan-price { font-size:28px; font-weight:800; color:var(--teal); margin:8px 0 4px; }
.plan-price span { font-size:14px; color:rgba(255,255,255,0.4); font-weight:400; }
.plan-desc { font-size:12px; color:rgba(255,255,255,0.4); margin-bottom:14px; line-height:1.5; }
.plan-features { display:flex; flex-direction:column; gap:6px; }
.plan-feature { font-size:12px; color:rgba(255,255,255,0.6); display:flex; align-items:center; gap:6px; }
.plan-feature::before { content:'✓'; color:var(--teal); font-weight:700; flex-shrink:0; }
.success-wrap { display:flex; flex-direction:column; align-items:center; text-align:center; gap:20px; padding:20px 0; }
.success-icon { width:80px; height:80px; border-radius:50%; background:rgba(0,212,160,0.15); border:2px solid rgba(0,212,160,0.3); display:flex; align-items:center; justify-content:center; font-size:36px; animation:popIn .5s cubic-bezier(.34,1.56,.64,1) both; }
.success-title { font-family:'Syne', sans-serif; font-size:28px; font-weight:700; color:#fff; }
.success-sub { font-size:15px; color:rgba(255,255,255,0.45); line-height:1.6; max-width:400px; }
.recap-row { display:flex; align-items:center; justify-content:center; gap:24px; padding:16px 24px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:12px; width:100%; }
.recap-item { text-align:center; }
.recap-val { font-size:15px; font-weight:700; color:var(--teal); }
.recap-key { font-size:10px; color:rgba(255,255,255,0.3); margin-top:2px; letter-spacing:.5px; }
.footer { display:flex; align-items:center; justify-content:space-between; padding:16px 0 24px; flex-shrink:0; border-top:1px solid rgba(255,255,255,0.06); }
.btn-back { padding:11px 20px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:rgba(255,255,255,0.5); font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; transition:all .2s; }
.btn-back:hover { border-color:rgba(255,255,255,0.2); color:rgba(255,255,255,0.8); }
.btn-next { display:flex; align-items:center; gap:8px; padding:13px 28px; border-radius:10px; border:none; background:var(--teal); color:var(--navy); font-size:15px; font-weight:700; cursor:pointer; font-family:inherit; transition:all .2s; }
.btn-next:hover { background:#00e8b0; transform:translateY(-1px); box-shadow:0 6px 20px rgba(0,212,160,0.3); }
.btn-next:disabled { opacity:.4; cursor:not-allowed; transform:none; box-shadow:none; }
.footer-hint { font-size:11px; color:rgba(255,255,255,0.2); }
.inline-error { color:#fda4af; font-size:13px; margin-top:-8px; }
@keyframes fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes popIn { from{opacity:0;transform:scale(.6)} to{opacity:1;transform:scale(1)} }
@media (max-width: 760px) {
  .shell { padding: 0 16px; }
  .input-row { grid-template-columns: 1fr; }
  .agent-grid { grid-template-columns: repeat(3, 1fr); }
  .recap-row { flex-direction: column; gap: 12px; }
}
`;
