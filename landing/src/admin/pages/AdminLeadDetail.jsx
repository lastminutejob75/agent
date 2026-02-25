import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { formatOpeningHoursPretty, getAmplitudeBadge, getAmplitudeScore } from "../../lib/openingHoursPretty.js";

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
  if (score >= 70) return { score, label: "Haute priorité", className: "bg-red-100 text-red-800" };
  if (score >= 40) return { score, label: "Moyenne", className: "bg-amber-100 text-amber-800" };
  return { score, label: "Standard", className: "bg-slate-100 text-slate-700" };
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

export default function AdminLeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
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

  const contactLabel = (lead.email?.trim() || lead.callback_phone || "—");
  const hasEmail = !!(lead.email && lead.email.trim());

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
      <div className="py-8">
        <p className="text-slate-500">Chargement…</p>
      </div>
    );
  }
  if (!lead) {
    return (
      <div className="py-8">
        <p className="text-red-600">Lead non trouvé</p>
        <Link to="/admin/leads" className="text-indigo-600 hover:underline mt-2 inline-block">
          Retour à la liste
        </Link>
      </div>
    );
  }

  const mailto = hasEmail ? `mailto:${lead.email.trim()}?subject=UWi – Votre assistant ${lead.assistant_name}` : null;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link to="/admin/leads" className="text-slate-500 hover:text-slate-700 text-sm">
          ← Leads
        </Link>
        <h1 className="text-2xl font-bold text-slate-800">Lead – {contactLabel}</h1>
      </div>

      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-4">Qualification</h2>
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <span className="text-xs text-slate-500">Grand compte potentiel</span>
            <p className="font-semibold text-slate-800">
              {(lead.is_enterprise || lead.daily_call_volume === "100+") ? (
                <span className="text-amber-700">Oui 🔥</span>
              ) : (
                "Non"
              )}
            </p>
          </div>
          <div>
            <span className="text-xs text-slate-500">Appels/jour</span>
            <p className="font-semibold text-slate-800">{lead.daily_call_volume || "—"}</p>
          </div>
          <div>
            <span className="text-xs text-slate-500">Spécialité</span>
            <p className="font-semibold text-slate-800">{lead.medical_specialty_label || lead.medical_specialty || "—"}</p>
          </div>
          <div>
            <span className="text-xs text-slate-500">Douleur principale</span>
            <p className="font-semibold text-slate-800 max-w-xs">{lead.primary_pain_point || "—"}</p>
          </div>
          <div>
            <span className="text-xs text-slate-500">Priorité</span>
            <p>
              {(() => {
                const prio = getLeadPriority(lead);
                return (
                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${prio.className}`} title={`Score: ${prio.score}`}>
                    {prio.label}
                  </span>
                );
              })()}
            </p>
          </div>
          <div>
            <span className="text-xs text-slate-500">Amplitude max / jour</span>
            <p className="font-semibold text-slate-800 flex items-center gap-2">
              {lead.max_daily_amplitude != null ? `${Number(lead.max_daily_amplitude).toFixed(1)} h` : "—"}
              {(() => {
                const amp = getAmplitudeBadge(lead);
                return amp ? <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${amp.className}`}>⏰ {amp.label}</span> : null;
              })()}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase mb-4">Informations</h2>
          <ul className="space-y-2 text-sm">
            <li><strong>Email:</strong> {hasEmail ? <a href={mailto} className="text-indigo-600 hover:underline">{lead.email}</a> : "—"}</li>
            {lead.callback_phone && <li><strong>Téléphone:</strong> {lead.callback_phone}</li>}
            <li><strong>Spécialité:</strong> {lead.medical_specialty_label || lead.medical_specialty || "—"}{lead.specialty_other ? ` – ${lead.specialty_other}` : ""}</li>
            <li><strong>Situation:</strong> {lead.primary_pain_point || "—"}</li>
            <li><strong>Appels/jour:</strong> {lead.daily_call_volume}</li>
            <li><strong>Assistante:</strong> {lead.assistant_name}</li>
            <li><strong>Voix:</strong> {lead.voice_gender === "female" ? "Féminine" : "Masculine"}</li>
            <li><strong>Rappel souhaité:</strong> {lead.wants_callback ? (lead.callback_phone ? `Oui – ${lead.callback_phone}` : "Oui") : "Non"}</li>
            <li><strong>Source:</strong> {lead.source || "landing_cta"}</li>
            <li><strong>Créé le:</strong> {formatDate(lead.created_at)}</li>
          </ul>
          <div className="mt-4 flex gap-2">
            {hasEmail && (
              <a href={mailto} className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200">
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
              className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
            >
              Copier {hasEmail ? "l'email" : "le téléphone"}
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2">Horaires cabinet</h2>
          <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans">
            {formatOpeningHoursPretty(lead.opening_hours)}
          </pre>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2">Partage rapide</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={copyDirectLink}
            className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
          >
            {copiedLink ? "Lien copié !" : "Copier lien direct"}
          </button>
          <button
            type="button"
            onClick={copySummary}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
          >
            {copied ? "Copié !" : "Copier le résumé"}
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2">Actions rapides</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            type="button"
            onClick={() => setStatus("contacted")}
            className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
          >
            Marquer contacté
          </button>
          <button
            type="button"
            onClick={() => setStatus("lost")}
            className="px-4 py-2 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-700"
          >
            Marquer perdu
          </button>
        </div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-3">Statut</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setStatus(opt.value)}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${
                lead.status === opt.value
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2 mt-4">Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Notes internes…"
        />
        <button
          type="button"
          onClick={saveNotes}
          disabled={saving}
          className="mt-2 px-4 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}
