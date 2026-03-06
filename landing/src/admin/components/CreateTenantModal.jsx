import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { getClientWelcomeLoginUrl } from "../../lib/clientAppUrl.js";

const C = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  text: "#FFFFFF",
  muted: "#6B90A8",
  danger: "#FF6B6B",
};

const ASSISTANTS = [
  { id: "sophie", prenom: "Sophie", gender: "f", img: "/avatars/uwi-avatar-sophie.png" },
  { id: "laura", prenom: "Laura", gender: "f", img: "/avatars/uwi-avatar-laura.png" },
  { id: "emma", prenom: "Emma", gender: "f", img: "/avatars/uwi-avatar-emma.png" },
  { id: "julie", prenom: "Julie", gender: "f", img: "/avatars/uwi-avatar-julie.png" },
  { id: "clara", prenom: "Clara", gender: "f", img: "/avatars/uwi-avatar-clara.png" },
  { id: "hugo", prenom: "Hugo", gender: "m", img: "/avatars/uwi-avatar-hugo.png" },
  { id: "julien", prenom: "Julien", gender: "m", img: "/avatars/uwi-avatar-julien.png" },
  { id: "nicolas", prenom: "Nicolas", gender: "m", img: "/avatars/uwi-avatar-nicolas.png" },
  { id: "alexandre", prenom: "Alexandre", gender: "m", img: "/avatars/uwi-avatar-alexandre.png" },
  { id: "thomas", prenom: "Thomas", gender: "m", img: "/avatars/uwi-avatar-thomas.png" },
];

const SECTORS = [
  { id: "medecin_generaliste", label: "Médecin généraliste" },
  { id: "specialiste", label: "Médecin spécialiste" },
  { id: "kine", label: "Kinésithérapeute" },
  { id: "dentiste", label: "Dentiste" },
  { id: "infirmier", label: "Infirmier(e)" },
];

const PLANS = [
  { id: "starter", label: "Starter — 99€/mois", quota: "300 min" },
  { id: "growth", label: "Growth — 149€/mois", quota: "800 min" },
  { id: "pro", label: "Pro — 199€/mois", quota: "2000 min" },
];

const STEPS = ["Infos client", "Configuration", "Assistant", "Récapitulatif"];

