import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { convertOpeningHours } from "../../lib/bookingUtils.js";
import { formatOpeningHoursPretty, getAmplitudeBadge, getAmplitudeScore } from "../../lib/openingHoursPretty.js";
import CreateTenantModal from "../components/CreateTenantModal.jsx";

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

const cardStyle = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 24, color: C.text };
const h2Style = { fontSize: 11, fontWeight: 700, color: "#9BB5C7", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 16 };
const btnStyle = { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const btnPrimary = { ...btnStyle, background: C.accent, color: C.bg };
const btnSecondary = { ...btnStyle, background: "#1E3D56", border: `1px solid ${C.border}`, color: "#E2E8F0" };
const btnSuccess = { ...btnStyle, background: "rgba(16,185,129,0.3)", color: "#10B981" };
const btnDanger = { ...btnStyle, background: "rgba(107,144,168,0.3)", color: "#E2E8F0" };
const btnActive = { ...btnStyle, background: C.accent, color: C.bg };
const ampBadgeStyle = (label) => {
  const isHigh = label?.includes("élevée");
  return { display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: isHigh ? "rgba(139,92,246,0.2)" : "rgba(56,189,248,0.2)", color: isHigh ? "#a78bfa" : "#38bdf8" };
};

const STATUS_LABELS = { new: "Nouveau", contacted: "Contacté", converted: "Converti", lost: "Perdu" };

export default function AdminLeadDetail() {
  const { id } = useParams();
  const [lead, setLead] = useState(null);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [followUpDate, setFollowUpDate] = useState("");
  const [followUpSaved, setFollowUpSaved] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [noteLog, setNoteLog] = useState([]);
  const [tenantModalNotice, setTenantModalNotice] = useState("");

  useEffect(() => {
    if (!id) return;
    adminApi
      .leadGet(id)
      .then(setLead)
      .catch(() => setLead(null));
  }, [id]);

  useEffect(() => {
    if (!lead) return;
    let parsed = [];
    try {
      if (typeof lead.notes_log === "string") {
        parsed = JSON.parse(lead.notes_log || "[]");
      } else if (Array.isArray(lead.notes_log)) {
        parsed = lead.notes_log;
      }
    } catch {
      /* ignore */
    }
    if (parsed.length === 0 && lead.notes) {
      parsed = [{ text: lead.notes, created_at: lead.created_at }];
    }
    setNoteLog(parsed);
    setFollowUpDate(lead.follow_up_at?.slice(0, 16) || "");
  }, [lead]);

  const VALID_SECTORS = ["medecin_generaliste", "specialiste", "kine", "dentiste", "infirmier"];
  const VALID_ASSISTANTS = ["sophie", "laura", "emma", "julie", "clara", "hugo", "julien", "nicolas", "alexandre", "thomas"];
  const tenantPrefill = lead
    ? {
        name: lead.cabinet_name || lead.email || "",
        email: lead.email || "",
        phone: lead.callback_phone || lead.phone || "",
        sector: VALID_SECTORS.includes(lead.medical_specialty) ? lead.medical_specialty : "medecin_generaliste",
        assistant_id: VALID_ASSISTANTS.includes(lead.assistant_name?.toLowerCase()) ? lead.assistant_name?.toLowerCase() : "sophie",
        plan_key:
          lead.daily_call_volume === "100+"
            ? "pro"
            : lead.daily_call_volume === "50-100"
              ? "growth"
              : "starter",
      }
    : {};
  const initialBookingRules = lead?.opening_hours ? convertOpeningHours(lead.opening_hours) : null;

  const handleStatusChange = async (newStatus) => {
    if (!id) return;
    const autoEntry = {
      text: `Statut changé → ${STATUS_LABELS[newStatus] || newStatus}`,
      action: "statut",
      created_at: new Date().toISOString(),
    };
    const updatedLog = [...noteLog, autoEntry];
    await adminApi.leadPatch(id, { status: newStatus, notes_log: JSON.stringify(updatedLog) });
    setLead((p) => (p ? { ...p, status: newStatus, notes_log: JSON.stringify(updatedLog) } : null));
    setNoteLog(updatedLog);
  };

  const handleConvertLead = () => {
    setTenantModalNotice("");
    setShowCreateTenant(true);
  };

  const handleTenantCreated = async (newTenant) => {
    if (!id) return;
    const entry = {
      text: `Tenant créé : ${newTenant?.name || lead?.cabinet_name || lead?.email || "Client"} (id: ${newTenant?.id || "—"})`,
      action: "conversion",
      created_at: new Date().toISOString(),
    };
    const updatedLog = [...noteLog, entry];
    try {
      await adminApi.leadPatch(id, {
        status: "converted",
        notes_log: JSON.stringify(updatedLog),
      });
      setLead((prev) =>
        prev
          ? { ...prev, status: "converted", notes_log: JSON.stringify(updatedLog) }
          : prev,
      );
      setNoteLog(updatedLog);
      setTenantModalNotice("");
    } catch (e) {
      setTenantModalNotice("Client créé, mais impossible de marquer le lead comme converti.");
    } finally {
      setShowCreateTenant(false);
    }
  };

  const handleTenantModalClose = () => {
    setShowCreateTenant(false);
    setTenantModalNotice("Création annulée — le lead n'a pas été modifié");
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
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", color: C.text }}>
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
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Grand compte potentiel</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>
              {(lead.is_enterprise || lead.daily_call_volume === "100+") ? (
                <span style={{ color: "#FFB347" }}>Oui 🔥</span>
              ) : (
                "Non"
              )}
            </p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Appels/jour</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>{lead.daily_call_volume || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Spécialité</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2 }}>{lead.medical_specialty_label || lead.medical_specialty || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Douleur principale</span>
            <p style={{ fontWeight: 600, color: C.text, marginTop: 2, maxWidth: 200 }}>{lead.primary_pain_point || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Priorité</span>
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
            <span style={{ fontSize: 11, color: "#9BB5C7" }}>Amplitude max / jour</span>
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
          <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 14, color: C.text }}>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Email:</strong> {hasEmail ? <a href={mailto} style={{ color: C.accent }}>{lead.email}</a> : <span style={{ color: C.text }}>—</span>}</li>
            {lead.callback_phone && <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Téléphone:</strong> <span style={{ color: C.text }}>{lead.callback_phone}</span></li>}
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Spécialité:</strong> <span style={{ color: C.text }}>{lead.medical_specialty_label || lead.medical_specialty || "—"}{lead.specialty_other ? ` – ${lead.specialty_other}` : ""}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Situation:</strong> <span style={{ color: C.text }}>{lead.primary_pain_point || "—"}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Appels/jour:</strong> <span style={{ color: C.text }}>{lead.daily_call_volume}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Assistante:</strong> <span style={{ color: C.text }}>{lead.assistant_name}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Voix:</strong> <span style={{ color: C.text }}>{lead.voice_gender === "female" ? "Féminine" : "Masculine"}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Rappel souhaité:</strong> <span style={{ color: C.text }}>{lead.wants_callback ? (lead.callback_phone ? `Oui – ${lead.callback_phone}` : "Oui") : "Non"}</span></li>
            {lead.callback_booking_date && (
              <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Créneau rappel réservé:</strong> <span style={{ color: C.text }}>{lead.callback_booking_date} à {lead.callback_booking_slot || "—"}</span></li>
            )}
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Source:</strong> <span style={{ color: C.text }}>{lead.source || "landing_cta"}</span></li>
            <li style={{ marginBottom: 8 }}><strong style={{ color: "#9BB5C7" }}>Créé le:</strong> <span style={{ color: C.text }}>{formatDate(lead.created_at)}</span></li>
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
          <a
            href={`https://www.uwiapp.com/demo?ref=${encodeURIComponent(lead.email || "")}`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: "linear-gradient(135deg, #00E5A0, #00b87c)",
              color: "#0A1828",
              borderRadius: 10,
              padding: "10px 18px",
              fontSize: 13,
              fontWeight: 800,
              textDecoration: "none",
              boxShadow: "0 4px 16px rgba(0,229,160,0.25)",
            }}
          >
            🎯 Envoyer la démo
          </a>
        </div>

        <h2 style={{ ...h2Style, marginTop: 24, marginBottom: 12 }}>Statut</h2>
        {tenantModalNotice && (
          <div
            style={{
              marginBottom: 12,
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(107,144,168,0.12)",
              border: "1px solid rgba(107,144,168,0.25)",
              color: "#C7D7E3",
              fontSize: 13,
            }}
          >
            {tenantModalNotice}
          </div>
        )}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {STATUS_OPTIONS.filter((opt) => opt.value !== "converted").map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleStatusChange(opt.value)}
              style={lead.status === opt.value ? btnActive : btnSecondary}
            >
              {opt.label}
            </button>
          ))}
          {lead.status === "converted" ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "8px 16px",
                borderRadius: 8,
                background: "rgba(16,185,129,0.18)",
                border: "1px solid rgba(16,185,129,0.35)",
                color: "#10B981",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              ✓ Client créé
            </span>
          ) : (
            <button
              type="button"
              onClick={handleConvertLead}
              style={{
                ...btnPrimary,
                fontWeight: 700,
              }}
            >
              ✨ Créer client
            </button>
          )}
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 11, color: "#6B90A8", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 }}>
            📅 Date de relance
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="datetime-local"
              value={followUpDate}
              onChange={(e) => setFollowUpDate(e.target.value)}
              style={{
                background: "#132840",
                border: "1px solid #1E3D56",
                borderRadius: 9,
                padding: "8px 12px",
                color: "#FFFFFF",
                fontSize: 13,
                fontFamily: "inherit",
                cursor: "pointer",
              }}
            />
            <button
              type="button"
              onClick={async () => {
                await adminApi.leadPatch(id, { follow_up_at: followUpDate });
                setFollowUpSaved(true);
                setTimeout(() => setFollowUpSaved(false), 2000);
              }}
              style={{
                padding: "8px 16px",
                borderRadius: 9,
                fontSize: 12,
                fontWeight: 700,
                background: followUpSaved ? "rgba(0,229,160,0.1)" : "#132840",
                border: `1px solid ${followUpSaved ? "#00E5A0" : "#1E3D56"}`,
                color: followUpSaved ? "#00E5A0" : "#6B90A8",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {followUpSaved ? "✓ Sauvegardé" : "Sauvegarder"}
            </button>
          </div>
        </div>

        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 11, color: "#6B90A8", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 }}>
            📝 Journal
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
            {noteLog.map((entry, i) => (
              <div key={i} style={{ background: "#0F2236", borderRadius: 10, padding: "10px 14px" }}>
                <div style={{ fontSize: 11, color: "#6B90A8", marginBottom: 4 }}>
                  {new Date(entry.created_at).toLocaleString("fr-FR")}
                  {entry.action && (
                    <span style={{ marginLeft: 8, color: "#00E5A0", fontWeight: 600 }}>· {entry.action}</span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: "#FFFFFF", lineHeight: 1.6 }}>{entry.text}</div>
              </div>
            ))}
            {noteLog.length === 0 && (
              <div style={{ fontSize: 13, color: "#6B90A8", fontStyle: "italic" }}>Aucune note pour l&apos;instant</div>
            )}
          </div>
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Ajouter une note..."
            rows={3}
            style={{
              width: "100%",
              background: "#0F2236",
              border: "1px solid #1E3D56",
              borderRadius: 10,
              padding: "10px 14px",
              color: "#FFFFFF",
              fontSize: 13,
              fontFamily: "inherit",
              resize: "vertical",
              outline: "none",
            }}
          />
          <button
            type="button"
            onClick={async () => {
              if (!newNote.trim()) return;
              const entry = { text: newNote.trim(), created_at: new Date().toISOString() };
              const updatedLog = [...noteLog, entry];
              await adminApi.leadPatch(id, { notes_log: JSON.stringify(updatedLog) });
              setNoteLog(updatedLog);
              setNewNote("");
            }}
            style={{
              marginTop: 8,
              padding: "9px 20px",
              borderRadius: 9,
              background: "linear-gradient(135deg, #00E5A0, #00b87c)",
              border: "none",
              color: "#0A1828",
              fontSize: 13,
              fontWeight: 800,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Ajouter au journal
          </button>
        </div>
      </div>

      {showCreateTenant && (
        <CreateTenantModal
          prefill={tenantPrefill}
          initialBookingRules={initialBookingRules}
          onClose={handleTenantModalClose}
          onCreated={handleTenantCreated}
        />
      )}
    </div>
  );
}
