import { useEffect, useState } from "react";

const T = {
  teal: "#0DC991",
  tealDark: "#0AAF7A",
  tealLight: "#E8FAF4",
  tealBorder: "#A7F3D0",
  red: "#EF4444",
  amberLight: "#FFFBEB",
  amberBorder: "#FDE68A",
  text: "#0f172a",
  textMid: "#334155",
  textSoft: "#64748b",
  textFaint: "#94a3b8",
  border: "#e2e8f0",
  borderLight: "#f1f5f9",
  bg: "#f8fafc",
  card: "#ffffff",
};

const E164_FR = /^\+33[1-9]\d{8}$/;

const TRANSFER_CASES = [
  { key: "urgent", label: "Urgence medicale", icon: "!" },
  { key: "unhappy", label: "Patient mecontent / situation sensible", icon: ":(" },
  { key: "complex", label: "Demande administrative complexe", icon: "#" },
  { key: "insists", label: "Le patient insiste pour parler a quelqu'un", icon: ">" },
  { key: "other", label: "Autre", icon: "+" },
];

const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

const DEFAULT_HOURS = {
  Lundi: { enabled: true, from: "09:00", to: "18:00" },
  Mardi: { enabled: true, from: "09:00", to: "18:00" },
  Mercredi: { enabled: true, from: "09:00", to: "18:00" },
  Jeudi: { enabled: true, from: "09:00", to: "18:00" },
  Vendredi: { enabled: true, from: "09:00", to: "18:00" },
  Samedi: { enabled: false, from: "09:00", to: "13:00" },
  Dimanche: { enabled: false, from: "09:00", to: "13:00" },
};

function sanitizePhoneInput(value) {
  const raw = String(value || "");
  const cleaned = raw.replace(/[^\d+]/g, "");
  const hasPlus = cleaned.startsWith("+");
  const digits = cleaned.replace(/\+/g, "");
  return `${hasPlus ? "+" : ""}${digits.slice(0, 15)}`;
}

function normalizeFrenchPhone(value) {
  const cleaned = sanitizePhoneInput(value);
  if (!cleaned) return "";
  if (cleaned.startsWith("+")) {
    return `+${cleaned.slice(1).replace(/\D/g, "")}`;
  }
  const digits = cleaned.replace(/\D/g, "");
  if (!digits) return "";
  if (digits.startsWith("00")) return `+${digits.slice(2)}`;
  if (digits.startsWith("33")) return `+${digits}`;
  if (digits.startsWith("0") && digits.length === 10) return `+33${digits.slice(1)}`;
  if (digits.length === 9) return `+33${digits}`;
  return digits;
}

function validatePhone(value) {
  const normalized = normalizeFrenchPhone(value);
  if (!normalized) return null;
  return E164_FR.test(normalized)
    ? null
    : "Numero invalide. Format attendu : +33 suivi de 9 chiffres.";
}

function prettyPhone(value) {
  const normalized = normalizeFrenchPhone(value);
  if (!E164_FR.test(normalized)) return value || "Non renseigne";
  const digits = normalized.slice(3);
  return `+33 ${digits[0]} ${digits.slice(1, 3)} ${digits.slice(3, 5)} ${digits.slice(5, 7)} ${digits.slice(7, 9)}`;
}

function buildDefaultHours(hours) {
  const merged = {};
  for (const day of DAYS) {
    const source = hours?.[day] || DEFAULT_HOURS[day];
    merged[day] = {
      enabled: Boolean(source?.enabled),
      from: source?.from || DEFAULT_HOURS[day].from,
      to: source?.to || DEFAULT_HOURS[day].to,
    };
  }
  return merged;
}

function buildInternalConfig(initialConfig, cabinetPhone) {
  if (!initialConfig) return null;
  return {
    main_number: initialConfig.main_number || cabinetPhone || "",
    always_urgent: Boolean(initialConfig.always_urgent),
    transfer_cases: Array.isArray(initialConfig.transfer_cases) ? initialConfig.transfer_cases : [],
    hours: buildDefaultHours(initialConfig.hours),
    no_consultation: Boolean(initialConfig.no_consultation),
    practitioner_phone: initialConfig.practitioner_phone || "",
    live_enabled: Boolean(initialConfig.live_enabled),
    callback_enabled: initialConfig.callback_enabled !== false,
    confirmed: Boolean(initialConfig.confirmed),
  };
}

