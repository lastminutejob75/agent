import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const C = {
  bg: "var(--bg, #0a0f1a)",
  card: "var(--card, #111827)",
  border: "var(--border, #1e293b)",
  text: "var(--text, #f1f5f9)",
  muted: "var(--muted, #64748b)",
  accent: "var(--accent, #00e5a0)",
  accentDim: "var(--accent-dim, #00b87c)",
  danger: "var(--danger, #ff6b6b)",
};

export default function AppAgenda() {
  const navigate = useNavigate();
  const [step, setStep] = useState("choice");
  const [me, setMe] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [calendarId, setCalendarId] = useState("");
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const [verifySuccess, setVerifySuccess] = useState(false);
  const [contactSoftware, setContactSoftware] = useState("pabau");
  const [contactOther, setContactOther] = useState("");
  const [contactLoading, setContactLoading] = useState(false);
  const [contactSent, setContactSent] = useState(false);
  const [noneLoading, setNoneLoading] = useState(false);
  const [noneDone, setNoneDone] = useState(false);

  useEffect(() => {
    Promise.all([api.tenantMe(), api.agendaConfig()])
      .then(([m, c]) => {
        setMe(m);
        setConfig(c);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const isConnected = me?.calendar_provider === "google" && me?.calendar_id;
  const isNone = me?.calendar_provider === "none";
  const serviceAccountEmail = config?.service_account_email || import.meta.env.VITE_SERVICE_ACCOUNT_EMAIL || "uwi-bot@xxx.iam.gserviceaccount.com";

  const handleVerifyGoogle = async () => {
    if (!calendarId.trim()) return;
    setVerifyLoading(true);
    setVerifyError("");
    setVerifySuccess(false);
    try {
      const res = await api.agendaVerifyGoogle(calendarId.trim());
      if (res?.ok) {
        setVerifySuccess(true);
        setMe((m) => ({ ...m, calendar_provider: "google", calendar_id: calendarId.trim() }));
      } else {
        setVerifyError(res?.reason === "permission" ? "Accès refusé. Vérifiez que vous avez bien partagé le calendrier avec " + serviceAccountEmail : "Erreur lors de la vérification. Réessayez.");
      }
    } catch {
      setVerifyError("Erreur de connexion. Réessayez.");
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleContactRequest = async () => {
    setContactLoading(true);
    setContactSent(false);
    try {
      await api.agendaContactRequest(contactSoftware, contactSoftware === "autre" ? contactOther : "");
      setContactSent(true);
    } catch {
      setVerifyError("Erreur lors de l'envoi. Réessayez.");
    } finally {
      setContactLoading(false);
    }
  };

  const handleActivateNone = async () => {
    setNoneLoading(true);
    setNoneDone(false);
    try {
      await api.agendaActivateNone();
      setNoneDone(true);
      setMe((m) => ({ ...m, calendar_provider: "none", calendar_id: "" }));
    } catch {
      setVerifyError("Erreur. Réessayez.");
    } finally {
      setNoneLoading(false);
    }
  };

  const cardStyle = {
    border: `1px solid ${C.border}`,
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
    background: C.card,
    cursor: "pointer",
  };

  const btnStyle = {
    padding: "10px 20px",
    borderRadius: 10,
    background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
    color: C.bg,
    border: "none",
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
  };

  if (loading) {
    return (
      <div className="page">
        <div className="dcard">
          <p style={{ color: C.muted }}>Chargement…</p>
        </div>
      </div>
    );
  }

  if (step === "google_instructions") {
    return (
      <div className="page">
        <div className="dcard">
          <button type="button" onClick={() => setStep("choice")} style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", marginBottom: 16 }}>← Retour</button>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Connecter Google Calendar</h2>
          <ol style={{ color: C.text, fontSize: 14, lineHeight: 1.8, marginBottom: 24 }}>
            <li>Ouvrez Google Calendar sur votre ordinateur</li>
            <li>Cliquez sur les 3 points à côté de votre calendrier → Paramètres</li>
            <li>Allez dans « Partager avec des personnes spécifiques »</li>
            <li>Ajoutez : <code style={{ background: C.border, padding: "2px 6px", borderRadius: 6 }}>{serviceAccountEmail}</code> avec les droits « Modifier les événements »</li>
            <li>Copiez l'ID du calendrier (format : xxx@group.calendar.google.com)</li>
          </ol>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, color: C.muted, marginBottom: 6 }}>ID de votre calendrier Google</label>
            <input
              type="text"
              value={calendarId}
              onChange={(e) => setCalendarId(e.target.value)}
              placeholder="xxx@group.calendar.google.com"
              style={{ width: "100%", padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
            />
          </div>
          <button type="button" onClick={handleVerifyGoogle} disabled={verifyLoading || !calendarId.trim()} style={btnStyle}>
            {verifyLoading ? "Vérification…" : "Vérifier et activer"}
          </button>
          {verifyError && <p style={{ color: C.danger, marginTop: 12, fontSize: 14 }}>❌ {verifyError}</p>}
          {verifySuccess && <p style={{ color: C.accent, marginTop: 12, fontSize: 14 }}>✅ Agenda connecté ! Votre assistant est opérationnel.</p>}
        </div>
      </div>
    );
  }

  if (step === "contact_request") {
    return (
      <div className="page">
        <div className="dcard">
          <button type="button" onClick={() => setStep("choice")} style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", marginBottom: 16 }}>← Retour</button>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Logiciel métier</h2>
          <p style={{ color: C.muted, marginBottom: 20, fontSize: 14 }}>Pabau, Maiia, Doctolib, ou autre logiciel de cabinet. Notre équipe vous contacte pour finaliser la connexion.</p>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 12, color: C.muted, marginBottom: 6 }}>Quel logiciel ?</label>
            <select
              value={contactSoftware}
              onChange={(e) => setContactSoftware(e.target.value)}
              style={{ width: "100%", padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
            >
              <option value="pabau">Pabau</option>
              <option value="maiia">Maiia</option>
              <option value="doctolib">Doctolib</option>
              <option value="autre">Autre</option>
            </select>
          </div>
          {contactSoftware === "autre" && (
            <div style={{ marginBottom: 16 }}>
              <input
                type="text"
                value={contactOther}
                onChange={(e) => setContactOther(e.target.value)}
                placeholder="Précisez le logiciel"
                style={{ width: "100%", padding: 12, borderRadius: 10, border: `1px solid ${C.border}`, background: C.bg, color: C.text }}
              />
            </div>
          )}
          <button type="button" onClick={handleContactRequest} disabled={contactLoading} style={btnStyle}>
            {contactLoading ? "Envoi…" : "Envoyer la demande"}
          </button>
          {contactSent && <p style={{ color: C.accent, marginTop: 12, fontSize: 14 }}>✅ Demande envoyée. Notre équipe vous contacte sous 24h pour finaliser la connexion.</p>}
        </div>
      </div>
    );
  }

  if (step === "activate_none") {
    return (
      <div className="page">
        <div className="dcard">
          {noneDone ? (
            <>
              <p style={{ color: C.accent, fontSize: 16, marginBottom: 16 }}>✅ Mode sans agenda activé. Votre assistant prend les rendez-vous dans son propre système.</p>
              <button type="button" onClick={() => navigate("/app")} style={btnStyle}>Retour au dashboard</button>
            </>
          ) : (
            <p style={{ color: C.muted }}>{noneLoading ? "Activation…" : "Erreur. "}<button type="button" onClick={() => setStep("choice")} style={{ background: "none", border: "none", color: C.accent, cursor: "pointer", textDecoration: "underline" }}>Retour</button></p>
          )}
        </div>
      </div>
    );
  }

  if (isConnected || isNone) {
    return (
      <div className="page">
        <div className="dcard">
          <div className="ch">
            <div className="ch-left">
              <div className="ch-ico ico-t">📆</div>
              <div><div className="ch-title">Mon agenda</div></div>
            </div>
          </div>
          <div style={{ padding: "24px 0" }}>
            {isConnected ? (
              <>
                <p style={{ color: C.text, marginBottom: 8 }}>Google Calendar connecté : <code style={{ fontSize: 12, opacity: 0.9 }}>{me.calendar_id}</code></p>
                <p style={{ color: C.muted, fontSize: 13 }}>Votre assistant vocal utilise ce calendrier pour proposer des créneaux et enregistrer les rendez-vous.</p>
              </>
            ) : (
              <p style={{ color: C.text }}>Mode sans agenda externe. L'assistant gère les rendez-vous dans son propre système.</p>
            )}
            <button type="button" onClick={() => { setStep("choice"); setVerifySuccess(false); setVerifyError(""); }} style={{ ...btnStyle, marginTop: 16, background: C.border, color: C.text }}>Modifier</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="dcard">
        <div className="ch">
          <div className="ch-left">
            <div className="ch-ico ico-t">📆</div>
            <div><div className="ch-title">Connecter votre agenda</div><div className="ch-sub">Choisissez comment votre assistant gère les rendez-vous</div></div>
          </div>
        </div>
        <div style={{ padding: "24px 0" }}>
          <div style={cardStyle} onClick={() => setStep("google_instructions")}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>📅</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Google Calendar</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Partagez votre calendrier existant avec notre assistant</div>
            <div style={{ color: C.accent, fontSize: 14 }}>Voir les instructions →</div>
          </div>
          <div style={cardStyle} onClick={() => setStep("contact_request")}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>📋</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Logiciel métier</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Pabau, Maiia, Doctolib, ou autre logiciel de cabinet</div>
            <div style={{ color: C.accent, fontSize: 14 }}>Nous contacter pour setup →</div>
          </div>
          <div
            style={cardStyle}
            onClick={() => {
              setStep("activate_none");
              handleActivateNone();
            }}
          >
            <div style={{ fontSize: 24, marginBottom: 8 }}>⏰</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Sans agenda externe</div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>L'assistant prend les RDV dans son propre calendrier</div>
            <div style={{ color: C.accent, fontSize: 14 }}>Activer →</div>
          </div>
        </div>
      </div>
    </div>
  );
}
