import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { adminApi } from "../../../lib/adminApi.js";
import CreateTenantStepper, { CREATION_STEP_LABELS } from "../../components/tenants/CreateTenantStepper.jsx";
import { T } from "../../theme.js";

const C = { bg: T.bgPage, card: T.bgCard, border: T.border, accent: T.teal, text: T.text, muted: T.textMuted, danger: T.red, navy: "#071A33" };

const inputStyle = {
  display: "block",
  width: "100%",
  marginTop: 4,
  padding: "10px 12px",
  border: `1px solid ${C.border}`,
  borderRadius: 12,
  background: C.card,
  color: C.text,
  fontSize: 14,
};
const labelStyle = { display: "block", fontSize: 12, fontWeight: 700, color: C.muted, marginBottom: 4 };

function Field({ label, children }) {
  return (
    <label style={labelStyle}>
      {label}
      {children}
    </label>
  );
}

function PlanCard({ title, detail, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: 16,
        borderRadius: 20,
        border: `2px solid ${selected ? T.teal : C.border}`,
        background: selected ? T.tealLight : C.card,
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "inherit",
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 900, color: C.text }}>{title}</div>
      <div style={{ marginTop: 6, fontSize: 13, fontWeight: 600, color: C.muted, lineHeight: 1.45 }}>{detail}</div>
    </button>
  );
}