function StepBar({ current, labels }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", marginBottom: 28 }}>
      {labels.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={label} style={{ display: "flex", alignItems: "flex-start", flex: i < labels.length - 1 ? 1 : "none" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, flexShrink: 0 }}>
              <div
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  background: done ? T.teal : active ? T.tealDark : T.borderLight,
                  border: `2px solid ${done ? T.teal : active ? T.tealDark : T.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  fontWeight: 700,
                  color: done || active ? "#fff" : T.textFaint,
                }}
              >
                {done ? "OK" : i + 1}
              </div>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: active ? 700 : 500,
                  color: active ? T.tealDark : done ? T.textSoft : T.textFaint,
                  textAlign: "center",
                  maxWidth: 70,
                  lineHeight: 1.3,
                }}
              >
                {label}
              </div>
            </div>
            {i < labels.length - 1 ? (
              <div style={{ flex: 1, height: 2, background: done ? T.teal : T.borderLight, margin: "14px 6px 0" }} />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function Step1({ data, onChange, cabinetPhone }) {
  const [focused, setFocused] = useState(false);
  const [error, setError] = useState(null);
  const normalizedCabinetPhone = normalizeFrenchPhone(cabinetPhone);
  const normalizedValue = normalizeFrenchPhone(data.number || "");
  const isAutofill = Boolean(normalizedCabinetPhone) && normalizedValue === normalizedCabinetPhone;

  useEffect(() => {
    setError(validatePhone(data.number));
  }, [data.number]);

  const handleBlur = () => {
    setFocused(false);
    if (!data.number && normalizedCabinetPhone) {
      onChange({ ...data, number: cabinetPhone });
      setError(null);
      return;
    }
    setError(validatePhone(data.number));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <div style={{ fontSize: 19, fontWeight: 800, color: T.text, marginBottom: 5 }}>Numero de transfert</div>
        <div style={{ fontSize: 13, color: T.textSoft, lineHeight: 1.6 }}>
          Quand l'assistante IA doit transferer l'appel, vers quel numero ?
        </div>
      </div>

      <div>
        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: T.textMid, marginBottom: 7 }}>
          Numero de transfert humain
        </label>
        <div style={{ position: "relative" }}>
          <input
            type="tel"
            value={data.number || ""}
            onChange={(e) => onChange({ ...data, number: sanitizePhoneInput(e.target.value) })}
            onFocus={() => setFocused(true)}
            onBlur={handleBlur}
            placeholder="+33 6 12 34 56 78"
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "13px 16px",
              paddingRight: 44,
              fontSize: 16,
              fontWeight: 600,
              color: T.text,
              background: T.card,
              border: `2px solid ${error ? T.red : focused ? T.teal : T.border}`,
              borderRadius: 12,
              outline: "none",
              fontFamily: "inherit",
            }}
          />
          {isAutofill ? (
            <span
              style={{ position: "absolute", right: 13, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: T.tealDark }}
              title="Repris depuis le numero du cabinet"
            >
              auto
            </span>
          ) : null}
        </div>
        {error ? (
          <div style={{ marginTop: 7, fontSize: 12, color: T.red }}>{error}</div>
        ) : (
          <div style={{ marginTop: 7, fontSize: 12, color: T.textFaint, lineHeight: 1.5 }}>
            {isAutofill
              ? "Repris depuis le numero de votre cabinet. Modifiez si vous souhaitez un numero different."
              : "Si l'assistant IA ne peut pas traiter la demande, l'appel sera transfere vers ce numero. Vous pouvez indiquer un telephone du cabinet, un mobile ou un standard."}
          </div>
        )}
      </div>

      <div
        style={{
          background: T.tealLight,
          border: `1px solid ${T.tealBorder}`,
          borderRadius: 12,
          padding: "13px 15px",
          display: "flex",
          gap: 10,
          alignItems: "flex-start",
        }}
      >
        <div style={{ fontSize: 12, color: T.textMid, lineHeight: 1.6 }}>
          <strong style={{ color: T.tealDark }}>L'assistante tente toujours de resoudre la demande avant de transferer.</strong>{" "}
          Si elle ne peut pas traiter la demande seule, l'appel sera automatiquement redirige vers ce numero.
        </div>
      </div>

      <label
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          padding: "13px 15px",
          borderRadius: 12,
          border: `1.5px solid ${data.alwaysUrgent ? T.tealBorder : T.border}`,
          background: data.alwaysUrgent ? T.tealLight : T.card,
          cursor: "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={Boolean(data.alwaysUrgent)}
          onChange={(e) => onChange({ ...data, alwaysUrgent: e.target.checked })}
          style={{ marginTop: 2, width: 16, height: 16, accentColor: T.teal, cursor: "pointer", flexShrink: 0 }}
        />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: data.alwaysUrgent ? T.tealDark : T.textMid }}>
            Toujours transferer les urgences, meme hors horaires
          </div>
          <div style={{ fontSize: 12, color: T.textFaint, marginTop: 2, lineHeight: 1.5 }}>
            En dehors de vos horaires configures, les urgences seront quand meme transferees.
          </div>
        </div>
      </label>
    </div>
  );
}

function Step2({ data, onChange }) {
  const toggle = (key) => {
    const current = data.transfer_cases || [];
    const next = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
    onChange({ ...data, transfer_cases: next });
  };
  const noneSelected = (data.transfer_cases || []).length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontSize: 19, fontWeight: 800, color: T.text, marginBottom: 5 }}>Dans quels cas transferer l'appel ?</div>
        <div style={{ fontSize: 13, color: T.textSoft, lineHeight: 1.6 }}>
          L'assistante IA gere la majorite des demandes. Cochez les situations ou elle doit vous passer l'appel.
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {TRANSFER_CASES.map((option) => {
          const active = (data.transfer_cases || []).includes(option.key);
          return (
            <label
              key={option.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 13,
                padding: "12px 15px",
                borderRadius: 12,
                border: `2px solid ${active ? T.teal : T.border}`,
                background: active ? T.tealLight : T.card,
                cursor: "pointer",
              }}
            >
              <input type="checkbox" checked={active} onChange={() => toggle(option.key)} style={{ display: "none" }} />
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 9,
                  background: active ? `${T.teal}22` : T.bg,
                  border: `1px solid ${active ? T.tealBorder : T.borderLight}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 14,
                  color: active ? T.tealDark : T.textSoft,
                  flexShrink: 0,
                }}
              >
                {option.icon}
              </div>
              <div style={{ flex: 1, fontSize: 13, fontWeight: active ? 700 : 500, color: active ? T.tealDark : T.textMid }}>
                {option.label}
              </div>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  border: `2px solid ${active ? T.teal : T.border}`,
                  background: active ? T.teal : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  color: "#fff",
                  flexShrink: 0,
                }}
              >
                {active ? "OK" : ""}
              </div>
            </label>
          );
        })}
      </div>

      {noneSelected ? (
        <div style={{ background: T.amberLight, border: `1px solid ${T.amberBorder}`, borderRadius: 11, padding: "12px 14px" }}>
          <div style={{ fontSize: 12, color: "#92400e", lineHeight: 1.6 }}>
            <strong>Aucun cas selectionne.</strong> L'assistante IA ne transferera l'appel que si le patient demande explicitement a parler a quelqu'un.
          </div>
        </div>
      ) : null}

      <div style={{ background: T.bg, border: `1px solid ${T.borderLight}`, borderRadius: 11, padding: "12px 14px" }}>
        <div style={{ fontSize: 12, color: T.textSoft, lineHeight: 1.6 }}>
          L'assistante gere elle-meme les prises de rendez-vous, informations, horaires et rappels. Les situations cochees ci-dessus declencheront un transfert automatique vers votre numero.
        </div>
      </div>
    </div>
  );
}

