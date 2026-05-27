import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Mail,
  Phone,
  Stethoscope,
  CreditCard,
  Bot,
  Sparkles,
  Check,
  CheckCheck,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  X,
  ExternalLink,
  Copy,
  Rocket,
  PhoneCall,
  Mic,
  Briefcase,
} from "lucide-react";
import { adminApi } from "../../lib/adminApi";
import { getClientWelcomeLoginUrl } from "../../lib/clientAppUrl.js";
import {
  deriveHorairesText,
  normalizeBookingRules,
} from "../../lib/bookingUtils.js";
import { normalizeFrenchPhone, sanitizePhoneInput } from "../../lib/transferConfig.js";
import { T, font, radius, keyframes } from "../theme.js";
import { Card, PanelCard } from "./ui/Card.jsx";
import { Button } from "./ui/Button.jsx";
import { Badge } from "./ui/Badge.jsx";
import { useDemoMode } from "../DemoModeProvider";

// ---- Constants --------------------------------------------------------------

const ASSISTANTS = [
  { id: "sophie", prenom: "Sophie", gender: "f", color: "#EC4899" },
  { id: "laura", prenom: "Laura", gender: "f", color: "#A855F7" },
  { id: "emma", prenom: "Emma", gender: "f", color: "#F43F5E" },
  { id: "julie", prenom: "Julie", gender: "f", color: "#D946EF" },
  { id: "clara", prenom: "Clara", gender: "f", color: "#F59E0B" },
  { id: "hugo", prenom: "Hugo", gender: "m", color: "#0EA5E9" },
  { id: "julien", prenom: "Julien", gender: "m", color: "#3B82F6" },
  { id: "nicolas", prenom: "Nicolas", gender: "m", color: "#6366F1" },
  { id: "alexandre", prenom: "Alexandre", gender: "m", color: "#14B8A6" },
  { id: "thomas", prenom: "Thomas", gender: "m", color: "#10B981" },
];

const SECTORS = [
  { id: "medecin_generaliste", label: "Médecin généraliste", emoji: "🩺" },
  { id: "specialiste", label: "Médecin spécialiste", emoji: "🧑‍⚕️" },
  { id: "kine", label: "Kinésithérapeute", emoji: "💪" },
  { id: "dentiste", label: "Dentiste", emoji: "🦷" },
  { id: "infirmier", label: "Infirmier(e)", emoji: "💉" },
];

const PLANS = [
  {
    id: "starter",
    label: "Starter",
    price: "99€/mois",
    quota: "300 min",
    desc: "Pour les cabinets en démarrage. Idéal jusqu'à 20 appels/jour.",
  },
  {
    id: "growth",
    label: "Growth",
    price: "149€/mois",
    quota: "800 min",
    desc: "Pour les cabinets en croissance. Idéal jusqu'à 50 appels/jour.",
    popular: true,
  },
  {
    id: "pro",
    label: "Pro",
    price: "199€/mois",
    quota: "2 000 min",
    desc: "Pour les centres médicaux à fort volume. Plus de 100 appels/jour.",
  },
];

const STEPS = [
  { id: "identity", label: "Identité", icon: Building2 },
  { id: "plan", label: "Plan & numéro", icon: CreditCard },
  { id: "agent", label: "Assistant", icon: Bot },
  { id: "review", label: "Récapitulatif", icon: Check },
];

// ---- Helpers ----------------------------------------------------------------

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((value || "").trim());
}

function isValidFrenchPhone(value) {
  return /^\+33\d{9}$/.test(normalizeFrenchPhone(value || ""));
}

function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ---- Sub-components ---------------------------------------------------------

