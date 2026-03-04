import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { formatOpeningHoursPretty, getAmplitudeBadge, getAmplitudeScore } from "../../lib/openingHoursPretty.js";

const C = { bg: "#0A1828", card: "#132840", border: "#1E3D56", accent: "#00E5A0", text: "#FFFFFF", muted: "#6B90A8" };
const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
const STATUS_OPTIONS = [
  { value: "new", label: "Nouveau" },
  { value: "contacted", label: "Contacté" },
  { value: "converted", label: "Converti" },
  { value: "lost", label: "Perdu" },
];

function getLeadPriority(lead) {
  let score = 0;
  const vol = lead?.daily_call_volume;
  if (vol === "100+") score += 50;
  else if (vol === "50-100") score += 30;
  else if (vol === "25-50") score += 20;
  const spec = (lead?.medical_specialty || "").toLowerCase();
  if (spec === "centre_medical" || spec === "clinique_privee") score += 30;
  const pain = lead?.primary_pain_point || "";
  if (pain.includes("secrétariat n'arrive pas") || pain.includes("secrétariat est débordé")) score += 20;
  score += getAmplitudeScore(lead);
  if (score >= 70) return { score, label: "Haute priorité", style: { background: "rgba(255,107,107,0.2)", color: "#FF6B6B" } };
  if (score >= 40) return { score, label: "Moyenne", style: { background: "rgba(255,179,71,0.2)", color: "#FFB347" } };
  return { score, label: "Standard", style: { background: "rgba(107,144,168,0.2)", color: C.muted } };
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

const cardStyle = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 24 };
const h2Style = { fontSize: 11, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 16 };
const btnStyle = { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const btnPrimary = { ...btnStyle, background: C.accent, color: C.bg };
const btnSecondary = { ...btnStyle, background: "rgba(107,144,168,0.2)", color: C.muted };
const btnSuccess = { ...btnStyle, background: "rgba(16,185,129,0.3)", color: "#10B981" };
const btnDanger = { ...btnStyle, background: "rgba(107,144,168,0.3)", color: C.muted };
const btnActive = { ...btnStyle, background: C.accent, color: C.bg };
const ampBadgeStyle = (label) => {
  const isHigh = label?.includes("élevée");
  return { display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: isHigh ? "rgba(139,92,246,0.2)" : "rgba(56,189,248,0.2)", color: isHigh ? "#a78bfa" : "#38bdf8" };
};

export default function AdminLeadDetail() {
  const { id } = useParams();
  const [lead, setLead] = useState(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!id) return;
    adminApi
      .leadGet(id)
      .then(setLead)
      .catch(() => setLead(null));
  }, [id]);

  useEffect(() => {
    if (lead) setNotes(lead.notes ?? "");
  }, [lead]);

  const saveNotes = () => {
    if (!id) return;
    setSaving(true);
    adminApi
      .leadPatch(id, { notes })
      .then(() => setSaving(false))
      .catch(() => setSaving(false));
  };

  const setStatus = (status) => {
    if (!id) return;
    adminApi.leadPatch(id, { status }).then(() => {
      setLead((p) => (p ? { ...p, status } : null));
    });
  };

  const copyDirectLink = () => {
    const url = window.location.origin + window.location.pathname;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const contactLabel = (lead?.email?.trim() || lead?.callback_phone || "—");
  const hasEmail = !!(lead?.email && lead.email.trim());

  const copySummary = () => {
    if (!lead) return;
    const lines = [
      `Email: ${lead.email?.trim() || "—"}`,
      ...(lead.callback_phone ? [`Téléphone: ${lead.callback_phone}`] : []),
      `Spécialité: ${lead.medical_specialty_label || lead.medical_specialty || "—"}${lead.specialty_other ? ` – ${lead.specialty_other}` : ""}`,
      `Situation: ${lead.primary_pain_point || "—"}`,
      `Appels/jour: ${lead.daily_call_volume}`,
      `Assistante: ${lead.assistant_name} (voix ${lead.voice_gender === "female" ? "féminine" : "masculine"})`,
      `Rappel souhaité: ${lead.wants_callback ? (lead.callback_phone ? `Oui – ${lead.callback_phone}` : "Oui") : "Non"}`,
      `Source: ${lead.source || "landing_cta"}`,
      `Date: ${formatDate(lead.created_at)}`,
    ];
    lines.push("Horaires:");
    lines.push(formatOpeningHoursPretty(lead.opening_hours));
    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!lead && id) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
        <p style={{ color: C.muted }}>Chargement…</p>
      </div>
    );
  }
  if (!lead) {
    return (
      <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
        <p style={{ color: "#FF6B6B" }}>Lead non trouvé</p>
        <Link to="/admin/leads" style={{ color: C.accent, fontWeight: 600, marginTop: 8, display: "inline-block" }}>
          Retour à la liste
        </Link>
      </div>
    );
  }

  const mailto = hasEmail ? `mailto:${lead.email.trim()}?subject=UWi – Votre assistant ${lead.assistant_name}` : null;

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <Link to="/admin/leads" style={{ color: C.muted, fontSize: 14 }}>
          ← Leads
        </Link>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8 }}>Lead – {contactLabel}</h1>
      </div>

      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={h2Style}>Qualification</h2>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 24 }}>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Grand compte potentiel</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>
              {(lead.is_enterprise || lead.daily_call_volume === "100+") ? (
                <span style={{ color: "#FFB347" }}>Oui 🔥</span>
              ) : (
                "Non"
              )}
            </p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Appels/jour</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>{lead.daily_call_volume || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Spécialité</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>{lead.medical_specialty_label || lead.medical_specialty || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Douleur principale</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2, maxWidth: 200 }}>{lead.primary_pain_point || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Priorité</span>
            <p style={{ marginTop: 2 }}>
              {(() => {
                const prio = getLeadPriority(lead);
                return (
                  <span style={{ display: "inline-flex", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, ...prio.style }} title={`Score: ${prio.score}`}>
                    {prio.label}
                  </span>
                );
              })()}
            </p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: C.muted }}>Amplitude max / jour</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2, display: "flex", alignItems: "center", gap: 8 }}>
              {lead.max_daily_amplitude != null ? `${Number(lead.max_daily_amplitude).toFixed(1)} h` : "—"}
              {(() => {
                const amp = getAmplitudeBadge(lead);
                return amp ? <span style={ampBadgeStyle(amp.label)}>⏰ {amp.label}</span> : null;
              })()}
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
        <div style={cardStyle}>
          <h2 style={h2Style}>Informations</h2>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 14 }}>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Email:</strong> {hasEmail ? <a href={mailto} style={{ color: C.accent }}>{lead.email}</a> : "—"}</li>
            {lead.callback_phone && <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Téléphone:</strong> {lead.callback_phone}</li>}
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Spécialité:</strong> {lead.medical_specialty_label || lead.medical_specialty || "—"}{lead.specialty_other ? ` – ${lead.specialty_other}` : ""}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Situation:</strong> {lead.primary_pain_point || "—"}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Appels/jour:</strong> {lead.daily_call_volume}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Assistante:</strong> {lead.assistant_name}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Voix:</strong> {lead.voice_gender === "female" ? "Féminine" : "Masculine"}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Rappel souhaité:</strong> {lead.wants_callback ? (lead.callback_phone ? `Oui – ${lead.callback_phone}` : "Oui") : "Non"}</li>
            {lead.callback_booking_date && (
              <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Créneau rappel réservé:</strong> {lead.callback_booking_date} à {lead.callback_booking_slot || "—"}</li>
            )}
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Source:</strong> {lead.source || "landing_cta"}</li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: C.muted }}>Créé le:</strong> {formatDate(lead.created_at)}</li>
          </ul>
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            {hasEmail && (
              <a href={mailto} style={{ ...btnSecondary, textDecoration: "none" }}>
                Envoyer un email
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(lead.email?.trim() || lead.callback_phone || "");
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              style={btnSecondary}
            >
              Copier {hasEmail ? "l'email" : "le téléphone"}
            </button>
          </div>
        </div>

        <div style={cardStyle}>
          <h2 style={h2Style}>Horaires cabinet</h2>
          <pre style={{ fontSize: 14, color: C.text, whiteSpace: "pre-wrap", fontFamily: "inherit", margin: 0 }}>
            {formatOpeningHoursPretty(lead.opening_hours)}
          </pre>
        </div>
      </div>

      <div style={{ ...cardStyle, marginTop: 24 }}>
        <h2 style={h2Style}>Partage rapide</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <button type="button" onClick={copyDirectLink} style={btnSecondary}>
            {copiedLink ? "Lien copié !" : "Copier lien direct"}
          </button>
          <button type="button" onClick={copySummary} style={btnPrimary}>
            {copied ? "Copié !" : "Copier le résumé"}
          </button>
        </div>
      </div>

      <div style={{ ...cardStyle, marginTop: 24 }}>
        <h2 style={h2Style}>Actions rapides</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          <button type="button" onClick={() => setStatus("contacted")} style={btnSuccess}>
            Marquer contacté
          </button>
          <button type="button" onClick={() => setStatus("lost")} style={btnDanger}>
            Marquer perdu
          </button>
        </div>
        <h2 style={{ ...h2Style, marginBottom: 12 }}>Statut</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setStatus(opt.value)}
              style={lead.status === opt.value ? btnActive : btnSecondary}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <h2 style={{ ...h2Style, marginBottom: 8 }}>Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          style={{
            width: "100%",
            padding: "12px",
            borderRadius: 8,
            border: `1px solid ${C.border}`,
            background: C.card,
            color: C.text,
            fontSize: 14,
          }}
          placeholder="Notes internes…"
        />
        <button type="button" onClick={saveNotes} disabled={saving} style={{ ...btnPrimary, marginTop: 8, opacity: saving ? 0.6 : 1 }}>
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}