function Step3({ data, onChange }) {
  const hours = buildDefaultHours(data.hours);

  const updateDay = (day, field, value) => {
    onChange({ ...data, hours: { ...hours, [day]: { ...hours[day], [field]: value } } });
  };

  const applyToAll = (day) => {
    const reference = hours[day];
    const nextHours = { ...hours };
    DAYS.forEach((item) => {
      if (nextHours[item].enabled) {
        nextHours[item] = { ...nextHours[item], from: reference.from, to: reference.to };
      }
    });
    onChange({ ...data, hours: nextHours });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontSize: 19, fontWeight: 800, color: T.text, marginBottom: 5 }}>Horaires de transfert</div>
        <div style={{ fontSize: 13, color: T.textSoft, lineHeight: 1.6 }}>
          A quels horaires pouvons-nous vous transferer les appels ?
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {DAYS.map((day) => {
          const dayConfig = hours[day];
          return (
            <div
              key={day}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 13px",
                borderRadius: 10,
                background: dayConfig.enabled ? T.card : T.bg,
                border: `1.5px solid ${dayConfig.enabled ? T.border : T.borderLight}`,
              }}
            >
              <label style={{ cursor: "pointer", flexShrink: 0 }}>
                <input type="checkbox" checked={dayConfig.enabled} onChange={(e) => updateDay(day, "enabled", e.target.checked)} style={{ display: "none" }} />
                <div style={{ width: 34, height: 19, borderRadius: 10, background: dayConfig.enabled ? T.teal : T.borderLight, position: "relative" }}>
                  <div
                    style={{
                      position: "absolute",
                      top: 2,
                      left: dayConfig.enabled ? 17 : 2,
                      width: 15,
                      height: 15,
                      borderRadius: "50%",
                      background: "#fff",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                    }}
                  />
                </div>
              </label>

              <div style={{ width: 76, fontSize: 13, fontWeight: dayConfig.enabled ? 600 : 400, color: dayConfig.enabled ? T.textMid : T.textFaint, flexShrink: 0 }}>
                {day}
              </div>

              {dayConfig.enabled ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1 }}>
                    <input
                      type="time"
                      value={dayConfig.from}
                      onChange={(e) => updateDay(day, "from", e.target.value)}
                      style={{ padding: "5px 8px", borderRadius: 8, border: `1.5px solid ${T.border}`, fontSize: 13, fontWeight: 500, color: T.text, background: T.card, outline: "none", fontFamily: "inherit" }}
                    />
                    <span style={{ fontSize: 11, color: T.textFaint }}>-&gt;</span>
                    <input
                      type="time"
                      value={dayConfig.to}
                      onChange={(e) => updateDay(day, "to", e.target.value)}
                      style={{ padding: "5px 8px", borderRadius: 8, border: `1.5px solid ${T.border}`, fontSize: 13, fontWeight: 500, color: T.text, background: T.card, outline: "none", fontFamily: "inherit" }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => applyToAll(day)}
                    style={{ fontSize: 10, fontWeight: 600, color: T.textFaint, background: "none", border: `1px solid ${T.borderLight}`, borderRadius: 6, padding: "3px 7px", cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}
                  >
                    Tous
                  </button>
                </>
              ) : (
                <div style={{ flex: 1, fontSize: 12, color: T.textFaint, fontStyle: "italic" }}>Ferme</div>
              )}
            </div>
          );
        })}
      </div>

      <label
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          padding: "13px 15px",
          borderRadius: 12,
          border: `1.5px solid ${data.no_consultation ? T.tealBorder : T.border}`,
          background: data.no_consultation ? T.tealLight : T.card,
          cursor: "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={Boolean(data.no_consultation)}
          onChange={(e) => onChange({ ...data, no_consultation: e.target.checked })}
          style={{ marginTop: 2, width: 16, height: 16, accentColor: T.teal, cursor: "pointer", flexShrink: 0 }}
        />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: data.no_consultation ? T.tealDark : T.textMid }}>
            Ne pas transferer pendant les consultations
          </div>
          <div style={{ fontSize: 12, color: T.textFaint, marginTop: 3, lineHeight: 1.5 }}>
            L'assistante prendra un message et proposera un rappel au patient.
          </div>
        </div>
      </label>

      <div style={{ background: T.bg, border: `1px solid ${T.borderLight}`, borderRadius: 11, padding: "12px 14px" }}>
        <div style={{ fontSize: 12, color: T.textSoft, lineHeight: 1.6 }}>
          En dehors de ces horaires, l'assistante IA continue de repondre aux appels mais ne transferera pas vers votre telephone.
        </div>
      </div>
    </div>
  );
}