function Stepper({ stepIdx }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        marginBottom: 0,
      }}
    >
      {STEPS.map((step, i) => {
        const Icon = step.icon;
        const isActive = i === stepIdx;
        const isDone = i < stepIdx;
        const tone = isActive || isDone ? T.teal : T.textMuted;
        return (
          <div
            key={step.id}
            style={{
              display: "flex",
              alignItems: "center",
              flex: i === STEPS.length - 1 ? "0 0 auto" : 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  background: isDone
                    ? T.teal
                    : isActive
                      ? "#FFFFFF"
                      : T.bgSubtle,
                  border: `2px solid ${tone}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: isDone ? "#FFFFFF" : tone,
                  fontWeight: 700,
                  fontSize: 13,
                  fontFamily: font.body,
                  flexShrink: 0,
                  transition: "all 0.2s",
                }}
              >
                {isDone ? <Check size={14} strokeWidth={3} /> : <Icon size={14} strokeWidth={2.4} />}
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 11,
                    color: T.textMuted,
                    fontFamily: font.body,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    lineHeight: 1.1,
                  }}
                >
                  Étape {i + 1}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: isActive || isDone ? T.text : T.textSecondary,
                    fontWeight: isActive ? 700 : 600,
                    fontFamily: font.body,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {step.label}
                </div>
              </div>
            </div>
            {i < STEPS.length - 1 ? (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: isDone ? T.teal : T.border,
                  margin: "0 12px",
                  borderRadius: 1,
                  transition: "background 0.2s",
                  minWidth: 16,
                }}
              />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function FieldLabel({ children, required }) {
  return (
    <div
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: T.textMuted,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        marginBottom: 6,
        fontFamily: font.body,
      }}
    >
      {children}
      {required ? <span style={{ color: T.red, marginLeft: 4 }}>*</span> : null}
    </div>
  );
}

function TextInputField({ icon, value, onChange, onBlur, type, placeholder, mono, invalid, autoFocus }) {
  const Icon = icon;
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
      {Icon ? (
        <Icon
          size={14}
          strokeWidth={2.4}
          style={{
            position: "absolute",
            left: 12,
            color: invalid ? T.red : T.textMuted,
            pointerEvents: "none",
          }}
        />
      ) : null}
      <input
        type={type || "text"}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={onChange}
        onBlur={onBlur}
        autoFocus={autoFocus}
        style={{
          width: "100%",
          background: T.bgCard,
          border: `1px solid ${invalid ? T.red : T.border}`,
          borderRadius: radius.md,
          padding: Icon ? "10px 12px 10px 36px" : "10px 12px",
          fontSize: 14,
          fontFamily: mono ? "ui-monospace, monospace" : font.body,
          color: T.text,
          outline: "none",
          boxSizing: "border-box",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = invalid ? T.red : T.teal;
          e.currentTarget.style.boxShadow = `0 0 0 3px ${invalid ? T.red : T.teal}15`;
        }}
        onBlurCapture={(e) => {
          e.currentTarget.style.borderColor = invalid ? T.red : T.border;
          e.currentTarget.style.boxShadow = "none";
        }}
      />
    </div>
  );
}

function ChoiceCard({ active, onClick, disabled, children, style }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 14px",
        borderRadius: radius.md,
        border: `1px solid ${active ? T.teal : T.border}`,
        background: active ? T.tealLight : T.bgCard,
        color: active ? T.teal : T.text,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        textAlign: "left",
        fontFamily: font.body,
        transition: "all 0.15s",
        width: "100%",
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!disabled && !active) e.currentTarget.style.borderColor = T.teal;
      }}
      onMouseLeave={(e) => {
        if (!disabled && !active) e.currentTarget.style.borderColor = T.border;
      }}
    >
      {children}
    </button>
  );
}

function AssistantAvatar({ assistant, active, onClick, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        padding: 12,
        borderRadius: radius.md,
        border: `2px solid ${active ? T.teal : T.border}`,
        background: active ? T.tealLight : T.bgCard,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        fontFamily: font.body,
        transition: "all 0.2s",
        position: "relative",
        boxShadow: active ? `0 4px 12px ${T.teal}25` : "none",
        transform: active ? "scale(1.02)" : "scale(1)",
      }}
      onMouseEnter={(e) => {
        if (!disabled && !active) e.currentTarget.style.borderColor = T.teal;
      }}
      onMouseLeave={(e) => {
        if (!disabled && !active) e.currentTarget.style.borderColor = T.border;
      }}
    >
      {active ? (
        <div
          style={{
            position: "absolute",
            top: 6,
            right: 6,
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: T.teal,
            color: "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
          }}
        >
          <Check size={12} strokeWidth={3} />
        </div>
      ) : null}
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: `linear-gradient(135deg, ${assistant.color}, ${assistant.color}AA)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
          fontWeight: 700,
          color: "#FFFFFF",
          fontFamily: font.display,
          boxShadow: "0 4px 12px rgba(15,23,42,0.1)",
        }}
      >
        {assistant.prenom[0]}
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: active ? T.teal : T.text,
        }}
      >
        {assistant.prenom}
      </div>
      <div style={{ fontSize: 10, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Voix {assistant.gender === "f" ? "féminine" : "masculine"}
      </div>
    </button>
  );
}

function ReviewRow({ label, value, icon }) {
  const Icon = icon;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 12px",
        background: T.bgSubtle,
        borderRadius: radius.md,
        border: `1px solid ${T.border}`,
      }}
    >
      {Icon ? (
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: radius.sm,
            background: T.bgCard,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: T.teal,
            flexShrink: 0,
          }}
        >
          <Icon size={14} strokeWidth={2.4} />
        </div>
      ) : null}
      <div
        style={{
          fontSize: 11,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          fontWeight: 600,
          fontFamily: font.body,
          minWidth: 100,
        }}
      >
        {label}
      </div>
      <div
        style={{
          flex: 1,
          fontSize: 13,
          fontWeight: 600,
          color: T.text,
          fontFamily: font.body,
          textAlign: "right",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={typeof value === "string" ? value : undefined}
      >
        {value || <span style={{ color: T.textMuted, fontWeight: 400 }}>—</span>}
      </div>
    </div>
  );
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange?.(!checked)}
      style={{
        width: 40,
        height: 22,
        borderRadius: 999,
        cursor: disabled ? "not-allowed" : "pointer",
        background: checked ? T.teal : T.border,
        position: "relative",
        border: "none",
        padding: 0,
        flexShrink: 0,
        transition: "background 0.2s",
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: checked ? 21 : 3,
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "#FFFFFF",
          boxShadow: "0 1px 3px rgba(15,23,42,0.2)",
          transition: "left 0.2s",
        }}
      />
    </button>
  );
}