function slugifyHint(parts) {
  return parts
    .join("-")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function sectorForApi(profession) {
  const value = (profession || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (value.includes("dent")) return "dentiste";
  if (value.includes("kine")) return "kine";
  if (value.includes("infirm")) return "infirmier";
  if (value.includes("general")) return "medecin_generaliste";
  return "specialiste";
}

export default function AdminTenantCreate() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fromLead = (searchParams.get("fromLead") || "").trim();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [fromLeadData, setFromLeadData] = useState(null);
  const [form, setForm] = useState({
    cabinetName: "",
    practitionerName: "",
    tenantType: "solo",
    profession: "",
    city: "",
    address: "",
    currentPhone: "",
    contactEmail: "",
    plan: "trial",
    channelVoice: true,
    channelPublicPage: true,
    channelWebChat: false,
    channelWhatsapp: false,
    voiceSetupMode: "later",
    vapiMode: "later",
    vapiAssistantId: "",
    calendarProvider: "none",
    calendarId: "",
    rulesDraft:
      "Horaires, jours fermés, motifs autorisés/refusés, durée RDV, nouveaux patients, urgences, transfert humain, documents à apporter.",
    ownerEmail: "",
    sendInviteLater: true,
  });

  const hintSlug = useMemo(
    () => slugifyHint([form.practitionerName, form.profession, form.city].filter(Boolean)),
    [form.practitionerName, form.profession, form.city],
  );

  const progress = Math.round(((step + 1) / CREATION_STEP_LABELS.length) * 100);

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  useEffect(() => {
    let cancelled = false;
    if (!fromLead) {
      setFromLeadData(null);
      return;
    }
    adminApi
      .leadGet(fromLead)
      .then((lead) => {
        if (cancelled || !lead) return;
        setFromLeadData(lead);
        setForm((prev) => ({
          ...prev,
          cabinetName: lead.cabinet_name || prev.cabinetName,
          practitionerName: lead.contact_name || lead.assistant_name || prev.practitionerName,
          profession: lead.profession || lead.medical_specialty_label || lead.medical_specialty || prev.profession,
          city: lead.city || prev.city,
          contactEmail: lead.email || prev.contactEmail,
          currentPhone: lead.callback_phone || prev.currentPhone,
          tenantType: lead.tenant_type === "multi_practitioner" ? "multi" : prev.tenantType,
          plan:
            lead.calls_per_day === "100+" || lead.daily_call_volume === "100+"
              ? "growth"
              : lead.offer_suggested === "starter"
                ? "starter"
                : "trial",
          channelVoice: true,
          channelPublicPage: true,
          channelWebChat: true,
          rulesDraft: [
            prev.rulesDraft,
            lead.pain_point || lead.primary_pain_point ? `Douleur lead: ${lead.pain_point || lead.primary_pain_point}` : "",
            lead.objection ? `Objection lead: ${lead.objection}` : "",
            lead.calls_per_day || lead.daily_call_volume ? `Appels/jour: ${lead.calls_per_day || lead.daily_call_volume}` : "",
            lead.has_assistant != null ? `Assistante: ${lead.has_assistant ? "oui" : "non"}` : "",
            lead.source_detail || lead.source ? `Source: ${lead.source_detail || lead.source}` : "",
          ]
            .filter(Boolean)
            .join("\n"),
        }));
      })
      .catch(() => {
        if (!cancelled) setFromLeadData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [fromLead]);

  const planKeyForApi = () => {
    // Tous les abonnements créés par le provisioning complet démarrent par
    // un essai Stripe de 30 jours. Le choix "trial" utilise donc Growth.
    if (form.plan === "trial") return "growth";
    if (form.plan === "starter") return "starter";
    if (form.plan === "growth") return "growth";
    if (form.plan === "pro") return "pro";
    return "";
  };

  async function finish() {
    setErrorMsg("");
    setLoading(true);
    try {
      const name = form.cabinetName.trim();
      const email = form.contactEmail.trim().toLowerCase();
      const phone = form.currentPhone.trim();
      if (!name || name.length < 2) throw new Error("Nom du cabinet trop court.");
      if (!email) throw new Error("Email cabinet requis.");
      if (phone.length < 5) throw new Error("Téléphone cabinet requis.");

      const notesPayload = {
        wizard: "tenant_create_v1",
        practitioner: form.practitionerName.trim(),
        tenant_type: form.tenantType,
        city: form.city.trim(),
        address: form.address.trim(),
        channels: {
          voice: form.channelVoice,
          public_page: form.channelPublicPage,
          web_chat: form.channelWebChat,
          whatsapp: form.channelWhatsapp,
        },
        vapi_mode: form.vapiMode,
        calendar_provider: form.calendarProvider,
      };

      const created = await adminApi.createTenantFull({
        name,
        email,
        owner_email: form.ownerEmail.trim().toLowerCase() || null,
        phone,
        sector: sectorForApi(form.profession),
        plan_key: planKeyForApi(),
        assistant_id: "sophie",
        timezone: "Europe/Paris",
        send_welcome: !form.sendInviteLater,
        lead_id: fromLead || null,
        vapi_mode: form.vapiMode,
        existing_vapi_assistant_id:
          form.vapiMode === "link" ? form.vapiAssistantId.trim() : null,
      });

      const tenantId = created.tenant_id || created.results?.tenant_id;
      if (!tenantId) throw new Error("Le provisioning n'a pas retourné de tenant.");
      const params = {
        creation_notes: JSON.stringify(notesPayload).slice(0, 1950),
        practitioner_name: form.practitionerName.trim(),
        business_name: name,
        specialty_label: (form.profession || "").trim(),
        contact_email: email,
        city: (form.city || "").trim(),
        address_line1: (form.address || "").trim(),
        phone_number: (form.currentPhone || "").trim(),
        tenant_type: form.tenantType,
        channel_voice_enabled: form.channelVoice ? "true" : "false",
        channel_public_page_enabled: form.channelPublicPage ? "true" : "false",
        channel_web_chat_enabled: form.channelWebChat ? "true" : "false",
        channel_whatsapp_enabled: form.channelWhatsapp ? "true" : "false",
        voice_setup_mode: form.voiceSetupMode,
        vapi_onboarding_mode: form.vapiMode,
        public_page_slug_hint: hintSlug,
        calendar_provider: form.calendarProvider || "none",
        calendar_id: (form.calendarId || "").trim(),
        onboarding_rules_draft: (form.rulesDraft || "").slice(0, 4000),
        owner_login_email: (form.ownerEmail || "").trim() || email,
      };
      if (form.vapiMode === "link" && form.vapiAssistantId.trim()) {
        params.vapi_assistant_id = form.vapiAssistantId.trim();
      }

      await adminApi.patchTenantParams(tenantId, params);
      navigate(`/admin/tenants/${tenantId}`);
    } catch (err) {
      const code = err?.data?.error_code;
      const detail = err?.data?.detail;
      if (err.status === 409 && code === "EMAIL_ALREADY_ASSIGNED") {
        setErrorMsg("Cet email est déjà rattaché à un autre client.");
      } else if (typeof detail === "string" && detail) {
        setErrorMsg(detail);
      } else if (Array.isArray(detail) && detail.length) {
        setErrorMsg(detail.map((x) => x?.msg ?? JSON.stringify(x)).join(" · "));
      } else {
        setErrorMsg(err.message || "Erreur lors de la création.");
      }
    } finally {
      setLoading(false);
    }
  }

  function renderStep() {
    if (step === 0) {
      return (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
          <Field label="Nom du cabinet *">
            <input style={inputStyle} value={form.cabinetName} onChange={(e) => set("cabinetName", e.target.value)} required minLength={2} />
          </Field>
          <Field label="Praticien principal">
            <input style={inputStyle} value={form.practitionerName} onChange={(e) => set("practitionerName", e.target.value)} />
          </Field>
          <Field label="Type">
            <select style={inputStyle} value={form.tenantType} onChange={(e) => set("tenantType", e.target.value)}>
              <option value="solo">Praticien seul</option>
              <option value="multi">Cabinet multi-praticiens</option>
            </select>
          </Field>
          <Field label="Profession / spécialité">
            <input style={inputStyle} value={form.profession} onChange={(e) => set("profession", e.target.value)} />
          </Field>
          <Field label="Ville">
            <input style={inputStyle} value={form.city} onChange={(e) => set("city", e.target.value)} />
          </Field>
          <Field label="Adresse">
            <input style={inputStyle} value={form.address} onChange={(e) => set("address", e.target.value)} />
          </Field>
          <Field label="Téléphone actuel du cabinet *">
            <input style={inputStyle} value={form.currentPhone} onChange={(e) => set("currentPhone", e.target.value)} placeholder="+33…" required minLength={5} />
          </Field>
          <Field label="Email cabinet *">
            <input style={inputStyle} type="email" value={form.contactEmail} onChange={(e) => set("contactEmail", e.target.value)} required />
          </Field>
        </div>
      );
    }
    if (step === 1) {
      return (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14 }}>
          <PlanCard
            title="Essai gratuit"
            detail="Sans engagement · onboarding guidé · Stripe checkout pour activer ensuite."
            selected={form.plan === "trial"}
            onClick={() => set("plan", "trial")}
          />
          <PlanCard title="Starter" detail="99 € · 400 min · dépassement facturé au passage." selected={form.plan === "starter"} onClick={() => set("plan", "starter")} />
          <PlanCard title="Growth" detail="149 € · 800 min · cabinet en croissance." selected={form.plan === "growth"} onClick={() => set("plan", "growth")} />
          <PlanCard title="Pro" detail="199 € · 1200 min · cabinets établis." selected={form.plan === "pro"} onClick={() => set("plan", "pro")} />
        </div>
      );
    }
    if (step === 2) {
      return (
        <div style={{ display: "grid", gap: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>Canaux</div>
          {[
            ["channelVoice", "Téléphone (vocal UWi)"],
            ["channelPublicPage", "Page publique"],
            ["channelWebChat", "Chat web"],
            ["channelWhatsapp", "WhatsApp (plus tard)"],
          ].map(([key, lab]) => (
            <label key={key} style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 600, color: C.text }}>
              <input type="checkbox" checked={form[key]} onChange={(e) => set(key, e.target.checked)} />
              {lab}
            </label>
          ))}
          <Field label="Mode téléphonie prévu">
            <select style={inputStyle} value={form.voiceSetupMode} onChange={(e) => set("voiceSetupMode", e.target.value)}>
              <option value="later">À définir après création</option>
              <option value="dedicated_uwi_number">Numéro UWi dédié</option>
              <option value="call_forwarding">Redirection depuis le numéro actuel</option>
            </select>
          </Field>
          <div style={{ padding: 14, borderRadius: 16, border: `1px solid ${T.teal}44`, background: T.tealLight, fontSize: 13, color: C.navy, fontWeight: 600 }}>
            Slug page publique suggéré : <span style={{ fontFamily: "monospace" }}>{hintSlug || "—"}</span>
          </div>
        </div>
      );
    }
    if (step === 3) {
      return (
        <div style={{ display: "grid", gap: 14 }}>
          <Field label="Stratégie assistant">
            <select style={inputStyle} value={form.vapiMode} onChange={(e) => set("vapiMode", e.target.value)}>
              <option value="later">Reporter · configuration depuis la fiche client</option>
              <option value="create">Créer assistant Vapi (backend)</option>
              <option value="link">Lier assistant existant</option>
            </select>
          </Field>
          {form.vapiMode === "link" ? (
            <Field label="Vapi assistant ID">
              <input style={inputStyle} value={form.vapiAssistantId} onChange={(e) => set("vapiAssistantId", e.target.value)} placeholder="asst_…" />
            </Field>
          ) : null}
          <div style={{ fontSize: 13, color: C.muted, lineHeight: 1.55 }}>
            La clé Vapi reste côté serveur uniquement. Les actions « créer / tester » sont disponibles depuis la fiche tenant (backend).
          </div>
        </div>
      );
    }
    if (step === 4) {
      return (
        <div style={{ display: "grid", gap: 14 }}>
          <Field label="Fournisseur agenda">
            <select style={inputStyle} value={form.calendarProvider} onChange={(e) => set("calendarProvider", e.target.value)}>
              <option value="none">Pas encore · hors ligne</option>
              <option value="google">Google Calendar</option>
            </select>
          </Field>
          <Field label="Calendar ID (si Google)">
            <input style={inputStyle} value={form.calendarId} onChange={(e) => set("calendarId", e.target.value)} placeholder="primary ou agenda@group.calendar.google.com" />
          </Field>
        </div>
      );
    }
    if (step === 5) {
      return (
        <Field label="Règles d’accueil (brouillon)">
          <textarea
            style={{ ...inputStyle, minHeight: 160, resize: "vertical" }}
            value={form.rulesDraft}
            onChange={(e) => set("rulesDraft", e.target.value)}
          />
        </Field>
      );
    }
    if (step === 6) {
      return (
        <div style={{ display: "grid", gap: 14 }}>
          <Field label="Email de connexion propriétaire (optionnel, défaut = email cabinet)">
            <input style={inputStyle} type="email" value={form.ownerEmail} onChange={(e) => set("ownerEmail", e.target.value)} placeholder={form.contactEmail} />
          </Field>
          <label style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 600, color: C.text }}>
            <input type="checkbox" checked={form.sendInviteLater} onChange={(e) => set("sendInviteLater", e.target.checked)} />
            Envoyer l&apos;email de première connexion plus tard (depuis la fiche client)
          </label>
          {!form.sendInviteLater ? (
            <p style={{ margin: 0, fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
              Un compte login et un mot de passe temporaire seront envoyés immédiatement à{" "}
              {(form.ownerEmail || form.contactEmail).trim() || "l'email cabinet"}.
            </p>
          ) : null}
        </div>
      );
    }
    const checklist = [
      ["Tenant créé en base", true],
      ["Abonnement choisi", Boolean(form.plan)],
      ["Canaux définis", true],
      ["Assistant Vapi", form.vapiMode === "link" ? Boolean(form.vapiAssistantId.trim()) : form.vapiMode === "create"],
      ["Agenda", form.calendarProvider === "google" ? Boolean(form.calendarId.trim()) : true],
      ["Règles d’accueil", Boolean(form.rulesDraft.trim())],
      ["Accès client", Boolean((form.ownerEmail || form.contactEmail).trim())],
    ];
    return (
      <div style={{ display: "grid", gap: 10 }}>
        {checklist.map(([label, ok]) => (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: 14,
              borderRadius: 14,
              border: `1px solid ${C.border}`,
              background: C.card,
            }}
          >
            <span style={{ fontWeight: 900, color: ok ? T.green : T.orange }}>{ok ? "✓" : "!"}</span>
            <span style={{ fontWeight: 700, color: C.text }}>{label}</span>
          </div>
        ))}
        <div style={{ fontSize: 13, color: C.muted }}>
          Après création, la fiche client permet de finaliser Stripe, routage vocal, tests agenda et invitation utilisateur.
        </div>
      </div>
    );
  }

  return (
    <div className="uwi-create-tenant-page" style={{ padding: "28px 32px", background: C.bg, minHeight: "100vh" }}>
      <style>{`
        .uwi-create-tenant-layout { display:grid; grid-template-columns:minmax(260px,300px) minmax(0,1fr); gap:24px; align-items:start; }
        @media (max-width: 900px) {
          .uwi-create-tenant-page { padding:18px 16px 28px !important; }
          .uwi-create-tenant-layout { grid-template-columns:minmax(0,1fr); gap:16px; }
          .uwi-create-tenant-stepper { overflow-x:auto; }
        }
        @media (max-width: 520px) {
          .uwi-create-tenant-page { padding:14px 12px 24px !important; }
          .uwi-create-tenant-form { padding:16px !important; border-radius:18px !important; }
        }
      `}</style>
      <Link to="/admin/tenants" style={{ color: C.muted, marginBottom: 12, display: "inline-block", fontWeight: 700 }}>
        ← Clients
      </Link>

      <header style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 900, color: C.text, letterSpacing: -0.6, margin: 0 }}>Créer un client</h1>
          <p style={{ marginTop: 8, maxWidth: 560, fontSize: 14, color: C.muted, fontWeight: 500, lineHeight: 1.55 }}>
            Parcours en {CREATION_STEP_LABELS.length} étapes : identité, offre, canaux, assistant, agenda, règles d’accueil, accès client puis validation.
          </p>
        </div>
        <div style={{ borderRadius: 20, border: `1px solid ${C.border}`, background: C.card, padding: "14px 18px" }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: C.muted }}>Activation</div>
          <div style={{ fontSize: 28, fontWeight: 900, color: C.text }}>{progress}%</div>
        </div>
      </header>

      {errorMsg ? (
        <div style={{ marginBottom: 16, padding: "12px 16px", border: `1px solid ${T.red}40`, background: T.redLight, borderRadius: 14, color: C.danger, fontWeight: 600 }}>
          {errorMsg}
        </div>
      ) : null}
      {fromLeadData ? (
        <div
          style={{
            marginBottom: 16,
            padding: "12px 16px",
            borderRadius: 14,
            border: `1px solid ${T.teal}40`,
            background: T.tealLight,
            color: C.navy,
            fontSize: 13,
            fontWeight: 700,
            lineHeight: 1.45,
          }}
        >
          Création depuis lead : <strong>{fromLeadData.cabinet_name || fromLeadData.email || fromLead}</strong>
          <div style={{ marginTop: 4, fontSize: 12, fontWeight: 600, color: C.muted }}>
            Source : {fromLeadData.source_detail || fromLeadData.source || "Lead admin"}
          </div>
        </div>
      ) : null}

      <div className="uwi-create-tenant-layout">
        <div className="uwi-create-tenant-stepper"><CreateTenantStepper step={step} onStep={setStep} /></div>
        <section className="uwi-create-tenant-form" style={{ borderRadius: 26, border: `1px solid ${C.border}`, background: C.card, padding: 22, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 900, letterSpacing: "0.14em", color: T.teal }}>ÉTAPE {step + 1}</div>
            <h2 style={{ margin: "6px 0 0", fontSize: 22, fontWeight: 900, color: C.text }}>{CREATION_STEP_LABELS[step]}</h2>
          </div>
          {renderStep()}
          <div style={{ marginTop: 22, paddingTop: 18, borderTop: `1px solid ${C.border}`, display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "space-between" }}>
            <button
              type="button"
              disabled={step === 0 || loading}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              style={{
                padding: "12px 18px",
                borderRadius: 14,
                border: `1px solid ${C.border}`,
                background: C.card,
                fontWeight: 800,
                cursor: step === 0 ? "default" : "pointer",
                opacity: step === 0 ? 0.45 : 1,
              }}
            >
              Précédent
            </button>
            {step < CREATION_STEP_LABELS.length - 1 ? (
              <button
                type="button"
                onClick={() => setStep((s) => Math.min(CREATION_STEP_LABELS.length - 1, s + 1))}
                style={{
                  padding: "12px 22px",
                  borderRadius: 14,
                  border: "none",
                  background: C.navy,
                  color: "#fff",
                  fontWeight: 900,
                  cursor: "pointer",
                }}
              >
                Continuer →
              </button>
            ) : (
              <button
                type="button"
                disabled={loading}
                onClick={finish}
                style={{
                  padding: "12px 22px",
                  borderRadius: 14,
                  border: "none",
                  background: T.teal,
                  color: "#fff",
                  fontWeight: 900,
                  cursor: "pointer",
                  opacity: loading ? 0.65 : 1,
                }}
              >
                {loading ? "Création…" : "Créer et ouvrir la fiche"}
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