function Recap({ step1, step2, step3, confirmedAt, practitionerPhone, onEdit }) {
  const activeCases = TRANSFER_CASES.filter((item) => (step2.transfer_cases || []).includes(item.key));
  const activeDays = DAYS.filter((day) => step3.hours?.[day]?.enabled ?? DEFAULT_HOURS[day].enabled);
  const noCases = activeCases.length === 0;
  const dateLabel = confirmedAt ? new Date(confirmedAt).toLocaleString("fr-FR") : "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: T.tealLight, border: `1.5px solid ${T.tealBorder}`, borderRadius: 14, padding: "18px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: T.tealDark }}>Configuration active</div>
          <button type="button" onClick={() => onEdit(0)} style={{ fontSize: 12, fontWeight: 600, color: T.textSoft, background: "none", border: `1px solid ${T.border}`, borderRadius: 8, padding: "5px 12px", cursor: "pointer" }}>
            Modifier
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: T.tealDark, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>
              Transfert vers
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.textMid }}>{prettyPhone(step1.number)}</div>
            {practitionerPhone ? (
              <div style={{ fontSize: 11, color: T.textSoft, marginTop: 2 }}>
                Ligne praticien dediee configuree : {prettyPhone(practitionerPhone)}
              </div>
            ) : null}
            {step1.alwaysUrgent ? (
              <div style={{ fontSize: 11, color: T.textSoft, marginTop: 2 }}>Urgences transferees meme hors horaires</div>
            ) : null}
          </div>

          <div style={{ height: 1, background: T.tealBorder }} />

          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: T.tealDark, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 5 }}>
              Transfert si
            </div>
            {noCases ? (
              <div style={{ fontSize: 12, color: T.textSoft, fontStyle: "italic" }}>
                Uniquement si le patient demande explicitement a parler a quelqu'un
              </div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {activeCases.map((item) => (
                  <span key={item.key} style={{ fontSize: 11, fontWeight: 600, color: T.tealDark, background: `${T.teal}20`, borderRadius: 6, padding: "2px 8px" }}>
                    {item.label}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div style={{ height: 1, background: T.tealBorder }} />

          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: T.tealDark, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 5 }}>
              Disponible
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {activeDays.map((day) => {
                const config = step3.hours?.[day] || DEFAULT_HOURS[day];
                return (
                  <div key={day} style={{ display: "flex", gap: 8, fontSize: 12, color: T.textMid }}>
                    <span style={{ width: 76, fontWeight: 600, flexShrink: 0 }}>{day}</span>
                    <span style={{ color: T.textSoft }}>
                      {config.from} -&gt; {config.to}
                    </span>
                  </div>
                );
              })}
            </div>
            {step3.no_consultation ? (
              <div style={{ fontSize: 11, color: T.textSoft, marginTop: 6 }}>Pas de transfert pendant les consultations</div>
            ) : null}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 12, color: T.textSoft, lineHeight: 1.6 }}>
        Le transfert humain est active. Si une situation importante l'exige, l'assistante redirigera l'appel vers {prettyPhone(step1.number)} pendant vos horaires de disponibilite.
        {dateLabel ? ` Derniere confirmation : ${dateLabel}.` : ""}
      </div>
    </div>
  );
}