export default function CreateTenantModal({ onClose, onCreated, prefill = {} }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [twilioNumbers, setTwilio] = useState([]);
  const [submitting, setSubmit] = useState(false);
  const [result, setResult] = useState(null);

  const [form, setForm] = useState({
    name: prefill.name || "",
    email: prefill.email || "",
    phone: prefill.phone || "",
    sector: prefill.sector || "medecin_generaliste",
    plan_key: prefill.plan_key || "starter",
    assistant_id: prefill.assistant_id || "sophie",
    twilio_number: prefill.twilio_number || "",
    send_welcome: true,
    timezone: "Europe/Paris",
  });

  useEffect(() => {
    adminApi
      .getTwilioNumbers()
      .then((nums) => setTwilio((nums || []).filter((n) => n.available)))
      .catch(() => {});
  }, []);

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const canNext = () => {
    if (step === 0) return form.name && form.email && form.phone;
    if (step === 1) return form.sector && form.plan_key;
    if (step === 2) return form.assistant_id;
    return true;
  };

  const handleSubmit = async () => {
    setSubmit(true);
    try {
      const payload = {
        ...form,
        twilio_number: form.twilio_number || null,
      };
      const res = await adminApi.createTenantFull(payload);
      setResult(res);
      setStep(4);
      onCreated?.({
        id: res?.tenant_id ?? res?.results?.tenant_id ?? null,
        name: form.name,
        email: form.email,
        phone_number: form.phone,
      });
    } catch (e) {
      setResult({ success: false, error: e?.message || "Erreur inconnue" });
      setStep(4);
    } finally {
      setSubmit(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(4px)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 24,
          width: "100%",
          maxWidth: 560,
          boxShadow: "0 32px 80px rgba(0,0,0,0.6)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ padding: "24px 28px 0", borderBottom: `1px solid ${C.border}`, paddingBottom: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: C.text, letterSpacing: -0.5 }}>
                Nouveau client
              </div>
              <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
                Création automatique — Vapi + Stripe + Twilio
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: C.muted,
                fontSize: 20,
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>

          {/* Stepper */}
          {step < 4 && (
            <div style={{ display: "flex", gap: 0 }}>
              {STEPS.map((s, i) => (
                <div
                  key={s}
                  style={{
                    flex: 1,
                    textAlign: "center",
                    paddingBottom: 12,
                    borderBottom: `2px solid ${i === step ? C.accent : i < step ? C.accentDim : C.border}`,
                    transition: "border-color 0.2s",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: i === step ? 700 : 500,
                      color: i === step ? C.accent : i < step ? C.accentDim : C.muted,
                    }}
                  >
                    {i < step ? "✓ " : ""}
                    {s}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        <div style={{ padding: "28px" }}>
          {/* Step 0 : Infos client */}
          {step === 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <Field
                label="Nom du cabinet"
                value={form.name}
                onChange={(v) => set("name", v)}
                placeholder="Cabinet Dr Martin"
              />
              <Field
                label="Email"
                type="email"
                value={form.email}
                onChange={(v) => set("email", v)}
                placeholder="contact@cabinet-martin.fr"
              />
              <Field
                label="Téléphone cabinet"
                type="tel"
                value={form.phone}
                onChange={(v) => set("phone", v)}
                placeholder="+33 1 23 45 67 89"
              />
            </div>
          )}

          {/* Step 1 : Configuration */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.muted,
                    fontWeight: 600,
                    marginBottom: 10,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  Secteur médical
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {SECTORS.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => set("sector", s.id)}
                      style={{
                        padding: "10px 14px",
                        borderRadius: 10,
                        cursor: "pointer",
                        background: form.sector === s.id ? "rgba(0,229,160,0.08)" : C.card,
                        border: `1px solid ${form.sector === s.id ? C.accent : C.border}`,
                        color: form.sector === s.id ? C.accent : C.text,
                        fontSize: 13,
                        fontWeight: form.sector === s.id ? 700 : 500,
                        transition: "all 0.15s",
                      }}
                    >
                      {s.label}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.muted,
                    fontWeight: 600,
                    marginBottom: 10,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  Plan
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {PLANS.map((p) => (
                    <div
                      key={p.id}
                      onClick={() => set("plan_key", p.id)}
                      style={{
                        padding: "10px 14px",
                        borderRadius: 10,
                        cursor: "pointer",
                        background: form.plan_key === p.id ? "rgba(0,229,160,0.08)" : C.card,
                        border: `1px solid ${form.plan_key === p.id ? C.accent : C.border}`,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "all 0.15s",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: form.plan_key === p.id ? 700 : 500,
                          color: form.plan_key === p.id ? C.accent : C.text,
                        }}
                      >
                        {p.label}
                      </span>
                      <span style={{ fontSize: 11, color: C.muted }}>{p.quota}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.muted,
                    fontWeight: 600,
                    marginBottom: 10,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  Numéro Twilio
                </div>
                <select
                  value={form.twilio_number}
                  onChange={(e) => set("twilio_number", e.target.value)}
                  style={{
                    width: "100%",
                    background: C.card,
                    border: `1px solid ${C.border}`,
                    borderRadius: 10,
                    padding: "10px 14px",
                    color: C.text,
                    fontSize: 13,
                    fontFamily: "inherit",
                    cursor: "pointer",
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
            </div>
          )}

          {/* Step 2 : Assistant */}
          {step === 2 && (
            <div>
              <div
                style={{
                  fontSize: 12,
                  color: C.muted,
                  fontWeight: 600,
                  marginBottom: 14,
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                Choisir l'assistant vocal
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {ASSISTANTS.map((a) => {
                  const active = form.assistant_id === a.id;
                  return (
                    <div
                      key={a.id}
                      onClick={() => set("assistant_id", a.id)}
                      style={{
                        borderRadius: 14,
                        overflow: "hidden",
                        cursor: "pointer",
                        border: `2px solid ${active ? C.accent : C.border}`,
                        boxShadow: active ? "0 0 16px rgba(0,229,160,0.25)" : "none",
                        transform: active ? "scale(1.02)" : "scale(1)",
                        transition: "all 0.2s",
                        background: C.bg,
                        position: "relative",
                      }}
                    >
                      <div style={{ position: "relative", height: 100, background: C.bg }}>
                        <img
                          src={a.img}
                          alt={a.prenom}
                          style={{
                            width: "100%",
                            height: "100%",
                            objectFit: "cover",
                            objectPosition: "top",
                            mixBlendMode: "luminosity",
                            filter: active ? "brightness(1.15)" : "brightness(0.8) saturate(0.7)",
                            position: "relative",
                            zIndex: 1,
                            transition: "filter 0.25s",
                          }}
                        />
                        {active && (
                          <div
                            style={{
                              position: "absolute",
                              top: 6,
                              right: 6,
                              zIndex: 2,
                              width: 20,
                              height: 20,
                              borderRadius: "50%",
                              background: C.accent,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 11,
                              fontWeight: 800,
                              color: C.bg,
                            }}
                          >
                            ✓
                          </div>
                        )}
                      </div>
                      <div
                        style={{
                          padding: "8px 10px",
                          background: active ? "rgba(0,229,160,0.08)" : C.card,
                        }}
                      >
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 700,
                            color: active ? C.accent : C.text,
                          }}
                        >
                          {a.prenom}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 3 : Récapitulatif */}
          {step === 3 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: 13, color: C.muted, marginBottom: 4 }}>
                Vérifiez les informations avant création :
              </div>
              {[
                ["Cabinet", form.name],
                ["Email", form.email],
                ["Téléphone", form.phone],
                ["Secteur", SECTORS.find((s) => s.id === form.sector)?.label],
                ["Plan", PLANS.find((p) => p.id === form.plan_key)?.label],
                ["Assistant", ASSISTANTS.find((a) => a.id === form.assistant_id)?.prenom],
                ["Numéro", form.twilio_number || "À assigner plus tard"],
                ["Email accès", form.send_welcome ? "✓ Oui" : "Non"],
              ].map(([l, v]) => (
                <div
                  key={l}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: C.card,
                    borderRadius: 8,
                  }}
                >
                  <span style={{ fontSize: 12, color: C.muted }}>{l}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: C.text }}>{v}</span>
                </div>
              ))}

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 12px",
                  background: C.card,
                  borderRadius: 8,
                }}
              >
                <span style={{ fontSize: 12, color: C.muted }}>Envoyer email de bienvenue</span>
                <div
                  onClick={() => set("send_welcome", !form.send_welcome)}
                  style={{
                    width: 36,
                    height: 20,
                    borderRadius: 10,
                    cursor: "pointer",
                    background: form.send_welcome ? C.accent : C.border,
                    position: "relative",
                    transition: "background 0.2s",
                  }}
                >
                  <div
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: "50%",
                      background: C.text,
                      position: "absolute",
                      top: 3,
                      left: form.send_welcome ? 19 : 3,
                      transition: "left 0.2s",
                    }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 4 : Résultat */}
          {step === 4 && result && (
            <div style={{ textAlign: "center", padding: "10px 0" }}>
              {result.success ? (
                <>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 800,
                      color: C.accent,
                      marginBottom: 8,
                    }}
                  >
                    Client créé avec succès !
                  </div>
                  {result.results?.errors?.length > 0 && (
                    <div
                      style={{
                        background: "rgba(255,179,71,0.1)",
                        border: "1px solid rgba(255,179,71,0.3)",
                        borderRadius: 10,
                        padding: 12,
                        marginBottom: 16,
                        fontSize: 12,
                        color: "#FFB347",
                        textAlign: "left",
                      }}
                    >
                      ⚠️ Avertissements :<br />
                      {result.results.errors.map((e, i) => (
                        <div key={i}>• {e}</div>
                      ))}
                    </div>
                  )}
                  <div
                    style={{
                      textAlign: "left",
                      background: C.card,
                      borderRadius: 12,
                      padding: 16,
                      marginBottom: 20,
                      fontSize: 13,
                      color: C.text,
                    }}
                  >
                    <div style={{ marginBottom: 8 }}>✅ Tenant créé</div>
                    <div style={{ marginBottom: 8 }}>
                      ✅ Assistant Vapi : {ASSISTANTS.find((a) => a.id === form.assistant_id)?.prenom || form.assistant_id}
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      ✅ Numéro Twilio : {result.results?.twilio_number || form.twilio_number || "—"}
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      ✅ Stripe : {PLANS.find((p) => p.id === form.plan_key)?.label || form.plan_key}
                    </div>
                    <div style={{ marginBottom: 0 }}>
                      ✅ Email envoyé à : {form.email}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, flexDirection: "column" }}>
                    <button
                      onClick={() => {
                        onClose?.();
                        navigate(`/admin/tenants/${result.tenant_id}`);
                      }}
                      style={{
                        width: "100%",
                        padding: 12,
                        borderRadius: 12,
                        background: C.card,
                        border: `1px solid ${C.border}`,
                        color: C.text,
                        fontSize: 14,
                        fontWeight: 700,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      Voir la fiche client
                    </button>
                    <button
                      onClick={() => {
                        const url = getClientWelcomeLoginUrl(form.email);
                        navigator.clipboard?.writeText(url).then(() => {
                          /* feedback optionnel */
                        });
                      }}
                      style={{
                        width: "100%",
                        padding: 12,
                        borderRadius: 12,
                        background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                        border: "none",
                        color: C.bg,
                        fontSize: 14,
                        fontWeight: 800,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      Copier le lien dashboard
                    </button>
                    <button
                      onClick={onClose}
                      style={{
                        width: "100%",
                        padding: 10,
                        borderRadius: 12,
                        background: "transparent",
                        border: `1px solid ${C.border}`,
                        color: C.muted,
                        fontSize: 13,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      Fermer
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 700,
                      color: C.danger,
                      marginBottom: 8,
                    }}
                  >
                    Erreur lors de la création
                  </div>
                  <div style={{ fontSize: 13, color: C.muted, marginBottom: 16 }}>
                    {result.error}
                  </div>
                  <button
                    onClick={() => setStep(3)}
                    style={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: 10,
                      padding: "10px 20px",
                      color: C.text,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    Réessayer
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer navigation */}
        {step < 4 && (
          <div
            style={{
              padding: "0 28px 24px",
              display: "flex",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <button
              onClick={() => (step > 0 ? setStep((s) => s - 1) : onClose())}
              style={{
                padding: "11px 20px",
                borderRadius: 11,
                background: C.card,
                border: `1px solid ${C.border}`,
                color: C.muted,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {step === 0 ? "Annuler" : "← Retour"}
            </button>

            {step < 3 ? (
              <button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canNext()}
                style={{
                  padding: "11px 24px",
                  borderRadius: 11,
                  background: canNext()
                    ? `linear-gradient(135deg,${C.accent},${C.accentDim})`
                    : C.border,
                  border: "none",
                  color: canNext() ? C.bg : C.muted,
                  fontSize: 13,
                  fontWeight: 800,
                  cursor: canNext() ? "pointer" : "not-allowed",
                  fontFamily: "inherit",
                  transition: "all 0.2s",
                }}
              >
                Suivant →
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={submitting}
                style={{
                  padding: "11px 24px",
                  borderRadius: 11,
                  background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                  border: "none",
                  color: C.bg,
                  fontSize: 13,
                  fontWeight: 800,
                  cursor: submitting ? "wait" : "pointer",
                  fontFamily: "inherit",
                }}
              >
                {submitting ? "Création en cours…" : "🚀 Créer le client"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <div>
      <div
        style={{
          fontSize: 12,
          color: "#6B90A8",
          fontWeight: 600,
          marginBottom: 6,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {label}
      </div>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: "100%",
          background: "#132840",
          border: "1px solid #1E3D56",
          borderRadius: 10,
          padding: "11px 14px",
          color: "#FFFFFF",
          fontSize: 13,
          fontFamily: "inherit",
          outline: "none",
        }}
      />
    </div>
  );
}