// ---- Main wizard ------------------------------------------------------------

/**
 * Wizard de creation de tenant. S'utilise dans une page (AdminTenantNew) ou
 * dans une modal (CreateTenantModal). N'a aucune chrome (header/footer) externe.
 *
 * Props :
 *  - prefill              : pre-remplir avec un lead
 *  - initialBookingRules  : booking rules (depuis lead.opening_hours)
 *  - onCancel             : callback bouton "Annuler" sur etape 0
 *  - onCreated            : callback succes ({ id, name, email, phone_number, results })
 */
export default function TenantCreationWizard({
  prefill = {},
  initialBookingRules = null,
  onCancel,
  onCreated,
}) {
  const navigate = useNavigate();
  const { isDemoMode } = useDemoMode();

  const [stepIdx, setStepIdx] = useState(0);
  const [twilioNumbers, setTwilioNumbers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const bookingRules = useMemo(
    () => normalizeBookingRules(initialBookingRules || {}),
    [initialBookingRules],
  );

  const [form, setForm] = useState(() => ({
    name: prefill.name || "",
    email: prefill.email || "",
    phone: prefill.phone || "",
    sector: prefill.sector || "",
    plan_key: prefill.plan_key || "",
    assistant_id: prefill.assistant_id || "",
    twilio_number: prefill.twilio_number || "",
    send_welcome: true,
    timezone: "Europe/Paris",
  }));
  const [touched, setTouched] = useState({});

  // Fetch Twilio numbers
  useEffect(() => {
    adminApi
      .getTwilioNumbers()
      .then((nums) => setTwilioNumbers((nums || []).filter((n) => n.available)))
      .catch(() => setTwilioNumbers([]));
  }, []);

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));
  const touch = (key) => setTouched((t) => ({ ...t, [key]: true }));

  // ---- Validations per step --------------------------------------------------

  const errors = useMemo(() => {
    const e = {};
    if (!form.name.trim() || form.name.trim().length < 2) e.name = "Nom requis (2 caractères min).";
    if (!isValidEmail(form.email)) e.email = "Email invalide.";
    if (!isValidFrenchPhone(form.phone)) e.phone = "Format attendu : +33XXXXXXXXX.";
    if (!form.sector) e.sector = "Sélectionne un secteur.";
    if (!form.plan_key) e.plan_key = "Sélectionne un plan.";
    if (!form.assistant_id) e.assistant_id = "Choisis un assistant.";
    return e;
  }, [form]);

  const stepErrors = useMemo(() => {
    if (stepIdx === 0) {
      return [errors.name, errors.email, errors.phone, errors.sector].filter(Boolean);
    }
    if (stepIdx === 1) {
      return [errors.plan_key].filter(Boolean);
    }
    if (stepIdx === 2) {
      return [errors.assistant_id].filter(Boolean);
    }
    return Object.values(errors);
  }, [stepIdx, errors]);

  const canNext = stepErrors.length === 0;

  // ---- Submission -----------------------------------------------------------

  const handleSubmit = async () => {
    setSubmitting(true);
    setResult(null);
    try {
      const payload = {
        ...form,
        phone: normalizeFrenchPhone(form.phone),
        twilio_number: form.twilio_number || null,
        booking_rules: bookingRules,
        lead_id: prefill.lead_id || null,
      };
      const res = await adminApi.createTenantFull(payload);
      const ok = { success: true, ...res };
      setResult(ok);
      onCreated?.({
        id: res?.tenant_id ?? res?.results?.tenant_id ?? null,
        name: form.name,
        email: form.email,
        phone_number: form.phone,
        results: res?.results || null,
      });
    } catch (e) {
      setResult({ success: false, error: e?.message || "Erreur inconnue" });
    } finally {
      setSubmitting(false);
    }
  };

  const goNext = () => {
    Object.keys(errors).forEach(touch);
    if (canNext) setStepIdx((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const goPrev = () => {
    if (stepIdx === 0) onCancel?.();
    else setStepIdx((s) => Math.max(s - 1, 0));
  };

  // ---- Render ---------------------------------------------------------------

  // Resultat de creation (success ou error)
  if (result) {
    return <ResultPanel result={result} form={form} onClose={onCancel} navigate={navigate} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, fontFamily: font.body }}>
      <style>{keyframes}</style>

      {/* Stepper */}
      <Card padding={20} style={{ background: T.bgCard }}>
        <Stepper stepIdx={stepIdx} />
      </Card>

      {/* Mode demo notice */}
      {isDemoMode ? (
        <Card padding={12} style={{ background: T.orangeLight, borderColor: `${T.orange}40` }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontSize: 13,
              color: T.orange,
              fontWeight: 600,
            }}
          >
            <AlertTriangle size={16} strokeWidth={2.4} />
            Mode démo : tu peux parcourir le wizard, mais la création réelle sera bloquée à
            l'étape finale.
          </div>
        </Card>
      ) : null}

      {/* Step content */}
      {stepIdx === 0 ? (
        <StepIdentity form={form} set={set} touched={touched} touch={touch} errors={errors} />
      ) : null}
      {stepIdx === 1 ? (
        <StepPlan
          form={form}
          set={set}
          twilioNumbers={twilioNumbers}
          errors={errors}
          touched={touched}
          touch={touch}
        />
      ) : null}
      {stepIdx === 2 ? (
        <StepAgent form={form} set={set} errors={errors} touched={touched} touch={touch} />
      ) : null}
      {stepIdx === 3 ? (
        <StepReview form={form} bookingRules={bookingRules} set={set} />
      ) : null}

      {/* Footer navigation */}
      <Card padding={16} style={{ background: T.bgCard }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <Button
            variant="ghost"
            size="md"
            iconLeft={<ChevronLeft size={14} strokeWidth={2.4} />}
            onClick={goPrev}
            disabled={submitting}
          >
            {stepIdx === 0 ? "Annuler" : "Retour"}
          </Button>

          {stepIdx < STEPS.length - 1 ? (
            <Button
              variant="primary"
              size="md"
              iconRight={<ChevronRight size={14} strokeWidth={2.4} />}
              onClick={goNext}
              disabled={!canNext}
              title={!canNext ? "Complète les champs obligatoires" : undefined}
            >
              Suivant
            </Button>
          ) : (
            <Button
              variant="primary"
              size="md"
              iconLeft={<Rocket size={14} strokeWidth={2.4} />}
              onClick={handleSubmit}
              disabled={submitting || !canNext || isDemoMode}
              title={
                isDemoMode
                  ? "Création réelle désactivée en mode démo"
                  : !canNext
                    ? "Complète les champs obligatoires"
                    : undefined
              }
            >
              {submitting ? "Création en cours…" : "Créer le client"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

// ---- Steps ------------------------------------------------------------------

function StepIdentity({ form, set, touched, touch, errors }) {
  const showErr = (key) => touched[key] && errors[key];
  return (
    <PanelCard
      eyebrow="Étape 1"
      title="Identité du cabinet"
      subtitle="Coordonnées principales et secteur d'activité"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <FieldLabel required>Nom du cabinet</FieldLabel>
          <TextInputField
            icon={Building2}
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            onBlur={() => touch("name")}
            placeholder="Cabinet du Dr Martin"
            invalid={showErr("name")}
            autoFocus
          />
          {showErr("name") ? <ErrorText msg={errors.name} /> : null}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 16 }}>
          <div>
            <FieldLabel required>Email contact</FieldLabel>
            <TextInputField
              icon={Mail}
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              onBlur={() => touch("email")}
              placeholder="contact@cabinet.fr"
              invalid={showErr("email")}
            />
            {showErr("email") ? <ErrorText msg={errors.email} /> : null}
          </div>
          <div>
            <FieldLabel required>Téléphone cabinet</FieldLabel>
            <TextInputField
              icon={Phone}
              type="tel"
              value={form.phone}
              onChange={(e) => set("phone", sanitizePhoneInput(e.target.value))}
              onBlur={(e) => {
                set("phone", normalizeFrenchPhone(e.target.value));
                touch("phone");
              }}
              placeholder="+33 1 23 45 67 89"
              mono
              invalid={showErr("phone")}
            />
            {showErr("phone") ? <ErrorText msg={errors.phone} /> : null}
          </div>
        </div>

        <div>
          <FieldLabel required>Secteur médical</FieldLabel>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: 8,
            }}
          >
            {SECTORS.map((s) => (
              <ChoiceCard
                key={s.id}
                active={form.sector === s.id}
                onClick={() => {
                  set("sector", s.id);
                  touch("sector");
                }}
              >
                <span style={{ fontSize: 22 }}>{s.emoji}</span>
                <span style={{ flex: 1, fontWeight: 600, fontSize: 13 }}>{s.label}</span>
                {form.sector === s.id ? (
                  <Check size={14} strokeWidth={2.6} style={{ color: T.teal, flexShrink: 0 }} />
                ) : null}
              </ChoiceCard>
            ))}
          </div>
          {showErr("sector") ? <ErrorText msg={errors.sector} /> : null}
        </div>
      </div>
    </PanelCard>
  );
}

function StepPlan({ form, set, twilioNumbers, errors, touched, touch }) {
  const showErr = (key) => touched[key] && errors[key];
  return (
    <PanelCard
      eyebrow="Étape 2"
      title="Plan & numéro de téléphone"
      subtitle="Choisis l'abonnement et un numéro Twilio (optionnel)"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div>
          <FieldLabel required>Plan</FieldLabel>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 10,
            }}
          >
            {PLANS.map((p) => {
              const active = form.plan_key === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    set("plan_key", p.id);
                    touch("plan_key");
                  }}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "stretch",
                    gap: 8,
                    padding: 16,
                    borderRadius: radius.md,
                    border: `2px solid ${active ? T.teal : T.border}`,
                    background: active ? T.tealLight : T.bgCard,
                    cursor: "pointer",
                    fontFamily: font.body,
                    textAlign: "left",
                    transition: "all 0.15s",
                    position: "relative",
                  }}
                >
                  {p.popular ? (
                    <Badge tone={T.orange} size="sm" style={{ position: "absolute", top: 10, right: 10 }}>
                      Populaire
                    </Badge>
                  ) : null}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                    <div
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        color: active ? T.teal : T.text,
                        fontFamily: font.display,
                      }}
                    >
                      {p.label}
                    </div>
                    {active ? <Check size={16} strokeWidth={2.6} style={{ color: T.teal }} /> : null}
                  </div>
                  <div
                    style={{
                      fontSize: 22,
                      fontWeight: 700,
                      color: T.text,
                      fontFamily: font.display,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {p.price}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: T.teal,
                      fontWeight: 600,
                      fontFamily: "ui-monospace, monospace",
                    }}
                  >
                    {p.quota} de communication
                  </div>
                  <div style={{ fontSize: 12, color: T.textSecondary, lineHeight: 1.5 }}>{p.desc}</div>
                </button>
              );
            })}
          </div>
          {showErr("plan_key") ? <ErrorText msg={errors.plan_key} /> : null}
        </div>

        <div>
          <FieldLabel>Numéro Twilio</FieldLabel>
          <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
            <PhoneCall
              size={14}
              strokeWidth={2.4}
              style={{
                position: "absolute",
                left: 12,
                color: T.textMuted,
                pointerEvents: "none",
              }}
            />
            <select
              value={form.twilio_number}
              onChange={(e) => set("twilio_number", e.target.value)}
              style={{
                width: "100%",
                background: T.bgCard,
                border: `1px solid ${T.border}`,
                borderRadius: radius.md,
                padding: "10px 12px 10px 36px",
                fontSize: 14,
                fontFamily: font.body,
                color: T.text,
                outline: "none",
                cursor: "pointer",
                appearance: "menulist",
              }}
            >
              <option value="">— Assigner plus tard —</option>
              {twilioNumbers.map((n) => (
                <option key={n.number} value={n.number}>
                  {n.friendly} ({n.number})
                </option>
              ))}
            </select>
          </div>
          <div
            style={{
              fontSize: 12,
              color: T.textMuted,
              marginTop: 6,
              fontFamily: font.body,
            }}
          >
            {twilioNumbers.length === 0
              ? "Aucun numéro Twilio disponible. Le client pourra en assigner un plus tard depuis sa fiche."
              : `${twilioNumbers.length} numéro(s) disponible(s) dans le pool Twilio.`}
          </div>
        </div>
      </div>
    </PanelCard>
  );
}