export default function CallTransferSettings({ cabinetPhone = "", initialConfig = null, onSave }) {
  const STEP_LABELS = ["Numero", "Quand transferer", "Horaires"];
  const [step, setStep] = useState(0);
  const [confirmedAt, setConfirmedAt] = useState(initialConfig?.confirmed_at || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [step1, setStep1] = useState({ number: cabinetPhone || "", alwaysUrgent: false });
  const [step2, setStep2] = useState({ transfer_cases: [] });
  const [step3, setStep3] = useState({ hours: buildDefaultHours(), no_consultation: false });
  const [advancedConfig, setAdvancedConfig] = useState({ practitioner_phone: "", live_enabled: true, callback_enabled: true });

  useEffect(() => {
    const config = buildInternalConfig(initialConfig, cabinetPhone);
    if (!config) {
      setStep(0);
      setConfirmedAt("");
      setStep1({ number: cabinetPhone || "", alwaysUrgent: false });
      setStep2({ transfer_cases: [] });
      setStep3({ hours: buildDefaultHours(), no_consultation: false });
      setAdvancedConfig({ practitioner_phone: "", live_enabled: true, callback_enabled: true });
      return;
    }
    setConfirmedAt(initialConfig?.confirmed_at || "");
    setStep1({ number: config.main_number, alwaysUrgent: config.always_urgent });
    setStep2({ transfer_cases: config.transfer_cases });
    setStep3({ hours: config.hours, no_consultation: config.no_consultation });
    setAdvancedConfig({
      practitioner_phone: config.practitioner_phone || "",
      live_enabled: config.live_enabled !== false,
      callback_enabled: config.callback_enabled !== false,
    });
    setStep(config.confirmed ? "done" : 0);
  }, [initialConfig, cabinetPhone]);

  const canNext = () => {
    if (step === 0) {
      return E164_FR.test(normalizeFrenchPhone(step1.number || ""));
    }
    return true;
  };

  const handleNext = async () => {
    if (step === 0 || step === 1) {
      setStep((current) => current + 1);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = {
        main_number: normalizeFrenchPhone(step1.number),
        always_urgent: Boolean(step1.alwaysUrgent),
        transfer_cases: step2.transfer_cases || [],
        hours: buildDefaultHours(step3.hours),
        no_consultation: Boolean(step3.no_consultation),
      };
      const result = await onSave?.(payload);
      setConfirmedAt(result?.confirmed_at || new Date().toISOString());
      setStep("done");
    } catch (e) {
      setError(e?.message || "Impossible d'enregistrer la configuration du transfert.");
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (nextStep = 0) => {
    setStep(nextStep);
    setError("");
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 11,
              background: T.tealLight,
              border: `1px solid ${T.tealBorder}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              flexShrink: 0,
            }}
          >
            Tel
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900">Transfert d'appel</h3>
            <p className="mt-1 text-sm text-gray-600">
              Configurez comment l'assistante IA transfere les appels vers votre equipe.
            </p>
          </div>
        </div>
      </div>

      {advancedConfig.practitioner_phone ? (
        <div
          style={{
            background: T.bg,
            border: `1px solid ${T.borderLight}`,
            borderRadius: 12,
            padding: "12px 14px",
            fontSize: 12,
            color: T.textSoft,
            lineHeight: 1.6,
          }}
        >
          Une configuration avancee existe aussi cote administration.
          {" "}Si le patient demande a parler au medecin, l'appel peut etre redirige vers {prettyPhone(advancedConfig.practitioner_phone)}.
        </div>
      ) : null}

      {advancedConfig.live_enabled !== true || advancedConfig.callback_enabled !== true ? (
        <div
          style={{
            background: T.bg,
            border: `1px solid ${T.borderLight}`,
            borderRadius: 12,
            padding: "12px 14px",
            fontSize: 12,
            color: T.textSoft,
            lineHeight: 1.6,
          }}
        >
          Mode de transfert actuellement applique :
          {" "}
          <span style={{ color: T.textMid, fontWeight: 600 }}>
            {advancedConfig.live_enabled && advancedConfig.callback_enabled
              ? "Live transfer puis rappel si echec"
              : advancedConfig.live_enabled
                ? "Live transfer uniquement"
                : advancedConfig.callback_enabled
                  ? "Rappel uniquement"
                  : "Transfert desactive"}
          </span>
          .
        </div>
      ) : null}

      {step === "done" ? (
        <Recap
          step1={step1}
          step2={step2}
          step3={step3}
          confirmedAt={confirmedAt}
          practitionerPhone={advancedConfig.practitioner_phone}
          onEdit={handleEdit}
        />
      ) : (
        <>
          <StepBar current={step} labels={STEP_LABELS} />
          <div style={{ minHeight: 300 }}>
            {step === 0 ? <Step1 data={step1} onChange={setStep1} cabinetPhone={cabinetPhone} /> : null}
            {step === 1 ? <Step2 data={step2} onChange={setStep2} /> : null}
            {step === 2 ? <Step3 data={step3} onChange={setStep3} /> : null}
          </div>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <div style={{ display: "flex", gap: 10, marginTop: 28, paddingTop: 20, borderTop: `1px solid ${T.borderLight}` }}>
            {step > 0 ? (
              <button
                type="button"
                onClick={() => setStep((current) => current - 1)}
                style={{ padding: "11px 20px", borderRadius: 11, border: `1.5px solid ${T.border}`, background: T.card, color: T.textSoft, fontSize: 13, fontWeight: 600, cursor: "pointer" }}
              >
                Retour
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleNext}
              disabled={!canNext() || saving}
              style={{
                flex: 1,
                padding: 13,
                borderRadius: 11,
                border: "none",
                background: canNext() && !saving ? `linear-gradient(135deg,${T.teal},${T.tealDark})` : T.borderLight,
                color: canNext() && !saving ? "#fff" : T.textFaint,
                fontSize: 14,
                fontWeight: 700,
                cursor: canNext() && !saving ? "pointer" : "not-allowed",
                boxShadow: canNext() && !saving ? `0 4px 14px ${T.teal}40` : "none",
              }}
            >
              {saving ? "Enregistrement..." : step < 2 ? "Continuer" : "Confirmer la configuration"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