function StepAgent({ form, set, errors, touched, touch }) {
  const showErr = (key) => touched[key] && errors[key];
  return (
    <PanelCard
      eyebrow="Étape 3"
      title="Choix de l'assistant vocal"
      subtitle="Sélectionne la voix et le prénom de l'assistante IA"
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 12,
        }}
      >
        {ASSISTANTS.map((a) => (
          <AssistantAvatar
            key={a.id}
            assistant={a}
            active={form.assistant_id === a.id}
            onClick={() => {
              set("assistant_id", a.id);
              touch("assistant_id");
            }}
          />
        ))}
      </div>
      {showErr("assistant_id") ? <ErrorText msg={errors.assistant_id} /> : null}
      {form.assistant_id ? (
        <Card
          padding={14}
          style={{
            marginTop: 16,
            background: T.tealLight,
            borderColor: `${T.teal}40`,
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 10,
              alignItems: "center",
              fontSize: 13,
              color: T.teal,
              fontFamily: font.body,
              fontWeight: 600,
            }}
          >
            <Mic size={14} strokeWidth={2.4} />
            <span>
              {ASSISTANTS.find((a) => a.id === form.assistant_id)?.prenom} sera la voix de votre
              cabinet. Vous pourrez la modifier plus tard depuis la fiche client.
            </span>
          </div>
        </Card>
      ) : null}
    </PanelCard>
  );
}

function StepReview({ form, bookingRules, set }) {
  const sector = SECTORS.find((s) => s.id === form.sector);
  const plan = PLANS.find((p) => p.id === form.plan_key);
  const assistant = ASSISTANTS.find((a) => a.id === form.assistant_id);
  return (
    <PanelCard
      eyebrow="Étape 4"
      title="Récapitulatif & création"
      subtitle="Vérifie les informations avant de provisionner le client"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 8 }}>
          <ReviewRow icon={Building2} label="Cabinet" value={form.name} />
          <ReviewRow icon={Mail} label="Email" value={form.email} />
          <ReviewRow icon={Phone} label="Téléphone" value={normalizeFrenchPhone(form.phone)} />
          <ReviewRow
            icon={Stethoscope}
            label="Secteur"
            value={sector ? `${sector.emoji} ${sector.label}` : null}
          />
          <ReviewRow
            icon={CreditCard}
            label="Plan"
            value={plan ? `${plan.label} · ${plan.price}` : null}
          />
          <ReviewRow icon={Bot} label="Assistant" value={assistant?.prenom} />
          <ReviewRow
            icon={PhoneCall}
            label="Numéro Twilio"
            value={form.twilio_number || "À assigner plus tard"}
          />
          <ReviewRow
            icon={Briefcase}
            label="Horaires"
            value={`${deriveHorairesText(bookingRules)} · RDV ${bookingRules.booking_duration_minutes} min`}
          />
        </div>

        <Card
          padding={14}
          style={{ background: T.bgSubtle, borderColor: T.border }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: 200 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: T.text,
                  marginBottom: 2,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <Mail size={14} strokeWidth={2.4} style={{ color: T.teal }} />
                Email de bienvenue
              </div>
              <div style={{ fontSize: 12, color: T.textSecondary, fontFamily: font.body }}>
                Envoie un email à <strong style={{ color: T.text }}>{form.email}</strong> avec le
                lien d'accès au dashboard client.
              </div>
            </div>
            <Toggle checked={form.send_welcome} onChange={(v) => set("send_welcome", v)} />
          </div>
        </Card>

        <Card padding={14} style={{ background: T.tealLight, borderColor: `${T.teal}40` }}>
          <div
            style={{
              fontSize: 12,
              color: T.teal,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 6,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Sparkles size={12} strokeWidth={2.6} />
            Provisioning automatique
          </div>
          <div
            style={{
              fontSize: 12,
              color: T.text,
              lineHeight: 1.6,
              fontFamily: font.body,
            }}
          >
            En cliquant sur "Créer le client", la plateforme va automatiquement :
          </div>
          <ul
            style={{
              fontSize: 12,
              color: T.textSecondary,
              fontFamily: font.body,
              margin: "6px 0 0 18px",
              padding: 0,
              lineHeight: 1.7,
            }}
          >
            <li>Créer le tenant en base de données</li>
            <li>Provisionner l'assistant Vapi (voix {assistant?.prenom})</li>
            <li>Créer le customer Stripe + l'abonnement {plan?.label}</li>
            {form.twilio_number ? (
              <li>Assigner le numéro Twilio {form.twilio_number}</li>
            ) : (
              <li style={{ color: T.textMuted }}>Numéro Twilio : à assigner plus tard</li>
            )}
            {form.send_welcome ? <li>Envoyer un email de bienvenue à {form.email}</li> : null}
          </ul>
        </Card>
      </div>
    </PanelCard>
  );
}

function ErrorText({ msg }) {
  return (
    <div
      style={{
        marginTop: 6,
        fontSize: 12,
        color: T.red,
        fontFamily: font.body,
        display: "flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      <AlertTriangle size={12} strokeWidth={2.4} />
      {msg}
    </div>
  );
}

// ---- Result panel -----------------------------------------------------------

function ResultPanel({ result, form, onClose, navigate }) {
  if (result.success) {
    const tenantId = result.tenant_id ?? result.results?.tenant_id;
    const warnings = result.results?.errors || [];
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16, fontFamily: font.body }}>
        <Card padding={28} style={{ background: T.greenLight, borderColor: `${T.green}40`, textAlign: "center" }}>
          <div
            style={{
              width: 64,
              height: 64,
              margin: "0 auto 16px",
              borderRadius: "50%",
              background: T.green,
              color: "#FFFFFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `0 8px 24px ${T.green}40`,
            }}
          >
            <CheckCheck size={32} strokeWidth={2.4} />
          </div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: T.text,
              fontFamily: font.display,
              marginBottom: 6,
            }}
          >
            Client créé avec succès
          </div>
          <div style={{ fontSize: 14, color: T.textSecondary }}>
            <strong style={{ color: T.text }}>{form.name}</strong> est maintenant opérationnel.
          </div>
        </Card>

        {warnings.length > 0 ? (
          <Card padding={14} style={{ background: T.orangeLight, borderColor: `${T.orange}40` }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: T.orange,
                marginBottom: 6,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <AlertTriangle size={14} strokeWidth={2.4} />
              Avertissements
            </div>
            <ul
              style={{
                margin: "0 0 0 18px",
                padding: 0,
                fontSize: 12,
                color: T.text,
                lineHeight: 1.7,
              }}
            >
              {warnings.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </Card>
        ) : null}

        <PanelCard
          eyebrow="Provisioning"
          title="Étapes complétées"
          subtitle="Toutes les intégrations ont été configurées"
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <ProvisionRow icon={Building2} label="Tenant créé" />
            <ProvisionRow
              icon={Bot}
              label={`Assistant Vapi : ${ASSISTANTS.find((a) => a.id === form.assistant_id)?.prenom || form.assistant_id}`}
            />
            <ProvisionRow
              icon={PhoneCall}
              label={`Numéro Twilio : ${result.results?.twilio_number || form.twilio_number || "à assigner plus tard"}`}
            />
            <ProvisionRow
              icon={CreditCard}
              label={`Stripe : ${PLANS.find((p) => p.id === form.plan_key)?.label || form.plan_key}`}
            />
            {form.send_welcome ? (
              <ProvisionRow icon={Mail} label={`Email envoyé à ${form.email}`} />
            ) : null}
          </div>
        </PanelCard>

        <Card padding={16} style={{ background: T.bgCard }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <Button
              variant="secondary"
              size="md"
              iconLeft={<Copy size={13} strokeWidth={2.4} />}
              onClick={() => {
                const url = getClientWelcomeLoginUrl(form.email);
                navigator.clipboard?.writeText(url);
              }}
            >
              Copier le lien dashboard
            </Button>
            {tenantId ? (
              <Button
                variant="primary"
                size="md"
                iconRight={<ExternalLink size={13} strokeWidth={2.4} />}
                onClick={() => {
                  onClose?.();
                  navigate(`/admin/tenants/${tenantId}`);
                }}
              >
                Voir la fiche client
              </Button>
            ) : null}
          </div>
        </Card>
      </div>
    );
  }

  // Erreur
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, fontFamily: font.body }}>
      <Card padding={28} style={{ background: T.redLight, borderColor: `${T.red}40`, textAlign: "center" }}>
        <div
          style={{
            width: 64,
            height: 64,
            margin: "0 auto 16px",
            borderRadius: "50%",
            background: T.red,
            color: "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: `0 8px 24px ${T.red}40`,
          }}
        >
          <X size={32} strokeWidth={2.4} />
        </div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: T.text,
            fontFamily: font.display,
            marginBottom: 6,
          }}
        >
          Erreur lors de la création
        </div>
        <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 0 }}>{result.error}</div>
      </Card>
      <Card padding={16} style={{ background: T.bgCard }}>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <Button variant="ghost" size="md" onClick={onClose}>
            Fermer
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => {
              window.location.reload();
            }}
          >
            Réessayer
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ProvisionRow({ icon, label }) {
  const Icon = icon;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 12px",
        background: T.bgSubtle,
        borderRadius: radius.md,
        border: `1px solid ${T.border}`,
      }}
    >
      <div
        style={{
          width: 24,
          height: 24,
          borderRadius: radius.sm,
          background: T.greenLight,
          color: T.green,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Check size={13} strokeWidth={3} />
      </div>
      <div
        style={{
          fontSize: 12,
          color: T.text,
          fontWeight: 500,
          fontFamily: font.body,
          flex: 1,
        }}
      >
        <span style={{ color: T.textMuted, marginRight: 4 }}>
          <Icon size={12} strokeWidth={2.4} style={{ display: "inline-block", verticalAlign: "middle" }} />
        </span>
        {label}
      </div>
    </div>
  );
}
